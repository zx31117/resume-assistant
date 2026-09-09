"""V2.1.0 R9/R15a：pm_template v1.2 的 reportlab PDF 渲染器。

视觉真源 = templates/_build_templates.py 的 V1.2 参数（与 pm_template.docx / docx 渲染同一套
视觉规格），本文档只做像素侧还原，不引入第二套样式：
  - 页面 A4；页边距 T=0.92cm B=1.39cm L=1.13cm R=1.09cm（与 build 常量一一对应）
  - 字号：姓名 20pt / 章节标题 12pt / 经历标题与正文 bullet 10.6pt / 联系方式与求职意向 10pt
  - 经历标题行“三列”Tab 布局：时间(左) / 学校·公司·项目名(中) / 专业·职位(右)（Word 用
    center/right 制表位；PDF 侧等价于中心对齐 + 右对齐锚点，逐段手排，不依赖制表符）
  - 章节标题下方底分隔线（还原 Word w:pBdr bottom）
  - bullet 前缀“●”（PDF 用 U+25CF，Noto Sans SC 含字形；Word 模板用 ⚫，规格允许 ●/⚫ 互换）
  - 全部常规不加粗；仅章节标题 / 姓名 / 经历标题模拟粗体
  - 右上角照片占位框（无真实照片时画空占位框，尺寸与偏移同 build 常量）
  - 空章节隐藏规则与 docx TemplateRenderer 一致（required 章节为空记 warning 并跳过；
    可选章节为空不渲染、加 warning）

V2.1.0 R15a（可移植中文字体内嵌）：
  放弃内置 Adobe CID 字体 STSong-Light（UnicodeCIDFont 不内嵌字形，浏览器/无字体机器不可读、
  不可移植）；改为内嵌可再分发 OFL 字体 templates/fonts/NotoSansSC-Regular.ttf（Noto Sans SC，
  reportlab TTFont 子集化内嵌为 FontFile2），使 PDF 自带字形、任何 viewer 与机器可读。
  字体资源走模板资源目录（backend_root/templates/fonts/）。

V2.1.0 R17a（确定性字体加载，fail closed）：
  仅使用打包/源码随附的固定 Noto 字体，不再有任何本机/系统字体回退。加载前校验字体文件
  存在且 SHA-256 == 固定值（d45f67f0…，来自 @expo-google-fonts/noto-sans-sc@0.4.3，
  OFL-1.1）；文件缺失、损坏或 hash 不符一律抛确定性 RuntimeError —— generate 链按既有
  "PDF 失败不中断 docx"处理（pdf_* 字段留空 + warning，前端显示真实"PDF 预览不可用"），
  绝不伪造 PDF 成功、绝不回退任何系统字体。

V2.1.0 R15a（PreviewAnchor 输出）：
  render() 绘制每条 bullet（经历/技能等可点内容行）时记录锚点，随渲染结果一起返回：
    {artifact_id, page_index, x0,y0,x1,y1（PDF 用户坐标，y 自底部向上，pt，A4 高 842）,
     content_item_id, bullet_index, text, fact_refs[]}
  fact_refs 逐 bullet 来源由调用方以 bullet_fact_refs 传入（build_v15 的
  build_meta.bullet_fact_refs：experience_id → 每条 bullet 的 fact_id 列表，仅覆盖
  AI 生成 bullets 的经历）；无映射/越界的 bullet 一律给空列表，不编造。

输入输出：
  render(resume_doc, template_id, backend_root, *, artifact_id="",
         bullet_fact_refs=None) -> (pdf_bytes, warnings, anchors)
  pdf_bytes 为内存 PDF（调用方负责按 artifact 身份落盘到 OUTPUT_DIR）。
"""
from __future__ import annotations

import hashlib
import io
import json
import os

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

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
FONT_CN = "NotoSansSC"
FONT_FILE_NAME = "NotoSansSC-Regular.ttf"       # templates/fonts/ 下可再分发 OFL 字体（TrueType）
FONT_TEMPLATE_SUBDIR = os.path.join("templates", "fonts")
# R17a：固定字体指纹。字体来自 @expo-google-fonts/noto-sans-sc@0.4.3（jsdelivr，OFL-1.1，
# 原始文件名 NotoSansSC-Regular.ttf）；加载前强制 SHA-256 校验，缺失/损坏/不符即失败。
FONT_EXPECTED_SHA256 = "d45f67f0a7c0ca3f256950777ce6a61cc7ce5f9696d02900cbbaac25f8aa7d16"

# 行内 bbox 估算（reportlab TTF 度量近似，用于 PreviewAnchor 命中区域）
_EM_ASCENT = 0.88    # Noto Sans SC ascent ≈ 0.88em
_EM_DESCENT = 0.12   # Noto Sans SC descent ≈ 0.12em

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

_font_registered = False


def _ensure_font_registered(backend_root: str) -> str | None:
    """按模板资源目录机制注册固定的 Noto Sans SC 字体（确定性，R17a）。

    全局只注册一次（reportlab 进程级字体注册表）。加载前校验字体文件存在且
    SHA-256 == FONT_EXPECTED_SHA256；缺失 / 损坏 / hash 不符一律抛 RuntimeError
    （fail closed）——绝不回退任何系统字体。成功恒返回 None
    （不再存在"临时回退"warning）。
    """
    global _font_registered
    if _font_registered:
        return None
    candidates = [
        os.path.join(backend_root, *FONT_TEMPLATE_SUBDIR.split(os.sep), FONT_FILE_NAME),
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            *FONT_TEMPLATE_SUBDIR.split(os.sep),
            FONT_FILE_NAME,
        ),
    ]
    # 相对 backend_root（开发/打包一致：settings.BASE_DIR 即 backend/ 根）
    rel = os.path.join(backend_root, "templates", "fonts", FONT_FILE_NAME)
    if rel not in candidates:
        candidates.insert(0, rel)
    path = next((p for p in candidates if os.path.isfile(p)), None)
    if path is None:
        raise RuntimeError(
            "PDF 中文字体不可用：templates/fonts/" + FONT_FILE_NAME + " 不存在；"
            "请随包放置固定可再分发 TTF（OFL Noto Sans SC，SHA-256 "
            + FONT_EXPECTED_SHA256[:16] + "…）"
        )
    actual = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if actual != FONT_EXPECTED_SHA256:
        raise RuntimeError(
            "PDF 中文字体校验失败（确定性失败边界，不回退系统字体）："
            + FONT_FILE_NAME + " SHA-256 不符，期望 "
            + FONT_EXPECTED_SHA256 + "，实际 " + actual
        )
    pdfmetrics.registerFont(TTFont(FONT_CN, path))
    _font_registered = True
    return None


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
    """直接操作 reportlab canvas 的流式排版器（无第三方 flowable 依赖）。

    R15a：排版过程逐 bullet 记录 PreviewAnchor（见 _record_anchor）。
    """

    def __init__(self, c, artifact_id: str = ""):
        self.c = c
        self.artifact_id = artifact_id
        self.anchors: list[dict] = []
        self.page_no = 0
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
            self.page_no += 1
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
            # H7 R33 (rev2)：单一文本对象 fill+stroke（text render mode 2）模拟粗体。
            # rev1 曾用"同位重叠画两次"，虽消除 R15a 0.6pt 常量在 10.6pt CJK 下的
            # 双边描边粘连/异常粗黑，但同一字形在内容流出现两次 → PDF 文本提取出现
            # 重复文本，R9 三端一致性门禁 FAIL（姓名/章节/技能文本对不上）。
            # rev2 回到单一文本对象：可提取/可选择不受影响；线宽按字号比例收窄
            # （clamp(size*3%, 0.2, 0.45)pt，10.6pt≈0.32pt）并让 stroke 色同 fill 色，
            # 在保清晰的同时维持粗体观感。
            lw = max(0.20, min(0.45, size * 0.030))
            t.setTextRenderMode(2)
            self.c.setLineWidth(lw)
            self.c.setStrokeColor(_hex_color(color))
        t.textOut(text)
        self.c.drawText(t)

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

    def _record_anchor(self, *, text: str, x0: float, x1: float,
                       y_top: float, y_bottom: float,
                       content_item_id=None, bullet_index=0,
                       fact_refs=None) -> None:
        """记录一条 PreviewAnchor（PDF 用户坐标 pt，y 自底部向上，A4 高 842）。"""
        self.anchors.append({
            "artifact_id": self.artifact_id,
            "page_index": self.page_no,
            "x0": round(x0, 2),
            "y0": round(y_bottom, 2),
            "x1": round(x1, 2),
            "y1": round(y_top, 2),
            "content_item_id": content_item_id,
            "bullet_index": bullet_index,
            "text": text,
            "fact_refs": list(fact_refs or []),
        })

    # ── bullet（● 前缀 + 悬挂缩进）────────────────────────────
    def draw_bullet(self, text: str, *, size: float = SZ_BODY, leading: float = LEAD_BODY,
                    space_after: float = 1.0, content_item_id=None,
                    bullet_index: int = 0, fact_refs=None) -> None:
        if not text:
            return
        self._ensure(leading)
        indent = _measure(BULLET, size) + 2.0
        first_w = self.left + self.width - indent
        lines = _wrap(text, size, first_w)
        first_y = self.y
        max_right = self.left + indent
        for i, ln in enumerate(lines):
            x = self.left + indent
            if i == 0:
                self._emit(BULLET, self.left, self.y, size, COLOR_BODY)
            self._emit(ln, x, self.y, size, COLOR_BODY)
            if x + _measure(ln, size) > max_right:
                max_right = x + _measure(ln, size)
            self.y -= leading
        if space_after:
            self._gap(space_after)
        bottom_y = first_y - leading * (len(lines) - 1)
        self._record_anchor(
            text=text,
            x0=self.left,
            x1=max_right,
            y_top=first_y + size * _EM_ASCENT,
            y_bottom=bottom_y - size * _EM_DESCENT,
            content_item_id=content_item_id,
            bullet_index=bullet_index,
            fact_refs=fact_refs,
        )

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


def _bullet_refs(prefs: list[list[str]], bullet_source_index: int) -> list[str]:
    """取某条 bullet 的 fact_refs（bullet_fact_refs 按源索引对齐；越界一律空，不编造）。"""
    if prefs and 0 <= bullet_source_index < len(prefs):
        return list(prefs[bullet_source_index] or [])
    return []


def render(resume_doc: ResumeDocument, template_id: str,
           backend_root: str, *, artifact_id: str = "",
           bullet_fact_refs: dict | None = None) -> tuple[bytes, list[str], list[dict]]:
    """把 ResumeDocument 渲染为 pm_template v1.2 布局的 PDF。

    返回 (pdf_bytes, warnings, anchors)。
    章节顺序 / 空章节规则与 docx 渲染器同源：
    spec.sections 顺序逐个渲染，required 章节内容缺失记 warning 并跳过，
    可选章节为空则不渲染（记 warning），profile 区三段（姓名/求职意向/联系方式）。

    artifact_id：本次生成 artifact 身份（写入 anchors）；bullet_fact_refs：可选逐 bullet
    fact_id 映射（experience_id → list[list[str]]，索引对齐该经历 items.bullets）。
    """
    warnings: list[str] = []
    fb = _ensure_font_registered(backend_root)
    if fb:
        warnings.append(fb)

    spec = _load_spec(template_id, backend_root)
    refs_map: dict[str, list[list[str]]] = dict(bullet_fact_refs or {})

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"resume_{template_id}")
    w = _PdfWriter(c, artifact_id=artifact_id)

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

        # 2) 渲染标题 + 内容（各条目传 content_item_id / 逐 bullet fact_refs）
        w.draw_section_title(title)
        if stype in ("education", "work", "project"):
            for i, item in enumerate(items):
                eid = getattr(item, "experience_id", "") or ""
                cid = eid or f"{sec.id}:{i}"
                prefs = refs_map.get(eid) if eid else None
                if stype == "education":
                    _render_education(w, item, cid, prefs)
                elif stype == "work":
                    _render_work(w, item, cid, prefs)
                else:
                    _render_project(w, item, cid, prefs)
        elif stype == "skills":
            for i, g in enumerate(items):
                _render_skill(w, g, content_item_id=f"skills:{i}", bullet_index=i)
        elif stype == "awards":
            for i, a in enumerate(items):
                w.draw_bullet(str(a), space_after=1.0, content_item_id="awards",
                              bullet_index=i, fact_refs=[])
        elif stype == "summary":
            for i, ln in enumerate(items):
                w.draw_bullet(str(ln), space_after=1.0, content_item_id="summary",
                              bullet_index=i, fact_refs=[])

    c.showPage()
    c.save()
    return buf.getvalue(), warnings, w.anchors


# ── 各类条目渲染 ────────────────────────────────────────────────

def _render_education(w: _PdfWriter, item: EducationItem,
                      content_item_id=None,
                      prefs: list[list[str]] | None = None) -> None:
    w.draw_item_title(
        _fmt_period(item.start_time, item.end_time),
        item.school,
        f"{item.major}（{item.degree}）" if item.degree else item.major,
    )
    # Education_Body 两行占位：description / gpa（空则隐藏，同 docx）
    vi = 0
    if item.description and item.description.strip():
        w.draw_bullet(item.description.strip(), space_after=1.0,
                      content_item_id=content_item_id, bullet_index=vi, fact_refs=[])
        vi += 1
    if item.gpa and item.gpa.strip():
        w.draw_bullet(item.gpa.strip(), space_after=1.0,
                      content_item_id=content_item_id, bullet_index=vi, fact_refs=[])
        vi += 1
    for j, b in enumerate(item.bullets or []):
        if b and b.strip():
            w.draw_bullet(b.strip(), space_after=1.0,
                          content_item_id=content_item_id, bullet_index=vi,
                          fact_refs=_bullet_refs(prefs, j))
            vi += 1


def _render_work(w: _PdfWriter, item: WorkItem,
                 content_item_id=None,
                 prefs: list[list[str]] | None = None) -> None:
    w.draw_item_title(
        _fmt_period(item.start_time, item.end_time),
        item.company,
        item.role,
    )
    for j, b in enumerate(item.bullets or []):
        if b and b.strip():
            w.draw_bullet(b.strip(), space_after=1.0,
                          content_item_id=content_item_id, bullet_index=j,
                          fact_refs=_bullet_refs(prefs, j))


def _render_project(w: _PdfWriter, item: ProjectItem,
                    content_item_id=None,
                    prefs: list[list[str]] | None = None) -> None:
    w.draw_item_title(
        _fmt_period(item.start_time, item.end_time),
        item.name,
        item.role,
    )
    for j, b in enumerate(item.bullets or []):
        if b and b.strip():
            w.draw_bullet(b.strip(), space_after=1.0,
                          content_item_id=content_item_id, bullet_index=j,
                          fact_refs=_bullet_refs(prefs, j))


def _render_skill(w: _PdfWriter, item: SkillGroup, *,
                  content_item_id=None, bullet_index: int = 0) -> None:
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
    first_y = w.y
    max_right = x + (_measure(rest_lines[0], SZ_BODY) if rest_lines else 0.0)
    for i, ln in enumerate(rest_lines):
        w._emit(ln, x, w.y, SZ_BODY, COLOR_BODY)
        if x + _measure(ln, SZ_BODY) > max_right:
            max_right = x + _measure(ln, SZ_BODY)
        if i != len(rest_lines) - 1:
            w.y -= LEAD_BODY
            x = w.left
    w.y -= LEAD_BODY
    w._gap(1.0)
    # 技能组整行为一个可点内容行锚点（同类 content_item_id=skills:<序>）
    n = len(rest_lines)
    last_y = first_y - LEAD_BODY * (n - 1) if n > 1 else first_y
    w._record_anchor(
        text=line,
        x0=w.left,
        x1=max_right,
        y_top=first_y + SZ_BODY * _EM_ASCENT,
        y_bottom=last_y - SZ_BODY * _EM_DESCENT,
        content_item_id=content_item_id,
        bullet_index=bullet_index,
        fact_refs=[],
    )
