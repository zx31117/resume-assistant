# AI Career Resume Assistant V1.2.0 技术方案

> 文档角色：V1.2.0 历史执行计划  
> 状态：已实施；路径 A 结果见 [RESULT.md](./RESULT.md)  
> 基线：[V1.1.0 RESULT](../v1.1.0/RESULT.md)  
> 经验阅读：必须同时理解“任意 Word 路线被否决”和“标准模板路线”两次决策语境  
> 当前全局上下文：[项目总览](../../README.md) · [决策记录](../../DECISIONS.md)；本文本身保留 V1.2.0 当时语境

> 版本：V1.2.0（标准化模板方向）
> 更新日期：2026-08-14
> 前序结论：V1.2.0 原「解析任意用户上传 Word 模板」方向经实测验证不可行，转向「系统内置标准化模板 + 占位符替换」。

---

## 0. 方向变更说明（必读）

### 0.1 原方案为何不可行

V1.2.0 原方案选择「用户上传 Word → 解析文本框 → 识别章节 → 按坐标写入」。基于 `input/模板.docx` 的真实 XML 结构实测（诊断报告已于 V1.2.0 阶段清理，下述结论留档），发现以下**不可逾越**的问题：

| 问题 | 实测数据 | 后果 |
|------|---------|------|
| 文本框跨章节坐标冲突 | 26 个文本框只占 8 个坐标；`pos=(-792480,5042535)` 同时叠了「校园经历标题 / 联系信息 / 求职意向 / 姓名」4 个章节 5 个文本框 | `seen_coords` 全局去重→先写章节占坐标→后写章节被误清空→**姓名/电话消失、结构完全混乱** |
| 家族识别策略矛盾 | 「内容完全一致」太严（空阴影层漏识别）；「坐标一致」太宽（跨章节误合并） | 写入时标题框和内容框混淆，**阴影层残留旧内容形成重影** |
| 章节锚点识别脆弱 | 4 字纯中文标题（校园经历/大赛经历）与纯中文姓名正则冲突；冒号/长度限制易误伤 | 常规章节被识别成姓名，**章节大面积丢失** |
| 字体压平 | 同段多 Run 多字体被合并成单一 StyleInfo | **原模板同段中英不同字体丢失** |
| 环境阻塞 | PowerShell 执行策略 `UnauthorizedAccess` 阻止所有 `.ps1` 自动化脚本 | 每次验证需用户手动双击运行→**反复生成覆盖→文件循环堆积** |

**根本判断**：解析「任意 Word 模板」等价于做 Word 渲染器的子集，工作量和风险指数级膨胀。V1.2.0 不做这个方向。

### 0.2 新方向：标准化模板系统

**核心思想**：不解析任意复杂 Word，建立**系统可控的标准化模板体系**——系统内置一组干净的 DOCX 模板（用原生段落+命名样式，不依赖文本框），每张模板配套一个 JSON 描述文件（声明章节、占位符、样式绑定）。渲染时按「占位符 → ResumeDocument 字段 → 模板样式」的映射关系写入，完全绕开文本框/坐标/家族识别。

**收益**：
- 技术风险从「解析 Word」的不可控降为「字符串替换+样式继承」的可控
- 生成稳定性在标准模板约束下具有**确定性输出**（结构不会乱、不会出现无用户信息、不会重影）。注：Word 自身因版本差异、字体缺失、渲染差异仍存在一定不确定性，方案只保证"输入相同 → 输出 docx 结构相同"
- 可编辑性大幅提升（用户拿到的是段落文本，不是锁在文本框里的浮动对象）
- 为 V2/V3 的「用户自定义模板 / Word → 模板转换」保留接口：届时把用户模板**转换**成标准化模板入库即可

---

## 1. 版本目标

### 1.1 V1.1.0 已解决
- PDF 简历解析 → experience 结构化入库
- 用户经历结构化数据库建设（SQL + embedding）
- JD 分析（关键词 / 技能要求 / 岗位画像）
- RAG 检索匹配（按 JD 从经历库拉匹配条目）
- AI 生成岗位针对性简历内容（ResumeContent JSON / Markdown）

### 1.2 V1.2.0 解决
将 AI 生成结果**稳定**输出为**可编辑**的 Word（DOCX）简历。

核心目标：
- 不做任意复杂 Word 的解析与重建
- 建立标准化、系统可控的模板系统
- 模板 DOCX + 模板 JSON 成对交付
- 渲染过程可预测、结果结构稳定
- 输出文件用户可直接在 Word 里手改（段落级可编辑，非文本框锁死）

### 1.3 版本边界
- **不支持**：任意用户上传 DOCX 模板、复杂文本框自动解析、shape 自动识别、Word XML 深度分析
- **支持**：系统内置标准化模板、标准 DOCX、模板 JSON 描述文件、占位符替换、样式继承

---

## 2. 核心设计原则

### 2.1 数据与展示严格分离

**禁止链路（反模式）**：
```
DOCX → 解析 → 修改 → 输出
```

**采用链路（正模式）**：
```
SQL 数据库 (真实数据)
     ↓
RAG 检索匹配
     ↓
AI 生成 (ResumeContent)
     ↓
ResumeBuilder 组装
     ↓
ResumeDocument 中间模型 (纯结构，与渲染无关)
     ↓
TemplateRenderer (拿模板 + 拿数据)
     ↓
DOCX Writer (替换占位符 + 继承样式)
     ↓
最终简历.docx
```

### 2.2 Word 只是渲染结果

系统内部真实数据来源：
- SQL 数据库（experience / skill 表）
- RAG 检索结果（匹配条目 + 评分）
- AI 生成内容（JD 定制化描述）

DOCX 模板只负责 4 件事：
1. 布局（段落顺序、分栏、缩进）
2. 样式（Paragraph Style / Run Style / 字体 / 字号 / 加粗）
3. 字体（CJK / Latin 分别指定）
4. 排版规则（段间距、页边距）

模板里不存任何事实数据，只存结构和样式。

### 2.3 模板标准化

**V1.2.0 承诺范围（必须做到）**：
- ✅ 系统内置标准化模板
- ✅ 标准 DOCX（原生段落 + 命名样式，**不使用文本框**）
- ✅ 每张模板配套 JSON 描述
- ✅ 模板可预览、可编辑（Word 里打开直接改段落样式）
- ✅ 多模板切换（`template_id` 参数）

**V1.2.0 不承诺范围（明确说不）**：
- ❌ 任意用户上传 Word 模板直接用
- ❌ 文本框 / shape / SmartArt / 浮动图片 自动识别
- ❌ Word XML 逆向分析
- ❌ 无损保留任意 Word 的复杂效果

---

## 3. 整体架构

```
┌───────────────────────────────────────────────────────────────────────────┐
│                               V1.1.0 已建                                    │
│  SQL DB (experience/skill)  JD Analysis    RAG Matching   AI Generator    │
└──────────────┬─────────────────┬───────────────────┬──────────┬───────────┘
               │                 │                   │          │
               └─────────────────┴───────────────────┴──────────┘
                                 ▼
                    ┌──────────────────────────┐
                    │    ResumeContent (V1.1.0)  │  ← 原始生成结果（字符串/JSON）
                    └───────────┬──────────────┘
                                ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                          V1.2.0 新增层                                       │
│                                                                             │
│  ┌────────────────────┐     ┌────────────────────────┐                    │
│  │   ResumeBuilder    │ ──► │   ResumeDocument        │                    │
│  │ (结构化装配/裁剪)   │     │   中间模型（纯结构）     │                    │
│  └────────────────────┘     └───────────┬────────────┘                    │
│                                          ▼                                 │
│                            ┌────────────────────────┐                    │
│                            │   TemplateRenderer     │                    │
│                            │  + 取模板 DOCX         │                    │
│                            │  + 取模板 JSON         │                    │
│                            │  + 占位符 ↔ 字段映射    │                    │
│                            └───────────┬────────────┘                    │
│                                        ▼                                 │
│                            ┌────────────────────────┐                    │
│                            │    DOCX Writer         │                    │
│                            │  + 段落级替换           │                    │
│                            │  + 样式继承            │                    │
│                            │  + 项目条目克隆扩容     │                    │
│                            │  + 规则排版微调         │                    │
│                            └───────────┬────────────┘                    │
└────────────────────────────────────────┼────────────────────────────────┘
                                         ▼
                              最终简历_岗位定制.docx
```

数据流关键约束：
- V1.1.0 输出的 `ResumeContent` **不能**直接喂给渲染器，必须经 `ResumeBuilder` 转成强类型 `ResumeDocument`
- `ResumeDocument` 与渲染完全解耦，未来加 PDF / 网页 / HR 系统接口时，这层**不变**
- 模板 DOCX 和 JSON 是**版本成对**的资产，变更时同步 bump `template_id`

---

## 4. 模块目录（新增/调整）

```
backend/
├── models/
│   ├── resume_document.py      # 既有，补齐字段（见 §5）
│   └── template_schema.py      # 重写：标准化模板描述（替换文本框方案）
├── templates/                  # 模板资产目录（原 templates_tmp 临时目录已清理）
│   ├── pm_template.docx        # 标准化模板 DOCX（段落+占位符，无文本框）
│   ├── pm_template.json        # 模板描述 JSON
│   ├── engineer_template.docx  # （后续扩展）技术岗模板
│   └── engineer_template.json
├── services/
│   ├── resume_builder.py       # 既有，重构：V1.1.0 输出 → ResumeDocument（裁剪前移）
│   ├── template_renderer.py    # 新增：模板读取 + 占位符映射 + 调用 DocxWriter
│   ├── docx_writer.py          # 重写：废弃文本框/坐标逻辑，改为「占位符替换 + 段落克隆」
│   ├── layout_optimizer.py     # 既有，保留：规则微调（不改内容）
└── config/
    └── template_mapping.json   # 新增：template_id → 模板路径的注册表
```

**弃用文件处理（V1.2.0 阶段清理已落地）**：
- `content_mapper.py`：已删除。裁剪职责移到 `ResumeBuilder.build(limit=...)`；映射职责移到 `TemplateRenderer` 按模板 JSON 声明的 sections 顺序渲染
- `template_parser.py`：已删除。原文本框解析/章节识别代码整体下线（生产代码零引用，仅历史调试脚本引用，随脚本一并清理）
- `models/template_schema.py` 的 `TemplateSection.source="textbox"` 等字段保留兼容，但新增 `TemplateSpec` 新类走标准化模板路径

---

## 5. 数据模型设计

### 5.1 ResumeDocument（中间模型，渲染无关）

文件：`models/resume_document.py`

**核心不变量**：这个类**只描述事实内容**，不包含任何段落索引、文本框坐标、样式 ID 等渲染相关信息。渲染需要的任何东西在 `TemplateRenderer` 里另外拿。

```python
@dataclass
class Profile:
    name: str                 # 姓名（必填）
    phone: str                # 电话
    email: str                # 邮箱
    location: Optional[str]   # 所在地
    target_position: str      # 求职意向 / 目标岗位（必填）
    summary: Optional[str]    # 自我评价 / 个人简介（V1.1.0 的 summary 字段）

@dataclass
class EducationItem:
    school: str
    major: str
    degree: str               # 本科 / 硕士 / 博士 / ...
    start_time: str           # "2023.09"
    end_time: str             # "2026.06" 或 "至今"
    gpa: Optional[str]
    description: Optional[str]  # 获奖 / 主修课 / 排名（单行或多行字符串）
    priority: float = 1.0     # RAG 匹配分 / 裁剪参考

@dataclass
class WorkItem:
    company: str
    role: str
    start_time: str
    end_time: str
    location: Optional[str]
    bullets: list[str]        # 职责/成果，每行一条（不内嵌换行，靠 bullet 展开）
    priority: float = 1.0

@dataclass
class ProjectItem:
    name: str
    role: str
    start_time: str
    end_time: str
    bullets: list[str]        # 项目背景 / 技术方案 / 成果 —— 每条独立 bullet
    tech_stack: Optional[list[str]]
    priority: float = 1.0

@dataclass
class SkillGroup:
    category: str             # 例如 "编程语言" / "产品工具" / "AI框架"
    items: list[str]          # 例如 ["Python", "SQL", "PyTorch"]

@dataclass
class ResumeDocument:
    profile: Profile
    education: list[EducationItem]
    work: list[WorkItem]
    projects: list[ProjectItem]
    skills: list[SkillGroup]
    awards: list[str]         # 奖项 / 证书，纯字符串列表
```

### 5.2 裁剪语义前移

旧方案 `content_mapper.py` 的裁剪（"决定展示哪些条目、展示几条"）**前移进 ResumeBuilder.build()**。

理由：
- 裁剪是业务决策（和 JD 匹配度、条目重要性有关），和模板无关
- 同一个 ResumeDocument 渲染到不同模板时，条目展示列表应该一样（模板只负责样式，不负责内容取舍）
- 旧方案把裁剪和渲染绑死，换模板要重裁，造成同一 JD 下不同模板输出不同内容集合 → 违反 2.1 数据展示分离

```python
class ResumeBuilder:
    @staticmethod
    def build(
        experiences_db: list,    # experience 表原始行
        jd_analysis: dict,       # V1.1.0 的 JD 分析结果
        generated_content: dict, # V1.1.0 的 AI 生成内容
        profile: Profile,        # 用户 profile（DB 优先，缺失时用模板兜底见 §9）
        *,
        max_education: int = 3,
        max_work: int = 3,
        max_projects: int = 3,
        max_awards: int = 5,
    ) -> ResumeDocument:
        """
        组装 + 裁剪（一步到位）。输出的 ResumeDocument 中每条 education/work/project
        都已经是 selected=True 的最终展示集合，后续渲染层不再裁内容。
        """
```

---

## 6. 模板系统设计

### 6.1 模板组成（成对资产）

每张模板 = 1 个 DOCX + 1 个 JSON：

```
backend/templates/
├── pm_template.docx     # 产品岗标准模板（段落+占位符+命名样式）
└── pm_template.json     # 模板声明
```

版本策略：模板大变更时不原地覆盖，改新增 `pm_template_v2.docx` + `pm_template_v2.json`，在 `config/template_mapping.json` 注册新 `template_id`。

### 6.2 模板 DOCX 编写规范（关键）

**必须遵守**，否则渲染器做不到稳定：

| 规则 | 说明 |
|------|------|
| R1 | 只用原生 Word 段落（`w:p`），**不使用文本框（`w:txbxContent`）、shape、SmartArt** |
| R2 | 章节标题使用命名段落样式。例：`SectionTitle`、`Education_Title`、`Work_Title`。**不用 Heading 1/2/3**（避免用户误点目录） |
| R3 | 正文使用命名段落样式。例：`Education_Body`、`Work_Body`、`Project_Body`、`Project_Bullet`、`Skill_Line` |
| R4 | 个人信息区使用 `Profile_Line`。例：姓名单独一个 `Profile_Name` 样式行 |
| R5 | 占位符统一用 `{{字段名}}` 双大括号。**一个占位符独占一个 Run**（不要和前后文字混在一个 Run） |
| R6 | 项目条目使用**单条模板段落** + `{{item.xxx}}`。渲染器负责克隆该段落、替换字段、插入多份。模板里只放 1 条样例（不放 3 条空占位） |
| R7 | 项目 bullet 使用单独的 `*_Bullet` 样式。模板里放 1 个 `{{item.bullet}}` 占位行 |
| R8 | 页面设置（页边距、纸张大小、默认字体）、页眉页脚、静态图标/背景**不使用占位符的区域**都直接放在模板里，渲染器完全不动 |
| R9 | 中英混排的多字体：模板原型段落里分 Run 设置好（CJK 一段 Run + Latin 一段 Run）。渲染器替换字段时按 Run 类型分别复用（见 §7.4） |
| R10 | 样式必须通过 Word「样式窗格」显式命名。禁止靠手动选一段设字体（那样叫 direct formatting，继承时会丢） |

### 6.3 模板 DOCX 结构样例（pm_template.docx）

**V1.2.0 PDF 布局复刻更新**：参照 `input/用户上传PDF.pdf` 提取的真实布局参数（pdfplumber 逐项测量），不再是 `input/模板.docx`。用纯段落 + 命名样式实现，关键排版特征：

- **页边距**：T=0.92cm B=1.39cm L=1.13cm R=1.09cm（PDF 实测，比 Word 默认小，因原 PDF 用文本框可超边距，改用段落后需缩小页边距匹配文字位置）
- **字号**：姓名 20pt 粗 #0D0D0D ｜ 章节标题 12pt 粗 #0D0D0D ｜ 经历标题行 10.6pt 粗 #262626 ｜ 正文 bullets 10.6pt 常规 #262626 ｜ 联系方式 10pt 常规
- **⚫ bullet**：用 `⚫`（U+26AB）前缀，**不是** `•`；bullet 行全部常规字体（**取消关键词加粗**）
- **三列 Tab**：经历标题行 `时间\t学校/公司\t专业/职位`，中点居中 + 右边右对齐
- **章节分隔线**：每个章节标题段加底边框（`w:pBdr/w:bottom`）
- **照片占位框**：右上角浮动 anchored drawing（2.375×2.9cm，距上 0.58cm 距右 1.63cm）
- **Profile 全左对齐**：姓名 → 求职意向 → 联系方式（顺序与 PDF 一致）

```
<页面顶部 - Profile 区，全左对齐 + 右上角照片框>
[Profile_Name 样式]         {{profile.name}}                        ← 20pt 粗
[Profile_Target 样式]       求职意向：{{profile.target_position}}      ← 10pt 常规
[Profile_Line 样式]         电话：{{profile.phone}} 丨 邮箱：{{profile.email}} 丨 所在地：{{profile.location}}  ← 10pt 常规
                              [右上角浮动照片占位框 2.375×2.9cm]

<教育背景区>
[SectionTitle_Education]    教育背景                                 ← 12pt 粗 + 底分隔线
[Education_ItemTitle]       {{edu.start_time}}-{{edu.end_time}} \t {{edu.school}} \t {{edu.major}}（{{edu.degree}}）  ← 三列 Tab
[Education_Body]            ⚫{{edu.description}}                    ← 10.6pt 常规
[Education_Body]            ⚫{{edu.gpa}}                            ← 可选，空则删行

<实习经历区>
[SectionTitle_Work]         实习经历                                 ← 12pt 粗 + 底分隔线
[Work_ItemTitle]            {{work.start_time}}-{{work.end_time}} \t {{work.company}} \t {{work.role}}  ← 三列 Tab
[Work_Bullet]               ⚫{{work.bullet}}                        ← 克隆此行，每条 bullet 一行

<项目经历区>
[SectionTitle_Project]      项目经历                                 ← 12pt 粗 + 底分隔线
[Project_ItemTitle]         {{project.start_time}}-{{project.end_time}} \t {{project.name}} \t {{project.role}}
[Project_Bullet]            ⚫{{project.bullet}}

<技能专长区>
[SectionTitle_Skills]       技能专长                                 ← 12pt 粗 + 底分隔线
[Skill_Line]                {{skill.category}}：{{skill.items}}      ← 分类加粗 + items 顿号分隔常规

<荣誉奖项区 - 可选，有数据才渲染>
[SectionTitle_Awards]       荣誉奖项                                 ← 12pt 粗 + 底分隔线
[Award_Line]                ⚫{{award}}                              ← 克隆，每条一行

<自我评价区 - 可选，有数据才渲染>
[SectionTitle_Summary]      自我评价                                 ← 12pt 粗 + 底分隔线
[Summary_Bullet]            ⚫{{summary.bullet}}                     ← profile.summary 按换行拆多条
```

**要点**：
- 每类项目条目（Education / Work / Project）模板里只写 1 条**完整的样例块**（标题行 + 内容行 / bullet 行），渲染器按 ResumeDocument 里实际条目数**克隆样例块 + 替换字段**
- 这是标准化模板方案的核心：**不需要知道模板里放几条空位**，只要有 1 条原型，就能扩任意条
- **V1.2.0 布局参数全部来自 PDF 实测**，非主观设计：页边距/字号/颜色/照片框位置/章节顺序均有 [布局一致性核对脚本](../../../backend/) 46/46 PASS 验证

### 6.4 模板 JSON

文件：`backend/templates/pm_template.json`

作用：告诉渲染器「模板里有哪些区块、每个区块对应 ResumeDocument 的哪个字段、区块里的段落样式原型是什么」。

**V1.2.0 设计原则（用户审核反馈）**：JSON **不做过重 DSL**，第一版只保留 4 个核心字段：`section / style / placeholder / repeat`。`join` / `skip_if_empty` / `layout_rules` 等过滤器与规则**后置到 V2 渐进加入**，避免 MVP 阶段提前设计未验证的复杂度。

```json
{
  "id": "pm_template",
  "version": "1.2",
  "display_name": "产品岗标准模板",
  "author": "ai-resume-system",
  "layout": {
    "page_size": "A4",
    "margin_cm": { "top": 0.92, "bottom": 1.39, "left": 1.13, "right": 1.09 },
    "default_font_cn": "微软雅黑",
    "default_font_en": "Microsoft YaHei",
    "page_limit": 1
  },
  "sections": [
    {
      "id": "profile",
      "type": "profile",
      "required": true,
      "rows": [
        { "style": "Profile_Name",     "placeholder": "{{profile.name}}" },
        { "style": "Profile_Line",     "placeholder": "{{profile.phone}} | {{profile.email}} | {{profile.location}}" },
        { "style": "Profile_Target",   "placeholder": "求职意向：{{profile.target_position}}" },
        { "style": "Profile_Summary",  "placeholder": "{{profile.summary}}" }
      ]
    },
    {
      "id": "education",
      "type": "education",
      "required": true,
      "title_style": "SectionTitle_Education",
      "max_items": 3,
      "item_block": [
        { "style": "Education_ItemTitle", "placeholder": "{{edu.school}} | {{edu.major}}（{{edu.degree}}） | {{edu.start_time}} - {{edu.end_time}}" },
        { "style": "Education_Body",      "placeholder": "{{edu.description}}" },
        { "style": "Education_Body",      "placeholder": "GPA：{{edu.gpa}}" }
      ]
    },
    {
      "id": "work",
      "type": "work",
      "required": true,
      "title_style": "SectionTitle_Work",
      "max_items": 3,
      "item_block": [
        { "style": "Work_ItemTitle", "placeholder": "{{work.company}} | {{work.role}} | {{work.start_time}} - {{work.end_time}}" },
        { "style": "Work_Bullet",    "placeholder": "• {{work.bullet}}", "repeat": "work.bullets" }
      ]
    },
    {
      "id": "projects",
      "type": "project",
      "required": true,
      "title_style": "SectionTitle_Project",
      "max_items": 3,
      "item_block": [
        { "style": "Project_ItemTitle", "placeholder": "{{project.name}} | {{project.role}} | {{project.start_time}} - {{project.end_time}}" },
        { "style": "Project_Bullet",    "placeholder": "• {{project.bullet}}", "repeat": "project.bullets" }
      ]
    },
    {
      "id": "skills",
      "type": "skills",
      "required": true,
      "title_style": "SectionTitle_Skills",
      "item_block": [
        { "style": "Skill_Line", "placeholder": "{{skill.category}}：{{skill.items}}", "repeat": "skills" }
      ]
    },
    {
      "id": "awards",
      "type": "awards",
      "required": false,
      "title_style": "SectionTitle_Awards",
      "max_items": 5,
      "item_block": [
        { "style": "Award_Line", "placeholder": "• {{award}}", "repeat": "awards" }
      ]
    }
  ]
}
```

> 注：V1.2.0 渲染器对列表字段（如 `skill.items`）的字符串化在代码内固定为「顿号分隔」，不暴露为 JSON 语法。等 V2 有真实多模板需求再升级为 `join` filter。

### 6.5 模板 JSON 关键语法（V1.2.0 仅 4 个）

| 语法 | 示例 | 含义 |
|------|------|------|
| `placeholder` | `"{{profile.name}}"` | 整段静态替换（只出现一次的字段） |
| `style` | `"Work_ItemTitle"` | 模板内命名段落样式名，**渲染器按 style 定位原型段，不依赖文本** |
| `title_style` | `"SectionTitle_Education"` | 章节标题样式名（标题文本由模板自身提供，渲染器不替换文本，只按 style 锚点定位） |
| `repeat` | `"repeat": "work.bullets"` | 克隆该行，遍历 ResumeDocument 中的列表字段（每条一行） |
| `max_items` | `3` | 该区块渲染上限（ResumeBuilder 已裁到 ≤ 这个值；这里是渲染兜底） |

**V1.2.0 不支持的语法（明确后置）**：
- ❌ `skip_if_empty`：V1.2.0 改为代码内固定规则——字段为空时整段删除（不占空白行），不暴露为 JSON 配置
- ❌ `join` filter：列表字段在代码内固定分隔符
- ❌ `layout_rules`：排版规则**后置**，V1.2.0 渲染器内置固定四级降级（见 §8.2），不读 JSON 规则
- ❌ `foreach`（已改名为 `repeat`，语义更直白）

### 6.6 章节定位：用 style 不用文本（关键变更）

**用户审核反馈明确要求**：不要依赖章节标题文本（如"教育背景"）定位，因为用户在 Word 里手改成"教育经历"会让渲染失败——这正是旧方案踩过的坑。

**V1.2.0 定位规则**：
- 模板里章节标题段必须使用专属命名样式，如 `SectionTitle_Education` / `SectionTitle_Work` / `SectionTitle_Project` / `SectionTitle_Skills` / `SectionTitle_Awards`
- 模板 JSON 的 `title_style` 字段声明该样式名
- 渲染器按「段落 `style.name == section_spec.title_style`」定位章节锚点，**完全不读段落文本**
- 标题段文本由模板作者写好（"教育背景"或"教育经历"都行），渲染器**不替换、不删除**，原样保留

这样：
- 用户在 Word 里把"教育背景"改成"教育经历"→ 渲染仍然成功（因为靠 style 定位）
- 旧方案"靠文本识别章节"的坑**不会回来**

### 6.7 模板注册表

文件：`backend/config/template_mapping.json`

```json
{
  "pm_template": {
    "docx": "templates/pm_template.docx",
    "json": "templates/pm_template.json",
    "default": true
  },
  "engineer_template": {
    "docx": "templates/engineer_template.docx",
    "json": "templates/engineer_template.json"
  }
}
```

---

## 7. 渲染器（TemplateRenderer + DOCX Writer）设计

### 7.1 渲染入口

文件：`services/template_renderer.py`

```python
class TemplateRenderer:
    def __init__(self, template_id: str):
        """加载模板资产：DOCX 路径 + JSON 声明。"""
        # 读 config/template_mapping.json 找路径
        # 读 templates/<id>.json 拿 sections 声明
        # 用 python-docx 打开 templates/<id>.docx（不直接改，在内存副本上操作）

    def render(self, doc: ResumeDocument) -> Document:
        """
        主入口：ResumeDocument → 已填充的 python-docx Document。
        调用方 Document.save(path) 存盘。
        """
        for section_spec in self.spec.sections:
            if section_spec.type == "profile":
                self._render_profile(section_spec, doc.profile)
            elif section_spec.type == "education":
                self._render_item_list(section_spec, doc.education, item_cls=EducationItem)
            elif section_spec.type == "work":
                self._render_item_list(section_spec, doc.work, item_cls=WorkItem)
            elif section_spec.type == "project":
                self._render_item_list(section_spec, doc.projects, item_cls=ProjectItem)
            elif section_spec.type == "skills":
                self._render_skills(section_spec, doc.skills)
            elif section_spec.type == "awards":
                self._render_awards(section_spec, doc.awards)
        # 最后过一遍 layout_optimizer
        return LayoutOptimizer.optimize(self._docx, self.spec.layout_rules)
```

### 7.2 占位符定位策略（按 style，不按文本）

**不做全文 `{{...}}` 正则扫描**。也**不按章节标题文本**定位（用户审核反馈明确否决了文本定位方案）。正确做法：

1. **定位章节标题锚点**：在模板 DOCX 里按「段落 `style.name == section_spec.title_style`」找到标题段位置。标题段**不替换、不删除**（文本由模板作者写好，原样保留）
2. **定位区块原型段落**：在标题段之后的 N 段里，按 `style.name == section_spec.item_block[].style` 找到原型段
3. **替换 + 克隆**：对原型段做字段替换得到真实段；需要几条就克隆几份；原型段最后删除

**为什么不按文本、不全文扫 `{{`**：
- 文本定位的坑：用户在 Word 里把"教育背景"改成"教育经历"→ 旧方案渲染失败。V1.2.0 靠 style 定位，文本可自由修改
- 正则全文扫 `{{` 会误命中模板注释、示例文本、嵌套字符串字面量
- 按 style + 锚点定位，位置精确可控，和模板 JSON 声明一一对应

### 7.3 item_list 渲染算法（Work/Project/Education）

```
输入：section_spec（含 title_style + item_block 声明）
      items：ResumeDocument 中对应列表（已由 ResumeBuilder 裁剪到 ≤ max_items）

1. 找标题锚点 P_title = 模板里「style.name == section_spec.title_style」的段落
2. 如果 P_title 找不到 → raise TemplateError(f"style [{section_spec.title_style}] not found in template")
3. 如果 items 为空且 section.required=false → 删除 P_title 及下方整块原型段，跳过
4. 如果 items 为空且 section.required=true →  raise TemplateError(f"必填章节[{section_spec.id}]无内容")
5. 收集 item_block 原型段列表：
   P_block = []
   cursor = P_title.next_sibling (paragraph only)
   for row_spec in section_spec.item_block:
       while cursor 存在 and cursor.style.name != row_spec.style:
           cursor = cursor.next_sibling   # 跳过空白/分隔段
       P_block.append( (row_spec, cursor) )
       cursor = cursor.next_sibling
6. 实际插入：
   ref = P_title        # 在 ref 之后插入新段
   for item in items:
       for (row_spec, proto_p) in P_block:
           if row_spec has "repeat":
               # bullet 行：遍历 item[repeat_list]，每个值克隆一行
               sub_values = resolve_dotpath(item, row_spec.repeat)
               for v in sub_values:
                   ctx = merge(item_ctx, {repeat_var: v})
                   new_p = clone_paragraph(proto_p)
                   fill_placeholders(new_p, row_spec.placeholder, ctx)
                   ref.insert_after(new_p)
                   ref = new_p
           else:
               # 普通行：字段替换
               ctx = resolve_context(item, row_spec.placeholder)
               # 空值兜底：任意占位符为空 → 整段删除（不占空白行）
               if any_placeholder_empty(ctx):
                   continue
               new_p = clone_paragraph(proto_p)
               fill_placeholders(new_p, row_spec.placeholder, ctx)
               ref.insert_after(new_p)
               ref = new_p
7. 删除原型块 P_block 中所有段落（不留模板样板行）
```

**V1.2.0 空值规则（代码内固定，不暴露为 JSON 配置）**：
- 任意占位符解析为空字符串 → 整段删除（不占空白行）
- 不区分"必填占位符"和"可选占位符"——空了就删段，由 ResumeBuilder 保证必填字段非空（见 §9 缺失直接报错）

### 7.4 clone_paragraph + fill_placeholders（V1.2.0 简化版）

用户审核反馈明确指出：V1.2.0 **不主动做 token 拆分 + 动态 Run 复制**，因为 python-docx 对 Run XML 操作复杂度高，且 V1.2.0 的优势正是"控制模板"——既然模板由我们标准化，就让模板阶段保证「一个占位符独占一个 Run」，渲染时只替换 `w:t` 文本、保留原 Run 属性即可。Run 级 token 拆分算法留 V2。

```python
def clone_paragraph(proto_p: Paragraph) -> Paragraph:
    """深拷贝段落 XML，保证样式 100% 继承。返回新段（未插入文档，需 insert_after）。"""
    # 用 lxml 深拷贝 proto_p._p 整个 w:p 元素
    new_p_elem = copy.deepcopy(proto_p._p)
    # 清空所有 w:t 的 text（不删 Run，保留 rPr 样式链）
    for t in new_p_elem.iter(qn('w:t')):
        t.text = ''
    return Paragraph(new_p_elem, proto_p._parent)

def fill_placeholders(new_p: Paragraph, placeholder_str: str, ctx: dict):
    """
    V1.2.0 简化策略：
    - 模板编写规范（§6.2 R5）已强制要求：一个 {{xxx}} 占位符独占一个 Run
    - 渲染器只做一件事：遍历新段所有 Run，找到含 {{xxx}} 的 w:t，
      用 ctx[xxx] 替换 w:t 的文本内容，Run 的 rPr（字体/字号/加粗）原样保留
    - 不解析 placeholder_str 里的多个占位符拼接，因为模板编写规范保证
      "求职意向：{{profile.target_position}}" 这种带前缀的占位符也是独占 Run
      （前缀文字在另一个 Run，不与 {{}} 混排）

    对含单个 {{xxx}} 的 Run：
        run.text = ctx.get(xxx, '')   # python-docx 高层 API 只改 w:t 文本

    对含多个 {{xxx}} 拼接的 Run（理论上不应出现，但兜底）：
        full = run.text
        for k, v in ctx.items():
            full = full.replace('{{' + k + '}}', str(v))
        run.text = full

    对列表字段 repeat（如 work.bullets）：
        - 外层 §7.3 算法已对每个 bullet 值 clone_paragraph 一次
        - 这里 ctx = {"work.bullet": 单条值}，run.text = ctx["work.bullet"]
    """
```

**V1.2.0 字体保真保障链**（替代旧方案的 Run 级动态复制）：
1. 模板编写规范 R5：一个 `{{xxx}}` 占位符独占一个 Run（模板作者在 Word 里手动分 Run，或我们用脚本预处理）
2. 模板编写规范 R9：中英混排段落，模板作者在原型段里分 Run 设置好 CJK Run + Latin Run
3. 渲染器只替换 `w:t` 文本，**完全不动 rPr XML** → 字体/字号/加粗原样继承
4. 多占位符混排的复杂场景（如 `{{work.company}} | {{work.role}}` 这种 1 个 Run 里塞两个占位符的情况）→ V1.2.0 模板编写规范**禁止**，由模板作者拆成多个 Run；渲染器遇到时降级为"字符串拼接替换"，不保证字体分角色继承

**为什么不做到 Run 级动态拆分**：
- python-docx 对 Run XML 操作复杂度高，V1.2.0 MVP 不上
- 既然模板由我们标准化，就让模板阶段保证分 Run，把复杂度前置到模板编写，而不是后置到渲染器
- V2 当出现用户自定义模板（无法保证分 Run）时，再升级到 §7.4 旧版的 token 拆分算法

### 7.5 缺失值处理 & 空值兜底

| 情况 | 处理 |
|------|------|
| `{{profile.name}}` 为空且 required | `raise ProfileIncompleteError`（提前中止，不生成半残文件，见 §9） |
| `{{edu.gpa}}` 为空 | 整段 GPA 行删除（代码内固定规则，不占空白行） |
| `{{edu.description}}` 为空 | 整段删除 |
| `work.bullets` 列表为空 | 该 WorkItem 下不产生 bullet 段，不占行 |
| `skills` 列表为空且 required=true | 渲染失败告警 |
| profile 整体为空（DB / request / AI 三层都拿不到） | **直接报错，不生成文件**（见 §9） |

---

## 8. 排版优化

### 8.1 原则重申

V1.2.0 只做**规则优化**，不做 AI 排版。

- **允许调整（四级降级）**：①段前距 ②字号 ③行距 ④页边距
- **禁止删除内容**：经历条目数量、bullet 数量、描述文字、用户事实内容，**一律不动**
- **裁剪位置**：经历条目裁剪**只在 ResumeBuilder 阶段**决定（按 JD 优先级排序 + max_items 上限），渲染层/LayoutOptimizer 不再裁内容

**用户审核反馈明确指出**：旧版 §8.2 的 `{"action":"reduce", "target":"item_count"}` 与 §8.1「禁止删除用户经历条目」**自相矛盾**（item_count 减少 = 删除经历）。V1.2.0 删除该能力，LayoutOptimizer 只调段落级样式，不裁条目。

### 8.2 排版规则引擎（LayoutOptimizer，V1.2.0 固定四级降级）

输入：已填充完成的 Document + 模板 JSON 的 `layout.page_limit`。

V1.2.0 排版规则**代码内固定**，不读 JSON 规则（layout_rules 后置到 V2）。算法：

```python
def optimize(doc, page_limit: int) -> list[str]:
    """
    返回应用的优化清单（供 generate-report 展示）。
    四级降级按顺序尝试，每级尝试后重新估算页数，达标即停。
    """
    applied = []
    if estimate_pages(doc) <= page_limit:
        return applied

    # 一级：段前距/段后距 6pt → 3pt → 0pt
    for spacing_pt in (6, 3, 0):
        if estimate_pages(doc) <= page_limit:
            break
        apply_paragraph_spacing(doc, spacing_pt)
        applied.append(f"paragraph spacing → {spacing_pt}pt")

    # 二级：正文字号 10.5pt → 10pt → 9.5pt
    for size_pt in (10.5, 10, 9.5):
        if estimate_pages(doc) <= page_limit:
            break
        apply_body_font_size(doc, size_pt)
        applied.append(f"body font size → {size_pt}pt")

    # 三级：行距 1.5 → 1.3 → 1.15
    for line_spacing in (1.5, 1.3, 1.15):
        if estimate_pages(doc) <= page_limit:
            break
        apply_line_spacing(doc, line_spacing)
        applied.append(f"line spacing → {line_spacing}")

    # 四级：页边距各减 0.3cm（最多减一次）
    if estimate_pages(doc) > page_limit:
        apply_margin_reduce(doc, 0.3)
        applied.append("margin reduced by 0.3cm")

    return applied
```

**降级终止条件**：四级都试完仍超页 → 不再继续，返回 warning "resume exceeds page_limit even after all layout optimizations"，**不删任何条目**，由用户在 Word 里手动调整。

---

## 9. profile 数据来源（V1.2.0 删除模板兜底）

### 9.1 数据隔离原则（用户审核反馈）

**旧方案的模板兜底设计危险**：从模板 DOCX 里取出"白晓彤 / 138xxxx / 北京"作为用户 profile。模板是**设计稿**不是**用户数据**，会导致：
- 用户 A 生成简历 → 姓名「张三」电话「138xxxx」（来自模板，不是用户 A 真实信息）
- 这是**严重数据污染**

**新原则**：
- 模板只提供**结构**（占位符 `{{profile.name}}`），**不提供事实数据**（不允许模板默认姓名）
- ResumeDocument 是简历事实的**唯一真源**，模板不参与数据
- profile 三层都拿不到 → **直接报错，不生成文件**（宁可不生成，也不生成污染数据）

### 9.2 ProfileResolver 三优先级（无模板兜底）

```python
class ProfileResolver:
    @staticmethod
    def resolve(
        user_id: str,
        request_profile: Optional[dict],   # 接口请求体里传的 profile（可覆盖 DB）
        resume_content_profile: dict,       # V1.1.0 AI 生成结果里的 profile（JD 定制化求职意向等）
    ) -> Profile:
        """
        优先级（字段级合并，非整体替换）：
          1) user_profile DB：从 user_profile 表按 user_id 取，有值的字段优先用 DB
          2) request_profile：请求参数显式传入的字段（用于覆盖 DB，如用户前端改了求职意向）
          3) resume_content_profile：AI 生成的 JD 定制化字段（主要是 target_position / summary）

        字段级合并规则：每个字段按上面优先级取第一个非空值。
        合并后必填字段（name / target_position）仍为空 → raise ProfileIncompleteError
        """
```

### 9.3 缺失处理

| 情况 | 处理 |
|------|------|
| DB 有完整 profile | 直接用 DB |
| DB 缺 target_position，request 有 | 合并：name/phone/email/location 用 DB，target_position 用 request |
| DB / request / AI 三层合并后 name 仍空 | `raise ProfileIncompleteError(missing=["name"])`，HTTP 4xx 返回，不生成 docx |
| 三层合并后 target_position 空 | 同上 `ProfileIncompleteError(missing=["target_position"])` |
| 可选字段（location/summary）空 | 正常生成，对应占位符段删除（不占空白行，见 §7.5） |

### 9.4 与模板的边界

- 模板 DOCX 里的 `{{profile.name}}` 占位符**必须保持占位符形式**，不允许填真实姓名
- 模板设计稿展示用 → 另出一份「预览版」docx（带样例数据，不参与生成流程），或在前端用 JSON mock 渲染预览
- 模板入库时校验：扫描所有 profile 占位符段，若发现实际文本不是 `{{xxx}}` 形式 → 报错"模板包含非占位符的真实数据，违反数据隔离原则"

---

## 10. API 设计

### 10.1 模板注册（管理用，V1.2.0 先本地文件不做 HTTP 上传）

**预留接口**（V2 再实装）：
```
POST /api/template/register
Content-Type: multipart/form-data
字段：
  template_id: string      # 例 pm_template_v2
  docx: file               # 模板 DOCX
  json: file               # 模板 JSON 描述
返回：
  { "ok": true, "template_id": "pm_template_v2", "sections": [...] }
```

V1.2.0 简化：模板直接放 `backend/templates/` 目录 + 在 `config/template_mapping.json` 里登记，无需 HTTP 上传。

### 10.2 模板列表查询

```
GET /api/template/list
返回：
{
  "templates": [
    {
      "template_id": "pm_template",
      "display_name": "产品岗标准模板",
      "page_limit": 1,
      "sections": ["profile", "education", "work", "projects", "skills", "awards"]
    }
  ]
}
```

### 10.3 核心：生成简历 DOCX

**用户审核反馈**：开发阶段不要直接返回二进制流，调试不方便。改为**返回 path + report**，由前端按 path 再下载文件。

```
POST /api/template/generate-docx
请求 JSON：
{
  "user_id": "u_xxx",
  "template_id": "pm_template",
  "jd": "AI产品经理实习生 JD 全文...",   # 或 jd_id
  "profile": {                          # 可选，覆盖 DB 的 profile（见 §9.2 第 2 优先级）
    "target_position": "AI产品经理（实习生）"
  }
}

响应（成功，HTTP 200，JSON）：
{
  "ok": true,
  "file_path": "output/resume_u_xxx_pm_template.docx",   # 服务端固定路径（不时间戳，避免循环）
  "file_name": "resume_u_xxx_pm_template.docx",
  "report": {
    "sections_rendered": ["profile", "education(2)", "work(3)", "projects(3)", "skills(5)", "awards(2)"],
    "page_count": 1,
    "layout_optimizations_applied": ["paragraph spacing → 3pt"],
    "warnings": [
      "awards 为空（非必填，已跳过）"
    ],
    "profile_source": "db"     # db / request / ai，标识 profile 来源（见 §9）
  },
  "download_url": "/api/file/download?path=output/resume_u_xxx_pm_template.docx"
}

响应（业务失败，HTTP 4xx，JSON）：
{
  "ok": false,
  "error_code": "PROFILE_INCOMPLETE",
  "message": "必填字段缺失：name。已尝试 DB / request / AI 三层数据源。",
  "missing_fields": ["name"]
}
```

**V2 升级路径**：生产环境可加 `?as_binary=1` 参数，直接返回二进制流（绕过 JSON 包装），用于前端流式下载。

### 10.4 文件下载（配套）

```
GET /api/file/download?path=output/resume_xxx.docx
响应：二进制流 + Content-Disposition: attachment
```

### 10.5 生成报告（可选，用于调试/预览）

```
POST /api/template/generate-report
请求同 generate-docx
返回 JSON（不返回二进制文件）：
{
  "ok": true,
  "file_name": "resume_xxx.docx",
  "sections_rendered": ["profile", "education(2)", "work(3)", "projects(3)", "skills(5)", "awards(2)"],
  "page_count": 1,
  "layout_optimizations_applied": [ "reduced paragraph spacing from 6pt to 3pt" ],
  "warnings": [
    "awards 为空（非必填，已跳过）",
    "profile.location 为空，使用模板兜底「北京」"
  ]
}
```

---

## 11. 验收标准

### 11.1 功能验收（必须全过）

| # | 检查项 | 方法 | 标 准 |
|---|--------|------|-------|
| F1 | 根据 JD 生成对应简历 | generate-docx → 打开 docx | 章节结构完整，内容与 JD 相关性可人工确认 |
| F2 | DOCX 可正常打开 | Word 打开 / python-docx 读取 | 无损坏提示，无 XML 报错 |
| F3 | 模板布局保持 | Word 中与模板原文件并排对比 | 页边距/分栏/缩进/图标位置一致 |
| F4 | 字体样式保持 | 抽样 5 段对比 rPr XML | eastAsia / ascii / sz / b 与模板原型一致 |
| F5 | 模板编写规范 R5 单 Run 占位符生效 | 含占位符段落抽查 Run | 一个 `{{xxx}}` 独占一个 Run，渲染后 Run 的 rPr 不变 |
| F6 | 内容全部来自 ResumeDocument | generate-report 中 sections_rendered vs ResumeDocument 字段比对 | 无任何超出 ResumeDocument 的虚构条目；**模板数据不混入** |
| F7 | 无文本框/无重影 | 生成 docx 的 XML 扫描 w:txbxContent | 计数为 0；不存在多段同坐标叠加 |
| F8 | profile 三层数据源合并正确 | 构造 DB 缺 target_position + request 有 → 生成 | name 用 DB，target_position 用 request，report.profile_source 标 db |
| F9 | profile 缺失直接报错 | user_id 无 DB 记录 + request 无 + AI 无 → 生成 | 返回 `PROFILE_INCOMPLETE`，不生成 docx（不污染数据） |
| F10 | 空值段删除正确 | 构造无 GPA 的 ResumeDocument → 生成 | 模板里 GPA 行完全不出现，不占空白行 |
| F11 | Work/Project 条目扩容正确 | 构造 3 条 Work → 生成 | 文档中出现 3 份 Work 块，原型块模板段完全删除 |
| F12 | 章节标题文本可改 | 在 Word 里把"教育背景"改成"教育经历" → 重新生成 | 仍然成功渲染（因为靠 style 定位，不靠文本） |
| F13 | LayoutOptimizer 不删条目 | 构造超页内容 → 生成 → 人工对比条目数 | 输出条目数 == ResumeDocument 条目数，排版只调样式 |

### 11.2 稳定性验收（必须全过）

| # | 检查项 | 标准 |
|---|--------|------|
| S1 | 模板结构错误时返回明确提示 | section_spec 中 style 在模板里找不到 → 返回 `TemplateError("style Education_ItemTitle not found in template")`，不静默生成 |
| S2 | 必填字段缺失时报错 | profile.name 为空（DB/request/AI 三层都空）→ 返回 `PROFILE_INCOMPLETE`，不产生空白/污染文件 |
| S3 | 不生成不存在的经历 | ResumeDocument.projects 只有 2 条 → 生成结果里 projects 块只能有 2 份，不得出现第 3 份 |
| S4 | 确定性输出 | 同一 ResumeDocument + 同一 template_id 生成 2 次 → 输出 docx 结构一致（页数/段落数/样式一致）|
| S5 | 条目数异常兜底 | ResumeBuilder 返回 5 条 work，而模板 max_items=3 → 渲染器截断到前 3 条并打 warning |
| S6 | 模板入库数据隔离校验 | 模板入库时扫描 profile 占位符段，若实际文本不是 `{{xxx}}` 形式 → 拒绝入库 |

### 11.3 可编辑性验收（V1.2.0 核心差异化指标）

| # | 检查项 | 标准 |
|---|--------|------|
| E1 | 用户可直接编辑正文段落 | 打开 DOCX 后，任意正文字段可双击进入编辑模式，光标进入段落不弹出「这是文本框」提示 |
| E2 | 修改一处字体不影响其他 | 手动把某段正文改成「宋体」→ 其他段字体不变 → 说明没有共享样式 bug |
| E3 | 删除条目不破坏结构 | 手动删除一个 Project 块的 3 个段落 → 后面章节不上飘错位 → 说明没有绝对坐标依赖 |
| E4 | 章节标题可改 | 手动把"教育背景"改成"教育经历" → 保存 → 重新生成（用该 docx 当模板的场景，V2 才支持）→ 仍然成功 |

---

## 12. 后续扩展

| 版本 | 能力 | 说明 |
|------|------|------|
| V2 | 用户自定义模板（上传 docx + 在线标注区） | 模板编辑器：用户点选段落 → 在侧栏指定属于哪个 section → 系统自动生成 JSON |
| V2 | 多模板市场 | 内置 10+ 套岗位模板（产品/研发/运营/设计/市场） |
| V3.0.0 | Word → 模板自动转换 | 用户上传一份简历 Word → AI 识别样式 → 自动生成标准化模板 + JSON（**这就是旧方案的最终形态，但放在 V3 做而不是 V1.2.0 硬上**） |
| V4 | 文档 Agent | 用户自然语言指令：「把 AI 项目突出一点」→ Agent 自动调项目排序 / 篇幅 / 模板（V2 架构已为该方向铺路：ResumeDocument + TemplateRenderer 的抽象使 Agent 只改数据不改 Word XML） |

---

## 13. 最终架构全景图

```
┌────────────────────────────────────────────────────────────────────────┐
│                          DATA LAYER (事实源)                            │
│  SQL (experience / skill / user_profile)    JD 文本                    │
└──────────────┬────────────────────────────────────────┬────────────────┘
               │                                        │
               ▼                                        ▼
   V1.1.0  RAG Matching + JD Analysis        V1.1.0  ResumeContent AI 生成
               │                                        │
               └──────────────────┬─────────────────────┘
                                  ▼
                 ┌───────────────────────────────────┐
                 │     ResumeBuilder.build()         │  ← 【裁剪在这里】
                 │  + 组装                           │     排序 + limit
                 │  + 裁剪（按 JD 优先）              │
                 │  + profile 三优先级兜底            │
                 └───────────────┬───────────────────┘
                                 ▼
                 ┌───────────────────────────────────┐
                 │      ResumeDocument               │  ← 渲染无关的纯结构
                 │  profile / education / work       │     唯一真源
                 │  projects / skills / awards       │
                 └───────────────┬───────────────────┘
                                 │
          ┌──────────────────────┼──────────────────────┐
          │                      │                      │ 多模板切换时：
          ▼                      ▼                      ▼ ResumeDocument 不变（事实真源，不参与渲染）
    pm_template.json      engineer.json          xxx_template.json
    pm_template.docx      engineer.docx          xxx_template.docx
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 ▼
                 ┌───────────────────────────────────┐
                 │      TemplateRenderer             │  ← 【只改渲染不改内容】
                 │  + 按 section 克隆原型段          │
                 │  + 占位符字段替换                 │
                 │  + CJK/Latin Run 级字体继承       │
                 └───────────────┬───────────────────┘
                                 ▼
                 ┌───────────────────────────────────┐
                 │      LayoutOptimizer              │  ← 只调段落级样式
                 │  + 段距 / 行距 / 字号             │     不删条目
                 │  + item_count 微调兜底            │
                 └───────────────┬───────────────────┘
                                 ▼
                     简历_{user_id}_{template_id}.docx
                          （段落级可编辑）
```

---

## 14. 实现优先级

### P0（可交付 MVP，验收 F1-F13 / S1-S6 / E1-E4）
1. `models/resume_document.py`：补齐 §5.1 的强类型字段（Profile 三字段必填 / WorkItem.bullets 为 list 等约束落地）
2. `models/template_schema.py`：新增 `TemplateSpec / SectionSpec / RowSpec` 新类（标准化模板 JSON 的对象化）；旧 `TemplateSection` 标记 deprecated
3. `services/resume_builder.py`：重构 `build()`，裁剪前移 + 接入 §9 的 ProfileResolver（DB / request / AI 三层合并，**无模板兜底**，缺失直接报错）
4. `backend/templates/` 目录 + `pm_template.docx` + `pm_template.json`：按 §6.3 / §6.4 做第一张标准模板（段落+命名样式，不用文本框）
5. `config/template_mapping.json`：模板注册表
6. `services/template_renderer.py`：§7 的渲染入口 + item_list 算法
7. `services/docx_writer.py`（重写）：`clone_paragraph` + `fill_placeholders`（只改 `w:t` 文本，rPr 原样继承，不做 Run 级动态拆分）
8. `services/layout_optimizer.py`：§8.2 规则引擎（不动内容）
9. `api/routes/template.py`：§10 的 HTTP 接口（list / generate-docx / generate-report）
10. 独立 E2E 脚本（不形成循环）：固定输出文件名，不时间戳，生成 1 docx + 1 report txt

### P1（体验增强）
1. 多模板：新增 `engineer_template.docx/json`（技术岗模板，技能区增加技术栈分层展示）
2. 模板管理：`POST /api/template/register` HTTP 上传 + JSON 校验
3. 排版优化 UI 提示：generate-report 返回优化清单让前端提示用户
4. 导出目录统一到 `backend/output/`（不再散落各处）

### P2（远期，和 V2/V3 对齐）
1. 模板编辑器（前端点选标注）
2. Word → 模板 AI 转换
3. 文档 Agent 自然语言交互

---

## 15. 与前版方案的差异对照

| 维度 | 前版（解析任意模板） | 本版（标准化模板系统） |
|------|---------------------|----------------------|
| 模板来源 | 用户上传任意 DOCX | 系统内置（docx+json 成对） |
| 文本框使用 | 依赖（模板里大量 w:txbxContent） | 禁止（只用原生 w:p） |
| 家族识别 / 坐标去重 | 需要，且有跨章节冲突 bug | 不需要（无绝对坐标依赖） |
| 章节识别 | 三级策略（Heading + 关键词 + LLM 预留） | 按 `title_style` 命名样式定位（不依赖文本） |
| 写入方式 | 按 textbox_indices 清空+重写 XML | 按 style 找到原型段 → 克隆 → 替换 `w:t` 文本 |
| 字体保真 | StyleInfo 合并（压平多字体） | 模板编写规范保证占位符单 Run + 渲染器只改 w:t（rPr 原样继承）；Run 级动态拆分留 V2 |
| profile 数据源 | DB + 模板兜底 | DB / request / AI 三层合并 + 缺失直接报错（**无模板兜底**） |
| 裁剪位置 | ContentMapper（渲染时） | ResumeBuilder（渲染前，与模板无关） |
| LayoutOptimizer 能力 | 字号/段距/行距/item_count | 字号/段距/行距/页边距（**禁止动 item_count**） |
| 模板 JSON 复杂度 | 7 种语法（含 join/skip_if_empty/layout_rules） | 4 种核心（section/style/placeholder/repeat），其余后置 V2 |
| 可编辑性 | 文本框锁死（用户手改困难） | 段落级可编辑（Word 原生操作） |
| 稳定性 | 高风险（文本框/坐标/家族任何一环都可能乱） | 在标准模板约束下具有**确定性输出**（克隆替换无状态；Word 自身渲染差异仍存在） |
| V2 扩展性 | 无（解析完即终点） | 有（用户自定义模板 / Word→标准模板转换 都接在入口） |

---

## 16. 结论

本方案与前一版「解析任意用户上传 Word 模板」相比，技术风险**显著降低**：
- 把 3 个致命复杂度（文本框家族识别 / 坐标去重 / 章节锚点识别）**整体移出了 V1.2.0 范围**，移到 V3 作为独立能力
- 用「克隆原型段 + 只改 w:t 文本」的确定性算法替代「坐标匹配 + 内容相同性」的概率性算法
- 章节定位改用命名样式（`title_style`），用户改标题文本不影响渲染
- 渲染层不再改数据，数据层不关心模板，符合 2.1 数据展示分离原则
- profile 数据严格来自 DB / request / AI 三层，**不引入模板兜底**避免数据污染，缺失直接报错
- LayoutOptimizer 只调段落级样式（字号/段距/行距/页边距），**不删条目**，与 §8.1 原则一致
- 模板 JSON 收敛到 4 个核心字段（section/style/placeholder/repeat），其余语法后置 V2，MVP 阶段不过度设计
- 在标准模板约束下具有**确定性输出**（输入相同 → 输出 docx 结构相同）；Word 自身因版本差异、字体缺失的渲染差异不属于方案可控范围
- 同时保留了未来升级到「用户自定义模板 / AI 模板理解」的接口：届时只需要把任意 Word 模板**转换成** `templates/xxx.docx + xxx.json` 入库即可，ResumeDocument、TemplateRenderer、LayoutOptimizer 三层完全不用改

**下一步**：用户确认方案后，按 §14 P0 清单（10 项）进入开发，完成后执行 §11 验收，验收结果记录在 [RESULT.md](./RESULT.md)。

---

## 17. 实施结果已迁移

本节原来是在开发完成后追加到技术方案中的“PDF 布局复刻实现附录”。为保持 PLAN 与 RESULT 分离，具体实测参数、46/46 布局核对、21/21 内容验收、最终文件改动和实际决策已迁移到：

- [V1.2.0 RESULT](./RESULT.md)
- [跨版本决策记录 D-011](../../DECISIONS.md#d-011-模板视觉参照改用用户-pdf)

重构前原文曾单独保存，现已由项目维护者清理；本 PLAN 与对应 RESULT 作为 V1.2.0 的保留记录。
