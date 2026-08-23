"""单条可运行的 Stub Demo。

T5 要求：「补虚构 Demo Profile/经历/JD + 单条可运行演示入口」。
本脚本**不依赖任何外部 API Key 或网络**：
- 不从 JDAnalyzer / LLM / Embedding 取结果（V1.5.0 链路全部 stub 化）；
- V1.5.0：向量持久化统一走 SQLite 派生表（fact_embeddings），无独立 vectorstore
  目录、无 Chroma/numpy+JSON 后端、无向量同步副作用；
- 所有输入来自 `../input/demo_*.json / demo_jd.txt`（完全虚构的 Demo 数据）；
- 最终在 `DOCX_OUTPUT_DIR`（默认 runtime root）下输出 `demo_resume.docx`。
"""
from __future__ import annotations

import json
import os
import re
import sys
import shutil
from datetime import datetime
from pathlib import Path

# V1.4：强制不走本地 .env 里的旧路径 env，确保演示结果落在统一 runtime root 下
for _k in ['SQLITE_PATH','CHROMA_PATH','DOCX_OUTPUT_DIR','RESUME_DATA_DIR']:
    os.environ.pop(_k, None)
try:
    import dotenv  # type: ignore
    dotenv.load_dotenv = lambda *a, **kw: False  # patch before any module imports
except Exception:
    pass

_BACKEND_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _BACKEND_DIR.parent
_INPUT_DIR = _REPO_ROOT / "input"
assert (_INPUT_DIR / "demo_profile.json").exists(), "找不到 input/demo_profile.json，请确认 V1.4 源码树完整。"

sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy.orm import Session

from core.config import settings
from core.version import APP_VERSION
from database import models
from database.init_db import init_db
from database.session import SessionLocal, engine

from api.schemas import JDAnalysisOut, GeneratedResumeContent, GeneratedExperienceItem

from models.resume_document import ResumeDocument, Profile, WorkItem, EducationItem, ProjectItem

from services import resume_builder, layout_optimizer
from services.template_renderer import TemplateRenderer

DEMO_USER_ID = "demo_user_stub_v14"
DEMO_TEMPLATE_ID = "pm_template"


# ──────────────────────────────────────────────────────────────────── #
# 1. 读 Demo 数据
# ──────────────────────────────────────────────────────────────────── #

def load_demo_data() -> tuple[dict, list[dict], str]:
    with (_INPUT_DIR / "demo_profile.json").open("r", encoding="utf-8") as f:
        profile = json.load(f)
    with (_INPUT_DIR / "demo_experiences.json").open("r", encoding="utf-8") as f:
        experiences = json.load(f)
    jd_text = (_INPUT_DIR / "demo_jd.txt").read_text(encoding="utf-8")
    return profile, experiences, jd_text


def parse_jd_demo(jd_text: str) -> JDAnalysisOut:
    """完全本地的 JD 解析（演示用，不调 LLM）：从 demo_jd.txt 关键词启发式抽。"""
    lines = [ln.strip() for ln in jd_text.splitlines() if ln.strip()]

    position = ""
    industry = ""
    for ln in lines:
        if not position and "岗位" in ln:
            m = re.search(r"岗位[:：]\s*([^，。、\(（]+)", ln)
            if m:
                position = m.group(1).strip()
        if not industry and "公司名称" in ln:
            m = re.search(r"公司名称[:：]\s*([^，。、\(（]+)", ln)
            if m:
                industry = m.group(1).strip()
    if not position:
        position = "高级后端研发工程师（Java）"
    # 启发式技能 / 职责关键词
    kw_blacklist = {"的","和","与","及","或","等","在","对","包括","确保","要求","职责","岗位","具备","包含"}
    required = []
    preferred = []
    responsibilities = []
    in_req = False
    in_resp = False
    for ln in lines:
        if "岗位要求" in ln or "任职要求" in ln:
            in_req, in_resp = True, False; continue
        if "岗位职责" in ln:
            in_req, in_resp = False, True; continue
        if "岗位" in ln and not ln.startswith("岗位"):
            in_req = in_resp = False
        num_bullet = re.match(r"^\s*\d+[、.．]\s*(.+)$", ln)
        if num_bullet:
            content = num_bullet.group(1).strip()
            if in_resp and len(responsibilities) < 6:
                responsibilities.append(content)
            elif in_req:
                if not preferred and len(required) >= 3:
                    preferred.append(content)
                elif len(required) < 5:
                    required.append(content)
    # 从全文抽技能词
    tech_tokens = ["Java","Spring","Spring Boot","MyBatis","MySQL","Redis","Kafka","MQ","SQL","分布式",
                   "高并发","高可用","K8s","Docker","Hive","Airflow","Git","Python"]
    keywords = [t for t in tech_tokens if re.search(re.escape(t), jd_text, flags=re.IGNORECASE)]
    experience_preferences = ["3-6 年后端经验", "计算机相关专业"]
    if not required:
        required = ["Java 基础扎实", "熟悉 Spring Boot / MySQL / Redis", "具备高并发系统开发经验"]
    if not responsibilities:
        responsibilities = ["负责交易链路系统设计与编码", "主导性能优化与稳定性保障", "与产品/前端协作推动项目"]
    if not keywords:
        keywords = ["Java","MySQL","Redis","高性能"]
    return JDAnalysisOut(
        position=position,
        industry=industry,
        required_skills=required,
        preferred_skills=preferred,
        responsibilities=responsibilities,
        keywords=keywords,
        experience_preferences=experience_preferences,
    )


# ──────────────────────────────────────────────────────────────────── #
# 2. 初始化 DB + 写 Demo 数据（幂等：先清旧 demo user 再写入）
# ──────────────────────────────────────────────────────────────────── #

def seed_demo_db(profile: dict, experiences: list[dict]) -> list[models.Experience]:
    init_db()
    db: Session = SessionLocal()
    try:
        # 清理旧 demo user（级联删 experiences / jobs）
        old = db.query(models.User).filter(models.User.id == DEMO_USER_ID).first()
        if old:
            db.delete(old)
            db.commit()
        user = models.User(
            id=DEMO_USER_ID,
            name=profile.get("name") or "",
            email=profile.get("email") or "",
        )
        db.add(user)
        db.flush()

        # Education：profile.education → Experience(type=education)
        edu_exps: list[models.Experience] = []
        for edu in (profile.get("education") or []):
            school = edu.get("school","")
            major = edu.get("major","")
            degree = edu.get("degree","")
            start_d = edu.get("start_date","").replace("/",".")
            end_d = edu.get("end_date","").replace("/",".")
            time_str = f"{start_d} - {end_d}"
            desc_bits = [f"学历：{degree}" if degree else ""]
            if edu.get("gpa"): desc_bits.append(f"GPA：{edu['gpa']}")
            description = "\n".join([b for b in desc_bits if b]) or f"{school} / {major}"
            achievements: list = []
            if edu.get("awards"): achievements = list(edu["awards"])
            exp = models.Experience(
                id=f"edu_{DEMO_USER_ID}_{re.sub(r'[^A-Za-z0-9]+','_', school or 'edu').strip('_')}",
                user_id=user.id,
                type="education",
                title=school,
                company="",
                time=time_str,
                role=major,
                description=description,
                skills=[],
                achievements=achievements,
                raw_text=(f"{school} {major} {degree} {time_str}\n{description}").strip(),
            )
            db.add(exp); edu_exps.append(exp)

        # Work：demo_experiences → Experience(type=work)
        work_exps: list[models.Experience] = []
        for d in experiences:
            exp_id = d.get("id") or re.sub(r'[^A-Za-z0-9]+','_', (d.get("company","")+d.get("job_title","")).strip('_'))
            start_d = (d.get("start_date","")).replace("/",".")
            end_d = (d.get("end_date","")).replace("/",".")
            time_str = f"{start_d} - {end_d}" if (start_d or end_d) else ""
            desc_lines = d.get("responsibilities") or []
            desc = "\n".join([ln for ln in desc_lines if isinstance(ln,str)])
            achievements = [x for x in (d.get("achievements") or []) if isinstance(x,str)]
            skills = [x for x in (d.get("skills") or []) if isinstance(x,str)]
            raw_chunks = [
                d.get("job_title","") or "",
                d.get("company","") or "",
                time_str,
                d.get("department","") or "",
                d.get("summary","") or "",
                desc,
                achievements and ("成果：" + "；".join(achievements)) or "",
            ]
            exp = models.Experience(
                id=exp_id,
                user_id=user.id,
                type="work",
                title=d.get("job_title","") or "",
                company=d.get("company","") or "",
                time=time_str,
                role=d.get("department","") or "",
                description=desc,
                skills=skills,
                achievements=achievements,
                raw_text="\n".join([c.strip() for c in raw_chunks if str(c).strip()]),
            )
            db.add(exp); work_exps.append(exp)

        # Project：从 demo_experiences 拆出项目条目，保证 ResumeBuilder.build 的 projects 章节至少 1 条
        project_exps: list[models.Experience] = []
        for idx, d in enumerate(experiences):
            company = d.get("company") or "示例公司"
            proj_name = f"{company}·核心项目{idx+1}"
            resp_lines = d.get("responsibilities") or []
            ach_lines = d.get("achievements") or []
            start_d = (d.get("start_date","")).replace("/",".")
            end_d = (d.get("end_date","")).replace("/",".")
            bullets = (resp_lines + ach_lines)[:6]
            desc = "\n".join(bullets) or f"{proj_name} 项目描述"
            skills = d.get("skills") or []
            exp_id = f"proj_{DEMO_USER_ID}_{idx}"
            exp = models.Experience(
                id=exp_id,
                user_id=user.id,
                type="project",
                title=proj_name,
                company=company,
                time=f"{start_d} - {end_d}",
                role=d.get("job_title","") or "后端",
                description=desc,
                skills=skills,
                achievements=ach_lines[:3],
                raw_text=f"{proj_name}\n{company} ({start_d} - {end_d})\n{desc}",
            )
            db.add(exp); project_exps.append(exp)

        db.commit()
        # T9 修复：session 关闭前把关联字段预取出来，避免外层遍历触发 DetachedInstanceError
        _ = [e.type for e in edu_exps]
        _ = [e.description for e in work_exps]
        _ = [e.achievements for e in work_exps]
        _ = [e.type for e in project_exps]
        _ = [e.description for e in project_exps]
        _ = [e.achievements for e in project_exps]
        return edu_exps + work_exps + project_exps
    finally:
        db.close()


# ──────────────────────────────────────────────────────────────────── #
# 3. 模拟 RAG 检索结果 + 生成内容（都是假的，不联网）
# ──────────────────────────────────────────────────────────────────── #

def fake_rag_matched(work_exps: list[models.Experience],
                    project_exps: list[models.Experience] | None = None,
                    top_k: int = 5) -> list[dict]:
    """把 demo 的 work 条目 + project 条目假装 RAG 检索命中，final_score 按顺序给高分。

    关键：projects 也必须出现在 matched 里；否则 ResumeBuilder.build 的
    `elif exp.type == "project" and exp.id in matched_ids` 分支永远跳过，
    导致必填章节 projects 无条目。
    """
    result = []
    all_candidates = []
    for exp in work_exps[:top_k]:
        all_candidates.append(("work", exp))
    for exp in (project_exps or [])[:top_k]:
        all_candidates.append(("project", exp))
    # work 优先（分数高一点），project 跟随，都在同一 matched 池
    for i, (_t, exp) in enumerate(all_candidates[:max(top_k, 4)]):
        score = 0.94 - i * 0.04
        result.append({
            "id": exp.id,
            "experience_id": exp.id,
            "final_score": round(score, 3),
            "rerank_score": round(score, 3),
            "chunk_text": (exp.description or "") + "\n" + "\n".join(exp.achievements or []),
        })
    return result


def fake_generated_content(work_exps: list[models.Experience],
                          project_exps: list[models.Experience] | None = None) -> GeneratedResumeContent:
    """模拟 ResumeContentGenerator 输出 —— bullets 直接抄 SQL 的 responsibilities+achievements。

    这样 AI bullets 与 SQL 事实一致，ResumeBuilder 的『AI 回退 SQL』路径也能走通，
    同时满足 PLAN §3.3『AI 只能改 bullets 文本，不能改公司/岗位/时间』的事实边界。
    """
    def _to_bullets(exp: models.Experience) -> list[str]:
        bullets: list[str] = []
        resp_lines = [ln.strip() for ln in (exp.description or "").splitlines() if ln.strip()]
        for line in resp_lines[:6]:
            bullets.append(line)
        for ach in (exp.achievements or []):
            s = str(ach).strip()
            if s:
                bullets.append(s)
        return bullets

    items = []
    for exp in work_exps:
        items.append(GeneratedExperienceItem(
            experience_id=exp.id,
            bullets=_to_bullets(exp),
        ))
    # project 也必须在 generated_content 里有条目，否则 ResumeBuilder 走 SQL fallback
    for exp in (project_exps or []):
        items.append(GeneratedExperienceItem(
            experience_id=exp.id,
            bullets=_to_bullets(exp),
        ))
    return GeneratedResumeContent(experiences=items)


# ──────────────────────────────────────────────────────────────────── #
# 4. 构造 request_profile（传给 ResumeBuilder.build 的身份字段唯一来源）
# ──────────────────────────────────────────────────────────────────── #

def to_request_profile(profile: dict, jd_position: str) -> dict:
    return {
        "name": profile.get("name") or "",
        "phone": profile.get("phone") or "",
        "email": profile.get("email") or "",
        "location": profile.get("city") or "",
        # target_position 只取 JD，不在 request 里塞；这里保留意图说明但构建器会忽略
        "job_intent": profile.get("job_intent") or "",
    }


# ──────────────────────────────────────────────────────────────────── #
# 主流程
# ──────────────────────────────────────────────────────────────────── #

def main() -> int:
    print("=" * 72)
    print(f" Resume Assistant V{APP_VERSION} — Stub Demo（无 API Key / 无网络）")
    print("=" * 72)
    print(f" repo root       = {_REPO_ROOT}")
    print(f" backend root    = {settings.BASE_DIR}")
    print(f" RESUME_DATA_DIR = {settings.RESUME_DATA_DIR}")
    print(f" SQLITE_PATH     = {settings.SQLITE_PATH}")
    print(f" DOCX_OUTPUT_DIR = {settings.DOCX_OUTPUT_DIR}")

    profile, demo_exps, jd_text = load_demo_data()
    jd = parse_jd_demo(jd_text)
    print(f"\n[OK] JD position = {jd.position!r}")
    print(f"[OK] JD required_skills = {len(jd.required_skills)} 条")
    print(f"[OK] Demo experiences   = {len(demo_exps)} 条")

    all_exps = seed_demo_db(profile, demo_exps)
    work_exps = [e for e in all_exps if e.type == "work"]
    edu_exps = [e for e in all_exps if e.type == "education"]
    project_exps = [e for e in all_exps if e.type == "project"]
    print(f"[OK] Demo 用户已落盘：user_id={DEMO_USER_ID!r}")
    print(f"     · work 经历 = {len(work_exps)} 条")
    print(f"     · edu 经历  = {len(edu_exps)} 条")
    print(f"     · project 经历 = {len(project_exps)} 条")

    matched = fake_rag_matched(work_exps, project_exps=project_exps, top_k=5)
    print(f"[OK] 模拟 RAG 命中 = {len(matched)} 条（top_k=5）")

    generated = fake_generated_content(work_exps, project_exps=project_exps)
    print(f"[OK] 模拟 ResumeContentGenerator 覆盖 = {len(generated.experiences)} 条")

    request_profile = to_request_profile(profile, jd.position)
    db: Session = SessionLocal()
    try:
        resume_doc: ResumeDocument
        build_meta: dict
        resume_doc, build_meta = resume_builder.build(
            db,
            user_id=DEMO_USER_ID,
            matched_experiences=matched,
            jd_analysis=jd,
            all_experiences=all_exps,
            request_profile=request_profile,
            generated_content=generated,
            max_education=3, max_work=3, max_projects=3, max_awards=5,
        )
    finally:
        db.close()
    counts = build_meta.get("counts", {}) or {}
    print(f"[OK] ResumeBuilder 输出条目：education={counts.get('education',0)}, work={counts.get('work',0)}, projects={counts.get('projects',0)}")

    backend_root = str(settings.BASE_DIR)
    renderer = TemplateRenderer(DEMO_TEMPLATE_ID, backend_root=backend_root)
    doc, render_warnings, render_stats = renderer.render(resume_doc)

    page_limit = renderer.spec.layout.page_limit
    applied_layout_rules, capacity_warnings = layout_optimizer.optimize(doc, page_limit=page_limit)
    layout_optimizer.remove_blank_trailing_pages(doc)
    final_page_count = layout_optimizer.estimate_pages(doc)
    print(f"[OK] 渲染完成：pages~{final_page_count}（limit≤{page_limit}）")
    if applied_layout_rules:
        print(f"     · 排版降级规则：{len(applied_layout_rules)} 条")
    if capacity_warnings:
        for w in capacity_warnings: print(f"     · CAPACITY WARN: {w}")
    if render_stats.get("unreplaced_placeholders"):
        print(f"     · ⚠️ 未替换占位符 = {render_stats['unreplaced_placeholders']}")

    # 9. 保存 DOCX 到 DOCX_OUTPUT_DIR
    output_dir = Path(settings.DOCX_OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / "demo_resume.docx"
    doc.save(str(out_file))
    size_kb = round(out_file.stat().st_size / 1024, 1)
    print(f"\n✅ Stub Demo 完成！")
    print(f"   · DOCX：{out_file}  ({size_kb} KB)")
    print(f"   · 页面估计：{final_page_count} 页")
    print(f"   · 命中条目：{[m['id'] for m in matched]}")
    print(f"\n提示：如需演示 API（带真实 LLM），请在 backend/.env 填入 ARK_API_KEY 后运行：")
    print(f"   uvicorn main:app --host 127.0.0.1 --port 8000 --reload")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
