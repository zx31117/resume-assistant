"""V2.2.0 T5：协作式取消 + revision fence + 资源清理（PLAN V220-G02 / Gate 6.1）。

后端是任务状态真源；"取消请求"与"旧任务迟到结果拒收"收敛到本模块，作为进程内可测的单一真源，
供生成 worker（P1–P4、Word worker）与 TaskService/API 复用：

- CancellationToken：每个"正在运行"任务一个。request_cancel 置位后，worker 在安全点调用
  raise_if_cancelled() 立即抛 TaskCancelledError，从而停止本产品可控的排队、Provider 流读取、
  事件发布、Word worker 与 artifact 发布。第三方 Provider 已接收请求后的内部计算或计费
  不承诺撤销（PLAN V220-G02）。
- RevisionFence：绑定 (task_id, locked_revision)。worker 每次把现状结果写回前必须
  assert_writable()；任务被取消、或该 run 已被新的前台活动任务接管/释放（旧 revision 不再
  活动）时抛 RevisionFenceError，从而拒收旧任务迟到结果、防止旧 revision 覆盖新任务当前结果。
- TaskRunRegistry：进程内登记当前运行的任务与其清理回调。request_cancel 置位取消 token、撤销
  fence 并执行全部登记清理（Provider client、后台 task、Word worker、文件句柄），随后释放本地
  活动槽 —— 新任务可立即开始。

"单前台活动任务"的 DB 级门禁仍在 task_repository.assert_single_active；本模块只承担运行期取消
信号与 fence。二者共同满足 Gate 6.1 的"无泄漏 + 迟到拒收 + 立即开始新任务"。
"""
from __future__ import annotations

import threading
from typing import Callable, Optional

from core.errors import DomainError


class TaskCancelledError(DomainError):
    """协作式取消信号：worker 在安全点被要求停止。"""

    stage = "task"
    error_code = "TASK_CANCELLED"
    http_status = 409
    retryable = False


class RevisionFenceError(DomainError):
    """revision fence 拒收：run 已取消/被新任务接管，迟到结果不得写回。"""

    stage = "task"
    error_code = "REVISION_FENCE_REJECTED"
    http_status = 409
    retryable = False


class CancellationToken:
    """线程安全、幂等的取消标志（每运行任务一个）。"""

    def __init__(self) -> None:
        self._event = threading.Event()

    def request_cancel(self) -> bool:
        """首次置位返回 True；重复置位返回 False（幂等，可安全重复请求）。"""
        already = self._event.is_set()
        self._event.set()
        return not already

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        """worker 安全点：已请求取消则抛 TaskCancelledError。"""
        if self._event.is_set():
            raise TaskCancelledError("任务已请求取消")

    def reset(self) -> None:
        self._event.clear()


class RevisionFence:
    """绑定 (task_id, locked_revision) 的写入门禁。"""

    def __init__(self, task_id: str, revision: int) -> None:
        self.task_id = task_id
        self.revision = revision
        self._active = True
        self._lock = threading.Lock()

    def is_active(self) -> bool:
        with self._lock:
            return self._active

    def revoke(self) -> None:
        with self._lock:
            self._active = False

    def assert_writable(self) -> None:
        """写回前门禁：已取消/被接管则抛 RevisionFenceError（迟到结果拒收）。"""
        if not self.is_active():
            raise RevisionFenceError(
                f"revision fence 拒收：任务 {self.task_id} rev{self.revision} 已取消/被接管",
                details={"task_id": self.task_id, "revision": self.revision},
            )


class TaskRunContext:
    """一次生成运行的上下文：取消 token + revision fence + 待清理资源。"""

    def __init__(self, task_id: str, revision: int) -> None:
        self.task_id = task_id
        self.revision = revision
        self.token = CancellationToken()
        self.fence = RevisionFence(task_id, revision)
        self._cleanups: list[Callable[[], None]] = []
        self._cleanup_lock = threading.Lock()

    def add_cleanup(self, fn: Callable[[], None]) -> None:
        with self._cleanup_lock:
            self._cleanups.append(fn)

    def run_cleanups(self) -> int:
        """顺序执行全部清理回调；单个失败不阻止后续。返回登记数量（可核对无遗漏）。"""
        with self._cleanup_lock:
            fns = list(self._cleanups)
            self._cleanups.clear()
        for fn in fns:
            try:
                fn()
            except Exception:
                # 单个清理失败不阻断其余；调用方依据登记数与可见清理结果判断是否泄漏
                pass
        return len(fns)

    def raise_if_cancelled(self) -> None:
        self.token.raise_if_cancelled()

    def assert_writable(self) -> None:
        """生成 worker 写回前统一门禁：先 fence，再取消信号。"""
        self.fence.assert_writable()
        self.token.raise_if_cancelled()


class TaskRunRegistry:
    """进程内登记当前运行的任务；负责请求取消与释放本地活动槽。"""

    def __init__(self) -> None:
        self._runs: dict[str, TaskRunContext] = {}
        self._lock = threading.Lock()

    def start(self, task_id: str, revision: int) -> TaskRunContext:
        """登记（或替换）某任务的运行；旧 run 若仍存在，先撤销其 fence 并清理。"""
        with self._lock:
            ctx = self._runs.get(task_id)
            if ctx is not None:
                ctx.fence.revoke()
                ctx.run_cleanups()
            ctx = TaskRunContext(task_id, revision)
            self._runs[task_id] = ctx
            return ctx

    def get(self, task_id: str) -> Optional[TaskRunContext]:
        with self._lock:
            return self._runs.get(task_id)

    def request_cancel(self, task_id: str) -> bool:
        """请求取消：置位 token、撤销 fence、执行清理、释放活动槽。返回是否确有登记。"""
        with self._lock:
            ctx = self._runs.get(task_id)
            if ctx is None:
                return False
            self._runs.pop(task_id, None)
        ctx.token.request_cancel()
        ctx.fence.revoke()
        ctx.run_cleanups()
        return True

    def active_count(self) -> int:
        with self._lock:
            return len(self._runs)

    def running_task_ids(self) -> list[str]:
        with self._lock:
            return list(self._runs.keys())

    def reset(self) -> None:
        """测试/收口用：撤销全部 fence 并清空登记。"""
        with self._lock:
            for ctx in self._runs.values():
                ctx.fence.revoke()
            self._runs.clear()


# 进程内默认单例（生成 worker / service / API 共享）。
registry = TaskRunRegistry()