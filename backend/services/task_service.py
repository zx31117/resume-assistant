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
import os
import threading
from typing import Any

from sqlalchemy.orm import Session

from core.task import TaskStatus
from core.task_cancel import registry
from core.owner import current_user_id, LocalOwnerContext
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


def _require_jd(jd: str) -> str:
    """V220-G02：JD 至少 60 字（以服务端为最终权威）。

    freeze_input 是生成点击的最终入口，这里作为服务端 backstop；草稿保存(save_draft)
    仍是宽松草稿，不在此收紧（保证输入中频繁自动保存不被拦截）。
    """
    if jd is None or not str(jd).strip():
        raise TaskInputValidationError(
            "JD 必填（V220-G02）；至少 60 字",
            details={"missing": ["jd"], "jd_len": len(str(jd or ""))},
        )
    j = str(jd).strip()
    if len(j) < 60:
        raise TaskInputValidationError(
            f"JD 至少 60 字（V220-G02），当前 {len(j)} 字",
            details={"missing": [], "jd_len": len(j), "min_jd_len": 60},
        )
    return j


def _run_task_cleanup(db: Session) -> None:
    """任务进入终态后的一次 cleanup（T9）。幂等；失败可见但不影响任务终态结果。"""
    try:
        from services.task_cleanup import run_cleanup
        run_cleanup(db)
        db.commit()
    except Exception as e:  # noqa: BLE001
        db.rollback()
        logger.error("T9 task-terminal cleanup failed task=%r: %r", id(db), e)


def _rollback_promoted(promoted: dict[str, Any] | None) -> None:
    """把已提升到发布目录、但事务未提交的 artifact 文件删除（幂等、错误可见）。"""
    if not promoted:
        return
    try:
        from services import document_assembler
        document_assembler._rollback_promoted(promoted)
    except Exception:  # noqa: BLE001
        logger.error("rollback promoted artifacts failed", exc_info=True)


def _cleanup_staging_quiet(task_id: str) -> bool:
    """删除本任务的 staging 根（幂等）。失败只记录，不影响任务终态。"""
    try:
        from services import artifact_store
        ok = artifact_store.cleanup_task_staging(task_id)
        if not ok:
            logger.error("staging cleanup incomplete task_id=%s", task_id)
        return ok
    except Exception:  # noqa: BLE001
        logger.error("staging cleanup failed task_id=%s", task_id, exc_info=True)
        return False


def _cleanup_staging_visible(db: Session, task, artifacts: dict[str, Any]) -> None:
    """发布成功后清理 staging 并把结果写入快照（错误可见，不静默）。"""
    try:
        from services import artifact_store
        ok = artifact_store.cleanup_dir_quiet(artifacts.get("staging_dir") or "")
        if not ok:
            logger.error("staging dir cleanup incomplete after publish task_id=%s",
                         getattr(task, "task_id", ""))
    except Exception:  # noqa: BLE001
        ok = False
        logger.error("staging dir cleanup failed after publish", exc_info=True)
    try:
        from database.models import TaskSnapshot
        snap = (db.query(TaskSnapshot).filter_by(task_id=task.task_id).first())
        if snap is not None and isinstance(snap.payload, dict):
            payload = dict(snap.payload)
            payload["staging_cleanup_ok"] = bool(ok)
            snap.payload = payload
    except Exception:  # noqa: BLE001
        logger.warning("record staging cleanup verdict failed", exc_info=True)


def _require_owner(task) -> None:
    """V2.2.0 P0：任务必须归属当前 owner，否则等价于不存在（404）。

    旧任务/异主任务（user_id IS NULL 的 LEGACY_UNOWNED，或其他身份）一律隔离，
    视同任务不存在——不做列选/后续访问，从 True Source 上拒绝越权触碰。
    """
    if task is None or task.user_id != current_user_id():
        raise TaskNotFoundError(
            f"任务不存在：{getattr(task, 'task_id', '')}",
            details={"task_id": getattr(task, 'task_id', '')},
        )


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
        _require_owner(task)
        self._repo.set_draft_input(task, name=name, phone=phone, email=email,
                                   location=location, jd=jd)
        self._db.commit()
        return self._view(task_id)

    def freeze_input(self, task_id: str, *, name: str, phone: str = "",
                     email: str = "", location: str = "", jd: str = "") -> dict[str, Any]:
        name = _require_name(name)
        jd = _require_jd(jd)   # V220-G02：JD 至少 60 字（服务端权威）
        task = self._repo.get(task_id)
        if task is None:
            raise TaskNotFoundError(f"任务不存在：{task_id}", details={"task_id": task_id})
        _require_owner(task)
        self._repo.freeze_input(task, name=name, phone=phone, email=email,
                                location=location, jd=jd)
        self._db.commit()
        return self._view(task_id)

    def start_task(self, task_id: str) -> dict[str, Any]:
        task = self._repo.get(task_id)
        if task is None:
            raise TaskNotFoundError(f"任务不存在：{task_id}", details={"task_id": task_id})
        _require_owner(task)
        self._repo.assert_single_active(exclude_task_id=task_id)
        self._repo.transition(task, TaskStatus.RUNNING)
        self._db.commit()
        return self._view(task_id)

    def get_task(self, task_id: str) -> dict[str, Any]:
        view = self._repo.get_view(task_id)
        if view is None:
            raise TaskNotFoundError(f"任务不存在：{task_id}", details={"task_id": task_id})
        if view.user_id != current_user_id():  # V2.2.0 P0：异主/LEGACY 隔离
            raise TaskNotFoundError(f"任务不存在：{task_id}", details={"task_id": task_id})
        return _task_view_dict(view)

    def list_records(self, *, limit: int = 200) -> list[dict[str, Any]]:
        """列出真实可用的生成记录（V220-R2-T08：我的简历）。

        V2.2.0 Revision 3 返工：对每一条候选记录做**文件级 fail-closed 校验**——
        已登记的不可变 artifact 引用必须指向真实存在、非零、hash 一致的文件；
        任一不成立则整条记录从列表剔除（绝不暴露假成功下载入口）。
        """
        from services import artifact_store

        rows = self._repo.list_records(limit=limit)
        out: list[dict[str, Any]] = []
        for rec in rows:
            arts = rec.get("artifacts") or []
            if not arts:
                continue  # 无任何已登记 artifact → 不是可下载的真实记录
            verified: list[dict[str, Any]] = []
            damaged = False
            for a in arts:
                ok, path = self._verify_artifact_on_disk(a)
                if not ok:
                    damaged = True
                    break
                verified.append({**a, "download_path": path})
            if damaged or not verified:
                logger.warning("records: 剔除存在损坏/缺失 artifact 的记录 task_id=%s",
                               rec.get("task_id"))
                continue
            rec = dict(rec)
            rec["artifacts"] = verified
            out.append(rec)
        return out

    def _verify_artifact_on_disk(self, art: dict[str, Any]) -> tuple[bool, str]:
        """校验已登记 artifact 的文件确实存在、非零且 hash 一致。返回 (ok, 相对语义路径)。"""
        from services import artifact_store

        fn = art.get("file_name") or ""
        if not fn:
            return False, ""
        abs_path = os.path.join(str(artifact_store.publish_root()), fn)
        if not artifact_store.assert_inside_publish(abs_path):
            return False, ""
        if not os.path.isfile(abs_path) or os.path.getsize(abs_path) <= 0:
            return False, ""
        if art.get("size_bytes") and os.path.getsize(abs_path) != int(art["size_bytes"]):
            return False, ""
        if art.get("sha256") and artifact_store.sha256_file(abs_path) != art["sha256"]:
            return False, ""
        return True, f"{(art.get('rel_dir') or 'output')}/{fn}"

    def resolve_artifact_download(self, task_id: str, kind: str) -> dict[str, Any]:
        """task-scoped、owner-scoped 的 artifact 下载解析（RESULT §R3-18 B）。

        授权链：当前 owner → Task（owner 必须匹配）→ 已登记的不可变 artifact 引用
        → 明确 artifact kind → 实际文件。客户端传入的 filename/basename/相对路径
        一律不参与授权。

        未授权与不存在对象返回同一错误（不泄露存在性差异）：`TaskNotFoundError`（404）。
        """
        from services import artifact_store

        k = (kind or "").strip().lower()
        if k not in ("docx", "pdf"):
            raise TaskNotFoundError(
                f"任务或产物不存在：{task_id}",
                details={"task_id": task_id},
            )
        task = self._repo.get(task_id)
        if task is None or task.user_id != current_user_id():
            raise TaskNotFoundError(
                f"任务或产物不存在：{task_id}", details={"task_id": task_id})
        if TaskStatus(task.status) != TaskStatus.SUCCEEDED:
            raise TaskNotFoundError(
                f"任务或产物不存在：{task_id}", details={"task_id": task_id})
        ref = self._repo.resolve_artifact(
            task_id, k, resume_revision=task.published_resume_revision)
        if ref is None or ref.get("user_id") != current_user_id():
            raise TaskNotFoundError(
                f"任务或产物不存在：{task_id}", details={"task_id": task_id})
        ok, _ = self._verify_artifact_on_disk(ref)
        if not ok:
            # 已登记但磁盘对象缺失/损坏 → fail closed，同样报“不存在”（不泄露差异）。
            raise TaskNotFoundError(
                f"任务或产物不存在：{task_id}", details={"task_id": task_id})
        abs_path = os.path.join(str(artifact_store.publish_root()), ref["file_name"])
        return {**ref, "abs_path": abs_path}

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        """实际取消（PLAN V220-G02 / Gate 6.1）。

        从 RUNNING/CANCELLING 出发：先请求运行期协作式取消（置位 token、撤销 revision
        fence、执行登记清理、释放本地活动槽），随后把未结束子任务置 CANCELLED，最后
        落地 CANCELLED 终态。迟到结果经 repository 写入门禁 + fence 双保险拒收。
        """
        task = self._repo.get(task_id)
        if task is None:
            raise TaskNotFoundError(f"任务不存在：{task_id}", details={"task_id": task_id})
        _require_owner(task)
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
        _require_owner(task)
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
        preload: Optional[dict[str, list[dict[str, Any]]]] = None,
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
        _require_owner(task)
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
            promoted_for_rollback: dict[str, Any] | None = None
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
                        local, task_id=task_id, contact=contact,
                        template_id="pm_template",  # V2.2.0 P0：装配归主用真实 owner，不用 task_id 冒充
                    )
                )
                summary = generate_task(local, db_task, ctx, input_view,
                                        budget=None, provider=provider,
                                        selector=selector, assembler=effective_assembler,
                                        preload=preload)
                # V2.2.0 Revision 3 返工：产物先写 task-scoped staging → 全量内容校验 →
                # 同盘原子提升 → 在**同一 DB 事务**登记不可变 artifact 引用 + SUCCEEDED。
                # 任一环节失败都不得出现 SUCCEEDED，并回滚已提升文件与 staging。
                promoted_for_rollback = document_assembler.promote_staged_artifacts(
                    summary.artifacts or {})
                repo.publish_success(db_task, resume_revision=revision,
                                     promoted=promoted_for_rollback)
                local.commit()
                promoted_for_rollback = None  # 已提交：不再需要回滚
                logger.info("run_generation SUCCEEDED task_id=%s revision=%d", task_id, revision)
                # 发布成功后才清理 staging（提升已移走文件，目录应为空）。
                _cleanup_staging_visible(local, db_task, summary.artifacts or {})
                _run_task_cleanup(local)  # T9：任务进入终态后触发 cleanup（幂等）
            except TaskCancelledError:
                local.rollback()
                _rollback_promoted(promoted_for_rollback)
                _cleanup_staging_quiet(task_id)
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
                _rollback_promoted(promoted_for_rollback)
                _cleanup_staging_quiet(task_id)
                from core.errors import DomainError as _DE
                code = e.error_code if isinstance(e, _DE) else "GENERATION_FAILED"
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

    def continue_failed_scope(self, source_task_id: str, *,
                              provider: object | None = None) -> dict[str, Any]:
        """「只重试失败范围」续试任务：从 FAILED 源任务创建续试任务（新 task_id）。

        - 保持 FAILED 为终态（不改状态机），以**新任务**承载续试（PLAN 不要求沿用同一 task_id）；
        - 复用源任务已完成经历（SUCCEEDED 子任务的 fact_results，零模型调用），仅重跑未完成经历；
        - 由此调用只发生在失败范围，已完成结果被复用。
        """
        from core import task as task_domain
        from database.models import InputRevision, TaskSnapshot, TaskSubtask
        from services import fact_service
        from services.task_generation import PreparedExperience, PreparedFact

        src = self._repo.get(source_task_id)
        if src is None:
            raise TaskNotFoundError(f"源任务不存在:{source_task_id}", details={"task_id": source_task_id})
        # V2.2.0 P0：续试仅对当前 owner 的 FAILED 源开放；LEGACY_UNOWNED（无主）与
        # 异主源一律隔离（视同不存在）。续试新任务继承当前 owner（create 已写入 user_id）。
        _require_owner(src)
        if task_domain.TaskStatus(src.status) != task_domain.TaskStatus.FAILED:
            raise TaskStateError(
                f"仅 FAILED 任务可续试失败范围，当前 {src.status}",
                details={"task_id": source_task_id, "status": src.status})

        subs = (self._db.query(TaskSubtask).filter_by(task_id=source_task_id)
                .order_by(TaskSubtask.sort_order, TaskSubtask.id).all())
        succeeded: dict[str, list[dict[str, Any]]] = {}
        incomplete: list[str] = []
        slot_by_exp: dict[str, tuple[int, str]] = {}
        for s in subs:
            slot_by_exp[s.experience_id] = (s.sort_order, s.experience_id)
            if s.status == task_domain.SubtaskStatus.SUCCEEDED.value:  # noqa: SIM
                succeeded[s.experience_id] = list(s.fact_results or [])
            else:
                incomplete.append(s.experience_id)

        if not succeeded:
            raise TaskStateError("源任务无已完成子任务可复用，无法续试失败范围",
                                 details={"task_id": source_task_id})
        if not incomplete:
            raise TaskStateError("源任务已全部完成，无失败范围可续试",
                                 details={"task_id": source_task_id})

        # 源 P2 选择顺序（sort_order 保序），兜底用子任务顺序
        snap = (self._db.query(TaskSnapshot).filter_by(task_id=source_task_id).first())
        selected_slots: list[tuple[int, str, str]] = []
        if snap and snap.payload and snap.payload.get("experiences"):
            for e in snap.payload["experiences"]:
                selected_slots.append((int(e.get("sort_order", 0) or 0),
                                       e.get("experience_id", ""),
                                       e.get("title") or e.get("experience_id", "")))
        for eid, (order, title) in slot_by_exp.items():
            if eid not in {s[1] for s in selected_slots}:
                selected_slots.append((order, eid, eid))
        selected_slots.sort(key=lambda x: x[0])

        # 源冻结入参 → 续试任务沿用同一输入
        latest = (self._db.query(InputRevision).filter_by(task_id=source_task_id)
                  .order_by(InputRevision.revision.desc()).first())
        if latest is None:
            raise TaskStateError("源任务无冻结入参，无法续试", details={"task_id": source_task_id})

        # 为失败范围抓取源 Fact（供重跑）
        fact_objs = fact_service.list_facts_for_experiences(self._db, incomplete)
        facts_by_exp: dict[str, list[PreparedFact]] = {}
        for f in fact_objs:
            facts_by_exp.setdefault(f.experience_id, []).append(PreparedFact(
                fact_id=f.fact_id, text=f.text or "",
                fact_type=f.fact_type.value if hasattr(f.fact_type, "value") else str(f.fact_type),
                source_text=f.source_text or ""))

        # 建续试任务（新 task_id，界面独立可操作）
        tid = self.create_task()["task_id"]
        kw = dict(name=latest.name or "", phone=latest.phone or "", email=latest.email or "",
                  location=latest.location or "", jd=latest.jd or "")
        self.save_draft(tid, **kw)
        self.freeze_input(tid, **kw)
        self.start_task(tid)

        # selector：按源选材范围重建（completed 以空 Fact 占位，由 preload 覆盖；失败范围带源 Fact）
        def _scope_selector(compact):
            preps = []
            for order, eid, title in selected_slots:
                preps.append(PreparedExperience(eid, order, title,
                                                facts=facts_by_exp.get(eid, [])))
            return preps

        self.run_generation(tid, provider=provider, selector=_scope_selector, preload=succeeded)
        return self._view(tid)

    def _view(self, task_id: str) -> dict[str, Any]:
        view = self._repo.get_view(task_id)
        if view is None:  # 理论上不应发生（刚写入/读取同一 ID）
            raise TaskNotFoundError(f"任务不存在：{task_id}", details={"task_id": task_id})
        return _task_view_dict(view)


def _task_view_dict(view) -> dict[str, Any]:
    return {
        "task_id": view.task_id,
        "user_id": view.user_id,
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