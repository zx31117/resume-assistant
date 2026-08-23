"""V1.5.0 Fact 服务层：显式修改与失效语义（PLAN §4.1 / §6.1.6）。

职责：
- modify_fact：用户显式修改 Fact 正文，更新 revision/content_hash + 时间戳
- 修改触发派生数据失效（旧向量 T3、旧 SelectedEvidenceSet T4）
- get/list 只读接口供选材与生成链路使用

边界（PLAN §3.3 / §4.1）：
- LLM、选材、生成链路不得调用写接口（modify_fact），不得写回事实库
- 只有用户明确的服务层操作才修改 Fact
- 失效钩子在 T2 为空占位；T3 注册向量失效，T4 注册 SelectedEvidenceSet 失效
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

# 失效回调：hook(fact_id, old_revision) → T3/T4 据此使引用旧 revision 的派生数据失效
_invalidation_hooks: list[Callable[[str, int], None]] = []


def register_invalidation_hook(fn: Callable[[str, int], None]) -> None:
    """T3/T4 注册派生数据失效回调（幂等追加）。"""
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


# ── 显式修改（PLAN §4.1 / §6.1.6） ───────────────────────────── #

def modify_fact(session: Session, fact_id: str, new_text: str) -> Fact:
    """显式修改 Fact 正文。

    - 更新 text、content_hash、revision+1、updated_at
    - 触发已注册失效钩子（旧向量/旧 SelectedEvidenceSet 引用旧 revision 失效）
    - 不修改 fact_type、source_*（类型与来源不可由正文修改改变）
    - 不允许空文本（空文本视为材料缺失，应删除而非修改）
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
    session.commit()
    logger.info(
        "Fact modified: fact_id=%s revision %d->%d",
        fact_id, old_revision, fact.revision,
    )

    for hook in _invalidation_hooks:
        try:
            hook(fact_id, old_revision)
        except Exception as e:
            logger.warning("invalidation hook error for fact_id=%s: %r", fact_id, e)
    return fact
