"""V1.5.0 核心用例编排 ResumeGenerationService（旧 V1.3 RAG 链路已退出）。

V1.5.0 PLAN §2 / §5 / §7 T6：
  迁移检查 → JD 分析 → 第一层 select_experiences → 第二层 select_evidence
  → 受约束改写 rewrite_with_evidence → build_v15（Builder 收缩）
  → TemplateRenderer → LayoutOptimizer → 保存 DOCX。

不直接操作 Word XML（渲染器独立），不直接调 LLM/Embedding
（通过 jd_analyzer / constrained_rewrite / embedding_service 编排）。
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from sqlalchemy.orm import Session

from api.schemas import (
    BuildCounts,
    BuildMeta,
    JDAnalysisOut,
    RenderStats,
    RequestProfile,
    ResumeDocxGenerateRequest,
    ResumeDocxGenerateResponse,
    StageStatus,
)
from core.config import settings
from core.errors import (
    ContentGenerationError,
    DomainError,
    FileSaveError,
    MigrationRequiredError,
    NoMatchedExperienceError,
    ProfileIncompleteError,
    ResumeBuildError,
)
from database import models
from database.models import SchemaVersion
from database.migrations import (
    SCHEMA_VERSION_FACT_MIGRATION,
    SCHEMA_VERSION_FACT_SCHEMA,
)
from models.resume_document import ResumeDocument
from services import (
    constrained_rewrite,
    embedding_service,
    experience_service,
    jd_analyzer,
    layout_optimizer,
    resume_builder,
    selection_service,
    template_renderer,
)

logger = logging.getLogger(__name__)

OUTPUT_DIR = settings.DOCX_OUTPUT_DIR
# V1.4：BASE_DIR 已在 Settings 中显式暴露；保留字符串形式的 BACKEND_ROOT 供 TemplateRenderer 形参消费
BACKEND_ROOT = str(settings.BASE_DIR)

# V1.5.0：迁移版本常量（与 database.migrations 一致）
_REQUIRED_MIGRATIONS = (SCHEMA_VERSION_FACT_SCHEMA, SCHEMA_VERSION_FACT_MIGRATION)


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
    """PLAN §4.1：target_position 缺失时使用 JDAnalysis.position。"""
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


def _ensure_migrations_applied(db: Session) -> dict:
    """V1.5.0：迁移前置检查（PLAN §6.3 / §8.2）。

    生成链路要求 facts / schema_versions / fact_embeddings 表均已就绪。
    任一未应用 → 抛 MigrationRequiredError（生成阻断，由用户显式运行迁移）。
    """
    applied = {row.version for row in db.query(SchemaVersion).all()}
    missing = [v for v in _REQUIRED_MIGRATIONS if v not in applied]
    if missing:
        raise MigrationRequiredError(
            f"V1.5.0 迁移未完成，生成阻断：missing={missing} applied={sorted(applied)}",
            stage="migration_check",
            details={"missing": missing, "applied": sorted(applied)},
        )
    return {"applied": sorted(applied)}


def generate_docx(
    db: Session,
    req: ResumeDocxGenerateRequest,
) -> ResumeDocxGenerateResponse:
    """V1.5.0 核心链路（PLAN §2 / §7 T6）。

    阶段：迁移检查 → JD 分析 → 第一层选材 → 第二层事实选材 → 受约束改写
          → Builder 收缩装配 → 渲染 → 排版 → 保存 DOCX。
    所有关键阶段抛 DomainError 子类，由 API 层统一映射。
    """
    user_id = req.user_id or settings.DEFAULT_USER_ID
    ctx = GenerationContext(user_id=user_id, template_id=req.template_id)

    # ── 1. 迁移检查（PLAN §6.3） ─────────────────────────────────
    t = ctx.start("migration_check")
    mig_stats = _ensure_migrations_applied(db)
    ctx.done("migration_check", t, note=json.dumps(mig_stats, ensure_ascii=False))

    # ── 2. JD 分析（strict） ────────────────────────────────────────
    t = ctx.start("jd_analysis")
    jd: JDAnalysisOut = jd_analyzer.analyze_jd(req.jd_text, strict=True)
    ctx.done("jd_analysis", t, note=f"position={jd.position!r}")

    # ── 3. Profile：target_position 兜底（JDAnalysis.position） ────
    profile_patched = _target_position_fallback(req.profile, jd)

    # ── 4. 拉取用户全部 Experience（V1.5.0：第一层选材基于全量） ──
    t = ctx.start("sql_readback")
    all_experiences: list[models.Experience] = experience_service.list_experiences(db, user_id)
    if not all_experiences:
        raise NoMatchedExperienceError(
            f"用户无任何经历，无法生成简历（user_id={user_id}）",
            stage="sql_readback",
        )
    ctx.done("sql_readback", t, note=f"total_experiences={len(all_experiences)}")

    # ── 5. 第一层选材：固定槽位规则 → CandidateExperienceSet ──────
    t = ctx.start("select_experiences")
    baseline = date.today()
    candidate_set = selection_service.select_experiences(
        all_experiences, jd.model_dump(), baseline_date=baseline,
    )
    matched_ids = candidate_set.selected_ids()
    ctx.matched_experience_ids = matched_ids
    ctx.done("select_experiences", t, note=(
        f"slots={len(candidate_set.slots)} excluded={len(candidate_set.excluded_ids)} "
        f"warnings={len(candidate_set.warnings)}"
    ))
    if candidate_set.warnings:
        ctx.warnings.extend(candidate_set.warnings[:5])  # 只前 5 条进 response warnings

    if not matched_ids:
        raise NoMatchedExperienceError(
            f"第一层未入选任何经历（user_id={user_id}, total={len(all_experiences)}）",
            stage="select_experiences",
        )

    # ── 6. 第二层选材：事实与表达侧重 → SelectedEvidenceSet ────────
    t = ctx.start("select_evidence")
    evidence_set = selection_service.select_evidence(
        db, candidate_set, jd.model_dump(),
    )
    ctx.done("select_evidence", t, note=(
        f"entries={len(evidence_set.entries)} "
        f"fact_refs={len(evidence_set.all_fact_refs())}"
    ))

    # ── 7. 受约束改写 → GeneratedResumeContentV15 ─────────────────
    t = ctx.start("content_generation")
    generated_v15, cg_warnings = constrained_rewrite.rewrite_with_evidence(
        db, candidate_set, evidence_set, jd.model_dump(),
    )
    ctx.warnings.extend(cg_warnings)
    ctx.done("content_generation", t, note=(
        f"v15_experiences={len(generated_v15.experiences)} warnings={len(cg_warnings)}"
    ))

    # ── 8. Builder 收缩装配（build_v15，PLAN §5.3 / T5） ─────────
    t = ctx.start("resume_build")
    request_profile_dict = _profile_to_dict(profile_patched)
    try:
        resume_doc: ResumeDocument
        build_meta: dict[str, Any]
        resume_doc, build_meta = resume_builder.build_v15(
            db,
            user_id=user_id,
            candidate_set=candidate_set,
            jd_analysis=jd,
            generated_content_v15=generated_v15,
            request_profile=request_profile_dict,
            all_experiences=all_experiences,
        )
    except ProfileIncompleteError:
        raise  # 保持原类型（已是 DomainError 子类）
    except DomainError:
        raise
    except Exception as e:
        logger.exception("ResumeBuilder V1.5 未知构建失败")
        raise ResumeBuildError(str(e), details={"error_type": type(e).__name__}) from e
    ctx.profile_source = build_meta.get("profile_source", "")
    ctx.warnings.extend([
        f"AI 优化条目: {len(build_meta.get('ai_covered_experience_ids', []))}",
        f"材料不足条目: {len(build_meta.get('insufficient_experience_ids', []))}",
    ])
    ctx.rendered_experience_ids = (
        [w.experience_id for w in resume_doc.work if w.experience_id]
        + [p.experience_id for p in resume_doc.projects if p.experience_id]
    )
    ctx.done("resume_build", t, note=json.dumps(build_meta.get("counts", {}), ensure_ascii=False))

    # ── 9. TemplateRenderer.render + LayoutOptimizer ───────────────
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

    # ── 10. 保存 DOCX ────────────────────────────────────────────────
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

    # ── 11. 组装响应 ────────────────────────────────────────────────
    counts = build_meta.get("counts", {}) or {}
    counts_obj = BuildCounts.model_validate(counts) if isinstance(counts, dict) else counts
    build_meta_obj = BuildMeta.model_validate(build_meta) if isinstance(build_meta, dict) else build_meta
    # V1.5.0：ai_unrecognized 不再来自 RAG mismatch，而是来自越界改写告警
    cg_unrecognized: list[str] = []
    for w in ctx.warnings:
        if "拒绝越界经历 experience_id=" in w:
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
