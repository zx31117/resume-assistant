"""V1.5.0 核心用例编排 ResumeGenerationService（旧 V1.3 RAG 链路已退出）。

V1.5.0 PLAN §2 / §5 / §7 T6：
  迁移检查 → JD 分析 → 第一层 select_experiences → 第二层 select_evidence
  → 受约束改写 rewrite_with_evidence → build_v15（Builder 收缩）
  → TemplateRenderer → LayoutOptimizer → 保存 DOCX。

不直接操作 Word XML（渲染器独立），不直接调 LLM/Embedding
（通过 jd_analyzer / constrained_rewrite / embedding_service 编排）。
"""
from __future__ import annotations

import hashlib
import logging
import os
import uuid
from datetime import date
from typing import Any, Optional

from sqlalchemy.orm import Session

from api.schemas import (
    BuildCounts,
    BuildMeta,
    DocPreviewEntry,
    DocPreviewSection,
    EvidenceFact,
    JDAnalysisOut,
    PreviewAnchor,
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
from core.operations import OperationType, Recording, ResourceType, tracker
from database import models
from database.models import Fact, SchemaVersion
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


def _stages_from_recording(recording: Recording) -> list[StageStatus]:
    """把统一后台阶段投影收束为响应 `stages`（PLAN §5.1 尾部一致性）。

    只取 COMPLETED / FAILED 事件（成功响应里均为 COMPLETED），
    阶段码、耗时与消息直接来自同一 operation_id 的后台记录，避免双轨漂移。
    """
    out: list[StageStatus] = []
    for ev in recording.stages():
        if ev["event_type"] not in ("COMPLETED", "FAILED"):
            continue
        out.append(StageStatus(
            stage=ev["stage_code"],
            status="done" if ev["event_type"] == "COMPLETED" else "failed",
            duration_ms=ev["elapsed_ms"],
            note=ev["message"] or None,
        ))
    return out


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


# ── V2.1.0 T6：内容预览 + 逐 bullet 事实依据（只读投影） ──────────────── #

def _build_doc_preview(resume_doc: ResumeDocument) -> list[DocPreviewSection]:
    """V2.1.0 T6：把最终 ResumeDocument 投影为内容预览 DTO 列表。

    纯只读：不修改 resume_doc；不调 LLM/DB；不编造任何字段。
    字段全部来自真实 ResumeDocument（profile / work / project / education /
    skills / awards），空 section 直接不输出。

    V2.1.0 R9：返回章节顺序与 pm_template v1.2 模板章节顺序对齐
    （personal→education→work→project→skills→awards），保证预览 JSON 与
    Word/PDF 渲染出的章节顺序一致（PLAN §14.2.A）。
    """
    # R9：模板（_build_templates.py）章节顺序映射；未知 section 保持靠后
    _SECTION_RANK = {
        "personal": 0, "education": 1, "work": 2,
        "project": 3, "skills": 4, "awards": 5,
    }
    sections: list[DocPreviewSection] = []

    # ── personal：profile 头部（不来自模板） ──
    profile = resume_doc.profile
    personal_bullets: list[str] = []
    if profile.target_position:
        personal_bullets.append(f"目标岗位：{profile.target_position}")
    if profile.location:
        personal_bullets.append(f"所在地：{profile.location}")
    if profile.summary:
        personal_bullets.append(f"自我评价：{profile.summary}")
    contact_subhead = " · ".join(
        x for x in [profile.phone, profile.email] if x
    )
    sections.append(DocPreviewSection(
        section="personal",
        title="个人信息",
        entries=[DocPreviewEntry(
            heading=profile.name or "（未署名）",
            subhead=contact_subhead,
            bullets=personal_bullets,
        )],
    ))

    # ── work：工作经历 ──
    if resume_doc.work:
        sec = DocPreviewSection(section="work", title="工作经历")
        for w in resume_doc.work:
            head = " · ".join(
                x for x in [w.company, w.role] if x
            ) or "工作经历"
            sub_parts: list[str] = []
            if w.start_time:
                sub_parts.append(f"{w.start_time} - {w.end_time or '至今'}")
            elif w.end_time:
                sub_parts.append(w.end_time)
            sec.entries.append(DocPreviewEntry(
                heading=head,
                subhead=" · ".join(sub_parts),
                bullets=list(w.bullets or []),
                experience_id=w.experience_id or None,
            ))
        sections.append(sec)

    # ── project：项目经历 ──
    if resume_doc.projects:
        sec = DocPreviewSection(section="project", title="项目经历")
        for p in resume_doc.projects:
            head = " · ".join(
                x for x in [p.name, p.role] if x
            ) or "项目"
            sub_parts: list[str] = []
            if p.start_time:
                sub_parts.append(f"{p.start_time} - {p.end_time or '至今'}")
            elif p.end_time:
                sub_parts.append(p.end_time)
            sec.entries.append(DocPreviewEntry(
                heading=head,
                subhead=" · ".join(sub_parts),
                bullets=list(p.bullets or []),
                experience_id=p.experience_id or None,
            ))
        sections.append(sec)

    # ── education：教育背景（formal + campus） ──
    if resume_doc.education:
        sec = DocPreviewSection(section="education", title="教育背景")
        for e in resume_doc.education:
            head = " · ".join(
                x for x in [e.school, e.major] if x
            ) or "教育"
            sub_parts: list[str] = []
            if e.start_time:
                sub_parts.append(f"{e.start_time} - {e.end_time or '至今'}")
            elif e.end_time:
                sub_parts.append(e.end_time)
            bullets = list(e.bullets or [])
            if e.description and not bullets:
                # formal education 通常没有 bullets；将 description 作为单条 bullet
                # 真实保留事实文本，不杜撰内容。
                bullets = [e.description]
            sec.entries.append(DocPreviewEntry(
                heading=head,
                subhead=" · ".join(sub_parts),
                bullets=bullets,
                experience_id=e.experience_id or None,
            ))
        sections.append(sec)

    # ── skills：技能分组 ──
    if resume_doc.skills:
        sec = DocPreviewSection(section="skills", title="技能")
        for g in resume_doc.skills:
            sec.entries.append(DocPreviewEntry(
                heading=g.category or "技能",
                subhead="",
                bullets=list(g.items or []),
            ))
        sections.append(sec)

    # ── awards：获奖 / 证书（扁平字符串） ──
    if resume_doc.awards:
        sections.append(DocPreviewSection(
            section="awards",
            title="获奖 / 证书",
            entries=[DocPreviewEntry(heading="", subhead="", bullets=list(resume_doc.awards))],
        ))

    return sorted(
        sections,
        key=lambda s: _SECTION_RANK.get(s.section, len(_SECTION_RANK)),
    )


def _build_evidence_map(
    db: Session,
    fact_ids: list[str],
) -> dict[str, list[EvidenceFact]]:
    """V2.1.0 T6：按 fact_id 从 Fact 表读取原文，按 experience_id 聚合。

    只读：仅 SELECT；不写库。空入参直接返回空 dict。
    reason 字段保持空字符串——本流水线不记录 per-fact 采用理由。
    """
    if not fact_ids:
        return {}
    seen: list[str] = []
    dedup: dict[str, None] = {}
    for fid in fact_ids:
        if fid and fid not in dedup:
            dedup[fid] = None
            seen.append(fid)
    if not seen:
        return {}
    rows = db.query(Fact).filter(Fact.fact_id.in_(seen)).all()
    out: dict[str, list[EvidenceFact]] = {}
    for f in rows:
        out.setdefault(f.experience_id or "", []).append(EvidenceFact(
            fact_id=f.fact_id,
            experience_id=f.experience_id,
            text=(f.text or "").strip(),
            reason="",
        ))
    return out


# ── V2.1.0 R15a：PDF artifact 身份与不可变落盘 ──────────────────── #

def _safe_artifact_id(artifact_id: str) -> str:
    """把 artifact 身份收敛为合法文件名字段；异常值一律回退新 UUID。"""
    if not artifact_id:
        return str(uuid.uuid4())
    clean = "".join(ch for ch in artifact_id if ch.isalnum() or ch in "-_")
    return clean or str(uuid.uuid4())


def write_pdf_artifact(pdf_bytes: bytes, user_id: str, template_id: str,
                       artifact_id: str) -> dict:
    """把 PDF 字节以不可变 artifact 身份写入 OUTPUT_DIR。

    命名含唯一身份（resume_<user>_<template>_<artifact_id>.pdf），同一 artifact_id
    只落一个文件、不原地覆盖；再次生成使用新 artifact_id → 新文件。
    返回 artifact 元数据：artifact_id / file_name / file_path / download_url /
    sha256（内容 SHA-256）/ size_bytes。
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_user_id = "".join(c for c in (user_id or "") if c.isalnum() or c in "-_") or "user"
    artifact_id = _safe_artifact_id(artifact_id)
    file_name = f"resume_{safe_user_id}_{template_id}_{artifact_id}.pdf"
    file_path_abs = os.path.join(OUTPUT_DIR, file_name)
    try:
        with open(file_path_abs, "wb") as f:
            f.write(pdf_bytes)
    except Exception as e:
        raise FileSaveError(f"PDF artifact 保存失败: {e}", details={"path": file_path_abs}) from e
    return {
        "artifact_id": artifact_id,
        "file_name": file_name,
        "file_path": f"output/{file_name}",
        "download_url": f"/api/template/download?path=output/{file_name}",
        "sha256": hashlib.sha256(pdf_bytes).hexdigest(),
        "size_bytes": len(pdf_bytes),
    }


def generate_docx(
    db: Session,
    req: ResumeDocxGenerateRequest,
    operation_id: Optional[str] = None,
) -> ResumeDocxGenerateResponse:
    """V1.5.0 核心链路（PLAN §2 / §7 T6）。

    阶段：迁移检查 → Embedding/索引就绪检查 → JD 分析 → SQL 回读 → 第一层选材
          → 第二层事实选材 → 受约束改写 → Builder 收缩装配 → 渲染+排版 → 保存 DOCX
          → 响应组装。
    V2.0.1（T2）：整条链路由统一 `tracker.operation` 记录真实阶段、资源类型与单调
    耗时（PLAN §5.1）；最终响应 `stages` 直接取自同一 operation_id 的后台投影。
    所有关键阶段抛 DomainError 子类，由 API 层统一映射。
    """
    user_id = req.user_id or settings.DEFAULT_USER_ID
    warnings: list[str] = []

    with tracker.operation(OperationType.GENERATE, operation_id=operation_id) as recording:
        # ── 1. 迁移检查（PLAN §6.3） ─────────────────────────────
        with recording.stage("migration_check", "迁移检查", ResourceType.LOCAL_DB) as s:
            mig_stats = _ensure_migrations_applied(db)
            s.counts(applied=len(mig_stats.get("applied", [])))

        # ── 2. Embedding/索引就绪检查（非阻断观测，PLAN §5.1） ──
        with recording.stage("embedding_ready", "Embedding/索引就绪检查", ResourceType.EMBEDDING) as s:
            emb = embedding_service.status_summary(db)
            s.counts(
                total=int(emb.get("total", 0)),
                valid=int(emb.get("VALID", 0)),
                pending=int(emb.get("PENDING", 0)),
                invalid=int(emb.get("INVALID", 0)),
                failed=int(emb.get("FAILED", 0)),
            )

        # ── 3. JD 分析（strict） ────────────────────────────────
        with recording.stage("jd_analysis", "JD 分析", ResourceType.LLM):
            jd: JDAnalysisOut = jd_analyzer.analyze_jd(req.jd_text, strict=True)

        # ── Profile：target_position 兜底（非阶段） ─────────────
        profile_patched = _target_position_fallback(req.profile, jd)

        # ── 4. SQL Experience 回读 ─────────────────────────────
        with recording.stage("sql_readback", "SQL Experience 回读", ResourceType.LOCAL_DB) as s:
            all_experiences: list[models.Experience] = experience_service.list_experiences(db, user_id)
            if not all_experiences:
                raise NoMatchedExperienceError(
                    f"用户无任何经历，无法生成简历（user_id={user_id}）",
                    stage="sql_readback",
                )
            s.counts(total=len(all_experiences))

        # ── 5. 第一层选材 ───────────────────────────────────────
        baseline = date.today()
        with recording.stage("select_experiences", "第一层 Experience 选择", ResourceType.LOCAL_CPU) as s:
            candidate_set = selection_service.select_experiences(
                all_experiences, jd.model_dump(), baseline_date=baseline,
            )
            matched_ids = candidate_set.selected_ids()
            s.counts(
                slots=len(candidate_set.slots),
                excluded=len(candidate_set.excluded_ids),
                warnings=len(candidate_set.warnings),
            )
        if candidate_set.warnings:
            warnings.extend(candidate_set.warnings[:5])  # 只前 5 条进 response warnings

        if not matched_ids:
            raise NoMatchedExperienceError(
                f"第一层未入选任何经历（user_id={user_id}, total={len(all_experiences)}）",
                stage="select_experiences",
            )

        # ── 6. 第二层事实选材 ───────────────────────────────────
        with recording.stage("select_evidence", "第二层 Fact 证据选择", ResourceType.EMBEDDING) as s:
            evidence_set = selection_service.select_evidence(db, candidate_set, jd.model_dump())
            s.counts(entries=len(evidence_set.entries), fact_refs=len(evidence_set.all_fact_refs()))

        # ── 7. 受约束改写 ───────────────────────────────────────
        with recording.stage("content_generation", "LLM 受约束改写", ResourceType.LLM) as s:
            generated_v15, cg_warnings = constrained_rewrite.rewrite_with_evidence(
                db, candidate_set, evidence_set, jd.model_dump(),
            )
            s.counts(experiences=len(generated_v15.experiences), warnings=len(cg_warnings))
        warnings.extend(cg_warnings)

        # ── 8. Builder 收缩装配 ─────────────────────────────────
        request_profile_dict = _profile_to_dict(profile_patched)
        with recording.stage("resume_build", "ResumeDocument 构建与来源校验", ResourceType.LOCAL_CPU) as s:
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
            bcounts = build_meta.get("counts", {}) or {}
            if isinstance(bcounts, dict):
                s.counts(**{k: int(v) for k, v in bcounts.items() if isinstance(v, (int, float))})
        profile_source = build_meta.get("profile_source", "")
        warnings.extend([
            f"AI 优化条目: {len(build_meta.get('ai_covered_experience_ids', []))}",
            f"材料不足条目: {len(build_meta.get('insufficient_experience_ids', []))}",
        ])
        rendered_ids = (
            [w.experience_id for w in resume_doc.work if w.experience_id]
            + [p.experience_id for p in resume_doc.projects if p.experience_id]
        )

        # ── 9. 渲染 + 排版 ─────────────────────────────────────
        with recording.stage("render", "DOCX 渲染与版式处理", ResourceType.LOCAL_CPU) as s:
            renderer = template_renderer.TemplateRenderer(req.template_id, backend_root=str(BACKEND_ROOT))
            doc, render_warnings, render_stats_raw = renderer.render(resume_doc)
            warnings.extend(render_warnings)
            page_limit = renderer.spec.layout.page_limit
            applied_layout_rules, capacity_warnings = layout_optimizer.optimize(doc, page_limit=page_limit)
            final_page_count = layout_optimizer.estimate_pages(doc)
            if applied_layout_rules:
                warnings.append(f"排版规则: {len(applied_layout_rules)} 条")
            if capacity_warnings:
                warnings.extend(capacity_warnings)
            render_stats = RenderStats(
                sections=render_stats_raw.get("sections", []),
                unreplaced_placeholders=render_stats_raw.get("unreplaced_placeholders", []),
                capacity_warnings=list(capacity_warnings),
            )
            s.counts(
                pages=int(final_page_count),
                warnings=len(render_warnings) + len(capacity_warnings),
            )

        # ── 10. 保存 DOCX ──────────────────────────────────────
        with recording.stage("save_docx", "输出文件保存", ResourceType.LOCAL_FILE):
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            safe_user_id = "".join(c for c in user_id if c.isalnum() or c in "-_") or "user"
            file_name = f"resume_{safe_user_id}_{req.template_id}.docx"
            file_path_abs = os.path.join(OUTPUT_DIR, file_name)
            try:
                doc.save(file_path_abs)
            except Exception as e:
                raise FileSaveError(f"DOCX 保存失败: {e}", details={"path": file_path_abs}) from e
            # V2.1.0 R9：同一 resume_doc 产出真实 PDF（同目录）。
            # V2.1.0 R15a：PDF 按不可变 artifact 身份命名，响应携带 artifact 元数据与 anchors。
            # PDF 渲染/保存失败不中断 DOCX 主链：响应 pdf_* 字段留空 + warning，
            # 下载 PDF 时由 download 端点返回真实 4xx/5xx，绝不假装成功。
            pdf_file_name: Optional[str] = None
            pdf_download_url: Optional[str] = None
            pdf_artifact_id: Optional[str] = None
            pdf_sha256: Optional[str] = None
            pdf_size_bytes: Optional[int] = None
            pdf_anchors: Optional[list[PreviewAnchor]] = None
            try:
                from services import pdf_renderer  # lazy：reportlab 缺失不阻塞 docx 链路
                pdf_artifact_id = recording.operation_id or str(uuid.uuid4())
                pdf_bytes, pdf_render_warnings, pdf_anchor_dicts = pdf_renderer.render(
                    resume_doc, req.template_id, str(BACKEND_ROOT),
                    artifact_id=pdf_artifact_id,
                    bullet_fact_refs=build_meta.get("bullet_fact_refs") or None,
                )
                for _w_pdf in pdf_render_warnings:
                    warnings.append(f"PDF: {_w_pdf}")
                pdf_meta = write_pdf_artifact(
                    pdf_bytes, user_id=safe_user_id,
                    template_id=req.template_id, artifact_id=pdf_artifact_id,
                )
                pdf_file_name = pdf_meta["file_name"]
                pdf_download_url = pdf_meta["download_url"]
                pdf_sha256 = pdf_meta["sha256"]
                pdf_size_bytes = pdf_meta["size_bytes"]
                pdf_anchors = [PreviewAnchor(**a) for a in pdf_anchor_dicts]
            except Exception as _e_pdf:  # noqa: BLE001 —— 真实失败状态由响应字段 + warning 表达
                logger.warning("PDF 渲染/保存失败（不影响 DOCX）: %s", _e_pdf)
                warnings.append(f"PDF 生成失败（可下载 Word；PDF 不可用）: {type(_e_pdf).__name__}: {_e_pdf}")
        download_url = f"/api/template/download?path=output/{file_name}"

        # ── 11. 组装响应 ───────────────────────────────────────
        with recording.stage("response_assembly", "响应组装与下载就绪", ResourceType.LOCAL_CPU):
            counts = build_meta.get("counts", {}) or {}
            counts_obj = BuildCounts.model_validate(counts) if isinstance(counts, dict) else counts
            build_meta_obj = BuildMeta.model_validate(build_meta) if isinstance(build_meta, dict) else build_meta
            # V1.5.0：ai_unrecognized 不再来自 RAG mismatch，而是来自越界改写告警
            cg_unrecognized: list[str] = []
            for w in warnings:
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

            # V2.1.0 T6：内容预览 + 逐 bullet 事实依据（只读投影，不改 builder/renderer/selection/rewrite）
            doc_preview = _build_doc_preview(resume_doc)
            # 取真实 selection_reason（per-experience 来自 EvidenceEntry；evidence_set 在作用域内）
            selection_reason_by_exp: dict[str, str] = {}
            if evidence_set is not None:
                for _entry in evidence_set.entries:
                    if _entry.selection_reason and _entry.experience_id:
                        selection_reason_by_exp[_entry.experience_id] = _entry.selection_reason
            for _sec in doc_preview:
                for _ent in _sec.entries:
                    if _ent.experience_id and _ent.experience_id in selection_reason_by_exp:
                        _ent.selection_reason = selection_reason_by_exp[_ent.experience_id]
            # 收集 doc_preview 涉及到的全部 experience_id，按 build_meta.fact_refs_per_experience 找 fact_id
            _exp_ids = {
                _ent.experience_id
                for _sec in doc_preview
                for _ent in _sec.entries
                if _ent.experience_id
            }
            _fact_ids: list[str] = []
            for _eid in _exp_ids:
                for _fid in (build_meta.get("fact_refs_per_experience") or {}).get(_eid, []) or []:
                    if _fid:
                        _fact_ids.append(_fid)
            evidence_map = _build_evidence_map(db, _fact_ids)

        return ResumeDocxGenerateResponse(
            operation_id=recording.operation_id,
            file_path=f"output/{file_name}",
            file_name=file_name,
            download_url=download_url,
            pdf_file_name=pdf_file_name,
            pdf_download_url=pdf_download_url,
            pdf_artifact_id=pdf_artifact_id,
            pdf_sha256=pdf_sha256,
            pdf_size_bytes=pdf_size_bytes,
            pdf_anchors=pdf_anchors,
            stages=_stages_from_recording(recording),
            matched_experience_ids=matched_ids,
            rendered_experience_ids=rendered_ids,
            profile_source=profile_source,
            page_count=final_page_count,
            warnings=warnings,
            build_counts=counts_obj,
            build_meta=build_meta_obj,
            render_stats=render_stats,
            template_id=req.template_id,
            doc_preview=doc_preview,
            evidence=evidence_map,
        )
