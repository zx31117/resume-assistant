"""V2.1.0 R9：pm_template v1.2 的 reportlab PDF 渲染器。

视觉真源 = templates/_build_templates.py 的 V1.2 参数（与 pm_template.docx / docx 渲染同一套
视觉规格），本文档只做像素侧还原，不引入第二套样式：
  - 页面 A4；页边距 T=0.92cm B=1.39cm L=1.13cm R=1.09cm（与 build 常量一一对应）
  - 字号：姓名 20pt / 章节标题 12pt / 经历标题与正文 bullet 10.6pt / 联系方式与求职意向 10pt
  - 经历标题行“三列”Tab 布局：时间(左) / 学校·公司·项目名(中) / 专业·职位(右)（Word 用
    center/right 制表位；PDF 侧等价于中心对齐 + 右对齐锚点，逐段手排，不依赖制表符）
  - 章节标题下方底分隔线（还原 Word w:pBdr bottom）
  - bullet 前缀“●”（PDF 用 U+25CF，STSong-Light 含字形；Word 模板用 ⚫，规格允许 ●/⚫ 互换）
  - 全部常规不加粗；仅章节标题 / 姓名 / 经历标题模拟粗体
  - 右上角照片占位框（无真实照片时画空占位框，尺寸与偏移同 build 常量）
  - 空章节隐藏规则与 docx TemplateRenderer 一致（required 章节为空记 warning 并跳过；
    可选章节为空不渲染、加 warning）

输入输出：
  render(resume_doc, template_id, backend_root) -> (pdf_bytes, warnings)
  pdf_bytes 为内存 PDF（调用方负责落盘到 OUTPUT_DIR）。

中文渲染：使用内置 Adobe CID 字体 STSong-Light（UnicodeCIDFont），不依赖外部 TTF。
"""
from __future__ import annotations

import io
import json
import os

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

from models.resume_document import (
    EducationItem,
    Profile,
    ProjectItem,
    ResumeDocument,
    SkillGroup,
    WorkItem,
)
from models.template_schema import TemplateSpec

# ── 视觉参数（与 templates/_build_templates.py 同源同步；改模板必须先改这里再重跑 fixture）──
FONT_CN = "STSong-Light"

CM = 28.3465  # 1cm ≈ 28.3465pt
MARGIN_TOP = 0.92 * CM
MARGIN_BOTTOM = 1.39 * CM
MARGIN_LEFT = 1.13 * CM
MARGIN_RIGHT = 1.09 * CM

COLOR_TITLE = "0D0D0D"   # 姓名/章节标题（同 build COLOR_TITLE）
COLOR_BODY = "262626"    # 正文（同 build COLOR_BODY）

SZ_NAME = 20.0
SZ_TITLE = 12.0
SZ_BODY = 10.6
SZ_CONTACT = 10.0

# 行距（同 build：正文行高约 18pt，profile/标题行各自不同）
LEAD_NAME = 24.0
LEAD_TARGET = 14.0
LEAD_CONTACT = 14.0
LEAD_TITLE = 16.0
LEAD_BODY = 18.0

BULLET = "● "            # docx 模板用 ⚫（U+26AB），PDF 用 ●（U+25CF），规格允许等价替换
DIVIDER_W = 0.75         # 章节标题底分隔线宽度（pt），docx pBdr sz=6 ≈ 0.75pt

# 照片占位框（cm→pt；同 _build_templates._add_photo_placeholder）
PHOTO_LEFT_CM = 21.0 - 1.63 - 2.375     # ≈16.995
PHOTO_TOP_CM = 0.58
PHOTO_W = 2.375 * CM
PHOTO_H = 2.9 * CM

# 章节显示标题文本（与 _build_templates.py 中 doc.add_paragraph(...) 的静态文案一致，
# docx 章节标题段落即此文本；TemplateSpec 只携带 style 名不带文案，故此处显式同步）
_SECTION_TITLES = {
    "education": "教育背景",
    "work": "实习经历",
    "project": "项目经历",
    "skills": "技能专长",
    "awards": "荣誉奖项",
    "summary": "自我评价",
}

pdfmetrics.registerFont(UnicodeCIDFont(FONT_CN))


def _load_spec(template_id: str, backend_root: str) -> TemplateSpec:
    """与 docx_writer.load_template_assets 相同的 config/template_mapping.json 寻址。

    只读模板 JSON（PDF 渲染不需要 docx 二进制；同一 template json/spec 即 layout 来源）。
    """
    mapping_path = os.path.join(backend_root, "config", "template_mapping.json")
    with open(mapping_path, "r", encoding="utf-8") as f:
        mapping = json.load(f)
    if template_id not in mapping:
        raise KeyError(f"template_id={template_id!r} 未在 config/template_mapping.json 注册")
    entry = mapping[template_id]
    json_rel = entry["json"].replace("/", os.sep)
    json_path = os.path.join(backend_root, json_rel)
    with open(json_path, "r", encoding="utf-8") as f:
        return TemplateSpec(**json.load(f))


def _hex_color(v: str) -> Color:
    if not v.startswith("#"):
        v = "#" + v
    return HexColor(v)


def _measure(text: str, size: float) -> float:
    return pdfmetrics.stringWidth(text, FONT_CN, size)


def _wrap(text: str, size: float, max_w: float) -> list[str]:
    """按可用宽度做逐字折行（CJK 与 ASCII 混合场景足够稳定）。"""
    if not text:
        return [""]
    lines: list[str] = []
    cur = ""
    for ch in text:
        if cur and _measure(cur + ch, size) > max_w:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


class _PdfWriter:
    """直接操作 reportlab canvas 的流式排版器（无第三方 flowable 依赖）。"""

    def __init__(self, c):
        self.c = c
        self.page_w, self.page_h = A4
        self.left = MARGIN_LEFT
        self.top = self.page_h - MARGIN_TOP
        self.bottom = MARGIN_BOTTOM
        self.width = self.page_w - MARGIN_LEFT - MARGIN_RIGHT
        self.x = self.left
        self.y = self.top
        self.drawn = False

    # ── 页面控制 ───────────────────────────────────────────────
    def _ensure(self, need: float) -> None:
        """need 单位为 pt：从当前 y 向下排 need 高度之前确认放得下。"""
        if self.y - need < self.bottom:
            self.c.showPage()
            self.y = self.top
            self.drawn = True

    def _gap(self, pt: float) -> None:
        self._ensure(0)
        self.y -= pt

    # ── 单行文本 ───────────────────────────────────────────────
    def _emit(self, text: str, x: float, y: float, size: float, color: str,
              bold: bool = False) -> None:
        if not text:
            return
        t = self.c.beginText(x, y)
        t.setFont(FONT_CN, size)
        t.setFillColor(_hex_color(color))
        if bold:
            # STSong-Light 为单一字重；用 text render mode=2（fill+stroke）模拟粗体
            t.setTextRenderMode(2)
            self.c.setLineWidth(0.6)
        t.textOut(text)
        self.c.drawText(t)
        if bold:
            self.c.setLineWidth(1.0)

    def draw_plain_row(self, text: str, size: float, leading: float, *,
                       color: str = COLOR_BODY, bold: bool = False,
                       space_before: float = 0.0, space_after: float = 0.0) -> None:
        """整行文本（自动折行），每物理行推进 leading。"""
        if not text:
            return
        if space_before:
            self._gap(space_before)
        lines = _wrap(text, size, self.width)
        self._ensure(leading * len(lines))
        for ln in lines:
            self._emit(ln, self.left, self.y, size, color, bold)
            self.y -= leading
        if space_after:
            self._gap(space_after)

    # ── bullet（● 前缀 + 悬挂缩进）────────────────────────────
    def draw_bullet(self, text: str, *, size: float = SZ_BODY, leading: float = LEAD_BODY,
                    space_after: float = 1.0) -> None:
        if not text:
            return
        self._ensure(leading)
        indent = _measure(BULLET, size) + 2.0
        first_w = self.left + self.width - indent
        lines = _wrap(text, size, first_w)
        for i, ln in enumerate(lines):
            if i == 0:
                self._emit(BULLET, self.left, self.y, size, COLOR_BODY)
                self._emit(ln, self.left + indent, self.y, size, COLOR_BODY)
            else:
                self._emit(ln, self.left + indent, self.y, size, COLOR_BODY)
            self.y -= leading
        if space_after:
            self._gap(space_after)

    # ── 章节标题：加粗 + 底分隔线 ─────────────────────────────
    def draw_section_title(self, text: str) -> None:
        self._gap(8.0)
        self._ensure(LEAD_TITLE + DIVIDER_W)
        self._emit(text, self.left, self.y, SZ_TITLE, COLOR_TITLE, bold=True)
        line_y = self.y - 3.0
        self.c.setStrokeColor(_hex_color(COLOR_TITLE))
        self.c.setLineWidth(DIVIDER_W)
        self.c.line(self.left, line_y, self.left + self.width, line_y)
        self.y -= LEAD_TITLE
        self._gap(4.0)

    # ── 经历标题行：左(时间) / 中(学校·公司·项目) / 右(专业·职位) ──
    def draw_item_title(self, left_text: str, center_text: str, right_text: str) -> None:
        """还原 Word 的三列制表位布局（等价于：中列中心锚定、右列右缘锚定）。"""
        self._gap(3.0)
        self._ensure(LEAD_BODY)
        w = self.width
        # 名字过长时降级：宁可右对齐并允许向中列方向延展，也不与时间列重叠
        lw = _measure(left_text, SZ_BODY)
        cw = _measure(center_text, SZ_BODY)
        rw = _measure(right_text, SZ_BODY)
        # 中点 = 内容区中心（Word center tab 9.39cm ≈ 左缘 + 内容宽/2）
        center_x = self.left + (w - cw) / 2.0
        right_x = self.left + w - rw
        if lw > 0 and center_x - (self.left + lw) < 18 and cw > 0:
            center_x = self.left + lw + 18
        if right_x - max(center_x + cw if cw else 0, self.left + lw) < 18 and rw > 0:
            right_x = self.left + w - rw  # 兜底仍右对齐（容忍与中列贴近）
        if lw:
            self._emit(left_text, self.left, self.y, SZ_BODY, COLOR_BODY, bold=True)
        if cw:
            self._emit(center_text, max(center_x, self.left + lw + 12 if lw else self.left),
                       self.y, SZ_BODY, COLOR_BODY, bold=True)
        if rw:
            self._emit(right_text, right_x, self.y, SZ_BODY, COLOR_BODY, bold=True)
        self.y -= LEAD_BODY
        self._gap(1.0)

    # ── 照片占位框（空框）────────────────────────────────────
    def draw_photo_placeholder(self) -> None:
        x = PHOTO_LEFT_CM * CM
        y = self.page_h - (PHOTO_TOP_CM * CM) - PHOTO_H
        self.c.setFillColor(_hex_color("F2F2F2"))
        self.c.setStrokeColor(_hex_color("BFBFBF"))
        self.c.setLineWidth(0.5)
        self.c.rect(x, y, PHOTO_W, PHOTO_H, stroke=1, fill=1)
        self.c.setLineWidth(1.0)


def _fmt_period(start: str, end: str) -> str:
    """还原模板经历标题行的时间列文案：{{start}}-{{end}}。"""
    if not start and not end:
        return ""
    if start and end:
        return f"{start}-{end}"
    return start or end


def render(resume_doc: ResumeDocument, template_id: str,
           backend_root: str) -> tuple[bytes, list[str]]:
    """把 ResumeDocument 渲染为 pm_template v1.2 布局的 PDF。

    返回 (pdf_bytes, warnings)。章节顺序 / 空章节规则与 docx 渲染器同源：
    spec.sections 顺序逐个渲染，required 章节内容缺失记 warning 并跳过，
    可选章节为空则不渲染（记 warning），profile 区三段（姓名/求职意向/联系方式）。
    """
    spec = _load_spec(template_id, backend_root)
    warnings: list[str] = []

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"resume_{template_id}")
    w = _PdfWriter(c)

    profile: Profile = resume_doc.profile

    # ── profile 头部 ─────────────────────────────────────────────
    if profile.name:
        w.draw_plain_row(profile.name, SZ_NAME, LEAD_NAME, color=COLOR_TITLE,
                         bold=True, space_after=4.0)
    if profile.target_position:
        w.draw_plain_row(f"求职意向：{profile.target_position}", SZ_CONTACT, LEAD_TARGET,
                         space_before=2.0, space_after=2.0)
    # 联系方式整行（与 docx Profile_Line 同规则：phone/email/location 任一缺失 → 整行隐藏）
    contact_parts = [
        (f"电话：{profile.phone}" if profile.phone else ""),
        (f"邮箱：{profile.email}" if profile.email else ""),
        (f"所在地：{profile.location}" if profile.location else ""),
    ]
    contact_parts = [p for p in contact_parts if p]
    if len(contact_parts) == 3:
        w.draw_plain_row(" 丨 ".join(contact_parts), SZ_CONTACT, LEAD_CONTACT, space_after=4.0)
    w.draw_photo_placeholder()
    w.drawn = True

    # ── 各章节（与 spec.sections 同序；docx 渲染器亦按此顺序）──
    for sec in spec.sections:
        stype = sec.type
        if stype == "profile":
            continue
        title = _SECTION_TITLES.get(sec.id) or _SECTION_TITLES.get(stype, "")
        required = bool(sec.required)

        # 1) 取条目集合，按类型分派
        items: list = []
        if stype == "education":
            items = list(resume_doc.education)
        elif stype == "work":
            items = list(resume_doc.work)
        elif stype == "project":
            items = list(resume_doc.projects)
        elif stype == "skills":
            items = list(resume_doc.skills)
        elif stype == "awards":
            items = [a for a in (resume_doc.awards or []) if (a or "").strip()]
        elif stype == "summary":
            items = [ln.strip() for ln in (profile.summary or "").split("\n") if ln.strip()]
        else:
            warnings.append(f"章节[{sec.id}]类型={stype!r}无 PDF 渲染处理，已跳过")
            continue

        if not items:
            if required:
                warnings.append(f"必填章节[{sec.id}]无条目（PDF 跳过渲染）")
            else:
                warnings.append(f"章节[{sec.id}]为空（非必填，PDF 不渲染）")
            continue

        # 2) 渲染标题 + 内容
        w.draw_section_title(title)
        for item in items:
            if stype == "education":
                _render_education(w, item)
            elif stype == "work":
                _render_work(w, item)
            elif stype == "project":
                _render_project(w, item)
            elif stype == "skills":
                _render_skill(w, item)
            elif stype == "awards":
                w.draw_bullet(str(item), space_after=1.0)
            elif stype == "summary":
                w.draw_bullet(str(item), space_after=1.0)

    c.showPage()
    c.save()
    return buf.getvalue(), warnings


# ── 各类条目渲染 ────────────────────────────────────────────────

def _render_education(w: _PdfWriter, item: EducationItem) -> None:
    w.draw_item_title(
        _fmt_period(item.start_time, item.end_time),
        item.school,
        f"{item.major}（{item.degree}）" if item.degree else item.major,
    )
    # Education_Body 两行占位：description / gpa（空则隐藏，同 docx）
    if item.description and item.description.strip():
        w.draw_bullet(item.description.strip(), space_after=1.0)
    if item.gpa and item.gpa.strip():
        w.draw_bullet(item.gpa.strip(), space_after=1.0)
    for b in (item.bullets or []):
        if b and b.strip():
            w.draw_bullet(b.strip(), space_after=1.0)


def _render_work(w: _PdfWriter, item: WorkItem) -> None:
    w.draw_item_title(
        _fmt_period(item.start_time, item.end_time),
        item.company,
        item.role,
    )
    for b in (item.bullets or []):
        if b and b.strip():
            w.draw_bullet(b.strip(), space_after=1.0)


def _render_project(w: _PdfWriter, item: ProjectItem) -> None:
    w.draw_item_title(
        _fmt_period(item.start_time, item.end_time),
        item.name,
        item.role,
    )
    for b in (item.bullets or []):
        if b and b.strip():
            w.draw_bullet(b.strip(), space_after=1.0)


def _render_skill(w: _PdfWriter, item: SkillGroup) -> None:
    joined = "、".join(x for x in (item.items or []) if x is not None)
    if not item.category or not joined:
        # docx Skill_Line 任一部分空 → 整段删除；PDF 同规则（不进视觉）
        return
    line = f"{item.category}：{joined}"
    # 分类段加粗、技能项常规：分两次 emit，保持同一行
    w._gap(1.0)
    w._ensure(LEAD_BODY)
    cat_w = _measure(f"{item.category}：", SZ_BODY)
    w._emit(f"{item.category}：", w.left, w.y, SZ_BODY, COLOR_BODY, bold=True)
    # 技能项可能折行
    rest_lines = _wrap(joined, SZ_BODY, w.width - cat_w)
    x = w.left + cat_w
    for i, ln in enumerate(rest_lines):
        w._emit(ln, x, w.y, SZ_BODY, COLOR_BODY)
        if i != len(rest_lines) - 1:
            w.y -= LEAD_BODY
            x = w.left
    w.y -= LEAD_BODY
    w._gap(1.0)
