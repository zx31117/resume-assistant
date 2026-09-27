#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V2.2.0 DOC_RETURNED 返工 · 离线门（无模型、无网络）：P4 anchor 三类目标正反向。

覆盖：
  [A1] build_rows_from_resume_doc 的 kind/来源投影（不猜测标题）；
  [A2] fact 锚点 = 有真实依据的 bullet；携带 artifact_id + fact_id + fact_refs；
       未定位行（如样例 PDF 缺标题行日期片段）逐行记 unavailable 且不带坐标；
  [A2b] 工作/项目标题行容错定位：PDF 含真实标题行时定位成功，且被 section 并集覆盖
       （整段条目真实可点，不靠固定坐标）；
  [A3] section（work/project/education）与 skills 整段锚点 = 已定位行的真实并集；
  [A4] 坐标在页内、x0<x1、y0<y1；并集覆盖其成员行；
  [A5] 反向：无 fact_refs 的 bullet 不产生可点事实热区（无幽灵热区）；
  [A6] 反向：技能行不单独出事实热区；定位失败 → 无锚点 + 逐行 unavailable 记账；
  [A7] PreviewAnchor schema：kind/fact_id 字段存在且历史锚点缺省按 fact 解释。

运行：python backend/_v220_docreturned_anchor.py  （退出码 0=全通过，1=有 FAIL）
"""
from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfbase.cidfonts import UnicodeCIDFont  # noqa: E402
from reportlab.pdfgen import canvas as rl_canvas  # noqa: E402

from api.schemas import PreviewAnchor  # noqa: E402
from models.resume_document import (  # noqa: E402
    EducationItem, Profile, ProjectItem, ResumeDocument, SkillGroup, WorkItem,
)
from services import pdf_anchors as pa  # noqa: E402

W, H = 595.0, 842.0
FAILS: list[str] = []


def check(cond: bool, label: str, extra="") -> None:
    print(("[PASS] " if cond else "[FAIL] ") + label + (f" | {extra}" if extra else ""))
    if not cond:
        FAILS.append(label)


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def make_pdf(lines: list[str]) -> bytes:
    """用可嵌入中文的 CID 字体画出**真实文本层** PDF（离线替代 Word COM 产物）。"""
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(W, H))
    c.setFont("STSong-Light", 11)
    y = H - 60
    for ln in lines:
        c.drawString(50, y, ln)
        y -= 18
    c.showPage()
    c.save()
    return buf.getvalue()


WORK_LINES = ["Acme Retail 高级后端工程师",
              "订单链路重构：把下单超时从 900ms 降到 210ms",
              "对账调度：日处理账单 200 万条"]
PROJ_LINES = ["Rocket 数据平台",
              "离线任务编排：把批处理窗口从 6 小时压到 40 分钟"]
SKILL_LINES = ["编程语言：Java、Python", "中间件：Kafka、Redis"]
EDU_LINES = ["Sample University 计算机科学与技术", "GPA 3.9/4.0"]
ALL_LINES = WORK_LINES + PROJ_LINES + SKILL_LINES + EDU_LINES


def build_doc() -> ResumeDocument:
    return ResumeDocument(
        profile=Profile(name="脱敏样例", target_position="后端工程师"),
        work=[WorkItem(company="Acme Retail", role="高级后端工程师", start_time="2021.03",
                       end_time="2024.06", experience_id="exp-w1",
                       bullets=WORK_LINES[1:], fact_refs=["f-1", "f-2", "f-3"])],
        projects=[ProjectItem(name="Rocket 数据平台", role="负责人", start_time="2020.01",
                              end_time="2021.02", experience_id="exp-p1",
                              bullets=PROJ_LINES[1:], fact_refs=["f-4", "f-5"])],
        education=[EducationItem(school="Sample University", major="计算机科学与技术",
                                 degree="本科", start_time="2016.09", end_time="2020.06",
                                 description="\n".join(EDU_LINES), experience_id="exp-e1",
                                 bullets=EDU_LINES, fact_refs=[])],
        skills=[SkillGroup(category="编程语言", items=["Java", "Python"], fact_refs=["f-1"]),
                SkillGroup(category="中间件", items=["Kafka", "Redis"], fact_refs=["f-2"])],
    )


def main() -> int:
    doc = build_doc()
    refs_by_bullet = {("exp-w1", 0): ["f-1"], ("exp-w1", 1): ["f-2"], ("exp-p1", 0): ["f-4"]}
    fact_ids_by_bullet = {("exp-w1", 0): "gf-1", ("exp-w1", 1): "gf-2", ("exp-p1", 0): "gf-4"}

    section("A1) 行投影（kind / 来源字段来自 ResumeDocument，不猜测）")
    rows = pa.build_rows_from_resume_doc(doc, refs_by_bullet=refs_by_bullet,
                                         fact_ids_by_bullet=fact_ids_by_bullet)
    kinds = [r["kind"] for r in rows]
    check(kinds.count("fact") == 3, "work/project bullet → fact 行 = 3", kinds.count("fact"))
    check(kinds.count("skill") == 2, "技能组 → skill 行 = 2", kinds.count("skill"))
    check(kinds.count("line") == 3, "教育整段 + 工作/项目标题行 → line 行 = 3", kinds.count("line"))
    titles = [r for r in rows if r["kind"] == "line" and r.get("bullet_index") is None]
    check(len(titles) == 2 and all(r.get("parts") for r in titles),
          "工作/项目各 1 条标题行且带 parts（容错定位，使整段条目真实可点）",
          [r.get("content_item_id") for r in titles])
    check(all(r.get("section_key") for r in rows), "每行都有 section 归属（用于并集）")
    check(all("fact_refs" in r for r in rows if r["kind"] == "fact"), "fact 行携带 fact_refs")

    anchors, unavail = pa.build_anchors_from_word_pdf(
        make_pdf(ALL_LINES), rows, artifact_id="art-1")
    facts = [a for a in anchors if a["kind"] == "fact"]
    secs = {a["content_item_id"]: a for a in anchors if a["kind"] == "section"}
    skills = [a for a in anchors if a["kind"] == "skills"]

    section("A2) fact 锚点身份与依据")
    check(len(facts) == 3, "fact 锚点数 = 有依据 bullet 数", len(facts))
    check(all(a["artifact_id"] == "art-1" for a in anchors), "全部锚点绑定同一 artifact_id")
    check(all(a["fact_id"] for a in facts), "fact 锚点携带本次生成 fact_id")
    check(all(a["fact_refs"] for a in facts), "fact 锚点携带真实 fact_refs")
    check(sorted(a["fact_id"] for a in facts) == ["gf-1", "gf-2", "gf-4"],
          "fact_id 与生成结果逐条对齐", sorted(a["fact_id"] for a in facts))
    check(not [u for u in unavail if u.get("kind") == "fact"],
          "全部 fact 行真实定位（无 unavailable）",
          [u.get("content_item_id") for u in unavail if u.get("kind") == "fact"])
    check(bool(unavail) and all(u.get("anchor_status") == "unavailable" and "x0" not in u
                                for u in unavail),
          "未定位行仅记账、不带坐标（诚实降级，不伪装可点）",
          [(u.get("content_item_id"), u.get("kind")) for u in unavail])

    section("A2b) 标题行容错定位：样例 PDF 含真实标题行时整段条目可被并集覆盖")
    lines_hdr = ["2021.03-2024.06  Acme Retail  高级后端工程师"] + WORK_LINES[1:] \
        + ["2020.01-2021.02  Rocket 数据平台  负责人"] + PROJ_LINES[1:] \
        + SKILL_LINES + EDU_LINES
    anchors_h, unavail_h = pa.build_anchors_from_word_pdf(
        make_pdf(lines_hdr), rows, artifact_id="art-h")
    secs_h = {a["content_item_id"]: a for a in anchors_h if a["kind"] == "section"}
    check(not [u for u in unavail_h
               if u.get("kind") == "line" and u.get("bullet_index") is None],
          "标题行在 PDF 中真实存在 → 定位成功（不再 unavailable）",
          [u.get("content_item_id") for u in unavail_h])
    facts_h = [a for a in anchors_h if a["kind"] == "fact" and a["content_item_id"] == "exp-w1"]
    check(facts_h and secs_h["exp-w1"]["y1"] > max(f["y1"] for f in facts_h) + 1,
          "section 并集把标题行纳入（整段条目高度 > 其 fact 行并集）",
          (secs_h["exp-w1"]["y1"], max(f["y1"] for f in facts_h)))

    section("A3) section / skills 整段并集")
    check(set(secs) == {"exp-w1", "exp-p1", "exp-e1"}, "section 覆盖 work/project/education", sorted(secs))
    check(len(skills) == 1 and skills[0]["content_item_id"] == "skills",
          "skills 整段 = 1 条 content_item_id='skills'", [s["content_item_id"] for s in skills])
    check(secs["exp-w1"]["text"] == "Acme Retail", "section 文案取自真实公司字段",
          secs["exp-w1"]["text"])
    check(skills[0]["text"] == "技能专长", "skills 锚点文案", skills[0]["text"])

    section("A4) 几何：页内 + 并集覆盖成员行")
    check(all(0 <= a["x0"] < a["x1"] <= W + 0.5 and 0 <= a["y0"] < a["y1"] <= H + 0.5
              for a in anchors), "全部锚点坐标在页内且 x0<x1 / y0<y1")
    w1 = secs["exp-w1"]
    facts_w1 = [a for a in facts if a["content_item_id"] == "exp-w1"]
    check(all(w1["y0"] <= f["y0"] + 0.01 and w1["y1"] >= f["y1"] - 0.01 for f in facts_w1),
          "section 并集覆盖其全部 fact 行")
    edu = secs["exp-e1"]
    check(edu["y1"] - edu["y0"] > 12, "教育整段并集高度 > 单行（覆盖多行描述）",
          round(edu["y1"] - edu["y0"], 2))

    section("A5/A6) 反向：无依据/技能行/定位失败")
    check([a for a in anchors if a["kind"] == "fact" and a["content_item_id"] == "skills:0"] == [],
          "技能行不单独出事实热区（仅整段 skills）")
    doc2 = ResumeDocument(work=[WorkItem(company="X", experience_id="exp-x",
                                         bullets=["无依据的事实行"], fact_refs=[])])
    rows2 = pa.build_rows_from_resume_doc(doc2)
    anchors2, _u2 = pa.build_anchors_from_word_pdf(
        make_pdf(["无依据的事实行"]), rows2, artifact_id="art-2")
    check([a for a in anchors2 if a["kind"] == "fact"] == [],
          "无 fact_refs 的 bullet 不产生事实热区（无幽灵热区）", anchors2)
    check(any(a["kind"] == "section" for a in anchors2), "仍作为所属 section 的几何来源")
    anchors3, unavail3 = pa.build_anchors_from_word_pdf(
        make_pdf(["完全不同的文本"]), rows2, artifact_id="art-3")
    check(anchors3 == [] and len(unavail3) == len(rows2),
          "定位失败 → 无锚点 + 逐行 unavailable 记账", len(unavail3))
    check(all(u.get("anchor_status") == "unavailable" and "x0" not in u for u in unavail3),
          "记账项不带坐标（诚实降级，不产生幽灵热区）")

    section("A7) PreviewAnchor schema 兼容")
    old = PreviewAnchor(artifact_id="a", text="x", x0=1, y0=1, x1=2, y1=2)
    check(old.kind == "fact" and old.fact_id is None, "历史锚点缺省 kind='fact'（向后兼容）")
    dumped = PreviewAnchor(artifact_id="a", text="x", kind="skills").model_dump()
    check(dumped.get("kind") == "skills" and "fact_id" in dumped, "kind/fact_id 可序列化")

    print(f"\nV2.2.0 DOC_RETURNED anchor 离线门：FAIL={len(FAILS)}")
    for f in FAILS:
        print(f"  - {f}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())