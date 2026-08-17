"""V1.2 模板路由（标准化模板方向）。

4 个接口（V1.2 主路线 + V1.1 兼容保留但 deprecated）：
- GET  /api/template/list:                     系统内置模板列表（V1.2 主用）
- POST /api/template/generate-docx:            生成简历 DOCX（返回 path+report+download_url，§10.3）
- POST /api/template/generate-report:          调试报告版（V1.2 主用）
- GET  /api/template/download:                 按 path 下载（§10.4）

【deprecated 保留】V1.1 旧路线（解析任意模板）接口不删除，仅标记 deprecated：
- POST /api/template/upload
- GET  /api/template/{template_id}/schema
"""
import json
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.config import settings
from models.resume_document import ResumeDocument
from services import resume_builder
from services.resume_builder import ProfileIncompleteError
from services.docx_writer import TemplateError, load_template_assets
from services.template_renderer import TemplateRenderer
from services import layout_optimizer

router = APIRouter()

# V1.4：源码资产根/运行数据根统一走 settings，不再硬编码
BACKEND_ROOT = str(settings.BASE_DIR)
OUTPUT_DIR = settings.DOCX_OUTPUT_DIR
# 统一由 config 保证目录存在；此处仅幂等 mkdir 避免直接 import settings 时初始化顺序极端情况遗漏
Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)


# ==================================================================
# 请求 / 响应模型
# ==================================================================

class GenerateDocxRequest(BaseModel):
    """§10.3 generate-docx 请求体。

    两种调用方式（二选一）：
      A. V1.2 E2E / 离线开发：直接传 resume_document_json（绕开 V1.1 DB/RAG/LLM 链路）
      B. 未来和 V1.1 集成时：传 user_id + jd，系统内部跑 JD 分析 + RAG + ResumeBuilder
    """
    user_id: str = "default_user"
    template_id: str = "pm_template"
    # 方式 A：直接传 ResumeDocument JSON
    resume_document: Optional[dict] = None
    # 方式 B：JD 全文 + 显式 profile 覆盖（V1.1 集成时用，P1 实现）
    jd: Optional[str] = None
    jd_id: Optional[str] = None
    profile: Optional[dict] = None  # §9.2 第 2 优先级（request 显式传的字段）

    model_config = {"protected_namespaces": ()}


# ==================================================================
# 工具：确保 pm_template.docx 存在（若不存在，尝试调用 build_templates 脚本）
# ==================================================================

def _ensure_template_docx(template_id: str) -> None:
    """如果模板 docx 缺失 → 尝试运行 templates/_build_templates.py 自动构建（E2E 零手动）。
    PowerShell 执行策略阻挡时 FileNotFoundError 会原样冒泡，generate-docx 以 HTTP 500 提示用户手动运行。
    """
    mapping_path = os.path.join(BACKEND_ROOT, "config", "template_mapping.json")
    with open(mapping_path, "r", encoding="utf-8") as f:
        mapping = json.load(f)
    entry = mapping.get(template_id)
    if not entry:
        return
    docx_path = os.path.join(BACKEND_ROOT, entry["docx"].replace("/", os.sep))
    if os.path.exists(docx_path):
        return
    build_script = os.path.join(BACKEND_ROOT, "templates", "_build_templates.py")
    if os.path.exists(build_script):
        import subprocess, sys
        subprocess.check_call([sys.executable, build_script])


# ==================================================================
# GET /api/template/list
# ==================================================================

@router.get("/list")
def list_templates():
    """§10.2：系统内置模板列表。"""
    mapping_path = os.path.join(BACKEND_ROOT, "config", "template_mapping.json")
    if not os.path.exists(mapping_path):
        raise HTTPException(status_code=500, detail="template_mapping.json 缺失")
    with open(mapping_path, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    result = []
    for tid, entry in mapping.items():
        json_path = os.path.join(BACKEND_ROOT, entry["json"].replace("/", os.sep))
        spec_data = {}
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                spec_data = json.load(f)
        sections = [s.get("type") for s in spec_data.get("sections", [])]
        layout = spec_data.get("layout", {})
        result.append({
            "template_id": tid,
            "display_name": spec_data.get("display_name", tid),
            "version": spec_data.get("version", "1.0"),
            "page_limit": layout.get("page_limit", 1),
            "sections": sections,
            "is_default": entry.get("default", False),
        })
    return {"templates": result}


# ==================================================================
# 生成核心（generate-docx 和 generate-report 共用）
# ==================================================================

def _build_and_render(req: GenerateDocxRequest) -> dict:
    """构建 ResumeDocument → 渲染 → 排版优化 → 输出到固定文件。

    返回 generate-report 的结构化响应（generate-docx 再在此基础上裁剪字段）。
    """
    # 1. 确保模板资产存在
    try:
        _ensure_template_docx(req.template_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"模板构建失败：{e}")

    # 2. 构建 ResumeDocument（方式 A：直接传 resume_document；方式 B：P1 再接入 V1.1 全链路）
    warnings: list[str] = []
    profile_source = "direct"
    build_counts: dict = {}
    if req.resume_document is not None:
        # 方式 A：直传
        try:
            resume_doc = ResumeDocument(**req.resume_document)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"resume_document 字段无效: {e}")
        resume_doc = resume_doc.to_standard()
        # 对直传文档也做 profile 处理（复用 ProfileResolver）
        try:
            rd_dict = resume_doc.profile.model_dump()
            profile, profile_source = resume_builder.ProfileResolver.resolve(
                request_profile=req.profile or rd_dict,
                jd_position=resume_doc.profile.target_position or "",
                db_profile=rd_dict,
                resume_content_profile=None,
            )
            resume_doc.profile = profile
        except ProfileIncompleteError as e:
            raise HTTPException(
                status_code=400,
                detail={
                    "ok": False,
                    "error_code": "PROFILE_INCOMPLETE",
                    "message": str(e),
                    "missing_fields": e.missing_fields,
                },
            )
        build_counts = {
            "education": len(resume_doc.education),
            "work": len(resume_doc.work),
            "projects": len(resume_doc.projects),
            "awards": len(resume_doc.awards),
            "skill_groups": len(resume_doc.skills),
        }
    else:
        # 方式 B：需要 V1.1 链路；V1.2 MVP 返回明确提示
        raise HTTPException(
            status_code=400,
            detail="JD 驱动生成需要 V1.1 全链路（JD 分析 + RAG + DB）集成。"
                   "V1.2 MVP 请通过 resume_document 字段传入预构建的 ResumeDocument。",
        )

    # 3. 加载模板 + 渲染
    try:
        renderer = TemplateRenderer(req.template_id, backend_root=BACKEND_ROOT)
        doc, render_warnings, _render_stats = renderer.render(resume_doc)
    except TemplateError as e:
        raise HTTPException(
            status_code=400,
            detail={"ok": False, "error_code": "TEMPLATE_ERROR", "message": str(e)},
        )
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"template_id 错误: {e}")
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e) + "（请在 backend/ 目录下运行: python templates/_build_templates.py）",
        )
    warnings.extend(render_warnings)

    # 渲染层 max_items 兜底截断的项目数检查 + 报告 sections_rendered 生成
    def section_count(sec_type: str) -> int:
        if sec_type == "education": return len(resume_doc.education)
        if sec_type == "work": return len(resume_doc.work)
        if sec_type == "project": return len(resume_doc.projects)
        if sec_type == "skills": return len(resume_doc.skills)
        if sec_type == "awards": return len(resume_doc.awards)
        return 0
    sections_rendered = []
    for sec in renderer.spec.sections:
        label = sec.id
        cnt = section_count(sec.type)
        if cnt:
            label = f"{sec.id}({cnt})"
        sections_rendered.append(label)

    # 4. 排版优化（只调段落级样式，不删条目）
    page_limit = renderer.spec.layout.page_limit
    applied_layout_rules, capacity_warnings = layout_optimizer.optimize(doc, page_limit=page_limit)
    final_page_count = layout_optimizer.estimate_pages(doc)
    if capacity_warnings:
        warnings.extend(capacity_warnings)

    # 5. 保存（固定文件名，不时间戳，避免循环堆积——§10.3 用户审核反馈）
    safe_user_id = "".join(c for c in req.user_id if c.isalnum() or c in "-_") or "user"
    file_name = f"resume_{safe_user_id}_{req.template_id}.docx"
    file_path = os.path.join(OUTPUT_DIR, file_name)
    doc.save(file_path)

    download_url = f"/api/template/download?path=output/{file_name}"

    report = {
        "sections_rendered": sections_rendered,
        "page_count": final_page_count,
        "layout_optimizations_applied": applied_layout_rules,
        "warnings": warnings,
        "profile_source": profile_source,
        "build_counts": build_counts,
    }

    return {
        "ok": True,
        "file_path": f"output/{file_name}",
        "file_name": file_name,
        "report": report,
        "download_url": download_url,
    }


# ==================================================================
# POST /api/template/generate-docx
# ==================================================================

@router.post("/generate-docx")
def generate_docx(req: GenerateDocxRequest):
    """§10.3：生成 DOCX 并返回 path + report + download_url。

    开发阶段**不直接返回二进制流**（用户审核反馈 §10.3：调试更方便）。
    后续 V2 可加 ?as_binary=1 参数。
    """
    return _build_and_render(req)


# ==================================================================
# POST /api/template/generate-report
# ==================================================================

@router.post("/generate-report")
def generate_report(req: GenerateDocxRequest):
    """§10.5：调试报告（同 generate-docx 逻辑，但返回更详尽数据）。"""
    result = _build_and_render(req)
    # 报告版：多加 template 信息
    try:
        _, spec = load_template_assets(req.template_id, BACKEND_ROOT)
        result["template_spec"] = {
            "id": spec.id,
            "display_name": spec.display_name,
            "version": spec.version,
            "sections": [
                {"id": s.id, "type": s.type, "required": s.required, "max_items": s.max_items}
                for s in spec.sections
            ],
        }
    except Exception:
        pass
    return result


# ==================================================================
# GET /api/template/download?path=output/resume_xxx.docx
# ==================================================================

@router.get("/download")
def download_file(path: str = Query(..., description="文件名，或相对 DOCX_OUTPUT_DIR 的相对路径，如 resume_user_pm_template.docx")):
    """§10.4：文件下载。

    V1.4：生成文件统一写入 settings.DOCX_OUTPUT_DIR（源码外 runtime root）；
    安全限制：只允许访问该目录下的文件（防止任意路径穿越）。
    兼容：若调用方仍传入 old-style "output/<name>" 前缀，会自动归一化后校验。
    """
    if not path:
        raise HTTPException(status_code=400, detail="path 为空")
    # 兼容旧前端：若传入 "output/xxx" 去掉前缀，只取文件名部分
    normalized = path.replace("\\", "/")
    if normalized.startswith("output/"):
        normalized = normalized[len("output/"):]
    # 只保留 basename，拒绝 "../" 穿越；文件只能位于 DOCX_OUTPUT_DIR 一级
    filename = os.path.basename(normalized)
    if not filename or filename in (".", ".."):
        raise HTTPException(status_code=400, detail="path 非法")
    abs_output = os.path.abspath(OUTPUT_DIR)
    abs_requested = os.path.join(abs_output, filename)
    if not os.path.isfile(abs_requested):
        raise HTTPException(status_code=404, detail=f"文件不存在: {filename}")
    return FileResponse(
        abs_requested,
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if filename.lower().endswith(".docx") else "application/octet-stream"
        ),
        filename=filename,
    )


# ==================================================================
# [deprecated] V1.1 旧接口保留（不删，防止 V1.1 老调用方 404）
# ==================================================================

@router.post("/upload", deprecated=True, tags=["V1.1 deprecated"])
def upload_template(file: UploadFile = File(...)):
    """V1.1 路线（解析任意用户上传 Word）—— V1.2 已改为系统内置模板，不再使用。"""
    raise HTTPException(
        status_code=410,
        detail="此接口在 V1.2 已下线。请改用 GET /api/template/list 获取系统内置标准化模板列表。",
    )


@router.get("/{template_id}/schema", deprecated=True, tags=["V1.1 deprecated"])
def get_template_schema(template_id: str):
    """V1.1 路线 deprecated。改用 GET /api/template/list 查 section 列表。"""
    raise HTTPException(
        status_code=410,
        detail="此接口在 V1.2 已下线。模板 JSON 描述文件位于 backend/templates/<id>.json，可直接读取。",
    )
