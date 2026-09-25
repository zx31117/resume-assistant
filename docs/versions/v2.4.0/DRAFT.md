# AI Career Resume Assistant V2.4.0 草稿：生成质量冻结与本地一页纸成品

> 文档角色：版本范围草稿，供 Product Owner 审核
> 状态：DRAFT，非开发指令，不改变当前版本状态
> 重写日期：2026-09-25
> 并行依赖：Day 1 先冻结 V2.3.0 的 Account/Auth、多用户隔离、PostgreSQL/pgvector、低敏 Career
> Memory、ApplicationCase、生成公共合同和埋点契约；实现与底座工作流并行，Day 6 完成真实集成
> 发布列车角色：V3.0.0 Release Train 的质量/本地装配工作流，不单独发布或独立验收
> 核心目标：在固定评测、受控多用户 Beta 和真实文件验收下，把 Job Model、召回、润色、内容预算、
> 固定模板与网页本地装配闭合为稳定的一页纸可投递成品；本版未通过，V3.0.0 不得首发

## 1. 版本判断

V2.4.0 是 V3.0.0 前最后一次允许系统性重塑生成内核的工作流。它不是只调整 Prompt，也不是只提高
Recall@K；它必须证明“选什么、怎么写、写多少、如何在本地补回真实身份/实体、怎样排成一页以及
最终文件是否可投”形成一个可复现闭环。

本工作流可以基于 Day 1 冻结合同和隔离夹具并行开发，但 Day 6 前必须接入真实 PostgreSQL、真实账号、
真实模型、香港服务器、桌面 Chromium 和批准 Word 环境；夹具通过不能替代 V3 最终完整纵切。

本版冻结：

~~~text
产品 Web 端粘贴 JD / 输入岗位信息
→ ApplicationCase
→ JobModelSnapshot
→ EvidenceSelection
→ ResumeContentPlan
→ ResumeRevision（服务器：无 Resume Identity / 真实实体名称）
→ LayoutPlan
→ 浏览器读取 Local Resume Identity / Local Entity Map
→ 单一固定模板与固定槽位
→ Local Preview / DOCX / PDF
~~~

Browser Assistant、招聘网站集成、字段填充和文件上传统一延后到 V3.0.0 之后的独立版本。本版不做
插件、站点 Adapter、DOM/iframe 验证或网站测试账号。

## 2. 用户结果

受控 Beta 用户应能够：

1. 在产品 Web 端粘贴 JD 或输入岗位信息，创建 ApplicationCase；
2. 看见系统区分 JD 明示、岗位先验和有来源的 Company Context；
3. 更早看到高置信结果，并在精排后获得冻结最终内容；
4. 对信息缺口选择回答、跳过、仅用于本次或确认写回 Career Memory；
5. 在当前设备录入或复用 Local Resume Identity 与 Local Entity Map；
6. 由浏览器本地生成一页 DOCX/PDF，姓名、联系方式和真实实体名称不离开设备；
7. 直接下载事实可信、岗位相关、专业排版且无需大段返工的成品。

若事实、一页或可读性无法同时满足，系统必须明确失败或请用户确认取舍，不能把两页、截断、隐藏
内容或极小字号文件标记为“可直接投递”。

## 3. Job Model v1

### 3.1 三层结构

~~~text
JobModelSnapshot
├── explicit_requirements     JD 明示
├── role_prior_requirements   岗位先验
└── company_context           公司/业务公开信息
~~~

| 来源 | 召回 | 排序 | 表达重点 | 可声称为招聘方硬要求 |
|---|---:|---:|---:|---:|
| JD 明示 | 是 | 是 | 是 | 是 |
| Role Prior | 是 | 是 | 是 | 否 |
| Company Context | 是 | 是 | 是 | 否 |
| 无来源模型推测 | 否 | 否 | 否 | 否 |

每条 Job Model 项保存来源类型、文本或 URL、采集时间、置信度、版本、适用范围和召回许可。联网材料
可能过期或错误，不能成为用户事实，也不能静默改变 JD 原文。

### 3.2 Role Profile 与 Company Context

- 首批 Role Profile 只覆盖 Product Owner 批准的高频岗位，包含同义词、能力维度、证据类型、
  召回词、边界、版本和审核状态；
- 无法识别岗位或 Profile 置信度不足时只使用 JD，不强套相近岗位；
- Company Context 只使用批准来源、缓存和 TTL，不建立无边界网络 Agent；
- 公司同名、部门或产品线不明确时显示不确定，不自动合并；
- Company Context 可补回文本相似度较低但业务相关的 Fact，只改变 emphasis，不改变 proposition；
- 来源失败、过期或冲突时退回 JD + Role Prior，并记录降级。

## 4. Person Model 与证据分层

### 4.1 Fact enrichment

确认 Fact 可生成 Embedding、fingerprint、能力/技能/行业/场景标签、关键词和通用摘要。所有派生数据
保存模型、Prompt、版本、来源和状态，可失效、可重建，不反向覆盖 Fact。

服务器 enrichment 只能消费批准的低敏 Career Memory，不得接收 Local Resume Identity、用户履历中
的真实公司/学校/客户/项目名称或它们的本地映射。

### 4.2 Stable / Adaptive Evidence

- `Stable Evidence`：多个相似岗位都成立、表达成熟且 Fact 未变化的基础内容；
- `Adaptive Evidence`：受当前 JD、Role Prior、Company Context 或用户补充影响，需要重选或重写。

缓存键至少覆盖 Fact revision/hash、Role Profile family、表达策略、Prompt 和模型版本。任何事实、
规则或版本不匹配都必须失效，不能为了速度复用旧文。

## 5. 召回质量冻结

候选信号可包括 JD 语义、Role Prior、Company Context、低敏技能/行业/场景、经历类型、时间、来源
质量、事实状态和用户明确偏好。opaque entity_ref 只能维持归属关系，真实实体名称不得进入召回、
排序、模型 Prompt 或质量评测。

固定评测集至少覆盖：

- short / typical / long Career Memory；
- 完整、宽泛、缺失关键信息、噪声和反例 JD；
- 多岗位、多行业、旧经历、弱相关和高文本相似但业务无关的 Fact；
- Company Context 能补召回的正例与不应补召回的负例；
- 双账号、未归属旧数据、身份/实体名称哨兵和跨账号负例。

正式 PLAN 冻结 Recall@K、Precision@K、nDCG 或等价指标，以及岗位要求覆盖、用户保留率、回退率、
延迟、Embedding 调用和成本阈值。跨账号召回、未知 Fact 和本地身份进入率始终为 0。

## 6. 润色与内容计划冻结

### 6.1 ResumeContentPlan

生成正文前形成版本化 ResumeContentPlan，至少包含：

- 章节及顺序；
- 每个章节的价值目标和字符/视觉行预算；
- 候选 Fact 的优先级、必要性和预期表达角度；
- 重复主题与合并关系；
- 可移除的最低优先级内容；
- 目标语言和表达风格；
- 为本地身份和真实实体名称固定槽位预留的空间预算。

系统承担事实边界内的专业选择，不要求用户先理解模板、页数、密度或逐条锁定。用户的自然语言意见
可以影响下一版计划，但不能绕过事实来源和一页纸门禁。

### 6.2 ResumeRevision

- 润色只使用冻结 EvidenceSelection；
- 每个内容条目保存稳定 ID、section、text、fact_refs、opaque entity_ref、来源 hash 和版本；
- 服务器文本不得包含姓名、联系方式、用户履历中的真实公司/学校/客户/项目名称；
- 改变重点不能改变事实命题；
- 不得用套话、空泛评价或无来源数字填补材料不足；
- 修改产生新 revision，不覆盖已经冻结的内容版本。

## 7. 方案 B：网页本地固定模板装配

### 7.1 三个数据域

~~~text
Account / Auth Identity
    认证与授权，不提供简历字段

Server Career Memory
    低敏 Experience / Fact / enrichment / entity_ref

Local-only
    Local Resume Identity
    Local Entity Map
    最终 Preview / DOCX / PDF
~~~

Auth 邮箱即使与简历联系邮箱相同，也不能自动复制。换设备后 Career Memory 可恢复，Local Resume
Identity 与 Local Entity Map 暂由用户重新输入。

### 7.2 单一模板与固定槽位

V3.0.0 前只冻结一套生产模板，首发以桌面 Chromium 为基准。模板版本化：

- 页面尺寸、页边距、字体和批准替代字体；
- 标题、正文、日期、地点、联系方式和实体名称层级；
- 全局字号、行距、段距、字距和 bullet 缩进；
- 关键词强调与 RichTextSpan；
- Local Resume Identity 固定槽位；
- 公司、学校、客户和项目真实名称固定槽位；
- 每个槽位的最大视觉行、宽度和失败规则；
- 最小可读性下限。

真实实体名称不能在正文中任意散落；服务器使用 entity_ref，浏览器只在模板定义的固定位置补回名称。
字段超长时由用户在本地提供简写，系统不得静默截断或把真实名称发送服务器求助。

### 7.3 本地装配流程

浏览器前端在用户设备上：

1. 从本地受控存储读取 Local Resume Identity 与 Local Entity Map；
2. 合并服务器返回的 ResumeRevision、LayoutPlan 和模板版本；
3. 生成本地 Preview、DOCX Blob 与 PDF Blob；
4. 对最终内容执行一页、溢出、空字段、槽位长度和可读性检查；
5. 只通过 Blob/Object URL 供用户预览和下载，不把最终字节回传服务器；
6. 清理临时内存和失效 Blob，不把正文写入日志、埋点或错误报告。

本地敏感存储不得使用明文 localStorage。正式 PLAN 必须冻结 IndexedDB/OPFS、WebCrypto、密钥生命周期、
清除、迁移、无痕模式和浏览器回收后的失败语义。页面禁止不必要第三方脚本，并以 CSP、依赖锁定、
出站白名单和负向网络探针证明本地字段未外发。

### 7.4 DOCX/PDF 同源的新定义

由于最终身份和真实实体名称不得发送服务器，V3.0.0 不再要求“最终 PDF 必须由包含真实身份的 DOCX
经服务端 Word 转换”。同源定义改为：

> Preview、DOCX 和 PDF 使用同一 JobModelSnapshot、EvidenceSelection、ResumeContentPlan、
> ResumeRevision、LayoutPlan、模板版本、Local Resume Identity revision 和 Local Entity Map revision。

PDF 使用固定字体资产和同一布局决策在本地生成；DOCX 使用同一内容和模板槽位生成。二者必须分别
通过内容、页数和视觉结构一致性检查，但允许记录由 Word 排版引擎造成的批准范围内差异。

### 7.5 Word 兼容与一页判定

字符数和预测宽度只作预约束。最终门禁包括：

- 浏览器本地 PDF 实际为一页；
- 本地 DOCX 在批准 Word 版本、字体和系统环境中实际为一页；
- V2.4.0 用合成身份、长短实体名称和边界长度建立 Word 兼容矩阵；
- 真实用户值只在本地参加运行时槽位/溢出检查，不进入服务端测试证据；
- 不承诺所有 Word、LibreOffice、操作系统和缺失字体环境像素级一致。

如果最终内容超页，先由本地检查计算不含原值的内容预算/溢出级别，再触发服务器对低敏正文执行受控
压缩；不得发送真实身份、真实实体名称或其原始长度明细。压缩顺序为：

1. 删除同义重复和空泛修饰；
2. 压缩超长 bullet，保留动作、方法、结果和事实边界；
3. 合并相邻重复表达；
4. 缩减低优先级 Fact 的表达；
5. 移除当前岗位价值最低且非必要的 Fact；
6. 在批准下限内调整全局段距、行距、字距和字号；
7. 重新本地装配并复测；
8. 仍不能通过时明确失败或请求用户确认取舍。

## 8. 信息缺口与事实回流

信息缺口使用 `PROPOSED → CONFIRMED / CURRENT_ONLY / REJECTED`：

1. 只在当前结果会显著改善时提问；
2. 说明原因并允许跳过；
3. 回答先服务当前 ApplicationCase；
4. 只有用户明确确认才能写回服务器 Career Memory；
5. 回流前移除 Resume Identity 和真实实体名称，只保留 entity_ref 与批准低敏描述；
6. 冲突、低置信和模型补全不覆盖旧 Fact；
7. Job Model 与模型推测永远不能写入 Person Model。

## 9. Fast Lane / Precision Lane 与性能

Fast Lane 先完成岗位识别、高置信候选和可复用 Stable Evidence；Precision Lane 完成扩展召回、
rerank、信息缺口和 Adaptive Evidence。最终文件只从冻结最终快照生成，中间结果不成为第二真源。

性能门禁使用真实服务器 P50/P95、cold/warm、缓存命中/未命中、模型调用、Token、成本，以及桌面
Chromium 的本地装配、预览、DOCX/PDF 生成和一页收敛时间。新增 Job Model 与本地检查不得无上限
串行叠加等待时间。

V3.0.0 后允许继续调优召回权重、top-k、阈值、Role/Company 内容、Prompt、模型、表达风格、内容
预算和批准范围内的全局版式参数；不得再重做事实真源、数据域、核心对象关系和本地装配合同。

## 10. 埋点与证据

本版记录但不保存用户正文、本地身份或真实实体名称：

- ApplicationCase、首结果、最终内容版本和下载漏斗；
- 召回规则、模型/Prompt/模板/LayoutPlan/本地装配器版本；
- Stable Evidence 命中、Adaptive Evidence 重算和缓存节省；
- 候选数、最终选择数、用户保留/重生成和反馈；
- 页数结果、超页原因类别、收敛动作和失败阶段；
- Token、成本、延迟、重试和资源；
- 测试/补贴行为与自然行为区分。

本地装配事件只上传枚举状态和脱敏计数；不得上传字段值、真实名称、文件字节、DOM、截图、完整错误
对象或可反推出身份的长度组合。

## 11. Release Train Day 1—6 质量/装配工作流候选

| 阶段 | 重点 | 退出条件 |
|---|---|---|
| Day 1—3 | 质量集、V2.3 基线、Job Model、混合召回、ResumeContentPlan 与润色 | 新旧路线可重复比较，隔离/事实边界不退化 |
| Day 3—5 | 固定模板、浏览器本地装配、超页收敛和合成边界矩阵 | 合成边界样本稳定生成本地一页 DOCX/PDF |
| Day 6 | 真实模型/服务器/桌面 Chromium/Word 完整纵切、人工盲评、性能与反证 | V3 集成候选可进入停止加功能阶段 |

时间不足时优先删除非核心增强，不减少质量集、本地隐私反证、Word 兼容、人工验收或反向用例。

## 12. 发布 Gate 候选

### 12.1 事实、相关性与隐私

- [ ] Role Prior/Company Context 不冒充 JD 明示要求或用户事实；
- [ ] 固定评测集证明召回相对 V2.3.0 基线达到批准阈值；
- [ ] 未知、无来源、过期和跨账号 Fact 进入最终结果为 0；
- [ ] Resume Identity、真实实体名称和原始简历文件进入服务器/模型/日志/埋点为 0；
- [ ] 润色盲评/真实偏好提升，重复、套话和事实越界不增加；
- [ ] 信息缺口未经确认不进入长期 Career Memory。

### 12.2 本地一页纸与文件

- [ ] 桌面 Chromium 本地 Preview、DOCX、PDF 均来自同一冻结输入和固定模板；
- [ ] 所有成功样本的本地 PDF 与批准 Word 环境 DOCX 均恰好一页；
- [ ] 一页不是通过静默删除必要事实、裁切、隐藏或突破字号/行距下限实现；
- [ ] 长短身份、实体名称、中英文混排、粗体、特殊字符和字体替代矩阵通过；
- [ ] 超长固定槽位明确失败或要求本地简写，不上传原值；
- [ ] 清缓存、无痕模式、存储拒绝、浏览器崩溃和新设备重录具有明确状态；
- [ ] 网络负向探针证明本地字段、映射和最终文件字节未外发；
- [ ] Product Owner 对代表性真实岗位完成人工验收并达到批准阈值。

### 12.3 性能与回归

- [ ] 真实服务器/模型/浏览器/Word 环境的 P50/P95、cold/warm 和成本不越过批准上限；
- [ ] V2.3.0 多用户隔离、备份恢复、埋点脱敏和关键不变量无回归；
- [ ] V2.2.0 渐进结果、任务连续性和事实来源能力无回归；产物路线变化按本版新合同验收。

这些 Gate 先作为合并阻断条件持续验证，并在 V3.0.0 候选统一独立验收；任一硬 Gate 未通过，V3.0.0
不得首发。

## 13. 正式 PLAN 前待冻结

1. 首批 Role Profile、Company Context 来源和 TTL；
2. 固定质量集及 Recall/Precision/人工盲评/延迟/成本阈值；
3. Fast/Precision 中间状态和最终替换 UI；
4. 单一生产模板、固定槽位、桌面 Chromium 版本和批准 Word/字体环境；
5. Local Resume Identity 与 Local Entity Map 字段白名单、revision 和本地重录流程；
6. IndexedDB/OPFS、WebCrypto、清除、迁移、无痕模式与存储失败语义；
7. DOCX/PDF 本地生成器、同源检查、允许的 Word 差异和超页最大收敛轮次；
8. Beta 用户规模、数据类型、退出条件和人工验收表；
9. V2.4.0 向 V3.0.0 交接的冻结基线、可调参数白名单和禁止大改合同；
10. 必要 Design Snapshot。

本文不单独授权开发；范围、阈值、模板、本地存储、参考环境和 Design Snapshot 由 V3.0.0 Release
Train PLAN 统一冻结。
