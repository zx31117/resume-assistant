"""V1.3 T5：唯一核心用例编排 ResumeGenerationService。

串联：
  索引就绪检查 → JDAnalyzer → RAG → SQL 回读 → ResumeContentGenerator
  → ResumeBuilder → TemplateRenderer → LayoutOptimizer → 保存 DOCX。

不直接操作 Word XML（渲染器独立），不直接调 LLM/Embedding（通过 jd_analyzer/resume_content_generator/rag_service）。
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.orm import Session

from api.schemas import (
    BuildCounts,
    BuildMeta,
    GeneratedResumeContent,
    JDAnalysisOut,
    RenderStats,
    RequestProfile,
    ResumeDocxGenerateRequest,
    ResumeDocxGenerateResponse,
    StageStatus,
)
from core.config import settings
from core.errors import (
    DomainError,
    FileSaveError,
    NoMatchedExperienceError,
    ProfileIncompleteError,
    ResumeBuildError,
)
from database import models
from models.resume_document import ResumeDocument
from services import (
    experience_service,
    jd_analyzer,
    layout_optimizer,
    rag_service,
    resume_builder,
    resume_content_generator,
    template_renderer,
    vector_index_sync,
)

logger = logging.getLogger(__name__)

OUTPUT_DIR = settings.DOCX_OUTPUT_DIR
# V1.4：BASE_DIR 已在 Settings 中显式暴露（Path 类型）；保留字符串形式的 BACKEND_ROOT 供 TemplateRenderer 形参消费
BACKEND_ROOT = str(settings.BASE_DIR)


@dataclass
class GenerationContext:
    """请求级上下文（阶段状态、计时、诊断信息收集）。"""

    user_id: str
    template_id: str
    stages: list[StageStatus] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    matched_experience_ids: list[str] = field(default_factory=list)
    rendered_experience_ids: list[str] = field(default_factory=list)
    profile_source: str = ""

    def start(self, stage: str) -> float:
        return time.perf_counter()

    def done(self, stage: str, started_at: float, note: Optional[str] = None) -> None:
        self.stages.append(StageStatus(
            stage=stage,
            status="done",
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
            note=note,
        ))

    def failed(self, stage: str, started_at: float, note: Optional[str] = None) -> None:
        self.stages.append(StageStatus(
            stage=stage,
            status="failed",
            duration_ms=round((time.perf_counter() - started_at) * 1000, 2),
            note=note,
        ))


def _profile_to_dict(p: RequestProfile) -> dict:
    """强类型 RequestProfile → dict（供 ResumeBuilder ProfileResolver 消费）。"""
    d = {
        "name": p.name,
        "phone": p.phone or "",
        "email": p.email or "",
        "target_position": p.target_position or "",
    }
    if p.location is not None:
        d["location"] = p.location
    if p.summary is not None:
        d["summary"] = p.summary
    return d


def _target_position_fallback(req_profile: RequestProfile, jd: JDAnalysisOut) -> RequestProfile:
    """PLAN §4.1：target_position 缺失时使用 JDAnalysis.position。

    不修改原对象，返回一个浅拷贝 patch。
    """
    if req_profile.target_position and req_profile.target_position.strip():
        return req_profile
    jd_pos = (jd.position or "").strip()
    if not jd_pos:
        return req_profile
    return RequestProfile(
        name=req_profile.name,
        phone=req_profile.phone,
        email=req_profile.email,
        location=req_profile.location,
        target_position=jd_pos,
        summary=req_profile.summary,
    )


def generate_docx(
    db: Session,
    req: ResumeDocxGenerateRequest,
) -> ResumeDocxGenerateResponse:
    """核心链路（V1.3 唯一产品主路线）。

    所有关键阶段抛 DomainError 子类，由 API 层统一映射。
    """
    user_id = req.user_id or settings.DEFAULT_USER_ID
    ctx = GenerationContext(user_id=user_id, template_id=req.template_id)

    # ── 1. 索引就绪检查 ─────────────────────────────────────────────
    t = ctx.start("index_check")
    index_stats = vector_index_sync.ensure_user_index_ready(db, user_id)
    ctx.done("index_check", t, note=json.dumps(index_stats, ensure_ascii=False))

    # ── 2. JD 分析（strict） ────────────────────────────────────────
    t = ctx.start("jd_analysis")
    jd: JDAnalysisOut = jd_analyzer.analyze_jd(req.jd_text, strict=True)
    ctx.done("jd_analysis", t, note=f"position={jd.position!r}")

    # ── 3. Profile：target_position 兜底（JDAnalysis.position） ────
    profile_patched = _target_position_fallback(req.profile, jd)

    # ── 4. RAG 检索 ─────────────────────────────────────────────────
    t = ctx.start("rag_match")
    matched = rag_service.retrieve(jd.model_dump(), user_id=user_id, k=req.top_k)
    matched_ids = [m["id"] for m in matched if m.get("id")]
    ctx.matched_experience_ids = matched_ids
    ctx.done("rag_match", t, note=f"matched={len(matched_ids)}/{req.top_k}")

    if not matched_ids:
        raise NoMatchedExperienceError(
            f"RAG 未检索到任何匹配经历（user_id={user_id}, top_k={req.top_k}）",
            stage="rag_match",
        )

    # ── 5. SQL 回读命中 Experience ──────────────────────────────────
    t = ctx.start("sql_readback")
    hit_experiences: list[models.Experience] = []
    for mid in matched_ids:
        exp = experience_service.get_experience(db, mid)
        if exp:
            hit_experiences.append(exp)
    if not hit_experiences:
        raise NoMatchedExperienceError(
            "RAG 返回的 matched_ids 在 SQL 中全部未命中（向量/数据库可能不一致，建议 rebuild）",
            stage="sql_readback",
        )
    ctx.done("sql_readback", t, note=f"hit_sql={len(hit_experiences)}")

    # ── 6. ResumeContentGenerator（strict） ────────────────────────
    t = ctx.start("content_generation")
    generated: GeneratedResumeContent
    cg_warnings: list[str]
    generated, cg_warnings = resume_content_generator.generate_content(
        jd, hit_experiences, strict=True,
    )
    ctx.warnings.extend(cg_warnings)
    ctx.done("content_generation", t, note=(
        f"ai_bullets_items={len(generated.experiences)}"
    ))

    # ── 7. ResumeBuilder.build（唯一内容选择入口） ─────────────────
    t = ctx.start("resume_build")
    request_profile_dict = _profile_to_dict(profile_patched)
    try:
        resume_doc: ResumeDocument
        build_meta: dict[str, Any]
        resume_doc, build_meta = resume_builder.build(
            db,
            user_id=user_id,
            matched_experiences=matched,
            jd_analysis=jd,
            all_experiences=None,  # 内部 list_experiences 拉全量（含 education 未匹配也要）
            request_profile=request_profile_dict,
            generated_content=generated,
        )
    except ProfileIncompleteError:
        raise  # 保持原类型（已是 DomainError 子类）
    except DomainError:
        raise
    except Exception as e:
        logger.exception("ResumeBuilder 未知构建失败")
        raise ResumeBuildError(str(e), details={"error_type": type(e).__name__}) from e
    ctx.profile_source = build_meta.get("profile_source", "")
    ctx.warnings.extend([
        f"AI 优化条目: {len(build_meta.get('ai_covered_experience_ids', []))}",
        f"SQL 回退条目: {len(build_meta.get('fallback_sql_experience_ids', []))}",
    ])
    ctx.rendered_experience_ids = (
        [w.experience_id for w in resume_doc.work if w.experience_id]
        + [p.experience_id for p in resume_doc.projects if p.experience_id]
    )
    ctx.done("resume_build", t, note=json.dumps(build_meta.get("counts", {}), ensure_ascii=False))

    # ── 8. TemplateRenderer.render + LayoutOptimizer ───────────────
    t = ctx.start("render")
    renderer = template_renderer.TemplateRenderer(req.template_id, backend_root=str(BACKEND_ROOT))
    doc, render_warnings, render_stats_raw = renderer.render(resume_doc)
    ctx.warnings.extend(render_warnings)
    page_limit = renderer.spec.layout.page_limit
    applied_layout_rules, capacity_warnings = layout_optimizer.optimize(doc, page_limit=page_limit)
    final_page_count = layout_optimizer.estimate_pages(doc)
    if applied_layout_rules:
        ctx.warnings.append(f"排版规则: {len(applied_layout_rules)} 条")
    if capacity_warnings:
        ctx.warnings.extend(capacity_warnings)
    # 组装 RenderStats（强类型）
    render_stats = RenderStats(
        sections=render_stats_raw.get("sections", []),
        unreplaced_placeholders=render_stats_raw.get("unreplaced_placeholders", []),
        capacity_warnings=list(capacity_warnings),
    )
    ctx.done("render", t, note=(
        f"pages~{final_page_count}(limit<={page_limit}), "
        f"warnings={len(render_warnings) + len(capacity_warnings)}, "
        f"render_preserved={render_stats.all_sections_preserved}"
    ))

    # ── 9. 保存 DOCX ────────────────────────────────────────────────
    t = ctx.start("save_docx")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_user_id = "".join(c for c in user_id if c.isalnum() or c in "-_") or "user"
    file_name = f"resume_{safe_user_id}_{req.template_id}.docx"
    file_path_abs = os.path.join(OUTPUT_DIR, file_name)
    try:
        doc.save(file_path_abs)
    except Exception as e:
        raise FileSaveError(f"DOCX 保存失败: {e}", details={"path": file_path_abs}) from e
    download_url = f"/api/template/download?path=output/{file_name}"
    ctx.done("save_docx", t, note=file_path_abs)

    # ── 10. 组装响应 ────────────────────────────────────────────────
    counts = build_meta.get("counts", {}) or {}
    counts_obj = BuildCounts.model_validate(counts) if isinstance(counts, dict) else counts
    build_meta_obj = BuildMeta.model_validate(build_meta) if isinstance(build_meta, dict) else build_meta
    # ai_unrecognized：ResumeContentGenerator 已经写进 warnings；ResumeBuilder 再从另一个维度再过滤一次，取并集
    cg_unrecognized: list[str] = []
    for w in ctx.warnings:
        if "丢弃未知 experience_id=" in w:
            try:
                eid = w.split("experience_id=", 1)[1].split("（", 1)[0].strip()
                if eid and eid not in cg_unrecognized:
                    cg_unrecognized.append(eid)
            except Exception:
                pass
    if cg_unrecognized:
        merged = sorted(set(build_meta_obj.ai_unrecognized_experience_ids) | set(cg_unrecognized))
        build_meta_obj = build_meta_obj.model_copy(update={"ai_unrecognized_experience_ids": merged})
    return ResumeDocxGenerateResponse(
        file_path=f"output/{file_name}",
        file_name=file_name,
        download_url=download_url,
        stages=ctx.stages,
        matched_experience_ids=ctx.matched_experience_ids,
        rendered_experience_ids=ctx.rendered_experience_ids,
        profile_source=ctx.profile_source,
        page_count=final_page_count,
        warnings=ctx.warnings,
        build_counts=counts_obj,
        build_meta=build_meta_obj,
        render_stats=render_stats,
        template_id=req.template_id,
    )
