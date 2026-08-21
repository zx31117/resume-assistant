"""简历生成路由。

V1.0/V1.1：/generate（RAG + 生成 Markdown）— deprecated，保留用于 V1.1 验收兼容。
V1.3：/generate-docx — 唯一核心链路入口（严格模式 / 全流程 / 生成 .docx）。
"""
from __future__ import annotations

import logging
import warnings

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api import schemas
from core.config import settings
from core.errors import DomainError
from database.session import get_db
from services import experience_service, rag_service, resume_generator, resume_generation_service

logger = logging.getLogger(__name__)

router = APIRouter()
_USER_ID = settings.DEFAULT_USER_ID

_DEPRECATION_WARNING = (
    "/api/resume/generate is deprecated since 1.3.0. "
    "Use POST /api/resume/generate-docx instead."
)


@router.post("/generate", response_model=schemas.ResumeOut)
def generate(req: schemas.GenerateRequest, db: Session = Depends(get_db)):
    """**DEPRECATED (since 1.3.0)** 旧 Markdown 简历生成。兼容 V1.1 验收。

    新链路请使用 POST /api/resume/generate-docx。
    """
    warnings.warn(_DEPRECATION_WARNING, DeprecationWarning, stacklevel=2)
    logger.warning("调用已弃用接口 /api/resume/generate")

    user_id = req.user_id or _USER_ID
    matched = rag_service.retrieve(req.jd_analysis, user_id=user_id, k=req.top_k)
    experiences = []
    for m in matched:
        exp = experience_service.get_experience(db, m["id"])
        if exp:
            experiences.append({
                "type": exp.type,
                "title": exp.title,
                "company": exp.company,
                "time": exp.time,
                "role": exp.role,
                "description": exp.description,
                "skills": exp.skills or [],
                "achievements": exp.achievements or [],
            })
    markdown = resume_generator.generate_resume(req.jd_analysis, experiences)
    return {
        "markdown": markdown,
        "matched_experiences": matched,
        "deprecation_warning": _DEPRECATION_WARNING,
    }


@router.post("/generate-docx", response_model=schemas.ResumeDocxGenerateResponse)
def generate_docx(req: schemas.ResumeDocxGenerateRequest, db: Session = Depends(get_db)):
    """V1.3 核心链路：唯一主入口。

    阶段：
    1. 索引就绪检查（VectorIndexJob PENDING/FAILED 幂等处理）
    2. JD 分析（strict，失败抛 JDValidationError）
    3. RAG TopK 匹配
    4. SQL 回读命中经历
    5. ResumeContentGenerator（strict，失败抛 LLMOutputInvalidError）
    6. ResumeBuilder.build（只从 SQL 取事实，按 experience_id 合并 AI bullets）
    7. TemplateRenderer.render + LayoutOptimizer
    8. 保存 DOCX

    错误统一以 DomainError 结构返回（见 schemas.DomainErrorOut）。
    """
    # NOTE: DomainError 被 main.py 的 exception_handler 统一映射为 JSON（ok=False + error_code + stage + ...）
    return resume_generation_service.generate_docx(db, req)
