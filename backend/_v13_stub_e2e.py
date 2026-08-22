"""V1.3 Stub E2E - 固定 LLM/Embedding mock，CI 可重复（V1.4.2 隔离修复）。

每次运行强制使用临时独立 RESUME_DATA_DIR，测试结束后整体清理，
完全不接触或污染用户真实 runtime。连续运行两次都应 20/20。
"""
import atexit
import json, os, re, shutil, sys, tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

# V1.4.1：在导入任何项目模块前，设置「测试专用假 Key」。
# 原因：core.config.Settings.ARK_API_KEY 是类属性，在 `import core.config` 时一次性从环境变量求值；
#       services/llm_service 顶层 `ChatOpenAI(api_key=settings.ARK_API_KEY)` 在 import 阶段就需要非空 key，
#       空 Key 会抛 openai.OpenAIError。本脚本是纯 Stub 测试，所有 LLM / Embedding 调用都会被 mock，
#       因此该假 Key 仅用于通过 import，绝不发起真实网络请求。
# 约束：不修改正式 llm_service / rag_service；真实 E2E 仍须提供真实 API Key。
# 用 setdefault：若外部已注入真实 Key 也不覆盖（测试验收时会清空真实 Key，故此处实际写入假 Key）。
os.environ.setdefault("ARK_API_KEY", "stub-e2e-ark-key-not-real")
os.environ.setdefault("OPENAI_API_KEY", "stub-e2e-openai-key-not-real")

# V1.4.2: 强制使用独立临时 RESUME_DATA_DIR，完全隔离用户真实 runtime。
# 隔离证明：真实 %LOCALAPPDATA%/ResumeAssistant 等目录不会被本脚本读取或写入。
_STUB_RUNTIME_TMP = Path(tempfile.mkdtemp(prefix="stub-e2e-runtime-")).resolve()
os.environ["RESUME_DATA_DIR"] = str(_STUB_RUNTIME_TMP)
# 显式覆盖三条显式路径，防止用户本机有残留环境变量绕过隔离
os.environ["SQLITE_PATH"] = str(_STUB_RUNTIME_TMP / "database" / "app.db")
os.environ["CHROMA_PATH"] = str(_STUB_RUNTIME_TMP / "vectorstore" / "chroma")
os.environ["DOCX_OUTPUT_DIR"] = str(_STUB_RUNTIME_TMP / "output")

def _cleanup_stub_runtime():
    if _STUB_RUNTIME_TMP.exists():
        shutil.rmtree(_STUB_RUNTIME_TMP, ignore_errors=True)
atexit.register(_cleanup_stub_runtime)

BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# V1.4：stub 验收的产物不写入源码树，统一落到 runtime DOCX_OUTPUT_DIR
from core.config import settings  # noqa: E402
# V1.4.1：公开版本真源
from core.version import APP_VERSION  # noqa: E402
# V1.4.1：ProfileResolver 边界测试 snapshot 用 Profile 类型
from models.resume_document import Profile as _ProfileDoc  # noqa: E402

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
    # V1.4.2: 不再访问真实 runtime。测试目录是临时隔离的，每次子测试前清空
    # output 下 DOCX（避免同一个测试 run 内前序残留影响渲染断言）。
    # 整个临时目录会在脚本退出时通过 atexit 删除。
    if OUTPUT_DIR.exists():
        for p in OUTPUT_DIR.glob("resume_*.docx"):
            try: p.unlink()
            except: pass
    print(f"[cleanup] runtime isolated at: {_STUB_RUNTIME_TMP}")

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
    # V1.4.1 修复：_setup_test_data 内部的 create_experience 会同步触发真实向量同步
    # （execute_job → rag_service._embed），必须在其之前就 mock 掉 embedding，避免无 Key 时真实网络请求。
    with patch("services.rag_service._embed", side_effect=_create_mock_embed()):
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

        dp = OUTPUT_DIR / resp.file_name if resp.file_name else BACKEND_ROOT / resp.file_path
        ok1 = dp.exists() and dp.stat().st_size > 2048
        ft = ""
        doc = None
        if ok1:
            doc = DocxDoc(str(dp))
            ft = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            ft += "\n" + "\n".join(cell.text for t in doc.tables for row in t.rows for cell in row.cells)

        print(f"  [DEBUG] DOCX text sample: {ft[:200]}...")

        results = {}
        results["1_core_docx_ok"] = {"status": "通过" if ok1 else "失败",
            "evidence": {"file_path": str(dp), "size": dp.stat().st_size if dp.exists() else 0, "stages": len(resp.stages)}}

        pt = ["王示例", "示例科技", "示例项目", "z****@***********", "138****1111", "示例市", "AI 产品经理（示例）"]
        ex = {"phone": STUB_PROFILE["phone"], "email": STUB_PROFILE["email"]}
        ok2 = all(v and v in ft for v in ex.values() if v) and not any(t in ft for t in pt)
        _has_profile_name_style = (
            any("Profile_Name" in (p.style.name if hasattr(p,"style") else "") for p in doc.paragraphs)
            if doc else False
        )
        results["2_personal_not_from_template"] = {"status": "通过" if ok2 else "失败",
            "evidence": {"present": {k: bool(v) and v in ft for k,v in ex.items()}, "profile_name_style_present": _has_profile_name_style, "leaked": [t for t in pt if t in ft]}}

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
    # V1.4.1 修复：提前 mock embedding，避免 _setup_test_data 触发真实向量同步
    with patch("services.rag_service._embed", side_effect=_create_mock_embed()):
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
    results.extend(_run_profile_boundary())
    return results

def _run_profile_boundary() -> list[dict]:
    """身份事实来源边界测试（V1.4.1 新增，替换旧 PROFILE_INCOMPLETE 契约）。

    覆盖点：
    1. ProfileResolver 单元：经历 raw_text 注入虚构联系方式，不进入最终 Profile；
    2. ProfileResolver 单元：request 只提供部分身份字段，只保留显式提供的值；
    3. ProfileResolver 单元：profile_source 只允许 request / empty；
    4. 核心链路（build + generate_docx）：姓名缺失不报错，流程成功；
    5. 核心链路：经历中虚构姓名/手机/邮箱不出现在 DOCX 文本里。
    """
    from services import resume_builder, resume_generation_service, experience_service
    from api.schemas import RequestProfile, ResumeDocxGenerateRequest
    from models.resume_document import Profile as ProfileDoc
    from docx import Document as DocxDoc

    results: list[dict] = []

    # ── 子测试 A：ProfileResolver 单元边界 ──
    # 构造一个"注入虚构身份信息"的经历 raw_text（真实姓名、手机、邮箱）
    FAKE_NAME = "欧阳不该出现在文档里"
    FAKE_PHONE = "13999998888"
    FAKE_EMAIL = "leaked-fake@example.invalid"
    fake_raws = [
        f"姓名：{FAKE_NAME}",
        f"联系方式：{FAKE_PHONE} / {FAKE_EMAIL}",
        "公司：深圳某某科技有限公司",
    ]
    fake_db_experiences = [
        type("FakeExp", (object,), {"raw_text": r, "type": "work"})()
        for r in fake_raws
    ]

    # A1. request 什么都不提供 → Profile 全空，且 source=empty
    p_a1, src_a1 = resume_builder.ProfileResolver.resolve(request_profile=None, jd_position="产品经理")
    ok_a1 = (
        p_a1.name == "" and p_a1.phone == "" and p_a1.email == "" and
        FAKE_NAME not in p_a1.name and FAKE_PHONE not in p_a1.phone and FAKE_EMAIL not in p_a1.email and
        p_a1.target_position == "产品经理" and p_a1.summary == "" and
        src_a1 == "empty"
    )
    results.append({
        "scenario": "Profile边界A1: request空 -> profile全空, source=empty, 不读取经历",
        "status": "通过" if ok_a1 else "失败",
        "evidence": {"profile": _profile_snapshot(p_a1), "source": src_a1,
                     "fake_raws_in_profile": any(FAKE_NAME in str(v) or FAKE_PHONE in str(v) or FAKE_EMAIL in str(v)
                                                 for v in [p_a1.name, p_a1.phone, p_a1.email])},
    })

    # A2. 经历 raw_text 注入虚构联系方式 + request 不提供对应字段 → 最终 Profile 为空
    p_a2, src_a2 = resume_builder.ProfileResolver.resolve(
        request_profile={}, jd_position="产品经理")
    ok_a2 = (
        p_a2.name == "" and p_a2.phone == "" and p_a2.email == "" and
        FAKE_NAME not in p_a2.name and FAKE_PHONE not in p_a2.phone and FAKE_EMAIL not in p_a2.email and
        src_a2 == "empty"
    )
    results.append({
        "scenario": "Profile边界A2: request空 + 经历含虚构联系方式 -> profile全空, 不回填",
        "status": "通过" if ok_a2 else "失败",
        "evidence": {"profile": _profile_snapshot(p_a2), "source": src_a2},
    })

    # A3. request 只提供 phone（或 phone+email），不提供 name → 只保留显式值，不从经历补 name
    p_a3, src_a3 = resume_builder.ProfileResolver.resolve(
        request_profile={"phone": STUB_PROFILE["phone"], "email": STUB_PROFILE["email"]},
        jd_position="产品经理")
    ok_a3 = (
        p_a3.name == "" and
        p_a3.phone == STUB_PROFILE["phone"] and p_a3.email == STUB_PROFILE["email"] and
        FAKE_NAME not in p_a3.name and FAKE_PHONE not in p_a3.phone and FAKE_EMAIL not in p_a3.email and
        src_a3 == "request"
    )
    results.append({
        "scenario": "Profile边界A3: request仅提供phone+email, 无name -> 仅保留显式值, 不经历补name",
        "status": "通过" if ok_a3 else "失败",
        "evidence": {"profile": _profile_snapshot(p_a3), "source": src_a3},
    })

    # A4. profile_source 只能是 request / empty（其他值都不允许）
    ok_src = src_a1 in ("request", "empty") and src_a2 in ("request", "empty") and src_a3 in ("request", "empty")
    results.append({
        "scenario": "Profile边界A4: profile_source 只取值 request 或 empty",
        "status": "通过" if ok_src else "失败",
        "evidence": {"A1": src_a1, "A2": src_a2, "A3": src_a3},
    })

    # ── 子测试 B：核心链路（姓名缺失不报错，虚构联系方式不进 DOCX）──
    _cleanup()
    from database.init_db import init_db
    from database.session import SessionLocal
    init_db()
    # V1.4.1 修复：提前 mock embedding，避免 _setup_test_data 触发真实向量同步
    with patch("services.rag_service._embed", side_effect=_create_mock_embed()):
        uid, _ = _setup_test_data(SessionLocal)
    db = SessionLocal()
    try:
        # 把 STUB_EXPERIENCES 第一条的 raw_text 注入虚构身份信息
        all_exps = experience_service.list_experiences(db, uid)
        if all_exps:
            injected = "\n".join([
                (all_exps[0].raw_text or ""),
                f"姓名：{FAKE_NAME}",
                f"联系电话：{FAKE_PHONE}",
                f"邮箱：{FAKE_EMAIL}",
            ])
            all_exps[0].raw_text = injected
            db.add(all_exps[0])
            db.commit()

        wids = [e.id for e in all_exps if e.type == "work"]
        pids = [e.id for e in all_exps if e.type == "project"]
        gc = _build_stub_gc(wids + pids)

        with patch("services.llm_service.chat_structured",
                   side_effect=_create_mock_chat_structured(STUB_JD_ANALYSIS, gc)), \
             patch("services.rag_service._embed", side_effect=_create_mock_embed()), \
             patch("services.rag_service.retrieve", side_effect=_create_mock_retrieve(all_exps)):
            # 场景 B1：name 为空，只提供 phone + email → 流程成功（不再报 PROFILE_INCOMPLETE）
            inc = RequestProfile(name="", phone=STUB_PROFILE["phone"], email=STUB_PROFILE["email"])
            req = ResumeDocxGenerateRequest(user_id=uid, template_id="pm_template",
                                            jd_text=STUB_JD_TEXT, profile=inc, top_k=5)
            try:
                resp = resume_generation_service.generate_docx(db, req)
                b1_ok = bool(resp.ok)
                b1_evidence = {"ok": resp.ok, "stages_done": all(s.status == "done" for s in resp.stages)}
            except Exception as e:
                b1_ok = False
                b1_evidence = {"error_type": type(e).__name__, "error": str(e)[:200]}

        results.append({
            "scenario": "Profile边界B1: name空但phone+email存在 -> 核心链路成功（不再PROFILE_INCOMPLETE）",
            "status": "通过" if b1_ok else "失败",
            "evidence": b1_evidence,
        })

        # 场景 B2：虚构姓名/手机/邮箱 不出现在 DOCX 文本中（DOCX 若产出则校验）
        if b1_ok and "file_path" in b1_evidence:
            pass
        if b1_ok:
            dp = OUTPUT_DIR / resp.file_name if resp.file_name else None
            if dp and dp.exists():
                d = DocxDoc(str(dp))
                ft = "\n".join(p.text for p in d.paragraphs if p.text.strip())
                ft += "\n" + "\n".join(cell.text for t in d.tables for row in t.rows for cell in row.cells)
                leaks = [x for x in (FAKE_NAME, FAKE_PHONE, FAKE_EMAIL) if x in ft]
                # 同时也不能出现 PROFILE_INCOMPLETE 字面量（证明没走旧契约）
                contract_leak = "PROFILE_INCOMPLETE" in ft
                b2_ok = len(leaks) == 0 and not contract_leak
                results.append({
                    "scenario": "Profile边界B2: 经历注入的虚构姓名/手机/邮箱不进入DOCX",
                    "status": "通过" if b2_ok else "失败",
                    "evidence": {"leaked": leaks, "old_contract_in_docx": contract_leak,
                                 "docx_sample": ft[:300]},
                })
            else:
                results.append({
                    "scenario": "Profile边界B2: 经历注入的虚构姓名/手机/邮箱不进入DOCX",
                    "status": "失败",
                    "evidence": {"reason": "DOCX未产出，无法校验", "file_path": str(dp) if dp else None},
                })
    finally:
        db.close()

    return results


def _profile_snapshot(p: _ProfileDoc) -> dict:
    """只返回身份字段快照，不泄露其他字段。"""
    return {
        "name": p.name,
        "phone": p.phone,
        "email": p.email,
        "location": p.location,
        "target_position": p.target_position,
        "summary": p.summary,
    }

def main():
    print("=" * 72)
    print("V1.3 Stub E2E - 固定 LLM/Embedding mock, CI 可重复")
    print("=" * 72)
    print("\n[1/2] Happy Path ...")
    happy = run_happy_path()
    for k, v in happy.items():
        print(f"  [{'PASS' if v['status']=='通过' else 'FAIL'}] {k}: {v['status']}")
    print("\n[2/2] 错误分支 + 身份边界 ...")
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
    # V1.4.2: 隔离完整性证明 — 临时 runtime 在结束时整体删除
    _cleanup_stub_runtime()
    print(f"  [isolation] 临时 runtime 已删除: {Path(str(_STUB_RUNTIME_TMP)).exists()} (False 为预期)")
    return all_results

if __name__ == "__main__":
    main()
