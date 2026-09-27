"""H8 §20.4：PreviewAnchor 从 Word 转换后的真实 PDF 文本层重建。

- 输入：转换器产出的**确切 PDF 字节** + 需要定位的内容行（profile 姓名/求职意向、
  education 描述、work/project 每条 bullet，附 content_item_id/bullet_index/fact_refs）。
- 方法：pypdfium2 提取每个字符的 bbox（PDF 坐标，y 自底向上，A4 高 842，单位 pt）；
  按"去空白归一"匹配目标文本；命中则取匹配字符 bbox 并集作为可点击锚区；
  匹配失败返回 `unavailable`（调用方记录 anchor_status，不高亮、不沿用 ReportLab 坐标）。
- 返回统一 dict 列表，兼容 PreviewAnchor 字段（artifact_id/page_index/x0/y0/x1/y1/
  content_item_id/bullet_index/text/fact_refs/kind/fact_id）。y 坐标自底向上。

V2.2.0 DOC_RETURNED 返工：新增三类可选中目标（DS-003）。
  行级输入带 kind：
    - 'fact'：单条事实正文行 → 定位成功且 fact_refs 非空时输出可选锚点；
    - 'line'：条目正文行（如教育整段描述）→ 只作为 section 并集的几何来源，不单独输出；
    - 'skill'：技能行 → 只作为 skills 并集的几何来源，不单独输出。
  section/skills 锚点 = 同一 section_key 下**已真实定位**行的 bbox 并集（按页分组），
  因此热区必然落在真实正文上，不使用固定样张坐标，也不做标题猜测。
  任一行定位失败 → 记 unavailable（诚实降级，不产生可点幽灵热区）。
"""
from __future__ import annotations

import io
import re
from typing import Iterable, Optional

import pypdfium2 as pdfium

A4_H = 842.0  # PDF 用户坐标高（A4 pt）

_WS = re.compile(r"\s+")

# 输出到 PreviewAnchor 的字段白名单（内部几何行还带 section_key/section_text，不外泄）
_ANCHOR_FIELDS = ("artifact_id", "page_index", "x0", "y0", "x1", "y1",
                  "content_item_id", "bullet_index", "text", "fact_refs",
                  "kind", "fact_id")


def _chars(pdf_bytes: bytes) -> list[dict]:
    """page0 每个字符的 {ch, x0, y0, x1, y1}（pypdfium2 charbox: left,bottom,right,top）。"""
    doc = pdfium.PdfDocument(io.BytesIO(pdf_bytes))
    page = doc[0]
    tp = page.get_textpage()
    out = []
    for i in range(tp.count_chars()):
        try:
            box = tp.get_charbox(i)  # (left, bottom, right, top) PDF pt, y bottom-up
            ch = tp.get_text_range(i, 1)  # (start, count) —— count=1 取单字符
        except Exception:  # noqa: BLE001
            continue
        if not ch or not ch.strip():
            continue
        out.append({"ch": ch, "x0": box[0], "y0": box[1], "x1": box[2], "y1": box[3]})
    return out


def _norm(s: str) -> str:
    return _WS.sub("", s or "")


def _find_span(chars: list[dict], target: str) -> tuple[int, int] | None:
    """在字符序列里找归一后 == target 的最小连续 span；返回 [i, j) 字符下标。"""
    norm = _norm("".join(c["ch"] for c in chars))
    if not norm:
        return None
    t = _norm(target)
    if not t:
        return None
    start = norm.find(t)
    if start < 0:
        return None
    # 归一位置 → 原始字符下标：去掉空白时压缩映射，这里近似用逐字符累计
    # 简化：由于我们建 chars 时已丢弃空白字符（不 append 空白），norm 与 chars 逐字对齐
    end = start + len(t)
    return (start, end)


def _find_span_parts(chars: list[dict], parts: Iterable[str]) -> tuple[int, int] | None:
    """按「非空片段顺序、允许中间夹杂分隔符」在归一文本上定位一段（经历标题行专用）。

    模板标题行由多个 Run 拼接（时间/分隔符/公司/职位），`fill_placeholders` 对空字段只清空
    该 Run 而**保留分隔符 Run**（"-"、Tab），因此标题行可见文本无法靠再实现分隔符规则精确
    重建。这里改为容错匹配：只要求各非空片段**按顺序出现**，片段之间的孤立分隔符/空白由
    `.*?` 吸收。返回 [i, j) 字符下标（与 chars 逐字对齐）。
    """
    norm = _norm("".join(c["ch"] for c in chars))
    esc = [re.escape(_norm(p)) for p in parts if _norm(p)]
    if not norm or not esc:
        return None
    m = re.search(".*?".join(esc), norm, re.S)
    return (m.start(), m.end()) if m else None


def build_anchors_from_word_pdf(
    pdf_bytes: bytes,
    rows: Iterable[dict],
    *,
    artifact_id: str = "",
) -> tuple[list[dict], list[dict]]:
    """rows: [{text, kind?, content_item_id?, bullet_index?, fact_refs?, fact_id?,
              section_key?, section_text?}]。

    kind 语义：
      - 'fact'（或缺省后的历史行）：定位成功且 fact_refs 非空 → 输出单条事实锚点；
        定位成功但无 fact_refs → 仅作为所属 section 的几何来源，不输出（无可展示依据，
        不得伪造可点热区）；
      - 'line'：条目正文行，仅参与其 section_key 的并集；
      - 'skill'：技能行，仅参与 skills 并集。

    返回 (anchors, unavailable)：anchors 为可选目标（kind ∈ fact/section/skills）；
    unavailable 为无法定位项（text 保留供告警，不产生坐标高亮）。
    """
    rows = list(rows)
    chars = _chars(pdf_bytes)
    located: list[dict] = []          # 已定位的内部几何行（含 section_key/section_text）
    unavailable: list[dict] = []
    for r in rows:
        text = r.get("text") or ""
        if not text.strip():
            continue
        kind = (r.get("kind") or "fact")
        rec = {
            "artifact_id": artifact_id,
            "page_index": 0,
            "content_item_id": r.get("content_item_id"),
            "bullet_index": r.get("bullet_index"),
            "text": text,
            "fact_refs": list(r.get("fact_refs") or []),
            "fact_id": r.get("fact_id") or None,
            "kind": kind,
            "_section_key": r.get("section_key"),
            "_section_text": r.get("section_text") or text,
        }
        parts = [str(p) for p in (r.get("parts") or []) if str(p or "").strip()]
        span = _find_span_parts(chars, parts) if parts else _find_span(chars, text)
        xs = chars[span[0]:span[1]] if span is not None else []
        if not xs:
            bad = {k: v for k, v in rec.items() if not k.startswith("_")}
            bad.pop("x0", None)
            bad["anchor_status"] = "unavailable"
            unavailable.append(bad)
            continue
        rec.update({
            "x0": round(min(c["x0"] for c in xs), 2),
            "x1": round(max(c["x1"] for c in xs), 2),
            "y0": round(min(c["y0"] for c in xs), 2),
            "y1": round(max(c["y1"] for c in xs), 2),
        })
        located.append(rec)

    anchors: list[dict] = []
    groups: dict[str, list[dict]] = {}
    for ln in located:
        key = ln.get("_section_key")
        if key:
            groups.setdefault(key, []).append(ln)
        if ln["kind"] == "fact" and ln["fact_refs"]:
            anchors.append({
                **{k: ln[k] for k in _ANCHOR_FIELDS},
                "kind": "fact",
            })
    # section / skills：同 key 下已定位行按页求并集（真实正文并集，非固定坐标）
    for key, lns in groups.items():
        out_kind = "skills" if key == "skills" else "section"
        by_page: dict[int, list[dict]] = {}
        for ln in lns:
            by_page.setdefault(ln["page_index"], []).append(ln)
        for page_index, plns in by_page.items():
            refs: list[str] = []
            for ln in plns:
                for r in ln["fact_refs"]:
                    if r and r not in refs:
                        refs.append(r)
            anchors.append({
                "artifact_id": artifact_id,
                "page_index": page_index,
                "x0": round(min(l["x0"] for l in plns), 2),
                "y0": round(min(l["y0"] for l in plns), 2),
                "x1": round(max(l["x1"] for l in plns), 2),
                "y1": round(max(l["y1"] for l in plns), 2),
                "content_item_id": key,
                "bullet_index": None,
                "text": plns[0]["_section_text"],
                "fact_refs": refs,
                "kind": out_kind,
                "fact_id": None,
            })
    return anchors, unavailable


def _time_part(item) -> str:
    """条目标题行的时间片段（与模板 `<start>-<end>` 的可见文本一致，空字段不参与）。"""
    s = str(getattr(item, "start_time", "") or "").strip()
    e = str(getattr(item, "end_time", "") or "").strip()
    if s and e:
        return f"{s}-{e}"
    return s or e


def build_rows_from_resume_doc(
    resume_doc,
    refs_by_bullet: Optional[dict] = None,
    fact_ids_by_bullet: Optional[dict] = None,
) -> list[dict]:
    """把最终 ResumeDocument 投影为待定位行（kind/content_item_id/fact_refs/fact_id）。

    - 教育：整段 description 作为 'line'（参与 section 并集，不单独可点；教育按条目整段呈现）；
    - 工作/项目：先追加一条**整段条目标题行** 'line'（时间/公司|项目名/职位，带 `parts`
      片段供容错定位），再逐条 bullet 'fact'；标题行使 section 并集覆盖整段条目（含标题行），
      与 DS-003 原型「section = 整段条目块、比 fact 行更宽」语义一致；
      fact_refs / fact_id 来自本次生成结果
      （refs_by_bullet / fact_ids_by_bullet 以 (experience_id, bullet_index) 为键）；
    - 技能：每个 SkillGroup 一行 'skill'（文本与模板渲染一致 `<category>：<items>`），
      统一并入 content_item_id='skills' 的整段锚点。
    section_text 取自 ResumeDocument 真实字段，不做标题猜测。
    """
    refs_by_bullet = refs_by_bullet or {}
    fact_ids_by_bullet = fact_ids_by_bullet or {}
    rows: list[dict] = []

    for edu in getattr(resume_doc, "education", []) or []:
        eid = getattr(edu, "experience_id", "") or ""
        if (getattr(edu, "description", "") or "").strip():
            rows.append({
                "text": edu.description, "kind": "line",
                "content_item_id": eid or None, "bullet_index": 0,
                "section_key": eid or None,
                "section_text": getattr(edu, "school", "") or getattr(edu, "major", "") or "教育经历",
            })

    for w in getattr(resume_doc, "work", []) or []:
        eid = getattr(w, "experience_id", "") or ""
        label = getattr(w, "company", "") or getattr(w, "role", "") or "工作经历"
        parts = [_time_part(w), getattr(w, "company", "") or "", getattr(w, "role", "") or ""]
        rows.append({
            "text": "".join(p for p in parts if p), "parts": parts, "kind": "line",
            "content_item_id": eid or None, "bullet_index": None,
            "section_key": eid or None, "section_text": label,
        })
        for bi, bl in enumerate(getattr(w, "bullets", []) or []):
            rows.append({
                "text": bl, "kind": "fact",
                "content_item_id": eid or None, "bullet_index": bi,
                "fact_refs": refs_by_bullet.get((eid, bi), []),
                "fact_id": fact_ids_by_bullet.get((eid, bi)),
                "section_key": eid or None, "section_text": label,
            })

    for pr in getattr(resume_doc, "projects", []) or []:
        eid = getattr(pr, "experience_id", "") or ""
        label = getattr(pr, "name", "") or getattr(pr, "role", "") or "项目经历"
        parts = [_time_part(pr), getattr(pr, "name", "") or "", getattr(pr, "role", "") or ""]
        rows.append({
            "text": "".join(p for p in parts if p), "parts": parts, "kind": "line",
            "content_item_id": eid or None, "bullet_index": None,
            "section_key": eid or None, "section_text": label,
        })
        for bi, bl in enumerate(getattr(pr, "bullets", []) or []):
            rows.append({
                "text": bl, "kind": "fact",
                "content_item_id": eid or None, "bullet_index": bi,
                "fact_refs": refs_by_bullet.get((eid, bi), []),
                "fact_id": fact_ids_by_bullet.get((eid, bi)),
                "section_key": eid or None, "section_text": label,
            })

    for si, g in enumerate(getattr(resume_doc, "skills", []) or []):
        items = getattr(g, "items", None) or []
        joined = "、".join(items) if isinstance(items, list) else str(items or "")
        category = getattr(g, "category", "") or ""
        line = f"{category}：{joined}" if joined else category
        if line.strip():
            rows.append({
                "text": line, "kind": "skill",
                "content_item_id": f"skills:{si}", "bullet_index": si,
                "section_key": "skills", "section_text": "技能专长",
            })
    return rows
