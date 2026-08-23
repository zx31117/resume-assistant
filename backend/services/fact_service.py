"""V1.5.0 Fact 服务层：显式修改与失效语义（PLAN §4.1 / §6.1.6）。

R4：Fact 修改与失效一致性。
- modify_fact 在同一事务内更新 Fact revision/hash 并失效旧 Embedding
- 失效失败不得被 warning 消化，而是回滚整个事务
- 生产路径不依赖可选的进程内钩子碰巧已注册
- 钩子机制保留供测试/其他失效需求，但生产路径不依赖它

边界（PLAN §3.3 / §4.1）：
- LLM、选材、生成链路不得调用写接口（modify_fact），不得写回事实库
- 只有用户明确的服务层操作才修改 Fact
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable, Optional

from sqlalchemy.orm import Session

from core.errors import FactNotFoundError, FactModificationError
from database.migrations import _normalize_text, _sha256
from database.models import Fact

logger = logging.getLogger(__name__)

# 失效回调：hook(fact_id, old_revision) → 供测试/其他失效需求使用
# R4：生产路径不依赖此钩子，modify_fact 直接在事务内失效 Embedding
_invalidation_hooks: list[Callable[[str, int], None]] = []


def register_invalidation_hook(fn: Callable[[str, int], None]) -> None:
    """注册派生数据失效回调（幂等追加）。供测试或其他失效需求使用。"""
    if fn not in _invalidation_hooks:
        _invalidation_hooks.append(fn)


def clear_invalidation_hooks() -> None:
    """测试用：清空回调注册表。"""
    _invalidation_hooks.clear()


# ── 只读 ─────────────────────────────────────────────────────── #

def get_fact(session: Session, fact_id: str) -> Optional[Fact]:
    return session.get(Fact, fact_id)


def list_facts_for_experience(session: Session, experience_id: str) -> list[Fact]:
    return (
        session.query(Fact)
        .filter(Fact.experience_id == experience_id)
        .order_by(Fact.source_field, Fact.source_index)
        .all()
    )


def list_facts_for_experiences(session: Session, experience_ids: list[str]) -> list[Fact]:
    """批量取入选经历的全部 Fact（T4 第二层选材用）。"""
    if not experience_ids:
        return []
    return (
        session.query(Fact)
        .filter(Fact.experience_id.in_(experience_ids))
        .order_by(Fact.experience_id, Fact.source_field, Fact.source_index)
        .all()
    )


# ── 显式修改（PLAN §4.1 / §6.1.6 / R4） ──────────────────────── #

def modify_fact(session: Session, fact_id: str, new_text: str) -> Fact:
    """显式修改 Fact 正文（R4：同事务失效一致性）。

    - 更新 text、content_hash、revision+1、updated_at
    - R4: 在同一 session 内直接失效旧 Embedding（不单独提交）
    - 失效失败 → 回滚整个事务并抛 FactModificationError（不被 warning 消化）
    - 不修改 fact_type、source_*（类型与来源不可由正文修改改变）
    - 不允许空文本（空文本视为材料缺失，应删除而非修改）
    - 钩子保留供测试/其他需求，但生产路径不依赖它

    Raises:
      - FactNotFoundError: fact_id 不存在
      - FactModificationError: 空文本或同事务失效失败
    """
    fact = session.get(Fact, fact_id)
    if fact is None:
        raise FactNotFoundError(
            f"Fact 不存在: {fact_id}",
            details={"fact_id": fact_id},
        )
    normalized = _normalize_text(new_text)
    if not normalized:
        raise FactModificationError(
            f"Fact 正文不可为空: {fact_id}",
            details={"fact_id": fact_id},
        )
    if normalized == _normalize_text(fact.text or ""):
        # 内容未变，不 bump revision（避免误触发失效）
        return fact

    old_revision = fact.revision or 1
    fact.text = normalized
    fact.content_hash = _sha256(normalized)
    fact.revision = old_revision + 1
    fact.updated_at = datetime.utcnow()

    # R4: 同事务失效旧 Embedding——不依赖可选的进程内钩子
    # 直接在同一 session 内将旧 VALID 向量标记为 INVALID，不单独提交。
    # 这样 Fact 更新与向量失效在同一 commit 内完成，
    # 不存在"新 Fact 已提交但旧 Embedding 仍 VALID"的窗口。
    try:
        from services.embedding_service import invalidate_fact_embedding
        n_invalidated = invalidate_fact_embedding(session, fact_id, commit=False)
        logger.info(
            "R4 same-tx invalidation: fact_id=%s invalidated=%d embeddings",
            fact_id, n_invalidated,
        )
    except Exception as e:
        # R4: 失效失败不得被 warning 消化——回滚整个事务
        session.rollback()
        raise FactModificationError(
            f"Fact 修改失败：向量失效错误（同事务一致性）: {e}",
            details={"fact_id": fact_id, "invalidation_error": repr(e)},
        ) from e

    session.commit()
    logger.info(
        "Fact modified: fact_id=%s revision %d->%d",
        fact_id, old_revision, fact.revision,
    )

    # 保留钩子机制供测试/其他失效需求，但生产路径不依赖它
    for hook in _invalidation_hooks:
        try:
            hook(fact_id, old_revision)
        except Exception as e:
            logger.warning("invalidation hook error for fact_id=%s: %r", fact_id, e)
    return fact
