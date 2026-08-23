"""Pydantic 请求/响应模型（对外契约）。"""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator


def _coerce_to_list(v: Any) -> list:
    """LLM 偶尔把列表字段返回为字符串，统一兜底为 list。"""
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


# ═══════════════════════════════════════════════════════════════════════════
# V1.3：统一响应 / 错误 结构（PLAN §4.3）
# ═══════════════════════════════════════════════════════════════════════════
class DomainErrorOut(BaseModel):
    """统一错误响应体，由 errors.DomainError 映射。"""

    ok: bool = False
    error_code: str
    stage: str
    message: str
    retryable: bool
    details: dict[str, Any] = {}


# ═══════════════════════════════════════════════════════════════════════════
# 基础经历 / 简历条目
# ═══════════════════════════════════════════════════════════════════════════

class ExperienceItem(BaseModel):
    type: str = ""
    title: str = ""
    company: str = ""
    time: str = ""
    role: str = ""
    description: str = ""
    skills: List[str] = []
    achievements: List[str] = []
    raw_text: str = ""

    @field_validator("skills", "achievements", mode="before")
    @classmethod
    def _coerce_list_fields(cls, v: Any) -> list:
        return _coerce_to_list(v)

    @field_validator("type", "title", "company", "time", "role", "description", "raw_text", mode="before")
    @classmethod
    def _coerce_str_fields(cls, v: Any) -> str:
        """LLM 偶尔返回 null，兜底为空字符串。"""
        if v is None:
            return ""
        return v


class ExperienceOut(ExperienceItem):
    id: str
    user_id: Optional[str] = None


class ExtractRequest(BaseModel):
    resume_text: str


class ExtractResponse(BaseModel):
    experiences: List[ExperienceItem]


class JDRequest(BaseModel):
    jd_text: str


class GenerateRequest(BaseModel):
    jd_analysis: dict
    user_id: Optional[str] = None
    top_k: int = 5


class JDAnalysisOut(BaseModel):
    """JD 分析结果（V1.1：7 字段）。"""

    position: str = ""
    industry: str = ""
    required_skills: List[str] = []
    preferred_skills: List[str] = []
    responsibilities: List[str] = []
    keywords: List[str] = []
    experience_preferences: List[str] = []

    @field_validator(
        "required_skills", "preferred_skills", "responsibilities",
        "keywords", "experience_preferences", mode="before",
    )
    @classmethod
    def _coerce_list_fields(cls, v: Any) -> list:
        return _coerce_to_list(v)

    @field_validator("position", "industry", mode="before")
    @classmethod
    def _coerce_str_fields(cls, v: Any) -> str:
        if v is None:
            return ""
        return v


class ExperienceExtractionResult(BaseModel):
    """单段简历章节的提取结果包装（用于 chat_structured）。"""

    experiences: List[ExperienceItem] = []

    @field_validator("experiences", mode="before")
    @classmethod
    def _coerce_experiences(cls, v: Any) -> list:
        if v is None:
            return []
        if isinstance(v, dict):
            return [v]
        return v


class MatchScores(BaseModel):
    """RAG 多因素评分（V1.1）。"""

    semantic: float = 0.0
    skill: float = 0.0
    role: float = 0.0
    final: float = 0.0


class MatchedExperience(BaseModel):
    id: str
    text: str
    metadata: dict
    distance: Optional[float] = None
    scores: Optional[MatchScores] = None
    reason: str = ""


class ResumeOut(BaseModel):
    markdown: str
    matched_experiences: List[MatchedExperience] = []
    deprecation_warning: Optional[str] = None


class ResumeTextOut(BaseModel):
    text: str


# ── V1.2 新增：模板填充模块 ────────────────────────────────────────


class TemplateSectionSummary(BaseModel):
    """模板上传接口返回的章节摘要（含完整定位信息）。

    写入时不靠标题名字定位，而是靠 paragraph_start / paragraph_end 圈定区域。
    """
    section_name: str
    type: str
    location: int                       # = title_paragraph_index，标题段落位置
    style_id: Optional[str] = None      # Word 原生 style 名
    paragraph_start: int                # 内容区域起始 paragraph index
    paragraph_end: int                  # 内容区域结束 paragraph index
    has_unsupported_objects: bool = False


class TemplateUploadResponse(BaseModel):
    """上传模板后返回解析结果。"""
    template_id: str
    section_count: int
    sections: List[TemplateSectionSummary]
    warnings: List[str] = []


class DocxGenerateRequest(BaseModel):
    """基于模板生成 Word 简历的请求。"""
    template_id: str
    jd_analysis: dict                   # 复用 V1.1 的 JDAnalysisOut
    user_id: Optional[str] = None
    top_k: int = 5
    layout_profile: str = "standard"    # "compact" | "standard"


class DocxGenerateResponse(BaseModel):
    """生成结果的元信息（文件内容通过 FileResponse 返回）。"""
    file_name: str
    page_count: int
    warnings: List[str] = []
    sections_filled: List[str] = []
    sections_missing: List[str] = []
    # V1.2 新增：被裁剪的条目清单（selected=False 的条目）
    items_filtered: List[dict] = []


# ═══════════════════════════════════════════════════════════════════════════
# V1.3 新增：核心 DOCX 链路契约（PLAN §4.1 / §4.2）
# ═══════════════════════════════════════════════════════════════════════════

class RequestProfile(BaseModel):
    """核心接口请求中显式传入的 Profile。

    必填：name；target_position 缺失时用 JDAnalysis.position 兜底。
    """

    name: str
    phone: str = ""
    email: str = ""
    location: Optional[str] = None
    target_position: str = ""
    summary: Optional[str] = None


class ResumeDocxGenerateRequest(BaseModel):
    """PLAN §4.1：唯一核心链路入口请求。

    必填：jd_text、profile、profile.name；
    target_position 缺失 → 用 JDAnalysis.position；
    user_id / template_id 默认；top_k 范围 1–20。
    """

    user_id: Optional[str] = None
    template_id: str = "pm_template"
    jd_text: str
    profile: RequestProfile
    top_k: int = Field(default=5, ge=1, le=20)


class GeneratedExperienceItem(BaseModel):
    """AI 生成的单条经历 bullets。

    约束（T3 strict 校验）：
    - experience_id 必须属于本次 RAG 命中集合；
    - AI 不得修改公司/岗位/时间等事实字段（这些由 Builder 从 SQL 取）。
    """

    experience_id: str
    bullets: List[str] = []

    @field_validator("bullets", mode="before")
    @classmethod
    def _coerce_bullets(cls, v: Any) -> list:
        return _coerce_to_list(v)


class GeneratedResumeContent(BaseModel):
    """PLAN §4.2：ResumeContentGenerator 的结构化输出。AI 只生成 bullets。"""

    experiences: List[GeneratedExperienceItem] = []


class StageStatus(BaseModel):
    stage: str
    status: str  # "done" | "failed" | "skipped"
    duration_ms: Optional[float] = None
    note: Optional[str] = None


class BuildCounts(BaseModel):
    """ResumeBuilder 各板块最终输出条目数（强类型，代替裸 dict）。"""

    education: int = 0
    work: int = 0
    projects: int = 0
    awards: int = 0
    skill_groups: int = 0


class BuildMeta(BaseModel):
    """ResumeBuilder 的全量诊断输出。

    T4 事实保护证据：
      - ai_covered_experience_ids：AI 提供了 bullets，最终条目用的是 AI bullets
      - fallback_sql_experience_ids：AI 没提供 bullets，走 SQL description+achievements 回退
      - ai_unrecognized_experience_ids：AI 返回了但不在本次匹配集合里，被 ResumeContentGenerator 丢弃
      - max_items_trimmed：Builder（唯一内容选择入口）按 max_* 裁剪的板块 + 被裁 id 列表
    """

    profile_source: str = ""
    ai_covered_experience_ids: List[str] = []
    fallback_sql_experience_ids: List[str] = []
    ai_unrecognized_experience_ids: List[str] = []
    max_items_trimmed: dict[str, List[str]] = {}  # section_key → trimmed_ids
    # R7: per-bullet fact_refs mapping (experience_id → list of fact_refs per bullet)
    bullet_fact_refs: dict[str, List[List[str]]] = {}
    # R7: per-experience fact_refs (backward compat, compressed from bullets)
    fact_refs_per_experience: dict[str, List[str]] = {}
    # R7: builder mode indicator
    builder_mode: str = ""
    counts: BuildCounts = BuildCounts()


class RenderSectionItemCount(BaseModel):
    """渲染前后单个板块的条目数对照（用于 PLAN §8.2 验证 Renderer 不截断）。"""

    section_id: str
    input_items: int
    rendered_items: int


class RenderStats(BaseModel):
    """渲染层统计：Renderer 不截断的证据。

    若任何板块 rendered < input 且非 max_items 保险兜底触发，即 T8 失败。
    """

    sections: List[RenderSectionItemCount] = []
    unreplaced_placeholders: List[str] = []
    capacity_warnings: List[str] = []

    @property
    def all_sections_preserved(self) -> bool:
        return all(s.input_items == s.rendered_items for s in self.sections)


class ResumeDocxGenerateResponse(BaseModel):
    """PLAN §4.3：核心接口成功响应。"""

    ok: bool = True
    file_path: str
    file_name: str
    download_url: str

    # 诊断信息
    stages: List[StageStatus] = []
    matched_experience_ids: List[str] = []
    rendered_experience_ids: List[str] = []
    profile_source: str = ""

    # 渲染 / 构建元信息（强类型）
    page_count: Optional[int] = None
    warnings: List[str] = []
    build_counts: BuildCounts = BuildCounts()
    build_meta: BuildMeta = BuildMeta()
    render_stats: RenderStats = RenderStats()
    template_id: str = ""



# ═══════════════════════════════════════════════════════════════════════════
# V1.5.0 新增：受约束改写契约（PLAN §4.4 / T5）
# ═══════════════════════════════════════════════════════════════════════════

class GeneratedBullet(BaseModel):
    """V1.5.0：单条 bullet + 其引用的 fact_refs（PLAN §4.4）。

    - bullet：受约束改写后的表达（不新增事实）
    - fact_refs：该 bullet 引用的 fact_id 列表（必须属于该经历的已选事实）
    """

    bullet: str = ""
    fact_refs: List[str] = []

    @field_validator("fact_refs", mode="before")
    @classmethod
    def _coerce_fact_refs(cls, v):
        return _coerce_to_list(v)


class GeneratedExperienceItemV15(BaseModel):
    """V1.5.0：单条经历的受约束改写结果。

    - bullets：带 fact_refs 的 bullet 列表
    - insufficient：材料不足标记（True 时不输出通用空话补齐）
    - insufficient_reason：不足原因
    """

    experience_id: str
    bullets: List[GeneratedBullet] = []
    insufficient: bool = False
    insufficient_reason: str = ""

    @field_validator("bullets", mode="before")
    @classmethod
    def _coerce_bullets_v15(cls, v):
        return _coerce_to_list(v)


class GeneratedResumeContentV15(BaseModel):
    """V1.5.0：受约束改写的结构化输出（PLAN §4.4）。

    LLM 只接收目标岗位 + 入选经历 + 表达侧重 + 可使用事实；
    每条 bullet 必须返回 fact_refs；越界引用被拒绝并告警。
    """

    experiences: List[GeneratedExperienceItemV15] = []

    @field_validator("experiences", mode="before")
    @classmethod
    def _coerce_experiences_v15(cls, v):
        return _coerce_to_list(v)
