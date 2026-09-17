"""V2.2.0 T3：Task API（创建 / 保存确认 / 冻结 / 启动 / 读取恢复）。

覆盖 PLAN V220-G01/G02 与 T3 完成证据（创建/保存/刷新/重连/终态矩阵）：
- POST /api/task               创建新的 DRAFT 任务；
- PUT  /api/task/{id}/save     保存草稿（姓名必填；后端确认，非前端假状态）；
- POST /api/task/{id}/freeze   冻结不可变 InputRevision（READY）；
- POST /api/task/{id}/start    置 RUNNING 并强制"单前台活动任务"门禁；
- GET  /api/task/{id}          读取权威快照 + 最新入参（刷新/重连/恢复）。

SSE 流（T4）与终态取消（T5）在后续 Task 独立实现；本路由只提供同步读/写与恢复视图。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from api import schemas
from database.session import SessionLocal, get_db
from services.task_service import TaskService

router = APIRouter()


def _svc(db=Depends(get_db)) -> TaskService:
    return TaskService(db)


@router.post("", response_model=schemas.TaskOut)
def create_task(svc: TaskService = Depends(_svc)):
    """创建一个新任务（DRAFT）。每个新任务重新填写，不从旧任务/档案回填。"""
    return svc.create_task()


@router.put("/{task_id}/save", response_model=schemas.TaskOut)
def save_draft(task_id: str, body: schemas.TaskInputIn,
               svc: TaskService = Depends(_svc)):
    """保存草稿入参（姓名必填）。返回后端已确认的持久化状态。"""
    return svc.save_draft(
        task_id, name=body.name, phone=body.phone, email=body.email,
        location=body.location, jd=body.jd)


@router.post("/{task_id}/freeze", response_model=schemas.TaskOut)
def freeze_input(task_id: str, body: schemas.TaskInputIn,
                 svc: TaskService = Depends(_svc)):
    """冻结不可变 InputRevision（进入 READY）。冻结后不再原地改写。"""
    return svc.freeze_input(
        task_id, name=body.name, phone=body.phone, email=body.email,
        location=body.location, jd=body.jd)


@router.post("/{task_id}/start", response_model=schemas.TaskOut)
def start_task(task_id: str, svc: TaskService = Depends(_svc)):
    """启动生成：置 RUNNING 前强制执行单前台活动任务门禁（409 fail closed）。"""
    return svc.start_task(task_id)


@router.post("/{task_id}/generate", response_model=schemas.TaskOut)
def run_generation(task_id: str, svc: TaskService = Depends(_svc)):
    """异步启动生成 worker（T06d）：RUNNING（或刚置 RUNNING）→ 后台执行 P1–P4。

    运行期间通过 existing SSE stream 渐进返回 P1–P4 结果；到达终态时 SUCCEEDED/FAILED/
    CANCELLED。本接口立即返回当前任务视图，不阻塞在生成完成。
    """
    return svc.run_generation(task_id)


@router.post("/{task_id}/cancel", response_model=schemas.TaskOut)
def cancel_task(task_id: str, svc: TaskService = Depends(_svc)):
    """实际取消（V220-G02）：RUNNING/CANCELLING → CANCELLED。

    先发协作式取消信号（置 token、撤销 revision fence、清理 Provider/worker/资源、
    释放本地活动槽），再收尾子任务并落地 CANCELLED。迟到结果经写入门禁 + fence 拒收。
    """
    return svc.cancel_task(task_id)


@router.get("/records", response_model=list[schemas.TaskRecordOut])
def list_records(limit: int = 200, svc: TaskService = Depends(_svc)):
    """我的简历：真实生成记录列表（V220-R2-T08）。

    列出所有 SUCCEEDED 且已发布 DOCX/PDF 产物的任务；每条含可下载引用与最新入参。
    必须在 GET /{task_id} 之前声明，避免被路径参数捕获。为空返回 []，不伪造历史。
    """
    return svc.list_records(limit=limit)


@router.get("/{task_id}", response_model=schemas.TaskOut)
def get_task(task_id: str, svc: TaskService = Depends(_svc)):
    """读取权威快照 + 最新入参（刷新/重连/恢复）。"""
    return svc.get_task(task_id)


@router.get("/{task_id}/stream")
def stream_task(task_id: str, after_seq: int = -1,
                svc: TaskService = Depends(_svc)):
    """SSE 任务事件流（T4）：先权威快照，再订阅后续 seq；终态后 done 关闭。

    客户端首次进入或重连：先读权威快照，再从 from_seq=snapshot_seq（或 after_seq）
    订阅业务完成事件；重复 seq 由客户端幂等忽略；出现缺口（环形缓冲过期/容量压缩
    造成的 seq 不连续）返回 refetch，客户端必须重取权威快照，禁止自行拼接猜测。

    SSE 为只读投影：不触发任何 LLM / Embedding / Word 副作用，重连不重复模型调用。
    """
    from core.task import TERMINAL_STATUSES, TaskStatus
    from services import task_sse
    from services.task_repository import TaskRepository

    def _snapshot_payload(db):
        repo = TaskRepository(db)
        task = repo.get(task_id)
        if task is None:
            return None, None
        return task

    def generate():
        import time
        resume_from = after_seq
        last_sent = -1
        while True:
            db = SessionLocal()
            task = None
            try:
                task = _snapshot_payload(db)
                if task is None:
                    yield task_sse.sse_frame("error", {
                        "task_id": task_id, "reason": "task_not_found"})
                    return
                repo = TaskRepository(db)
                snap = repo.snapshot_seq(task_id)
                plan = task_sse.build_initial(resume_from, snap)
                from_seq = plan["from_seq"]
                # 权威快照帧
                from database.models import TaskSnapshot
                snap_obj = db.query(TaskSnapshot).filter_by(task_id=task_id).first()
                task_status = TaskStatus(task.status)
                yield task_sse.snapshot_frame(
                    task_id, snap, snap_obj.phase if snap_obj else "",
                    snap_obj.payload if snap_obj else {},
                    task.status, task_status in TERMINAL_STATUSES)
                # 订阅从 from_seq 之后的事件
                events = repo.list_events_after(task_id, from_seq)
                seqs = [e["seq"] for e in events]
                if task_sse.detect_gap(seqs, from_seq):
                    yield task_sse.refetch_frame(
                        task_id, "gap", from_seq, snap,
                        expected=(from_seq + 1), got=(seqs[0] if seqs else None))
                    # 回退到权威快照 seq 重新订阅
                    from_seq = snap
                    events = repo.list_events_after(task_id, from_seq)
                for e in events:
                    last_sent = e["seq"]
                    yield task_sse.event_frame(
                        task_id, e["input_revision"], e["seq"], e["event_type"],
                        e["phase"], e["payload"])
                if task_status in TERMINAL_STATUSES:
                    yield task_sse.done_frame(task_id, task.status)
                    return
            finally:
                db.close()
            if last_sent > resume_from:
                resume_from = last_sent
            time.sleep(0.2)

    return StreamingResponse(generate(), media_type="text/event-stream")