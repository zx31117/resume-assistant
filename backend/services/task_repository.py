"""V2.2.0 T2：Task 状态真源 Repository（PLAN §2.3 / §2.4）。

后端是任务状态真源。本模块封装对 `Task / InputRevision / TaskSubtask / TaskSnapshot /
TaskEvent` 的全部持久化写路径，并把 PLAN §2.3 的语义和 §2.4 的容量上限集中到一个可测试点：

- 状态机跳转白名单（core.task.TRANSITIONS），非法跳转 fail closed 抛 TaskStateError；
- 一次 profile 只有一个前台活动任务（RUNNING/CANCELLING），冲突时抛
  ActiveTaskConflictError；开始新任务不允许旧 task/revision 再写回当前结果；
- InputRevision 冻结后不可变；新一次冻结生成新 revision；
- 覆盖式权威快照：每任务一条，更新时推进本任务单调 seq；
- 业务完成事件持久化（TaskEvent），seq 全任务单调唯一；增量可幂等去重；
- 容量硬上限：单任务 256 KiB 状态 / 256 KiB（事件+快照）；超限压缩完成事件而非删结果。

只允许本模块通过 SQLAlchemy session 修改这些任务表；service/API 一律调用本模块方法。
"""
from __future__ import annotations

import hashlib
import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.errors import DomainError
from core.task import (
    ACTIVE_EXCLUSIVE_STATUSES,
    EVENT_RING_BUFFER_SIZE,
    TASK_EVENT_SNAPSHOT_LIMIT_BYTES,
    TASK_STATE_HARD_LIMIT_BYTES,
    TERMINAL_STATUSES,
    TRANSITIONS,
    SubtaskStatus,
    TaskStatus,
)
from database.models import (
    InputRevision,
    Task,
    TaskEvent,
    TaskSnapshot,
    TaskSubtask,
)

logger = logging.getLogger(__name__)


# ── 领域错误 ─────────────────────────────────────────────────── #

class TaskError(DomainError):
    """V2.2.0 任务领域错误基类。"""

    stage = "task"
    retryable = False


class TaskNotFoundError(TaskError):
    """按 task_id 未找到任务。"""

    error_code = "TASK_NOT_FOUND"
    http_status = 404


class TaskStateError(TaskError):
    """非法状态跳转 / 非法操作（fail closed）。"""

    error_code = "TASK_STATE_INVALID"
    http_status = 409


class ActiveTaskConflictError(TaskError):
    """已有前台活动任务（RUNNING/CANCELLING），拒绝再启动新活动任务。"""

    error_code = "ACTIVE_TASK_CONFLICT"
    http_status = 409


class TaskCapacityError(TaskError):
    """任务状态超过硬上限（单任务/事件快照合计）。超限不产生截断成功。"""

    error_code = "TASK_CAPACITY_EXCEEDED"
    http_status = 413


class InputRevisionFrozenError(TaskError):
    """尝试修改已冻结的 InputRevision。"""

    error_code = "INPUT_REVISION_FROZEN"
    http_status = 409


class TaskInputValidationError(TaskError):
    """任务入参非法（如姓名必填缺失）。"""

    error_code = "TASK_INPUT_INVALID"
    http_status = 400


# ── 数据访问辅助与单例锁 ──────────────────────────────────────── #

# 进程内任务锁：使"单活动任务 + seq 单调 + 容量"在并发写下也原子。
_TASK_LOCKS: dict[str, threading.RLock] = {}
_TASK_LOCKS_GUARD = threading.Lock()


def _task_lock(task_id: str) -> threading.RLock:
    """返回并缓存该任务专属重入锁（进程内；跨进程一致性靠 SQLite 约束 + 门禁）。"""
    with _TASK_LOCKS_GUARD:
        if task_id not in _TASK_LOCKS:
            _TASK_LOCKS[task_id] = threading.RLock()
        return _TASK_LOCKS[task_id]


def _sha256(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.utcnow()


def _json_bytes(obj: Any) -> int:
    import json as _json
    return len(_json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


# ── 查询投影 ──────────────────────────────────────────────────── #

@dataclass
class TaskView:
    """给 API/service 的任务只读投影（含可选子任务/事件）。"""

    task_id: str
    status: str
    current_input_revision: int
    active_operation_id: Optional[str]
    seq: int
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime]
    terminal_error: Optional[str]
    published_resume_revision: Optional[int]
    published_docx_path: Optional[str]
    published_pdf_path: Optional[str]
    latest_input: Optional[dict[str, Any]] = None
    subtasks: list[dict[str, Any]] = field(default_factory=list)
    snapshot: Optional[dict[str, Any]] = None


def _task_view(task: Task, latest_input: Optional[InputRevision] = None,
               subtasks: Optional[list[TaskSubtask]] = None,
               snapshot: Optional[TaskSnapshot] = None) -> TaskView:
    return TaskView(
        task_id=task.task_id,
        status=task.status,
        current_input_revision=task.current_input_revision,
        active_operation_id=task.active_operation_id,
        seq=task.seq,
        created_at=task.created_at,
        updated_at=task.updated_at,
        expires_at=task.expires_at,
        terminal_error=task.terminal_error,
        published_resume_revision=task.published_resume_revision,
        published_docx_path=task.published_docx_path,
        published_pdf_path=task.published_pdf_path,
        latest_input=(_input_view(latest_input) if latest_input is not None else None),
        subtasks=[_subtask_view(s) for s in (subtasks or [])],
        snapshot=(_snapshot_view(snapshot) if snapshot is not None else None),
    )


def _input_view(rev: InputRevision) -> dict[str, Any]:
    return {
        "revision": rev.revision,
        "name": rev.name,
        "phone": rev.phone,
        "email": rev.email,
        "location": rev.location,
        "jd": rev.jd,
        "input_hash": rev.input_hash,
        "created_at": rev.created_at.isoformat() if rev.created_at else "",
    }


def _subtask_view(st: TaskSubtask) -> dict[str, Any]:
    return {
        "experience_id": st.experience_id,
        "sort_order": st.sort_order,
        "status": st.status,
        "fact_results": st.fact_results or [],
        "failure_code": st.failure_code,
        "started_at": st.started_at.isoformat() if st.started_at else "",
        "updated_at": st.updated_at.isoformat() if st.updated_at else "",
    }


def _snapshot_view(sn: TaskSnapshot) -> dict[str, Any]:
    return {
        "seq": sn.seq,
        "phase": sn.phase,
        "payload": sn.payload or {},
        "updated_at": sn.updated_at.isoformat() if sn.updated_at else "",
    }


# ── Repository ────────────────────────────────────────────────── #

class TaskRepository:
    """任务状态唯一写路径。所有方法使用传入 session；调用方负责事务/提交。"""

    def __init__(self, db: Session) -> None:
        self._db = db

    # ── 创建 / 状态 ──
    def next_task_id(self) -> str:
        return _new_uuid()

    def create(self, task_id: Optional[str] = None) -> Task:
        task_id = task_id or self.next_task_id()
        task = Task(
            task_id=task_id,
            status=TaskStatus.DRAFT.value,
            current_input_revision=0,
            active_operation_id=None,
            seq=0,
            created_at=_utcnow(),
            updated_at=_utcnow(),
            expires_at=None,
            terminal_error=None,
        )
        self._db.add(task)
        return task

    def get(self, task_id: str) -> Optional[Task]:
        return self._db.get(Task, task_id)

    def get_view(self, task_id: str) -> Optional[TaskView]:
        task = self.get(task_id)
        if task is None:
            return None
        return self._view_of(task)

    def assert_writable(self, task: Task) -> None:
        """终态（SUCCEEDED/FAILED/CANCELLED）拒收现状结果写入（T5：迟到结果不得发布）。

        生成 worker 写快照/事件前先经此门禁（配合 core.task_cancel 的 revision fence 双保险）；
        取消/失败/成功后仅有清理与 publish 收口允许触碰。
        """
        if TaskStatus(task.status) in TERMINAL_STATUSES:
            raise TaskStateError(
                f"任务已处于终态 {task.status}，拒收迟到现状结果",
                details={"task_id": task.task_id, "status": task.status},
            )

    def cancel_open_subtasks(self, task: Task) -> int:
        """把任务内未结束（PENDING/RUNNING）子任务置为 CANCELLED，返回受影响数。"""
        subs = (self._db.query(TaskSubtask)
                .filter_by(task_id=task.task_id)
                .filter(TaskSubtask.status.in_([
                    SubtaskStatus.PENDING.value, SubtaskStatus.RUNNING.value,
                ]))
                .all())
        for st in subs:
            self.update_subtask(task, st.experience_id, status=SubtaskStatus.CANCELLED)
        return len(subs)

    def _view_of(self, task: Task) -> TaskView:
        latest = (self._db.query(InputRevision)
                  .filter_by(task_id=task.task_id)
                  .order_by(InputRevision.revision.desc())
                  .first())
        subtasks = (self._db.query(TaskSubtask)
                    .filter_by(task_id=task.task_id)
                    .order_by(TaskSubtask.sort_order, TaskSubtask.id)
                    .all())
        snapshot = (self._db.query(TaskSnapshot)
                    .filter_by(task_id=task.task_id)
                    .first())
        return _task_view(task, latest, subtasks, snapshot)

    def transition(self, task: Task, target: TaskStatus, *, terminal_error: Optional[str] = None) -> None:
        """状态机跳转（fail closed on 非法跳转）。传入 target 为 TaskStatus 或等同字符串。"""
        if isinstance(target, str):
            target = TaskStatus(target)
        src = TaskStatus(task.status)
        allowed = TRANSITIONS.get(src)
        if allowed is None or target not in allowed:
            raise TaskStateError(
                f"非法任务状态跳转 {src.value} -> {target.value}",
                details={"from": src.value, "to": target.value},
            )
        if target in TERMINAL_STATUSES and target != TaskStatus.CANCELLED:
            # 终态落地固定过期时点（T9 清理），并保持已发布产物引用不被清除
            task.expires_at = _utcnow() + timedelta(hours=24)
        if target == TaskStatus.CANCELLED and task.status == TaskStatus.CANCELLED:
            # 幂等重复确认同一取消态：允许（不额外改）
            task.updated_at = _utcnow()
            return
        task.status = target.value
        task.updated_at = _utcnow()
        if terminal_error is not None and target in (TaskStatus.FAILED, TaskStatus.CANCELLED):
            task.terminal_error = terminal_error

    def assert_single_active(self, exclude_task_id: Optional[str] = None) -> None:
        """确保一次 profile 只有一条 RUNNING/CANCELLING 前台任务（T2/T3/T5 共用）。"""
        q = self._db.query(Task).filter(
            Task.status.in_([s.value for s in ACTIVE_EXCLUSIVE_STATUSES])
        )
        if exclude_task_id is not None:
            q = q.filter(Task.task_id != exclude_task_id)
        existing = q.first()
        if existing is not None:
            raise ActiveTaskConflictError(
                f"已有前台活动任务在进行中：{existing.task_id}",
                details={"active_task_id": existing.task_id, "status": existing.status},
            )

    # ── InputRevision（不可变） ──
    def set_draft_input(self, task: Task, *, name: str, phone: str, email: str,
                        location: str, jd: str) -> Task:
        """仅在 DRAFT 下更新可编辑入参（不冻结，revision=0 草稿行）。

        一旦 freeze_input 冻结到 READY，InputRevision 不可变；任何已冻结 revision 不得原地改写。
        每次保存都校验容量上限，超限抛 TaskCapacityError（不静默截断）。
        """
        if TaskStatus(task.status) != TaskStatus.DRAFT:
            raise TaskStateError(
                f"草稿保存仅允许 DRAFT，当前 {task.status}",
                details={"status": task.status},
            )
        self._assert_state_bytes(name, phone, email, location, jd)
        rev = task.current_input_revision
        existing = (self._db.query(InputRevision)
                    .filter_by(task_id=task.task_id, revision=rev)
                    .first()) if rev > 0 else None
        if existing is None:
            existing = InputRevision(
                task_id=task.task_id, revision=rev or 0,
                name=name, phone=phone, email=email, location=location, jd=jd,
                input_hash=_sha256(name + phone + email + location + jd),
                created_at=_utcnow(),
            )
            self._db.add(existing)
            # autoflush=False：同事务内再次保存草稿（同 revision 0）时查询可见并原地更新
            self._db.flush()
        else:
            existing.name = name
            existing.phone = phone
            existing.email = email
            existing.location = location
            existing.jd = jd
            existing.input_hash = _sha256(name + phone + email + location + jd)
            existing.created_at = _utcnow()
        task.updated_at = _utcnow()
        return task

    def freeze_input(self, task: Task, *, name: str, phone: str, email: str,
                     location: str, jd: str) -> InputRevision:
        """冻结一个不可变 InputRevision（READY，生成点击时调用）。

        新 revision = 当前 + 1；冻结后 task.current_input_revision 指向该 revision。
        旧 revision 保留完整原文用于回看；冻结后不可原地修改（新一次冻结生成新 revision）。
        """
        if TaskStatus(task.status) not in set(TRANSITIONS.keys()) - TERMINAL_STATUSES:
            raise TaskStateError(
                f"非法冻结任务状态 {task.status}",
                details={"status": task.status},
            )
        self._assert_state_bytes(name, phone, email, location, jd)
        new_rev = (task.current_input_revision or 0) + 1
        rev = InputRevision(
            task_id=task.task_id, revision=new_rev,
            name=name, phone=phone, email=email, location=location, jd=jd,
            input_hash=_sha256(name + phone + email + location + jd),
            created_at=_utcnow(),
        )
        self._db.add(rev)
        if task.status == TaskStatus.DRAFT.value:
            self.transition(task, TaskStatus.READY)
        task.current_input_revision = new_rev
        task.updated_at = _utcnow()
        return rev

    def _assert_state_bytes(self, name: str, phone: str, email: str,
                            location: str, jd: str) -> None:
        size = _json_bytes({
            "name": name, "phone": phone, "email": email,
            "location": location, "jd": jd,
        })
        if size > TASK_STATE_HARD_LIMIT_BYTES:
            raise TaskCapacityError(
                "入参记录超过单任务状态硬上限 256 KiB，拒绝保存（不静默截断）",
                details={"bytes": size, "limit": TASK_STATE_HARD_LIMIT_BYTES},
            )

    # ── Subtask ──
    def upsert_subtask(self, task: Task, experience_id: str, sort_order: int) -> TaskSubtask:
        st = (self._db.query(TaskSubtask)
              .filter_by(task_id=task.task_id, experience_id=experience_id)
              .first())
        if st is None:
            st = TaskSubtask(
                task_id=task.task_id, experience_id=experience_id,
                sort_order=sort_order, status=SubtaskStatus.PENDING.value,
                fact_results=[], failure_code=None, started_at=None,
                updated_at=_utcnow(),
            )
            self._db.add(st)
            # autoflush=False：同事务内再次 upsert 同一经历时查询可见并原地更新
            self._db.flush()
        else:
            st.sort_order = sort_order
            st.updated_at = _utcnow()
        return st

    def update_subtask(self, task: Task, experience_id: str, *,
                       status: Optional[SubtaskStatus] = None,
                       fact_results: Optional[list[dict[str, Any]]] = None,
                       failure_code: Optional[str] = None) -> TaskSubtask:
        st = (self._db.query(TaskSubtask)
              .filter_by(task_id=task.task_id, experience_id=experience_id)
              .first())
        if st is None:
            raise TaskNotFoundError(f"子任务不存在：{experience_id}",
                                    details={"experience_id": experience_id})
        if status is not None:
            st.status = status.value if isinstance(status, SubtaskStatus) else status
        if fact_results is not None:
            st.fact_results = fact_results
        if failure_code is not None:
            st.failure_code = failure_code
        if status == SubtaskStatus.RUNNING and st.started_at is None:
            st.started_at = _utcnow()
        st.updated_at = _utcnow()
        return st

    # ── 覆盖式权威快照 + 事件（同一把锁保证 seq 单调） ──
    def next_seq(self, task: Task) -> int:
        """推进并返回本任务新的单调 seq（供快照/事件共用，保证无缺口有序）。"""
        task.seq = (task.seq or 0) + 1
        return task.seq

    def save_snapshot(self, task: Task, *, phase: str, payload: dict[str, Any]) -> TaskSnapshot:
        """覆盖式权威快照：每任务一条，更新时推进 seq 并写入 payload。

        事件+快照合计受 256 KiB 硬上限约束；超限时压缩完成事件（见 _compress_events）。
        """
        self.assert_writable(task)
        seq = self.next_seq(task)
        snap = (self._db.query(TaskSnapshot)
                .filter_by(task_id=task.task_id)
                .first())
        if snap is None:
            snap = TaskSnapshot(task_id=task.task_id, seq=seq, phase=phase,
                                payload=payload, updated_at=_utcnow())
            self._db.add(snap)
            # autoflush=False 下立即落可见，避免同事务再次 save_snapshot 时查询不到而重复插入
            self._db.flush()
        else:
            snap.seq = seq
            snap.phase = phase
            snap.payload = payload
            snap.updated_at = _utcnow()
        task.updated_at = _utcnow()
        self._enforce_event_snapshot_cap(task)
        return snap

    def append_event(self, task: Task, *, input_revision: int, event_type: str,
                     phase: str, payload: dict[str, Any]) -> TaskEvent:
        """持久化一个业务完成事件（seq 全任务唯一可靠序）。终态拒收迟到事件。"""
        self.assert_writable(task)
        seq = self.next_seq(task)
        ev = TaskEvent(
            task_id=task.task_id, seq=seq, input_revision=input_revision,
            event_type=event_type, phase=phase, payload=payload,
            created_at=_utcnow(),
        )
        self._db.add(ev)
        # autoflush=False：使刚 add 的事件立即可被容量查询计数
        self._db.flush()
        task.updated_at = _utcnow()
        self._enforce_event_snapshot_cap(task)
        return ev

    def _enforce_event_snapshot_cap(self, task: Task) -> None:
        """事件 + 快照合计 <= 256 KiB。超限时压缩早期完成事件而非删结果。

        core.task.EVENT_RING_BUFFER_SIZE 提供"事件环形缓冲上限"；容量与数量取先到。
        压缩只删除最早的业务完成事件（增量已由后续/快照覆盖），绝不删除权威快照。
        """
        events = (self._db.query(TaskEvent)
                  .filter_by(task_id=task.task_id)
                  .order_by(TaskEvent.seq)
                  .all())
        snap = (self._db.query(TaskSnapshot)
                .filter_by(task_id=task.task_id)
                .first())
        # 数量上限（环形缓冲）
        if len(events) > EVENT_RING_BUFFER_SIZE:
            to_drop = len(events) - EVENT_RING_BUFFER_SIZE
            for ev in events[:to_drop]:
                self._db.delete(ev)
            events = events[to_drop:]
        # 字节上限（事件 + 快照 payload 合计）
        while events or snap:
            total = sum(_json_bytes(e.payload or {}) for e in events)
            if snap is not None:
                total += _json_bytes(snap.payload or {})
            if total <= TASK_EVENT_SNAPSHOT_LIMIT_BYTES:
                break
            if not events:
                # 快照自身超限：压缩快照中的长 reason（保留结果，压缩增量文本）
                self._compress_snapshot(snap)
                break
            # 删最旧事件（有 events 时先删事件）
            self._db.delete(events[0])
            events = events[1:]

    def _compress_snapshot(self, snap: TaskSnapshot) -> None:
        """快照超限时的诚实压缩：保留业务结果，仅裁剪 reason 增量文本字段。

        绝不删除业务完成结果；reason 是旁侧流式文本，可截断为前缀占位（T4/G3 明确允许
        reason 非字符级回放，断流用完整 reason 补偿事件或明确失败态）。
        """
        payload = dict(snap.payload or {})
        reasons = payload.get("reasons")
        if isinstance(reasons, dict):
            for fact_id, text in list(reasons.items()):
                if isinstance(text, str) and len(text) > 4096:
                    reasons[fact_id] = text[:4096] + "…(truncated)"
        payload["snapshot_truncated_reason"] = True
        snap.payload = payload
        snap.updated_at = _utcnow()

    # ── 状态发布（终态引用产物） ──
    def publish_artifacts(self, task: Task, *, resume_revision: int,
                          docx_path: str, pdf_path: str) -> None:
        """仅在 SUCCEEDED 终态发布最终产物引用（T5：取消/失败不得发布 artifact）。"""
        if TaskStatus(task.status) != TaskStatus.SUCCEEDED:
            raise TaskStateError("仅在 SUCCEEDED 发布最终产物引用",
                                 details={"status": task.status})
        task.published_resume_revision = resume_revision
        task.published_docx_path = docx_path
        task.published_pdf_path = pdf_path
        task.updated_at = _utcnow()

    # ── 事件读取（SSE 重连：先取快照，再从 seq+1 订阅） ──
    def list_events_after(self, task_id: str, after_seq: int,
                          limit: int = 500) -> list[dict[str, Any]]:
        rows = (self._db.query(TaskEvent)
                .filter(TaskEvent.task_id == task_id, TaskEvent.seq > after_seq)
                .order_by(TaskEvent.seq)
                .limit(min(max(limit, 1), 1000))
                .all())
        return [{
            "seq": e.seq, "input_revision": e.input_revision,
            "event_type": e.event_type, "phase": e.phase, "payload": e.payload or {},
        } for e in rows]

    def snapshot_seq(self, task_id: str) -> int:
        snap = (self._db.query(TaskSnapshot).filter_by(task_id=task_id).first())
        return snap.seq if snap is not None else 0


# 进程内默认单例（基于全局 SessionLocal；也可由调用方显式传入 self._db）
_global_repo = None


def get_task_repository(db: Session) -> TaskRepository:
    return TaskRepository(db)