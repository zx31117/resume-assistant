"""V2.2.0 T3：Task 应用服务层（PLAN §2.3 / V220-G01/G02）。

封装 TaskRepository 为 API 可用的编排点，收口三个不变量：
- 创建：无输入，返回后端确认的 DRAFT TaskView；
- 保存：姓名必填（V220-G02），电话/邮箱/所在地选填，JD 原文保存；仅 DRAFT 可编辑；
- 冻结：进入 READY，生成不可变 InputRevision（revision+1），返回后端确认的视图；
- 启动：置 RUNNING 前先执行"单前台活动任务"门禁（ActiveTaskConflictError，fail closed）；
- 读取：返回 TaskView（含权威快照与最新入参），供刷新/重连/恢复使用。

所有持久化写通过 repository；service 负责提交事务并做 API 层校验。
"""
from __future__ import annotations

import logging
import threading
from typing import Any

from sqlalchemy.orm import Session

from core.task import TaskStatus
from core.task_cancel import registry
from services.task_repository import (
    TaskInputValidationError,
    TaskNotFoundError,
    TaskRepository,
    TaskStateError,
)

logger = logging.getLogger(__name__)


def _require_name(name: str) -> str:
    if name is None or not str(name).strip():
        raise TaskInputValidationError(
            "姓名必填（V220-G02）；电话、邮箱、所在地可选",
            details={"missing": ["name"]},
        )
    return str(name).strip()


def _run_task_cleanup(db: Session) -> None:
    """任务进入终态后的一次 cleanup（T9）。幂等；失败可见但不影响任务终态结果。"""
    try:
        from services.task_cleanup import run_cleanup
        run_cleanup(db)
        db.commit()
    except Exception as e:  # noqa: BLE001
        db.rollback()
        logger.error("T9 task-terminal cleanup failed task=%r: %r", id(db), e)


class TaskService:
    """使用显式传入 session（由 FastAPI get_db 提供）。"""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = TaskRepository(db)

    def create_task(self) -> dict[str, Any]:
        task = self._repo.create()
        self._db.commit()
        return self._view(task.task_id)

    def save_draft(self, task_id: str, *, name: str, phone: str = "",
                   email: str = "", location: str = "", jd: str = "") -> dict[str, Any]:
        name = _require_name(name)
        task = self._repo.get(task_id)
        if task is None:
            raise TaskNotFoundError(f"任务不存在：{task_id}", details={"task_id": task_id})
        self._repo.set_draft_input(task, name=name, phone=phone, email=email,
                                   location=location, jd=jd)
        self._db.commit()
        return self._view(task_id)

    def freeze_input(self, task_id: str, *, name: str, phone: str = "",
                     email: str = "", location: str = "", jd: str = "") -> dict[str, Any]:
        name = _require_name(name)
        task = self._repo.get(task_id)
        if task is None:
            raise TaskNotFoundError(f"任务不存在：{task_id}", details={"task_id": task_id})
        self._repo.freeze_input(task, name=name, phone=phone, email=email,
                                location=location, jd=jd)
        self._db.commit()
        return self._view(task_id)

    def start_task(self, task_id: str) -> dict[str, Any]:
        task = self._repo.get(task_id)
        if task is None:
            raise TaskNotFoundError(f"任务不存在：{task_id}", details={"task_id": task_id})
        # 单前台活动任务门禁（排除自身，幂等允许重复 RUNNING）
        self._repo.assert_single_active(exclude_task_id=task_id)
        self._repo.transition(task, TaskStatus.RUNNING)
        self._db.commit()
        return self._view(task_id)

    def get_task(self, task_id: str) -> dict[str, Any]:
        view = self._repo.get_view(task_id)
        if view is None:
            raise TaskNotFoundError(f"任务不存在：{task_id}", details={"task_id": task_id})
        return _task_view_dict(view)

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        """实际取消（PLAN V220-G02 / Gate 6.1）。

        从 RUNNING/CANCELLING 出发：先请求运行期协作式取消（置位 token、撤销 revision
        fence、执行登记清理、释放本地活动槽），随后把未结束子任务置 CANCELLED，最后
        落地 CANCELLED 终态。迟到结果经 repository 写入门禁 + fence 双保险拒收。
        """
        task = self._repo.get(task_id)
        if task is None:
            raise TaskNotFoundError(f"任务不存在：{task_id}", details={"task_id": task_id})
        cur = TaskStatus(task.status)
        if cur not in (TaskStatus.RUNNING, TaskStatus.CANCELLING):
            raise TaskStateError(
                f"仅 RUNNING/CANCELLING 状态可取消，当前 {task.status}",
                details={"task_id": task_id, "status": task.status},
            )
        # 运行期协作式取消 + 清理 + 释放本地活动槽（DB 活动槽随后经 CANCELLED 释放）
        registry.request_cancel(task_id)
        if cur != TaskStatus.CANCELLING:
            self._repo.transition(task, TaskStatus.CANCELLING)
        self._repo.cancel_open_subtasks(task)
        self._repo.transition(task, TaskStatus.CANCELLED, terminal_error="TASK_CANCELLED")
        self._db.commit()
        return self._view(task_id)

    def start_run(self, task_id: str) -> tuple[str, int, dict[str, Any]]:
        """登记一次生成运行，返回 (task_id, revision, TaskRunContext)。供 T6 生成 worker 使用。

        复用协作式取消与 revision fence 机制：生成开始前登记 run，写回前经
        ctx.assert_writable()（先 fence 再取消信号）；取消时 registry 统一清理并释放活动槽。
        """
        task = self._repo.get(task_id)
        if task is None:
            raise TaskNotFoundError(f"任务不存在：{task_id}", details={"task_id": task_id})
        revision = task.current_input_revision or 0
        ctx = registry.start(task_id, revision)
        return task_id, revision, ctx

    def run_generation(
        self,
        task_id: str,
        *,
        provider: object | None = None,
        selector: object | None = None,
        assembler: object | None = None,
    ) -> dict[str, Any]:
        """启动一次生成运行（异步 worker），接通 task_generation 编排器（PLAN §2.1 / T06d）。

        - 任务须已 RUNNING（API 先 start_task 置 RUNNING）；
        - worker 线程自行获取独立 session 执行 P1–P4，独占写 DB（规避 SQLite 线程不安全）；
        - 运行成功且 assembler 装配完成 → SUCCEEDED；显式取消/协作取消 → CANCELLED；
          其他失败 → FAILED（终态错误码稳定，不存正文/堆栈）。
        - assembler=None 时（T06 阶段未接入真实 DOCX），内容生成成功即落地 SUCCEEDED，
          快照记录 P4.pending；T07 接入 assembler 后升级为装配+发布产物。
        """
        task = self._repo.get(task_id)
        if task is None:
            raise TaskNotFoundError(f"任务不存在：{task_id}", details={"task_id": task_id})
        if TaskStatus(task.status) != TaskStatus.RUNNING:
            raise TaskStateError(
                f"仅 RUNNING 状态可启动生成，当前 {task.status}",
                details={"task_id": task_id, "status": task.status},
            )
        revision = task.current_input_revision or 0
        self._db.commit()  # 确保 RUNNING 已落盘，worker 独立 session 才能读到

        from core import task as task_domain
        from core.errors import ContentGenerationError
        from core.task_cancel import TaskCancelledError
        from database import models as db_models
        from database import session as db_session
        from services.task_repository import TaskRepository

        _train_terminal = (task_domain.TaskStatus.SUCCEEDED,
                           task_domain.TaskStatus.FAILED,
                           task_domain.TaskStatus.CANCELLED)

        def _worker() -> None:
            from services.task_generation import generate_task

            local = db_session.SessionLocal()
            try:
                db_task = local.get(db_models.Task, task_id)
                if db_task is None:
                    return
                ctx = registry.start(task_id, revision)
                repo = TaskRepository(local)
                latest = (local.query(db_models.InputRevision)
                          .filter_by(task_id=task_id, revision=revision).first())
                input_view = {
                    "revision": revision,
                    "name": latest.name or "" if latest else "",
                    "phone": latest.phone or "" if latest else "",
                    "email": latest.email or "" if latest else "",
                    "location": latest.location or "" if latest else "",
                    "jd": latest.jd or "" if latest else "",
                    "input_hash": latest.input_hash or "" if latest else "",
                }
                # V2.2.0 T07：P4 装配默认接入真实 DOCX/PDF 链（assembler=None 时
                # 用任务管线 assembler；显式传入则沿用调用方）。
                contact = {
                    "name": input_view["name"], "phone": input_view["phone"],
                    "email": input_view["email"], "location": input_view["location"],
                }
                from services import document_assembler
                effective_assembler = assembler if assembler is not None else (
                    document_assembler.make_task_assembler(
                        local, contact=contact,
                        template_id="pm_template", user_id=task_id,
                    )
                )
                summary = generate_task(local, db_task, ctx, input_view,
                                        budget=None, provider=provider,
                                        selector=selector, assembler=effective_assembler)
                # 先落地 SUCCEEDED，再发布产物引用（publish_artifacts 仅允许在 SUCCEEDED
                # 终态写入发布路径；倒序会被 guard 拒绝，如 T10 真实装配链暴露）。
                repo.transition(db_task, TaskStatus.SUCCEEDED)
                if summary.assembled and summary.artifacts.get("docx_path"):
                    repo.publish_artifacts(
                        db_task, resume_revision=revision,
                        docx_path=summary.artifacts["docx_path"],
                        pdf_path=summary.artifacts.get("pdf_path") or "",
                    )
                local.commit()
                logger.info("run_generation SUCCEEDED task_id=%s revision=%d", task_id, revision)
                _run_task_cleanup(local)  # T9：任务进入终态后触发 cleanup（幂等）
            except TaskCancelledError:
                local.rollback()
                cancelled = local.get(db_models.Task, task_id)
                if cancelled is not None:
                    try:
                        TaskRepository(local).transition(
                            cancelled, TaskStatus.CANCELLED, terminal_error="TASK_CANCELLED")
                        local.commit()
                        _run_task_cleanup(local)  # T9：进入终态后 cleanup
                    except Exception:
                        local.rollback()
            except Exception as e:  # noqa: BLE001
                local.rollback()
                code = e.error_code if isinstance(e, ContentGenerationError) else "GENERATION_FAILED"
                failed = local.get(db_models.Task, task_id)
                if failed is not None and TaskStatus(failed.status) not in _train_terminal:
                    try:
                        TaskRepository(local).transition(failed, TaskStatus.FAILED, terminal_error=code)
                        local.commit()
                        logger.warning("run_generation FAILED task_id=%s code=%s err=%r",
                                       task_id, code, e)
                        _run_task_cleanup(local)  # T9：进入终态后 cleanup（幂等）
                    except Exception as ce:  # noqa: BLE001
                        local.rollback()
                        logger.error("run_generation finalize FAILED task_id=%s err=%r", task_id, ce)
                else:
                    logger.warning("run_generation FAILED task_id=%s code=%s (already terminal) err=%r",
                                   task_id, code, e)
            finally:
                local.close()

        _ = threading.Thread(target=_worker, name=f"taskGen-{task_id[:8]}", daemon=True)
        _.start()
        return self._view(task_id)

    def _view(self, task_id: str) -> dict[str, Any]:
        view = self._repo.get_view(task_id)
        if view is None:  # 理论上不应发生（刚写入/读取同一 ID）
            raise TaskNotFoundError(f"任务不存在：{task_id}", details={"task_id": task_id})
        return _task_view_dict(view)


def _task_view_dict(view) -> dict[str, Any]:
    return {
        "task_id": view.task_id,
        "status": view.status,
        "current_input_revision": view.current_input_revision,
        "active_operation_id": view.active_operation_id,
        "seq": view.seq,
        "created_at": view.created_at.isoformat() if view.created_at else "",
        "updated_at": view.updated_at.isoformat() if view.updated_at else "",
        "expires_at": view.expires_at.isoformat() if view.expires_at else None,
        "terminal_error": view.terminal_error,
        "published_resume_revision": view.published_resume_revision,
        "published_docx_path": view.published_docx_path,
        "published_pdf_path": view.published_pdf_path,
        "latest_input": view.latest_input,
        "subtasks": view.subtasks,
        "snapshot": view.snapshot,
    }