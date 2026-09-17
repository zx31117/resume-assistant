"""V2.2.0 T07：任务生成结果 → ResumeDocument 的纯逻辑装配，与 P4 assembler 接入真实 DOCX/PDF 链。

设计约束（PLAN §V220-G05 / §6.3）：
- 全部为确定性纯函数（不调 LLM/DB/Word），便于独立测试；
- 联系方式：唯一来源是输入（name/phone/email/location）；Unicode/空白归一，
  缺失字段留空、绝不回填模板/DB；
- 教育：学校/专业/学历/时间保持独立语义；专业在外、学历在括号内，缺任一字段
  不输出空括号，禁止倒置/重复括号/`本科（）`；
- 观点 headline/body：headline 只做加粗简短标题+冒号，正文保持普通字重；
- 技能：2～4 个与 JD 相关、有 Fact 依据、可扫读的能力类别；事实不足时诚实减少
  类别，不得用内部实现词或关键词堆砌补数；类别与条目均保留 fact_refs；
- headline/body/skills/reason 的 fact_refs 一直保留到 ResumeDocument。

P4 装配入口 `assemble_and_render`：兼容 task_generation 的 assembler 钩子签名
 `(summary, compact) -> (assembled: bool, artifacts: dict)`，产出 DOCX（+同源 PDF）
 文件路径供 run_generation 调用 publish_artifacts 发布。
"""
from __future__ import annotations

import hashlib
import logging
import os
import unicodedata
import uuid
from typing import Any, Optional

from models.resume_document import (
    Profile,
    EducationItem,
    WorkItem,
    ProjectItem,
    SkillGroup,
    ResumeDocument,
)

logger = logging.getLogger(__name__)


# ── 归一化（T07a：Unicode/空白归一） ─────────────────────────────── #

def normalize_text(value: Optional[str]) -> str:
    """Unicode 归一（NFKC）+ 折叠空白。空/None → ""。

    用于**匹配类**文本（联系方式、技能 token、type/experience_id 等）：NFKC 把全角
    数字/字母/空白收敛到 ASCII，保证同一语义输入确定性相等。
    """
    if value is None:
        return ""
    try:
        folded = unicodedata.normalize("NFKC", str(value))
    except Exception:  # noqa: BLE001  个别输入异常时不阻断主链
        folded = str(value)
    return " ".join(folded.split())


def _display_text(value: Optional[str]) -> str:
    """展示文本归一：折叠空白 + 去除控制字符，但**保留全角字符**（NFKC 不适用）。

    简历正文/教育字段里的全角冒号 `：`、全角括号 `（）` 应原样保留（NFKC 会把它们
    收敛为 ASCII，破坏中文排版）。用于 headline/body、education school/major/degree。
    """
    if value is None:
        return ""
    s = str(value)
    s = "".join(ch for ch in s if ch.isprintable())
    return " ".join(s.split())


def normalize_contact(
    *,
    name: str = "",
    phone: str = "",
    email: str = "",
    location: str = "",
    target_position: str = "",
) -> Profile:
    """构造 Profile（联系方式唯一来源），T07a 无回填。

    - 全字段经 Unicode/空白归一；
    - 空缺字段留空（location 空→None），不抛错（合法状态）；
    - target_position 来自 compact JD（PLAN §3.3：求职意向只取 JD）。
    """
    loc = normalize_text(location)
    return Profile(
        name=normalize_text(name),
        phone=normalize_text(phone),
        email=normalize_text(email),
        location=loc or None,
        target_position=normalize_text(target_position),
        summary="",
    )


# ── 教育（T07d：专业在外、学历在括号内、缺字段不输出空括号） ────── #

def _has_paren(s: str) -> bool:
    """是否已含括号（中英文圆括号任一）。"""
    return any(ch in s for ch in "（）()")


def format_education_line(
    school: str = "",
    major: str = "",
    degree: str = "",
) -> str:
    """按 T07d 规则拼接「学校 [专业]（学历）」。

    规则：
      - 专业在外、学历在括号内；
      - 缺任一字段都不输出空括号（绝不产生 `本科（）` 或 `A大学（）`）；
      - 字段本身已带括号时不再包一层（不重复括号）。
    返回值恒不含空圆括号。
    """
    school = _display_text(school)
    major = _display_text(major)
    degree = _display_text(degree)

    parts: list[str] = []
    if school:
        parts.append(school)
    if major:
        parts.append(major)

    middle = " ".join(parts)
    if degree and not _has_paren(degree):
        degree_printed = f"（{degree}）"
    elif degree:
        degree_printed = degree  # 已带括号，不重复包裹
    else:
        degree_printed = ""

    return (" ".join(filter(None, [middle, degree_printed]))).strip()


# ── 观点 headline/body（T07c）：冒号边界 + 加粗分离 ──────────────── #

_FULL_COLON = "："
_SEP_CHARS = "：:"


def compose_fact_bullet(headline: str, body: str) -> str:
    """把 headline + body 合成一条 bullet 文本。

    - 仅当 headline 非空时加冒号：headline 尾部若已有冒号则不重复；
    - headline 为空、body 非空 → 直接返回 body（无孤立冒号）。
    返回文本供渲染层按 `headline：/body` 边界做标题加粗（见 template_renderer）。
    """
    h = _display_text(headline)
    b = _display_text(body)
    if h and b:
        if h[-1] in _SEP_CHARS:
            return h + b          # h 已带冒号，不重复、不插孤空白
        return h + _FULL_COLON + b
    if h:
        return h
    return b


def split_headline_boundary(text: str) -> tuple[str, str]:
    """按 T07c 加粗边界切分 `headline：body → (加粗部分含冒号, 普通正文)`。

    返回 (bold_part, body_part)；无法定位冒号时返回 (text, "")。
    headline 非空但 body 为空时冒号不单独出现，避免孤立冒号。
    """
    if not text:
        return "", ""
    for sep in (_FULL_COLON, ":"):
        idx = text.find(sep)
        if idx > 0:  # 冒号前至少一个字符才算标题
            head = text[: idx + len(sep)].rstrip()
            body = text[idx + len(sep):].strip()
            if head:
                return head, body
    return text, ""


# ── 技能（T07b：2~4 类、JD 相关、有 Fact 依据、可扫读） ──────────── #

# 能力类别启发式：把 JD 原子技能名归入可扫读类别（仅做归类，不做堆砌）
_SKILL_TAXONOMY: list[tuple[str, tuple[str, ...]]] = [
    ("编程语言与框架", ("python", "java", "c++", "c", "go", "javascript", "js", "typescript",
                       "react", "vue", "flutter", "spring", "django", "flask", "pytorch",
                       "tensorflow", "hadoop", "spark", "flink", "sql", "mysql", "redis",
                       "大模型", "深度学习", "机器学习", "nlp", "数据挖掘", "爬虫", "后端开发",
                       "前端开发", "微服务", "分布式")),
    ("工具与平台", ("git", "docker", "linux", "kubernetes", "k8s", "jenkins", "figma",
                   "axure", "jira", "gitlab", "ci/cd", "aws", "阿里云", "腾讯云", "office",
                   "excel", "word", "powpoint", "mysql", "mongodb")),
    ("领域与专业能力", ("需求分析", "产品设计", "数据分析", "项目管理", "运营策略", "用户研究",
                    "算法", "推荐系统", "搜索", "风控", "增长", "商业化", "供应链", "财务",
                    "法律", "广告营销")),
    ("通用能力", ("沟通", "协作", "团队", "抗压", "学习能力", "执行力", "责任心", "跨职能",
                "英语", "中文", "日语", "韩语")),
]

# 技能类别数量约束（T07b）：上限 4；下限不强凑（事实不足诚实减少）
_MAX_CATEGORIES = 4


def build_skill_groups(
    compact: dict[str, Any],
    experiences: list[Any],
    *,
    max_categories: int = _MAX_CATEGORIES,
) -> list[SkillGroup]:
    """从 compact JD + 已生成事实生成最多 4 个 JD 相关、有 Fact 依据的能力类别。

    依据判定（诚实减少、不堆砌，T07b）：
      - 候选技能 = compact.required_skills + preferred_skills（原子化）；
      - 某技能"有 Fact 依据" ⇔ 该技能名（小写）以子串形式出现在至少一条已生成
        事实的 headline/body 文本里；未命中者不进入技能区（宁可类别不足，不用
        内部实现词或关键词堆砌补数）。
      - 类别的 fact_refs = 支撑该类别所有成员技能的 facts 的 fact_refs 并集
        （成员技能的依据事实与其 fact_refs 一一对应，保证可核验）。

    每个 experience 需具备字段：facts（含 headline/body/fact_refs）。
    返回类别列表（0..4 个；无依据技能时返回空列表，渲染层按空技能区不展示）。
    """
    if not experiences:
        return []

    # 1) 汇总每条事实的（小写文本, fact_refs）
    fact_entries: list[tuple[str, list[str]]] = []
    for exp in experiences:
        for f in (getattr(exp, "facts", None) or []):
            body = normalize_text(getattr(f, "body", "") or "")
            head = normalize_text(getattr(f, "headline", "") or "")
            blob = (head + " " + body).lower()
            refs = [r for r in (getattr(f, "fact_refs", None) or []) if r]
            if blob.strip():
                fact_entries.append((blob, refs))
    if not fact_entries:
        return []

    # 2) 候选技能（保留顺序，去重）
    candidate: list[str] = []
    seen: set[str] = set()
    for sk in (list(compact.get("required_skills") or [])
               + list(compact.get("preferred_skills") or [])):
        s = normalize_text(sk).lower()
        if not s or s in seen:
            continue
        seen.add(s)
        candidate.append(s)

    # 3) 依据过滤 + 每技能的 fact_refs（按子串命中收集支撑事实的 fact_refs 并集）
    grounded: list[str] = []
    refs_by_skill: dict[str, list[str]] = {}
    for s in candidate:
        refs: list[str] = []
        hit = False
        for blob, refs_i in fact_entries:
            if s in blob:
                hit = True
                for r in refs_i:
                    if r not in refs:
                        refs.append(r)
        if hit:
            grounded.append(s)
            refs_by_skill[s] = refs

    # 4) 归类与裁剪
    groups: list[SkillGroup] = []
    assigned: set[str] = set()

    for cat_label, kws in _SKILL_TAXONOMY:
        members = [s for s in grounded if s not in assigned and any(kw in s for kw in kws)]
        if members:
            groups.append(SkillGroup(category=cat_label, items=members,
                                     fact_refs=_uniq_refs(members, refs_by_skill)))
            assigned.update(members)

    # 未命中启发式类别的依据技能兜底到「其他能力」
    leftover = [s for s in grounded if s not in assigned]
    if leftover:
        groups.append(SkillGroup(category="其他能力", items=leftover,
                                 fact_refs=_uniq_refs(leftover, refs_by_skill)))

    # 5) 容量约束（上限 4；下限不强制凑数）
    if len(groups) > max_categories:
        groups = groups[:max_categories]
    return groups


def _uniq_refs(skills: list[str], refs_by_skill: dict[str, list[str]]) -> list[str]:
    """并集取所有成员技能的 fact_refs（去重、保序）。"""
    out: list[str] = []
    for s in skills:
        for r in refs_by_skill.get(s, []):
            if r not in out:
                out.append(r)
    return out


# ── 装配入口（T07：产 ResumeDocument） ──────────────────────────── #

def build_resume_document(
    *,
    contact: dict[str, str],
    compact: dict[str, Any],
    experiences: list[Any],
    enough_experience_ids: Optional[set[str]] = None,
) -> ResumeDocument:
    """从生成结果装配标准 ResumeDocument（确定性，不依赖 DB）。

    每个 experience（dataclass：experience_id/sort_order/title/facts/type，
    facts 含 headline/body/fact_refs）：
      - facts 逐条 compose 成 bullet（headline：body），保留该条 fact_refs；
      - experience.type ∈ {work, project, education} 分派到 Work/Project/Education。
        缺 type 时按 title 启发式（含"教育/大学/学院"→education）。
    联系方式只来自 contact（T07a）；target_position 只来自 compact（T07 规则）。
    """
    contact_prof = normalize_contact(
        name=contact.get("name", ""),
        phone=contact.get("phone", ""),
        email=contact.get("email", ""),
        location=contact.get("location", ""),
        target_position=compact.get("position", "") or "",
    )

    work_items: list[WorkItem] = []
    project_items: list[ProjectItem] = []
    edu_items: list[EducationItem] = []

    for exp in experiences:
        exp_type = normalize_text(getattr(exp, "type", "") or "").lower()
        if not exp_type:
            t = normalize_text(getattr(exp, "title", "") or "")
            if any(k in t for k in ("教育", "大学", "学院", "学校", "学历")):
                exp_type = "education"
            else:
                exp_type = "work"

        bullets: list[str] = []
        refs: list[str] = []
        for f in (getattr(exp, "facts", None) or []):
            bullet = compose_fact_bullet(getattr(f, "headline", ""),
                                         getattr(f, "body", ""))
            if bullet:
                bullets.append(bullet)
                for r in (getattr(f, "fact_refs", None) or []):
                    if r and r not in refs:
                        refs.append(r)
        exp_id = normalize_text(getattr(exp, "experience_id", "") or "")

        start = getattr(exp, "start_time", "") or ""
        end = getattr(exp, "end_time", "") or ""

        if exp_type == "education":
            school = _display_text(getattr(exp, "school", "") or ""
                                   or getattr(exp, "title", "") or "")
            major = _display_text(getattr(exp, "major", "") or ""
                                  or getattr(exp, "role", "") or "")
            degree = _display_text(getattr(exp, "degree", "") or "")
            # 教育正文走模板的 {{edu.description}} 占位符（教育 item_block 不用 repeat）。
            # 把 P3 生成的教育事实（headline：body）原样接入 description，保证事实确定性
            # 进入 DOCX/PDF（V220-G05 / §6.3），不改变事实文本、不改模板真源。
            description = "\n".join(bullets) if bullets else ""
            edu_items.append(EducationItem(
                school=school, major=major, degree=degree,
                start_time=start, end_time=end or "至今",
                description=description or None,
                experience_id=exp_id, bullets=bullets, fact_refs=refs,
            ))
        elif exp_type == "project":
            project_items.append(ProjectItem(
                name=_display_text(getattr(exp, "title", "") or ""),
                role="",
                start_time=start, end_time=end,
                bullets=bullets, experience_id=exp_id, fact_refs=refs,
            ))
        else:
            work_items.append(WorkItem(
                company=_display_text(getattr(exp, "company", "") or ""
                                      or getattr(exp, "title", "") or ""),
                role="",
                start_time=start, end_time=end,
                bullets=bullets, experience_id=exp_id, fact_refs=refs,
            ))

    # 教育字段格式化修正（T07d）：school/major/degree 独立语义保留，
    # 渲染行文本 = format_education_line(...)；school/major/degree 仍各自保留原值。
    # （渲染层展示时使用格式化行；此处保持字段独立供校验，不写回单一拼接串。）

    skill_groups = build_skill_groups(compact, experiences)

    doc = ResumeDocument(
        profile=contact_prof,
        summary="",
        education=edu_items,
        work=work_items,
        projects=project_items,
        skills=skill_groups,
        awards=[],
        meta={
            "builder_mode": "v220_task_pipeline",
            "position": contact_prof.target_position,
        },
    )
    return doc.to_standard()


# ── P4 assembler：真实 DOCX/PDF 链接入 ───────────────────────────── #

def assemble_and_render(
    db,
    summary,
    compact,
    *,
    contact: dict[str, str],
    template_id: str,
    experience_rows: list[dict[str, Any]],
    user_id: str = "",
    backend_root: Optional[str] = None,
    timeout_s: float = 90.0,
) -> tuple[bool, dict[str, Any]]:
    """task_generation 的 P4 assembler 实现：装配 ResumeDocument → DOCX → 同源 PDF。

    入参：
      - summary：GenerationSummary（experiences 为 GeneratedExperience）
      - compact：P1 紧凑 JD（dict 或 JDAnalysisOutLike）
      - contact：联系方式（name/phone/email/location，来自冻结 InputRevision）
      - experience_rows：由调用方从 DB 查得的经历元信息
        [{experience_id, type, school/company, major/role, degree,
          start_time, end_time}]，用于把生成结果映射到 Education/Work/Project。

    返回 (assembled, artifacts)；artifacts 至少含 docx_path / pdf_path / file_name。
    任何一步失败 → fail closed：返回 (False, {})，由 run_generation 交回内容成功
    状态（不发布残缺 artifact）。
    """
    try:
        # 1) 把 summary.experiences 与 experience_rows 合并出装配需要的字段
        by_id = {r["experience_id"]: r for r in experience_rows if r.get("experience_id")}
        merged: list[Any] = []
        for exp in summary.experiences:
            eid = exp.experience_id
            row = by_id.get(eid, {})
            merged.append(JsonExperience(
                experience_id=eid,
                title=exp.title,
                facts=[JsonFact(headline=f.headline, body=f.body,
                                fact_refs=list(f.fact_refs)) for f in exp.facts],
                type=row.get("type", ""),
                company=row.get("company", ""),
                school=row.get("school", ""),
                major=row.get("major", ""),
                role=row.get("role", ""),
                degree=row.get("degree", ""),
                start_time=row.get("start_time", ""),
                end_time=row.get("end_time", ""),
            ))

        resume_doc = build_resume_document(
            contact=contact, compact=_compact_dict(compact), experiences=merged,
        )

        # 2) 渲染 + 保存 DOCX（复用 TemplateRenderer；模板资产缺失时 fail closed）
        from services import docx_to_pdf, template_renderer
        from core.config import settings

        if backend_root is None:
            backend_root = str(settings.BASE_DIR)
        out_dir = settings.DOCX_OUTPUT_DIR
        os.makedirs(out_dir, exist_ok=True)

        renderer = template_renderer.TemplateRenderer(template_id, backend_root=backend_root)
        renderer.bold_headline = True  # T07c：headline 加粗、正文普通
        renderer.allow_empty_required = True  # T08：合法短输入空章节优雅移除
        doc, warnings, _ = renderer.render(resume_doc)

        safe_user = "".join(c for c in (user_id or "user") if c.isalnum() or c in "-_") or "user"
        op_slug = uuid.uuid4().hex[:16]
        docx_name = f"resume_{safe_user}_{template_id}_{op_slug}.docx"
        docx_abs = os.path.join(out_dir, docx_name)
        doc.save(docx_abs)

        # 3) 同源 PDF（Word COM）；失败则 DOCX 仍有效，PDF 置空
        pdf_name = ""
        pdf_abs = ""
        pdf_sha256 = ""
        pdf_bytes = b""
        try:
            conv = docx_to_pdf.convert_docx_to_pdf_bytes(docx_abs, timeout_s=timeout_s)
            pdf_bytes = conv["pdf_bytes"]
            pdf_name = f"resume_{safe_user}_{template_id}_{op_slug}.pdf"
            pdf_abs = os.path.join(out_dir, pdf_name)
            with open(pdf_abs, "wb") as f:
                f.write(pdf_bytes)
            pdf_sha256 = _file_sha256(pdf_abs)
        except Exception as e:  # noqa: BLE001 —— fail closed：PDF 不可用不标成功
            logger.warning("T07 P4 Word→PDF 失败（DOCX 仍有效）: %s", e)
            pdf_name = ""
            pdf_abs = ""

        # 4) PreviewAnchor：从 Word 转换后的确切 PDF 文本层重建（T06 anchor/依据定位）。
        #    绑定本 revision artifact 身份 op_slug；无法可靠定位的行记 unavailable（不高亮，诚实降级）。
        pdf_anchors: list[dict] = []
        if pdf_bytes:
            try:
                from services import pdf_anchors as _pa
                rows: list[dict] = []
                for edu_ in resume_doc.education:
                    if getattr(edu_, "description", None):
                        rows.append({"text": edu_.description,
                                     "content_item_id": edu_.experience_id or None,
                                     "bullet_index": 0})
                for w_ in resume_doc.work:
                    for bi, bl in enumerate(w_.bullets):
                        rows.append({"text": bl,
                                     "content_item_id": w_.experience_id or None,
                                     "bullet_index": bi})
                for pr_ in resume_doc.projects:
                    for bi, bl in enumerate(pr_.bullets):
                        rows.append({"text": bl,
                                     "content_item_id": pr_.experience_id or None,
                                     "bullet_index": bi})
                _anchors, _unavail = _pa.build_anchors_from_word_pdf(
                    pdf_bytes, rows, artifact_id=op_slug)
                pdf_anchors = [dict(a) for a in _anchors]
                if _unavail:
                    warnings.append(
                        f"PDF: 锚点 unavailable {len(_unavail)} 条（诚实降级，不高亮）: "
                        + ";".join(u.get("text", "")[:16] for u in _unavail[:3]))
            except Exception as e:  # noqa: BLE001 —— 锚点失败不影响 DOCX/PDF 本身可用
                logger.warning("T06 P4 锚点重建失败（PDF 仍可用）: %s", e)
                warnings.append(f"PDF: 锚点重建失败（预览可用，anchor 不可用）: {type(e).__name__}")

        artifacts = {
            "docx_path": f"output/{docx_name}",
            "pdf_path": f"output/{pdf_name}" if pdf_name else "",
            "docx_abs": docx_abs,
            "pdf_abs": pdf_abs,
            "template_id": template_id,
            "resume_revision_key": op_slug,
            "pdf_artifact_id": op_slug if pdf_name else "",
            "docx_sha256": _file_sha256(docx_abs),
            "pdf_sha256": pdf_sha256,
            "pdf_anchors": pdf_anchors,
            "warnings": list(warnings),
        }
        return True, artifacts
    except Exception as e:  # noqa: BLE001
        logger.exception("T07 P4 assemble_and_render 失败（fail closed）")
        return False, {"error": type(e).__name__, "message": str(e)}


def _compact_dict(jd_analysis) -> dict[str, Any]:
    if isinstance(jd_analysis, dict):
        return jd_analysis
    return jd_analysis.model_dump() if hasattr(jd_analysis, "model_dump") else dict(jd_analysis)


def _file_sha256(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:  # noqa: BLE001
        return ""


def make_task_assembler(
    db,
    *,
    contact: dict[str, str],
    template_id: str,
    user_id: str = "",
    backend_root: Optional[str] = None,
) -> Any:
    """构造 task_generation 的 P4 assembler 闭包（签名 `(summary, compact)`）。

    从 summary.experiences 的 experience_id 回查 DB Experience 的 type/字段，
    得到装配 Education/Work/Project 所需的元数据，再交给 assemble_and_render。
    """
    from database.models import Experience

    def _asm(summary, compact):
        ids = [e.experience_id for e in getattr(summary, "experiences", [])]
        rows: list[dict[str, Any]] = []
        if ids:
            exps = db.query(Experience).filter(Experience.id.in_(ids)).all()
            by_id = {e.id: e for e in exps}
            for eid in ids:
                e = by_id.get(eid)
                if e is None:
                    rows.append({"experience_id": eid, "type": "work"})
                    continue
                t = normalize_text(e.type or "")
                start, end = _split_time(e.time or "")
                if t == "education":
                    rows.append({
                        "experience_id": eid, "type": "education",
                        "school": e.company or e.title or "", "major": e.role or "",
                        "degree": "", "start_time": start, "end_time": end,
                    })
                elif t == "project":
                    rows.append({
                        "experience_id": eid, "type": "project",
                        "title": e.title or "", "start_time": start, "end_time": end,
                    })
                else:
                    rows.append({
                        "experience_id": eid, "type": "work",
                        "company": e.company or e.title or "",
                        "role": e.role or "", "start_time": start, "end_time": end,
                    })
        return assemble_and_render(
            db, summary, compact, contact=contact,
            experience_rows=rows, template_id=template_id,
            user_id=user_id, backend_root=backend_root,
        )

    return _asm


def _split_time(time_str: str) -> tuple[str, str]:
    """把 `2022.09 - 2026.06` / `2022.09-至今` 拆为 (start, end)。"""
    if not time_str:
        return "", ""
    parts = [p.strip() for p in time_str.split("-", 1)]
    if len(parts) == 2:
        return parts[0], parts[1]
    return time_str, ""


# ── 装配用轻量载体（避免依赖 DB ORM，保持纯逻辑可测） ─────────────── #

class JsonFact:
    def __init__(self, headline: str = "", body: str = "", fact_refs=None):
        self.headline = headline
        self.body = body
        self.fact_refs = list(fact_refs or [])


class JsonExperience:
    def __init__(self, *, experience_id, title="", facts=None, type="",
                 company="", school="", major="", role="", degree="",
                 start_time="", end_time=""):
        self.experience_id = experience_id
        self.title = title
        self.facts = list(facts or [])
        self.type = type
        self.company = company
        self.school = school
        self.major = major
        self.role = role
        self.degree = degree
        self.start_time = start_time
        self.end_time = end_time