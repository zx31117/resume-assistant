"""V2.2.0 T7e 验证：联系方式、技能、headline/body/fact_refs、教育字段修正
（PLAN §V220-G05 / §6.3 / V220-R1-T07）。

纯逻辑 + 轻量渲染（不触发真实模型 / Embedding / Word COM），确定性断言：

- [T1] 联系方式全组合：仅姓名、每个选填字段、全部字段、Unicode/空白归一；
- [T2] 教育字段修正：学校/专业/学历独立语义、专业在外学历在括号内、
      缺任一字段不输出空括号、无倒置/重复括号/`本科（）`；
- [T3] 技能 2～4 类：JD 相关、有 Fact 依据、诚实减少（不关键词堆砌）、fact_refs 保留；
- [T4] headline/body：冒号边界、body/hl 缺一不产孤立冒号、fact_refs 贯穿到 work/project/skills；
- [T5] ResumeDocument 装配：联系方式进入 profile、经历 facts→bullets、skills 进 doc；
- [T6] Renderer 修正：最终 DOCX 无空圆括号；`headline：body` bullet 拆为
      「加粗标题+冒号」+「普通正文」。

退出码 0 = 全部通过；非 0 = 有失败。
"""
from __future__ import annotations

import os
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


def _exp(experience_id, type, *, title="", facts=None, school="", major="",
         degree="", company="", start_time="", end_time=""):
    from services.document_assembler import JsonExperience
    kw = dict(experience_id=experience_id, type=type, title=title, facts=list(facts or []),
              school=school, major=major, degree=degree, company=company,
              start_time=start_time, end_time=end_time)
    return JsonExperience(**kw)


def _run_tests_inner(state):
    from services import document_assembler as da

    print("\n[T1] 联系方式全组合 + Unicode/空白归一")
    # 仅姓名
    p = da.normalize_contact(name="张三")
    check(p.name == "张三" and not p.phone and not p.email and p.location is None,
          "仅姓名 → phone/email/location 为空")
    # 每个选填字段单独
    p = da.normalize_contact(phone="13800000000")
    check(p.phone == "13800000000" and not p.name, "仅电话")
    p = da.normalize_contact(email="a@b.c")
    check(p.email == "a@b.c" and not p.phone and not p.name, "仅邮箱")
    p = da.normalize_contact(location="上海 浦东")
    check(p.location == "上海 浦东" and p.name == "", "仅所在地")
    # 全部字段
    p = da.normalize_contact(name="张三", phone="138", email="a@b.c", location="上海",
                             target_position="后端工程师")
    check(p.name == "张三" and p.phone == "138" and p.email == "a@b.c"
          and p.location == "上海" and p.target_position == "后端工程师",
          "全部字段 → 全部进入 Profile，target_position 只取 JD")
    # Unicode / 空白归一
    p = da.normalize_contact(name="  张三  ", phone="１３８　０１２３",  # 全角数字 + 全角空格
                             email="Ａ＠Ｂ．Ｃ")
    check(p.name == "张三", f"名字首尾空白折叠 → {p.name!r}")
    check(p.phone == "138 0123", f"全角数字/空白归一 → {p.phone!r}")
    check(p.email == "A@B.C", f"全角字母归一（NFKC）→ {p.email!r}")
    # 缺任一字段不回填模板
    check(p.location is None, "缺 input_revision 的字段不产生回填空串")

    print("\n[T2] 教育字段修正（专业在外、学历在括号内、缺字段不输出空括号）")
    cases = [
        (("A大学", "计算机", "本科"), "A大学 计算机（本科）"),
        (("A大学", "计算机", ""), "A大学 计算机"),
        (("A大学", "", "本科"), "A大学（本科）"),
        (("", "计算机", "硕士"), "计算机（硕士）"),
        (("A大学", "", ""), "A大学"),
        (("", "", ""), ""),
    ]
    for (s, m, d), expected in cases:
        got = da.format_education_line(school=s, major=m, degree=d)
        # 归一：去掉拼接时的可选空白，便于断言（无空括号/倒置/重复是硬指标）
        compact = "".join(got.split())
        expected_compact = "".join(expected.split())
        check(compact == expected_compact, f"组合 school={s!r} major={m!r} degree={d!r}",
              extra=f"→ {got!r}")
        check("（）" not in got and "()" not in got,
              f"无空括号（学校={s!r} 专业={m!r} 学历={d!r}）")
        check(not (d and f"（{d}）" not in got and not any(c in d for c in "（）()")),
              f"学历在括号内（学校={s!r} 学历={d!r}）")
    # 已有括号不重复包裹
    got = da.format_education_line(school="A大学", major="计算机",
                                   degree="（本科）")
    check("计算机（（本科）" not in got and "（本科）" in got,
          f"学历已带括号不重复包裹 → {got!r}")
    # 中英混排
    got = da.format_education_line(school="X University", major="CS", degree="Master")
    check("CS" in got and "Master" in got and "（Master）" in got.replace(" ", ""),
          f"中英混排学历入括号 → {got!r}")
    # 无倒置：学历绝不作为不带括号的独立位置出现
    got = da.format_education_line(school="A大学", major="", degree="本科")
    check(got.replace(" ", "") == "A大学（本科）", f"学历不倒置到括号外 → {got!r}")

    print("\n[T3] 技能生成（JD 相关、Fact 依据、诚实减少、fact_refs）")
    # 3 个不同类别的 JD 技能，均被事实正文命中 → 期望 3 个类别
    exps = [
        _exp("w1", "work", title="后端", facts=[
            _fact("Python 服务", "用 Python gunicorn 部署大模型推理 API", ["P1"]),
            _fact("分布式", "基于 Kubernetes 扩容", ["K1"]),
        ]),
        _exp("w2", "work", title="算法", facts=[
            _fact("建模", "基于 Python 完成用户画像 数据分析", ["D1"]),
        ]),
    ]
    compact3 = {"position": "算法工程师",
                "required_skills": ["Python", "Kubernetes", "数据分析"],
                "preferred_skills": []}
    groups = da.build_skill_groups(compact3, exps)
    check(2 <= len(groups) <= 4, f"技能类别 2~4 个 → 实际 {len(groups)}")
    all_items = [it for g in groups for it in g.items]
    for skill in ("python", "kubernetes", "数据分析"):
        check(skill in all_items, f"JD 相关且有 Fact 依据的技能进入技能区: {skill}")
    check(any(g.fact_refs for g in groups), "技能类别保留可核验 fact_refs")
    # 诚实减少：JD required 中出现但无任何事实依据的技能不进入技能区
    groups2 = da.build_skill_groups(
        {"position": "p", "required_skills": ["Python", "Kubernetes", "GO", "Figma"],
         "preferred_skills": []}, exps)
    all_items2 = [it for g in groups2 for it in g.items]
    check("python" in all_items2 and "kubernetes" in all_items2, "有依据技能保留")
    for ghost in ("go", "figma"):
        check(ghost not in all_items2, f"无 Fact 依据的技能被诚实剔除: {ghost}")
    # 完全无依据 → 空技能区（宁可减少，不做关键词堆砌）
    empty = [_exp("x1", "work", title="x",
                  facts=[_fact("标题", "正文不含任何 JD 技能名", ["X1"])])]
    groups3 = da.build_skill_groups(
        {"required_skills": ["PyTorch", "推荐算法"], "preferred_skills": []}, empty)
    group_items3 = [it for g in groups3 for it in g.items]
    check(len([x for x in (["pytorch", "推荐算法"]) if x in group_items3]) == 0,
          "事实不足 → 不关键词堆砌/不强行补数")

    print("\n[T4] headline/body 合成 + 冒号边界 + fact_refs 贯穿")
    check(da.compose_fact_bullet("重构支付", "吞吐提升40%") == "重构支付：吞吐提升40%",
          "compose：headline：body")
    check(da.compose_fact_bullet("优化", "") == "优化", "body 空 → 仅标题，无孤立冒号")
    check(da.compose_fact_bullet("", "纯正文") == "纯正文", "headline 空 → 纯正文")
    check(da.compose_fact_bullet("重构支付：", "正文") == "重构支付：正文" or
          da.compose_fact_bullet("重构支付：", "正文").count("：") == 1,
          "headline 已带冒号不重复")
    head, body = da.split_headline_boundary("重构支付：吞吐提升40%")
    check(head == "重构支付：" and body == "吞吐提升40%",
          f"加粗边界分离 → ({head!r}, {body!r})")
    head, body = da.split_headline_boundary("仅标题")
    check(head == "仅标题" and body == "", "无冒号 → 整体为标题，无正文")

    # 装配后 fact_refs 保留
    doc = da.build_resume_document(
        contact={"name": "张三", "phone": "138", "email": "a@b.c", "location": "上海"},
        compact={"position": "后端工程师", "required_skills": ["Python"]},
        experiences=[
            _exp("w1", "work", title="某科技", facts=[
                _fact("Python 开发", "用 Python 完成大模型服务", ["P1", "P2"])]),
            _exp("p1", "project", title="推荐系统", facts=[
                _fact("召回", "完成向量召回模块", ["R1"])]),
        ])
    check(doc.work[0].bullets == ["Python 开发：用 Python 完成大模型服务"],
          "work bullet 由 headline：body 合成")
    check(set(doc.work[0].fact_refs) == {"P1", "P2"}, "work fact_refs 保留")
    check(doc.projects[0].fact_refs == ["R1"], "project fact_refs 保留")
    check(any(g.fact_refs for g in doc.skills), "skills 在 ResumeDocument 中保留 fact_refs")

    print("\n[T5] ResumeDocument 装配完整性")
    e_exp = _exp("e1", "education", school="A大学", major="计算机科学",
                 degree="本科",
                 facts=[_fact("主修", "机器学习与数据挖掘", ["E1"])],
                 start_time="2019.09", end_time="2023.06")
    doc = da.build_resume_document(
        contact={"name": "张同学", "phone": "138-0000", "email": "x@y.z", "location": "北京"},
        compact={"position": "算法工程师", "required_skills": ["机器学习"]},
        experiences=[
            _exp("w1", "work", title="某公司", facts=[_fact("A", "构建数据管道", ["W1"])],
                 start_time="2023.07", end_time="至今"),
            e_exp,
        ])
    check(doc.profile.name == "张同学" and doc.profile.target_position == "算法工程师",
          "联系方式与 target_position（来自 JD）进入 profile")
    check(len(doc.education) == 1 and doc.education[0].school == "A大学"
          and doc.education[0].major == "计算机科学" and doc.education[0].degree == "本科",
          "教育字段独立语义保留")
    check(doc.education[0].bullets == ["主修：机器学习与数据挖掘"], "教育正文由 facts 合成")
    check(doc.work[0].start_time == "2023.07" and doc.work[0].end_time == "至今",
          "时间独立语义保留")

    print("\n[T6] Renderer 修正（无空圆括号 / headline 加粗边界）")
    try:
        from services.template_renderer import TemplateRenderer
        doc = da.build_resume_document(
            contact={"name": "张同学", "phone": "138-0000", "email": "a@b.c",
                     "location": "上海"},
            compact={"position": "后端工程师",
                     "required_skills": ["Python", "大模型", "机器学习"]},
            experiences=[
                _exp("w1", "work", title="某科技", company="某科技",
                     facts=[_fact("Python 开发", "用 Python 完成大模型服务", ["P1"])],
                     start_time="2023.01", end_time="2025.06"),
                _exp("e2", "education", school="A大学", major="计算机科学",
                     degree="本科",
                     facts=[_fact("主修课程", "机器学习与数据挖掘", ["E1"])],
                     start_time="2019.09", end_time="2023.06"),
                _exp("p3", "project", title="智能推荐系统",
                     facts=[_fact("卷积推荐", "实现基于深度学习的推荐算法", ["R1"])],
                     start_time="2024.02", end_time="2024.06"),
            ])
        r = TemplateRenderer("pm_template", backend_root=BACKEND_ROOT)
        r.bold_headline = True
        d, warns, _ = r.render(doc)
        txt = "\n".join(p.text for p in d.paragraphs)
        check("（）" not in txt and "()" not in txt,
              "渲染输出无空圆括号（修复本科（））")
        # work bullet 段落：加粗 headline+冒号 + 普通正文
        target = None
        for p in d.paragraphs:
            if "用 Python 完成大模型服务" in p.text:
                target = p
                break
        check(target is not None, "work bullet 段落存在")
        if target is not None:
            runs = [x for x in target.runs if x.text and x.text.strip()]
            bold_heads = [x.text for x in runs if bool(x.font.bold)]
            normal = [x.text for x in runs if not bool(x.font.bold)]
            check("Python 开发：" in bold_heads,
                  f"headline+冒号 加粗 → {bold_heads!r}")
            check("用 Python 完成大模型服务" in normal,
                  f"正文普通字重 → {normal!r}")
    except Exception as ex:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        check(False, f"Renderer 修正验证异常: {ex!r}")

    print(f"\n结果：{_passed} 通过 / {_failed} 失败")
    return 1 if _failed else 0


if __name__ == "__main__":
    def _fn(state):
        return _run_tests_inner(state)
    run_isolated("v22_t7_", _fn, "V2.2.0 T7 document/contact/skill/education gate")