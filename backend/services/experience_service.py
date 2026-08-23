"""经历业务服务（无 AI，无 LangChain）。

V1.5.0：向量编排已退出本模块。
- 自身不调用 LLM、不直接计算 embedding，也不 import langchain。
- Experience CRUD 是纯 SQL；向量持久化统一走 FactEmbedding（由迁移触发，
  services/embedding_service.rebuild_embeddings 全量重建）。
- build_index_text / metadata 保留为公开工具方法供其他模块复用。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from database import models


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


def create_experience(db: Session, user_id: str, data: dict) -> models.Experience:
    """创建经历：纯 SQL 写入。

    V1.5.0：不再创建 VectorIndexJob，不做向量同步副作用。
    Fact 迁移与向量重建由 services/migrations.run_migrations 与
    embedding_service.rebuild_embeddings 在适当时机触发。
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
    db.add(exp)
    db.commit()
    db.refresh(exp)
    return exp


def list_experiences(db: Session, user_id: str) -> list:
    return (
        db.query(models.Experience)
        .filter(models.Experience.user_id == user_id)
        .order_by(models.Experience.created_at.desc())
        .all()
    )


def get_experience(db: Session, exp_id: str) -> Optional[models.Experience]:
    return db.query(models.Experience).filter(models.Experience.id == exp_id).first()


def update_experience(db: Session, exp_id: str, data: dict) -> Optional[models.Experience]:
    """更新经历：纯 SQL 更新。

    V1.5.0：不再创建 VectorIndexJob；Experience 内容变化后，
    Fact 迁移（migrations._upsert_fact）会在下次迁移执行时 bump revision，
    进而使旧 FactEmbedding 与旧 SelectedEvidenceSet 失效。
    """
    exp = get_experience(db, exp_id)
    if not exp:
        return None
    for key in ["type", "title", "company", "time", "role", "description", "skills", "achievements", "raw_text"]:
        if key in data:
            setattr(exp, key, data[key])
    db.commit()
    db.refresh(exp)
    return exp


def delete_experience(db: Session, exp_id: str) -> bool:
    """删除经历：纯 SQL 删除。

    V1.5.0：不再创建 DELETE Job；Experience 删除后级联删除其 Fact
    （cascade=all, delete-orphan），残留 FactEmbedding 在下次 rebuild 时清理。
    """
    exp = get_experience(db, exp_id)
    if not exp:
        return False
    db.delete(exp)
    db.commit()
    return True
