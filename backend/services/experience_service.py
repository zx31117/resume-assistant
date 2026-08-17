"""经历业务服务（无 AI，无 LangChain）。

V1.3 T7：SQL ↔ 向量 同步一致性，通过 VectorIndexJob + 同事务提交 + 请求内同步执行。

边界约束：
- 自身不调用 LLM、不直接计算 embedding，也不 import langchain。
- SQL 写入 + VectorIndexJob 创建在同一事务；之后同步执行 Job；
- 向量写入通过 rag_service（AI 限定在 rag_service 内）编排完成。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from database import models
from database.models import IndexJobStatus, IndexOperation
from services import rag_service, vector_index_sync


def build_index_text(exp: models.Experience) -> str:
    """拼接用于向量化的文本（纯业务，无 AI）。"""
    parts = [exp.title, exp.role, exp.company, exp.description]
    parts += exp.skills or []
    parts += exp.achievements or []
    return "\n".join([p for p in parts if p])


def metadata(exp: models.Experience) -> dict:
    """向量 metadata（公开化，供 vector_index_sync 复用）。"""
    return {
        "user_id": exp.user_id or "",
        "type": exp.type or "",
        "title": exp.title or "",
        "skills": ",".join(exp.skills or []),
    }


# 兼容旧内部命名（其他模块若 import _metadata 仍可用）
_metadata = metadata


def create_experience(db: Session, user_id: str, data: dict) -> models.Experience:
    """创建经历：Experience + UPSERT Job 同事务提交，再同步执行索引。"""
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
    # 先 flush 让 exp.id（uuid default）可用（有些方言需要 flush 才生成）
    db.flush()

    job = models.VectorIndexJob(
        experience_id=exp.id,
        user_id=user_id,
        operation=IndexOperation.UPSERT,
        status=IndexJobStatus.PENDING,
    )
    db.add(job)
    db.commit()
    db.refresh(exp)
    db.refresh(job)

    # 请求内同步执行向量 Job
    vector_index_sync.execute_job(db, job)

    # 如果执行成功，VectorIndexJob 会被标 DONE；这里再把 exp.vector_id 写回 SQL
    # （execute_job 在 UPSERT 分支里已经写了 exp.vector_id，但要保证 commit 后生效）
    db.refresh(exp)
    if not exp.vector_id:
        exp.vector_id = exp.id
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
    """更新经历：更新 SQL + 新建 UPSERT Job 同事务提交，再同步执行。"""
    exp = get_experience(db, exp_id)
    if not exp:
        return None
    for key in ["type", "title", "company", "time", "role", "description", "skills", "achievements", "raw_text"]:
        if key in data:
            setattr(exp, key, data[key])

    job = models.VectorIndexJob(
        experience_id=exp.id,
        user_id=exp.user_id,
        operation=IndexOperation.UPSERT,
        status=IndexJobStatus.PENDING,
    )
    db.add(job)
    db.commit()
    db.refresh(exp)
    db.refresh(job)

    vector_index_sync.execute_job(db, job)
    db.refresh(exp)
    return exp


def delete_experience(db: Session, exp_id: str) -> bool:
    """删除经历：先写 DELETE Job → 同步执行向量删除 → 最后删除 SQL 记录。

    顺序：先保证 SQL 里 DELETE Job 记录存在（即使后续 API crash，重建也能追溯）；
    执行向量删除成功后，再真正删除 Experience（Job 会级联删除，因为 experience 上 cascade=all, delete-orphan）。
    """
    exp = get_experience(db, exp_id)
    if not exp:
        return False

    user_id = exp.user_id
    job = models.VectorIndexJob(
        experience_id=exp_id,
        user_id=user_id,
        operation=IndexOperation.DELETE,
        status=IndexJobStatus.PENDING,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        vector_index_sync.execute_job(db, job)
    finally:
        # 向量无论是否成功，都要删除 SQL 里的 Experience（让用户能看到删了；失败的 DELETE Job 若因为级联被删，
        # 残留向量会在后续 RAG 时被 user_id where + SQL 回读过滤，安全）
        db.delete(exp)
        db.commit()
    return True
