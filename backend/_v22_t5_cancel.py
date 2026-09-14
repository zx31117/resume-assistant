"""V2.2.0 T5 验证：实际取消、Provider/worker 清理与 revision fence（PLAN §4 / Gate 6.1）。

退出码 0 = 业务断言通过且临时 runtime 清理干净；非 0 = 有失败/异常/清理失败。

完成证据（乱序/缺口/缓冲过期/重连不增调用之外，T5 专属）：
- [C1] 纯机制：CancellationToken 置位幂等 + raise_if_cancelled；RevisionFence revoke 后拒写；
- [C2] 纯机制：TaskRunRegistry 登记/取消/清理回调执行/活动槽释放（无泄漏）；
- [C3] 纯机制：run 被替换后旧 ctx 的 fence 拒绝（旧 revision 迟到结果被拒）；
- [C4] 并发 worker：线程内轮询 ctx.raise_if_cancelled 在取消后抛 TaskCancelledError；
- [C5] API：RUNNING→CANCELLED；取消后活动槽释放，新任务立即可 start；
- [C6] API：取消后迟到写入（save_snapshot/append_event/publish_artifacts）被拒；
- [C7] API：DRAFT/READY/SUCCEEDED 非法取消 fail closed（409）；
- [C8] 收尾：取消后未结束子任务置 CANCELLED。
"""
from __future__ import annotations

import sys
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


def _run_tests_inner(state) -> int:
    import threading
    from fastapi.testclient import TestClient
    from main import app
    from database.session import SessionLocal, engine
    from core import security
    from core.task import TaskStatus, SubtaskStatus
    from core.task_cancel import (
        RevisionFenceError,
        TaskCancelledError,
        TaskRunRegistry,
        registry,
    )
    from services.task_repository import TaskRepository, TaskStateError
    from services.task_service import TaskService

    state.register_engine(engine)
    cookies = {security.SESSION_COOKIE_NAME: security.SESSION_TOKEN}
    auth_headers = {"Host": "127.0.0.1:8000"}
    REQ = {"headers": auth_headers, "cookies": cookies}

    from database import migrations as mig
    mig.run_migrations()
    registry.reset()
    baseline = registry.active_count()

    # ── [C1] 纯机制：CancellationToken / RevisionFence ──
    print("\n[C1] CancellationToken + RevisionFence 机制")
    from core.task_cancel import CancellationToken, RevisionFence
    token = CancellationToken()
    check(token.is_cancelled() is False, "默认未取消")
    check(token.request_cancel() is True, "首次置位返回 True")
    check(token.request_cancel() is False, "重复置位幂等返回 False")
    check(token.is_cancelled() is True, "已取消")
    try:
        token.raise_if_cancelled()
        check(False, "取消后 raise_if_cancelled 应抛 TaskCancelledError")
    except TaskCancelledError:
        check(True, "取消后 raise_if_cancelled 抛 TaskCancelledError")

    fence = RevisionFence("t1", 1)
    check(fence.is_active() is True, "fence 默认活动")
    fence.assert_writable()
    check(True, "活动 fence 允许写")
    fence.revoke()
    check(fence.is_active() is False, "revoke 后失活")
    try:
        fence.assert_writable()
        check(False, "revoke 后写应抛 RevisionFenceError")
    except RevisionFenceError:
        check(True, "revoke 后写抛 RevisionFenceError")

    # ── [C2] 纯机制：TaskRunRegistry 取消 + 清理 + 活动槽释放 ──
    print("\n[C2] TaskRunRegistry 取消/清理/无泄漏")
    clean_called = {"n": 0}
    ctx = registry.start("task-a", 3)
    ctx.add_cleanup(lambda: clean_called.__setitem__("n", clean_called["n"] + 1))
    ctx.add_cleanup(lambda: clean_called.__setitem__("n", clean_called["n"] + 1))
    check(registry.active_count() == baseline + 1, "登记 1 个运行")
    check(registry.get("task-a") is ctx, "可按 task_id 取回 run")
    ctx2 = registry.start("task-b", 1)
    check(registry.active_count() == baseline + 2, "登记第 2 个运行")
    cancelled = registry.request_cancel("task-a")
    check(cancelled is True, "request_cancel 返回确有登记")
    check(ctx.token.is_cancelled() is True, "取消后 token 置位")
    check(ctx.fence.is_active() is False, "取消后 fence 撤销")
    check(clean_called["n"] == 2, "所有登记清理回调均已执行", extra=str(clean_called))
    check(registry.active_count() == baseline + 1, "task-a 活动槽已释放")
    check("task-a" not in registry.running_task_ids(), "task-a 已从登记移除")
    # 幂等/其余运行继续取消
    cancelled_idem = registry.request_cancel("task-b")
    check(cancelled_idem is True, "task-b 也被取消")
    check(ctx2.token.is_cancelled() is True, "task-b 的 token 置位")
    check(registry.active_count() == baseline, "全部取消后回到基线")
    registry.reset()
    check(registry.active_count() == baseline, "registry 复位到基线")

    # ── [C3] 纯机制：run 被替换后旧 ctx fence 拒绝 ──
    print("\n[C3] run 被替换 => 旧 revision fence 拒写")
    old = registry.start("task-r", 1)
    registry.start("task-r", 2)  # 新 revision 接管同一 task
    check(old.fence.is_active() is False, "旧 run 的 fence 被撤销")
    try:
        old.assert_writable()
        check(False, "旧 run 写应被 RevisionFenceError 拒收")
    except RevisionFenceError:
        check(True, "旧 run 写被 RevisionFenceError 拒收")
    registry.reset()

    # ── [C4] 并发 worker：轮询 raise_if_cancelled，取消后协作式停止 ──
    print("\n[C4] 并发 worker 协作式取消")
    go = threading.Event()
    wctx = registry.start("task-w", 1)
    results = []

    def _worker():
        go.wait()  # 等主线程先发出取消，再进入首安全点
        try:
            wctx.raise_if_cancelled()
            results.append("finished")
        except TaskCancelledError:
            results.append("cancelled")

    t = threading.Thread(target=_worker)
    t.start()
    registry.request_cancel("task-w")
    go.set()
    t.join(timeout=3)
    check(results and results[-1] == "cancelled", "worker 在协作点感知取消并停止", extra=str(results))
    registry.reset()

    # ── API 段：迁移与 TestClient ──
    client = TestClient(app)
    state.register_client(client)
    svc_db = SessionLocal()
    svc = TaskService(svc_db)

    def _make_running(task_id=None):
        t = svc.create_task() if task_id is None else {"task_id": task_id}
        tid = t["task_id"]
        svc.save_draft(tid, name="甲", phone="138", email="a@b.c", location="上海", jd="JD")
        svc.freeze_input(tid, name="甲", phone="138", email="a@b.c", location="上海", jd="JD")
        svc.start_task(tid)
        return tid

    # ── [C5] API：RUNNING→CANCELLED，且释放活动槽后新任务立即可 start ──
    print("\n[C5] API 取消 + 释放活动槽")
    tid1 = _make_running()
    a1 = svc.get_task(tid1)
    check(a1["status"] == "RUNNING", "task1 已 RUNNING")
    r = client.post(f"/api/task/{tid1}/cancel", **REQ)
    check(r.status_code == 200, "cancel 200", extra=str(r.status_code) + " " + r.text[:200])
    cancelled_view = r.json()
    check(cancelled_view["status"] == "CANCELLED", "取消后终态 CANCELLED",
          extra=cancelled_view.get("status"))
    check(cancelled_view.get("terminal_error") == "TASK_CANCELLED", "terminal_error 置 TASK_CANCELLED")
    # 活动槽释放：新任务立即可 start
    tid2 = _make_running()
    a2 = svc.get_task(tid2)
    check(a2["status"] == "RUNNING", "取消后新任务立即可用", extra=a2.get("status"))
    svc.cancel_task(tid2)  # 释放 tid2 活动槽，供后续用例继续 start 新任务

    # ── [C6] 取消后迟到写入被拒 ──
    print("\n[C6] 取消后迟到结果拒收")
    db = SessionLocal()
    db2 = SessionLocal()
    repo = TaskRepository(db)
    task = repo.get(tid1)
    try:
        repo.save_snapshot(task, phase="P3", payload={"fact_id": "f1"})
        check(False, "取消后 save_snapshot 应被拒")
    except TaskStateError:
        check(True, "取消后 save_snapshot 被 TaskStateError 拒收")
    try:
        repo.append_event(task, input_revision=1, event_type="fact_completed", phase="P3",
                          payload={"fact_id": "f1"})
        check(False, "取消后 append_event 应被拒")
    except TaskStateError:
        check(True, "取消后 append_event 被 TaskStateError 拒收")
    try:
        repo.publish_artifacts(task, resume_revision=1, docx_path="a.docx", pdf_path="a.pdf")
        check(False, "取消后 publish_artifacts 应被拒")
    except TaskStateError:
        check(True, "取消后 publish_artifacts 被 TaskStateError 拒收（不得发布）")

    # ── [C7] 非法取消 fail closed（DRAFT/READY/SUCCEEDED）──
    print("\n[C7] 非法取消 fail closed")
    td = svc.create_task()["task_id"]
    r = client.post(f"/api/task/{td}/cancel", **REQ)
    check(r.status_code == 409, "DRAFT 取消 → 409", extra=str(r.status_code))
    svc.save_draft(td, name="乙")
    svc.freeze_input(td, name="乙")
    r = client.post(f"/api/task/{td}/cancel", **REQ)
    check(r.status_code == 409, "READY 取消 → 409", extra=str(r.status_code))
    # SUCCEEDED 任务取消
    ts = _make_running()
    sdb = SessionLocal()
    srepo = TaskRepository(sdb)
    stask = srepo.get(ts)
    srepo.transition(stask, TaskStatus.SUCCEEDED)
    sdb.commit()
    r = client.post(f"/api/task/{ts}/cancel", **REQ)
    check(r.status_code == 409, "SUCCEEDED 取消 → 409", extra=str(r.status_code))

    # ── [C8] 取消后未结束子任务置 CANCELLED ──
    print("\n[C8] 子任务收尾")
    tc = _make_running()
    cdb = SessionLocal()
    crepo = TaskRepository(cdb)
    ctask = crepo.get(tc)
    crepo.upsert_subtask(ctask, "exp-1", 0)
    crepo.update_subtask(ctask, "exp-1", status=SubtaskStatus.RUNNING)
    crepo.upsert_subtask(ctask, "exp-2", 1)  # 保持 PENDING
    cdb.commit()
    svc.cancel_task(tc)
    v = svc.get_task(tc)
    subs = {s["experience_id"]: s["status"] for s in v["subtasks"]}
    check(subs.get("exp-1") == "CANCELLED", "RUNNING 子任务 → CANCELLED", extra=str(subs))
    check(subs.get("exp-2") == "CANCELLED", "PENDING 子任务 → CANCELLED", extra=str(subs))

    # 收尾：登记清理
    registry.reset()
    check(registry.active_count() == baseline, "收尾 registry 回到基线（无泄漏）")

    for df in (svc_db, db, db2, sdb, cdb):
        df.close()
    print(f"\n结果：{_passed} 通过 / {_failed} 失败")
    return 1 if _failed else 0


if __name__ == "__main__":
    def _fn(state):
        return _run_tests_inner(state)

    run_isolated("v22_t5_", _fn, "V2.2.0 T5 cancel/revision-fence gate")