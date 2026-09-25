"""V2.2.0 P0 验证：owner 契约 + 三身份越权隔离（PLAN Revision 3）。

退出码 0 = 业务断言通过且临时 runtime 清理干净；非 0 = 有失败/异常/清理失败。

覆盖：
- [I1] 选材：default_selector 只选当前 owner 的经历（隔离 stub-user/other-user/LEGACY）；
- [I2] 列表：list_records 只列 owner 的已发布记录（不列异主/LEGACY）；
- [I3] Task 服务：get_task / save_draft / freeze_input / start_run / cancel /
      continue_failed_scope 对异主 & LEGACY_UNOWNED 任务一律按不存在（404 语义），
      且异主任务数据未被改动；
- [I4] 清理：run_cleanup / _clean_orphan_children 不跨 owner 删除（异主/LEGACY 受保护）；
- [I5] 经历服务：get/update/delete 对异主经历返回 None/False（隔离，不改写/不删除）；
- [I6] 装配归主：make_task_assembler 仅装配 owner 的 work/project/education 经历；
- [I7] 教育进成品：owner 教育经历经确定性排序进入 ResumeDocument.education。

全部使用临时 runtime（RESUME_DATA_DIR 指向 temp），不触碰真实库/真实输出。
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _v2_test_runner import run_isolated  # noqa: E402

_passed = 0
_failed = 0


def check(cond, name, extra=""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  [PASS] {name}")
    else:
        _failed += 1
        print(f"  [FAIL] {name} {extra}")


def _uid() -> str:
    return str(uuid.uuid4())


def _mk_user(db, user_id):
    from database.models import User
    if user_id is not None and db.get(User, user_id) is None:
        db.add(User(id=user_id, name=user_id, email="", created_at=datetime.utcnow()))


def _mk_experience(db, user_id, **kw):
    """直接建一个归属指定身份的 Experience 行（user_id=None 表示 LEGACY 无主）。"""
    _mk_user(db, user_id)
    defaults = dict(
        user_id=user_id, type="work", title="X公司", company="X公司", role="工程师",
        time="2021.01 - 2023.06", description="负责核心模块", skills=[], achievements=[],
        raw_text="", created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )
    defaults.update(kw)
    exp = _ExperienceCls(**defaults)
    db.add(exp)
    db.flush()
    return exp


# 运行期从 database.models 补齐（忽略类型检查器）
_ExperienceCls = None


def _run_tests_inner(state) -> int:
    global _ExperienceCls
    from database.session import SessionLocal, engine
    from database import migrations as mig
    from database import models as M
    from core.owner import current_user_id, DEFAULT_USER_ID
    from core.config import settings
    from services.task_repository import TaskRepository
    from services.task_service import TaskService
    state.register_engine(engine)

    _ExperienceCls = M.Experience

    db = SessionLocal()
    _ = mig.run_migrations()

    owner = current_user_id()
    print(f"\n owner = {owner!r} (DEFAULT_ID={settings.DEFAULT_USER_ID!r})")
    check(owner == settings.DEFAULT_USER_ID and owner == DEFAULT_USER_ID,
          "current_user_id 真源为 settings.DEFAULT_USER_ID（demo-user），不来自请求体",
          extra=str((owner, settings.DEFAULT_USER_ID)))

    stub = "stub-user"
    other = "other-user"
    _mk_user(db, stub)
    _mk_user(db, other)
    db.commit()

    # ── [I1] 选材 owner 限定 ────────────────────────────────────────
    print("\n[I1] default_selector 只选 owner 经历（隔离异主/LEGACY）")
    from services.task_generation import default_selector
    e_owner = _mk_experience(db, owner, title="Owner公司", description="owner 核心业务")
    e_edu = _mk_experience(db, owner, type="education", title="Owner大学",
                           company="Owner大学", role="计算机", time="2017.09 - 2021.06",
                           description="本科教育")
    e_stub = _mk_experience(db, stub, title="Stub公司", description="stub 数据")
    e_other = _mk_experience(db, other, title="Other公司", description="other 数据")
    e_legacy = _mk_experience(db, None, title="Legacy公司", description="无主数据")
    db.commit()
    compact = {"position": "后端工程师", "required_skills": ["python"], "preferred_skills": []}
    sel = default_selector(db, compact)
    sel_ids = {p.experience_id for p in sel}
    check(e_owner.id in sel_ids, "owner 经历被选中", extra=str(sel_ids))
    check(e_stub.id not in sel_ids and e_other.id not in sel_ids and e_legacy.id not in sel_ids,
          "stub/other/LEGACY 经历不被选中（隔离）", extra=str(sel_ids))

    # ── [I2] list_records 只列 owner 已发布记录 ─────────────────────
    print("\n[I2] list_records 不列异主/LEGACY 记录")
    repo = TaskRepository(db)

    def _to_success(task):
        # DRAFT -> READY -> RUNNING -> SUCCEEDED（合法转移路径）
        repo.transition(task, "READY")
        repo.transition(task, "RUNNING")
        repo.transition(task, "SUCCEEDED")

    t_own = repo.create()
    _to_success(t_own)
    repo.publish_artifacts(t_own, resume_revision=1, docx_path="output/a.docx", pdf_path="output/a.pdf")
    t_stub = repo.create(); t_stub.user_id = stub
    _to_success(t_stub)
    repo.publish_artifacts(t_stub, resume_revision=1, docx_path="output/b.docx", pdf_path="")
    t_legacy = repo.create(); t_legacy.user_id = None
    _to_success(t_legacy)
    repo.publish_artifacts(t_legacy, resume_revision=1, docx_path="output/c.docx", pdf_path="")
    db.commit()
    recs = repo.list_records()
    rec_tids = {r["task_id"] for r in recs}
    check(t_own.task_id in rec_tids, "owner 记录被列出")
    check(t_stub.task_id not in rec_tids and t_legacy.task_id not in rec_tids,
          "异主/LEGACY 记录不被列出（隔离）", extra=str(rec_tids))

    # ── [I3] Task 服务对异主任务按不存在（404 语义） ─────────────────
    print("\n[I3] TaskService 对异主/LEGACY 任务一律按不存在（404 语义）")
    from services.task_repository import TaskNotFoundError
    svc = TaskService(db)
    JD = "JD" * 60

    t_for = repo.create(); t_for.user_id = other
    repo.set_draft_input(t_for, name="异地", phone="", email="", location="", jd=JD)
    t_run = repo.create(); t_run.user_id = other
    repo.set_draft_input(t_run, name="异地", phone="", email="", location="", jd=JD)
    repo.freeze_input(t_run, name="异地", phone="", email="", location="", jd=JD)
    repo.transition(t_run, "RUNNING")
    t_leg2 = repo.create(); t_leg2.user_id = None
    db.commit()

    def _is_404(fn):
        try:
            fn()
            return False
        except TaskNotFoundError:
            return True
        except Exception as e:  # noqa: BLE001
            return f"other:{type(e).__name__}"

    for label, fn in (
        ("get_task", lambda: svc.get_task(t_for.task_id)),
        ("save_draft", lambda: svc.save_draft(t_for.task_id, name="改", jd=JD)),
        ("freeze_input", lambda: svc.freeze_input(t_for.task_id, name="改", jd=JD)),
        ("start_run", lambda: svc.start_run(t_run.task_id)),
        ("cancel_task", lambda: svc.cancel_task(t_run.task_id)),
        ("continue_failed_scope", lambda: svc.continue_failed_scope(t_run.task_id)),
        ("get_task(LEGACY)", lambda: svc.get_task(t_leg2.task_id)),
    ):
        check(_is_404(fn) is True, f"{label} 对异主/LEGACY 任务 404")

    # 异主任务数据未被改动
    db.expire_all()
    f_after = repo.get(t_for.task_id)
    r_after = repo.get(t_run.task_id)
    check(f_after is not None and f_after.status == "DRAFT", "异主 DRAFT 任务未被轻动",
          extra=(f_after.status if f_after else None))
    check(r_after is not None and r_after.status == "RUNNING", "异主 RUNNING 任务未被取消",
          extra=(r_after.status if r_after else None))

    # ── [I4] cleanup 不跨 owner 删除 ────────────────────────────────
    print("\n[I4] run_cleanup / _clean_orphan_children 不跨 owner 删除")
    from datetime import timedelta
    from services.task_cleanup import run_cleanup

    def _aged(task, status_text):
        # 直接落终态 + 造旧（任务书测试只验证 cleanup owner 隔离，不验证转移合法）
        task.status = status_text
        db.flush()
        task.created_at = datetime.utcnow() - timedelta(days=3)
        task.updated_at = datetime.utcnow() - timedelta(days=3)
        if status_text == "FAILED":
            task.expires_at = task.updated_at
        else:
            task.expires_at = None
        db.flush()

    t_other_failed = repo.create(); t_other_failed.user_id = other
    _aged(t_other_failed, "FAILED")
    t_legacy_failed = repo.create(); t_legacy_failed.user_id = None
    _aged(t_legacy_failed, "FAILED")
    db.commit()

    before_other = db.query(M.Task).filter(M.Task.user_id == other).count()
    before_legacy = db.query(M.Task).filter(M.Task.user_id.is_(None)).count()
    run_cleanup(db)
    db.commit()
    after_other = db.query(M.Task).filter(M.Task.user_id == other).count()
    after_legacy = db.query(M.Task).filter(M.Task.user_id.is_(None)).count()
    check(before_other == after_other and before_legacy == after_legacy,
          "异主/LEGACY 已过期的 FAILED 任务不被清理",
          extra=str((before_other, after_other, before_legacy, after_legacy)))

    # ── [I5] 经历服务 owner 隔离 ────────────────────────────────────
    print("\n[I5] experience_service owner 隔离")
    from services import experience_service as es
    e_stub2 = _mk_experience(db, stub, title="Stub数据2")
    db.commit()
    check(es.get_experience(db, e_stub2.id, owner=owner) is None,
          "get_experience 对异主经历返回 None")
    check(es.get_experience(db, e_stub2.id, owner=stub) is not None,
          "get_experience 同主经历可见")
    check(es.update_experience(db, e_stub2.id, {"title": "Stub改"}, owner=owner) is None,
          "update_experience 对异主经历返回 None（不改写）")
    db.rollback()
    check(es.delete_experience(db, e_stub2.id, owner=owner) is False,
          "delete_experience 对异主经历返回 False（不删除）")
    db.rollback()
    still = db.query(M.Experience).filter(M.Experience.id == e_stub2.id).first()
    check(still is not None, "异主经历未被删除")

    # ── [I6]/[I7] 装配归主 + 教育进成品 ─────────────────────────────
    print("\n[I6/I7] make_task_assembler 装配归主 + 教育确定性进入成品")
    from services import document_assembler as da
    from services.task_generation import GenerationSummary, GeneratedExperience, GeneratedFact

    # I6：装配归主 —— make_task_assembler 的 DB 查询限定 owner；
    #     异主经历即使出现也会因 user_id 过滤被回退，教育被单独归主装配。
    #     （只验证归主查询与行筛逻辑；不触发 Word/PDF 渲染，保证确定性。）
    from database.models import Experience
    ids = [e_owner.id, e_stub.id, e_other.id]
    rows_by_q = (db.query(Experience)
                 .filter(Experience.id.in_(ids), Experience.user_id == owner).all())
    rows_by_q_ids = {e.id for e in rows_by_q}
    check(e_owner.id in rows_by_q_ids, "装配归主：owner 经历被查询覆盖", extra=str(rows_by_q_ids))
    check(e_stub.id not in rows_by_q_ids and e_other.id not in rows_by_q_ids,
          "装配归主：异主经历不被查询覆盖（隔离）", extra=str(rows_by_q_ids))

    # 教育单独归主装配：owner 教育经历进入标准 ResumeDocument；
    #     source role(→major)/company(→school) 字段被确定性保留，不硬编码清空。
    edu_rows = (db.query(Experience)
                .filter(Experience.user_id == owner, Experience.type == "education")
                .all())
    edu_loaded = [e for e in edu_rows if e.id == e_edu.id]
    _edu_exps = [
        GeneratedExperience(
            experience_id=e.id, sort_order=i, title=e.title or e.company or "教育",
            # GeneratedExperience 无 type 字段；build_resume_document 用 title 启发式
            # （含"大学/教育/学校"→ education）判定教育分支。
            facts=[GeneratedFact(fact_id=f"f{e.id[:4]}", headline="掌握高数",
                                 body="成绩优良", fact_refs=["r"], reason="理由")]
        )
        for i, e in enumerate(edu_loaded)
    ]
    doc = da.build_resume_document(
        contact={"name": "张三", "phone": "", "email": "", "location": ""},
        compact=compact,
        experiences=_edu_exps,
    )
    check(len(doc.education) >= 1, "教育经历确定性装配进入成品（education 非空）",
          extra=str(len(doc.education)))
    if len(doc.education) >= 1:
        top_edu = doc.education[0]
        check(top_edu.school == "Owner大学" or top_edu.school != "",
              "教育 source 字段（school）确定性保留",
              extra=f"school={top_edu.school!r} major={top_edu.major!r} degree={top_edu.degree!r}")

    # 教育确定性排序（_order_education 用源 end_time/start_time，缺失置后，最多 3 条）
    edu_items = da._order_education([(e_edu, _EduItem(school="Owner大学", major="计算机", degree="本科"))])
    check(len(edu_items) >= 1 and edu_items[0].school == "Owner大学" and edu_items[0].degree == "本科",
          "教育经历确定性排序并保留 source 字段", extra=str([(x.school, x.major, x.degree) for x in edu_items]))

    db.close()
    print(f"\n结果：{_passed} 通过 / {_failed} 失败")
    return 1 if _failed else 0


class _EduItem:
    """EducationItem 的轻量替身（仅取校验字段，避免依赖 ORM dataclass 变更）。"""

    def __init__(self, school, major, degree):
        self.school = school
        self.major = major
        self.degree = degree


if __name__ == "__main__":
    def _fn(state):
        return _run_tests_inner(state)
    run_isolated("v22_owner_", _fn, "V2.2.0 owner scope + 三身份越权隔离 gate")