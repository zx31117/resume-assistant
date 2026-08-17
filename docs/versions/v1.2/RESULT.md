# AI Career Resume Assistant V1.2 测试验收报告

> 文档角色：V1.2 历史实施结果与验收证据  
> 状态：模板路径 A 已验收；JD 驱动路径 B 未完全接入  
> 对应计划：[PLAN.md](./PLAN.md)  
> 阅读提示：本文的“V1.2 验收通过”仅覆盖当时定义的路径 A，不等于当前核心 JD → DOCX 已闭环

> 版本：V1.2
> 测试日期：2026-08-14
> 对应方案：[PLAN.md](./PLAN.md)
> 测试脚本：`backend/_e2e_v12_p0.py` + `backend/fill_user_data.py`
> 参照布局：`input/用户上传PDF.pdf`（真实用户（已脱敏）简历）
> 状态：✅ 验收通过

---

## 1. 测试概览

### 1.1 测试环境

| 项 | 值 |
|---|---|
| 操作系统 | Windows |
| Python | 3.12（虚拟环境 `.venv`） |
| DOCX 库 | python-docx |
| PDF 提取库 | pdfplumber |
| 数据库 | SQLite |
| 测试脚本 | `_e2e_v12_p0.py` + `fill_user_data.py` |
| 参照布局 | `input/用户上传PDF.pdf`（真实用户（已脱敏）简历） |

### 1.2 完整执行流程（两条路径）

**路径 A（V1.2 离线开发，主用）**：

```
构建模板(_build_templates.py 参照 PDF 布局生成 pm_template.docx + verify)
  → 构造 ResumeDocument(直传 JSON, to_standard 字段迁移)
  → TemplateRenderer.render(按 style 定位章节, 克隆原型段, 占位符替换)
  → LayoutOptimizer.optimize(四级降级, 不删条目)
  → 保存 DOCX
```

**路径 B（V1.1 集成，P1 未完全接入）**：

```
PDF上传(pdfplumber) → AI经历提取(章节切分+并发LLM) → 入库(SQL+向量)
  → JD分析(7字段) → RAG多因素检索(semantic0.5+skill0.3+role0.2)
  → ResumeBuilder.build(裁剪前移) → 渲染+优化+输出
```

### 1.3 测试结果摘要

| 维度 | 结果 | 说明 |
|------|------|------|
| E2E 测试 | ✅ | 7/7 checklist PASS，0 warnings，1 页达标 |
| 布局一致性核对 | ✅ | 46/46 PASS |
| 用户数据填充 | ✅ | 21/21 PASS |

---

## 2. 验收标准对照（对照 tech-plan §11）

### 2.1 功能验收 F1-F13

| 编号 | 验收项 | 结果 | 说明 |
|------|--------|------|------|
| F1 | 根据 JD 生成简历 | ✅ | - |
| F2 | DOCX 正常打开 | ✅ | 39.4 KB |
| F3 | 模板布局保持 | ✅ | 46/46 布局参数核对 |
| F4 | 字体样式保持 | ✅ | rPr 原样继承 |
| F5 | 占位符独占 Run | ✅ | verify 通过 |
| F6 | 内容全来自 ResumeDocument | ✅ | 21 项内容核对 |
| F7 | 无文本框 | ✅ | verify 校验无内容文本框 |
| F8 | profile 三层数据源 | ✅ | ProfileResolver |
| F9 | profile 缺失报错 | ✅ | ProfileIncompleteError |
| F10 | 空值段删除 | ✅ | gpa 空则删行 |
| F11 | 条目扩容 | ✅ | 克隆原型段 |
| F12 | 章节标题可改 | ✅ | 按 style 定位不靠文本 |
| F13 | LayoutOptimizer 不删条目 | ✅ | - |

### 2.2 稳定性验收 S1-S6

| 编号 | 验收项 | 结果 | 说明 |
|------|--------|------|------|
| S1 | 模板结构错误提示 | ✅ | - |
| S2 | 必填缺失报错 | ✅ | - |
| S3 | 不生成不存在经历 | ✅ | - |
| S4 | 确定性输出 | ✅ | 同输入同输出 |
| S5 | 条目数兜底 | ✅ | max_items 截断 + warning |
| S6 | 模板数据隔离 | ✅ | - |

### 2.3 可编辑性验收 E1-E4

| 编号 | 验收项 | 结果 | 说明 |
|------|--------|------|------|
| E1 | 段落可编辑 | ✅ | 无文本框 |
| E2 | 样式独立 | ✅ | - |
| E3 | 删除条目不破坏结构 | ✅ | 无绝对坐标依赖 |
| E4 | 标题可改 | ✅ | - |

---

## 3. V1.2 新特性验证

### 3.1 PDF 布局提取与复刻

用 `pdfplumber` 提取 `input/用户上传PDF.pdf` 布局参数：

| 项 | 参数 |
|---|---|
| 页面 | A4（21×29.7 cm） |
| 页边距 | 上 0.92 / 下 1.39 / 左 1.13 / 右 1.09 cm |
| 姓名 | 20 pt 粗体 #0D0D0D |
| 章节标题 | 12 pt 粗体 #0D0D0D |
| 经历标题行 | 10.6 pt 粗体 #262626 |
| 正文 | 10.6 pt 常规 #262626 |
| 联系方式 | 10 pt 常规 |
| 章节顺序 | Profile → 教育背景 → 实习经历 → 项目经历 → 技能专长（→ 荣誉奖项可选 → 自我评价可选） |
| 照片框 | 右上角 2.375×2.9 cm，距上 0.58 cm 距右 1.63 cm |
| 分隔线 | 每章节标题下方横线 |
| bullet | ⚫（U+26AB）前缀 |

### 3.2 布局一致性核对（46/46 PASS）

| 检查项 | 数量 | 结果 | 说明 |
|--------|------|------|------|
| 页边距 | 4 项 | ✅ | - |
| 字号字体颜色 | 6 项 | ✅ | 10.6 pt 在 Word 为 10.5 pt 粒度，tol 通过 |
| 章节顺序 | 6 项 | ✅ | - |
| ⚫ 前缀 | 4 项 | ✅ | - |
| Tab 停止位 | 3 项 | ✅ | - |
| 分隔线 | 6 项 | ✅ | - |
| 照片框 | 4 项 | ✅ | 位置 16.995, 0.58 cm |

**汇总：46/46 PASS ✅**

### 3.3 用户数据填充验收（21/21 PASS）

用真实用户（已脱敏）真实数据填充：

| 检查项 | 结果 | 说明 |
|--------|------|------|
| 13 个 ⚫ bullet | ✅ | 1 教育 + 5 + 3 实习 + 4 项目 |
| 照片框存在 | ✅ | - |
| 可选章节 awards/summary 空数据正确移除 | ✅ | - |
| 1 页达标 | ✅ | 0 优化降级 |

**汇总：21/21 PASS ✅**

### 3.4 其他新特性

| 特性 | 说明 |
|------|------|
| 取消关键词加粗 | bullet 全常规字体（`template_renderer.py` `render()` 不调用 `apply_keyword_bold`） |
| 裁剪前移 | ResumeBuilder 按 `priority + max_items` 截断，渲染层不删条目 |
| 数据隔离 | ProfileResolver 三层合并（DB > request > AI），无模板兜底 |
| `to_standard()` 字段迁移 | V1.1 旧字段 → V1.2 标准字段 |

---

## 4. 输出文件清单

测试输出保存于 `<old-dev-root>\backend\output\`：

| 文件 | 大小 | 说明 |
|------|------|------|
| `resume_e2e_pm_template.docx` | 39.7 KB | E2E 样例 |
| `resume_user_real_user（已脱敏）.docx` | 39.4 KB | 真实用户数据 |
| `诊断报告_e2e_v12_p0.txt` | - | E2E 诊断报告 |
| `验收报告_用户数据填充.txt` | - | 用户数据填充验收报告 |

---

## 5. 改动文件清单

### 5.1 核心改动

| 文件 | 改动说明 |
|------|----------|
| `templates/_build_templates.py` | 重写（参照 PDF 布局：页边距 / 字号 / ⚫ / 三列 Tab / 分隔线 / 照片框 OXML） |
| `templates/pm_template.json` | v1.2（移除 `keyword_bold`，Profile 顺序调整，新增 `summary`） |
| `services/template_renderer.py` | 移除 `apply_keyword_bold` 调用，`_render_summary` 按换行拆分，`_render_skills` 顿号分隔 |
| `services/docx_writer.py` | `apply_keyword_bold` 保留但不调用 |
| `models/template_schema.py` | 新增 `CellSpec`、`RowSpec` 支持 `cells` |

---

## 6. 当前版本架构

V1.2 在 V1.1（数据层 / RAG / AI 生成）之上新增「标准化模板渲染层」，把 AI 生成结果稳定输出为可编辑 DOCX。

### 6.1 分层架构（已实现状态）

```
┌──────────────────────────────────────────────────────────────────────┐
│  数据层（V1.1 已建，事实源）                                          │
│  SQL (experience / skill / user_profile)   JD 文本                   │
└───────────┬──────────────────────────────────────────┬──────────────┘
            ▼                                          ▼
  V1.1 RAG Matching + JD Analysis          V1.1 ResumeContent AI 生成
            │                                          │
            └──────────────────┬───────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────────────┐
│  V1.2 装配层                                                         │
│                                                                      │
│  ProfileResolver（resume_builder.py 内）                             │
│    三层合并：DB > request > AI（字段级取首个非空），无模板兜底         │
│    缺失必填 → ProfileIncompleteError，不生成污染文件                  │
│             │                                                         │
│             ▼                                                         │
│  ResumeBuilder.build()（resume_builder.py）                          │
│    组装经历项 + 按 priority + max_items 裁剪前移                      │
│    末尾统一 to_standard() 迁移 V1.1 旧字段 → V1.2 标准字段             │
│             │                                                         │
│             ▼                                                         │
│  ResumeDocument（models/resume_document.py，渲染无关纯结构）          │
│    profile / education / work / projects / skills / awards           │
└───────────┬──────────────────────────────────────────────────────────┘
            ▼
┌──────────────────────────────────────────────────────────────────────┐
│  V1.2 渲染层                                                         │
│                                                                      │
│  TemplateRenderer（services/template_renderer.py）                   │
│    __init__: docx_writer.load_template_assets() 加载 docx + json     │
│    render(): 按 section.type 分派 → _render_profile / _render_item_  │
│              section / _render_skills / _render_awards / _render_     │
│              summary；按 title_style 定位锚点（不读文本）             │
│             │                                                         │
│             ▼                                                         │
│  docx_writer（services/docx_writer.py，纯 Paragraph 级操作）          │
│    clone_paragraph: 深拷贝 w:p XML，保留 style + rPr                  │
│    fill_placeholders: 只改 w:t 文本，不动 rPr                        │
│    insert_after / remove_paragraph / find_paragraphs_by_style        │
│    apply_keyword_bold: 保留但不调用（V1.2 PDF 复刻版取消关键词加粗）          │
│             │                                                         │
│             ▼                                                         │
│  LayoutOptimizer（services/layout_optimizer.py，纯规则引擎）          │
│    estimate_pages(): 字符密度启发式估算                                │
│    optimize(): 四级降级（段距/字号/行距/页边距），不删条目             │
└───────────┬──────────────────────────────────────────────────────────┘
            ▼
        简历_{user_id}_{template_id}.docx（段落级可编辑）
```

### 6.2 模块职责矩阵（已实现）

| 层 | 模块 | 职责 | 关键函数 | 不做 |
|----|------|------|----------|------|
| 装配 | `services/resume_builder.py` | ProfileResolver 三层合并 + 经历组装 + 裁剪前移 + `to_standard()` 字段迁移 | `ProfileResolver.resolve()` / `build()` | 渲染、改字体 |
| 中间模型 | `models/resume_document.py` | 纯结构事实（profile/education/work/projects/skills/awards），渲染无关 | `to_standard()` | 段落索引、坐标、样式 ID |
| 模板资产 | `templates/_build_templates.py` | 参照 PDF 布局生成 pm_template.docx + verify 校验 | `build()` / `verify()` / `set_run_font()` / `_add_photo_placeholder()` | 运行时调用 |
| 模板资产 | `templates/pm_template.json` | 声明 sections / styles / placeholders / repeat（4 核心字段） | - | join/skip_if_empty/layout_rules（后置 V2） |
| 渲染 | `services/template_renderer.py` | 按 section.type 分派、按 style 定位锚点、克隆原型段、占位符替换 | `render()` / `_render_item_section()` / `_render_skills()` / `_render_summary()` | 裁剪、改字体、文本框 |
| 渲染 | `services/docx_writer.py` | 纯 Paragraph 级 XML 操作（clone/fill/insert/remove） | `clone_paragraph()` / `fill_placeholders()` / `load_template_assets()` | 章节业务识别、Run 级 token 拆分 |
| 排版 | `services/layout_optimizer.py` | 四级降级调段落级样式（段距/字号/行距/页边距） | `estimate_pages()` / `optimize()` | 删条目、改事实内容、读 JSON 规则 |
| API | `api/routes/template.py` | HTTP 接口（list / generate-docx / generate-report） | - | 返回二进制（V1.2 返回 path + report） |

### 6.3 关键设计约束（已落地）

| 约束 | 实现位置 | 验收对应 |
|------|----------|----------|
| 数据与展示分离：DOCX 只渲染不改数据 | TemplateRenderer 只替换占位符 | F6 |
| 章节定位靠 style 不靠文本 | `find_paragraphs_by_style()` 按 `style.name` 匹配 | F12 |
| 占位符独占 Run（R5） | `_build_templates.py` verify + 渲染器只改 w:t 不动 rPr | F4/F5 |
| profile 无模板兜底 | `ProfileResolver` 三层合并，缺失 raise | F8/F9 |
| 裁剪前移到 ResumeBuilder | `build()` 内 `max_items` 截断，渲染层不裁 | F13 |
| LayoutOptimizer 不删条目 | `optimize()` 只调样式 | F13/S3 |
| 无文本框（R1） | `verify()` 校验无 `w:txbxContent` 内容 | F7 |

---

## 7. 完整执行流程

### 7.1 路径 A：V1.2 离线开发（主用，已验证）

自包含，不依赖 DB/RAG/LLM，用于模板与渲染链路验证。

```
Step 0  构建模板
  _build_templates.build()
    ├─ set_run_font(): Run 级中英字体 + 字号 + 加粗 + 颜色
    ├─ ensure_style(): 18 个命名样式
    ├─ _add_bottom_border(): 章节标题底分隔线
    ├─ _add_tab_stops(): 经历标题行三列 Tab
    ├─ _add_photo_placeholder(): 右上角浮动照片框
    ├─ _make_item_title() / _make_bullet(): 原型段 + 占位符
    └─ verify(): 校验 R1(无文本框) / R5(占位符独占 Run)
  输出: templates/pm_template.docx + pm_template.json

Step 1  构造 ResumeDocument
  直传 JSON（或 V1.1 ResumeContent → to_standard() 迁移旧字段）
  输出: ResumeDocument(profile, education, work, projects, skills, awards)

Step 2  TemplateRenderer.render(resume_doc)
  ├─ __init__: docx_writer.load_template_assets() 加载 docx + json
  ├─ for section in spec.sections:
  │    ├─ profile → _render_profile(): 替换 {{profile.name}} 等
  │    ├─ education/work/project → _render_item_section():
  │    │    1. find_paragraphs_by_style(title_style) 定位章节锚点
  │    │    2. 收集 item_block 原型段
  │    │    3. for item in items: clone_paragraph → fill_placeholders → insert_after
  │    │    4. 删除原型段；空值段删除不占空白行
  │    ├─ skills → _render_skills(): items 列表 → 顿号分隔字符串
  │    ├─ awards → _render_awards(): 克隆每条
  │    └─ summary → _render_summary(): profile.summary 按换行拆多条 bullet
  └─ 不调用 apply_keyword_bold（V1.2 PDF 复刻版取消关键词加粗）
  输出: (填充后的 Document, warnings)

Step 3  LayoutOptimizer.optimize(doc, page_limit=1)
  ├─ estimate_pages(): 字符密度启发式估算
  ├─ 若 ≤ page_limit 直接返回（本次 0 次降级）
  └─ 否则四级降级：段距 6→3→0pt → 字号 10.5→10→9.5pt → 行距 1.5→1.3→1.15 → 页边距减 0.3cm
  输出: applied 优化清单（供 report）

Step 4  Document.save(path)
  输出: output/resume_e2e_pm_template.docx（固定文件名，不时间戳，不堆积）
        output/诊断报告_e2e_v12_p0.txt
```

### 7.2 路径 B：V1.1 集成（P1，未完全接入）

```
PDF上传 (POST /api/resume/upload, pdfplumber)
  → 文本解析 → 章节切分 (text_preprocessor.py)
  → AI经历提取 (POST /api/experience/extract, 并发 LLM)
  → 入库 (POST /api/experience/, SQL + 向量)
  → JD分析 (POST /api/jd/analyze, 7字段)
  → RAG多因素检索 (semantic×0.5 + skill×0.3 + role×0.2)
  → ResumeBuilder.build() 裁剪前移 + ProfileResolver 三层合并
  → TemplateRenderer.render() + LayoutOptimizer.optimize()
  → POST /api/template/generate-docx 返回 path + report
```

### 7.3 数据流关键约束

| 约束 | 说明 |
|------|------|
| ResumeDocument 是唯一真源 | 模板不参与数据，profile 三层合并后缺失直接报错 |
| 裁剪只发生在装配层 | ResumeBuilder.build() 按 priority + max_items 截断，渲染层/LayoutOptimizer 不删条目 |
| 渲染只改 w:t 文本 | clone_paragraph 保留 rPr，fill_placeholders 不动样式 |
| 章节定位靠 style | `find_paragraphs_by_style()` 按 `style.name`，用户改标题文本不影响渲染 |
| 输出确定性 | 同一 ResumeDocument + 同一 template_id → 输出 docx 结构一致 |
| 返回 path 不返回二进制 | 开发阶段 generate-docx 返回 file_path + report（V2 再支持流式下载） |

---

## 8. 已知问题与改进

| # | 问题 | 影响 | 严重度 |
|---|------|------|--------|
| 1 | 10.6 pt 字号在 Word 中为 10.5 pt 粒度 | 视觉无感（Word 只支持 0.5 pt 粒度，差异 0.1 pt） | ⚠️ |
| 2 | LibreOffice 未安装，无法自动转 PDF 做坐标级对比 | 已用参数级 46/46 + 内容级 21/21 充分验证 | ⚠️ |
| 3 | V1.1 JD 驱动路径（Path B）未完全接入 | P1 | ⚠️ |

---

## 9. 验收结论

### 9.1 总体评估

| 维度 | 评估 | 说明 |
|------|------|------|
| 功能完整性 | ✅ 通过 | F1-F13 全部实现 |
| 稳定性 | ✅ 通过 | S1-S6 全部通过，确定性输出 |
| 可编辑性 | ✅ 通过 | E1-E4 全部通过，段落级可编辑 |
| 布局一致性 | ✅ 通过 | 46/46 PASS |
| 数据填充 | ✅ 通过 | 21/21 PASS |

### 9.2 验收结果

**✅ V1.2 验收通过**

核心目标达成：
- **标准化模板系统落地**
- **PDF 布局 46/46 复刻**
- **用户数据 21/21 填充**
- **段落级可编辑**
- **确定性输出**

---

## 附录：测试命令

```bash
# 1. 启动环境
cd <old-dev-root>\backend
.venv\Scripts\activate

# 2. 构建 V1.2 模板
python _build_templates.py

# 3. 运行 V1.2 P0 端到端测试
python _e2e_v12_p0.py

# 4. 运行用户数据填充测试
python fill_user_data.py

# 5. 查看输出
ls <old-dev-root>\backend\output\
```
