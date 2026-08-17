"""V1.2 简历中间抽象——所有渲染器（DOCX/MD/PDF）的统一输入。

设计约束：
- ResumeDocument 完全不含任何 Word/Markdown 渲染信息（纯事实层）
- ResumeBuilder 是唯一构造 ResumeDocument 的入口（构造时所有条目 selected=True）
- 裁剪前移到 ResumeBuilder.build()（按 max_items 直接截断，渲染层不再裁）
- 所有渲染器（docx_writer / 未来 PDF / HTMLRenderer）只读消费
"""
from typing import List, Optional

from pydantic import BaseModel


class Profile(BaseModel):
    """个人信息头部（数据隔离原则：绝对不从模板 DOCX 取默认值，只从 DB/request/AI 来）。

    必填字段（缺失直接 ProfileIncompleteError）：
      - name
      - target_position
    """
    name: str = ""
    phone: str = ""
    email: str = ""
    location: Optional[str] = None    # 所在地（城市，可选）
    target_position: str = ""         # 求职意向/目标岗位（必填）
    summary: Optional[str] = None     # 自我评价 / 个人简介（可选）

    # --- 兼容旧字段（V1.1 → V1.2 迁移期） ---
    # V1.1 用 job_intent，V1.2 统一为 target_position。保留此字段做读取兼容，
    # 写入时 V1.2 只写 target_position，ProfileResolver 负责把 job_intent 搬到 target_position
    job_intent: Optional[str] = None

    def to_standard(self) -> "Profile":
        """旧字段 → 新字段的一次性迁移（让 ProfileResolver 不用关心旧字段）。"""
        if self.job_intent and not self.target_position:
            self.target_position = self.job_intent
            self.job_intent = None
        return self


class ResumeItemMixin(BaseModel):
    """所有经历条目的通用字段（裁剪前移到 ResumeBuilder，构建时已裁到 max_items 上限）。

    - priority: 综合优先级 = RAG final score（0.0-1.0），用于排序；ResumeBuilder 排序后截断
    - selected: V1.2 构建后恒 True（因为裁剪前移，渲染层不裁）；保留字段兼容旧读取器
    """
    priority: float = 0.0
    selected: bool = True


class EducationItem(ResumeItemMixin):
    school: str = ""
    major: str = ""
    degree: str = ""                  # 学历：本科/硕士/博士
    start_time: str = ""              # "2022.09"
    end_time: str = ""                # "2026.06" 或 "至今"
    gpa: Optional[str] = None
    description: Optional[str] = None  # 获奖/主修课/排名（单行或多行字符串，为空则渲染器不占行）
    experience_id: str = ""

    # --- 兼容旧字段：time（V1.1 "2022.09 - 2026.06" 形式） ---
    time: Optional[str] = None

    def to_standard(self) -> "EducationItem":
        """旧 time 字段 → start_time / end_time 一次性迁移。"""
        if self.time and not (self.start_time and self.end_time):
            parts = [p.strip() for p in self.time.split("-", 1)]
            if len(parts) == 2:
                self.start_time, self.end_time = parts
            self.time = None
        return self


class WorkItem(ResumeItemMixin):
    company: str = ""
    role: str = ""
    start_time: str = ""
    end_time: str = ""
    location: Optional[str] = None
    bullets: List[str] = []           # 职责/成果，每条一行（渲染器按 bullet 克隆行）
    experience_id: str = ""

    # --- 兼容旧字段：time / description / achievements ---
    time: Optional[str] = None
    description: Optional[str] = None
    achievements: Optional[List[str]] = None
    skills: Optional[List[str]] = None

    def to_standard(self) -> "WorkItem":
        """旧字段迁移：time → start/end；description+achievements → bullets。"""
        if self.time and not (self.start_time and self.end_time):
            parts = [p.strip() for p in self.time.split("-", 1)]
            if len(parts) == 2:
                self.start_time, self.end_time = parts
            self.time = None
        if not self.bullets:
            merged: list[str] = []
            if self.description and self.description.strip():
                merged.append(self.description.strip())
            if self.achievements:
                merged.extend(self.achievements)
            self.bullets = merged
        self.description = None
        self.achievements = None
        self.skills = None
        return self


class ProjectItem(ResumeItemMixin):
    name: str = ""                   # V1.2 用 name（替代旧的 title）
    role: str = ""
    start_time: str = ""
    end_time: str = ""
    bullets: List[str] = []           # 项目背景/技术方案/成果，每条一行
    tech_stack: Optional[List[str]] = None
    experience_id: str = ""

    # --- 兼容旧字段：title / time / description / achievements / skills ---
    title: Optional[str] = None
    time: Optional[str] = None
    description: Optional[str] = None
    achievements: Optional[List[str]] = None
    skills: Optional[List[str]] = None

    def to_standard(self) -> "ProjectItem":
        """旧字段迁移：title → name；time → start/end；description+achievements → bullets。"""
        if self.title and not self.name:
            self.name = self.title
            self.title = None
        if self.time and not (self.start_time and self.end_time):
            parts = [p.strip() for p in self.time.split("-", 1)]
            if len(parts) == 2:
                self.start_time, self.end_time = parts
            self.time = None
        if not self.bullets:
            merged: list[str] = []
            if self.description and self.description.strip():
                merged.append(self.description.strip())
            if self.achievements:
                merged.extend(self.achievements)
            self.bullets = merged
        self.description = None
        self.achievements = None
        self.skills = None
        return self


class SkillGroup(BaseModel):
    """技能分组（按类聚合，避免一条条罗列）。"""
    category: str = ""          # 如"编程语言"/"产品工具"/"AI 框架"
    items: List[str] = []


class ResumeDocument(BaseModel):
    """简历中间抽象——渲染无关的纯事实层。

    V1.2 新铁律：
      - ResumeBuilder.build() 负责**组装 + 裁剪**（按 JD 优先序 + max_items 一次性截断）
      - ResumeDocument 输出后，任何渲染层（DOCX/PDF/HTML）**不得再删条目、改事实**
      - 数据来源：DB / API request / AI 生成；模板只提供结构，不提供任何事实

    兼容：
      - 旧的 summary 字段保留（V1.2 统一走 profile.summary，构建时 ResumeBuilder 会搬过去）
    """
    profile: Profile = Profile()
    education: List[EducationItem] = []
    work: List[WorkItem] = []
    projects: List[ProjectItem] = []
    skills: List[SkillGroup] = []
    awards: List[str] = []                  # 获奖/证书（扁平字符串列表）
    meta: dict = {}                         # 元信息：JD position、生成时间、top_k 等

    # --- 兼容旧字段 ---
    summary: str = ""                       # V1.1：个人优势/自我评价；V1.2 请使用 profile.summary

    def to_standard(self) -> "ResumeDocument":
        """V1.1 → V1.2 一次性迁移：
        - profile 旧 job_intent → target_position
        - 所有 EducationItem/WorkItem/ProjectItem 旧字段迁移
        - self.summary → profile.summary（如果 profile.summary 为空）
        """
        self.profile = self.profile.to_standard()
        self.education = [e.to_standard() for e in self.education]
        self.work = [w.to_standard() for w in self.work]
        self.projects = [p.to_standard() for p in self.projects]
        if self.summary and not self.profile.summary:
            self.profile.summary = self.summary
            self.summary = ""
        return self
