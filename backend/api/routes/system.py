"""V2.0.0 系统维护路由（PLAN §3.3 / §4.1）。

图形闭环的薄 API：status / migrate / rebuild / retry。
- 全部包装 manage.py CLI 已使用的同一 service / 迁移函数，行为与 CLI 等价且 fail-closed；
- 迁移、重建、重试共享并发门禁（与生成互斥，见 core.concurrency）；
- 不执行任何 shell、任意 SQL 或用户提交的本地路径。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter

from core import concurrency
from core.config import settings
from core.errors import MigrationError
from core.version import APP_VERSION
from database import models
from database.migrations import (
    SCHEMA_VERSION_FACT_MIGRATION,
    SCHEMA_VERSION_FACT_SCHEMA,
    run_migrations,
)
from database.session import SessionLocal
from services import embedding_service

logger = logging.getLogger(__name__)

router = APIRouter()


def _status_dict() -> dict:
    """组装系统状态快照（与 manage.py status 一致口径）。"""
    session = SessionLocal()
    try:
        applied = {row.version for row in session.query(models.SchemaVersion).all()}
        required = [SCHEMA_VERSION_FACT_SCHEMA, SCHEMA_VERSION_FACT_MIGRATION]
        missing = [v for v in required if v not in applied]
        fact_count = session.query(models.Fact).count()
        exp_count = session.query(models.Experience).count()
        emb = embedding_service.status_summary(session)

        pending = emb.get("PENDING", 0)
        failed = emb.get("FAILED", 0)
        invalid = emb.get("INVALID", 0)
        ready = bool(
            not missing
            and fact_count > 0
            and pending == 0
            and failed == 0
            and invalid == 0
        )

        next_steps: list[str] = []
        if missing:
            next_steps.append(f"需要运行迁移：{', '.join(missing)}（点按「初始化 / 迁移」）")
        if fact_count == 0:
            next_steps.append("尚无 Fact：请先到「履历库」导入或创建 Experience")
        if pending > 0 or failed > 0 or invalid > 0:
            next_steps.append(
                f"索引未就绪：PENDING={pending} FAILED={failed} INVALID={invalid}（点按「重建索引」）"
            )
        if ready:
            next_steps.append("就绪：可以前往「生成工作台」生成简历")

        return {
            "version": APP_VERSION,
            "migrations": {
                "applied": sorted(applied),
                "missing": missing,
                "applied_count": len(applied),
            },
            "counts": {"experience": exp_count, "fact": fact_count},
            "embeddings": emb,
            "ready": ready,
            "next_steps": next_steps,
        }
    finally:
        session.close()


@router.get("/status")
def status():
    """系统状态：版本、迁移、Experience/Fact/Embedding 汇总与下一步。"""
    return _status_dict()


@router.post("/migrate")
def migrate():
    """运行迁移（备份 + schema + Fact 迁移），与 manage.py migrate 等价。"""
    with concurrency.exclusive_operation("migrate"):
        try:
            summary = run_migrations(backup=True)
        except MigrationError:
            raise
    return {"ok": True, "summary": summary}


@router.post("/rebuild")
def rebuild():
    """全量重建 Embedding（PENDING/INVALID/FAILED），与 manage.py rebuild 等价。"""
    with concurrency.exclusive_operation("rebuild"):
        session = SessionLocal()
        try:
            summary = embedding_service.rebuild_embeddings(session)
        finally:
            session.close()
    return {"ok": True, "summary": summary}


@router.post("/retry")
def retry():
    """重试失败项（复用 rebuild_embeddings），与 manage.py retry 等价。"""
    with concurrency.exclusive_operation("retry"):
        session = SessionLocal()
        try:
            summary = embedding_service.rebuild_embeddings(session)
        finally:
            session.close()
    return {"ok": True, "summary": summary}