"""V2.2.0 T4：SSE 恢复与去重协议（PLAN §2.3 / V220-G01）。

纯函数，供 SSE 端点与客户端适配复用，保证协议语义单一真源、可无 LLM 单元验证：

- should_accept：客户端去重（seq 递增才接受；重复/乱序旧 seq 幂等忽略）。
- detect_gap：给定 from_seq 与待投递事件 seq 列表，判断是否出现缺口。
  缺口 = 第一个事件不是 from_seq+1 或后续不连续；出现缺口（如服务端环形缓冲
  过期、事件被容量压缩）时客户端必须重取权威快照，禁止自行拼接猜测。
- build_initial：决定"先权威快照，再从某 seq 订阅后续"的投递顺序。

SSE 事件统一携带 task_id / input_revision / seq / type / phase / payload；
业务完成事件与权威快照持久化；字符/token delta 不逐条写数据库。
重连只读持久化状态，"不重复模型调用"由结构保证（SSE 不触发任何生成副作用）。
"""
from __future__ import annotations

import json
from typing import Any, Optional


def should_accept(seq: int, last_seen_seq: int) -> bool:
    """客户端去重：只有 seq > last_seen_seq 才接受；否则幂等忽略（不按内存拼接）。"""
    return seq > last_seen_seq


def detect_gap(event_seqs: list[int], from_seq: int) -> bool:
    """事件 seq 从 from_seq+1 起是否连续。不连续（含首个即跳跃/缺口）视为缺口。"""
    expected = from_seq + 1
    for s in event_seqs:
        if s != expected:
            return True
        expected += 1
    return False


def build_initial(after_seq: int, snapshot_seq: int) -> dict[str, Any]:
    """决定恢复顺序：始终先发权威快照，再从有效 seq 订阅后续。

    - after_seq < snapshot_seq（或首次/未携带）：快照已推进，从 snapshot_seq 续订；
    - after_seq >= snapshot_seq：客户端看到的快照未变，从 after_seq 续订增量事件。
    """
    if after_seq is None or after_seq < 0:
        after_seq = -1
    from_seq = max(after_seq, snapshot_seq)
    return {"from_seq": from_seq, "snapshot_seq": snapshot_seq}


def sse_frame(event: str, data: dict[str, Any]) -> str:
    """单条 SSE 帧：\\n 分隔 data，确保换行不破坏协议。"""
    payload = json.dumps(data, ensure_ascii=False)
    payload = payload.replace("\n", "\\n").replace("\r", "\\r")
    return f"event: {event}\ndata: {payload}\n\n"


def event_frame(task_id: str, input_revision: int, seq: int, event_type: str,
                phase: str, payload: dict[str, Any]) -> str:
    """业务完成事件帧：统一带 task_id/input_revision/seq/type/phase/payload。"""
    return sse_frame("event", {
        "task_id": task_id,
        "input_revision": input_revision,
        "seq": seq,
        "type": event_type,
        "phase": phase,
        "payload": payload,
    })


def snapshot_frame(task_id: str, seq: int, phase: str, payload: dict[str, Any],
                   status: str, terminal: bool) -> str:
    """权威快照帧：客户端据其恢复当前可回看业务结果。"""
    return sse_frame("snapshot", {
        "task_id": task_id,
        "seq": seq,
        "phase": phase,
        "payload": payload,
        "status": status,
        "terminal": terminal,
    })


def refetch_frame(task_id: str, reason: str, from_seq: int, snapshot_seq: int,
                  expected: Optional[int] = None, got: Optional[int] = None) -> str:
    """缺口/缓冲过期指示：客户端必须重取权威快照。"""
    return sse_frame("refetch", {
        "task_id": task_id,
        "reason": reason,
        "from_seq": from_seq,
        "snapshot_seq": snapshot_seq,
        "expected": expected,
        "got": got,
    })


def done_frame(task_id: str, status: str) -> str:
    return sse_frame("done", {"task_id": task_id, "status": status})