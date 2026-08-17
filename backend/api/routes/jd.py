"""JD 分析路由。"""
from fastapi import APIRouter

from api import schemas
from services import jd_analyzer

router = APIRouter()


@router.post("/analyze")
def analyze(req: schemas.JDRequest):
    """JD 文本 → 结构化岗位需求。"""
    return jd_analyzer.analyze_jd(req.jd_text)
