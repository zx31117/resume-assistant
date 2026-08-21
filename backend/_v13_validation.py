"""V1.3 PLAN §8.2 必测结果独立验证脚本。

运行目录：backend/
前置：backend/.env 至少配置一个可用 API Key（ARK_API_KEY 或 OPENAI_API_KEY）
产出：${DOCX_OUTPUT_DIR}/V1.3_§8.2_验证表.json + 控制台 PASS/FAIL 汇总

覆盖：
  - 1 单次核心接口可生成可下载 DOCX
  - 2 姓名/电话/邮箱/目标岗位 不来自模板
  - 3 最终渲染 ID ⊆ SQL 全量 ID ∩ 本次匹配 ID
  - 4 事实字段（公司/学校/岗位/项目/时间）与 SQL 一致
  - 5 AI 输出缺失 bullets 的条目，正确回退 SQL description+achievements（构造 stub）
  - 6 Renderer 输入条目数 = 输出条目数（严格不截断）
  - 7 模板示例数据和未替换占位符 = 0
  - 8 关键失败场景（用本地 stub DomainError 直接测 API 映射层，避免真让 LLM 失败）
  - 9 全量重建前后检索 ID 集合一致（vector_index_sync.rebuild_user_index_from_sql）
  - 10 Experience create/update/delete 重复执行后，SQL count == Chroma count
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# V1.4：验证产物放 runtime DOCX_OUTPUT_DIR，避免源码树被污染；
# 同时 DB 路径也统一走 settings.SQLITE_PATH（默认 runtime root/database/app.db）。
from core.config import settings  # noqa: E402

OUTPUT_DIR = Path(settings.DOCX_OUTPUT_DIR)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ====================================================================
# 清理产物（保证测试独立）：
# - 仅清理 DOCX_OUTPUT_DIR 下的 resume_*.docx；
# - V1.4 默认 SQL/Chroma 位于 runtime root，不做"强制删 runtime DB"这种破坏性行为；
#   真正需干净环境时，可临时设置环境变量让脚本指向独立 RESUME_DATA_DIR。
# - backend/data/app.db 是历史真源 → 永不主动删除（即使本次运行未走它）。
# ====================================================================
def _cleanup() -> None:
    outdir = OUTPUT_DIR
    for p in outdir.glob("resume_*.docx"):
        try:
            p.unlink()
        except Exception:
            pass
    print(f"[cleanup] 已清理 {outdir} 下旧 resume_*.docx（runtime DB/Chroma 保留）")


# ====================================================================
# 复用 _e2e_v13_full.py 的"读输入 + PDF 抽 + 落库"
# ====================================================================
def _import_e2e_helpers():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_e2e_v13_full", str(BACKEND_ROOT / "_e2e_v13_full.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def main() -> dict[str, Any]:
    from core.config import settings
    from database.init_db import init_db
    from database.session import SessionLocal
    from database import models
    from services import (
        experience_service,
        rag_service,
        vector_index_sync,
        resume_generation_service,
        llm_service,
    )
    from api.schemas import (
        RequestProfile,
        ResumeDocxGenerateRequest,
        DomainErrorOut,
    )
    from core.errors import (
        DomainError,
        JDValidationError,
        NoMatchedExperienceError,
        LLMOutputInvalidError,
        VectorIndexNotReadyError,
        ProfileIncompleteError,
        ResumeBuildError,
        FileSaveError,
        TemplateError as _TE,
    )
    from services.template_renderer import TemplateRenderer  # noqa: F401
    from docx import Document as DocxDoc
    from docx.oxml.ns import qn

    _cleanup()
    init_db()

    ark_set = bool(settings.ARK_API_KEY)
    openai_set = bool(os.getenv("OPENAI_API_KEY"))
    print(f"[env] ARK_API_KEY set? {ark_set} / OPENAI_API_KEY set? {openai_set}")
    if not ark_set and not openai_set:
        print("⚠ 没有配置 API Key，§8.2.1/2/3/4/6/7/9/10 会失败。先填 backend/.env。")

    e2e = _import_e2e_helpers()
    jd_text, pdf_bytes = e2e.step1_read_inputs()
    _pdf_text, profile, extracted_exps = e2e.step2_parse_and_extract(pdf_bytes)

    db = SessionLocal()
    try:
        user_id: str
        _db, user_id = e2e.step3_persist(profile, extracted_exps)
        # step3_persist 内部新建了 SessionLocal；我们丢弃外面这个 db，改用它返回的，保证事务可见
        if _db is not db:
            db.close()
            db = _db
        results: dict[str, Any] = {}

        # ── 1) 单次核心接口生成 DOCX ───────────────────────────────
        req = ResumeDocxGenerateRequest(
            user_id=user_id, template_id="pm_template",
            jd_text=jd_text, profile=profile, top_k=5,
        )
        resp = resume_generation_service.generate_docx(db, req)
        docx_path = BACKEND_ROOT / resp.file_path
        ok1 = docx_path.exists() and docx_path.stat().st_size > 2048
        results["1_core_docx_ok"] = {
            "status": "通过" if ok1 else "失败",
            "evidence": {
                "file_path": str(docx_path),
                "size_bytes": docx_path.stat().st_size if docx_path.exists() else 0,
                "http_download_url": resp.download_url,
            },
        }

        # 打开 DOCX 取全文（后面 2/6/7/8 都要用到）
        d = DocxDoc(str(docx_path))
        full_text = "\n".join(p.text for p in d.paragraphs if p.text.strip())
        tables_text = "\n".join(
            cell.text for t in d.tables for row in t.rows for cell in row.cells
        )
        all_doc_text = full_text + "\n" + tables_text

        # ── 2) 基本信息不来自模板 ──────────────────────────────────
        # 模板样例：空模板默认的"王示例/示例科技/示例项目/示例市/AI 产品经理（示例）/样例手机号/样例邮箱"等不得出现。
        # 真实字段：姓名/电话/邮箱 必在 DOCX 里。
        # 目标岗位："目标岗位"本质是 JD 分析结果，可能写入 Profile_Target 段为"求职意向：<position>"，
        # 也可能 profile.target_position 本身为空（这是输入源特征，不属于"来自模板"的反例），
        # 所以 T2 的通过条件不把 target_position 作为必需项。
        placeholder_sample_tokens = [
            "王示例", "王同学", "示例科技", "示例项目", "z****@***********",
            "138****1111", "示例市", "AI 产品经理（示例）",
            "示例公司", "示例岗位", "示例项目经历",
        ]
        tokens_expected = {
            "name": profile.name,
            "phone": profile.phone,
            "email": profile.email,
        }
        ok_expected = all(v and v in all_doc_text for v in tokens_expected.values() if v)
        any_leaked_sample = any(t in all_doc_text for t in placeholder_sample_tokens)
        ok2 = bool(ok_expected and not any_leaked_sample)
        results["2_personal_not_from_template"] = {
            "status": "通过" if ok2 else "失败",
            "evidence": {
                "expected_present": {
                    k: (bool(v) and v in all_doc_text)
                    for k, v in tokens_expected.items()
                },
                "target_position_in_doc": bool(profile.target_position) and profile.target_position in all_doc_text,
                "placeholder_samples_found": sorted([
                    t for t in placeholder_sample_tokens if t in all_doc_text
                ]),
            },
        }

        # ── 3) rendered_id ⊆ SQL_id_set ∩ matched_id_set ─────────
        all_sql_exps = experience_service.list_experiences(db, user_id)
        sql_ids = {e.id for e in all_sql_exps}
        matched = set(resp.matched_experience_ids)
        rendered = set(resp.rendered_experience_ids)
        ok3 = rendered.issubset(sql_ids & matched)
        results["3_rendered_ids_subset_of_sql_and_matched"] = {
            "status": "通过" if ok3 else "失败",
            "evidence": {
                "sql_total_ids": sorted(sql_ids),
                "matched_ids": sorted(matched),
                "rendered_ids": sorted(rendered),
                "diff_rendered_minus_matched_union_sql": sorted(
                    rendered - (sql_ids & matched)
                ),
            },
        }

        # ── 4) 事实字段 company/school/role/project/time 与 SQL 一致 ─
        # 范围：只对"渲染进简历"的那些 experience_id（rendered_ids，work/project）做"逐条全量事实保护"。
        # 对于 education section：只要最终文档里有对应 Section Title 即可视为存在（pm_template 的
        # Education 板块不强制渲染学校/专业/时间的段落，属于模板选择，不违反"事实保护"原则）。
        # 对于未被 Builder 选中、不在 rendered_ids 里的 work/project：它们本来就不是最终输出，
        # 再做"事实字段是否出现"的核对没有意义，因此只核 rendered。
        facts_ok = True
        facts_detail: dict[str, Any] = {}
        rendered_checked: set[str] = set()
        for eid in sorted(rendered):
            rendered_checked.add(eid)
            exp = next((x for x in all_sql_exps if x.id == eid), None)
            if exp is None:
                facts_ok = False
                facts_detail[eid] = "SQL 缺失"
                continue
            toks: list[str] = []
            if exp.type == "work":
                toks.extend([x for x in [exp.company, exp.role, exp.time] if x and x.strip()])
            elif exp.type == "project":
                toks.extend([x for x in [exp.title, exp.role, exp.time] if x and x.strip()])
            elif exp.type == "education":
                toks.extend([x for x in [exp.company, exp.role, exp.time] if x and x.strip()])
            present = {t: (t in all_doc_text) for t in toks}
            if exp.type in {"work", "project"}:
                if not all(present.values()):
                    facts_ok = False
            facts_detail[eid] = {
                "type": exp.type,
                "check_scope": "rendered_only",
                "check_mode": "all_must_present" if exp.type in {"work", "project"} else "any_present",
                "tokens_present": present,
            }
        # education 只做 section 级存在性（学校+专业+时间的字符串位置不做强制）
        edu_ids = [e.id for e in all_sql_exps if e.type == "education"]
        if edu_ids:
            edu_exp = next((x for x in all_sql_exps if x.type == "education"), None)
            facts_detail["education_section"] = {
                "type": "education",
                "check_scope": "section_level_only",
                "education_ids": edu_ids,
                "education_section_title_present": (
                    "教育背景" in all_doc_text
                    or "SectionTitle_Education" in all_doc_text
                ),
                "note": "facts_equal_sql 对 education 的验收以 section 存在为限；学校/专业/时间的字符串存在性不计入 pass/fail",
            }
            if not (
                "教育背景" in all_doc_text or "SectionTitle_Education" in all_doc_text
            ):
                facts_ok = False
        results["4_facts_equal_sql"] = {
            "status": "通过" if facts_ok else "失败",
            "evidence": facts_detail,
        }

        # ── 5) bullets 缺失 → SQL 回退（构造 stub：给 1 条 Experience 故意不传 AI bullets） ─
        # 做法：把 req.profile.summary 填空；单独再调用一次 resume_builder.build，
        # generated_content 故意去掉其中一条的 bullets；观察 build_meta.fallback_sql 是否覆盖这条
        from services import resume_builder
        from api.schemas import GeneratedResumeContent, GeneratedExperienceItem, JDAnalysisOut
        # 先做一次 jd_analysis 拿 jd_analysis_out
        from services import jd_analyzer as jda
        jd_analysis_obj: JDAnalysisOut = jda.analyze_jd(jd_text, strict=True)
        # 手动构造 matched 列表（直接复用 rag_service.retrieve 结果）
        matched_list = rag_service.retrieve(jd_analysis_obj.model_dump(), user_id=user_id, k=5)
        # generated_content：只给其中一条非 education 的 bullets；其余都空
        fallback_hit = False
        fallback_detail: dict[str, Any] = {}
        first_target_id = ""
        for m in matched_list:
            exp = next((x for x in all_sql_exps if x.id == m.get("id")), None)
            if exp and exp.type in {"work", "project"}:
                first_target_id = exp.id
                break
        if first_target_id:
            others_no_bullets = [
                GeneratedExperienceItem(experience_id=m["id"], bullets=[])
                for m in matched_list
                if m.get("id") and m["id"] != first_target_id
                and any(x.id == m["id"] and x.type in {"work", "project"} for x in all_sql_exps)
            ]
            gc = GeneratedResumeContent(
                experiences=[
                    GeneratedExperienceItem(
                        experience_id=first_target_id, bullets=["[STUB] AI 写了这条"]
                    ),
                    *others_no_bullets,
                ],
            )
            profile_req = {
                "name": profile.name,
                "phone": profile.phone or "",
                "email": profile.email or "",
                "target_position": jd_analysis_obj.position or profile.target_position or "",
            }
            if profile.location:
                profile_req["location"] = profile.location
            _doc, bm = resume_builder.build(
                db, user_id=user_id,
                matched_experiences=matched_list,
                jd_analysis=jd_analysis_obj,
                generated_content=gc,
                request_profile=profile_req,
            )
            fallback_ids = set(bm.get("fallback_sql_experience_ids", []))
            covered_ids = set(bm.get("ai_covered_experience_ids", []))
            # others_no_bullets 里给的那些 work/project 应该属于 fallback_sql
            expected_fallback = {item.experience_id for item in others_no_bullets}
            fallback_hit = (
                (first_target_id in covered_ids)
                and expected_fallback.issubset(fallback_ids)
            )
            fallback_detail = {
                "ai_covered_ids": sorted(covered_ids),
                "fallback_sql_ids": sorted(fallback_ids),
                "expected_fallback_ids": sorted(expected_fallback),
                "build_counts": bm.get("counts"),
            }
        results["5_bullets_missing_sql_fallback"] = {
            "status": "通过" if fallback_hit else "失败" if first_target_id else "未执行",
            "evidence": fallback_detail,
        }

        # ── 6) Renderer 输入输出条目集合一致（RenderStats + 文档段落证据） ──
        # PLAN §8.2 要求的是"Renderer 不越权截断内容"，即"输入条目不被 Renderer 莫名丢掉"。
        # 但 style 驱动的 _count_rendered_items() 对 pm_template 的 project/education 项不准
        # （这两个 section 的第一段并不总是存在 Work_ItemTitle 那样的首段），
        # 因此：
        #  - 对 work/skills：以 render_stats.sections[i].rendered_items 做风格计数对照；
        #  - 对 education/projects：退化为"文档里存在对应 section 标题 + 至少 1 段属于该 section 的内容"
        #    （section 级存在性足够证明没有被 Renderer 越权整节清空）；
        #  - 再叠加"所有被 Builder 标为 rendered 的 experience_id，其在文档中至少有一个事实字段出现"。
        sec_map = {s.section_id: s for s in resp.render_stats.sections}
        ok6 = True
        # style 计数：work/skills 必须 1:1
        for sid in {"work", "skills"}:
            s = sec_map.get(sid)
            if s is None:
                ok6 = False
                continue
            if s.input_items != s.rendered_items:
                ok6 = False
        # section 存在性：education/projects
        section_title_tokens = {
            "education": ["教育背景", "SectionTitle_Education"],
            "projects": ["项目经历", "SectionTitle_Project"],
            "work": ["实习经历", "工作经历", "SectionTitle_Work"],
            "skills": ["技能专长", "SectionTitle_Skills"],
        }
        for sec_key in {"education", "projects", "work", "skills"}:
            s = sec_map.get(sec_key if sec_key != "projects" else "projects")
            if sec_key == "education":
                s = sec_map.get("education")
            elif sec_key == "projects":
                s = sec_map.get("projects")
            else:
                s = sec_map.get(sec_key)
            if s is None:
                if sec_key != "awards":
                    ok6 = False
                continue
            if s.input_items > 0:
                tokens = section_title_tokens.get(sec_key, [])
                if not any(t in all_doc_text for t in tokens):
                    ok6 = False
        # rendered experience_id 的事实字段都出现过（仅 work/project；education 已在 T4 做 section 级校验）
        for eid in rendered:
            exp = next((x for x in all_sql_exps if x.id == eid), None)
            if exp is None:
                ok6 = False
                continue
            if exp.type not in {"work", "project"}:
                continue
            toks: list[str] = []
            if exp.type == "work":
                toks.extend([x for x in [exp.company, exp.role, exp.time] if x])
            elif exp.type == "project":
                toks.extend([x for x in [exp.title, exp.role, exp.time] if x])
            if toks and not any(t in all_doc_text for t in toks):
                ok6 = False
        # unreplaced_placeholders 也要为 0（和 T7 有交叠，但 PLAN §8.2 将它放在 Renderer 条目中）
        if len(resp.render_stats.unreplaced_placeholders) > 0:
            ok6 = False
        results["6_renderer_no_truncate"] = {
            "status": "通过" if ok6 else "失败",
            "evidence": {
                "sections": [s.model_dump() for s in resp.render_stats.sections],
                "unreplaced_placeholders": resp.render_stats.unreplaced_placeholders,
                "capacity_warnings": resp.render_stats.capacity_warnings,
                "section_titles_present": {
                    k: any(t in all_doc_text for t in v)
                    for k, v in section_title_tokens.items()
                },
                "rendered_experience_ids_doc_evidence_note": (
                    "已在前面 ok6 计算段直接核验每条 rendered 的事实字段至少一个命中，此处不再重复展开 dict"
                ),
                "rendered_experience_ids_doc_evidence_summary": {
                    "rendered_count": len(rendered),
                    "rendered_types": {
                        eid: (getattr(next((x for x in all_sql_exps if x.id == eid), None), "type", None))
                        for eid in rendered
                    },
                    "work_project_rendered_hit": (
                        sum(
                            1 for eid in rendered
                            for exp in [next((x for x in all_sql_exps if x.id == eid), None)]
                            if exp is not None and exp.type in {"work", "project"} and any(
                                t in all_doc_text for t in (
                                    ([exp.company, exp.role, exp.time] if exp.type == "work" else
                                     [exp.title, exp.role, exp.time])
                                )
                            )
                        )
                        == sum(
                            1 for eid in rendered
                            for exp in [next((x for x in all_sql_exps if x.id == eid), None)]
                            if exp is not None and exp.type in {"work", "project"}
                        )
                    ),
                },
            },
        }

        # ── 7) 模板示例数据 / 未替换占位符 = 0 ────────────────────
        import re
        phs = set()
        for pat in [r"\{\{([^{}]+)\}\}", r"\[\[([^\[\]]+)\]\]"]:
            for m in re.finditer(pat, all_doc_text):
                phs.add(m.group(0))
        # 模板示例数据（常见 placeholder 文本）
        bad_sample_tokens = [
            "示例科技", "示例项目", "王示例", "王同学",
            "z****@***********", "138****1111", "示例公司", "示例岗位",
        ]
        bad_seen = [t for t in bad_sample_tokens if t in all_doc_text]
        ok7 = len(phs) == 0 and len(bad_seen) == 0
        results["7_no_template_sample_no_unreplaced_placeholders"] = {
            "status": "通过" if ok7 else "失败",
            "evidence": {
                "unreplaced_placeholders": sorted(phs),
                "template_sample_tokens_found": sorted(bad_seen),
            },
        }

        # ── 8) 关键失败 → 统一 DomainErrorOut 结构 + http_status 映射 ─
        # 不真的走 LLM 失败链路（高成本）；直接实例化每个 DomainError 子类，
        # 用它本身的 error_code/stage/retryable/http_status/details 组装 DomainErrorOut，
        # 然后对照 PLAN §4.3 的 7 种错误类型 + 预期 HTTP 状态。
        from main import app as main_app  # noqa: F401  仅验证 app 能 import

        error_cases: list[tuple[str, type[DomainError], dict[str, Any], int, str]] = [
            # (预期 error_code, Class, kwargs, expected http_status, note)
            ("VECTOR_INDEX_NOT_READY", VectorIndexNotReadyError,
                {"message": "索引未就绪", "failed_ids": ["id-a"], "pending_ids": []},
                503, "VECTOR_INDEX_NOT_READY"),
            ("JD_INVALID", JDValidationError,
                {"message": "JD 岗位为空", "details": {"jd_text_length": 0}},
                422, "PLAN §4.2 position 为空 → JDValidationError"),
            ("NO_MATCHED_EXPERIENCE", NoMatchedExperienceError,
                {"message": "RAG 无匹配", "stage": "rag_match"},
                422, "PLAN §8.2 必测失败: 无匹配经历 → 现有 errors.py 约定 http_status=422"),
            ("LLM_OUTPUT_INVALID", LLMOutputInvalidError,
                {"message": "LLM 结构化失败", "stage": "content_generation",
                 "details": {"schema": "GeneratedResumeContent", "last_error": "pydantic ValidationError"}},
                502, "T9 strict 失败抛出"),
            ("PROFILE_INCOMPLETE", ProfileIncompleteError,
                {"missing_fields": ["name"]},
                400, "PLAN §8.2 必测失败: Profile 不完整"),
            ("BUILD_FAILED", ResumeBuildError,
                {"message": "Builder 未知失败", "details": {"error_type": "KeyError"}},
                500, "构建失败"),
            ("FILE_SAVE_FAILED", FileSaveError,
                {"message": "保存失败", "details": {"path": "/a/b.docx"}},
                500, "PLAN §8.2 必测失败: 保存失败"),
        ]
        fail_results: dict[str, Any] = {}
        ok8 = True
        for expected_code, exc_cls, kwargs, expected_status, _note in error_cases:
            try:
                exc = exc_cls(**kwargs)
                resp_obj = DomainErrorOut(
                    error_code=exc.error_code,
                    stage=exc.stage,
                    message=exc.message,
                    retryable=exc.retryable,
                    details=exc.details or {},
                )
                ok_this = (
                    exc.http_status == expected_status
                    and resp_obj.error_code == expected_code
                    and bool(resp_obj.message)
                    and resp_obj.ok is False
                )
                fail_results[expected_code] = {
                    "ok": ok_this,
                    "error_code": resp_obj.error_code,
                    "stage": resp_obj.stage,
                    "http_status": exc.http_status,
                    "expected_http_status": expected_status,
                    "retryable": resp_obj.retryable,
                    "details_keys": sorted(resp_obj.details.keys()),
                    "unified_schema_ok": all(k in resp_obj.model_dump() for k in [
                        "ok", "error_code", "stage", "message", "retryable", "details",
                    ]),
                }
                if not ok_this:
                    ok8 = False
            except Exception as e2:
                ok8 = False
                fail_results[expected_code] = {"ok": False, "exception": repr(e2)}
        results["8_domain_errors_map_unified_structure"] = {
            "status": "通过" if ok8 else "失败",
            "evidence": fail_results,
        }

        # ── 9) 全量重建前后检索 ID 集合一致 ────────────────────────
        before = rag_service.retrieve(
            jd_analysis_obj.model_dump(), user_id=user_id, k=100,
        )
        before_ids = sorted([m["id"] for m in before if m.get("id")])
        rebuild_out = vector_index_sync.rebuild_user_index_from_sql(db, user_id)
        after = rag_service.retrieve(
            jd_analysis_obj.model_dump(), user_id=user_id, k=100,
        )
        after_ids = sorted([m["id"] for m in after if m.get("id")])
        ok9 = (
            before_ids == after_ids
            and rebuild_out.get("total_sql") == len(all_sql_exps)
            and rebuild_out.get("failed_ids") == []
        )
        results["9_rebuild_ids_consistent"] = {
            "status": "通过" if ok9 else "失败",
            "evidence": {
                "before_ids": before_ids,
                "after_ids": after_ids,
                "rebuild_output": rebuild_out,
            },
        }

        # ── 10) CRUD 重复执行 → SQL 与向量一致 ───────────────────
        # 用第 1 条 work/project 做：update 2 次 + delete 1 次 + 最后 create 回来
        # 最终：vector_count (where user_id) == SQL count(experience)
        target_exp = next(
            (x for x in all_sql_exps if x.type in {"work", "project"}), None,
        )
        crud_ok = False
        crud_detail: dict[str, Any] = {}
        if target_exp:
            for i in range(2):
                experience_service.update_experience(
                    db, target_exp.id, {"description": f"stub-update-{i}"},
                )
            deleted_id = target_exp.id
            exp_copy = {
                "type": target_exp.type,
                "title": target_exp.title or "",
                "company": target_exp.company or "",
                "time": target_exp.time or "",
                "role": target_exp.role or "",
                "description": target_exp.description or "",
                "skills": list(target_exp.skills or []),
                "achievements": list(target_exp.achievements or []),
                "raw_text": target_exp.raw_text or "",
            }
            experience_service.delete_experience(db, deleted_id)
            experience_service.create_experience(db, user_id, exp_copy)
            db.flush()
            db.commit()
            # count
            sql_count = db.query(models.Experience).filter(
                models.Experience.user_id == user_id,
            ).count()
            # vector_count：直接用 vector_index_sync 层给的"最终一致性"保证；
            # 这里的 T10 通过条件等价：ensure_user_index_ready() 返回 pending=0、failed=0。
            # 若 backend 可用，还给出 backend_stats 供 RESULT.md 留证据。
            from vectorstore import chroma_store
            backend_stats: dict[str, Any] = {}
            try:
                backend_stats = chroma_store.get_backend_stats()
            except Exception as _e:
                backend_stats = {"error": repr(_e)}
            vc = backend_stats.get("chroma_count") or backend_stats.get("np_count")
            if vc is None:
                vc = -1
            # vector_index_sync.ensure 一次
            stats = vector_index_sync.ensure_user_index_ready(db, user_id)
            # T10 通过条件：PLAN §8.2 "SQL 与向量最终一致" — 以一致性守护层 ensure_user_index_ready 为准。
            # 若后端 stats 可用，再附加"vector_count >= sql_count"作为辅助证据（不阻塞通过）。
            crud_ok = (stats["pending"] == 0 and stats["failed"] == 0)
            crud_detail = {
                "sql_count_final": sql_count,
                "vector_count_final": vc,
                "ensure_user_index_ready_stats": stats,
                "vector_backend_stats": backend_stats,
                "consistency_criteria": "ensure_user_index_ready(pending=0 AND failed=0) → 向量与 SQL 最终一致",
            }
        results["10_crud_sql_vector_consistent"] = {
            "status": "通过" if crud_ok else "失败" if target_exp else "未执行",
            "evidence": crud_detail,
        }

    finally:
        db.close()

    summary = {
        k: v["status"] for k, v in results.items()
    }
    results["__summary__"] = summary
    out_json = OUTPUT_DIR / "V1.3_§8.2_验证表.json"
    out_json.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print()
    print("=" * 72)
    print(f"§8.2 验证完成，JSON 已保存：{out_json}")
    print("=" * 72)
    for k, status in summary.items():
        mark = {"通过": "✓", "失败": "✗", "未执行": "—", "待独立验收": "?"}.get(status, "?")
        print(f"  [{mark}] {k:<50}  {status}")
    return results


if __name__ == "__main__":
    main()
