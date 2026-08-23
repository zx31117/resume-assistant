"""V1.4 T7 — 干净环境 + 核心回归脚本。

作用：
 1. 验证 V1.4 默认路径下"空 runtime 自动初始化"；
 2. 验证源码核心模块可 import、核心模块导出类/函数可实例化；
 3. 验证 V1.3 源码级回归用例（Case 1-10 中不依赖 LLM/RAG/Vector 的部分）；
 4. 验证迁移（SQL 部分，可 SUSPEND vector rebuild，不删旧 backend/data）。

执行方式（在 backend/ 目录下）：
    python _v14_t7_regression.py
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import sys
import shutil
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

# —— 强制 V1.4 默认路径（屏蔽本地 .env / 旧 env）—— #
for _k in [
    'SQLITE_PATH','CHROMA_PATH','DOCX_OUTPUT_DIR','RESUME_DATA_DIR',
    'ARK_API_KEY','ARK_BASE_URL','LLM_MODEL','EMBEDDING_MODEL',
    'APP_HOST','APP_PORT',
]:
    os.environ.pop(_k, None)
try:
    import dotenv  # type: ignore
    dotenv.load_dotenv = lambda *a, **kw: False  # patch before any module imports
except Exception:
    pass

_BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND))


# ============================================================
# 测试框架：轻量断言，输出 JSON 报告
# ============================================================

@dataclass
class Case:
    id: str
    name: str
    section: str
    fn: Callable[["RunCtx"], None]


@dataclass
class CaseResult:
    id: str
    name: str
    section: str
    status: str       # PASS / FAIL / SUSPEND
    detail: str = ""
    duration_ms: float = 0.0


@dataclass
class RunCtx:
    clean_runtime: Path          # 本次 T7 临时 runtime 根
    clean_sqlite: Path           # clean_runtime / database/app.db
    clean_output: Path
    section: str = ""
    results: list[CaseResult] = field(default_factory=list)
    sections: set[str] = field(default_factory=set)

    def _runtime_data_backup_cleanup(self):
        pass


def case(section: str, cid: str, name: str):
    def deco(fn):
        _ALL_CASES.append(Case(id=cid, name=name, section=section, fn=fn))
        return fn
    return deco


_ALL_CASES: list[Case] = []


@contextmanager
def timing(cr: CaseResult):
    t0 = time.perf_counter()
    try:
        yield
    finally:
        cr.duration_ms = round((time.perf_counter() - t0) * 1000, 1)


def run_case(ctx: RunCtx, c: Case):
    cr = CaseResult(id=c.id, name=c.name, section=c.section, status="FAIL")
    ctx.sections.add(c.section)
    try:
        with timing(cr):
            c.fn(ctx)
        cr.status = "PASS"
    except Suspend as e:
        cr.status = "SUSPEND"
        cr.detail = str(e)
    except AssertionError as e:
        cr.detail = f"AssertionError: {e}"
    except Exception as e:
        cr.detail = f"{type(e).__name__}: {e}"[:400]
    ctx.results.append(cr)
    sym = {"PASS":"✅","FAIL":"❌","SUSPEND":"⏸️"}.get(cr.status,"?")
    print(f"  [{cr.status:<7}] {c.section}-{c.id:<5} {c.name}" + (f" — {cr.detail}" if cr.detail else ""))


class Suspend(Exception):
    pass


# ============================================================
# SECTION 1: 干净 runtime 自动初始化（路径 + 目录）
# ============================================================

@case("RUNTIME", "1", "V1.4 默认 RESUME_DATA_DIR 位于源码外")
def _(ctx: RunCtx):
    from core.config import settings
    rd = settings.RESUME_DATA_DIR
    assert isinstance(rd, Path), "RESUME_DATA_DIR 类型应是 Path"
    repo = _BACKEND.parent.resolve()
    # 要求不在源码树下
    try:
        rd.relative_to(repo)
        within = True
    except ValueError:
        within = False
    assert not within, f"默认 RESUME_DATA_DIR={rd} 不应位于源码树 {repo} 下"

@case("RUNTIME", "2", "空 runtime 第一次 import settings 自动建 5 个子目录")
def _(ctx: RunCtx):
    from core.config import settings
    expected = ["database","vectorstore","output","logs","cache"]
    missing = [n for n in expected if not (settings.RESUME_DATA_DIR / n).is_dir()]
    assert not missing, f"缺失自动创建的子目录: {missing}"

@case("RUNTIME", "3", "SQLITE_PATH/CHROMA_PATH/DOCX_OUTPUT_DIR 都落在 runtime root 下")
def _(ctx: RunCtx):
    from core.config import settings
    rd = settings.RESUME_DATA_DIR
    pairs = {
        "SQLITE_PATH": settings.SQLITE_PATH,
        "CHROMA_PATH": settings.CHROMA_PATH,
        "DOCX_OUTPUT_DIR": settings.DOCX_OUTPUT_DIR,
    }
    bad = []
    for k, v in pairs.items():
        try:
            Path(v).resolve().relative_to(rd.resolve())
        except Exception:
            bad.append(f"{k}={v}")
    assert not bad, f"以下路径不在 runtime root 下: {bad}"


# ============================================================
# SECTION 2: 核心模块 import / 核心类构造（源码级）
# ============================================================

@case("CORE", "1", "导入全部核心模块（无 import Syntax/Dep 错误）")
def _(ctx: RunCtx):
    # V1.3 main / api.routes.* / resume_generation_service / llm_service 在模块顶层初始化 OpenAI 客户端，
    # 要求 api_key（运行时 V1.3 既有行为）。T7 回归在隔离沙箱中无 ARK_API_KEY，故用 stub 环境变量占位，
    # 确保能走完 Python import 路径 → 验证无语法/依赖错误；不触发真实 API 调用。
    _stub_env = {
        "ARK_API_KEY": "t7-regression-stub-sk-dummy-not-real",
        "OPENAI_API_KEY": "t7-regression-stub-sk-dummy-not-real",
    }
    _saved = {k: os.environ.get(k) for k in _stub_env}
    try:
        for k, v in _stub_env.items():
            os.environ[k] = v
        mods = [
            "main",
            "api.schemas", "api.routes.generate","api.routes.template","api.routes.experience",
            "api.routes.jd","api.routes.resume",
            "core.config","core.errors",
            "database.init_db","database.session","database.models","database.migrations",
            "models.resume_document","models.template_schema",
            "services.docx_writer","services.template_renderer",
            "services.resume_builder","services.layout_optimizer",
            "services.resume_generation_service",
            "services.llm_service","services.embedding_service",
            "services.fact_service","services.selection_service","services.constrained_rewrite",
            "run_stub_demo",
        ]
        failed = []
        for m in mods:
            try:
                importlib.import_module(m)
            except Exception as e:
                failed.append(f"{m}: {type(e).__name__}:{e}")
        assert not failed, f"模块导入失败: {failed[:5]}{'...'+str(len(failed)) if len(failed)>5 else ''}"
    finally:
        for k, old_v in _saved.items():
            if old_v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old_v

@case("CORE", "2", "Settings.BASE_DIR 是 Path 并指向 backend/")
def _(ctx: RunCtx):
    from core.config import settings
    bd = settings.BASE_DIR
    assert isinstance(bd, Path), "BASE_DIR 应是 Path（用于内部资产定位）"
    assert (bd / "main.py").is_file(), f"BASE_DIR={bd} 下找不到 main.py"

@case("CORE", "3", "数据库初始化：init_db() 能建 3 张表（空 runtime）")
def _(ctx: RunCtx):
    from database.init_db import init_db
    from database.session import SessionLocal, engine
    init_db()
    from sqlalchemy import inspect
    insp = inspect(engine)
    tables = insp.get_table_names()
    required = {"users","experiences","facts","schema_versions","fact_embeddings"}
    missing = required - set(tables)
    assert not missing, f"缺表: {missing}; found={tables}"

@case("CORE", "4", "TemplateRenderer(pm_template) 能加载（模板资产完整）")
def _(ctx: RunCtx):
    from services.template_renderer import TemplateRenderer
    tr = TemplateRenderer("pm_template", backend_root=str(_BACKEND))
    assert tr.template_id == "pm_template" and tr.doc is not None and tr.spec is not None, "模板加载异常"
    # template spec 中至少存在 work / education 章节（否则简历没法落盘）
    types = {s.type for s in tr.spec.sections}
    for t in ("profile","work","education"):
        assert t in types, f"模板 spec 缺失章节 type={t}"


# ============================================================
# SECTION 3: V1.3 源码级回归（§8.2 的 10 case 的 offline 子集）
# ============================================================

@case("V13", "1", "事实边界：模板 JSON 中不含任何用户姓名/公司/经历字段")
def _(ctx: RunCtx):
    with (_BACKEND / "templates" / "pm_template.json").open("r", encoding="utf-8") as f:
        spec = json.load(f)
    # 把全 JSON 转字符串做关键词检索
    s = json.dumps(spec, ensure_ascii=False)
    hits = []
    for bad in ("示例大学","示例云科技","星辰科技","林示例","张示例","张三","白晓"):
        if bad in s: hits.append(bad)
    # 也不含真实人名公司名特征
    assert not hits, f"模板 JSON 不应含用户/公司事实字段，但发现: {hits}"

@case("V13", "2", "ProfileResolver：target_position 只取 JD.position，身份只取 request")
def _(ctx: RunCtx):
    from services.resume_builder import ProfileResolver
    profile, src = ProfileResolver.resolve(
        request_profile={"name":"甲","phone":"1","email":"2","location":"3","job_intent":"不要用这个"},
        jd_position="Java 工程师",
    )
    assert profile.name == "甲" and profile.phone == "1" and profile.email == "2" and profile.location == "3"
    assert profile.target_position == "Java 工程师", f"target_position 必须来自 JD，实际 {profile.target_position!r}"
    # request 不放求职意向 → JD.position 仍然生效；且不回退 request.job_intent
    profile2, _ = ProfileResolver.resolve(request_profile={}, jd_position="后端")
    assert profile2.target_position == "后端"

@case("V13", "3", "ResumeBuilder.build：AI 未覆盖的条目会用 SQL description+achievements 回退")
def _(ctx: RunCtx):
    from sqlalchemy.orm import Session
    from database.session import SessionLocal
    from database import models
    from services import resume_builder
    from api.schemas import JDAnalysisOut, GeneratedResumeContent
    # 本 case 验证「SQL fallback」——AI 完全没覆盖 → 用 SQL description+achievements 生成 bullets。
    # 为避免 TemplateRenderer 必填 projects 报错，同时构造 1 条 project 夹具。
    db: Session = SessionLocal()
    try:
        u = models.User(id="t7_fallback_user", name="Fallback", email="fb@example.com")
        # T9 修复：先 add + commit 再 flush，确保 User 实例真正 persistent
        #        （避免 SA 的 "Instance is not persisted" 错误）
        existing = db.query(models.User).filter(models.User.id == u.id).first()
        if existing:
            db.delete(existing); db.commit()
        db.add(u); db.commit()
        db.refresh(u)

        exp_work = models.Experience(
            id="t7_fallback_exp_work", user_id=u.id, type="work",
            title="软件工程师", company="Fallback Co", time="2021 - 至今",
            role="后端组", description="负责下单/支付", skills=["Java","SQL"],
            achievements=["618 零事故","系统 TPS 翻 2 倍"],
            raw_text="Fallback Work",
        )
        exp_proj = models.Experience(
            id="t7_fallback_exp_project", user_id=u.id, type="project",
            title="核心支付链路重构", company="Fallback Co", time="2022.01 - 2022.06",
            role="主程", description="端到端链路：下单 → 风控 → 支付回调", skills=["Kafka","Redis"],
            achievements=["幂等上线零重复扣款","峰值 TPS x3"],
            raw_text="Fallback Project",
        )
        existing_w = db.query(models.Experience).filter(models.Experience.id == exp_work.id).first()
        if existing_w: db.delete(existing_w); db.commit()
        existing_p = db.query(models.Experience).filter(models.Experience.id == exp_proj.id).first()
        if existing_p: db.delete(existing_p); db.commit()
        db.add_all([exp_work, exp_proj]); db.commit()

        jd = JDAnalysisOut(position="高级后端工程师")
        matched = [
            {"id": exp_work.id, "final_score": 0.9, "rerank_score": 0.9, "chunk_text": ""},
            {"id": exp_proj.id, "final_score": 0.8, "rerank_score": 0.8, "chunk_text": ""},
        ]
        gen = GeneratedResumeContent(experiences=[])  # AI 完全没生成任何 bullets → 回退 SQL
        doc, meta = resume_builder.build(
            db, user_id=u.id, matched_experiences=matched, jd_analysis=jd,
            all_experiences=[exp_work, exp_proj],
            request_profile={"name":"F","job_intent":""},
            generated_content=gen,
        )
        assert len(doc.work) == 1, f"work 条目数应为 1，实际 {len(doc.work)}"
        w = doc.work[0]
        assert w.company == "Fallback Co" and w.role == "后端组"  # 事实字段来自 SQL
        bullets = [b.strip() for b in w.bullets if b.strip()]
        assert len(bullets) >= 3, f"回退 bullets 条数不足: {bullets}"
        assert any("下单" in b for b in bullets), "未检测到 SQL description 回退"
        assert any("618" in b or "TPS 翻 2 倍" in b for b in bullets), "未检测到 SQL achievements 回退"
        assert len(doc.projects) == 1, f"projects 条目数应为 1，实际 {len(doc.projects)}"
        # 清理
        db.delete(u); db.commit()
    finally:
        db.close()

@case("V13", "4", "TemplateRenderer.render 输入输出条目数一致（渲染层不裁条目）")
def _(ctx: RunCtx):
    from services.template_renderer import TemplateRenderer
    from models.resume_document import (
        ResumeDocument, Profile, WorkItem, EducationItem, ProjectItem, SkillGroup,
    )
    doc = ResumeDocument(
        profile=Profile(name="R", target_position="P", phone="1", email="2"),
        education=[
            EducationItem(school="S", major="M", degree="本科", start_time="2018.09", end_time="2022.06"),
        ],
        work=[
            WorkItem(company="C1", role="R1", start_time="2022.07", end_time="2024.01",
                     bullets=["b1","b2","b3"]),
            WorkItem(company="C2", role="R2", start_time="2024.02", end_time="至今",
                     bullets=["a1","a2"]),
        ],
        projects=[
            ProjectItem(name="Payments", role="Owner", start_time="2023.01", end_time="2023.06",
                        bullets=["p1","p2"]),
        ],
        skills=[
            SkillGroup(category="语言", items=["Python","Java"]),
            SkillGroup(category="框架", items=["FastAPI","Spring Boot"]),
        ],
        awards=[],
    )
    tr = TemplateRenderer("pm_template", backend_root=str(_BACKEND))
    out_doc, warnings, stats = tr.render(doc)
    sec_counts = {s["section_id"]:(s["input_items"],s["rendered_items"]) for s in stats["sections"]}
    # work / education / projects 条目数对照；skills 是分组聚合不计入 rendered_items 断言
    for sid, in_cnt, expect in [
        ("work", 2, 2),
        ("education", 1, 1),
        ("projects", 1, 1),
    ]:
        found_in, found_rn = sec_counts.get(sid, (None, None))
        assert found_in == in_cnt and found_rn == expect, (
            f"{sid}: input={found_in}/expected_in={in_cnt}, rendered={found_rn}/expected_rn={expect}"
        )

@case("V13", "5", "DOCX 输出路径：run_stub_demo 样式的生成结果必落在 DOCX_OUTPUT_DIR")
def _(ctx: RunCtx):
    from core.config import settings
    out_dir = Path(settings.DOCX_OUTPUT_DIR).resolve()
    rd = settings.RESUME_DATA_DIR.resolve()
    # 必须是 runtime/output 子目录
    out_dir.relative_to(rd)
    # 我们在此不跑 run_stub_demo（避免写真实 demo_resume.docx），只验证 settings 值已经在 runtime 下
    assert out_dir == rd / "output", f"DOCX_OUTPUT_DIR 相对 runtime 错位：{out_dir} vs {rd/'output'}"


# ============================================================
# SECTION 4: 迁移回归（SQL 一致性，SUSPEND vector rebuild 若缺 key）
# ============================================================

@case("MIG", "1", "（T8 干净首发包）旧 backend/data/app.db 不出现在首发包 OR 存在均可（A/B 分类一致：C 类一律不进首发）")
def _(ctx: RunCtx):
    """V1.4 PLAN §6.8 明确：T8 首发包不得携带 C 类 runtime data。backend/data/app.db 属于 C 类，
    因此 T8 首发包里它一定不存在。MIG-1 的验收方式改为：在文档 README.md §2.4
    明确列出『回滚开关三行』，并在 T7 报告（本脚本输出）中标注本 MIG-1/2 在
    干净首发包中 SKIP，迁移复核应在开发 worktree 或发布机进行。"""
    old_db = _BACKEND / "data" / "app.db"
    if old_db.is_file():
        # 开发 worktree 环境 → 执行严格断言（和上一轮 MIG-1 行为一致）
        assert old_db.stat().st_size > 0, f"旧 DB 存在但为空: {old_db}"
        ctx._last_old_db = str(old_db)
    else:
        # T8 干净首发包 → 记录为 SKIP（非失败）
        raise Suspend("T8 干净首发包不含 C 类 backend/data/app.db，本用例 SKIP。迁移复核请在开发 worktree 或发布机执行。")

@case("MIG", "2", "干净 runtime 下跑迁移：新旧 DB 表数/记录数完全一致")
def _(ctx: RunCtx):
    """T8 干净首发包中没有旧库 → MIG-2 SKIP；开发 worktree 中照常执行严格断言。"""
    old_db = _BACKEND / "data" / "app.db"
    if not old_db.is_file():
        raise Suspend("T8 干净首发包无旧 backend/data/app.db（符合 C 类隔离设计），本用例 SKIP。")

    # 用 clean runtime（临时空目录）强制迁移
    clean_root = ctx.clean_runtime
    os.environ["RESUME_DATA_DIR"] = str(clean_root)
    try:
        # 需要 reload settings / database.session 以强制用干净 runtime
        from core import config as _cfg_m
        import importlib as _il
        _il.reload(_cfg_m)
        from core.config import settings as S
        assert S.RESUME_DATA_DIR.resolve() == clean_root.resolve()
        import database.session as _s_m
        _il.reload(_s_m)
        import database.init_db as _i_m
        _il.reload(_i_m)
        # 调用迁移脚本的主逻辑
        from _v14_t3_migrate import do_migrate
        report = do_migrate(
            backend_root=_BACKEND,
            settings_module=None,
            rebuild_vectors=False,   # T7 不触发 RAG upsert（沙箱缺 key SUSPEND）
            strict_sql=True,
        )
        sql_eq = report.get("sql_identical") or {}
        require_keys = ["tables_equal","counts_equal","users_ids_set_equal",
                        "experiences_ids_set_equal","jobs_ids_set_equal"]
        for k in require_keys:
            assert sql_eq.get(k) is True, f"迁移一致性失败: {k}={sql_eq.get(k)}"
        assert report.get("OLD_DATA_NOT_DELETED") is True, "旧 DB 不应被删除"
        counts = sql_eq.get("new_counts", {})
        assert counts.get("experiences") == 5 and counts.get("users") == 1 and counts.get("vector_index_jobs") == 9, (
            f"记录数不符合 V1.4 基线(5/1/9): {counts}"
        )
    finally:
        os.environ.pop("RESUME_DATA_DIR", None)

@case("MIG", "3", "向量重建（⚠️SUSPEND：需本机 ARK_API_KEY）")
def _(ctx: RunCtx):
    # 纯 SUSPEND 占位：在本机有 API Key 环境下跑 `python _v14_t3_migrate.py --rebuild-vectors`
    raise Suspend("需要在机器配置 ARK_API_KEY 后，手动在 backend 目录执行: python _v14_t3_migrate.py")


# ============================================================
# 驱动
# ============================================================

def prepare_clean_runtime(tmpbase: str) -> Path:
    clean = Path(tmpbase) / f"t7-runtime-{int(time.time())}"
    if clean.exists(): shutil.rmtree(clean, ignore_errors=True)
    clean.mkdir(parents=True, exist_ok=True)
    return clean


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tmpdir", default=None, help="临时 clean runtime 根目录（默认使用系统 tempfile.gettempdir）")
    ap.add_argument("--report", default=None, help="输出 JSON 报告路径")
    args = ap.parse_args()

    tmpbase = args.tmpdir or tempfile.gettempdir()
    clean_runtime = prepare_clean_runtime(tmpbase)
    clean_runtime = clean_runtime.resolve()
    ctx = RunCtx(
        clean_runtime=clean_runtime,
        clean_sqlite=clean_runtime/"database"/"app.db",
        clean_output=clean_runtime/"output",
    )

    print(f"\nT7 回归环境：")
    print(f"  backend   = {_BACKEND}")
    print(f"  clean RDD = {ctx.clean_runtime}")
    print()

    t0 = time.perf_counter()
    for c in _ALL_CASES:
        run_case(ctx, c)
    total_ms = round((time.perf_counter() - t0) * 1000, 1)

    # 汇总
    pass_n = sum(1 for r in ctx.results if r.status == "PASS")
    fail_n = sum(1 for r in ctx.results if r.status == "FAIL")
    susp_n = sum(1 for r in ctx.results if r.status == "SUSPEND")
    print()
    print("=" * 72)
    print(f"T7 汇总：total={len(ctx.results)}  PASS={pass_n}  FAIL={fail_n}  SUSPEND={susp_n}  duration_ms={total_ms}")
    print("=" * 72)

    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "backend_root": str(_BACKEND),
        "clean_runtime": str(ctx.clean_runtime),
        "total": len(ctx.results), "pass": pass_n, "fail": fail_n, "suspend": susp_n,
        "duration_ms": total_ms,
        "cases": [r.__dict__ for r in ctx.results],
    }
    if args.report:
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON 报告写入: {args.report}")
    else:
        print("（如需 JSON 报告，下次加 --report=...）")

    return 1 if fail_n else 0


if __name__ == "__main__":
    raise SystemExit(main())
