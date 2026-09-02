"""管理 / 生成共享并发门禁（PLAN §3.3）。

迁移、全量重建、重试与生成共享同一进程锁。语义冻结为"拒绝"：
- 已有 mutating 操作在跑时，后续 mutating 请求抛 ConcurrencyConflictError(409)，
  不排队、不重复执行、不并发改写同一数据库/索引。

V2.0.1（T4）：门禁除了记录持有操作名，还记录 holder 的 operation_id 与持有起始
单调时刻，供 409 冲突返回真实占用操作编号、类型与已运行时长（PLAN §3.5 / R4）。
"""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import Optional

from core.errors import ConcurrencyConflictError

_guard = threading.Lock()
_current_op: Optional[str] = None
_current_operation_id: Optional[str] = None
_current_started_perf: Optional[float] = None


def _holder_elapsed_ms() -> int:
    if _current_started_perf is None:
        return 0
    return max(0, int((time.perf_counter() - _current_started_perf) * 1000))


def current_holder() -> Optional[dict]:
    """返回当前门禁持有者信息（无则 None）；供诊断与 409 复用，不持有锁。"""
    if _current_op is None:
        return None
    return {
        "operation": _current_op,
        "operation_id": _current_operation_id,
        "elapsed_ms": _holder_elapsed_ms(),
    }


@contextmanager
def exclusive_operation(op_name: str, operation_id: Optional[str] = None):
    """获取全局互斥；被占用时立即拒绝（非阻塞），不排队。

    operation_id 可选：传入后被记入 holder，冲突时随 409 返回给前端定位是谁在跑。
    """
    global _current_op, _current_operation_id, _current_started_perf
    if not _guard.acquire(blocking=False):
        holder = current_holder()
        raise ConcurrencyConflictError(
            f"另一项维护或生成操作正在进行，拒绝并发执行（{op_name}）",
            details={
                "operation": op_name,
                "holder": holder["operation"] if holder else _current_op,
                "holder_operation_id": holder["operation_id"] if holder else None,
                "holder_elapsed_ms": holder["elapsed_ms"] if holder else 0,
            },
        )
    _current_op = op_name
    _current_operation_id = operation_id
    _current_started_perf = time.perf_counter()
    try:
        yield
    finally:
        _current_op = None
        _current_operation_id = None
        _current_started_perf = None
        _guard.release()