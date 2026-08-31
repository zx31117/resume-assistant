"""管理 / 生成共享并发门禁（PLAN §3.3）。

迁移、全量重建、重试与生成共享同一进程锁。语义冻结为"拒绝"：
- 已有 mutating 操作在跑时，后续 mutating 请求抛 ConcurrencyConflictError(409)，
  不排队、不重复执行、不并发改写同一数据库/索引。
"""
from __future__ import annotations

import threading
from contextlib import contextmanager

from core.errors import ConcurrencyConflictError

_guard = threading.Lock()
_current_op: str | None = None


@contextmanager
def exclusive_operation(op_name: str):
    """获取全局互斥；被占用时立即拒绝（非阻塞），不排队。"""
    global _current_op
    if not _guard.acquire(blocking=False):
        raise ConcurrencyConflictError(
            f"另一项维护或生成操作正在进行，拒绝并发执行（{op_name}）",
            # holder 为当前占用操作名（尽力而为的诊断信息），供前端提示"谁在跑"
            details={"operation": op_name, "holder": _current_op},
        )
    _current_op = op_name
    try:
        yield
    finally:
        _current_op = None
        _guard.release()