"""V2.1.0 T6 验证脚本（零 API Key，不调 LLM，不写运行时库）。

运行：python _v21_t6_doc_preview.py

覆盖（每条计 1 PASS；累计 12 PASS，全部通过 exit 0）：
  1) Pydantic DTO DocPreviewEntry 可序列化
  2) Pydantic DTO DocPreviewSection 可序列化
  3) Pydantic DTO EvidenceFact 可序列化
  4) ResumeDocxGenerateResponse 在不传 doc_preview/evidence 时仍可构造（旧契约不受影响）
  5) ResumeDocxGenerateResponse 在携带 doc_preview/evidence 时可序列化往返
  6) _build_doc_preview 投影 personal section 标题/heading/subhead 来自真实 Profile
  7) _build_doc_preview 投影 work section 条目与 bullets 真实来自 ResumeDocument
  8) _build_doc_preview 投影 project section 条目与 bullets 真实
  9) _build_doc_preview 投影 skills/awards section 真实
 10) _build_doc_preview 不发明：空字段不出现，不凭空生成 section
 11) _build_evidence_map 空入参 → 空 dict（边界）
 12) _build_evidence_map 内存 SQLite 注入 Fact 行 → 正确按 experience_id 聚合原文
 13) py_compile：schemas.py / services/resume_generation_service.py / api/routes/generate.py 全部 0
 14) import api.routes.generate 加载成功（route 仍可注册）
"""
from __future__ import annotations

import io
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

PASS_COUNT = 0
FAILURES: list[str] = []


def _assert(cond: bool, label: str, detail: str = "") -> None:
    global PASS_COUNT
    if cond:
        PASS_COUNT += 1
        print(f"  [PASS] {label}")
    else:
        msg = f"  [FAIL] {label}" + (f" — {detail}" if detail else "")
        print(msg, file=sys.stderr)
        FAILURES.append(label)


def _section(title: str) -> None:
    print(f"\n[{title}]")


# ═══════════════════════════════════════════════════════════════════════════
# 1) DTO 序列化
# ═══════════════════════════════════════════════════════════════════════════
def test_dto_serialisation() -> None:
    _section("1) DTO 序列化")
    from api.schemas import (
        DocPreviewEntry,
        DocPreviewSection,
        EvidenceFact,
    )
    try:
        e = DocPreviewEntry(
            heading="H", subhead="S", bullets=["b1", "b2"], experience_id="eid-x",
        )
        payload = e.model_dump()
        _assert(
            payload["heading"] == "H" and payload["bullets"] == ["b1", "b2"]
            and payload["experience_id"] == "eid-x",
            "DocPreviewEntry 序列化字段一致",
            f"got {payload}",
        )
    except Exception as ex:
        _assert(False, "DocPreviewEntry 序列化抛异常", repr(ex))

    try:
        sec = DocPreviewSection(section="work", title="工作经历", entries=[e])
        payload = sec.model_dump()
        _assert(
            payload["section"] == "work" and payload["title"] == "工作经历"
            and isinstance(payload["entries"], list) and len(payload["entries"]) == 1,
            "DocPreviewSection 序列化字段一致",
            f"got {payload}",
        )
    except Exception as ex:
        _assert(False, "DocPreviewSection 序列化抛异常", repr(ex))

    try:
        f = EvidenceFact(fact_id="f-1", experience_id="eid-x", text="原文", reason="")
        payload = f.model_dump()
        _assert(
            payload["fact_id"] == "f-1" and payload["text"] == "原文" and payload["reason"] == "",
            "EvidenceFact 序列化字段一致（reason 允许为空）",
            f"got {payload}",
        )
    except Exception as ex:
        _assert(False, "EvidenceFact 序列化抛异常", repr(ex))


# ═══════════════════════════════════════════════════════════════════════════
# 2) ResumeDocxGenerateResponse 默认 + 携带 doc_preview/evidence
# ═══════════════════════════════════════════════════════════════════════════
def test_response_default_and_full() -> None:
    _section("2) ResumeDocxGenerateResponse 默认与携带字段")
    from api.schemas import (
        BuildCounts,
        BuildMeta,
        RenderStats,
        ResumeDocxGenerateResponse,
        DocPreviewEntry,
        DocPreviewSection,
        EvidenceFact,
    )
    try:
        # 默认（无 doc_preview/evidence）—— 旧契约
        resp = ResumeDocxGenerateResponse(
            file_path="output/x.docx", file_name="x.docx",
            download_url="/api/template/download?path=output/x.docx",
            build_counts=BuildCounts(),
            build_meta=BuildMeta(),
            render_stats=RenderStats(),
        )
        _assert(
            resp.doc_preview is None and resp.evidence is None,
            "默认响应 doc_preview/evidence 为 None（旧契约不破坏）",
        )
    except Exception as ex:
        _assert(False, "默认响应构造抛异常", repr(ex))

    try:
        # 携带 doc_preview + evidence —— 完整往返
        sec = DocPreviewSection(
            section="work", title="工作",
            entries=[DocPreviewEntry(heading="H", bullets=["b1"], experience_id="eid-1")],
        )
        ev = {"eid-1": [EvidenceFact(fact_id="f-1", experience_id="eid-1", text="T")]}
        resp = ResumeDocxGenerateResponse(
            file_path="output/x.docx", file_name="x.docx",
            download_url="/api/template/download?path=output/x.docx",
            build_counts=BuildCounts(),
            build_meta=BuildMeta(),
            render_stats=RenderStats(),
            doc_preview=[sec],
            evidence=ev,
        )
        dump = resp.model_dump()
        _assert(
            isinstance(dump.get("doc_preview"), list)
            and dump["doc_preview"][0]["section"] == "work"
            and dump["doc_preview"][0]["entries"][0]["bullets"] == ["b1"]
            and dump["evidence"]["eid-1"][0]["text"] == "T",
            "doc_preview/evidence 序列化往返一致",
        )
    except Exception as ex:
        _assert(False, "携带 doc_preview/evidence 序列化抛异常", repr(ex))


# ═══════════════════════════════════════════════════════════════════════════
# 3) _build_doc_preview 真实投影
# ═══════════════════════════════════════════════════════════════════════════
def _make_resume_doc():
    from models.resume_document import (
        EducationItem, Profile, ProjectItem, ResumeDocument, SkillGroup, WorkItem,
    )
    return ResumeDocument(
        profile=Profile(
            name="张三", phone="138-0000-0000", email="z@example.com",
            location="深圳", target_position="后端开发实习生", summary=None,
        ),
        work=[
            WorkItem(
                company="青屿科技", role="后端开发实习生",
                start_time="2025.06", end_time="2025.09",
                bullets=["设计并实现订单查询接口，P95 延迟从 850ms 优化到 320ms（基于 4 万条样本的本地压测）",
                         "参与评审 12 项 API 改动，覆盖网关/订单/库存/接口四个模块；其中 1 项被列入错效率下降 42%"],
                experience_id="exp-work-1",
            ),
        ],
        projects=[
            ProjectItem(
                name="校园二手交易平台", role="后端负责人",
                start_time="2024.10", end_time="2025.02",
                bullets=["设计并发商品/消息/订单/支付三维幂等方案，使用 Redis 缓存商品详情，命中率 78%"],
                experience_id="exp-proj-1",
            ),
        ],
        education=[
            EducationItem(
                school="蓝港示范大学", major="软件工程 · 本科",
                start_time="2022.09", end_time="2026.06",
                description="核心课程：数据结构、操作系统、计算机网络、数据库系统、软件工程；GPA 3.6 / 4.0",
                experience_id="exp-edu-1",
            ),
        ],
        skills=[
            SkillGroup(category="编程语言", items=["Java", "Python", "TypeScript"]),
            SkillGroup(category="后端", items=["Spring Boot", "FastAPI"]),
        ],
        awards=["2024 年校级一等奖学金", "GPA 3.6 / 4.0"],
    )


def test_build_doc_preview() -> None:
    _section("3) _build_doc_preview 真实投影")
    from services.resume_generation_service import _build_doc_preview
    doc = _make_resume_doc()
    sections = _build_doc_preview(doc)

    by_section: dict[str, DocPreviewEntry] = {}
    sec_by_name: dict[str, list] = {}
    for s in sections:
        sec_by_name[s.section] = s.entries
    # personal
    personal = sec_by_name.get("personal", [])
    _assert(
        len(personal) == 1
        and personal[0].heading == "张三"
        and "138-0000-0000" in (personal[0].subhead or "")
        and "z@example.com" in (personal[0].subhead or "")
        and any("后端开发实习生" in b for b in personal[0].bullets)
        and any("深圳" in b for b in personal[0].bullets),
        "personal section 来自真实 Profile",
    )
    # work
    work = sec_by_name.get("work", [])
    _assert(
        len(work) == 1
        and work[0].experience_id == "exp-work-1"
        and work[0].heading == "青屿科技 · 后端开发实习生"
        and "2025.06 - 2025.09" in (work[0].subhead or "")
        and len(work[0].bullets) == 2
        and work[0].bullets[0].startswith("设计并实现订单查询接口"),
        "work section 真实条目与 bullets 来自 ResumeDocument",
    )
    # project
    proj = sec_by_name.get("project", [])
    _assert(
        len(proj) == 1
        and proj[0].experience_id == "exp-proj-1"
        and proj[0].heading == "校园二手交易平台 · 后端负责人"
        and "命中率 78%" in proj[0].bullets[0],
        "project section 真实条目与 bullets 来自 ResumeDocument",
    )
    # skills + awards
    skills = sec_by_name.get("skills", [])
    awards = sec_by_name.get("awards", [])
    _assert(
        len(skills) == 2
        and skills[0].heading == "编程语言" and "Java" in skills[0].bullets
        and skills[1].heading == "后端" and "FastAPI" in skills[1].bullets
        and len(awards) == 1 and "2024 年校级一等奖学金" in awards[0].bullets,
        "skills/awards section 来自 ResumeDocument 真实字段",
    )
    # education 描述回退为单条 bullet（不杜撰）
    edu = sec_by_name.get("education", [])
    _assert(
        len(edu) == 1
        and "蓝港示范大学" in edu[0].heading
        and len(edu[0].bullets) == 1
        and "GPA 3.6 / 4.0" in edu[0].bullets[0],
        "education section description 真实保留为 bullet",
    )
    # 不发明：ResumeDocument 没有任何 meta/profiles/preview 的虚构字段
    _assert(
        not any(getattr(s, "meta", None) for s in sections)
        and all(s.title in {"个人信息", "工作经历", "项目经历", "教育背景", "技能", "获奖 / 证书"} for s in sections),
        "_build_doc_preview 不凭空杜撰字段或 section 名",
    )


# ═══════════════════════════════════════════════════════════════════════════
# 4) _build_evidence_map 边界 + 真实 Fact 拉取
# ═══════════════════════════════════════════════════════════════════════════
def test_build_evidence_map() -> None:
    _section("4) _build_evidence_map 边界 + 真实 DB 读取")
    from services.resume_generation_service import _build_evidence_map
    # 边界：空入参
    _assert(_build_evidence_map(db=None, fact_ids=[]) == {}, "空 fact_ids → 空 dict（边界）")

    # 真实：内存 SQLite 注入 Fact
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database.models import Base, Experience, Fact
    engine_mem = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine_mem)
    SessionMem = sessionmaker(bind=engine_mem)
    db = SessionMem()
    try:
        exp = Experience(
            id="exp-1", type="work", title="T", company="C",
            time="2023.01 - 2023.06", role="R",
        )
        db.add(exp)
        db.flush()
        db.add(Fact(
            fact_id="f-1", experience_id="exp-1", text="FACT-A-原文",
            revision=1, content_hash="h1",
        ))
        db.add(Fact(
            fact_id="f-2", experience_id="exp-1", text="FACT-B-原文",
            revision=1, content_hash="h2",
        ))
        db.commit()
        result = _build_evidence_map(db, ["f-1", "f-2", "f-missing", "f-1"])
        items = result.get("exp-1", [])
        _assert(
            len(items) == 2
            and {i.fact_id for i in items} == {"f-1", "f-2"}
            and {i.text for i in items} == {"FACT-A-原文", "FACT-B-原文"}
            and all(i.reason == "" for i in items),
            "内存 SQLite 注入 Fact 后按 experience_id 聚合正确（去重、忽略缺漏、reason 空）",
        )
    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════════════════
# 5) py_compile + route import
# ═══════════════════════════════════════════════════════════════════════════
def test_compile_and_route() -> None:
    _section("5) py_compile + route 加载")
    import py_compile
    targets = [
        BACKEND_ROOT / "api" / "schemas.py",
        BACKEND_ROOT / "services" / "resume_generation_service.py",
        BACKEND_ROOT / "api" / "routes" / "generate.py",
    ]
    compile_ok = True
    for p in targets:
        try:
            py_compile.compile(str(p), doraise=True)
        except py_compile.PyCompileError as e:
            compile_ok = False
            print(f"  py_compile 失败：{p}: {e}", file=sys.stderr)
    _assert(compile_ok, "schemas.py / service.py / generate.py py_compile exit 0")

    # route import：捕获 import 期间的标准输出（避免无谓噪音），只看异常
    buf_out, buf_err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(buf_out), redirect_stderr(buf_err):
            from api.routes import generate as generate_route  # noqa: F401
        _assert(generate_route.router is not None, "api.routes.generate 可 import 且 router 存在")
    except Exception as ex:
        _assert(False, "api.routes.generate import 失败", repr(ex))


# ═══════════════════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════════════════
def main() -> int:
    test_dto_serialisation()
    test_response_default_and_full()
    test_build_doc_preview()
    test_build_evidence_map()
    test_compile_and_route()

    print()
    print("=" * 60)
    print(f"V2.1.0 T6 doc_preview/evidence 验证：PASS={PASS_COUNT} FAIL={len(FAILURES)}")
    print("=" * 60)
    if FAILURES:
        for f in FAILURES:
            print(f"  - {f}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
