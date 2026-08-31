"""FastAPI 入口。

启动：uvicorn main:app --reload
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from api.routes import experience, generate, jd, resume
from core.config import settings
from core.errors import DomainError
from core.security import is_write_request, set_session_cookie, validate_write_request
from core.version import APP_VERSION
from database.init_db import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时建表（V1.5.0：Fact / SchemaVersion / FactEmbedding）
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


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    """V2.0.0 本地管理安全边界（PLAN §3.3）。

    - 写操作（POST/PUT/PATCH/DELETE）校验 Host/Origin/启动会话令牌；
      任一不满足直接拒绝（403），防止本机其他网页静默调用管理接口。
    - 每个响应种下启动会话 Cookie（HttpOnly + SameSite=Strict），
      前端同源请求自动携带，令牌不通过 URL 暴露。
    """
    if is_write_request(request):
        reason = validate_write_request(request)
        if reason is not None:
            return JSONResponse(
                status_code=403,
                content={
                    "ok": False,
                    "error_code": "FORBIDDEN",
                    "stage": "security",
                    "message": f"写入被拒绝：{reason}",
                    "retryable": False,
                    "details": {},
                },
            )
    response = await call_next(request)
    set_session_cookie(response)
    return response


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

# V2.0.0：连接配置与系统维护薄 API（PLAN §3.2 / §3.3 / §4.1）
from api.routes import config, system
app.include_router(config.router, prefix="/api/config", tags=["config-v2"])
app.include_router(system.router, prefix="/api/system", tags=["system-v2"])

# V1.2：模板填充路由（延迟 import，python-docx 缺失时 V1.1 链路仍可启动）
try:
    from api.routes import template
    app.include_router(template.router, prefix="/api/template", tags=["template-v1.2"])
except ImportError:
    pass


@app.get("/api/health", tags=["system"])
def health():
    """同源健康检查：保留原 GET / 的版本语义，前端与启动器据此判定就绪。"""
    return {
        "status": "ok",
        "service": "AI Career Resume Assistant",
        "version": APP_VERSION,
        "core_entry": "POST /api/resume/generate-docx",
    }


# V2.0.0：前端同源托管。生产构建产物存在时挂载静态资源并提供 SPA 回退；
# 未构建（源码 / CLI 开发）时回退为纯 JSON 根路由，不破坏原入口。
# 冻结打包时 frontend/dist 位于 _MEIPASS 包内；源码模式下是 backend 的兄弟目录。
import sys as _sys

if getattr(_sys, "frozen", False) and hasattr(_sys, "_MEIPASS"):
    FRONTEND_DIST = Path(_sys._MEIPASS) / "frontend" / "dist"
else:
    FRONTEND_DIST = settings.BASE_DIR.parent / "frontend" / "dist"

if FRONTEND_DIST.is_dir():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/", include_in_schema=False)
    def spa_index() -> FileResponse:
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        """SPA 前端路由回退：/api 与 /assets 由前置路由处理，其余回退到 index.html。"""
        if full_path.startswith(("api/", "assets/")):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")

else:
    @app.get("/")
    def root():
        return {
            "status": "ok",
            "service": "AI Career Resume Assistant V1",
            "version": APP_VERSION,
            "core_entry": "POST /api/resume/generate-docx",
        }


if __name__ == "__main__":
    import uvicorn
    from core.config import settings

    uvicorn.run("main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=True)
