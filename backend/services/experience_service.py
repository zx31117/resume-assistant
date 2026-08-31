"""经历业务服务（无 AI，无 LangChain）。

V1.5.0 R1：Experience CRUD 全生命周期。
- create 立即生成确定性 Fact（不等下次迁移）
- update 对新增、修改、删除的来源项做 reconciliation，更新 revision/hash 并同事务失效旧向量
- delete 清理 Fact、FactEmbedding，不留孤儿
- SchemaVersion 只门控一次性 schema/data 升级，不承担日常 CRUD 同步
- 自身不调用 LLM、不直接计算 embedding，也不 import langchain。
- build_index_text / metadata 保留为公开工具方法供其他模块复用。
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from database import models
from database.models import Fact, FactEmbedding, EmbeddingStatus
from database.migrations import _iter_fact_candidates, _upsert_fact, derive_fact_id

logger = logging.getLogger(__name__)


def build_index_text(exp: models.Experience) -> str:
    """拼接用于向量化的文本（纯业务，无 AI）。"""
    parts = [exp.title, exp.role, exp.company, exp.description]
    parts += exp.skills or []
    parts += exp.achievements or []
    return "\n".join([p for p in parts if p])


def metadata(exp: models.Experience) -> dict:
    """向量 metadata（公开化，供其他模块复用）。"""
    return {
        "user_id": exp.user_id or "",
        "type": exp.type or "",
        "title": exp.title or "",
        "skills": ",".join(exp.skills or []),
    }


# 兼容旧内部命名（其他模块若 import _metadata 仍可用）
_metadata = metadata


def _reconcile_facts(db: Session, exp: models.Experience) -> dict:
    """R1: 对经历的 Fact 进行 reconciliation。

    根据当前 Experience 字段重新派生 Fact 候选，与现有 Fact 对比：
    - 新候选且无对应 Fact → 创建
    - 候选且 source_hash 变化 → 更新 text/revision/hash + 同事务失效旧向量
    - 现有 Fact 不再有对应候选 → 删除 Fact + 其 Embedding
    返回 {created, updated, noop, deleted, invalidated} 统计。
    """
    candidates = _iter_fact_candidates(exp)
    candidate_ids = {
        derive_fact_id(exp.id, c["source_field"], c["source_index"])
        for c in candidates
    }

    created = updated = noop = 0
    invalidated_facts: list[str] = []
    for cand in candidates:
        fid, status = _upsert_fact(db, exp.id, cand)
        if status == "created":
            created += 1
        elif status == "updated":
            updated += 1
            invalidated_facts.append(fid)
        else:
            noop += 1

    # 删除不再有对应候选的 Fact + 其 Embedding
    existing = db.query(Fact).filter(Fact.experience_id == exp.id).all()
    deleted = 0
    for fact in existing:
        if fact.fact_id not in candidate_ids:
            db.query(FactEmbedding).filter(FactEmbedding.fact_id == fact.fact_id).delete()
            db.delete(fact)
            deleted += 1

    # R4: 同事务失效被更新的 Fact 的旧向量（不单独提交）
    for fid in invalidated_facts:
        from services.embedding_service import invalidate_fact_embedding
        invalidate_fact_embedding(db, fid, commit=False)

    logger.info(
        "reconcile_facts: exp=%s created=%d updated=%d noop=%d deleted=%d invalidated=%d",
        exp.id, created, updated, noop, deleted, len(invalidated_facts),
    )
    return {
        "created": created, "updated": updated, "noop": noop,
        "deleted": deleted, "invalidated": invalidated_facts,
    }


def create_experience(db: Session, user_id: str, data: dict) -> models.Experience:
    """R1: 创建经历——立即生成确定性 Fact（同事务，W1）。

    V1.5.0 R1：create 后立即调用 _reconcile_facts 生成 Fact，
    不等下次迁移。SchemaVersion 不承担日常 CRUD 同步。

    W1：Experience 写入与 Fact reconciliation 在同一事务内完成；
    reconciliation 任一步失败即 rollback，不留下"无 Fact 的孤儿 Experience"。
    """
    exp = models.Experience(
        user_id=user_id,
        type=data.get("type", ""),
        title=data.get("title", ""),
        company=data.get("company", ""),
        time=data.get("time", ""),
        role=data.get("role", ""),
        description=data.get("description", ""),
        skills=data.get("skills", []) or [],
        achievements=data.get("achievements", []) or [],
        raw_text=data.get("raw_text", ""),
    )
    try:
        db.add(exp)
        db.flush()  # 分配 id（Python 端已生成，flush 确保 FK 顺序与可见性）
        # R1: 立即生成确定性 Fact（与 Experience 同事务）
        _reconcile_facts(db, exp)
        db.commit()
    except Exception:
        # W1: reconciliation 失败不得先提交 Experience——回滚留下无孤儿
        db.rollback()
        raise
    db.refresh(exp)
    _annotate_summary(db, [exp])
    return exp


def list_experiences(db: Session, user_id: str) -> list:
    exps = (
        db.query(models.Experience)
        .filter(models.Experience.user_id == user_id)
        .order_by(models.Experience.created_at.desc())
        .all()
    )
    _annotate_summary(db, exps)
    return exps


def _summarize_experiences(db: Session, exps: list) -> dict:
    """批量聚合每 Experience 的 Fact 数与 Embedding 汇总状态（避免 N+1）。

    summary_status：
      empty   —— 无 Fact（异常态，正常 create/update 后不应出现）
      failed  —— 任一 FactEmbedding 处于 FAILED
      pending —— 存在 Fact 但向量未全部就绪（PENDING/INVALID/缺失）
      ready   —— 存在 Fact 且全部 VALID
    """
    ids = [e.id for e in exps]
    empty = {e.id: {"fact_count": 0, "summary_status": "empty"} for e in exps}
    if not ids:
        return empty

    fact_counts = dict(
        db.query(Fact.experience_id, func.count(Fact.fact_id))
        .filter(Fact.experience_id.in_(ids))
        .group_by(Fact.experience_id)
        .all()
    )

    # 按 experience_id + status 聚合向量行数
    emb_rows = (
        db.query(Fact.experience_id, FactEmbedding.status, func.count(FactEmbedding.id))
        .join(FactEmbedding, FactEmbedding.fact_id == Fact.fact_id)
        .filter(Fact.experience_id.in_(ids))
        .group_by(Fact.experience_id, FactEmbedding.status)
        .all()
    )

    agg: dict[str, dict[str, int]] = {eid: {"PENDING": 0, "VALID": 0, "INVALID": 0, "FAILED": 0} for eid in ids}
    for exp_id, status, cnt in emb_rows:
        key = status.value if hasattr(status, "value") else str(status)
        bucket = agg.setdefault(exp_id, {"PENDING": 0, "VALID": 0, "INVALID": 0, "FAILED": 0})
        bucket[key] = bucket.get(key, 0) + (cnt or 0)

    out = {}
    for e in exps:
        fc = int(fact_counts.get(e.id, 0) or 0)
        a = agg.get(e.id, {"PENDING": 0, "VALID": 0, "INVALID": 0, "FAILED": 0})
        if fc == 0:
            status = "empty"
        elif a["FAILED"] > 0:
            status = "failed"
        elif a["PENDING"] > 0 or a["INVALID"] > 0 or a["VALID"] == 0:
            status = "pending"
        else:
            status = "ready"
        out[e.id] = {"fact_count": fc, "summary_status": status}
    return out


def _annotate_summary(db: Session, exps: list) -> None:
    """把汇总状态以动态属性写回 ORM 对象，供 ExperienceOut 序列化。"""
    summary = _summarize_experiences(db, exps)
    for exp in exps:
        s = summary.get(exp.id, {"fact_count": 0, "summary_status": "empty"})
        setattr(exp, "fact_count", s["fact_count"])
        setattr(exp, "summary_status", s["summary_status"])


def get_experience(db: Session, exp_id: str) -> Optional[models.Experience]:
    return db.query(models.Experience).filter(models.Experience.id == exp_id).first()


def update_experience(db: Session, exp_id: str, data: dict) -> Optional[models.Experience]:
    """R1: 更新经历——对 Fact 做 reconciliation（同事务，W1）。

    V1.5.0 R1：update 后调用 _reconcile_facts 对新增、修改、删除的来源项做
    reconciliation，更新 revision/hash 并同事务失效旧向量。不等下次迁移。

    W1：Experience 字段更新与 Fact reconciliation 在同一事务内完成；
    reconciliation 任一步失败即 rollback，不留下"新 Experience + 旧 Fact/Embedding"窗口。
    """
    exp = get_experience(db, exp_id)
    if not exp:
        return None
    try:
        for key in ["type", "title", "company", "time", "role", "description", "skills", "achievements", "raw_text"]:
            if key in data:
                setattr(exp, key, data[key])
        db.flush()
        # R1: 对 Fact 做 reconciliation（同事务失效旧向量）
        _reconcile_facts(db, exp)
        db.commit()
    except Exception:
        # W1: reconciliation 失败不得先提交 Experience——回滚保持旧一致状态
        db.rollback()
        raise
    db.refresh(exp)
    _annotate_summary(db, [exp])
    return exp


def delete_experience(db: Session, exp_id: str) -> bool:
    """R1: 删除经历——清理 Fact 与 FactEmbedding。

    V1.5.0 R1：delete 前显式删除其 Fact 的 FactEmbedding，再删除 Experience
    （级联删除 Fact）。不留孤儿向量行。
    """
    exp = get_experience(db, exp_id)
    if not exp:
        return False
    # R1: 先删除其 Fact 的 Embedding，再删除 Experience（级联删除 Fact）
    fact_ids = [f.fact_id for f in db.query(Fact).filter(Fact.experience_id == exp_id).all()]
    if fact_ids:
        db.query(FactEmbedding).filter(FactEmbedding.fact_id.in_(fact_ids)).delete(synchronize_session=False)
    db.delete(exp)
    db.commit()
    return True
