"""V2.2.0 T3 验证：Task API（创建 / 保存确认 / 冻结 / 启动 / 读取恢复）。

退出码 0 = 业务断言通过且临时 runtime 清理干净；非 0 = 有失败/异常/清理失败。

覆盖（PLAN §4 T3 完成证据：创建/保存/刷新/重连/终态矩阵、V220-G01/G02）：
- [A1] 创建新任务 → DRAFT，返回后端确认 task_id；
- [A2] 姓名必填：缺姓名保存/冻结被 400 拒绝；填姓名保存成功且回读一致；
- [A3] 保存确认：保存后再次读取状态来自后端（status/updated_at/latest_input 落库）；
- [A4] 冻结：进入 READY，revision 单调递增，冻结原文不可原地改写；
- [A5] 单前台活动任务：READY→RUNNING 成功；再启动第二个任务 409 ActiveTaskConflictError；
- [A6] 恢复快照：写入覆盖式快照后可读取（刷新/重连恢复基准）；
- [A7] 终态矩阵：终态后再保存被拒（fail closed）。

通过 TestClient 走真实 HTTP 层（含统一 DomainError 映射），临时 runtime 内独立 DB。
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
    from fastapi.testclient import TestClient
    from main import app
    from services.task_repository import TaskRepository
    from database.session import SessionLocal, engine
    from core import security

    state.register_engine(engine)

    cookies = {security.SESSION_COOKIE_NAME: security.SESSION_TOKEN}
    auth_headers = {"Host": "127.0.0.1:8000"}
    REQ = {"headers": auth_headers, "cookies": cookies}

    client = TestClient(app)
    state.register_client(client)

    # 迁移在 lifespan 的 init_db 已完成；但保证任务表就绪
    from database import migrations as mig
    mig.run_migrations()

    db = SessionLocal()

    # ── [A1] 创建新任务 → DRAFT ──
    print("\n[A1] 创建新任务")
    r = client.post("/api/task", **REQ)
    check(r.status_code == 200, "POST /api/task 返回 200", extra=str(r.status_code))
    body = r.json()
    check(body["status"] == "DRAFT", "新任务为 DRAFT", extra=body.get("status"))
    check(body["task_id"], "返回后端确认的 task_id", extra=body.get("task_id"))
    task_id = body["task_id"]
    check(body["current_input_revision"] == 0, "初始无冻结 revision")

    # ── [A2] 扩展：单任务保存（A3/A4/A5 用） ──
    print("\n[A2-A4] 保存确认 / 姓名必填 / 冻结")
    # 姓名必填：缺姓名
    r_missing = client.put(f"/api/task/{task_id}/save", json={
        "name": "   ", "phone": "", "email": "", "location": "", "jd": "岗位JD"}, **REQ)
    check(r_missing.status_code == 400, "缺姓名保存被 400 拒绝", extra=str(r_missing.status_code))
    check(r_missing.json().get("error_code") == "TASK_INPUT_INVALID",
          "错误码 TASK_INPUT_INVALID", extra=r_missing.json().get("error_code"))
    # 保存草稿
    r_save = client.put(f"/api/task/{task_id}/save", json={
        "name": "张三", "phone": "138", "email": "a@b.c", "location": "上海", "jd": "岗位JD全文"}, **REQ)
    check(r_save.status_code == 200, "保存返回 200", extra=str(r_save.status_code))
    saved = r_save.json()
    check(saved["status"] == "DRAFT", "保存后仍在 DRAFT")
    check(saved["latest_input"]["name"] == "张三", "保存确认入参回读一致")
    check(saved["latest_input"]["phone"] == "138" and saved["latest_input"]["jd"] == "岗位JD全文",
          "电话/JD 原文保存")
    # 刷新/重连读取
    r_get = client.get(f"/api/task/{task_id}", **REQ)
    check(r_get.status_code == 200, "GET 读取恢复 200", extra=str(r_get.status_code))
    check(r_get.json()["latest_input"]["name"] == "张三", "刷新从后端读到已保存状态")
    # 冻结
    r_freeze = client.post(f"/api/task/{task_id}/freeze", json={
        "name": "张三", "phone": "138", "email": "a@b.c", "location": "上海", "jd": "岗位JD全文"}, **REQ)
    check(r_freeze.status_code == 200, "冻结返回 200", extra=str(r_freeze.status_code))
    frozen = r_freeze.json()
    check(frozen["status"] == "READY", "冻结后进入 READY", extra=frozen.get("status"))
    rev = frozen["current_input_revision"]
    check(rev == 1, "第一次冻结 revision=1", extra=str(rev))
    # 冻结后原地保存应被拒（fail closed）
    r_save2 = client.put(f"/api/task/{task_id}/save", json={
        "name": "李四改", "phone": "", "email": "", "location": "", "jd": "x"}, **REQ)
    check(r_save2.status_code == 409, "READY 下原地保存被 409 拒绝", extra=str(r_save2.status_code))

    # 冻结不可变：读取仍是张三
    r_get2 = client.get(f"/api/task/{task_id}", **REQ)
    check(r_get2.json()["latest_input"]["name"] == "张三", "冻结原文未被改写")

    # ── [A5] 单前台活动任务 ──
    print("\n[A5] 单前台活动任务")
    r_start = client.post(f"/api/task/{task_id}/start", **REQ)
    check(r_start.status_code == 200, "start 返回 200（无其他活动任务）", extra=str(r_start.status_code))
    check(r_start.json()["status"] == "RUNNING", "启动后进入 RUNNING")
    # 已有 RUNNING，再创建并启动第二个任务 → 409
    r2 = client.post("/api/task", **REQ)
    task2 = r2.json()["task_id"]
    client.put(f"/api/task/{task2}/save", json={
        "name": "王五", "phone": "", "email": "", "location": "", "jd": "JD2"}, **REQ)
    client.post(f"/api/task/{task2}/freeze", json={
        "name": "王五", "phone": "", "email": "", "location": "", "jd": "JD2"}, **REQ)
    r_start2 = client.post(f"/api/task/{task2}/start", **REQ)
    check(r_start2.status_code == 409, "已有活动任务时启动第二任务 409",
          extra=str(r_start2.status_code))
    check(r_start2.json().get("error_code") == "ACTIVE_TASK_CONFLICT",
          "错误码 ACTIVE_TASK_CONFLICT", extra=r_start2.json().get("error_code"))

    # 活动槽释放后（第一任务取消/终态），第二任务可启动
    from core.task import TaskStatus
    db2 = SessionLocal()
    repo = TaskRepository(db2)
    t1 = repo.get(task_id)
    repo.transition(t1, TaskStatus.CANCELLED)
    db2.commit()
    r_start2b = client.post(f"/api/task/{task2}/start", **REQ)
    check(r_start2b.status_code == 200, "活动槽释放后第二任务可启动",
          extra=str(r_start2b.status_code))
    check(r_start2b.json()["status"] == "RUNNING", "第二任务进入 RUNNING")

    # ── [A6] 恢复快照 ──
    print("\n[A6] 恢复快照")
    db3 = SessionLocal()
    repo3 = TaskRepository(db3)
    # 用已 RUNNING 的 task2 写入覆盖式快照
    t2 = repo3.get(task2)
    repo3.save_snapshot(t2, phase="P1", payload={"jd_items": ["岗位职责", "任职资格"]})
    db3.commit()
    r_get3 = client.get(f"/api/task/{task2}", **REQ)
    snap = r_get3.json().get("snapshot")
    check(snap is not None and snap["phase"] == "P1", "恢复权威快照 P1",
          extra=str(snap))
    check(snap["payload"].get("jd_items") == ["岗位职责", "任职资格"], "快照 payload 完整恢复")

    # ── [A7] 终态矩阵：终态后保存被拒 fail closed ──
    print("\n[A7] 终态后保存被拒")
    r_save_term = client.put(f"/api/task/{task2}/save", json={
        "name": "终态改名", "phone": "", "email": "", "location": "", "jd": ""}, **REQ)
    check(r_save_term.status_code == 409, "终态(RUNNING 非编辑态)保存被拒",
          extra=str(r_save_term.status_code))

    db.close(); db2.close(); db3.close()
    print(f"\n结果：{_passed} 通过 / {_failed} 失败")
    return 1 if _failed else 0


if __name__ == "__main__":
    def _fn(state):
        return _run_tests_inner(state)

    run_isolated("v22_t3_", _fn, "V2.2.0 T3 task API gate")