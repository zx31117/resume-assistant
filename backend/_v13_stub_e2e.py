"""V1.3 Stub E2E - 固定 LLM/Embedding mock，CI 可重复"""
import json, os, re, shutil, sys
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# V1.4：stub 验收的产物不写入源码树，统一落到 runtime DOCX_OUTPUT_DIR
from core.config import settings  # noqa: E402

OUTPUT_DIR = Path(settings.DOCX_OUTPUT_DIR)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

STUB_JD_ANALYSIS = {
    "position": "AI硬件产品经理", "industry": "智能硬件/AI",
    "required_skills": ["产品规划", "AI", "硬件", "数据分析", "项目管理"],
    "preferred_skills": ["大模型", "Python", "用户研究"],
    "responsibilities": ["负责AI硬件产品规划和定义"],
    "keywords": ["AI", "硬件", "产品经理", "智能硬件"],
    "experience_preferences": ["3年以上产品经验"],
}
STUB_EMBEDDING_VECTOR = [0.1] * 2048

STUB_EXPERIENCES = [
    {"type": "work", "title": "影像测试实习生", "company": "深圳传音控股股份有限公司",
     "role": "影像测试实习生（AI方向）", "time": "2026.05-至今",
     "description": "负责AI影像产品测试和数据分析。",
     "skills": ["AI", "数据分析", "Python"], "achievements": ["完成3个AI影像项目测试"]},
    {"type": "project", "title": "基于STM32的智能家居控制系统",
     "role": "项目负责人", "time": "2025.03-2025.06",
     "description": "设计STM32智能家居系统。",
     "skills": ["STM32", "C语言", "IoT"], "achievements": ["校级优秀项目奖"]},
    {"type": "project", "title": "基于LLM Agent的智能客服系统",
     "role": "核心开发者", "time": "2025.09-2025.12",
     "description": "基于LLM Agent构建智能客服。",
     "skills": ["Python", "LLM", "NLP"], "achievements": ["客服效率提升40%"]},
    {"type": "education", "title": "电子信息工程", "company": "某某大学",
     "role": "本科", "time": "2022.09-2026.06",
     "description": "GPA 3.8/4.0", "skills": [], "achievements": []},
]
STUB_PROFILE = {"name": "张三", "phone": "13800000001", "email": "zhangsan@example.com",
                "location": "深圳", "target_position": "AI硬件产品经理"}
STUB_JD_TEXT = "AI硬件产品经理\n负责AI硬件产品规划。\n要求: 3年产品经验, AI/硬件优先。"

def _cleanup():
    d = BACKEND_ROOT / "data"
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    for p in OUTPUT_DIR.glob("resume_*.docx"):
        try: p.unlink()
        except: pass
    print("[cleanup] done")

def _build_stub_gc(exp_ids):
    items = [{"experience_id": eid, "bullets": [f"[STUB] AI bullet for {eid[:8]}"]} for eid in exp_ids]
    return {"experiences": items}

def _create_mock_chat_structured(stub_jd, stub_gc):
    from api.schemas import JDAnalysisOut, GeneratedResumeContent
    def fn(system, user_template, schema, strict=False, default=None, **variables):
        if schema is JDAnalysisOut or schema.__name__ == "JDAnalysisOut":
            return JDAnalysisOut.model_validate(stub_jd)
        elif schema is GeneratedResumeContent or schema.__name__ == "GeneratedResumeContent":
            return GeneratedResumeContent.model_validate(stub_gc)
        return schema() if default is None else default
    return fn

def _create_mock_embed():
    return lambda text: list(STUB_EMBEDDING_VECTOR)

def _create_mock_retrieve(all_exps):
    def fn(jd_analysis, user_id=None, k=5):
        matched = [e for e in all_exps if e.type in ("work", "project")]
        return [{"id": e.id, "text": e.description or "", "metadata": {},
                 "distance": 0.5, "scores": {"semantic": 0.8, "skill": 0.7, "role": 0.6, "final": 0.75},
                 "reason": "stub match"} for e in matched[:k]]
    return fn

def _setup_test_data(db_factory):
    from database import models
    from services import experience_service, vector_index_sync
    db = db_factory()
    try:
        u = db.query(models.User).filter(models.User.id == "stub-user").first()
        if not u:
            u = models.User(id="stub-user", name="张三")
            db.add(u)
            db.commit()
        uid = "stub-user"
        ids = []
        for ed in STUB_EXPERIENCES:
            exp = experience_service.create_experience(db, uid, ed)
            ids.append(exp.id)
        try:
            vector_index_sync.ensure_user_index_ready(db, uid)
        except Exception:
            pass
        return uid, ids
    finally:
        db.close()

def run_happy_path():
    from database.init_db import init_db
    from database.session import SessionLocal
    from services import resume_generation_service, experience_service
    from api.schemas import RequestProfile, ResumeDocxGenerateRequest
    from docx import Document as DocxDoc

    _cleanup()
    init_db()
    uid, eids = _setup_test_data(SessionLocal)
    db = SessionLocal()
    try:
        all_exps = experience_service.list_experiences(db, uid)
        wids = [e.id for e in all_exps if e.type == "work"]
        pids = [e.id for e in all_exps if e.type == "project"]
        matched = wids + pids
        gc = _build_stub_gc(matched)

        with patch("services.llm_service.chat_structured",
                   side_effect=_create_mock_chat_structured(STUB_JD_ANALYSIS, gc)), \
             patch("services.rag_service._embed", side_effect=_create_mock_embed()), \
             patch("services.rag_service.retrieve", side_effect=_create_mock_retrieve(all_exps)):
            req = ResumeDocxGenerateRequest(user_id=uid, template_id="pm_template",
                                            jd_text=STUB_JD_TEXT, profile=RequestProfile(**STUB_PROFILE), top_k=5)
            resp = resume_generation_service.generate_docx(db, req)

        dp = BACKEND_ROOT / resp.file_path
        ok1 = dp.exists() and dp.stat().st_size > 2048
        ft = ""
        if dp.exists():
            d = DocxDoc(str(dp))
            ft = "\n".join(p.text for p in d.paragraphs if p.text.strip())
            ft += "\n" + "\n".join(cell.text for t in d.tables for row in t.rows for cell in row.cells)

        print(f"  [DEBUG] DOCX text sample: {ft[:200]}...")

        results = {}
        results["1_core_docx_ok"] = {"status": "通过" if ok1 else "失败",
            "evidence": {"file_path": str(dp), "size": dp.stat().st_size if dp.exists() else 0, "stages": len(resp.stages)}}

        pt = ["王示例", "示例科技", "示例项目", "z****@***********", "138****1111", "示例市", "AI 产品经理（示例）"]
        ex = {"phone": STUB_PROFILE["phone"], "email": STUB_PROFILE["email"]}
        ok2 = all(v and v in ft for v in ex.values() if v) and not any(t in ft for t in pt)
        results["2_personal_not_from_template"] = {"status": "通过" if ok2 else "失败",
            "evidence": {"present": {k: bool(v) and v in ft for k,v in ex.items()}, "name_in_doc": any("Profile_Name" in (p.style.name if hasattr(p,"style") else "") for p in d.paragraphs), "name_in_doc": any("Profile_Name" in (p.style.name if hasattr(p,"style") else "") for p in d.paragraphs), "leaked": [t for t in pt if t in ft]}}

        sids = {e.id for e in all_exps}
        ms = set(resp.matched_experience_ids)
        rs = set(resp.rendered_experience_ids)
        ok3 = rs.issubset(sids & ms)
        results["3_rendered_ids_subset"] = {"status": "通过" if ok3 else "失败",
            "evidence": {"sql": sorted(sids), "matched": sorted(ms), "rendered": sorted(rs), "diff": sorted(rs - (sids & ms))}}

        fo = True; fd = {}
        for eid in sorted(rs):
            exp = next((x for x in all_exps if x.id == eid), None)
            if not exp: fo = False; fd[eid] = "SQL缺失"; continue
            toks = []
            if exp.type == "work": toks = [x for x in [exp.company, exp.role, exp.time] if x and x.strip()]
            elif exp.type == "project": toks = [x for x in [exp.title, exp.role, exp.time] if x and x.strip()]
            pr = {t: (t in ft) for t in toks}
            if exp.type in ("work","project") and not all(pr.values()): fo = False
            fd[eid] = {"type": exp.type, "tokens": pr}
        results["4_facts_equal_sql"] = {"status": "通过" if fo else "失败", "evidence": fd}

        from services import resume_builder
        from api.schemas import GeneratedResumeContent, GeneratedExperienceItem, JDAnalysisOut
        if wids and pids:
            tid = wids[0]
            others = [GeneratedExperienceItem(experience_id=eid, bullets=[]) for eid in pids]
            gct = GeneratedResumeContent(experiences=[GeneratedExperienceItem(experience_id=tid, bullets=["[STUB] AI bullet"]), *others])
            jdo = JDAnalysisOut.model_validate(STUB_JD_ANALYSIS)
            ml = [{"id": w, "scores": {"final": 0.9}} for w in wids] + [{"id": p, "scores": {"final": 0.8}} for p in pids]
            _doc, bm = resume_builder.build(db, user_id=uid, matched_experiences=ml, jd_analysis=jdo, generated_content=gct, request_profile=STUB_PROFILE)
            cov = set(bm.get("ai_covered_experience_ids", []))
            fb = set(bm.get("fallback_sql_experience_ids", []))
            ok5 = (tid in cov) and all(pid in fb for pid in pids)
            results["5_bullets_missing_sql_fallback"] = {"status": "通过" if ok5 else "失败",
                "evidence": {"ai_covered": sorted(cov), "fallback": sorted(fb), "counts": bm.get("counts")}}
        else:
            results["5_bullets_missing_sql_fallback"] = {"status": "未执行", "evidence": "no work/project"}

        sm = {s.section_id: s for s in resp.render_stats.sections}
        ok6 = True
        for sid in ("work","skills"):
            s = sm.get(sid)
            if s and s.input_items != s.rendered_items: ok6 = False
        st = {"education": ["教育背景"], "projects": ["项目经历"], "work": ["实习经历","工作经历"], "skills": ["技能专长"]}
        for sk, tks in st.items():
            s = sm.get(sk)
            if s and s.input_items > 0 and not any(t in ft for t in tks): ok6 = False
        if len(resp.render_stats.unreplaced_placeholders) > 0: ok6 = False
        results["6_renderer_no_truncate"] = {"status": "通过" if ok6 else "失败",
            "evidence": {"sections": [s.model_dump() for s in resp.render_stats.sections],
                         "unreplaced": resp.render_stats.unreplaced_placeholders,
                         "capacity_warnings": resp.render_stats.capacity_warnings}}

        phs = set()
        for pat in [r"\{\{([^{}]+)\}\}", r"\[\[([^\[\]]+)\]\]"]:
            for m in re.finditer(pat, ft): phs.add(m.group(0))
        bt = ["示例科技","示例项目","王示例","z****@***********","138****1111"]
        bs = [t for t in bt if t in ft]
        ok7 = len(phs)==0 and len(bs)==0
        results["7_no_template_sample"] = {"status": "通过" if ok7 else "失败",
            "evidence": {"unreplaced": sorted(phs), "samples": sorted(bs)}}

        ok8 = all(s.status == "done" for s in resp.stages)
        results["8_all_stages_done"] = {"status": "通过" if ok8 else "失败",
            "evidence": {"stages": [s.model_dump() for s in resp.stages]}}

        rf = ["file_path","file_name","download_url","stages","matched_experience_ids",
              "rendered_experience_ids","profile_source","build_counts","build_meta","render_stats","warnings","template_id"]
        ok9 = all(hasattr(resp,f) and getattr(resp,f) is not None for f in rf)
        results["9_response_structure"] = {"status": "通过" if ok9 else "失败",
            "evidence": {"missing": [f for f in rf if not hasattr(resp,f) or getattr(resp,f) is None]}}

        bm2 = resp.build_meta
        ok10 = all([isinstance(bm2.profile_source,str) and bm2.profile_source,
                    isinstance(bm2.ai_covered_experience_ids,list),
                    isinstance(bm2.fallback_sql_experience_ids,list),
                    isinstance(bm2.ai_unrecognized_experience_ids,list)])
        results["10_build_meta_diagnostics"] = {"status": "通过" if ok10 else "失败",
            "evidence": {"profile_source": bm2.profile_source, "ai_covered": bm2.ai_covered_experience_ids,
                         "fallback": bm2.fallback_sql_experience_ids, "ai_unrecognized": bm2.ai_unrecognized_experience_ids,
                         "trimmed": bm2.max_items_trimmed, "counts": bm2.counts.model_dump()}}
        return results
    finally:
        db.close()

def _run_error(desc, extra_patches, exp_code, exp_http):
    from database.init_db import init_db
    from database.session import SessionLocal
    from services import resume_generation_service, experience_service
    from api.schemas import RequestProfile, ResumeDocxGenerateRequest
    from core.errors import DomainError
    _cleanup()
    init_db()
    uid, eids = _setup_test_data(SessionLocal)
    db = SessionLocal()
    try:
        all_exps = experience_service.list_experiences(db, uid)
        wids = [e.id for e in all_exps if e.type == "work"]
        pids = [e.id for e in all_exps if e.type == "project"]
        gc = _build_stub_gc(wids + pids)
        am = {"services.llm_service.chat_structured": _create_mock_chat_structured(STUB_JD_ANALYSIS, gc),
              "services.rag_service._embed": _create_mock_embed(),
              "services.rag_service.retrieve": _create_mock_retrieve(all_exps)}
        for t, se in extra_patches:
            am[t] = se
        ps = []
        for t, se in am.items():
            p = patch(t, side_effect=se if callable(se) else se)
            p.start()
            ps.append(p)
        try:
            req = ResumeDocxGenerateRequest(user_id=uid, template_id="pm_template",
                                            jd_text=STUB_JD_TEXT, profile=RequestProfile(**STUB_PROFILE), top_k=5)
            resp = resume_generation_service.generate_docx(db, req)
            return {"scenario": desc, "status": "失败",
                    "evidence": {"expected": exp_code, "expected_http": exp_http, "actual": f"no error, ok={resp.ok}"}}
        except DomainError as e:
            ok = (e.error_code == exp_code and e.http_status == exp_http and bool(e.message))
            return {"scenario": desc, "status": "通过" if ok else "失败",
                    "evidence": {"error_code": e.error_code, "http": e.http_status, "expected": exp_code,
                                 "expected_http": exp_http, "message": (e.message or "")[:200], "stage": e.stage, "retryable": e.retryable}}
        except Exception as e:
            return {"scenario": desc, "status": "失败", "evidence": {"expected": exp_code, "actual": f"{type(e).__name__}: {e}"}}
        finally:
            for p in ps:
                p.stop()
    finally:
        db.close()

def run_error_branches():
    from core.errors import LLMOutputInvalidError
    from core.errors import VectorIndexNotReadyError as VINRE
    sc = [
        ("JD分析: position为空 -> JD_INVALID (422)",
         [("services.llm_service.chat_structured",
           _create_mock_chat_structured({**STUB_JD_ANALYSIS, "position": ""}, _build_stub_gc([])))],
         "JD_INVALID", 422),
        ("RAG: 无匹配 -> NO_MATCHED_EXPERIENCE (422)",
         [("services.rag_service.retrieve", lambda *a,**kw: [])],
         "NO_MATCHED_EXPERIENCE", 422),
        ("LLM: structured失败 -> LLM_OUTPUT_INVALID (502)",
         [("services.llm_service.chat_structured",
           MagicMock(side_effect=LLMOutputInvalidError("stub", stage="content_generation", details={"s":"Gen"})))],
         "LLM_OUTPUT_INVALID", 502),
        ("索引: 未就绪 -> VECTOR_INDEX_NOT_READY (503)",
         [("services.vector_index_sync.ensure_user_index_ready",
           MagicMock(side_effect=VINRE("stub", failed_ids=["id-1"], pending_ids=[])))],
         "VECTOR_INDEX_NOT_READY", 503),
    ]
    results = [_run_error(d, p, c, h) for d, p, c, h in sc]
    results.append(_run_profile_error())
    return results

def _run_profile_error():
    from database.init_db import init_db
    from database.session import SessionLocal
    from services import resume_generation_service, experience_service
    from api.schemas import RequestProfile, ResumeDocxGenerateRequest
    from core.errors import DomainError
    _cleanup()
    init_db()
    uid, eids = _setup_test_data(SessionLocal)
    db = SessionLocal()
    try:
        all_exps = experience_service.list_experiences(db, uid)
        wids = [e.id for e in all_exps if e.type == "work"]
        pids = [e.id for e in all_exps if e.type == "project"]
        gc = _build_stub_gc(wids + pids)
        with patch("services.resume_builder._extract_profile_from_experiences", return_value=type("obj",(object,),{"name":"","phone":"","email":"","location":"","target_position":"","summary":"","job_intent":"","model_dump":lambda self: self.__dict__})()), \
             patch("services.rag_service._embed", side_effect=_create_mock_embed()), \
             patch("services.rag_service.retrieve", side_effect=_create_mock_retrieve(all_exps)):
            inc = RequestProfile(name="", phone=STUB_PROFILE["phone"], email=STUB_PROFILE["email"])
            req = ResumeDocxGenerateRequest(user_id=uid, template_id="pm_template", jd_text=STUB_JD_TEXT, profile=inc, top_k=5)
            try:
                resp = resume_generation_service.generate_docx(db, req)
                return {"scenario": "Profile: name为空 -> PROFILE_INCOMPLETE (400)", "status": "失败",
                        "evidence": {"expected": "PROFILE_INCOMPLETE", "expected_http": 400, "actual": f"no error, ok={resp.ok}"}}
            except DomainError as e:
                ok = (e.error_code == "PROFILE_INCOMPLETE" and e.http_status == 400)
                return {"scenario": "Profile: name为空 -> PROFILE_INCOMPLETE (400)", "status": "通过" if ok else "失败",
                        "evidence": {"error_code": e.error_code, "http": e.http_status, "expected": "PROFILE_INCOMPLETE",
                                     "expected_http": 400, "message": (e.message or "")[:200], "stage": e.stage}}
    finally:
        db.close()

def main():
    print("=" * 72)
    print("V1.3 Stub E2E - 固定 LLM/Embedding mock, CI 可重复")
    print("=" * 72)
    print("\n[1/2] Happy Path ...")
    happy = run_happy_path()
    for k, v in happy.items():
        print(f"  [{'PASS' if v['status']=='通过' else 'FAIL'}] {k}: {v['status']}")
    print("\n[2/2] 错误分支 (5 scenarios) ...")
    errors = run_error_branches()
    for r in errors:
        print(f"  [{'PASS' if r['status']=='通过' else 'FAIL'}] {r['scenario']}")
    all_results = {"happy_path": happy, "error_branches": errors,
                   "__summary__": {"happy_path": {k: v["status"] for k,v in happy.items()},
                                   "error_branches": {r["scenario"]: r["status"] for r in errors}}}
    hp = sum(1 for v in happy.values() if v["status"]=="通过")
    ht = len(happy)
    ep = sum(1 for r in errors if r["status"]=="通过")
    et = len(errors)
    out = OUTPUT_DIR / "V1.3_StubE2E_验证表.json"
    out.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{'=' * 72}")
    print(f"Stub E2E 完成 - {out}")
    print(f"  Happy Path: {hp}/{ht}  错误分支: {ep}/{et}  总计: {hp+ep}/{ht+et}")
    print("=" * 72)
    if hp != ht or ep != et:
        print("\n存在未通过的测试项!")
        sys.exit(1)
    return all_results

if __name__ == "__main__":
    main()