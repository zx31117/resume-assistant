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
import re
import unicodedata
import uuid
from typing import Any, Optional

from core.errors import (
    ArtifactInvalidError,
    DomainError,
    OptionalContentAbsentError,
    SourceContentLostError,
    TemplateStructureInvalidError,
)
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


# ── 教育确定性排序（PLAN Revision 3 P0） ───────────────────────── #

_EDU_MAX_ITEMS = 3


def _order_education(edu_sources: list[tuple[Any, EducationItem]]) -> list[EducationItem]:
    """教育经历按确定性规则排序并截断。

    规则：end desc → start desc → experience_id asc；year/month 无法解析的条目置后；
    最多 _EDU_MAX_ITEMS 条；走**来源字段**（end_time/start_time），不参与 JD 相关性。
    """
    def _key(tup):
        exp, _item = tup
        end = _to_ym(_display_text(getattr(exp, "end_time", "") or ""))
        start = _to_ym(_display_text(getattr(exp, "start_time", "") or ""))
        # 无法解析 → 置后（end = 极小数位）
        end_ord = _ym_ordinal(end) if end else -1
        start_ord = _ym_ordinal(start) if start else -1
        eid = normalize_text(getattr(exp, "experience_id", "") or "")
        return (-end_ord, -start_ord, eid)

    ordered = sorted(edu_sources, key=_key)
    return [item for _exp, item in ordered[:_EDU_MAX_ITEMS]]


def _to_ym(s: str) -> Optional[tuple[int, int]]:
    """从 'YYYY.MM' / 'YYYY-MM' / 'YYYY年MM月' / 'YYYY' 提取 (year, month)；无法解析返回 None。"""
    import re as _re
    m = _re.search(r"(\d{4})[.\-年/](\d{1,2})?月?", s or "")
    if not m:
        return None
    year = int(m.group(1))
    month = int(m.group(2)) if m.group(2) else 1
    if not (1 <= month <= 12):
        month = 1
    return (year, month)


def _ym_ordinal(ym: tuple[int, int]) -> int:
    return ym[0] * 12 + ym[1]


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
    edu_sources: list[tuple[object, Any]] = []  # (exp, bullets/refs) 供确定性排序

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
            item = EducationItem(
                school=school, major=major, degree=degree,
                start_time=start, end_time=end or "至今",
                description=description or None,
                experience_id=exp_id, bullets=bullets, fact_refs=refs,
            )
            # V2.2.0 P0：教育确定性排序（end desc → start desc → id asc；缺失置后，
            # 最多 3 条，不参与 JD 相关性）。防止"教育未进成品/顺序随查询抖动"。
            edu_sources.append((exp, item))
        elif exp_type == "project":
            # V2.2.0 P0：非空 source role 不得硬编码清空（旧代码 role=""）。
            project_items.append(ProjectItem(
                name=_display_text(getattr(exp, "title", "") or "")
                or _display_text(getattr(exp, "name", "") or ""),
                role=_display_text(getattr(exp, "role", "") or ""),
                start_time=start, end_time=end,
                bullets=bullets, experience_id=exp_id, fact_refs=refs,
            ))
        else:
            # V2.2.0 P0：非空 source role/company 不得硬编码清空（旧代码 role=""）。
            work_items.append(WorkItem(
                company=_display_text(getattr(exp, "company", "") or ""
                                      or getattr(exp, "title", "") or ""),
                role=_display_text(getattr(exp, "role", "") or ""),
                start_time=start, end_time=end,
                bullets=bullets, experience_id=exp_id, fact_refs=refs,
            ))

    # V2.2.0 P0：教育按确定性时间排序并限制最 3 条（缺失年份置后，id asc 兜底防抖）。
    edu_items = _order_education(edu_sources)

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
    task_id: str,
    contact: dict[str, str],
    template_id: str,
    experience_rows: list[dict[str, Any]],
    user_id: str = "",
    backend_root: Optional[str] = None,
    timeout_s: float = 90.0,
    forbidden_sentinels: Optional[list[str]] = None,
) -> tuple[bool, dict[str, Any]]:
    """task_generation 的 P4 assembler 实现：装配 → DOCX/PDF 写入 task-scoped staging → 校验。

    与 Revision 3 之前的版本相比，本函数**不再**直接写最终 output 目录：
    全部产物先落到 `<RESUME_DATA_DIR>/staging/<task_id>/<op_slug>/`（不可公开），
    完成 `validate_staged_artifacts` 全部校验后由 `run_generation` 在同盘原子提升并
    与 `SUCCEEDED` 一起提交。任一步失败都 fail closed（不发布、清理 staging）。

    返回 (assembled, artifacts)；artifacts 至少含最终的 docx/pdf 文件名与前缀语义标签；
    真实字节位于 `docx_staged_abs` / `pdf_staged_abs`（尚未提升）。
    """
    stage_dir = None
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
        # V2.2.0 P0：教育经历未经过 P2 选材（确定性结构），把 owner 的教育经历行
        # 单独并入装配，保证"教育进成品"（不参与 JD 相关性，进入 build_resume_document
        # 的教育分支做确定性排序/截断）。
        merged_ids = {e.experience_id for e in summary.experiences}
        for row in experience_rows:
            eid = row.get("experience_id")
            if eid and row.get("type") == "education" and eid not in merged_ids:
                merged.append(JsonExperience(
                    experience_id=eid,
                    title=row.get("school") or row.get("title") or "",
                    facts=[],
                    type="education",
                    company=row.get("school", ""),
                    school=row.get("school", ""),
                    major=row.get("major", ""),
                    role="",
                    degree=row.get("degree", ""),
                    start_time=row.get("start_time", ""),
                    end_time=row.get("end_time", ""),
                ))

        compact_dict = _compact_dict(compact)
        resume_doc = build_resume_document(
            contact=contact, compact=compact_dict, experiences=merged,
        )

        # 2) 渲染（复用 TemplateRenderer；模板资产缺失时 fail closed）
        from services import artifact_store, docx_to_pdf, template_renderer
        from core.config import settings

        if backend_root is None:
            backend_root = str(settings.BASE_DIR)

        renderer = template_renderer.TemplateRenderer(template_id, backend_root=backend_root)
        renderer.bold_headline = True  # T07c：headline 加粗、正文普通
        renderer.allow_empty_required = True  # T08：合法短输入空章节优雅移除
        doc, warnings, render_stats = renderer.render(resume_doc)

        # V2.2.0 P0：结构校验阻断发布 —— 未替换占位符属结构性错误，raise → 任务 FAILED 且不发布。
        unreplaced = render_stats.get("unreplaced_placeholders") or []
        if unreplaced:
            raise TemplateStructureInvalidError(
                "装配输出仍含未替换占位符，判定为结构性错误，拒绝发布",
                details={"unreplaced_placeholders": sorted(unreplaced)[:20],
                         "template_id": template_id},
            )

        # 3) 写入不可公开的 task-scoped staging（绝不直接写最终 output）
        save_user = user_id or contact.get("name") or ""
        safe_user = artifact_store.safe_token(save_user)[:40] or "user"
        op_slug = uuid.uuid4().hex[:16]
        stage_dir = artifact_store.task_staging_dir(task_id or "unknown", op_slug)
        if not artifact_store.assert_inside_staging(stage_dir):
            raise ArtifactInvalidError(
                "staging 目录不在受控根内，拒绝写盘",
                details={"template_id": template_id},
            )
        docx_name = f"resume_{safe_user}_{template_id}_{op_slug}.docx"
        pdf_name = f"resume_{safe_user}_{template_id}_{op_slug}.pdf"
        docx_staged = os.path.join(str(stage_dir), docx_name)
        try:
            doc.save(docx_staged)
        except Exception as e:  # noqa: BLE001
            raise ArtifactInvalidError(
                f"DOCX 写入 staging 失败，artifact 不可用：{e}",
                details={"template_id": template_id},
            ) from e

        # 4) 同源 PDF（Word COM）；失败则 DOCX 仍有效，PDF 置空（不得伪造）
        pdf_staged = ""
        pdf_bytes = b""
        try:
            conv = docx_to_pdf.convert_docx_to_pdf_bytes(docx_staged, timeout_s=timeout_s)
            pdf_bytes = conv["pdf_bytes"]
            pdf_staged = os.path.join(str(stage_dir), pdf_name)
            if pdf_bytes:
                with open(pdf_staged, "wb") as f:
                    f.write(pdf_bytes)
            else:
                pdf_staged = ""
        except Exception as e:  # noqa: BLE001 —— fail closed：PDF 不可用不标成功
            logger.warning("T07 P4 Word→PDF 失败（DOCX 仍有效）: %s", e)
            pdf_staged = ""

        if not pdf_staged:
            pdf_name = ""

        # 5) 发布前内容级校验（存在/非零/可读/格式/章节/字段守恒/education/占位符/同源/哨兵）
        problems = validate_staged_artifacts(
            docx_path=docx_staged,
            pdf_path=pdf_staged or None,
            task_id=task_id or "",
            owner=user_id or "",
            resume_doc=resume_doc,
            render_stats=render_stats,
            contact=contact,
            experience_rows=experience_rows,
            template_id=template_id,
            forbidden_sentinels=forbidden_sentinels or [],
        )
        if problems:
            assert_publishable(problems)

        # 6) PreviewAnchor：从 Word 转换后的确切 PDF 文本层重建（T06 anchor/依据定位）。
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

        docx_sha = artifact_store.sha256_file(docx_staged)
        pdf_sha = artifact_store.sha256_file(pdf_staged) if pdf_staged else ""
        artifacts = {
            # 最终发布名（提升后相对 output 目录的语义标签；staging 阶段尚未存在）
            "docx_path": f"output/{docx_name}",
            "pdf_path": f"output/{pdf_name}" if pdf_name else "",
            "docx_file_name": docx_name,
            "pdf_file_name": pdf_name or "",
            "docx_staged_abs": docx_staged,
            "pdf_staged_abs": pdf_staged,
            "staging_dir": str(stage_dir),
            "staged": True,
            "template_id": template_id,
            "resume_revision_key": op_slug,
            "pdf_artifact_id": op_slug if pdf_name else "",
            "docx_sha256": docx_sha,
            "docx_size_bytes": os.path.getsize(docx_staged) if os.path.exists(docx_staged) else 0,
            "pdf_sha256": pdf_sha,
            "pdf_size_bytes": os.path.getsize(pdf_staged) if pdf_staged else 0,
            "pdf_anchors": pdf_anchors,
            "warnings": list(warnings),
            "validate": {"ok": True, "problems": []},
        }
        return True, artifacts
    except DomainError as e:  # noqa: BLE001
        # V2.2.0 P0：结构性错误（来源丢失/模板结构/artifact 不可用）不再静默吞掉，
        # 向上抛出让 run_generation 把任务置 FAILED 且不发布残缺 artifact。
        # 失败路径必须清理本轮 staging（不得留下可被误认为产物的残留）。
        if stage_dir is not None:
            try:
                from services import artifact_store as _as
                _as.cleanup_dir_quiet(stage_dir)
            except Exception:  # noqa: BLE001
                logger.error("artifact staging cleanup failed after DomainError")
        logger.warning("T07 P4 assemble_and_render 结构性错误阻断发布: %s", e)
        raise
    except Exception as e:  # noqa: BLE001
        if stage_dir is not None:
            try:
                from services import artifact_store as _as
                _as.cleanup_dir_quiet(stage_dir)
            except Exception:  # noqa: BLE001
                logger.error("artifact staging cleanup failed after failure")
        logger.exception("T07 P4 assemble_and_render 失败（fail closed）")
        return False, {"error": type(e).__name__, "message": str(e)}


# ── 发布前内容级校验（RESULT §R3-18 C2） ──────────────────────── #

# 已知的其它身份 / stub 哨兵标记（与内容 E2E 使用的固定哨兵一致；大小写不敏感）。
_RESERVED_SENTINEL_MARKERS = (
    "STUB-占位", "OTHER-异主", "OTHER-异校", "stub-user", "other-user",
    "LEGACY_UNOWNED",
)


def assert_publishable(problems: list[str]) -> None:
    """发布门禁：任一内容校验问题都必须阻断发布（fail closed）。

    这是 staging → 原子提升之间**唯一**的放行点；`assemble_and_render` 与
    任何其它调用方都必须经由此处，禁止“先发布后补校验”。
    """
    if problems:
        raise ArtifactInvalidError(
            "staging artifact 未通过发布前内容校验，拒绝发布",
            details={"problems": list(problems)[:20], "count": len(problems)},
        )


def validate_staged_artifacts(
    *,
    docx_path: str,
    pdf_path: Optional[str],
    task_id: str,
    owner: str,
    resume_doc: ResumeDocument,
    render_stats: dict[str, Any],
    contact: dict[str, str],
    experience_rows: list[dict[str, Any]],
    template_id: str,
    forbidden_sentinels: list[str],
) -> list[str]:
    """对 staging 中的 DOCX/PDF 做发布前全量校验，返回问题列表（空 = 通过）。

    fail-closed：任何一项不成立都返回非空 problems，调用方据此拒绝发布。
    """
    from services import artifact_store as _as

    problems: list[str] = []

    # 1) 路径必须位于当前 task staging 内（越界路径直接拒）。
    if not _as.assert_inside_staging(docx_path):
        problems.append("docx:NOT_IN_TASK_STAGING")
    if pdf_path and not _as.assert_inside_staging(pdf_path):
        problems.append("pdf:NOT_IN_TASK_STAGING")
    # staging 目录语义必须包含本任务 id（owner/task/source 一致性锚点）。
    if task_id and _as.safe_token(task_id)[:64] not in os.path.normpath(docx_path):
        problems.append("docx:TASK_ID_NOT_BOUND")

    # 2) 存在 / 非零 / 可读。
    problems += _as.file_problems(docx_path, min_bytes=_as.MIN_DOCX_BYTES, label="docx")
    if pdf_path:
        problems += _as.file_problems(pdf_path, min_bytes=_as.MIN_PDF_BYTES, label="pdf")
    if problems:
        return problems

    # 3) 格式可解析。
    problems += _as.docx_problems(docx_path)
    if pdf_path:
        problems += _as.pdf_problems(pdf_path)

    # 4) 未替换占位符（结构性错误）。
    if render_stats.get("unreplaced_placeholders"):
        problems.append("docx:UNREPLACED_PLACEHOLDER")

    # 5) 必需章节：源里有 work/project/education 时成品必须有对应条目。
    n_work_src = sum(1 for r in experience_rows if (r.get("type") or "") == "work")
    n_proj_src = sum(1 for r in experience_rows if (r.get("type") or "") == "project")
    n_edu_src = sum(1 for r in experience_rows if (r.get("type") or "") == "education")
    if n_work_src and not resume_doc.work:
        problems.append("docx:REQUIRED_SECTION_WORK_MISSING")
    if n_proj_src and not resume_doc.projects:
        problems.append("docx:REQUIRED_SECTION_PROJECT_MISSING")
    if n_edu_src and not resume_doc.education:
        problems.append("docx:REQUIRED_SECTION_EDUCATION_MISSING")

    # 6) 非空源字段守恒（company / name / role / school / major / degree / time）。
    problems += _field_conservation_problems(resume_doc, experience_rows)

    # 7) 联系方式：非空字段必须出现（且恰一次由渲染保证），全空时不出现空标签。
    docx_text = ""
    try:
        docx_text = _as.docx_text(docx_path)
    except Exception:  # noqa: BLE001
        problems.append("docx:TEXT_EXTRACT_FAILED")
    norm_docx = _as.normalize_for_match(docx_text)

    for key in ("phone", "email", "location"):
        val = _display_text(contact.get(key, "") or "")
        if val and _as.normalize_for_match(val) not in norm_docx:
            problems.append(f"docx:CONTACT_FIELD_LOST:{key}")
    name_val = _display_text(contact.get("name", "") or "")
    if name_val and _as.normalize_for_match(name_val) not in norm_docx:
        problems.append("docx:CONTACT_FIELD_LOST:name")

    # 8) 模板样例文字 / 原型占位泄漏。
    for marker in ("{{", "}}", "[[", "]]"):
        if marker in docx_text:
            problems.append(f"docx:TEMPLATE_MARKER_LEAK:{marker}")

    # 9) 其他 owner / stub 哨兵不得出现。
    haystack = norm_docx
    for tok in list(forbidden_sentinels) + list(_RESERVED_SENTINEL_MARKERS):
        t = _as.normalize_for_match(str(tok))
        if len(t) < 4:
            continue
        if t in haystack:
            problems.append(f"docx:FOREIGN_OWNER_SENTINEL:{str(tok)[:24]}")

    # 10) DOCX / PDF 内容同源（PDF 存在时必须成立）。
    if pdf_path:
        try:
            pdf_text = _as.pdf_text(pdf_path)
            norm_pdf = _as.normalize_for_match(pdf_text)
            if not norm_pdf:
                problems.append("pdf:EMPTY_TEXT_LAYER")
            else:
                problems += _same_source_problems(resume_doc, norm_pdf)
        except Exception:  # noqa: BLE001
            problems.append("pdf:TEXT_EXTRACT_FAILED")

    if not owner:
        problems.append("artifact:OWNER_EMPTY")
    return problems


def _norm(s: Any) -> str:
    return re.sub(r"\s+", "", _display_text(str(s or "")))


def _field_conservation_problems(resume_doc: ResumeDocument,
                                 experience_rows: list[dict[str, Any]]) -> list[str]:
    """源中非空的 role/company/name/school/major/degree/time 必须进入成品对应字段。"""
    problems: list[str] = []
    work_norm = [
        {k: _norm(getattr(w, k, "")) for k in ("company", "role", "start_time", "end_time")}
        for w in resume_doc.work
    ]
    proj_norm = [
        {k: _norm(getattr(p, k, "")) for k in ("name", "role", "start_time", "end_time")}
        for p in resume_doc.projects
    ]
    edu_norm = [
        {k: _norm(getattr(e, k, "")) for k in ("school", "major", "degree")}
        for e in resume_doc.education
    ]

    def _present(rows: list[dict[str, str]], fields: tuple[str, ...], val: str) -> bool:
        nv = _norm(val)
        if not nv:
            return True
        return any(any(nv == r.get(f, "") or nv in (r.get(f, "") or "") for f in fields)
                   for r in rows)

    for row in experience_rows:
        etype = (row.get("type") or "")
        if etype == "work":
            for f in ("company", "role"):
                if not _present(work_norm, ("company", "role"), row.get(f, "")):
                    problems.append(f"docx:SOURCE_FIELD_LOST:work.{f}")
        elif etype == "project":
            name = row.get("title") or row.get("name") or ""
            if not _present(proj_norm, ("name", "role"), name):
                problems.append("docx:SOURCE_FIELD_LOST:project.name")
            if not _present(proj_norm, ("name", "role"), row.get("role", "")):
                problems.append("docx:SOURCE_FIELD_LOST:project.role")
        elif etype == "education":
            for f in ("school", "major"):
                if not _present(edu_norm, ("school", "major", "degree"), row.get(f, "")):
                    problems.append(f"docx:SOURCE_FIELD_LOST:education.{f}")
    return problems


def _same_source_problems(resume_doc: ResumeDocument, norm_pdf: str) -> list[str]:
    """DOCX/PDF 同源：成品的关键条目文本必须同时出现在 PDF 文本层。"""
    problems: list[str] = []
    checked = 0
    for item in list(resume_doc.work) + list(resume_doc.projects):
        for bullet in list(getattr(item, "bullets", []) or [])[:1]:
            seg = _norm(bullet)[:24]
            if len(seg) < 8:
                continue
            checked += 1
            if seg not in norm_pdf:
                problems.append("pdf:NOT_SAME_SOURCE_AS_DOCX")
                return problems
    for edu in resume_doc.education:
        seg = _norm(getattr(edu, "school", ""))[:12]
        if len(seg) < 4:
            continue
        checked += 1
        if seg not in norm_pdf:
            problems.append("pdf:EDUCATION_NOT_IN_PDF")
            return problems
    if checked == 0:
        # 无任何可比对条目时不能声明同源成立（诚实 fail-closed）。
        problems.append("pdf:NO_COMPARABLE_CONTENT")
    return problems


def promote_staged_artifacts(artifacts: dict[str, Any]) -> dict[str, Any]:
    """把 staging 中的 DOCX/PDF 同盘原子提升到最终 output 目录。

    返回提升后的 `promoted` 子字典（final abs 路径 + 文件名 + sha + size）。
    任一文件提升失败：回滚本次已提升文件并抛 ArtifactInvalidError（不留下半成品）。
    """
    from services import artifact_store as _as

    out_dir = str(_as.publish_root())
    promoted: dict[str, Any] = {"docx": None, "pdf": None}
    done: list[str] = []
    try:
        docx_final, err = _as.promote(artifacts.get("docx_staged_abs", ""), out_dir,
                                      artifacts.get("docx_file_name", ""))
        if err or not docx_final:
            raise ArtifactInvalidError(
                f"DOCX 原子提升失败：{err}", details={"reason": err})
        done.append(docx_final)
        promoted["docx"] = {
            "file_name": artifacts.get("docx_file_name", ""),
            "abs": docx_final,
            "sha256": _as.sha256_file(docx_final),
            "size_bytes": os.path.getsize(docx_final),
        }
        if artifacts.get("pdf_staged_abs"):
            pdf_final, err = _as.promote(artifacts.get("pdf_staged_abs", ""), out_dir,
                                         artifacts.get("pdf_file_name", ""))
            if err or not pdf_final:
                raise ArtifactInvalidError(
                    f"PDF 原子提升失败：{err}", details={"reason": err})
            done.append(pdf_final)
            promoted["pdf"] = {
                "file_name": artifacts.get("pdf_file_name", ""),
                "abs": pdf_final,
                "sha256": _as.sha256_file(pdf_final),
                "size_bytes": os.path.getsize(pdf_final),
            }
        return promoted
    except Exception:
        # 回滚：删除本次已提升文件，避免"提升了一半"的半成品对后续可见。
        for f in done:
            _as.remove_file_quiet(f)
        raise


def _rollback_promoted(promoted: Optional[dict[str, Any]]) -> None:
    """回滚已提升文件（幂等）。"""
    from services import artifact_store as _as
    if not promoted:
        return
    for kind in ("docx", "pdf"):
        rec = promoted.get(kind)
        if rec and rec.get("abs"):
            _as.remove_file_quiet(rec["abs"])


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
    task_id: str,
    contact: dict[str, str],
    template_id: str,
    user_id: str = "",
    backend_root: Optional[str] = None,
) -> Any:
    """构造 task_generation 的 P4 assembler 闭包（签名 `(summary, compact)`）。

    V2.2.0 P0：装配归主用**真实 owner**（current_user_id），不用 task_id 冒充：
      - 从 summary.experiences 的 experience_id 回查 DB Experience 的 type/字段；
      - **单独取当前 owner 的教育经历**（教育不经过 P2 选材，必须确定性装配进成品）；
      所有查询都限定 user_id == current_user_id()，隔离异主/LEGACY 素材。
    V2.2.0 Revision 3 返工：产物写入 task-scoped staging，并收集**其它身份**的内容特征
    作为禁止哨兵，供发布前校验证明成品不含异主内容。
    """
    from core.owner import current_user_id
    from database.models import Experience

    owner = current_user_id() if not user_id else user_id

    # 其它身份（含 stub/LEGACY 无主）的显著内容特征 → 禁止出现在当前 owner 的成品里。
    forbidden: list[str] = []
    try:
        others = (db.query(Experience)
                  .filter((Experience.user_id.is_(None)) | (Experience.user_id != owner))
                  .all())
        for e in others:
            for tok in (e.company, e.title, getattr(e, "role", "")):
                t = (tok or "").strip()
                if len(t) >= 4 and t not in forbidden:
                    forbidden.append(t)
    except Exception:  # noqa: BLE001 —— 收集失败不阻断主链（仍有保留哨兵兜底）
        logger.warning("collect forbidden sentinels failed", exc_info=True)

    def _asm(summary, compact):
        ids = [e.experience_id for e in getattr(summary, "experiences", [])]
        rows: list[dict[str, Any]] = []
        if ids:
            exps = (db.query(Experience)
                    .filter(Experience.id.in_(ids), Experience.user_id == owner)
                    .all())
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
                        "title": e.title or "", "role": e.role or "",
                        "start_time": start, "end_time": end,
                    })
                else:
                    rows.append({
                        "experience_id": eid, "type": "work",
                        "company": e.company or e.title or "",
                        "role": e.role or "", "start_time": start, "end_time": end,
                    })
        # V2.2.0 P0：单独装配 owner 的教育经历（确定性进成品，不参与 P2 选材）。
        edu_rows = (db.query(Experience)
                    .filter(Experience.user_id == owner)
                    .filter(Experience.type == "education")
                    .all())
        for e in edu_rows:
            if e.id in set(ids):
                continue  # 已从 summary 选材回查覆盖（一般不会发生）
            start, end = _split_time(e.time or "")
            rows.append({
                "experience_id": e.id, "type": "education",
                "school": e.company or e.title or "", "title": e.title or "",
                "major": e.role or "", "degree": "", "start_time": start, "end_time": end,
            })
        return assemble_and_render(
            db, summary, compact, task_id=task_id, contact=contact,
            experience_rows=rows, template_id=template_id,
            user_id=owner, backend_root=backend_root,
            forbidden_sentinels=forbidden,
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