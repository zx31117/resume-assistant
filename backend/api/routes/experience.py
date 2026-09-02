"""经历 CRUD 与提取路由。

V2.0.1（T3）：提取与 Experience create/update/delete 统一进入 OperationTracker，
记录真实阶段、资源类型与事务/回滚结果（PLAN §5.2）；批量页面用
X-Operation-Group-ID 关联顺序 create 子操作，子事务边界不变（PLAN §3.3）。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from api import schemas
from core.config import settings
from core.operations import OperationType, ResourceType, resolve_operation_id, tracker, valid_operation_id
from database.session import get_db
from services import experience_extractor, experience_service

router = APIRouter()
_USER_ID = settings.DEFAULT_USER_ID


@router.post("/extract", response_model=schemas.ExtractResponse)
def extract(
    req: schemas.ExtractRequest,
    x_operation_id: Optional[str] = Header(default=None, alias="X-Operation-ID"),
):
    """原始简历文本 → 结构化经历列表（AI 提取，不入库）。"""
    operation_id = resolve_operation_id(x_operation_id)
    with tracker.operation(OperationType.EXTRACT, operation_id=operation_id) as recording:
        with recording.stage("input_validate", "输入校验", ResourceType.LOCAL_CPU):
            if not (req.resume_text or "").strip():
                raise HTTPException(status_code=422, detail="简历文本为空，请先解析 PDF 或粘贴文本")
        with recording.stage("llm_extract", "LLM 提取等待", ResourceType.LLM):
            experiences = experience_extractor.extract_experiences(req.resume_text)
        # V2.0.0 修复：提取失败被静默吞掉后按"空成功"返回，前端进入 0 项卡死。
        # 这里把"空结果"当作明确失败（fail-closed），由前端提示重试。
        with recording.stage("result_validate", "结构化结果校验", ResourceType.LOCAL_CPU):
            if not experiences:
                raise HTTPException(status_code=422, detail="未能从简历中提取到经历，请确认「本地系统」已配置并测试连接后重试")
    return {"experiences": experiences}


@router.post("/", response_model=schemas.ExperienceOut)
def save(
    req: schemas.ExperienceItem,
    db: Session = Depends(get_db),
    x_operation_id: Optional[str] = Header(default=None, alias="X-Operation-ID"),
    x_operation_group_id: Optional[str] = Header(default=None, alias="X-Operation-Group-ID"),
):
    """保存经历（写 SQL + 向量库）。"""
    operation_id = resolve_operation_id(x_operation_id)
    group_id = valid_operation_id(x_operation_group_id)
    with tracker.operation(OperationType.EXPERIENCE_CREATE, group_id=group_id, operation_id=operation_id) as recording:
        return experience_service.create_experience(db, _USER_ID, req.model_dump(), recording=recording)


@router.get("/", response_model=list[schemas.ExperienceOut])
def list_all(db: Session = Depends(get_db)):
    return experience_service.list_experiences(db, _USER_ID)


@router.put("/{exp_id}", response_model=schemas.ExperienceOut)
def update(
    exp_id: str,
    req: schemas.ExperienceItem,
    db: Session = Depends(get_db),
    x_operation_id: Optional[str] = Header(default=None, alias="X-Operation-ID"),
):
    operation_id = resolve_operation_id(x_operation_id)
    with tracker.operation(OperationType.EXPERIENCE_UPDATE, operation_id=operation_id) as recording:
        exp = experience_service.update_experience(db, exp_id, req.model_dump(), recording=recording)
        if not exp:
            raise HTTPException(status_code=404, detail="Experience not found")
        return exp


@router.delete("/{exp_id}")
def delete(
    exp_id: str,
    db: Session = Depends(get_db),
    x_operation_id: Optional[str] = Header(default=None, alias="X-Operation-ID"),
):
    operation_id = resolve_operation_id(x_operation_id)
    with tracker.operation(OperationType.EXPERIENCE_DELETE, operation_id=operation_id) as recording:
        ok = experience_service.delete_experience(db, exp_id, recording=recording)
        if not ok:
            raise HTTPException(status_code=404, detail="Experience not found")
        return {"ok": True}
