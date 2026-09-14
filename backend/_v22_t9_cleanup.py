"""V2.2.0 T9 验证：容量/保留/cleanup 与并发故障恢复（PLAN §2.4 / Gate §6.4 / V220-R1-T09）。

证据项：20条、16MiB、保护对象、失败/幂等/越界。

覆盖：
- [T1] 保留期：FAILED/CANCELLED 已过 24h 可清理；未过保留期保留；SUCCEEDED 永不清理；
- [T2] 保护对象：DRAFT/READY/RUNNING/CANCELLING/SUCCEEDED 即使超限也不误删；
- [T3] 20 条上限：可清理终态超过 20 时最旧优先清理，恰好/超出边界（越界）；
- [T4] 16 MiB 上限：临时状态总量超限最旧优先清理至达标；
- [T5] 孤立子记录：指向不存在 Task 的 InputRevision/Subtask/Snapshot/Event 被清理；
- [T6] 幂等：cleanup 重复执行不产生额外删除；
- [T7] 失败可见：对非法 session 直接抛出（不静默成功）。

退出码 0 = 全部通过；非 0 = 有失败/异常/清理失败。
"""
from __future__ import annotations

import sys
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


def _utcnow() -> datetime:
    return datetime.utcnow()


def _draft(repo, label, jd="JD"):
    t = repo.create()
    repo.set_draft_input(t, name=label, phone="", email="", location="", jd=jd)
    return t


def _make_terminal(db, repo, status, *, expired=True, payload_bytes=0):
    """建一个已冻结并到终态的任务；`expired=True` 令其已过 24h 保留期。"""
    from core.task import TaskStatus
    t = repo.create()
    repo.set_draft_input(t, name="王", phone="", email="", location="", jd="JD")
    repo.freeze_input(t, name="王", phone="", email="", location="", jd="JD")
    repo.transition(t, TaskStatus.RUNNING)
    if payload_bytes > 0:
        # RUNNING 仍可写时先灌大快照，再落终态（终态拒写快照）
        repo.save_snapshot(t, phase="P3", payload={"blob": "x" * payload_bytes})
    repo.transition(t, TaskStatus(status))
    db.flush()
    if expired:
        aged = _utcnow() - timedelta(days=2, minutes=5)
        t.updated_at = aged
        t.created_at = aged
        if status == "FAILED":
            t.expires_at = aged          # 已过
        elif status == "CANCELLED":
            t.expires_at = None          # 依 updated_at + 24h → 已过
        else:                            # SUCCEEDED 保护对象
            t.expires_at = None
    else:
        t.updated_at = _utcnow()
        t.created_at = _utcnow()
        t.expires_at = _utcnow() + timedelta(hours=24)  # 未过
    db.flush()
    db.commit()
    return t


def _count(db, model) -> int:
    return db.query(model).count()


def _count_status(db, st) -> int:
    from database.models import Task
    return db.query(Task).filter(Task.status == st).count()


def _run_tests_inner(state) -> int:
    from datetime import datetime as _dt
    from database.session import SessionLocal, engine
    from database import migrations as mig
    from database.models import (
        InputRevision, Task, TaskEvent, TaskSnapshot, TaskSubtask)
    from services.task_repository import TaskRepository
    from services.task_cleanup import run_cleanup
    from core.task import TaskStatus
    state.register_engine(engine)
    db = SessionLocal()

    _ = mig.run_migrations()
    now = _utcnow()

    print("\n[T1] 保留期：过 24h 可清理，未过保留，SUCCEEDED 永不清理")
    for t in db.query(Task).all():
        db.delete(t)
    db.commit()
    repo = TaskRepository(db)
    _make_terminal(db, repo, "FAILED", expired=True)
    _make_terminal(db, repo, "CANCELLED", expired=True)
    _make_terminal(db, repo, "FAILED", expired=False)   # 刚终态 → 保留
    _make_terminal(db, repo, "SUCCEEDED", expired=True)  # 保护 → 永不清理
    s = run_cleanup(db)
    db.commit()
    check(_count_status(db, "FAILED") == 1,
          "FAILED 仅保留未过保留期 1 条；过保留期 1 条已清理",
          f"实际={_count_status(db,'FAILED')}")
    check(_count_status(db, "CANCELLED") == 0, "CANCELLED 已过 24h 被清理")
    check(_count_status(db, "SUCCEEDED") == 1, "SUCCEEDED 永不清理（保护对象）")
    check(s["deleted_tasks"] == 2, "本步删除 2 个过保留期终态", f"deleted={s['deleted_tasks']}")

    print("\n[T2] 保护对象：DRAFT/READY/RUNNING/CANCELLING/SUCCEEDED 超限也不误删")
    for t in db.query(Task).all():
        db.delete(t)
    db.commit()
    repo.create()                                        # DRAFT
    _draft(repo, "DRAFT-1")                              # DRAFT
    rd = repo.create(); _draft(repo, "READY")
    repo.freeze_input(rd, name="王", phone="", email="", location="", jd="J")  # READY
    run = repo.create(); _draft(repo, "RUNNING")
    repo.freeze_input(run, name="王", phone="", email="", location="", jd="J")
    repo.transition(run, TaskStatus.RUNNING)             # RUNNING
    canc = repo.create(); _draft(repo, "CANCELLING")
    repo.freeze_input(canc, name="王", phone="", email="", location="", jd="J")
    repo.transition(canc, TaskStatus.RUNNING)
    repo.transition(canc, TaskStatus.CANCELLING)          # CANCELLING(活动)
    _make_terminal(db, repo, "SUCCEEDED", expired=True)   # 保护
    db.commit()
    for _ in range(30):
        _make_terminal(db, repo, "FAILED", expired=True, payload_bytes=700 * 1024)
    s = run_cleanup(db)
    db.commit()
    for lbl, got in (("DRAFT", _count_status(db, "DRAFT")),
                     ("READY", _count_status(db, "READY")),
                     ("RUNNING", _count_status(db, "RUNNING")),
                     ("CANCELLING", _count_status(db, "CANCELLING")),
                     ("SUCCEEDED", _count_status(db, "SUCCEEDED"))):
        check(got >= 1, f"保护对象 {lbl} 未被误删（{got} 条保留）")
    check(_count_status(db, "FAILED") <= 20,
          f"可清理 FAILED 被压到上限内（实际 {_count_status(db,'FAILED')}）")

    print("\n[T3] 20 条上限：恰好 20 不删，越界 21 删 1（越界）")
    for t in db.query(Task).all():
        db.delete(t)
    db.commit()
    for _ in range(20):
        _make_terminal(db, repo, "FAILED", expired=False)  # 未过保留期，新近终态
    rows = db.query(Task).filter(Task.status == "FAILED").all()
    print("  DEBUG T3: n=%d" % len(rows))
    for r in rows[:3]:
        print("    status=%s updated_at=%s expires_at=%s" % (r.status, r.updated_at, r.expires_at))
    s = run_cleanup(db)
    db.commit()
    check(s["deleted_tasks"] == 0, "恰好 20 条不触发清理", f"deleted={s['deleted_tasks']}")
    _make_terminal(db, repo, "FAILED", expired=False)  # 21 → 越界
    s = run_cleanup(db)
    db.commit()
    check(s["deleted_tasks"] == 1, "21 条越界 → 最旧优先删 1 条",
          f"deleted={s['deleted_tasks']}")
    check(_count_status(db, "FAILED") == 20, "清理后 FAILED 回到 20 条")

    print("\n[T4] 16 MiB 上限：超限最旧优先清理至达标")
    for t in db.query(Task).all():
        db.delete(t)
    db.commit()
    for _ in range(3):
        _make_terminal(db, repo, "FAILED", expired=False, payload_bytes=7 * 1024 * 1024)
    s = run_cleanup(db)
    db.commit()
    check(s["temporary_bytes_after"] <= 16 * 1024 * 1024,
          f"清理后临时状态 ≤ 16MiB（实际 {s['temporary_bytes_after']/1024/1024:.1f} MiB）")
    check(s["deleted_tasks"] >= 1, "超额快照被清理", f"deleted={s['deleted_tasks']}")

    print("\n[T5] 孤立子记录：无父 Task 的子记录被清理")
    for t in db.query(Task).all():
        db.delete(t)
    db.commit()
    orphan = Task(task_id=_uid(), status="DRAFT", current_input_revision=0,
                  seq=0, created_at=now, updated_at=now)
    db.add(orphan)
    db.flush()
    db.add(InputRevision(task_id=orphan.task_id, revision=0, jd="j", input_hash="h",
                         created_at=now))
    db.add(TaskSubtask(task_id=orphan.task_id, experience_id="x", sort_order=0,
                       status="PENDING", fact_results=[], updated_at=now))
    db.add(TaskSnapshot(task_id=orphan.task_id, seq=1, phase="P3", payload={},
                        updated_at=now))
    db.add(TaskEvent(task_id=orphan.task_id, seq=2, input_revision=0, event_type="e",
                     phase="P3", payload={}, created_at=now))
    db.flush()
    db.delete(orphan)  # 删父 Task，留下子记录成孤儿
    db.commit()
    before = (_count(db, InputRevision) + _count(db, TaskSubtask)
              + _count(db, TaskSnapshot) + _count(db, TaskEvent))
    s = run_cleanup(db)
    db.commit()
    after = (_count(db, InputRevision) + _count(db, TaskSubtask)
             + _count(db, TaskSnapshot) + _count(db, TaskEvent))
    check(before >= 4 and after == 0, f"孤立子记录全部清理（before={before} after={after}）")
    check(s["deleted_children"] >= 4, f"delete_children 计数一致（{s['deleted_children']}）")

    print("\n[T6] 幂等：重复 cleanup 不产生额外删除")
    for t in db.query(Task).all():
        db.delete(t)
    db.commit()
    for _ in range(25):
        _make_terminal(db, repo, "FAILED")
    run_cleanup(db); db.commit()
    s2 = run_cleanup(db); db.commit()
    check(s2["deleted_tasks"] == 0 and s2["deleted_children"] == 0,
          "第二次 cleanup 零删除（幂等）", f"{s2}")

    print("\n[T7] 失败可见：对非法 session 直接抛出（不静默成功）")
    threw = False
    try:
        run_cleanup(object())  # type: ignore
    except Exception:
        threw = True
    check(threw, "run_cleanup 对非法 session 抛出（失败可见，不静默）")

    db.close()
    print(f"\n结果：{_passed} 通过 / {_failed} 失败")
    return 1 if _failed else 0


if __name__ == "__main__":
    def _fn(state):
        return _run_tests_inner(state)
    run_isolated("v22_t9_", _fn, "V2.2.0 T9 capacity/retention/cleanup gate")