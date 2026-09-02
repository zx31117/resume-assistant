"""V2.0.1 T1：统一操作可观测性核心（PLAN §3 / §4 / §5）。

单一事实机制：生成、提取、Experience CRUD、迁移、重建与重试等所有可观测操作，
都通过本模块的 `OperationTracker` 记录其状态、阶段与单调耗时，并写入 runtime
data root 下的结构化 JSONL（脱敏）日志，供前端轮询、刷新与重启后复盘。

设计约束（PLAN §4.3 / §10）：
- 不建立第二业务真源：日志只承载诊断证据，不参与任何事务/业务结果判定；
- 脱敏在写入前完成：禁止 API Key、Credential、Prompt、JD/Fact 正文、PII、
  绝对路径与原始异常堆栈进入 JSONL/API/摘要；
- 单调时钟：耗时一律用 time.perf_counter() 计算，墙上时间仅用于展示；
- 诊断故障降级：日志写入失败标记 DEGRADED，不破坏业务，也不伪称证据完整；
- 读取非阻塞：活动注册表与最近记录在内存，诊断读取不获取业务共享门禁。
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterator, Optional

from core.config import settings

# ── 枚举（稳定契约，禁止以任意用户输入扩展） ──────────────────── #


class OperationStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    INTERRUPTED = "INTERRUPTED"


class StageEventType(str, Enum):
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class ResourceType(str, Enum):
    LOCAL_DB = "LOCAL_DB"
    LOCAL_FILE = "LOCAL_FILE"
    LOCAL_CPU = "LOCAL_CPU"
    LLM = "LLM"
    EMBEDDING = "EMBEDDING"


class OperationType(str, Enum):
    """可观测操作的稳定类型（PLAN §4.1 operation_type）。"""

    GENERATE = "generate"
    EXTRACT = "extract"
    EXPERIENCE_CREATE = "experience_create"
    EXPERIENCE_UPDATE = "experience_update"
    EXPERIENCE_DELETE = "experience_delete"
    MIGRATE = "migrate"
    REBUILD = "rebuild"
    RETRY = "retry"


# 操作生命周期事件码（日志级别标识，非业务错误码）
_OP_STARTED = "OP_STARTED"
_OP_SUCCEEDED = "OP_SUCCEEDED"
_OP_FAILED = "OP_FAILED"
_OP_TIMED_OUT = "OP_TIMED_OUT"
_OP_INTERRUPTED = "OP_INTERRUPTED"

# 终态集合
_TERMINAL = {OperationStatus.SUCCEEDED, OperationStatus.FAILED, OperationStatus.TIMED_OUT, OperationStatus.INTERRUPTED}

# 轮转上限（PLAN §3.4）：7 天 / 10 MiB，先到即清理最旧
_MAX_AGE_DAYS = 7
_MAX_SIZE_BYTES = 10 * 1024 * 1024

# 最近操作 API 上限（PLAN §3.4）
_MAX_RECENT = 200


def _utcnow_iso() -> str:
    return _dt.datetime.utcnow().isoformat(timespec="milliseconds") + "Z"


def _new_uuid() -> str:
    return str(uuid.uuid4())


def new_operation_id() -> str:
    """生成合法 operation_id。"""
    return _new_uuid()


def valid_operation_id(value: Optional[str]) -> Optional[str]:
    """校验并返回合法 UUID 字符串；非法返回 None（PLAN §7.2 路径参数严格校验）。"""
    if not value or not isinstance(value, str):
        return None
    try:
        uuid.UUID(value)
        return value
    except (ValueError, AttributeError):
        return None


def resolve_operation_id(value: Optional[str]) -> str:
    """解析 X-Operation-ID：合法 UUID 直接使用，否则生成新 UUID（PLAN §3.3）。"""
    v = valid_operation_id(value)
    return v if v is not None else _new_uuid()


# ── 结构体 ────────────────────────────────────────────────────── #


@dataclass
class StageEvent:
    """单个阶段事件（内存投影，同时会写入 JSONL）。"""

    seq: int
    event_type: StageEventType
    stage_code: str
    stage_name: str
    resource_type: ResourceType
    event_code: str
    attempt: int
    max_attempts: int
    elapsed_ms: int
    message: str
    safe_counts: dict[str, int]
    ts: str


class OperationRecord:
    """一次可观测操作的内存记录（线程安全）。"""

    def __init__(
        self,
        operation_id: str,
        operation_type: OperationType,
        group_id: Optional[str] = None,
        seq_start: int = 0,
    ) -> None:
        self._lock = threading.Lock()
        self.operation_id = operation_id
        self.group_id = group_id
        self.operation_type = operation_type
        self.status: OperationStatus = OperationStatus.RUNNING
        self.stage_code = ""
        self.stage_name = ""
        self.resource_type: ResourceType = ResourceType.LOCAL_CPU
        self.attempt = 1
        self.max_attempts = 1
        self.diagnostic_code = ""
        self.safe_counts: dict[str, int] = {}
        self.safe_summary: dict[str, Any] = {}

        self.started_perf = time.perf_counter()
        self.started_wall = _utcnow_iso()
        self.last_event_wall = self.started_wall
        self.ended_wall: Optional[str] = None

        # 当前阶段计时（单调）
        self._stage_start_perf: Optional[float] = None
        self._stage_code: Optional[str] = None

        self.stages: list[StageEvent] = []
        # 无法归入业务阶段的耗时（单调累计，PLAN §4.1）
        self.unattributed_ms = 0
        # 终态冻结的总耗时：终态后 projection 不再随快照时刻增长（PLAN §3.5 单调事实源）
        self._final_elapsed_ms: Optional[int] = None

        # 首个生命周期事件 seq（由 tracker 在 begin 时写入）
        self._seq_start = seq_start

    # ── 内部（由 tracker 调用，业务代码不直接触碰） ──
    def _begin_stage(self, stage_code: str, stage_name: str, resource_type: ResourceType, seq: int) -> None:
        with self._lock:
            self.stage_code = stage_code
            self.stage_name = stage_name
            self.resource_type = resource_type
            self._stage_code = stage_code
            self._stage_start_perf = time.perf_counter()
            self.last_event_wall = _utcnow_iso()
            self.stages.append(StageEvent(
                seq=seq,
                event_type=StageEventType.STARTED,
                stage_code=stage_code,
                stage_name=stage_name,
                resource_type=resource_type,
                event_code=f"STAGE_STARTED.{stage_code}",
                attempt=self.attempt,
                max_attempts=self.max_attempts,
                elapsed_ms=0,
                message="",
                safe_counts={},
                ts=_utcnow_iso(),
            ))

    def _end_stage(
        self,
        stage_code: str,
        event_type: StageEventType,
        seq: int,
        message: str = "",
        safe_counts: Optional[dict[str, int]] = None,
    ) -> int:
        """结束当前阶段，返回该阶段单调耗时(ms)。"""
        with self._lock:
            started = self._stage_start_perf
            elapsed = 0
            if started is not None:
                elapsed = max(0, int((time.perf_counter() - started) * 1000))
            self._stage_start_perf = None
            self._stage_code = None
            self.last_event_wall = _utcnow_iso()
            self.stages.append(StageEvent(
                seq=seq,
                event_type=event_type,
                stage_code=stage_code,
                stage_name="",
                resource_type=self.resource_type,
                event_code=f"STAGE_{event_type.value}.{stage_code}",
                attempt=self.attempt,
                max_attempts=self.max_attempts,
                elapsed_ms=elapsed,
                message=message,
                safe_counts=dict(safe_counts or {}),
                ts=_utcnow_iso(),
            ))
            return elapsed

    def _finalize(
        self,
        status: OperationStatus,
        diagnostic_code: str,
        seq: int,
    ) -> None:
        with self._lock:
            self.status = status
            self.diagnostic_code = diagnostic_code
            self.ended_wall = _utcnow_iso()
            self.last_event_wall = self.ended_wall
            # 冻结总耗时（终态后不再随快照时刻增长）
            self._final_elapsed_ms = max(0, int((time.perf_counter() - self.started_perf) * 1000))
            # 若有未收口阶段，剩余耗时计入 unattributed
            if self._stage_start_perf is not None:
                self.unattributed_ms += max(0, int((time.perf_counter() - self._stage_start_perf) * 1000))
                self._stage_start_perf = None
                self._stage_code = None

    def projection(self) -> dict[str, Any]:
        """只读投影（线程安全快照，结构稳定，API 直接序列化）。"""
        with self._lock:
            if self.status in _TERMINAL and self._final_elapsed_ms is not None:
                elapsed_ms = self._final_elapsed_ms
            else:
                elapsed_ms = max(0, int((time.perf_counter() - self.started_perf) * 1000))
            stage_elapsed_ms = 0
            if self._stage_start_perf is not None:
                stage_elapsed_ms = max(0, int((time.perf_counter() - self._stage_start_perf) * 1000))
            return {
                "operation_id": self.operation_id,
                "group_id": self.group_id,
                "operation_type": self.operation_type.value,
                "status": self.status.value,
                "stage_code": self.stage_code,
                "stage_name": self.stage_name,
                "resource_type": self.resource_type.value,
                "started_at": self.started_wall,
                "last_event_at": self.last_event_wall,
                "ended_at": self.ended_wall,
                "elapsed_ms": elapsed_ms,
                "stage_elapsed_ms": stage_elapsed_ms,
                "attempt": self.attempt,
                "max_attempts": self.max_attempts,
                "diagnostic_code": self.diagnostic_code,
                "safe_counts": dict(self.safe_counts),
                "safe_summary": dict(self.safe_summary),
                "stage_count": len(self.stages),
                "unattributed_ms": self.unattributed_ms,
            }

    def stage_projection(self) -> list[dict[str, Any]]:
        """完整阶段列表投影（按顺序）。"""
        with self._lock:
            return [
                {
                    "seq": s.seq,
                    "event_type": s.event_type.value,
                    "stage_code": s.stage_code,
                    "stage_name": s.stage_name,
                    "resource_type": s.resource_type.value,
                    "event_code": s.event_code,
                    "attempt": s.attempt,
                    "max_attempts": s.max_attempts,
                    "elapsed_ms": s.elapsed_ms,
                    "message": s.message,
                    "safe_counts": dict(s.safe_counts),
                    "ts": s.ts,
                }
                for s in self.stages
            ]


# ── 阶段上下文管理器（业务代码持有句柄） ──────────────────────── #


class _StageScope:
    """`with recording.stage(...)` 返回的阶段作用域。"""

    def __init__(self, tracker: "OperationTracker", operation_id: str, stage_code: str) -> None:
        self._tracker = tracker
        self._operation_id = operation_id
        self._stage_code = stage_code
        self._message = ""
        self._safe_counts: dict[str, int] = {}
        self._ended = False

    def note(self, message: str) -> None:
        """记录脱敏阶段说明（覆盖，仅白名单内容）。"""
        self._message = _sanitize_message(message)

    def counts(self, **kwargs: int) -> None:
        """记录安全计数（总数/已处理/成功/失败等，不含正文）。"""
        self._safe_counts.update({k: int(v) for k, v in kwargs.items()})

    def __enter__(self) -> "_StageScope":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self._ended:
            return False
        self._ended = True
        if exc_type is not None:
            self._tracker._stage_failed(self._operation_id, self._stage_code, self._message, self._safe_counts)
            return False  # 传播异常
        self._tracker._stage_completed(self._operation_id, self._stage_code, self._message, self._safe_counts)
        return False


class Recording:
    """一次操作的业务句柄（由 `tracker.operation()` 上下文管理器产出）。"""

    def __init__(self, tracker: "OperationTracker", record: OperationRecord) -> None:
        self._tracker = tracker
        self._record = record

    @property
    def operation_id(self) -> str:
        return self._record.operation_id

    def stage(
        self,
        stage_code: str,
        stage_name: str = "",
        resource_type: ResourceType = ResourceType.LOCAL_CPU,
    ) -> _StageScope:
        """开启一个真实阶段的计时作用域。"""
        self._tracker._stage_started(self._record.operation_id, stage_code, stage_name, resource_type)
        return _StageScope(self._tracker, self._record.operation_id, stage_code)

    def rolled_back(self, stage_code: str, message: str = "") -> None:
        """标记某已执行写步骤被回滚（PLAN §3.5 / R3）。"""
        self._tracker._stage_rolled_back(self._record.operation_id, stage_code, message)

    def set_attempts(self, attempt: int, max_attempts: int) -> None:
        with self._record._lock:
            self._record.attempt = int(attempt)
            self._record.max_attempts = int(max_attempts)

    def set_counts(self, counts: dict[str, int]) -> None:
        with self._record._lock:
            self._record.safe_counts = {k: int(v) for k, v in counts.items()}

    def set_summary(self, summary: dict[str, Any]) -> None:
        with self._record._lock:
            self._record.safe_summary = dict(summary)

    def set_diagnostic(self, code: str) -> None:
        with self._record._lock:
            self._record.diagnostic_code = _sanitize_message(code)

    def mark_timeout(self, diagnostic_code: str = "TIMEOUT") -> None:
        self._tracker._finalize(self._record.operation_id, OperationStatus.TIMED_OUT, diagnostic_code)

    def snapshot(self) -> dict[str, Any]:
        return self._record.projection()

    def stages(self) -> list[dict[str, Any]]:
        """按顺序返回已完成/失败/回滚的阶段投影（供响应回填，保证与后台一致）。"""
        return self._record.stage_projection()


# ── 脱敏 ──────────────────────────────────────────────────────── #

# 高危 token 片段：只要出现即视为敏感，整条 message 降级为占位
_SENSITIVE_MARKERS = (
    "ark_api_key", "authorization", "bearer ", "api_key", "apikey",
    "cookie", "session_token", "password",
)

# 结构化脱敏：邮箱 / Windows 绝对路径 / 绝对路径 / 疑似电话号码
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_WIN_PATH_RE = re.compile(r"[A-Za-z]:[\\/][^\s]*")
_UNIX_ABS_PATH_RE = re.compile(r"(?:/[\w.-]+){2,}/?")
_PHONE_RE = re.compile(r"\b\+?\d[\d\s\-()]{6,}\d\b")


def _sanitize_message(message: str) -> str:
    """消息级脱敏（PLAN §4.2）：写入前按字段白名单处理，命中敏感标记整体降级。

    只保留安全文案；邮箱、本机路径、疑似电话一律替换为占位，禁止 PII/绝对路径落库。
    """
    if not message:
        return ""
    if not isinstance(message, str):
        return ""
    low = message.lower()
    for marker in _SENSITIVE_MARKERS:
        if marker in low:
            return "<redacted>"
    s = _EMAIL_RE.sub("<email>", message)
    s = _WIN_PATH_RE.sub("<path>", s)
    s = _UNIX_ABS_PATH_RE.sub("<path>", s)
    s = _PHONE_RE.sub("<phone>", s)
    # 长度上限，防误写长正文
    return s[:500]


# ── 操作类型 → 组件 ──────────────────────────────────────────── #

def _component_of(op_type: OperationType) -> str:
    """把稳定类型映射到稳定组件名（§4.2 component）。"""
    mapping = {
        OperationType.GENERATE: "generate",
        OperationType.EXTRACT: "experience",
        OperationType.EXPERIENCE_CREATE: "experience",
        OperationType.EXPERIENCE_UPDATE: "experience",
        OperationType.EXPERIENCE_DELETE: "experience",
        OperationType.MIGRATE: "migration",
        OperationType.REBUILD: "embedding",
        OperationType.RETRY: "embedding",
    }
    return mapping.get(op_type, op_type.value)


# ── 诊断健康状态 ─────────────────────────────────────────────── #


class DiagnosticsHealth(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


# ── Tracker ──────────────────────────────────────────────────── #


class OperationTracker:
    """进程内操作注册表 + 脱敏 JSONL 日志 + 轮转/启动收口（单例）。"""

    def __init__(self) -> None:
        # 内存注册表与文件写使用独立锁，避免长操作阻塞诊断读取（PLAN R1）
        self._mem_lock = threading.RLock()
        self._file_lock = threading.Lock()
        self._active: dict[str, OperationRecord] = {}
        self._recent: list[OperationRecord] = []  # 新→旧，最多 _MAX_RECENT
        self._seq = 0
        self._health = DiagnosticsHealth.HEALTHY
        self._log_path: Path = settings.DIAGNOSTICS_DIR / "operations.jsonl"
        self._initialized = False

    # ── 初始化与启动收口 ──
    def initialize(self) -> None:
        """启动时收口：重建 seq、把遗留 RUNNING 收为 INTERRUPTED、执行轮转。

        只在进程启动调用一次；幂等。失败不抛（诊断设施降级，不阻断业务）。
        """
        with self._mem_lock:
            if self._initialized:
                return
            self._initialized = True
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            self._reconcile_on_startup()
            self._maybe_rotate(force=True)
        except Exception:
            self._health = DiagnosticsHealth.DEGRADED

    def _reconcile_on_startup(self) -> None:
        """扫描 JSONL：为无终态的 OP_STARTED 追加 INTERRUPTED，并恢复 seq。"""
        if not self._log_path.exists():
            self._seq = 0
            return
        lines_since_op: dict[str, str] = {}
        opened: dict[str, bool] = {}
        # 首遍：定位每个 operation_id 是否有终态；记录最大 seq
        try:
            with open(self._log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except Exception:
                        continue
                    seq = int(ev.get("seq", 0))
                    self._seq = max(self._seq, seq)
                    oid = ev.get("operation_id")
                    if not oid:
                        continue
                    code = ev.get("event_code", "")
                    if code == _OP_STARTED:
                        opened.setdefault(oid, True)
                    elif code in (_OP_SUCCEEDED, _OP_FAILED, _OP_TIMED_OUT, _OP_INTERRUPTED):
                        opened[oid] = False
        except Exception:
            return

        appended = 0
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                for oid, still_open in opened.items():
                    if not still_open:
                        continue
                    self._seq += 1
                    f.write(json.dumps(self._event_line(
                        seq=self._seq,
                        level="WARNING",
                        component="reconcile",
                        operation_id=oid,
                        group_id=None,
                        operation_type="",
                        status=OperationStatus.INTERRUPTED.value,
                        stage_code="",
                        resource_type="",
                        event_code=_OP_INTERRUPTED,
                        message="应用在操作进行中被中断（启动收口）",
                        attempt=1,
                        max_attempts=1,
                        elapsed_ms=0,
                        diagnostic_code="PROCESS_INTERRUPTED",
                        safe_counts={},
                    ), ensure_ascii=False) + "\n")
                    appended += 1
        except Exception:
            pass

    # ── 生命周期 API ──
    @contextmanager
    def operation(
        self,
        operation_type: OperationType,
        group_id: Optional[str] = None,
        operation_id: Optional[str] = None,
    ) -> Iterator[Recording]:
        """一次操作的上下文：进入注册 RUNNING，正常结束 SUCCEEDED，异常 FAILED。

        并发门禁拒绝的请求不应进入本管理器（它们没有开始业务执行）。
        """
        if not self._initialized:
            self.initialize()
        oid = operation_id or _new_uuid()
        rec = self._begin(oid, operation_type, group_id)
        recording = Recording(self, rec)
        try:
            yield recording
        except Exception as exc:
            # 诊断失败不得吞业务异常：仅当仍 RUNNING 时收为 FAILED，然后原样 re-raise
            if rec.status == OperationStatus.RUNNING:
                self._finalize(oid, OperationStatus.FAILED, self._classify_from_context())
            # 把 operation_id 附着到异常，供错误响应回传（失败后可按 oid 复盘）
            try:
                setattr(exc, "operation_id", oid)
            except Exception:
                pass
            raise
        else:
            if rec.status == OperationStatus.RUNNING:
                self._finalize(oid, OperationStatus.SUCCEEDED, "")

    def _begin(self, oid: str, op_type: OperationType, group_id: Optional[str]) -> OperationRecord:
        with self._mem_lock:
            self._seq += 1
            rec = OperationRecord(oid, op_type, group_id, seq_start=self._seq)
            self._active[oid] = rec
        self._write(self._event_line(
            seq=self._seq,
            level="INFO",
            component=_component_of(op_type),
            operation_id=oid,
            group_id=group_id,
            operation_type=op_type.value,
            status=OperationStatus.RUNNING.value,
            stage_code="",
            resource_type="",
            event_code=_OP_STARTED,
            message=f"{op_type.value} 开始",
            attempt=1,
            max_attempts=1,
            elapsed_ms=0,
            diagnostic_code="",
            safe_counts={},
        ))
        return rec

    def _stage_started(
        self, oid: str, stage_code: str, stage_name: str, resource_type: ResourceType,
    ) -> None:
        rec = self._get_record(oid)
        if rec is None:
            return
        with self._mem_lock:
            self._seq += 1
            seq = self._seq
        rec._begin_stage(stage_code, stage_name, resource_type, seq)
        self._write(self._event_line(
            seq=seq,
            level="INFO",
            component=_component_of(rec.operation_type),
            operation_id=oid,
            group_id=rec.group_id,
            operation_type=rec.operation_type.value,
            status=OperationStatus.RUNNING.value,
            stage_code=stage_code,
            resource_type=resource_type.value,
            event_code=f"STAGE_STARTED.{stage_code}",
            message=f"{stage_name or stage_code} 开始",
            attempt=rec.attempt,
            max_attempts=rec.max_attempts,
            elapsed_ms=0,
            diagnostic_code="",
            safe_counts={},
        ))

    def _stage_completed(
        self, oid: str, stage_code: str, message: str = "", safe_counts: Optional[dict[str, int]] = None,
    ) -> None:
        rec = self._get_record(oid)
        if rec is None:
            return
        with self._mem_lock:
            self._seq += 1
            seq = self._seq
        elapsed = rec._end_stage(stage_code, StageEventType.COMPLETED, seq, _sanitize_message(message), safe_counts)
        self._write(self._event_line(
            seq=seq,
            level="INFO",
            component=_component_of(rec.operation_type),
            operation_id=oid,
            group_id=rec.group_id,
            operation_type=rec.operation_type.value,
            status=OperationStatus.RUNNING.value,
            stage_code=stage_code,
            resource_type=rec.resource_type.value,
            event_code=f"STAGE_COMPLETED.{stage_code}",
            message=_sanitize_message(message),
            attempt=rec.attempt,
            max_attempts=rec.max_attempts,
            elapsed_ms=elapsed,
            diagnostic_code="",
            safe_counts=dict(safe_counts or {}),
        ))

    def _stage_failed(
        self, oid: str, stage_code: str, message: str = "", safe_counts: Optional[dict[str, int]] = None,
    ) -> None:
        rec = self._get_record(oid)
        if rec is None:
            return
        with self._mem_lock:
            self._seq += 1
            seq = self._seq
        elapsed = rec._end_stage(stage_code, StageEventType.FAILED, seq, _sanitize_message(message), safe_counts)
        self._write(self._event_line(
            seq=seq,
            level="ERROR",
            component=_component_of(rec.operation_type),
            operation_id=oid,
            group_id=rec.group_id,
            operation_type=rec.operation_type.value,
            status=OperationStatus.RUNNING.value,
            stage_code=stage_code,
            resource_type=rec.resource_type.value,
            event_code=f"STAGE_FAILED.{stage_code}",
            message=_sanitize_message(message),
            attempt=rec.attempt,
            max_attempts=rec.max_attempts,
            elapsed_ms=elapsed,
            diagnostic_code="",
            safe_counts=dict(safe_counts or {}),
        ))

    def _stage_rolled_back(self, oid: str, stage_code: str, message: str = "") -> None:
        rec = self._get_record(oid)
        if rec is None:
            return
        with self._mem_lock:
            self._seq += 1
            seq = self._seq
        self._write(self._event_line(
            seq=seq,
            level="WARNING",
            component=_component_of(rec.operation_type),
            operation_id=oid,
            group_id=rec.group_id,
            operation_type=rec.operation_type.value,
            status=OperationStatus.RUNNING.value,
            stage_code=stage_code,
            resource_type=rec.resource_type.value,
            event_code=f"STAGE_ROLLED_BACK.{stage_code}",
            message=_sanitize_message(message),
            attempt=rec.attempt,
            max_attempts=rec.max_attempts,
            elapsed_ms=0,
            diagnostic_code="",
            safe_counts={},
        ))
        with self._mem_lock:
            rec.stages.append(StageEvent(
                seq=seq,
                event_type=StageEventType.ROLLED_BACK,
                stage_code=stage_code,
                stage_name="",
                resource_type=rec.resource_type,
                event_code=f"STAGE_ROLLED_BACK.{stage_code}",
                attempt=rec.attempt,
                max_attempts=rec.max_attempts,
                elapsed_ms=0,
                message=_sanitize_message(message),
                safe_counts={},
                ts=_utcnow_iso(),
            ))

    def _finalize(self, oid: str, status: OperationStatus, diagnostic_code: str) -> None:
        rec = self._get_record(oid)
        if rec is None:
            return
        with self._mem_lock:
            self._seq += 1
            seq = self._seq
            rec._finalize(status, _sanitize_message(diagnostic_code), seq)
            # 移出活动，进入最近
            self._active.pop(oid, None)
            self._recent.insert(0, rec)
            if len(self._recent) > _MAX_RECENT:
                self._recent = self._recent[:_MAX_RECENT]
        event_code = {
            OperationStatus.SUCCEEDED: _OP_SUCCEEDED,
            OperationStatus.FAILED: _OP_FAILED,
            OperationStatus.TIMED_OUT: _OP_TIMED_OUT,
            OperationStatus.INTERRUPTED: _OP_INTERRUPTED,
        }[status]
        level = "INFO" if status == OperationStatus.SUCCEEDED else "ERROR"
        self._write(self._event_line(
            seq=seq,
            level=level,
            component=_component_of(rec.operation_type),
            operation_id=oid,
            group_id=rec.group_id,
            operation_type=rec.operation_type.value,
            status=status.value,
            stage_code="",
            resource_type="",
            event_code=event_code,
            message=f"{rec.operation_type.value} {status.value}",
            attempt=rec.attempt,
            max_attempts=rec.max_attempts,
            elapsed_ms=rec.projection()["elapsed_ms"],
            diagnostic_code=_sanitize_message(diagnostic_code),
            safe_counts=rec.safe_counts,
        ))
        # 写轮转检查放在终结后（低频）
        self._maybe_rotate()

    # ── 读取 API（非阻塞，只读内存或文件快照） ──
    def list_operations(
        self,
        *,
        status: Optional[str] = None,
        operation_type: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        with self._mem_lock:
            all_recs = list(self._active.values()) + list(self._recent)
        out: list[dict[str, Any]] = []
        for rec in all_recs:
            p = rec.projection()
            if status and p["status"] != status:
                continue
            if operation_type and p["operation_type"] != operation_type:
                continue
            out.append(p)
        # 活动在前，最近在后；按 started 时间倒序稳定
        return out[:limit]

    def get_operation(self, oid: str) -> Optional[dict[str, Any]]:
        with self._mem_lock:
            rec = self._active.get(oid)
            if rec is None:
                for r in self._recent:
                    if r.operation_id == oid:
                        rec = r
                        break
        if rec is None:
            return None
        proj = rec.projection()
        proj["stages"] = rec.stage_projection()
        # R5：近期同类耗时对比（按 operation_type + stage_code，排除本次自身）
        recent: dict[str, dict[str, Any]] = {}
        seen: set[str] = set()
        for s in proj["stages"]:
            sc = s.get("stage_code", "")
            if not sc or sc in seen:
                continue
            seen.add(sc)
            recent[sc] = self.recent_stats(rec.operation_type.value, sc, exclude_oid=oid)
        proj["recent_stats"] = recent
        return proj

    def read_logs(self, after_seq: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        """按事件序号增量读取日志（after_seq 之后的新事件）。"""
        limit = max(1, min(int(limit), 500))
        events: list[dict[str, Any]] = []
        if not self._log_path.exists():
            return events
        try:
            with open(self._log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except Exception:
                        continue
                    if int(ev.get("seq", 0)) > after_seq:
                        events.append(ev)
                        if len(events) >= limit:
                            break
        except Exception:
            self._health = DiagnosticsHealth.DEGRADED
        return events

    def diagnostics(self, oid: str) -> Optional[dict[str, Any]]:
        """脱敏诊断摘要：内存优先，失败则回退文件（非阻塞）。"""
        op = self.get_operation(oid)
        if op is not None:
            return {
                "operation_id": op["operation_id"],
                "operation_type": op["operation_type"],
                "status": op["status"],
                "diagnostic_code": op["diagnostic_code"],
                "started_at": op["started_at"],
                "ended_at": op["ended_at"],
                "elapsed_ms": op["elapsed_ms"],
                "stage_count": op["stage_count"],
                "safe_counts": op["safe_counts"],
                "safe_summary": op["safe_summary"],
                "stages": op.get("stages", []),
            }
        # 内存无 → 复盘场景：从 JSONL 重建脱敏摘要（不读业务正文）
        return self._diagnostics_from_file(oid)

    def _diagnostics_from_file(self, oid: str) -> Optional[dict[str, Any]]:
        if not self._log_path.exists():
            return None
        stages: list[dict[str, Any]] = []
        status = ""
        diagnostic_code = ""
        started_at = ""
        ended_at = ""
        safe_counts: dict[str, int] = {}
        try:
            with open(self._log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except Exception:
                        continue
                    if ev.get("operation_id") != oid:
                        continue
                    code = ev.get("event_code", "")
                    if code == _OP_STARTED:
                        started_at = ev.get("ts", "")
                    if code in (_OP_SUCCEEDED, _OP_FAILED, _OP_TIMED_OUT, _OP_INTERRUPTED):
                        status = ev.get("status", "")
                        diagnostic_code = ev.get("diagnostic_code", "")
                        ended_at = ev.get("ts", "")
                        safe_counts = ev.get("safe_counts", {})
                    if code.startswith("STAGE_"):
                        stages.append({
                            "event_type": code.split(".", 1)[0].replace("STAGE_", ""),
                            "stage_code": ev.get("stage_code", ""),
                            "elapsed_ms": ev.get("elapsed_ms", 0),
                            "event_code": code,
                        })
        except Exception:
            return None
        if not started_at and not status:
            return None
        return {
            "operation_id": oid,
            "status": status,
            "diagnostic_code": diagnostic_code,
            "started_at": started_at,
            "ended_at": ended_at,
            "safe_counts": safe_counts,
            "stages": stages,
        }

    def recent_stats(
        self,
        operation_type: str,
        stage_code: str,
        n: int = 20,
        exclude_oid: Optional[str] = None,
    ) -> dict[str, Any]:
        """R5：按 operation_type + stage_code 计算最近 n 次的样本数/中位数/最大值。

        exclude_oid：结算某次操作的对比时排除其自身，避免"本次"污染"近期"基线。
        """
        n = max(1, min(int(n), 20))
        elapsed: list[int] = []
        with self._mem_lock:
            recs = list(self._active.values()) + list(self._recent)
        for rec in recs:
            if exclude_oid is not None and rec.operation_id == exclude_oid:
                continue
            if rec.operation_type.value != operation_type:
                continue
            for s in rec.stages:
                if s.stage_code == stage_code and s.event_type == StageEventType.COMPLETED:
                    elapsed.append(s.elapsed_ms)
        elapsed = elapsed[-n:]
        if not elapsed:
            return {"sample_size": 0, "median_ms": None, "max_ms": None}
        ordered = sorted(elapsed)
        mid = len(ordered) // 2
        if len(ordered) % 2 == 0:
            median = int((ordered[mid - 1] + ordered[mid]) / 2)
        else:
            median = ordered[mid]
        return {"sample_size": len(ordered), "median_ms": median, "max_ms": max(ordered)}

    def health(self) -> str:
        return self._health.value

    def clear_logs(self) -> dict[str, Any]:
        """受保护的历史日志清理（删除/裁剪 JSONL，不影响活动操作）。"""
        with self._file_lock:
            try:
                if self._log_path.exists():
                    self._log_path.unlink()
                self._seq = 0
                with self._mem_lock:
                    self._recent = []
            except Exception:
                self._health = DiagnosticsHealth.DEGRADED
                return {"ok": False, "error": "LOGS_CLEAR_FAILED"}
        return {"ok": True}

    # ── 内部 ──
    def _get_record(self, oid: str) -> Optional[OperationRecord]:
        with self._mem_lock:
            return self._active.get(oid)

    @staticmethod
    def _event_line(
        *,
        seq: int,
        level: str,
        component: str,
        operation_id: str,
        group_id: Optional[str],
        operation_type: str,
        status: str,
        stage_code: str,
        resource_type: str,
        event_code: str,
        message: str,
        attempt: int,
        max_attempts: int,
        elapsed_ms: int,
        diagnostic_code: str,
        safe_counts: dict[str, int],
    ) -> dict[str, Any]:
        return {
            "seq": seq,
            "ts": _utcnow_iso(),
            "level": level,
            "component": component,
            "operation_id": operation_id,
            "group_id": group_id,
            "operation_type": operation_type,
            "status": status,
            "stage_code": stage_code,
            "resource_type": resource_type,
            "event_code": event_code,
            "message": _sanitize_message(message),
            "attempt": attempt,
            "max_attempts": max_attempts,
            "elapsed_ms": elapsed_ms,
            "diagnostic_code": _sanitize_message(diagnostic_code),
            "safe_counts": dict(safe_counts or {}),
        }

    def _write(self, event: dict[str, Any]) -> None:
        """把单个事件追加到 JSONL；失败降级诊断健康，不抛。"""
        with self._file_lock:
            try:
                self._log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self._log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(event, ensure_ascii=False) + "\n")
            except Exception:
                self._health = DiagnosticsHealth.DEGRADED

    def _maybe_rotate(self, force: bool = False) -> None:
        """轮转：超过 7 天或 10 MiB 先到即清理最旧。低频调用。"""
        with self._file_lock:
            try:
                if not self._log_path.exists():
                    return
                size = self._log_path.stat().st_size
                if not force and size <= _MAX_SIZE_BYTES:
                    return
                self._trim_file()
            except Exception:
                self._health = DiagnosticsHealth.DEGRADED

    def _trim_file(self) -> None:
        """保留最近 7 天且不超过大小上限的行。"""
        cutoff = _dt.datetime.utcnow() - _dt.timedelta(days=_MAX_AGE_DAYS)
        kept: list[dict[str, Any]] = [ev for ev in self._read_all() if self._within_age(ev, cutoff)]
        # 若仍超大小，丢弃最旧（按 seq 升序，砍掉前段）
        while kept:
            total = sum(len(json.dumps(e, ensure_ascii=False)) + 1 for e in kept)
            if total <= _MAX_SIZE_BYTES:
                break
            kept = kept[len(kept) // 10 or 1 :] if len(kept) > 1 else []
        tmp = self._log_path.with_suffix(".jsonl.tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                for e in kept:
                    f.write(json.dumps(e, ensure_ascii=False) + "\n")
            os.replace(tmp, self._log_path)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except Exception:
                    pass

    @staticmethod
    def _within_age(ev: dict[str, Any], cutoff: _dt.datetime) -> bool:
        ts = ev.get("ts", "")
        try:
            dt = _dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt.replace(tzinfo=None) >= cutoff
        except Exception:
            return False

    def _read_all(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        with open(self._log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except Exception:
                    continue
        return events

    # ── 异常分类（仅存稳定码，不存堆栈/正文） ──
    @staticmethod
    def _classify_from_context() -> str:
        """从当前异常上下文取稳定分类；避免依赖未定义变量。"""
        import sys as _sys

        exc_type, _exc, _tb = _sys.exc_info()
        if exc_type is None:
            return "UNKNOWN"
        name = exc_type.__name__
        # 白名单：常见稳定类型名直接返回；其余统一归类
        known = {
            "MigrationRequiredError", "VectorIndexNotReadyError", "NoMatchedExperienceError",
            "ProfileIncompleteError", "LLMOutputInvalidError", "ContentGenerationError",
            "FileSaveError", "ResumeBuildError", "ConcurrencyConflictError", "MigrationError",
            "FactNotFoundError", "FactModificationError", "RetrievalHealthError",
            "ConfigInvalidError", "CredentialStorageError", "TimeOutError", "TimeoutError",
        }
        return name if name in known else "INTERNAL_ERROR"


def optional_stage(
    recording: Optional["Recording"],
    stage_code: str,
    stage_name: str = "",
    resource_type: ResourceType = ResourceType.LOCAL_CPU,
):
    """返回阶段上下文：recording 为 None 时退回 no-op（CLI/测试直调服务仍可用）。

    recording 非 None 时等价 `recording.stage(...)`（进入时已发出 STARTED）。
    """
    from contextlib import nullcontext

    if recording is None:
        return nullcontext()
    return recording.stage(stage_code, stage_name, resource_type)


# ── 单例 ─────────────────────────────────────────────────────── #

tracker = OperationTracker()