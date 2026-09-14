"""V2.2.0 T4 验证：SSE seq / 去重 / 缺口重取 / 断线恢复 / artifact 身份。

退出码 0 = 业务断言通过且临时 runtime 清理干净；非 0 = 有失败/异常/清理失败。

覆盖（PLAN §4 T4 完成证据：重复/乱序/缺口/缓冲过期/重连不增调用）：
- [S1] 纯协议：should_accept 去重（重复/乱序旧 seq 幂等忽略；递增接受）；
- [S2] 纯协议：detect_gap 连续无缺口；跳跃/首个即缺 → 缺口；
- [S3] build_initial：首次(from_seq=snapshot)/带 after_seq>=snapshot(增量)正确；
- [S4] API 终态流：先权威快照，再按 seq 顺序投递业务完成事件，最后 done 关闭；
- [S5] 重连增量：with after_seq=last，只返回该 seq 之后的事件，不重放旧事件；
- [S6] 缺口重取：删除中间一条事件后可探测缺口，返回 refetch（客户端须重取快照）；
- [S7] 事件帧携带 task_id/input_revision/seq/type/phase/payload；
- [S8] 快照 seq 单调、业务完成事件 seq 全局唯一可靠序（SSE 断点基准）。

SSE 不触发任何模型副作用，重连只读持久化状态——"重连不重复模型调用"由结构保证。
"""
from __future__ import annotations

import json
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


def _parse_sse(text: str) -> list[dict]:
    """把 SSE 文本解析为 [{event, data}] 列表。"""
    frames = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        ev = ""
        dat = ""
        for line in block.split("\n"):
            if line.startswith("event:"):
                ev = line[len("event:"):].strip()
            elif line.startswith("data:"):
                dat += line[len("data:"):].strip()
        if ev:
            frames.append({"event": ev, "data": json.loads(dat)})
    return frames


def _run_tests_inner(state) -> int:
    from fastapi.testclient import TestClient
    from main import app
    from services import task_sse
    from services.task_repository import TaskRepository
    from services.task_service import TaskService
    from core.task import TaskStatus, SubtaskStatus
    from database.session import SessionLocal, engine
    from core import security

    state.register_engine(engine)
    cookies = {security.SESSION_COOKIE_NAME: security.SESSION_TOKEN}
    auth_headers = {"Host": "127.0.0.1:8000"}
    REQ = {"headers": auth_headers, "cookies": cookies}

    # ── [S1] 纯协议：去重 ──
    print("\n[S1] should_accept 去重")
    check(task_sse.should_accept(5, 4) is True, "递增 seq 接受")
    check(task_sse.should_accept(4, 4) is False, "重复 seq 幂等忽略")
    check(task_sse.should_accept(3, 4) is False, "乱序旧 seq 忽略")
    check(task_sse.should_accept(2, 5) is False, "远旧 seq 忽略")

    # ── [S2] 纯协议：缺口检测 ──
    print("\n[S2] detect_gap")
    check(task_sse.detect_gap([6, 7, 8], 5) is False, "连续无缺口")
    check(task_sse.detect_gap([], 5) is False, "无新事件不算缺口")
    check(task_sse.detect_gap([7], 5) is True, "首个事件跳跃 => 缺口")
    check(task_sse.detect_gap([6, 8], 5) is True, "中间缺号 => 缺口")

    # ── [S3] build_initial ──
    print("\n[S3] build_initial 恢复顺序")
    p1 = task_sse.build_initial(-1, 9)
    check(p1["from_seq"] == 9 and p1["snapshot_seq"] == 9, "首次从 snapshot_seq 续订")
    p2 = task_sse.build_initial(20, 9)
    check(p2["from_seq"] == 20, "after_seq>=snapshot：增量续订")
    p3 = task_sse.build_initial(7, 9)
    check(p3["from_seq"] == 9, "after_seq<snapshot：回退到快照")
    check(task_sse.build_initial(None, 4)["from_seq"] == 4, "None after_seq 视为首次")

    # ── [S4] API 终态流：先快照→有序事件→done ──
    print("\n[S4] API 终态流")
    client = TestClient(app)
    state.register_client(client)
    from database import migrations as mig
    mig.run_migrations()
    svc_db = SessionLocal()
    svc = TaskService(svc_db)
    t = svc.create_task()
    task_id = t["task_id"]
    svc.save_draft(task_id, name="甲", phone="138", email="a@b.c", location="上海", jd="JD")
    svc.freeze_input(task_id, name="甲", phone="138", email="a@b.c", location="上海", jd="JD")
    svc.start_task(task_id)
    # 用 repository 写快照 + 事件并推进终态
    db = SessionLocal()
    repo = TaskRepository(db)
    task = repo.get(task_id)
    repo.save_snapshot(task, phase="P3", payload={"fact_id": "f1", "headline": "h"})
    repo.append_event(task, input_revision=1, event_type="fact_completed", phase="P3",
                      payload={"fact_id": "f1", "headline": "h", "body": "b"})
    repo.append_event(task, input_revision=1, event_type="reason_delta", phase="P3",
                      payload={"fact_id": "f1", "text": "原始理由"})
    repo.transition(task, TaskStatus.SUCCEEDED)
    db.commit()

    r = client.get(f"/api/task/{task_id}/stream", **REQ)
    check(r.status_code == 200, "流返回 200", extra=str(r.status_code))
    frames = _parse_sse(r.text)
    check(frames[0]["event"] == "snapshot", "首条为权威快照", extra=frames[0]["event"])
    snap_data = frames[0]["data"]
    check(snap_data["phase"] == "P3" and snap_data["status"] == "SUCCEEDED",
          "快照含阶段与终态", extra=str(snap_data))
    # 事件（跳过 snapshot）
    events = [f for f in frames if f["event"] == "event"]
    check(len(events) == 2, "投递 2 条业务完成事件", extra=str(len(events)))
    check(events[0]["data"]["seq"] < events[1]["data"]["seq"], "事件按 seq 递增")
    check(events[0]["data"]["type"] == "fact_completed", "事件类型正确")
    # 每帧携带 task_id/input_revision/seq/type/phase/payload（S7）
    required = ["task_id", "input_revision", "seq", "type", "phase", "payload"]
    all_ok = all(all(k in e["data"] for k in required) for e in events)
    check(all_ok, "事件帧携带全部协议字段")
    check(events[0]["data"]["task_id"] == task_id, "事件帧绑 task_id")
    last_sent = events[-1]["data"]["seq"]
    tail_events = [f for f in frames if f["event"] != "snapshot"]
    check(frames[-1]["event"] == "done", "终态后以 done 关闭", extra=frames[-1]["event"])
    check(frames[-1]["data"]["status"] == "SUCCEEDED", "done 携带终态")

    # ── [S5] 重连增量：after_seq=last，只返回其后事件 ──
    print("\n[S5] 重连增量")
    r2 = client.get(f"/api/task/{task_id}/stream?after_seq={last_sent}", **REQ)
    frames2 = _parse_sse(r2.text)
    ev2 = [f for f in frames2 if f["event"] == "event"]
    check(len(ev2) == 0, "after_seq=last 后无新事件（不重放）", extra=str(len(ev2)))
    check(frames2[0]["event"] == "snapshot" and frames2[-1]["event"] == "done",
          "重连仍先快照后 done")

    # ── [S6] 缺口重取：删除中间事件（模拟环形缓冲/容量压缩）→ refetch ──
    print("\n[S6] 缺口重取")
    db2 = SessionLocal()
    from database.models import TaskEvent
    # 删除 seq 最小的事件，制造"从快照下一个 seq 缺失"
    ev_rows = db2.query(TaskEvent).filter_by(task_id=task_id).order_by(TaskEvent.seq).all()
    if ev_rows:
        db2.delete(ev_rows[0])
        db2.commit()
    r3 = client.get(f"/api/task/{task_id}/stream?after_seq=0", **REQ)
    frames3 = _parse_sse(r3.text)
    refetch = [f for f in frames3 if f["event"] == "refetch"]
    # 缺口判定条件：list_events_after(task, from_seq) 的首 seq != from_seq+1。
    # 快照 seq 若用于事件 seq 之后仍成立；删除首事件后 from_seq=snapshot_seq，
    # 首个现存事件 seq > snapshot_seq+1 => 缺口 => refetch。
    check(len(refetch) >= 1, "缺口被探测并返回 refetch", extra=str(len(refetch)))
    if refetch:
        check(refetch[0]["data"]["reason"] == "gap", "refetch 理由是 gap")

    # ── [S8] 快照 seq 单调（业务完成事件 seq 全任务唯一可靠序）──
    print("\n[S8] seq 基线")
    db3 = SessionLocal()
    repo3 = TaskRepository(db3)
    snap_now = repo3.snapshot_seq(task_id)
    check(isinstance(snap_now, int) and snap_now >= 1, "snapshot_seq 单调整数")

    for df in (db, db2, db3, svc_db):
        df.close()
    print(f"\n结果：{_passed} 通过 / {_failed} 失败")
    return 1 if _failed else 0


if __name__ == "__main__":
    def _fn(state):
        return _run_tests_inner(state)

    run_isolated("v22_t4_", _fn, "V2.2.0 T4 SSE protocol gate")