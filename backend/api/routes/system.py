"""V2.0.0 系统维护路由（PLAN §3.3 / §4.1）。

图形闭环的薄 API：status / migrate / rebuild / retry。
- 全部包装 manage.py CLI 已使用的同一 service / 迁移函数，行为与 CLI 等价且 fail-closed；
- 迁移、重建、重试共享并发门禁（与生成互斥，见 core.concurrency）；
- 不执行任何 shell、任意 SQL 或用户提交的本地路径。
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query

from core import concurrency
from core.config import settings
from core.errors import (
    DiagnosticsInvalidParamError,
    DiagnosticsUnavailableError,
    LogsClearError,
    OperationNotFoundError,
)
from core.operations import OperationStatus, OperationType, resolve_operation_id, tracker, valid_operation_id
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

# T4：诊断 API 只接受固定枚举筛选（PLAN §7.2 白名单），不接受任意用户输入。
_STATUS_WHITELIST = {s.value for s in OperationStatus}
_OPERATION_TYPE_WHITELIST = {t.value for t in OperationType}


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
def migrate(x_operation_id: Optional[str] = Header(default=None, alias="X-Operation-ID")):
    """运行迁移（备份 + schema + Fact 迁移），与 manage.py migrate 等价。

    V2.0.1（T3）：迁移真实阶段进入统一 operation 记录；operation_id 用于刷新复盘。
    """
    operation_id = resolve_operation_id(x_operation_id)
    with concurrency.exclusive_operation("migrate", operation_id=operation_id):
        with tracker.operation(OperationType.MIGRATE, operation_id=operation_id) as recording:
            summary = run_migrations(backup=True, recording=recording)
    return {"ok": True, "summary": summary, "operation_id": operation_id}


@router.post("/rebuild")
def rebuild(x_operation_id: Optional[str] = Header(default=None, alias="X-Operation-ID")):
    """全量重建 Embedding（PENDING/INVALID/FAILED），与 manage.py rebuild 等价。

    V2.0.1（T3）：重建真实阶段进入统一 operation 记录（PLAN §5.3）。
    """
    operation_id = resolve_operation_id(x_operation_id)
    with concurrency.exclusive_operation("rebuild", operation_id=operation_id):
        with tracker.operation(OperationType.REBUILD, operation_id=operation_id) as recording:
            session = SessionLocal()
            try:
                summary = embedding_service.rebuild_embeddings(session, recording=recording)
            finally:
                session.close()
    return {"ok": True, "summary": summary, "operation_id": operation_id}


@router.post("/retry")
def retry(x_operation_id: Optional[str] = Header(default=None, alias="X-Operation-ID")):
    """重试失败项（复用 rebuild_embeddings），与 manage.py retry 等价。

    V2.0.1（T3）：重试真实阶段进入统一 operation 记录（PLAN §5.3）。
    """
    operation_id = resolve_operation_id(x_operation_id)
    with concurrency.exclusive_operation("retry", operation_id=operation_id):
        with tracker.operation(OperationType.RETRY, operation_id=operation_id) as recording:
            session = SessionLocal()
            try:
                summary = embedding_service.rebuild_embeddings(session, recording=recording)
            finally:
                session.close()
    return {"ok": True, "summary": summary, "operation_id": operation_id}


# ── V2.0.1 T4：固定只读诊断 API（PLAN §7.2） ──────────────────── #
# 这些 GET 接口不获取生成/维护共享门禁，也不等待长事务（R1）；
# 只读 tracker 的内存注册表 + 独立文件快照，非法/越权输入一律稳定拒绝。


@router.get("/operations")
def list_operations(
    status: Optional[str] = Query(default=None),
    operation_type: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
):
    """活动/最近操作列表，支持固定枚举筛选与上限（PLAN §7.2）。"""
    if status is not None and status not in _STATUS_WHITELIST:
        raise DiagnosticsInvalidParamError(f"非法 status 筛选值：{status}")
    if operation_type is not None and operation_type not in _OPERATION_TYPE_WHITELIST:
        raise DiagnosticsInvalidParamError(f"非法 operation_type 筛选值：{operation_type}")
    operations = tracker.list_operations(status=status, operation_type=operation_type, limit=limit)
    return {"ok": True, "operations": operations, "diagnostics_health": tracker.health()}


@router.get("/operations/{operation_id}")
def get_operation(operation_id: str):
    """单次操作与完整阶段（路径参数严格校验 UUID，PLAN §7.2）。"""
    oid = valid_operation_id(operation_id)
    if oid is None:
        raise DiagnosticsInvalidParamError(f"非法 operation_id：{operation_id}")
    operation = tracker.get_operation(oid)
    if operation is None:
        raise OperationNotFoundError(f"未找到操作记录：{oid}")
    return {"ok": True, "operation": operation, "diagnostics_health": tracker.health()}


@router.get("/logs")
def read_logs(
    after_seq: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
):
    """按事件序号增量读取白名单日志（PLAN §3.4 / §7.2）。"""
    events = tracker.read_logs(after_seq=after_seq, limit=limit)
    return {"ok": True, "events": events, "diagnostics_health": tracker.health()}


@router.get("/diagnostics/{operation_id}")
def diagnostics(operation_id: str):
    """同一次操作的脱敏诊断摘要（PLAN §7.2）。"""
    oid = valid_operation_id(operation_id)
    if oid is None:
        raise DiagnosticsInvalidParamError(f"非法 operation_id：{operation_id}")
    summary = tracker.diagnostics(oid)
    if summary is None:
        raise DiagnosticsUnavailableError(f"诊断摘要不可用（日志已轮转或设施降级）：{oid}")
    return {"ok": True, "diagnostics": summary, "diagnostics_health": tracker.health()}


@router.delete("/logs")
def clear_logs():
    """受保护的历史日志清理（写操作，经统一本地管理安全校验，PLAN §7.2）。"""
    result = tracker.clear_logs()
    if not result.get("ok"):
        raise LogsClearError("历史日志清理失败")
    return {"ok": True}