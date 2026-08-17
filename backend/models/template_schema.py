"""V1.2 模板结构模型。

新路线（V1.2 主用）：
  LayoutSpec / SectionSpec / RowSpec / TemplateSpec —— 标准化模板 JSON 描述的对象化表示，
  用 style（段落命名样式名）定位，不靠文本匹配。
"""
from typing import List, Optional

from pydantic import BaseModel, field_validator


# 标准化章节类型（type 字段枚举）
SECTION_TYPES = {
    "profile": "个人信息区（姓名+联系方式+求职意向+自我评价，V1.2 主用）",
    "header": "个人信息头部（V1.1 旧模板兼容）",
    "summary": "个人优势/自我评价",
    "education": "教育背景",
    "work": "工作/实习经历",
    "project": "项目经历",
    "skills": "专业技能",
    "awards": "获奖证书",
    "other": "其他（自定义）",
}


# ============================================================
# V1.2 新路线：标准化模板 JSON 描述的对象化
# ============================================================

class LayoutSpec(BaseModel):
    """模板整体排版规格（来自模板 JSON 的 layout 字段）。"""
    page_size: str = "A4"
    margin_cm: dict = {}                  # {top, bottom, left, right}
    default_font_cn: str = "微软雅黑"
    default_font_en: str = "Microsoft YaHei"
    page_limit: int = 1                   # 期望页数（超了时 LayoutOptimizer 按规则降级）


class CellSpec(BaseModel):
    """段落中单个占位符 Cell 的声明（一行中包含多个 {{xxx}} 时使用）。

    例如 ItemTitle 行：
        {{edu.start_time}} - {{edu.end_time}}        {{edu.school}}        {{edu.major}}（{{edu.degree}}）
    每个占位符对应一个 CellSpec。渲染时不依赖此对象（fill_placeholders 会全局扫），
    仅用于 JSON 自描述和调试报告。
    """
    placeholder: Optional[str] = None       # "edu.start_time" / "work.company" 等（不含{{}}）
    description: Optional[str] = None       # 人类可读注释
    bold: Optional[bool] = None             # V1.2.1 P0-1：该 Cell 是否加粗；None 表示继承模板 Run 本身的 rPr
    keyword_bold: Optional[bool] = None     # 若内容含「：」，冒号前自动加粗（V1.2.1 P0-1）


class RowSpec(BaseModel):
    """一个章节块中的一行/一类行的声明。

    两种模式：
      - 普通行（repeat 为空）：每行对应一个段落
      - 重复行（repeat 非空）：该行会被渲染器按 repeat 指向的列表字段克隆多次；
    """
    style: str                                    # Word 中段落命名样式名（必填）
    placeholder: Optional[str] = None             # 简单行：形如"{{edu.school}}"（模板描述用，实际渲染走 fill_placeholders 全局扫）
    repeat: Optional[str] = None                  # 形如"work.bullets" / "awards" / "skills"；None=普通行
    cells: Optional[List[CellSpec]] = None        # 复杂行：多个占位符 Cell 的列表
    # 注：V1.2 不暴露 skip_if_empty / join filter 为 JSON 配置，按代码内固定规则执行

    @field_validator("placeholder", "cells")
    @classmethod
    def _check_at_least_one(cls, v, info):
        """placeholder 或 cells 至少填一个（都空则无法自描述）。"""
        return v  # 不强校验，因为 render 阶段不靠这个，只是描述性字段


class SectionSpec(BaseModel):
    """模板中的一个章节声明（标准化模板用，**不靠文本定位**）。"""
    id: str                               # 章节唯一 id（JSON 里的 id，如 profile / education / work）
    type: str                             # 标准化类型（见 SECTION_TYPES：profile/education/...）
    required: bool = False                # 无内容时是否报错
    max_items: Optional[int] = None       # 渲染层兜底截断上限（> ResumeBuilder 的上限时生效）
    title_style: Optional[str] = None     # 章节标题段的 style 名（如 SectionTitle_Education）。profile 类型没有标题段
    rows: Optional[List[RowSpec]] = None  # profile 类型使用：一行一行声明
    item_block: Optional[List[RowSpec]] = None  # work/project/education/awards/skills 类型使用：每个 item 的多行模板

    @field_validator("type")
    @classmethod
    def _validate_type(cls, v: str) -> str:
        if v not in SECTION_TYPES:
            raise ValueError(f"unknown section type: {v!r}; allowed: {sorted(SECTION_TYPES)}")
        return v


class TemplateSpec(BaseModel):
    """标准化模板的完整描述（对应 templates/<id>.json 文件）。"""
    id: str
    version: str = "1.0"
    display_name: str = ""
    author: str = ""
    layout: LayoutSpec = LayoutSpec()
    sections: List[SectionSpec] = []

    # --- 辅助 ---
    def sections_by_type(self, typ: str) -> List[SectionSpec]:
        return [s for s in self.sections if s.type == typ]
