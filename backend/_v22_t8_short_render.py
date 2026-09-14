"""V2.2.0 T8e 验证：修复合法短输入 TemplateError，不改事实/模板真源
（PLAN §V220-G05 / §6.3 / V220-R1-T08 / A10）。

背景（A10 REJECTED）：V2.1.0 短样例 7/7 TemplateError，原因是合法短简历缺少
某几个 `required=true` 章节（如只有教育+工作、无项目经历→`必填章节[projects]无条目`）。

T08 修复原则：**不改事实、不改模板真源**。渲染层新增 `allow_empty_required`
开关（默认 False 保持旧调用方/复刻 fixture 严格行为），由 T07/T08 装配链
（`document_assembler.assemble_and_render`）显式开启：合法短输入下空章节即便
模板标 required 也优雅移除（仍按 title_style 定位删除标题+原型段），不抛 TemplateError。

本测试确定性断言：
- [T1] 原失败可复现对照：默认严格渲染器对合法短输入仍抛 TemplateError（复现 A10）；
- [T2] 关闭 A10：T08 装配链（allow_empty_required=True）下各类合法短输入渲染成功，
      无未替换占位符，不抛异常；
- [T3] 事实不改变：work/education 的 headline：body 事实文本完整出现在 DOCX 输出；
- [T4] 空章节优雅移除：被移除章节不再出现在最终文档（style 不存在），保留章节不受影响；
- [T5] 模板真源不变：pm_template.json 的 education/work/project/skills 仍 required=true
      （修复只发生在渲染层，不修改模板资产）。

退出码 0 = 全部通过；非 0 = 有失败。
"""
from __future__ import annotations

import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _v2_test_runner import run_isolated  # noqa: E402

BACKEND_ROOT = str(_THIS_DIR)

_passed = 0
_failed = 0


def check(cond, name, extra=""):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  [PASS] {name}")
    else:
        _failed += 1
        print(f"  [FAIL] {name} {extra}")


def _fact(headline="", body="", fact_refs=None):
    from services.document_assembler import JsonFact
    return JsonFact(headline=headline, body=body, fact_refs=list(fact_refs or []))


def _exp(experience_id, exp_type, *, school="", major="", degree="", company="",
         title="", facts=None, start_time="", end_time=""):
    from services.document_assembler import JsonExperience
    return JsonExperience(experience_id=experience_id, type=exp_type,
                          title=title, facts=list(facts or []), school=school,
                          major=major, degree=degree, company=company,
                          start_time=start_time, end_time=end_time)


def _short_doc():
    """合法短输入：1 教育 + 1 工作，无项目经历、无技能（A10 原失败点）。"""
    from services import document_assembler as da
    return da.build_resume_document(
        contact={"name": "张三", "phone": "138", "email": "a@b.c", "location": "上海"},
        compact={"position": "后端工程师", "required_skills": ["Python"], "preferred_skills": []},
        experiences=[
            _exp("e1", "education", school="A大学", major="计算机科学", degree="本科",
                 facts=[_fact("主修", "机器学习与数据挖掘", ["E1"])],
                 start_time="2019.09", end_time="2023.06"),
            _exp("w1", "work", company="某科技",
                 facts=[_fact("Python 开发", "用 Python 完成大模型服务", ["P1"])],
                 start_time="2023.07", end_time="至今"),
        ],
    )


def _doc_text(docx) -> str:
    out = [p.text for p in docx.paragraphs]
    for table in docx.tables:
        for row in table.rows:
            for cell in row.cells:
                out.append(cell.text)
    return "\n".join(out)


def _style_count(docx, style_name) -> int:
    return len(docx.paragraphs) if not style_name else sum(
        1 for p in docx.paragraphs if p.style.name == style_name)


def _populated_section_titles():
    """返回 pm_template 中标 required=true 的章节 id 集合（模板真源对照）。"""
    import json
    with open(Path(BACKEND_ROOT) / "templates" / "pm_template.json", encoding="utf-8") as f:
        spec = json.load(f)
    return {s["id"]: s.get("required") for s in spec["sections"]}


def _run_tests_inner(state):
    from services import document_assembler as da
    from services.template_renderer import TemplateRenderer

    print("\n[T1] 原失败可复现对照：默认严格渲染器对合法短输入仍抛 TemplateError（A10 原样）")
    doc = _short_doc()
    try:
        r = TemplateRenderer("pm_template", backend_root=BACKEND_ROOT)
        r.render(doc)  # 默认 allow_empty_required=False（严格）
        check(False, "严格渲染器对短输入应抛 TemplateError，却渲染成功")
    except Exception as e:
        check(type(e).__name__ == "TemplateError",
              f"严格渲染器复现 TemplateError → {type(e).__name__}: {e}")

    print("\n[T2] 关闭 A10：T08 装配链下各合法短输入渲染成功、无未替换占位符")
    scenarios = {
        "1教育+1工作(无项目/无技能)": _short_doc(),
        "只有教育": da.build_resume_document(
            contact={"name": "张同学", "phone": "138", "email": "a@b.c", "location": "北京"},
            compact={"position": "前端工程师", "required_skills": ["JavaScript"], "preferred_skills": []},
            experiences=[_exp("e1", "education", school="A大学", major="计算机", degree="本科",
                              facts=[_fact("主修", "ML", ["E1"])],
                              start_time="2019", end_time="2023")]),
        "只有工作": da.build_resume_document(
            contact={"name": "李工", "phone": "139", "email": "b@c.d", "location": "深圳"},
            compact={"position": "后端工程师", "required_skills": ["Python"], "preferred_skills": []},
            experiences=[_exp("w1", "work", company="某公司",
                              facts=[_fact("开发", "用 Python 构建服务", ["W1"])],
                              start_time="2023", end_time="至今")]),
        "只有项目": da.build_resume_document(
            contact={"name": "王生", "phone": "137", "email": "c@d.e", "location": "杭州"},
            compact={"position": "算法工程师", "required_skills": ["推荐"], "preferred_skills": []},
            experiences=[_exp("p1", "project", title="推荐系统",
                              facts=[_fact("召回", "实现向量召回", ["R1"])],
                              start_time="2024", end_time="2024")]),
    }
    for name, d in scenarios.items():
        try:
            r = TemplateRenderer("pm_template", backend_root=BACKEND_ROOT)
            r.bold_headline = True
            r.allow_empty_required = True  # T08 装配链开启
            outdoc, _w, stats = r.render(d)
            ok = (stats["unreplaced_placeholders"] == [])
            check(ok, f"短输入[{name}]渲染成功且无未替换占位符",
                  extra=f"unreplaced={stats['unreplaced_placeholders']}")
        except Exception as e:  # noqa: BLE001
            check(False, f"短输入[{name}]应渲染成功", extra=f"异常: {type(e).__name__}: {e}")

    print("\n[T3] 事实不改变：work/education 的 headline：body 事实完整出现在 DOCX 输出")
    doc = _short_doc()
    r = TemplateRenderer("pm_template", backend_root=BACKEND_ROOT)
    r.allow_empty_required = True
    outdoc, _, _ = r.render(doc)
    txt = _doc_text(outdoc)
    check("用 Python 完成大模型服务" in txt, "work 事实正文保留")
    check("机器学习与数据挖掘" in txt, "education 事实正文保留")
    check("Python 开发：" in txt or "Python 开发" in txt, "work headline 保留")

    print("\n[T4] 空章节优雅移除：被移除章节 style 不再出现，保留章节不受影响")
    doc = _short_doc()  # work+education 有内容，projects 空
    r = TemplateRenderer("pm_template", backend_root=BACKEND_ROOT)
    r.allow_empty_required = True
    outdoc, _, _ = r.render(doc)
    # 空 projects：其 item_block 首样式 Project_ItemTitle 应已从文档移除
    check(_style_count(outdoc, "Project_ItemTitle") == 0,
          "空章节 projects（Project_ItemTitle）已从文档移除")
    # 保留章节的原型应仍在：education/work 各有条目 → 其样式至少存在
    check(_style_count(outdoc, "Work_ItemTitle") >= 1, "非空章节 work 保留渲染")

    print("\n[T5] 模板真源不变：education/work/project/skills 仍 required=true")
    req = _populated_section_titles()
    for sec in ("education", "work", "projects", "skills"):
        check(req.get(sec) is True, f"模板章节 {sec} 仍 required=true（未改模板）",
              extra=f"actual={req.get(sec)}")

    print(f"\n结果：{_passed} 通过 / {_failed} 失败")
    return 1 if _failed else 0


if __name__ == "__main__":
    def _fn(state):
        return _run_tests_inner(state)
    run_isolated("v22_t8_", _fn, "V2.2.0 T8 short-input render gate")