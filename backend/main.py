"""FastAPI 入口。

启动：uvicorn main:app --reload
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.routes import experience, generate, jd, resume
from core.errors import DomainError
from core.version import APP_VERSION
from database.init_db import init_db
from vectorstore.chroma_store import backend as vector_backend

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时建表（含 V1.3 的 VectorIndexJob）
    init_db()
    yield


app = FastAPI(
    title="AI Career Resume Assistant",
    version=APP_VERSION,
    lifespan=lifespan,
    description=(
        "核心生成：POST /api/resume/generate-docx\n"
        "V1.1 兼容（deprecated）：POST /api/resume/generate\n"
        "V1.2 模板：/api/template/*"
    ),
)


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """所有领域异常统一为 DomainErrorOut 结构。"""
    status_code = exc.http_status or 500
    payload = exc.to_dict()
    logger.warning(
        f"[DomainError] {request.method} {request.url.path} "
        f"-> {exc.error_code} stage={exc.stage}: {exc.message}"
    )
    return JSONResponse(
        status_code=status_code,
        content=payload,
    )


app.include_router(resume.router, prefix="/api/resume", tags=["resume"])
app.include_router(experience.router, prefix="/api/experience", tags=["experience"])
app.include_router(jd.router, prefix="/api/jd", tags=["jd"])
# V1.3 新核心 + V1.1 旧 generate 兼容
app.include_router(generate.router, prefix="/api/resume", tags=["generate"])

# V1.2：模板填充路由（延迟 import，python-docx 缺失时 V1.1 链路仍可启动）
try:
    from api.routes import template
    app.include_router(template.router, prefix="/api/template", tags=["template-v1.2"])
except ImportError:
    pass


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "AI Career Resume Assistant V1",
        "vector_backend": vector_backend(),
        "version": APP_VERSION,
        "core_entry": "POST /api/resume/generate-docx",
    }


if __name__ == "__main__":
    import uvicorn
    from core.config import settings

    uvicorn.run("main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=True)
