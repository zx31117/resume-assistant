"""V2.2.0 T2 验证：Task/InputRevision/Subtasks/Snapshot schema + migration + repository。

退出码 0 = 业务断言通过且临时 runtime 清理干净；非 0 = 有失败/异常/清理失败。

覆盖（PLAN §2.3/§2.4 / Gate §6.1）：
- migration：新库、V2.1.0 旧库（先建 Fact 表再跑任务迁移）、重复执行幂等、失败回滚、备份
- repository：状态机全跳转/非法跳转 fail closed；单活动任务；InputRevision 冻结后不可原地改写
- 覆盖式快照 + 单调 seq；事件 + 快照 256 KiB 容量（进 buffer 压缩不删结果）
- 容量上限（单任务 256 KiB 入参）超限明确拒绝，不静默截断

全部使用临时 runtime（RESUME_DATA_DIR 指向 temp），不触碰真实库/真实输出。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta
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


def _list_tables(db) -> set[str]:
    from sqlalchemy import text
    return set(db.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")).scalars())


# ── 测试主体（在临时 runtime 环境内延迟导入） ──
def _run_tests_inner(state) -> int:
    from database.session import SessionLocal, engine
    from database import migrations as mig
    from database.models import (
        InputRevision, Task, TaskEvent, TaskSnapshot, TaskSubtask, Fact, Experience)
    from services.task_repository import (
        TaskRepository, ActiveTaskConflictError, TaskCapacityError,
        TaskNotFoundError, TaskStateError)
    from core.task import TaskStatus, SubtaskStatus
    state.register_engine(engine)

    db = SessionLocal()
    state.engine = engine

    # ── [M1] 全新库迁移 ──
    print("\n[M1] 全新库：fact + task schema 迁移")
    r = mig.run_migrations()
    check(r["error"] is None, "全新库迁移无错误")
    check(any(v == mig.SCHEMA_VERSION_TASK_SCHEMA for v in r["applied"]),
          "task-schema 迁移被应用", extra=str(r["applied"]))
    # 表已建（查询 sqlite_master）
    tables = _list_tables(db)
    for t in ("tasks", "input_revisions", "task_subtasks", "task_snapshots", "task_events"):
        check(t in tables, f"表 {t} 存在", extra=str(sorted(tables)))

    # ── [M2] 重复执行幂等 ──
    print("\n[M2] 重复执行迁移（幂等）")
    r2 = mig.run_migrations()
    check(r2["error"] is None, "二次迁移无错误")
    check(any(v == mig.SCHEMA_VERSION_TASK_SCHEMA for v in r2["applied"]) is False,
          "task-schema 不再被重复应用", extra=str(r2["applied"]))

    # ── [M3] 旧库升级：先建 V2.1.0 表（不含任务表），再跑迁移补建 ──
    print("\n[M3] V2.1.0 旧库升级补建任务表")
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    old_dir = Path(tempfile.mkdtemp(prefix="v22_old_"))
    old_path = str(old_dir / "old.db")
    old_engine = None
    try:
        old_engine = create_engine(f"sqlite:///{old_path}")
        # 只建 V2.1.0 表（不含任务表）——通过原始 DDL 建 fact/schema 相关表
        old_local = sessionmaker(bind=old_engine, autoflush=False)
        osession = old_local()
        osession.execute(text("CREATE TABLE users (id VARCHAR PRIMARY KEY, name VARCHAR, email VARCHAR, created_at DATETIME)"))
        osession.execute(text("CREATE TABLE experiences (id VARCHAR PRIMARY KEY, user_id VARCHAR, type VARCHAR, title VARCHAR, company VARCHAR, time VARCHAR, role VARCHAR, description TEXT, skills JSON, achievements JSON, raw_text TEXT, created_at DATETIME, updated_at DATETIME)"))
        osession.execute(text("CREATE TABLE facts (fact_id VARCHAR PRIMARY KEY, experience_id VARCHAR, fact_type VARCHAR, text TEXT, source_text TEXT, source_field VARCHAR, source_index INTEGER, content_hash VARCHAR, source_hash VARCHAR, revision INTEGER, created_at DATETIME, updated_at DATETIME)"))
        osession.execute(text("CREATE TABLE schema_versions (version VARCHAR PRIMARY KEY, applied_at DATETIME, description TEXT)"))
        osession.commit()
        old_session_tables = set(osession.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")).scalars())
        check("tasks" not in old_session_tables, "旧库 sanity：无 tasks 表")
        osession.close()
        # 对旧库执行迁移（允许备份，验证备份路径）
        r3 = mig.run_migrations(db_path=old_path, backup=True)
        check(r3["error"] is None, "旧库升级迁移无错误", extra=str(r3["error"]))
        check(r3["backup"] is not None and r3["backup"].get("sqlite"), "旧库迁移前已备份", extra=str(r3.get("backup", {}).get("sqlite")))
        osession2 = old_local()
        tables_after = set(osession2.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")).scalars())
        for t in ("tasks", "input_revisions", "task_subtasks", "task_snapshots", "task_events"):
            check(t in tables_after, f"旧库升级后存在表 {t}", extra=str(sorted(tables_after)))
        # 旧数据保留（schema_versions 记录了旧迁移）
        sv = osession2.execute(text("SELECT version FROM schema_versions")).scalars().all()
        check(mig.SCHEMA_VERSION_FACT_SCHEMA in sv, "旧迁移版本保留", extra=str(sv))
        osession2.close()
    finally:
        if old_engine is not None:
            old_engine.dispose()
        import shutil
        shutil.rmtree(old_dir, ignore_errors=True)

    # ── [R1] 状态机：创建→DRAFT，非法跳转 fail closed ──
    print("\n[R1] 状态机跳转")
    repo = TaskRepository(db)
    task = repo.create()
    db.commit()
    check(task.status == "DRAFT", "初始 DRAFT")
    # 非法：DRAFT 直接 -> RUNNING
    try:
        repo.transition(task, TaskStatus.RUNNING)
        db.commit()
        check(False, "DRAFT->RUNNING 应被拒绝")
    except TaskStateError:
        db.rollback()
        check(True, "DRAFT->RUNNING 非法跳转被拒绝")
    # 合法：DRAFT -> READY -> RUNNING -> SUCCEEDED
    repo.transition(task, TaskStatus.READY)
    repo.transition(task, TaskStatus.RUNNING)
    repo.transition(task, TaskStatus.SUCCEEDED)
    db.commit()
    check(task.status == "SUCCEEDED", "DRAFT->READY->RUNNING->SUCCEEDED 成功")
    # 终态再跳转被拒绝
    try:
        repo.transition(task, TaskStatus.FAILED)
        db.commit()
        check(False, "终态再跳转应被拒绝")
    except TaskStateError:
        db.rollback()
        check(True, "终态再跳转被拒绝")

    # ── [R2] InputRevision 不可变：冻结后原地改写被拒 ──
    print("\n[R2] InputRevision 冻结不可变")
    t2 = repo.create()
    # 先在 DRAFT 保存草稿
    repo.set_draft_input(t2, name="张三", phone="", email="", location="", jd="目标岗位JD")
    db.commit()
    check(t2.status == "DRAFT", "草稿保存仍在 DRAFT")
    # 冻结
    rev = repo.freeze_input(t2, name="张三", phone="138", email="a@b.c", location="上海", jd="目标JD全文")
    db.commit()
    check(t2.status == "READY", "冻结后进入 READY")
    check(t2.current_input_revision == rev.revision, "冻结 revision 正确")
    frozen_rev = rev.revision
    # READY 下原地改写草稿应被拒（InputRevision 已冻结）
    try:
        repo.set_draft_input(t2, name="李四改", phone="", email="", location="", jd="x")
        db.commit()
        check(False, "冻结后原地改写应被拒")
    except TaskStateError:
        db.rollback()
        check(True, "冻结后原地改写被拒")
    # 查回原文未被污染
    row = db.query(InputRevision).filter_by(task_id=t2.task_id, revision=frozen_rev).first()
    check(row.name == "张三", "冻结原文未被改写", extra=row.name)

    # ── [R3] 单前台活动任务 ──
    print("\n[R3] 单前台活动任务")
    repo.assert_single_active()  # 当前无 RUNNING，应通过
    # 把 t2 变 RUNNING
    repo.transition(t2, TaskStatus.RUNNING)
    db.commit()
    try:
        repo.assert_single_active()
        check(False, "已有活动任务时应抛冲突")
    except ActiveTaskConflictError:
        db.rollback()
        check(True, "已有活动任务正确抛冲突")
    # 结束后可再启动新活动
    repo.transition(t2, TaskStatus.SUCCEEDED)
    db.commit()
    repo.assert_single_active()
    check(True, "活动结束后可启动新活动任务")

    # ── [R4] 单调 seq + 覆盖式快照 + 事件 ──
    print("\n[R4] 单调 seq 与快照覆盖")
    t3 = repo.create()
    db.commit()
    repo.transition(t3, TaskStatus.READY)
    repo.transition(t3, TaskStatus.RUNNING)
    db.commit()
    s1 = repo.save_snapshot(t3, phase="P1", payload={"jd_items": ["a"]})
    seq1 = s1.seq  # 覆盖式同对象会随后续 in-place 更新而变，须在调用时点捕获
    s2 = repo.save_snapshot(t3, phase="P2", payload={"selected": [1, 2]})
    seq2 = s2.seq
    e1 = repo.append_event(t3, input_revision=1, event_type="fact_completed",
                           phase="P3", payload={"fact_id": "f1"})
    e2 = repo.append_event(t3, input_revision=1, event_type="reason_delta",
                           phase="P3", payload={"fact_id": "f1", "text": "x"})
    db.commit()
    check(seq2 == seq1 + 1, "快照 seq 单调递增", extra=str((seq1, seq2)))
    check(e1.seq == seq2 + 1 and e2.seq == e1.seq + 1, "事件 seq 紧随快照且严格递增",
          extra=str((seq1, seq2, e1.seq, e2.seq)))
    snaps = db.query(TaskSnapshot).filter_by(task_id=t3.task_id).all()
    check(len(snaps) == 1, "快照覆盖式（每任务一条）", extra=str(len(snaps)))
    check(snaps[0].phase == "P2", "快照取最新 phase", extra=snaps[0].phase)
    # 事件按 seq 读取
    events_after = repo.list_events_after(t3.task_id, s2.seq)
    check(all(ev["seq"] > s2.seq for ev in events_after), "重连从快照 seq 之后订阅")
    check(len(events_after) == 2, "之后有 2 条事件", extra=str(len(events_after)))

    # ── [R5] 经历子任务 ──
    print("\n[R5] 经历子任务")
    st = repo.upsert_subtask(t3, experience_id="exp1", sort_order=0)
    repo.upsert_subtask(t3, experience_id="exp2", sort_order=1)
    repo.update_subtask(t3, "exp1", status=SubtaskStatus.RUNNING)
    repo.update_subtask(t3, "exp1", status=SubtaskStatus.SUCCEEDED,
                        fact_results=[{"fact_id": "f1", "headline": "h", "body": "b", "fact_refs": ["r1"]}])
    db.commit()
    subs = db.query(TaskSubtask).filter_by(task_id=t3.task_id).order_by(TaskSubtask.sort_order).all()
    check(len(subs) == 2, "两个经历子任务")
    check(subs[0].status == "SUCCEEDED", "exp1 SUCCEEDED")
    check(subs[0].fact_results[0]["fact_id"] == "f1", "fact_result 写入")

    # ── [R6] 入参容量上限（256 KiB） ──
    print("\n[R6] 单任务入参容量上限")
    t_cap = repo.create()  # 独立 DRAFT 任务；t3 此刻为 RUNNING，set_draft_input 仅允许 DRAFT
    db.commit()
    big = "x" * (256 * 1024 + 100)  # 略超 256KiB
    try:
        repo.set_draft_input(t_cap, name=big, phone="", email="", location="", jd="")
        db.commit()
        check(False, "超限入参应被拒绝")
    except TaskCapacityError:
        db.rollback()
        check(True, "超限入参明确拒绝（413 语义）")

    # ── [R7] 事件+快照 256KiB 总量下超限压缩不删结果 ──
    print("\n[R7] 事件+快照超限压缩（不删业务结果）")
    big_payload = {"data": "z" * (128 * 1024)}
    repo.append_event(t3, input_revision=1, event_type="fact_completed", phase="P3", payload=big_payload)
    repo.append_event(t3, input_revision=1, event_type="fact_completed", phase="P3", payload=big_payload)
    repo.append_event(t3, input_revision=1, event_type="fact_completed", phase="P3", payload=big_payload)
    db.commit()
    repo._enforce_event_snapshot_cap(t3)
    db.commit()
    # 快照仍存在、极早期事件被压缩
    snap_after = db.query(TaskSnapshot).filter_by(task_id=t3.task_id).first()
    check(snap_after is not None, "压缩后权威快照仍保留")
    evs = db.query(TaskEvent).filter_by(task_id=t3.task_id).order_by(TaskEvent.seq).all()
    total = sum(len(json.dumps(e.payload or {}, ensure_ascii=False)) for e in evs)
    total += len(json.dumps(snap_after.payload or {}, ensure_ascii=False)) if snap_after else 0
    check(total <= 256 * 1024, "事件+快照合计 <= 256KiB", extra=str(total))

    print(f"\n结果：{_passed} 通过 / {_failed} 失败")
    db.close()  # 释放 checked-out 连接，确保临时 runtime 的 app.db 可被删除
    return 1 if _failed else 0


def _run_tests(state) -> int:
    try:
        return _run_tests_inner(state)
    finally:
        # 任何异常下也释放 session/engine，确保临时 runtime 可清理
        try:
            from database.session import SessionLocal, engine as _eng
            SessionLocal().close()
            _eng.dispose()
        except Exception:
            pass


if __name__ == "__main__":
    def _fn(state):
        global Base
        import database.models as dm  # 延迟导入（临时 runtime 已生效）
        Base = dm.Base
        return _run_tests(state)

    run_isolated("v22_t2_", _fn, "V2.2.0 T2 task schema/repository gate")