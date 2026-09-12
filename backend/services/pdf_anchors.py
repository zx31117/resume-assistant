"""H8 §20.4：PreviewAnchor 从 Word 转换后的真实 PDF 文本层重建。

- 输入：转换器产出的**确切 PDF 字节** + 需要定位的内容行（profile 姓名/求职意向、
  education 描述、work/project 每条 bullet，附 content_item_id/bullet_index/fact_refs）。
- 方法：pypdfium2 提取每个字符的 bbox（PDF 坐标，y 自底向上，A4 高 842，单位 pt）；
  按"去空白归一"匹配目标文本；命中则取匹配字符 bbox 并集作为可点击锚区；
  匹配失败返回 `unavailable`（调用方记录 anchor_status，不高亮、不沿用 ReportLab 坐标）。
- 返回统一 dict 列表，兼容 PreviewAnchor 字段（artifact_id/page_index/x0/y0/x1/y1/
  content_item_id/bullet_index/text/fact_refs）。y 坐标自底向上（与 PreviewAnchor 约定一致）。
"""
from __future__ import annotations

import io
import re
from typing import Iterable

import pypdfium2 as pdfium

A4_H = 842.0  # PDF 用户坐标高（A4 pt）

_WS = re.compile(r"\s+")


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


def build_anchors_from_word_pdf(
    pdf_bytes: bytes,
    rows: Iterable[dict],
    *,
    artifact_id: str = "",
) -> tuple[list[dict], list[dict]]:
    """rows: [{text, content_item_id?, bullet_index?, fact_refs?}]。

    返回 (anchors, unavailable)：anchors 为成功定位项；unavailable 为无法定位项
    （text 保留供前端展示依据，不产生坐标高亮）。
    """
    chars = _chars(pdf_bytes)
    anchors: list[dict] = []
    unavailable: list[dict] = []
    joined = "".join(c["ch"] for c in chars)
    for r in rows:
        text = r.get("text") or ""
        if not text.strip():
            continue
        span = _find_span(chars, text)
        rec = {
            "artifact_id": artifact_id,
            "page_index": 0,
            "x0": 0.0, "y0": 0.0, "x1": 0.0, "y1": 0.0,
            "content_item_id": r.get("content_item_id"),
            "bullet_index": r.get("bullet_index"),
            "text": text,
            "fact_refs": list(r.get("fact_refs") or []),
        }
        if span is None:
            rec.pop("x0", None)
            rec["anchor_status"] = "unavailable"
            unavailable.append(rec)
            continue
        xs = chars[span[0]:span[1]]
        if not xs:
            rec.pop("x0", None)
            rec["anchor_status"] = "unavailable"
            unavailable.append(rec)
            continue
        x0 = min(c["x0"] for c in xs)
        x1 = max(c["x1"] for c in xs)
        y0 = min(c["y0"] for c in xs)
        y1 = max(c["y1"] for c in xs)
        rec.update({"x0": round(x0, 2), "y0": round(y0, 2),
                    "x1": round(x1, 2), "y1": round(y1, 2)})
        anchors.append(rec)
    return anchors, unavailable
