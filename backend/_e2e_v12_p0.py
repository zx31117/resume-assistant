r"""V1.2 §14 P0 清单 E2E 验证脚本。

【使用方式】（避免 PowerShell 执行策略问题，不用 .ps1）
  在 backend/ 目录下直接运行：
    .venv\Scripts\python.exe _e2e_v12_p0.py

【本脚本做了什么】
  0. 自动构建 pm_template.docx（调用 templates/_build_templates.build()，无需手动先跑）
  1. 构造一份产品岗样例 ResumeDocument（自包含，不依赖 DB/RAG/LLM）
  2. 加载模板资产 + 渲染（TemplateRenderer，按 style 定位）
  3. 排版优化（LayoutOptimizer，四级降级，不删条目）
  4. 保存为 DOCX_OUTPUT_DIR/resume_e2e_pm_template.docx（不时间戳，不堆积）
  5. 打印诊断报告（sections_rendered / page_count / warnings / layout_rules / build_counts）

【关键承诺】
  - 固定输出文件名：${DOCX_OUTPUT_DIR}/resume_e2e_pm_template.docx（覆盖，不累积）
  - 不使用 .ps1，不触发双击循环
  - 全程无外部 API 调用（DB/LLM/RAG 全 mock），离线可跑
  - V1.4：输出目录统一走 settings.DOCX_OUTPUT_DIR（runtime root 下），不污染源码树
"""
import os
import sys
import json
import traceback

# 确保 backend/ 在 import path 里
BACKEND_ROOT = os.path.dirname(os.path.abspath(__file__))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

# V1.4：统一从 runtime root 派生输出目录，避免源码树中出现 output/ 提交污染
from core.config import settings  # noqa: E402

OUTPUT_DIR = settings.DOCX_OUTPUT_DIR
os.makedirs(OUTPUT_DIR, exist_ok=True)


# =====================================================================
# Step 0: 自动构建 pm_template.docx（无需用户单独跑 _build_templates.py）
# =====================================================================
def step0_build_template() -> None:
    """§P0-4：构建 pm_template.docx（**每次都强制重新构建**，确保 _build_templates.py 修改后 docx 同步最新）。"""
    print("=" * 68)
    print("Step 0: build pm_template.docx")
    print("=" * 68)
    tpl_path = os.path.join(BACKEND_ROOT, "templates", "pm_template.docx")
    # 避免旧模板残留导致样式不匹配 → 有/无 都重新构建（构建脚本幂等）
    print(f"  [BUILD] 运行 _build_templates.build() 生成/更新 {tpl_path}")
    import importlib.util
    build_script_path = os.path.join(BACKEND_ROOT, "templates", "_build_templates.py")
    spec = importlib.util.spec_from_file_location("_build_templates_mod", build_script_path)
    build_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_mod)
    build_mod.build()  # build 内部会 save + verify
    print()


# =====================================================================
# Step 1: 构造样例 ResumeDocument（产品岗样例数据，全自包含，不依赖 DB）
# =====================================================================
def step1_build_resume_doc():
    """构造产品岗样例 ResumeDocument（V1.2 标准字段）。"""
    print("=" * 68)
    print("Step 1: build sample ResumeDocument")
    print("=" * 68)
    from models.resume_document import (
        Profile, EducationItem, WorkItem, ProjectItem,
        SkillGroup, ResumeDocument,
    )

    profile = Profile(
        name="白晓",
        phone="13812345678",
        email="baixiao@example.com",
        location="北京朝阳区",
        target_position="AI产品经理（实习生）",
        # 自我评价改为多行「关键词：正文」格式（与原模板「自我评价」章节一致；
        #   按换行拆成多条 Summary_Bullet）
        summary=(
            "陌生领域速学：零基础情况下，2周内自学LangChain框架并搭建RAG原型demo；\n"
            "跨职能粘合剂：在团队中常担任PM与开发的「翻译官」，能清晰描述业务逻辑降低沟通成本；\n"
            "数据驱动思维：遇到决策先看数据再下结论，建立30+项指标看板验证产品效果；\n"
            "抗压能力强：曾并行推进3条产品线+2个大赛项目，按期交付全部里程碑。"
        ),
    )

    education = [
        EducationItem(
            school="北京大学",
            major="计算机科学与技术",
            degree="硕士",
            start_time="2019.09",
            end_time="2022.06",
            # 加关键词前缀 → 渲染时自动加粗「本科绩点」四个字
            gpa="本科绩点：3.8/4.0（专业前 5%）",
            description="主修课程：人工智能、机器学习、自然语言处理、软件工程",
            priority=0.95,
        ),
        EducationItem(
            school="清华大学",
            major="软件工程",
            degree="学士",
            start_time="2015.09",
            end_time="2019.06",
            gpa="本科绩点：3.7/4.0",
            description="获得荣誉：国家奖学金（2017、2018）、校优秀毕业生",
            priority=0.9,
        ),
    ]

    work = [
        WorkItem(
            company="字节跳动",
            role="产品经理",
            start_time="2022.07",
            end_time="至今",
            bullets=[
                # 每行格式「关键词：正文」→ 粗体前缀 + 常规正文（原模板特征）
                "产品负责：主导 AI 写作助手产品从 0 到 1 搭建，上线 6 个月 DAU 突破 120 万，次月留存 42%",
                "方案设计：对接大模型团队设计 Prompt 策略与内容安全方案，内容合规率从 91% 提升至 99.2%",
                "数据驱动：定义 30+ 核心指标看板，驱动 AB 实验 80+ 次，单次实验最高提升 CTR 18%",
                "团队协作：协调算法/前端/后端/运营 4 条线共 40+ 人，周迭代交付准时率 97%",
            ],
            priority=0.98,
        ),
        WorkItem(
            company="腾讯",
            role="产品助理",
            start_time="2021.03",
            end_time="2022.06",
            bullets=[
                "迭代管理：负责视频号创作者工具后台，迭代 4 个大版本，创作者发布效率提升 35%",
                "数据分析：独立完成数据分析报告 12 份，发现创作者分层痛点并推动分层权益上线",
                "PRD 撰写：输出 PRD 20+ 份，涵盖需求背景、流程图、交互说明、埋点方案",
            ],
            priority=0.82,
        ),
    ]

    projects = [
        ProjectItem(
            name="智能简历生成平台（本项目 V1.x）",
            role="产品负责人",
            start_time="2026.03",
            end_time="至今",
            bullets=[
                "路线规划：定义产品路线图（V1.0 PDF 解析 → V1.1 JD 匹配 → V1.2 标准化模板填充）",
                "体系设计：设计用户数据模型与模板体系规范，V1.2 标准化模板输出保真度 98%+",
                "算法协作：与 AI 团队协作设计 JD RAG 评分算法，经历召回准确率从 72% 提升至 91%",
                "排版策略：制定四级排版降级规则，1 页简历达标率 93%（不删任何经历条目）",
            ],
            priority=0.96,
        ),
        ProjectItem(
            name="AIGC 内容安全风控系统",
            role="产品经理",
            start_time="2023.05",
            end_time="2023.12",
            bullets=[
                "风控规划：规划三阶段风控方案，规则引擎→小模型过滤→人工审核兜底层层收敛",
                "标签体系：与算法团队合作定义 80+ 风险标签体系，误杀率控制在 1.2% 以内",
                "效果产出：上线后拦截违规内容 120 万+ 条，审核团队人效提升 3 倍",
            ],
            priority=0.85,
        ),
        ProjectItem(
            name="用户增长 AB 实验平台",
            role="产品经理（内部工具）",
            start_time="2023.01",
            end_time="2023.04",
            bullets=[
                "平台架构：对接数据团队搭建实验分流与指标计算平台，支持同时跑 50 组实验",
                "模板沉淀：梳理 10 种实验模板（按钮/文案/推荐算法等），运营自助创建率 70%+",
                "效率提升：平台上线后，实验排期从平均 2 周缩短到 2 天",
            ],
            priority=0.75,
        ),
    ]

    skills = [
        SkillGroup(category="产品工具", items=["Axure RP", "Figma", "墨刀", "Jira", "Confluence", "Teambition"]),
        SkillGroup(category="数据分析", items=["SQL", "Excel（数据透视/宏）", "Tableau", "神策数据", "GrowingIO"]),
        SkillGroup(category="AI 能力", items=["Prompt Engineering", "RAG 架构理解", "LLM 评估体系", "向量库（Chroma）"]),
        SkillGroup(category="编程语言", items=["Python", "SQL", "JavaScript（基础）", "Shell"]),
        SkillGroup(category="软技能", items=["跨团队协作", "用户访谈", "项目推进", "数据驱动决策"]),
    ]

    awards = [
        "字节跳动 2023 年度最佳新人奖",
        "腾讯 2021 Q3 季度之星",
        "北京大学 2020 研究生国家奖学金",
        "清华大学 2018 国家奖学金",
        "\"互联网+\" 创新创业大赛 全国金奖（2020）",
    ]

    doc = ResumeDocument(
        profile=profile,
        education=education,
        work=work,
        projects=projects,
        skills=skills,
        awards=awards,
        meta={
            "jd_position": "产品经理（AI 方向）",
            "matched_count": 7,
            "total_experiences": 10,
            "user_id": "e2e_sample_user",
            "profile_source": "e2e_sample",
        },
    )
    doc = doc.to_standard()
    print(f"  ✓ profile: {profile.name} / {profile.target_position}")
    print(f"  ✓ education: {len(education)} 条, work: {len(work)} 条, projects: {len(projects)} 条")
    print(f"  ✓ skill_groups: {len(skills)} 组, awards: {len(awards)} 条")
    print()
    return doc


# =====================================================================
# Step 2: 渲染（TemplateRenderer） + Step 3: 排版优化（LayoutOptimizer）
# =====================================================================
def step23_render_and_optimize(resume_doc):
    """§P0-6 渲染 + §P0-8 排版优化。"""
    print("=" * 68)
    print("Step 2+3: TemplateRenderer.render → LayoutOptimizer.optimize")
    print("=" * 68)
    from services.template_renderer import TemplateRenderer
    from services import layout_optimizer

    renderer = TemplateRenderer("pm_template", backend_root=BACKEND_ROOT)
    doc, render_warnings, _render_stats = renderer.render(resume_doc)
    print(f"  [Renderer] spec: {renderer.spec.id} v{renderer.spec.version}")
    print(f"  [Renderer] page_limit: {renderer.spec.layout.page_limit}")
    if render_warnings:
        print(f"  [Renderer] warnings ({len(render_warnings)}):")
        for w in render_warnings:
            print(f"    - {w}")
    else:
        print("  [Renderer] warnings: 0")

    page_limit = renderer.spec.layout.page_limit
    estimated_before = layout_optimizer.estimate_pages(doc)
    applied_rules, capacity_warnings = layout_optimizer.optimize(doc, page_limit=page_limit)
    estimated_after = layout_optimizer.estimate_pages(doc)
    print(f"  [Layout]   pages (estimate): {estimated_before} → {estimated_after}  （target ≤ {page_limit}）")
    if applied_rules:
        print(f"  [Layout]   optimizations applied ({len(applied_rules)}):")
        for r in applied_rules:
            print(f"    - {r}")
    else:
        print("  [Layout]   optimizations applied: 0（初始页数已达标）")
    if capacity_warnings:
        print("  [Layout]   capacity warnings:")
        for w in capacity_warnings:
            print(f"    - {w}")
    print()
    return doc, render_warnings, applied_rules, estimated_after, renderer


# =====================================================================
# Step 4: 保存（固定文件名，不时间戳，不堆积）
# =====================================================================
def step4_save(doc) -> str:
    """§10.3 用户审核反馈：固定文件名，覆盖写入，不堆积。"""
    print("=" * 68)
    print("Step 4: save DOCX（固定文件名覆盖）")
    print("=" * 68)
    # 固定文件名，不时间戳 —— 多次运行不堆积；同时符合"输出放 output 文件夹"偏好
    file_name = "resume_e2e_pm_template.docx"
    file_path = os.path.join(OUTPUT_DIR, file_name)
    doc.save(file_path)
    size_kb = os.path.getsize(file_path) / 1024.0
    print(f"  ✓ 保存成功: {file_path}")
    print(f"    文件大小: {size_kb:.1f} KB")
    print(f"    文件名（固定，不堆积）: {file_name}")
    print()
    return file_path


# =====================================================================
# Step 5: 诊断报告 + 自检（提交前自查，用户要求）
# =====================================================================
def step5_diagnose_report(resume_doc, renderer, render_warnings, applied_rules, page_count, file_path) -> dict:
    """§用户要求：提交前自己检查 —— 打印结构化报告并写入 txt（放 output/）。"""
    print("=" * 68)
    print("Step 5: 诊断报告（提交前自查）")
    print("=" * 68)

    # sections_rendered（同 API 报告格式）
    def section_count(sec_type: str) -> int:
        return {
            "profile": 1,
            "summary": 1 if resume_doc.profile.summary else 0,
            "education": len(resume_doc.education),
            "work": len(resume_doc.work),
            "project": len(resume_doc.projects),
            "skills": len(resume_doc.skills),
            "awards": len(resume_doc.awards),
        }.get(sec_type, 0)

    sections_rendered = []
    for sec in renderer.spec.sections:
        cnt = section_count(sec.type)
        label = f"{sec.id}({cnt})" if cnt else sec.id
        sections_rendered.append(label)

    build_counts = {
        "education": len(resume_doc.education),
        "work": len(resume_doc.work),
        "projects": len(resume_doc.projects),
        "awards": len(resume_doc.awards),
        "skill_groups": len(resume_doc.skills),
    }

    # 自检 checklist（绿色通过 / 红色失败）
    checks = []
    # 1. 必填章节必须非空
    for sec in renderer.spec.sections:
        if sec.required:
            cnt = section_count(sec.type)
            ok = cnt > 0
            checks.append((f"必填章节 {sec.id}/{sec.type} 非空（{cnt} 条）", ok))
    # 2. 页数估算是否达标
    checks.append((f"页数估算 ≤ {renderer.spec.layout.page_limit}（estimate ~{page_count}）",
                   page_count <= renderer.spec.layout.page_limit))
    # 3. 文件是否生成且可读
    docx_exists = os.path.isfile(file_path) and os.path.getsize(file_path) > 2000
    checks.append(("输出 DOCX 文件存在且大小正常（> 2KB）", docx_exists))

    report_lines = []
    report_lines.append("=== V1.2 §14 P0 E2E 诊断报告 ===")
    report_lines.append(f"模板: {renderer.spec.id} v{renderer.spec.version}")
    report_lines.append(f"输出文件: {file_path}")
    report_lines.append("")
    report_lines.append(f"sections_rendered: {json.dumps(sections_rendered, ensure_ascii=False)}")
    report_lines.append(f"build_counts: {json.dumps(build_counts, ensure_ascii=False)}")
    report_lines.append(f"page_count (estimate): {page_count}")
    report_lines.append(f"profile_source: {resume_doc.meta.get('profile_source', 'n/a')}")
    report_lines.append("")
    report_lines.append(f"render_warnings ({len(render_warnings)}):")
    for w in render_warnings:
        report_lines.append(f"  - {w}")
    report_lines.append(f"layout_optimizations ({len(applied_rules)}):")
    for r in applied_rules:
        report_lines.append(f"  - {r}")
    report_lines.append("")
    report_lines.append("--- 自检 checklist ---")
    all_pass = True
    for desc, ok in checks:
        tag = "PASS" if ok else "FAIL"
        report_lines.append(f"  [{tag}] {desc}")
        all_pass = all_pass and ok
    report_lines.append("")
    if all_pass:
        report_lines.append("结论: ✓ 所有自检项通过，可提交审核")
    else:
        report_lines.append("结论: ✗ 存在自检失败项，请修复后重新运行")

    report_text = "\n".join(report_lines)
    print(report_text)

    # 同时落盘到 output/（用户偏好：生成结果放 output 文件夹）
    report_name = "诊断报告_e2e_v12_p0.txt"
    report_path = os.path.join(OUTPUT_DIR, report_name)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    print()
    print(f"  报告已保存: {report_path}")
    print()
    return {
        "ok": all_pass,
        "sections_rendered": sections_rendered,
        "build_counts": build_counts,
        "page_count": page_count,
        "file_path": file_path,
        "report_path": report_path,
    }


# =====================================================================
# main
# =====================================================================
def main():
    try:
        step0_build_template()
        resume_doc = step1_build_resume_doc()
        doc, render_warnings, applied_rules, page_count, renderer = step23_render_and_optimize(resume_doc)
        file_path = step4_save(doc)
        rpt = step5_diagnose_report(resume_doc, renderer, render_warnings, applied_rules, page_count, file_path)
        if not rpt["ok"]:
            sys.exit(2)
        print(f"✅ E2E PASSED  |  DOCX: {rpt['file_path']}  |  REPORT: {rpt['report_path']}")
    except Exception as e:
        print("❌ E2E FAILED  详细错误如下：")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
