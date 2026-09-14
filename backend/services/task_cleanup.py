"""V2.2.0 T9：容量/保留/cleanup（PLAN §2.4 / Gate §6.4）。

触发点（调用方决定）：应用启动、任务进入终态、超过记录/字节阈值时扫描。
本模块只做幂等清理，限定 runtime 任务数据（task 表 + 本任务写入的 artifact 引用），
失败可见，绝不误删活动任务 / 已发布 artifact / 相邻文件。

对 Revision 1（无持久 profile / 无"当前页面引用"持久指针）的保守解释：

- **永不自动清理**（保护对象，§2.4"不得清理"）：
    - `DRAFT / READY / RUNNING / CANCELLING`（活动/工作台/当前页面）；
    - `SUCCEEDED`（工作台状态保留到用户开始新任务；已发布 DOCX/PDF 保留到用户主动删除）。
- **可自动清理**（§2.4"FAILED/CANCELLED 保留 24 小时"）：
    - `FAILED / CANCELLED` 且已过保留期（`expires_at`，缺省则按 `updated_at + 24h`）；
    - 指向已不存在 Task 的孤立子记录（InputRevision / TaskSubtask / TaskSnapshot / TaskEvent）。

约束（超限按最旧优先清理可清理对象，绝不触碰保护对象）：
- 可清理终态保留条数 ≤ `MAX_KEEP_TERMINAL`(20)；
- 任务临时状态（artifact 正文之外）总量 ≤ `TASK_TEMPORARY_TOTAL_LIMIT_BYTES`(16 MiB)。

文件策略：FAILED/CANCELLED 在 P4 装配链中不发布 artifact（仅 SUCCEEDED 发布），
因此本工具无可自动删除的产物文件；孤儿/相邻文件一律不动，防止误删。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from core.task import (
    DRAFT_EXPIRES_HOURS,
    FAILED_OR_CANCELLED_EXPIRES_HOURS,
    MAX_KEEP_TERMINAL,
    TASK_TEMPORARY_TOTAL_LIMIT_BYTES,
)
from database.models import (
    InputRevision,
    Task,
    TaskEvent,
    TaskSnapshot,
    TaskSubtask,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.utcnow()


def _json_bytes(obj: Any) -> int:
    return len(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


# 可清理的终态（FAILED/CANCELLED；SUCCEEDED 属保护对象）
_CLEANABLE_TERMINAL = ("FAILED", "CANCELLED")


def _task_temp_bytes(db: Session, task: Task) -> int:
    """单任务在临时表（InputRevision/Subtask/Snapshot/Event + Task 元数据）中的字节估算。"""
    total = _json_bytes({
        "t": task.status, "rev": task.current_input_revision, "op": task.active_operation_id,
        "err": task.terminal_error, "seq": task.seq,
    })
    for rev in (db.query(InputRevision).filter_by(task_id=task.task_id).all()
                if task else []) and (db.query(InputRevision)
                                      .filter_by(task_id=task.task_id).all()):
        total += _json_bytes({"r": rev.revision, "n": rev.name, "p": rev.phone,
                              "e": rev.email, "l": rev.location, "j": rev.jd})
    for st in db.query(TaskSubtask).filter_by(task_id=task.task_id).all():
        total += _json_bytes({"st": st.sort_order, "fr": st.fact_results or [],
                              "fc": st.failure_code})
    snap = db.query(TaskSnapshot).filter_by(task_id=task.task_id).first()
    if snap is not None:
        total += _json_bytes({"sp": snap.payload or {}})
    for ev in db.query(TaskEvent).filter_by(task_id=task.task_id).all():
        total += _json_bytes({"ev": ev.payload or {}})
    return total


def _total_temp_bytes(db: Session) -> int:
    """全部任务临时状态（artifact 正文之外）总量。"""
    total = 0
    for t in db.query(Task).all():
        total += _task_temp_bytes(db, t)
    # 孤立子记录（无父 Task）也要计入临时总量
    task_ids = {t.task_id for t in db.query(Task).all()}
    for rev in db.query(InputRevision).all():
        if rev.task_id not in task_ids:
            total += _json_bytes({"r": rev.revision, "j": rev.jd})
    for st in db.query(TaskSubtask).all():
        if st.task_id not in task_ids:
            total += _json_bytes({"fr": st.fact_results or []})
    for snap in db.query(TaskSnapshot).all():
        if snap.task_id not in task_ids:
            total += _json_bytes({"sp": snap.payload or {}})
    for ev in db.query(TaskEvent).all():
        if ev.task_id not in task_ids:
            total += _json_bytes({"ev": ev.payload or {}})
    return total


def _delete_task(db: Session, task: Task) -> None:
    """删除 Task 及其全部子记录（无 ORM 级联，显式删除；孤儿一并清掉）。"""
    for rev in db.query(InputRevision).filter_by(task_id=task.task_id).all():
        db.delete(rev)
    for st in db.query(TaskSubtask).filter_by(task_id=task.task_id).all():
        db.delete(st)
    snap = db.query(TaskSnapshot).filter_by(task_id=task.task_id).first()
    if snap is not None:
        db.delete(snap)
    for ev in db.query(TaskEvent).filter_by(task_id=task.task_id).all():
        db.delete(ev)
    db.delete(task)
    # 会话 autoflush=False：显式 flush，保证后续 _total_temp_bytes / 计数取到真实删后状态
    # （否则 pending 删除在重查询下仍被计入，16MiB 收敛循环与 summary 会失真）。
    db.flush()


def _clean_orphan_children(db: Session) -> int:
    """清理指向不存在 Task 的孤立子记录，返回删除条数。"""
    task_ids = {t.task_id for t in db.query(Task.task_id).all()}
    n = 0
    for model in (InputRevision, TaskSubtask, TaskSnapshot, TaskEvent):
        for row in db.query(model).all():
            if row.task_id not in task_ids:
                db.delete(row)
                n += 1
    return n


def run_cleanup(
    db: Session,
    *,
    now: Optional[datetime] = None,
    keep: int = MAX_KEEP_TERMINAL,
    temp_limit: int = TASK_TEMPORARY_TOTAL_LIMIT_BYTES,
) -> dict[str, Any]:
    """执行一次幂等清理。

    返回 summary（供测试断言）。只操作任务临时表，不改 artifact 文件。
    绝不删除保护对象（活动状态 + SUCCEEDED）。失败可见（抛/记日志），非静默。
    """
    now = now or _utcnow()
    summary: dict[str, Any] = {
        "deleted_tasks": 0,
        "deleted_children": 0,
        "protected_kept": 0,
        "cleaned_tasks": 0,
        "temporary_bytes_before": 0,
        "temporary_bytes_after": 0,
    }
    summary["temporary_bytes_before"] = _total_temp_bytes(db)

    # 1) 孤立子记录
    summary["deleted_children"] = _clean_orphan_children(db)

    # 2) 可清理终态候选：FAILED/CANCELLED，最旧优先
    hours = timedelta(hours=FAILED_OR_CANCELLED_EXPIRES_HOURS)

    def _past_retention(t: Task) -> bool:
        return (t.expires_at is not None and t.expires_at <= now) or (
            t.expires_at is None and (t.updated_at or now) <= now - hours
        )

    candidates = (db.query(Task)
                  .filter(Task.status.in_(_CLEANABLE_TERMINAL))
                  .order_by(Task.updated_at.asc())  # 最旧优先
                  .all())

    # 3) 20 条上限：只保留最新 keep 条，删超过的最旧候选
    if len(candidates) > keep:
        excess = len(candidates) - keep
        for t in candidates[:excess]:
            _delete_task(db, t)
            summary["deleted_tasks"] += 1
        candidates = candidates[excess:]

    # 4) 保留期：最新 keep 条中已过保留期的同样可清（FAILED/CANCELLED 保留 24h）
    survived: list[Task] = []
    for t in candidates:
        if _past_retention(t):
            _delete_task(db, t)
            summary["deleted_tasks"] += 1
        else:
            survived.append(t)
    candidates = survived

    # 5) 16 MiB 上限：超限时最旧优先清剩余可清理终态，直至达标
    while _total_temp_bytes(db) > temp_limit and candidates:
        t = candidates.pop(0)
        _delete_task(db, t)
        summary["deleted_tasks"] += 1
    # 若已无可清理对象仍超限：保留保护对象不删，上报可见（不可自动再压低）。
    if _total_temp_bytes(db) > temp_limit:
        logger.warning("T9 cleanup: 16MiB 超限且无可清理终态可再降"
                       "(temporary_bytes=%s)", _total_temp_bytes(db))

    # 保护对象计数（供测试证明未误删）
    summary["protected_kept"] = db.query(Task).filter(
        Task.status.notin_(_CLEANABLE_TERMINAL)).count()
    summary["cleaned_tasks"] = summary["deleted_tasks"]
    summary["temporary_bytes_after"] = _total_temp_bytes(db)
    db.flush()
    return summary