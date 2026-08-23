"""简历生成路由。

V1.0/V1.1：/generate — deprecated（V1.5.0：RAG 已退出，返回 410）。
V1.3/V1.5.0：/generate-docx — 唯一核心链路入口（两层选材 + 受约束改写 + .docx）。
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
from services import resume_generation_service

logger = logging.getLogger(__name__)

router = APIRouter()
_USER_ID = settings.DEFAULT_USER_ID

_DEPRECATION_WARNING = (
    "/api/resume/generate is deprecated since 1.3.0. "
    "Use POST /api/resume/generate-docx instead."
)


@router.post("/generate")
def generate(req: schemas.GenerateRequest, db: Session = Depends(get_db)):
    """**DEPRECATED (since 1.5.0)** 旧 Markdown 简历生成已退出。

    V1.5.0：rag_service 已删除，旧 RAG 检索链路不再可用。
    请使用 POST /api/resume/generate-docx（V1.5.0 两层选材 + 受约束改写）。
    """
    warnings.warn(_DEPRECATION_WARNING, DeprecationWarning, stacklevel=2)
    logger.warning("调用已弃用接口 /api/resume/generate（V1.5.0：RAG 已退出）")
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=410,
        content={
            "ok": False,
            "error_code": "DEPRECATED",
            "stage": "generate_route",
            "message": _DEPRECATION_WARNING,
            "retryable": False,
            "details": {"removed_since": "1.5.0", "replacement": "POST /api/resume/generate-docx"},
        },
    )


@router.post("/generate-docx", response_model=schemas.ResumeDocxGenerateResponse)
def generate_docx(req: schemas.ResumeDocxGenerateRequest, db: Session = Depends(get_db)):
    """V1.3 核心链路：唯一主入口。

    V1.5.0 链路（PLAN §2 / §7 T6）：
    1. 迁移检查（Fact/SchemaVersion 就绪）
    2. JD 分析（strict）
    3. 第一层选材（固定槽位 → CandidateExperienceSet）
    4. 第二层事实选材（→ SelectedEvidenceSet）
    5. 受约束改写（fact_refs → GeneratedResumeContentV15）
    6. Builder 收缩装配（build_v15）
    7. 渲染 + 排版
    8. 保存 DOCX

    错误统一以 DomainError 结构返回（见 schemas.DomainErrorOut）。
    """
    # NOTE: DomainError 被 main.py 的 exception_handler 统一映射为 JSON（ok=False + error_code + stage + ...）
    return resume_generation_service.generate_docx(db, req)
