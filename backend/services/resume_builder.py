"""V1.3 ResumeBuilder（纯业务编排层，不调 AI）。

铁律（PLAN §3.3 事实边界）：
  - **事实唯一来源：SQL Experience**；AI 只提供 bullets 文本改写，不能改公司/岗位/项目/时间
  - **唯一内容选择入口**：本 build() 内部排序 + 裁剪，任何渲染层不得再删条目
  - **AI 内容合并**：按 experience_id 精确合并 GeneratedResumeContent；空 bullets → 回退 SQL
  - **身份字段只取 request**：name/phone/email/location 只从请求显式值取，缺失留空，不做 fallback
  - **求职意向只取 JD**：target_position = JDAnalysis.position，不从 request/DB/经历库取
  - **V1.3 不生成、不渲染个人总结**：summary 恒为空字符串

边界：
- 可读：experience_service（DB 查询）
- 不调：LLM、RAG、LangChain
- 不写：DB、向量库
- 下游：TemplateRenderer（渲染）+ LayoutOptimizer（只调样式不裁条目）
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from api.schemas import GeneratedResumeContent
from core.errors import ProfileIncompleteError  # noqa: F401  保持旧导入路径兼容（template.py 用）
from database import models
from models.resume_document import (
    Profile,
    EducationItem,
    WorkItem,
    ProjectItem,
    SkillGroup,
    ResumeDocument,
)


# ── ProfileResolver（V1.3：身份字段只取 request，求职意向只取 JD） ── #

class ProfileResolver:
    """PLAN §3.3 事实边界：身份字段只取 request，求职意向只取 JD。

    - name / phone / email / location：只从 request_profile 取，缺失留空
    - target_position：只从 jd_position 取（JDAnalysis.position）
    - summary：恒为空（V1.3 不生成、不渲染）
    - 不从 DB / AI / 经历库 / 模板回填任何身份字段
    - 身份字段缺失不属于错误（PLAN §4.3）
    """

    @staticmethod
    def resolve(
        request_profile: Optional[dict] = None,
        jd_position: str = "",
        *,
        db_profile: Optional[dict] = None,              # 保留参数兼容旧调用方，V1.3 不使用
        resume_content_profile: Optional[dict] = None,   # 同上
    ) -> tuple[Profile, str]:
        """返回 (Profile, profile_source)。

        profile_source 只会是 "request"（至少一个身份字段非空）或 "empty"（全空）。
        不会抛 ProfileIncompleteError——身份字段缺失属于合法状态。
        """
        rp = request_profile or {}
        profile = Profile(
            name=(rp.get("name") or "").strip(),
            phone=(rp.get("phone") or "").strip(),
            email=(rp.get("email") or "").strip(),
            location=(rp.get("location") or "").strip() or None,
            target_position=(jd_position or "").strip(),
            summary="",  # V1.3 不生成、不渲染
        )
        has_any = any([profile.name, profile.phone, profile.email, profile.location])
        profile_source = "request" if has_any else "empty"
        return profile, profile_source


def _categorize_skills(skills_with_freq: dict[str, int]) -> list[SkillGroup]:
    """把技能按类别分组（粗粒度规则）。"""
    if not skills_with_freq:
        return []

    # 简单分类规则（可扩展）
    tech_kw = {"python", "java", "c++", "c", "go", "javascript", "js", "react", "vue",
               "sql", "mysql", "redis", "ai", "ml", "dl", "nlp", "cv", "llm",
               "深度学习", "机器学习", "大模型", "人工智能"}
    product_kw = {"产品", "需求", "prd", "用户", "运营", "策略", "数据分析"}
    tool_kw = {"git", "docker", "linux", "k8s", "jenkins", "figma", "axure", "jira"}
    lang_kw = {"英语", "中文", "日语", "韩语", "french", "english", "chinese", "japanese"}

    groups = {"技术": [], "产品": [], "工具": [], "语言": [], "其他": []}
    for skill, freq in sorted(skills_with_freq.items(), key=lambda x: -x[1]):
        s = skill.lower()
        if any(k in s for k in tech_kw):
            groups["技术"].append(skill)
        elif any(k in s for k in product_kw):
            groups["产品"].append(skill)
        elif any(k in s for k in tool_kw):
            groups["工具"].append(skill)
        elif any(k in s for k in lang_kw):
            groups["语言"].append(skill)
        else:
            groups["其他"].append(skill)

    result = []
    for cat, items in groups.items():
        if items:
            result.append(SkillGroup(category=cat, items=items))
    return result


def _collect_skills(experiences: list[models.Experience], jd_required_skills: list) -> dict[str, int]:
    """收集技能频率（经历 skills ∩ JD required_skills 优先）。"""
    freq: dict[str, int] = {}
    jd_set = {s.lower().strip() for s in (jd_required_skills or []) if s}

    for exp in experiences:
        for s in (exp.skills or []):
            s = s.strip()
            if not s:
                continue
            # JD 命中的技能权重 +3，其他 +1
            freq[s] = freq.get(s, 0) + (3 if s.lower() in jd_set else 1)

    return freq


def _extract_awards(experiences: list[models.Experience]) -> list[str]:
    """从经历的 achievements 中筛选含奖/证/赛的条目。"""
    awards = []
    award_kw = ["奖", "证书", "认证", "赛", "荣誉", "奖学金", "排名", "绩点", "GPA"]
    for exp in experiences:
        for ach in (exp.achievements or []):
            if any(kw in ach for kw in award_kw):
                awards.append(ach.strip())
    return awards


# ── 辅助：按 jd_analysis 兼容 BaseModel / dict 取字段 ──────── #

def _jd_get(jd_analysis: object, key: str, default=None):
    """兼容 JDAnalysisOut 对象和 dict 两种调用风格。"""
    if isinstance(jd_analysis, dict):
        return jd_analysis.get(key, default)
    return getattr(jd_analysis, key, default)


# ── 主入口（V1.3：新增 generated_content 参数，按 ID 合并 AI bullets） ── #

def build(
    db: Session,
    user_id: str,
    matched_experiences: list[dict],
    jd_analysis: object,  # dict | JDAnalysisOut 都兼容
    all_experiences: Optional[list[models.Experience]] = None,
    *,
    # V1.3 Profile 数据源（身份字段只取 request，求职意向只取 JD）
    db_profile: Optional[dict] = None,                 # 保留兼容，V1.3 不使用
    request_profile: Optional[dict] = None,            # 身份字段唯一来源
    resume_content_profile: Optional[dict] = None,     # 保留兼容，V1.3 不使用
    # V1.3 T3：AI 生成的 bullets（按 experience_id 合并）
    generated_content: Optional[GeneratedResumeContent] = None,
    # 裁剪上限（仅本层用，渲染层只能告警不能截断）
    max_education: int = 3,
    max_work: int = 3,
    max_projects: int = 3,
    max_awards: int = 5,
    # 保留兼容（V1.3 忽略，始终使用新规则）
    enforce_v12_profile: bool = True,
) -> tuple[ResumeDocument, dict]:
    """构建 V1.3 标准 ResumeDocument（ID 合并 AI bullets + 裁剪前移 + 身份字段只取 request）。

    返回 (resume_doc, build_meta)。

    T4 事实保护（PLAN §3.3）：
      - WorkItem/ProjectItem 的事实字段（company/role/time/...）全部来自 SQL；
      - AI 仅能覆盖 bullets 列表；AI 缺失 bullets 时回退 SQL description+achievements；
      - 身份字段（name/phone/email/location）只取 request_profile，缺失留空；
      - 求职意向（target_position）只取 JDAnalysis.position；
      - summary 恒为空（V1.3 不生成、不渲染个人总结）。
    """
    if all_experiences is None:
        from services import experience_service
        all_experiences = experience_service.list_experiences(db, user_id)

    # ── 1. score 映射（matched 优先序） ──
    score_map: dict[str, float] = {}
    matched_ids: set[str] = set()
    for m in matched_experiences:
        m_id = m.get("id") or ""
        scores = m.get("scores") or {}
        final = scores.get("final", 0.0) if isinstance(scores, dict) else 0.0
        score_map[m_id] = float(final)
        matched_ids.add(m_id)

    # ── 1b. 构造 AI bullets 索引（experience_id → bullets） ──
    ai_bullets_map: dict[str, list[str]] = {}
    if generated_content is not None:
        for item in generated_content.experiences:
            if item.experience_id and item.bullets:
                ai_bullets_map[item.experience_id] = [b for b in item.bullets if b and b.strip()]

    # ── 2. 构造经历项列表：事实字段仅来自 SQL，bullets AI > SQL fallback ──
    education_items: list[EducationItem] = []
    work_items: list[WorkItem] = []
    project_items: list[ProjectItem] = []

    for exp in all_experiences:
        priority = score_map.get(exp.id, 0.0)
        if exp.type == "education":
            education_items.append(EducationItem(
                school=exp.company or exp.title or "",
                major=exp.role or "",
                degree="",
                time=exp.time or "",
                description=exp.description or "",
                priority=priority,
                experience_id=exp.id,
            ))
        elif exp.type == "work" and exp.id in matched_ids:
            ai_bullets = ai_bullets_map.get(exp.id)
            if ai_bullets:
                # AI 生成 bullets：直接填充 bullets 字段，旧字段留空避免 to_standard 覆盖
                work_items.append(WorkItem(
                    company=exp.company or "",
                    role=exp.role or "",
                    time=exp.time or "",
                    bullets=ai_bullets,
                    priority=priority,
                    experience_id=exp.id,
                ))
            else:
                # T4 回退：SQL description + achievements
                work_items.append(WorkItem(
                    company=exp.company or "",
                    role=exp.role or "",
                    time=exp.time or "",
                    description=exp.description or "",
                    achievements=list(exp.achievements or []),
                    skills=list(exp.skills or []),
                    priority=priority,
                    experience_id=exp.id,
                ))
        elif exp.type == "project" and exp.id in matched_ids:
            ai_bullets = ai_bullets_map.get(exp.id)
            if ai_bullets:
                project_items.append(ProjectItem(
                    title=exp.title or "",
                    role=exp.role or "",
                    time=exp.time or "",
                    bullets=ai_bullets,
                    priority=priority,
                    experience_id=exp.id,
                ))
            else:
                project_items.append(ProjectItem(
                    title=exp.title or "",
                    role=exp.role or "",
                    time=exp.time or "",
                    description=exp.description or "",
                    achievements=list(exp.achievements or []),
                    skills=list(exp.skills or []),
                    priority=priority,
                    experience_id=exp.id,
                ))

    # ── 3. 裁剪前移（按 priority 降序，top max_* 截断）—— 唯一内容选择入口 ──
    max_items_trimmed: dict[str, list[str]] = {}

    def _apply_max(items, limit: int, key: str) -> list:
        if len(items) > limit:
            max_items_trimmed[key] = [
                (getattr(x, "experience_id", None) or "") for x in items[limit:]
                if getattr(x, "experience_id", None)
            ]
            return items[:limit]
        return items

    education_items.sort(key=lambda x: (x.priority, x.time or ""), reverse=True)
    education_items = _apply_max(education_items, max_education, "education")

    work_items.sort(key=lambda x: x.priority, reverse=True)
    work_items = _apply_max(work_items, max_work, "work")

    project_items.sort(key=lambda x: x.priority, reverse=True)
    project_items = _apply_max(project_items, max_projects, "projects")

    # ── 4. Profile 处理（V1.3：身份字段只取 request，求职意向只取 JD） ──
    jd_position = _jd_get(jd_analysis, "position", "") or ""
    profile, profile_source = ProfileResolver.resolve(
        request_profile=request_profile,
        jd_position=jd_position,
        db_profile=db_profile,                  # 保留兼容，V1.3 不使用
        resume_content_profile=resume_content_profile,  # 同上
    )

    # ── 5. 技能 & 奖项（奖项也在这里按 max_awards 截断） ──
    required_skills = _jd_get(jd_analysis, "required_skills") or []
    skills_freq = _collect_skills(all_experiences, list(required_skills))
    skill_groups = _categorize_skills(skills_freq)

    awards = _extract_awards(all_experiences)[:max_awards]

    # ── 6. summary（V1.3 不生成、不渲染个人总结） ──
    summary_in_profile = ""  # PLAN §3.3：V1.3 不生成或渲染个人总结/自我评价

    # ── 7. 组装 ResumeDocument ──
    # 构建前统计 AI 覆盖 vs SQL fallback（仅用于调试 meta）
    final_ids_work = {w.experience_id for w in work_items if w.experience_id}
    final_ids_project = {p.experience_id for p in project_items if p.experience_id}
    ai_covered_ids = sorted((final_ids_work | final_ids_project) & ai_bullets_map.keys())
    fallback_ids = sorted((final_ids_work | final_ids_project) - ai_bullets_map.keys())

    doc = ResumeDocument(
        profile=profile,
        summary=summary_in_profile,
        education=education_items,
        work=work_items,
        projects=project_items,
        skills=skill_groups,
        awards=awards,
        meta={
            "jd_position": jd_position,
            "matched_count": len(matched_ids),
            "total_experiences": len(all_experiences),
            "user_id": user_id,
            "profile_source": profile_source,
            "ai_covered_experience_ids": ai_covered_ids,
            "fallback_sql_experience_ids": fallback_ids,
        },
    )

    # ── 8. 收尾：旧字段 → 新字段 一次性迁移（下游拿标准字段） ──
    doc = doc.to_standard()

    build_meta = {
        "profile_source": profile_source,
        "ai_covered_experience_ids": ai_covered_ids,
        "fallback_sql_experience_ids": fallback_ids,
        "ai_unrecognized_experience_ids": sorted(
            set(ai_bullets_map.keys()) - (final_ids_work | final_ids_project)
        ),
        "max_items_trimmed": max_items_trimmed,
        "counts": {
            "education": len(doc.education),
            "work": len(doc.work),
            "projects": len(doc.projects),
            "awards": len(doc.awards),
            "skill_groups": len(doc.skills),
        },
    }

    return doc, build_meta
