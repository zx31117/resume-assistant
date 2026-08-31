"""经历 CRUD 路由。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api import schemas
from core.config import settings
from database.session import get_db
from services import experience_extractor, experience_service

router = APIRouter()
_USER_ID = settings.DEFAULT_USER_ID


@router.post("/extract", response_model=schemas.ExtractResponse)
def extract(req: schemas.ExtractRequest):
    """原始简历文本 → 结构化经历列表（AI 提取，不入库）。"""
    if not (req.resume_text or "").strip():
        raise HTTPException(status_code=422, detail="简历文本为空，请先解析 PDF 或粘贴文本")
    experiences = experience_extractor.extract_experiences(req.resume_text)
    # V2.0.0 修复：提取失败被静默吞掉后按"空成功"返回，前端进入 0 项卡死。
    # 这里把"空结果"当作明确失败（fail-closed），由前端提示重试。
    if not experiences:
        raise HTTPException(status_code=422, detail="未能从简历中提取到经历，请确认「本地系统」已配置并测试连接后重试")
    return {"experiences": experiences}


@router.post("/", response_model=schemas.ExperienceOut)
def save(req: schemas.ExperienceItem, db: Session = Depends(get_db)):
    """保存经历（写 SQL + 向量库）。"""
    return experience_service.create_experience(db, _USER_ID, req.model_dump())


@router.get("/", response_model=list[schemas.ExperienceOut])
def list_all(db: Session = Depends(get_db)):
    return experience_service.list_experiences(db, _USER_ID)


@router.put("/{exp_id}", response_model=schemas.ExperienceOut)
def update(exp_id: str, req: schemas.ExperienceItem, db: Session = Depends(get_db)):
    exp = experience_service.update_experience(db, exp_id, req.model_dump())
    if not exp:
        raise HTTPException(status_code=404, detail="Experience not found")
    return exp


@router.delete("/{exp_id}")
def delete(exp_id: str, db: Session = Depends(get_db)):
    ok = experience_service.delete_experience(db, exp_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Experience not found")
    return {"ok": True}
