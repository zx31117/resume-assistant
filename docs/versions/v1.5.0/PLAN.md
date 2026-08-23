# V1.5.0 PLAN：事实级内容决策、两层选材与 SQLite 持久化收束

> 文档角色：V1.5.0 唯一已批准开发指令
> 当前状态：已批准执行；可以按本 PLAN 向开发 Agent 交接
> 计划日期：2026-08-22
> 批准日期：2026-08-23
> 最近修订：2026-08-23；用户已批准按收束后的范围开始执行
> 版本性质：V1 最后一轮核心架构收束；不以召回、措辞或排版质量提升作为 PASS 条件
> 产品发布基线：annotated tag `v1.4.2` 指向 `8aa56e7a497dfa2008192a9ad7320e5019de814f`
> 开发 Git 基线：执行起点是先获取并解析执行时最新的公开 `origin/main`，证明 `v1.4.2` 是其祖先，再创建 `version/v1.5.0` 与固定 current worktree
> 当前 planning checkout：只用于冻结批准文档，不是开发基线；不得在此启动源码开发，其中未提交的 V2/V3 草稿也不得被开发 Agent 当作 V1.5.0 指令

## 1. 版本定位

V1.4.2 已完成 V1 核心 JD → DOCX 链路、源码与 runtime 隔离、发布基线和开发档案收口。V1.5.0 只解决三个会让 V2 绑定旧契约的问题：

1. 现有链路没有严格区分“哪些经历进入简历”和“入选经历突出什么”，多个模块可能重复做内容决策；
2. SQL 只有较粗粒度 Experience，尚无可稳定引用、修改和判定过期的 Fact 与选材结果；
3. Chroma 与 numpy + JSON 两套向量持久化实现具有不同的增删改、重建和失败语义。

因此，本版本最终定位为“事实级内容决策、两层选材与 SQLite 持久化收束”。V1.5.0 建立正确的事实身份、选择顺序、来源追踪、失效语义和单一向量持久化实现；检索召回质量、表达质量、交互式素材补充、模型管理和前端体验留到 V2。

## 2. 目标链路

~~~text
完整职业履历 Experience / Fact（SQLite 事实源）
↓
① 经历层选择
   工作/实习：取最近 3 次，不足不补
   项目/论文：共享同一候选池，只从生成基准日前 3 年内
              按 JD 相关性取最多 2 项，不足不补
   若前两类入选合计 < 2：只补最匹配的 1 项校园经历
↓
CandidateExperienceSet（经历名单已经冻结）
↓
② 入选经历内的事实与表达侧重选择
   只从第一层入选经历中选择 fact_refs 与 expression_focus
↓
SelectedEvidenceSet（可序列化、可追溯、可判定过期）
↓
③ LLM 受约束改写
   输入语义：目标岗位 A + 入选经历 B/C/D
             + 各自应突出 E/F/G + 可使用事实
   只负责受约束改写，不得重选经历或写回事实库
↓
④ Builder 确定性装配
   章节、顺序、来源映射、容量告警
↓
ResumeDocument → TemplateRenderer → DOCX
~~~

第一层决定简历中有哪些经历；第二层只决定这些入选经历中的哪些已知事实值得表达以及表达侧重。LLM 不接收完整职业库后自行选材，也不能绕过第一层名单增加、替换或删除经历。

## 3. 强制边界

### 3.1 必须保持的 V1 事实规则

1. 公司、岗位、学校、项目、时间、指标和产物只能来自 SQL 中可回查的 Experience / Fact；
2. 姓名、电话、邮箱和所在地只取本次请求显式输入，缺失留空；
3. 求职意向只来自当前 JD 的岗位分析，职业事实库不保存求职意向；
4. V1 不生成或渲染个人总结 / 自我评价；
5. 模板和 Renderer 不选择、删除或改写业务内容；
6. 关键失败保持可见，不得用空成功、旧索引或第二后端静默兜底。

### 3.2 素材与验收边界

- V1.5.0 的真实素材仍只来自已有简历，可能只有现有 Experience 字段和粗粒度 bullets；
- 原简历没有的细节视为未知，不通过 LLM 追问、推断、补齐或编造；
- V1.5.0 不建设交互式细节补充，也不要求用户先提供真实、丰富、细粒度素材；
- 架构、迁移、失效和固定规则验收可以使用现有粗粒度材料的副本及完全虚构 fixture；
- 这些证据只能证明结构、边界和迁移正确，不能宣传为召回质量、内容质量或真实招聘效果验收；
- 交互式补充、用户确认新细节和基于丰富素材的质量评测统一留到 V2。

### 3.3 本版本不做

- 不调优相关性模型、权重、阈值、同分策略或措辞效果；固定槽位规则必须落地，但“选得是否理想”不是 V1.5 PASS 条件；
- 不用真实履历评估 Precision、Recall、Top-K 命中、不同 JD 的表达差异或招聘质量；
- 不实现 React 页面、个人履历库、编辑 UI、管理后台或浏览器 E2E；
- 不实现 Draft/Revision、跨修订 `content_item_id`、锁定、局部重生成、Artifact 历史或完整 Fact 修改历史；
- 不实现 DOCX 页面预览、PDF 转换、一页纸或视觉排版优化；
- 不实现长期归档、回收站和删除交互；
- 不新增豆包以外的模型，不建立统一 LLM / Embedding Provider，不增加多模型配置、API Provider 扩展、BYOK、能力探测、Token 用量或费用统计；这些统一属于 V2；
- 不进行 LangChain 重构，不引入 LangChain Retriever、VectorStore、Agent、LangGraph 或其他工作流框架；现有豆包调用与当前 LangChain 使用只按本版本必要的数据契约适配，不因推迟事项单独改动或删除；
- 不实现账号、权限隔离、服务器化、多用户或云端 Provider Gateway；
- 不保留 Chroma 或 numpy + JSON 作为隐藏保险后端。

## 4. 拟冻结的数据契约

以下是开发和审核必须保持的最小语义。开发 Agent 可以调整字段名，但必须在 RESULT 给出等价映射，不能改变边界。

### 4.1 Fact 与修改语义

Fact 是经历内部可表达的已知素材，不把所有简历字段强行拆成 Fact。首批范围只覆盖：

- 工作 / 实习经历中的职责、行动、方法、结果、指标和产物；
- 项目 / 论文中的工作内容、方法、产物和结果；
- 校园经历中的职责、行动和结果；校园 Fact 可以迁移和保存，但只有第一层补位规则触发时才能参与本次内容决策。

姓名与联系方式、教育背景、技能等继续使用现有确定性结构，不在本版本通过 LLM 扩写为细节事实。每个 Fact 至少具备：

| 字段/概念 | 作用 |
|---|---|
| `fact_id` | 稳定身份；内容修改后仍可识别为同一职业事实 |
| `experience_id` | 回到所属完整经历 |
| `fact_type` | 职责、行动、方法、结果、指标、产物等类型 |
| `text` | 当前规范化事实文本 |
| `source_text` / source locator | 回查原始输入，不允许只保留 AI 摘要 |
| `revision` / content hash | 判断同一 ID 的内容是否已经变化 |
| `source_hash` | 核对迁移来源是否变化 |
| `created_at` / `updated_at` | 变更与迁移核对 |

职业事实允许用户通过明确的服务层操作修改。修改必须更新正文、revision/hash 和时间戳，并使对应旧向量与引用旧 revision/hash 的 SelectedEvidenceSet 失效。LLM、选材或生成链路不得静默修改 Fact，也不得把生成文案写回事实库。V1.5.0 只实现服务层修改与失效语义，不实现编辑 UI 或完整历史版本库。

### 4.2 CandidateExperienceSet

第一层结果至少保存：

| 字段/概念 | 作用 |
|---|---|
| `generation_baseline_date` | 本次“三年内”规则使用的明确日期快照 |
| `rule_version` | 固定槽位规则版本 |
| `experience_id` | 入选经历身份 |
| `slot_type` / `slot_rank` | 工作/实习、项目/论文或校园槽位及顺序 |
| `selection_basis` | 时间、相关性或校园补位依据 |
| `excluded_ids` / warnings | 日期缺失、超出窗口、无素材等可解释结果 |

CandidateExperienceSet 形成后，后续阶段不得改变其中的经历名单。

### 4.3 SelectedEvidenceSet

第二层结果至少包含：

| 字段/概念 | 作用 |
|---|---|
| `selection_id` | 本次选材结果身份 |
| `jd_hash` | 形成结果时使用的 JD 快照 |
| `rule_version` | 经历层和事实层规则版本 |
| `generation_baseline_date` | 与第一层一致的生成基准日 |
| `experience_id` / `slot_type` / `slot_rank` | 只能引用第一层入选经历 |
| `fact_refs` | `fact_id + revision/hash`；只引用所属入选经历中的事实 |
| `selection_reason` | 事实与当前 JD 的关联依据 |
| `expression_focus` | 应突出什么，不是新增事实 |
| `scores` | 可解释分项；质量不作为 V1.5 PASS 条件 |
| `source_text` | 供核验和受约束改写使用 |

该对象必须可以序列化和重新核对。JD、Fact revision/hash、规则版本或生成基准日变化时，旧结果必须明确过期，不能继续冒充当前选材。

### 4.4 生成结果与 ResumeDocument

- LLM 只接收目标岗位、CandidateExperienceSet 中的入选经历、SelectedEvidenceSet 指定的表达侧重和可使用事实；
- 每条 bullet 必须返回 `fact_refs`；未知、未选、跨经历或版本不匹配的引用必须拒绝并告警；
- LLM 不得重选经历、加入未入选经历、生成新事实或写回 Fact；
- 材料不足时返回明确不足状态，不用通用空话补齐；
- Builder 只做确定性装配，不执行第二套 JD 相关性判断；
- 来源映射以结构化字段进入 ResumeDocument 或等价 sidecar，不能在 Builder / Renderer 前退化为只有文字的裸字符串；
- V1.5.0 不生成跨修订稳定的 `content_item_id`，该身份留到 V2 的 Draft/Revision 契约。

## 5. 固定选择规则

### 5.1 第一层：经历名单

1. 每次生成冻结一个 `generation_baseline_date`，所有三年窗口判断和结果快照使用同一日期；
2. 工作 / 实习按可核验时间倒序取最近 3 次，在职经历视为最新；不足 3 次不以其他类型填充，也不创建空白经历；
3. 项目 / 论文属于同一个候选池。只保留位于 `[生成基准日 - 3 个日历年, 生成基准日]` 的项目 / 论文，再按与当前 JD 的相关性取最多 2 项；不足 2 项不以更早项目、论文或其他类型填充；
4. 在进行中的项目视为截至生成基准日仍在窗口内；已结束项目使用可核验结束/发表日期。不能证明日期属于窗口的项目 / 论文不进入该槽位，并返回告警；
5. 工作 / 实习与项目 / 论文最终入选合计少于 2 项时，只补最匹配的 1 项校园经历；没有校园素材时保持缺失并告警，不生成虚构内容；
6. 具体日期字段映射、时间并列顺序和相关性同分规则由开发 Agent 根据现有 Schema 固化为确定性规则，在 RESULT 中记录并以 fixture 验证；这些实现细节不改变上述数量、时间窗口和补位边界。

### 5.2 第二层：事实与表达侧重

- 第二层只遍历第一层已经入选的经历；
- 每个结果只能引用该经历现有、版本匹配且有来源的 Fact；
- `selection_reason` 和 `expression_focus` 可以结合 JD，不能成为新事实；
- 传给 LLM 的语义必须等价于“目标岗位 A + 入选经历 B/C/D + 应突出 E/F/G + 可使用事实”；
- LLM 只负责受约束改写，不能改变经历名单或事实库；
- 现有粗粒度 bullet 可以作为一个较粗 Fact 参与流程。粒度粗不阻断架构验收，但不得据此声称事实召回或内容质量已经验收。

### 5.3 模块职责

| 模块/阶段 | V1.5.0 职责 | 禁止事项 |
|---|---|---|
| 经历层 Selector | 执行固定槽位规则，产出 CandidateExperienceSet | 不生成文案，不修改 Fact |
| 事实层 Selector | 只在入选经历中选择 fact_refs 和 expression_focus | 不改变经历名单，不写回事实 |
| LLM 改写 | 使用已选事实生成带来源的 bullets | 不重选经历，不补造事实，不写回 SQL |
| Builder | 章节、顺序、装配、来源映射和告警 | 不再做 JD 相关性选择 |
| Renderer | 展示 ResumeDocument | 不删除、截断或改写业务内容 |

## 6. SQLite 与迁移契约

### 6.1 Fact 迁移

采用确定性迁移，不在迁移中调用 LLM：

1. 将现有 Experience 中属于首批范围的非空细节字段和 bullets 按原文迁移为 Fact；
2. 每个 Fact 保留来源字段/位置、source text 和 source hash；
3. 旧描述无法安全拆细时保留为较粗 Fact，不猜测或补写；
4. 当前简历没有的细节保持缺失；
5. 重复迁移必须得到相同身份和数量，不重复创建 Fact；
6. 后续只有用户明确调用服务层修改能力时才更新 Fact，并触发派生数据失效。

### 6.2 SQLite 向量存储

新增等价于 `fact_embeddings` 的派生表：

- 以 `fact_id + embedding_fingerprint` 唯一定位；
- 保存 dimension、明确 dtype 的 BLOB vector bytes、Fact revision/hash、状态和更新时间；
- 查询时读取本次候选 Fact 的向量并执行内存精确相似度计算；
- numpy 只作为计算库保留，不承担 JSON 向量持久化或 fallback 后端角色；
- fingerprint、维度或 Fact revision/hash 不匹配时向量立即失效，完成重建前不得使用。

### 6.3 旧索引退出

不迁移 Chroma 或 numpy + JSON 中的旧向量字节，统一从 SQLite Fact 使用当前豆包 Embedding 调用重建：

1. 迁移前验证源数据库身份，并复制数据库与旧索引作为只读备份；
2. 升级 Schema，确定性生成/迁移 Fact；
3. 核对 Experience、Fact 数量、ID、来源 hash、失败项和孤儿记录；
4. 将新 Embedding 状态标记为 pending；
5. 有可用 Key 时执行重建；无 Key 时可以停在“事实迁移完成、索引待重建”，生成接口必须明确阻断；
6. 重建完成后核对数量、维度、fingerprint、失败项和可重试状态；
7. Chroma 与 numpy + JSON 退出活动配置、依赖、代码分支和测试契约；备份存在不等于活动 fallback；
8. 迁移中途失败后可以安全重试或回滚，且不得在未经核对时删除原 Experience、旧数据库或旧索引。

V1.5.0 必须建立正式 schema version 和顺序迁移记录。迁移脚本对成功、异常和提前退出路径都要释放 engine、client、文件句柄和临时资源；日志、测试产物和 RESULT 不记录真实履历正文、API Key 或本机用户名。用户数据只能在可恢复副本上演练，虚构 fixture 足以完成结构与失败路径验收。

## 7. 实施任务

| Task | 责任 | 内容 | 退出条件 |
|---|---|---|---|
| T0 基线与文档冻结 | 文档 Agent | 记录 2026-08-23 批准状态；获取执行时最新 `origin/main`，完成远端、祖先关系和 clean preflight，再创建固定 `version/v1.5.0` current worktree | branch、base commit、tag 祖先关系和 clean 状态明确 |
| T1 源码现状与契约映射 | 开发 Agent | 对照 PLAN 识别 Experience、索引、豆包调用、Builder、测试和配置入口；建立 RESULT 骨架 | 实际文件范围、旧路径和 PLAN 偏差已记录 |
| T2 Fact Schema 与迁移框架 | 开发 Agent | 只迁移首批 Fact 范围；建立可明确修改的 Fact、revision/来源、schema version、备份和幂等迁移 | 不扩写原简历；修改会使派生数据失效；副本与虚构 fixture 通过 |
| T3 SQLite Embedding 与索引任务 | 开发 Agent | 建立 BLOB 向量派生表、内存精确检索、fingerprint、失效与全量重建 | 增删改、失败、重试和重建一致；无隐藏 fallback |
| T4 两层选材与 SelectedEvidenceSet | 开发 Agent | 建立固定经历槽位、槽位内 Fact/侧重点选择、序列化结果和过期判断 | 固定数量/窗口/校园分支通过；第二层不能改名单 |
| T5 改写与 Builder 收缩 | 开发 Agent | 生成只使用 fact_refs；Builder 只装配并保留来源映射 | 越界输出被拒绝；LLM 不重选或写回；来源不丢失 |
| T6 旧向量实现退出 | 开发 Agent | 删除 Chroma、numpy + JSON 活动后端及其依赖、配置、分支和旧测试契约 | SQLite 新状态生效，旧状态退出，无并行向量真源 |
| T7 开发验证与候选 | 开发 Agent | 完成测试矩阵、迁移副本演练、RESULT 和 clean candidate commit | RESULT 满足最低交付契约；不得 push main/tag |
| T8 高性能源码/数据验收 | 高性能验收 Agent | 在 clean review worktree 独立审查迁移、事实边界、两层选材、失败路径、旧实现退出和核心回归 | 绑定精确 commit，阻断项为 0 |
| T9 人工核心流程验收 | 用户 | 使用允许的数据副本从导入/已有库走到 JD → DOCX，确认事实边界和流程可用 | 用户明确通过或给出返工项；不扩大为内容质量验收 |
| T10 文档与发布 | 文档 Agent | 汇总 RESULT，按实际结果更新 CURRENT_STATE、DECISIONS 和索引；用户确认后 fast-forward main 并创建 annotated tag `v1.5.0` | 远端 main/tag 核对一致；不 force push |

开发 Agent 不得把 T2–T6 拆成新的长期分项文档。阶段结论统一写入同一个 RESULT，机读产物进入临时目录或 runtime，不进入版本档案。

## 8. 开发验证矩阵

### 8.1 Fact、选择与改写

- 新旧 Experience 可以形成可回查 Fact；迁移不虚构、扩写或丢失来源；
- 服务层显式修改 Fact 后 revision/hash 更新，旧向量和旧 SelectedEvidenceSet 失效；LLM 与生成链路不能写回；
- 0、1、2、3、4 次工作/实习分别验证“最近最多 3 次、缺位不补”，并覆盖在职、同日和日期缺失；
- 项目/论文作为同一池验证三年边界日前后、正好三年、在进行中、日期缺失及 0/1/2/3 个候选；最终最多 2 项，不用更早内容补位；
- 前两类入选合计为 0、1、2 时分别验证校园条件分支；触发时最多 1 项，无校园素材时不生成虚构内容；
- 第二层与 LLM 只接收第一层入选经历；每条 bullet 只引用已选且版本匹配的 fact_refs；
- 未知、未选、跨经历、无来源、版本过期和材料不足路径保持可见；
- 更换 JD 或生成基准日不修改 Experience / Fact；Builder 和 Renderer 不重新做相关性选择。

### 8.2 SQLite 与迁移生命周期

- 全新空库初始化、V1.4.2 数据库副本迁移和同一迁移重复运行；
- Schema 部分创建、Fact 部分写入、Embedding 部分失败后的安全重试或回滚；
- 无 API Key 时事实迁移完成、索引明确 pending、生成显式阻断；
- Fact revision/hash、Embedding 维度或 fingerprint 改变后旧向量不可用；
- 备份、数量/hash 核对、孤儿检查及成功/异常/提前退出资源释放；
- 旧索引备份不被活动代码读取，活动 Chroma/numpy + JSON 路径为 0。

### 8.3 回归

- Profile 仍只取 request，缺失留空；求职意向仍只来自 JD；不生成个人总结；
- 当前豆包 LLM / Embedding 调用继续服务核心链路，不新增或切换其他模型；
- 旧 Markdown 和 internal 模板调试接口不成为新主链；
- 核心 JD → DOCX 正常路径与主要错误分支通过；
- Stub 测试继续使用独立临时 runtime，成功和失败路径均无残留；
- 应用版本、根 README 和运行入口最终按实际发布统一为 1.5.0。

### 8.4 证据解释

- 粗粒度真实材料副本用于证明可迁移、可追溯和不越界，不用于证明选材质量；
- 完全虚构 fixture 用于覆盖数量、时间窗口、校园分支、失效和失败路径，不用于声称真实召回效果；
- V1.5.0 不以 Precision、Recall、Top-K、不同 JD 的表达差异或人工招聘质量评分作为 PASS 条件；
- RESULT 必须分别给出功能验收与结构变更验收，并明确哪些质量验证未进入本版本。

## 9. 高性能验收要求

T8 必须读取源码并独立复核：

1. Experience → Fact 迁移、备份、幂等、失败重试和回滚；
2. SQL 事实源、Fact revision/hash、来源和显式修改边界；
3. SQLite BLOB 向量、内存精确检索、fingerprint、失效与重建；
4. Chroma 与 numpy + JSON 的活动代码、配置、依赖和测试契约是否真正退出；
5. 最近 3 次工作/实习、三年内共享池最多 2 项项目/论文及条件触发的 1 项校园经历是否只有一套实现；
6. 第二层和 LLM 是否只能使用第一层名单与已选 fact_refs，是否存在静默写回；
7. Builder 职责变化、来源映射和现有 V1 事实边界是否一致；
8. 迁移与测试工具在成功、异常和提前退出时的完整资源生命周期；
9. 现有豆包调用是否被误删，以及 V1.5 是否混入任何多模型/API Provider 或 LangChain/LangGraph 扩展。

验收 Agent 必须从本 PLAN 独立推导失败场景，不能只复跑开发 Agent 的命令。首次打回后，文档 Agent 应把症状上升为完整问题类别并一次性补齐返工矩阵。

## 10. PLAN 完成标准

只有以下条件全部满足，V1.5.0 才能标记已验收：

- 首批 Fact、CandidateExperienceSet、SelectedEvidenceSet 和数据库迁移契约实际落地；
- 两层选材实际落地，LLM 不能重选经历、使用越界事实或写回职业事实库；
- 用户显式修改 Fact 会更新 revision/hash，并使旧向量与旧 SelectedEvidenceSet 失效；
- SQL 是唯一事实源，SQLite BLOB 是唯一活动向量持久化实现，numpy 只用于计算；
- Chroma 与 numpy + JSON 活动路径退出，旧向量从 Fact 重建而不是迁移；
- 固定经历槽位、三年窗口、共享项目/论文池和校园补位规则的结构验证通过；
- 验收证据没有把粗粒度材料或虚构 fixture 宣传为召回/内容质量通过；
- 当前豆包主链与既有 V1.3.0–V1.4.2 事实边界、错误可见性、测试隔离和 DOCX 流程无回归；
- 功能验收与结构变更验收分别通过，高性能验收绑定精确候选 commit；
- RESULT 明确 API、数据模型、模块、配置/依赖的实际变化、验证证据和 PLAN 偏差；
- CURRENT_STATE、DECISIONS、版本索引和根 README 只按实际实现与发布结果同步；
- 用户单独确认正式发布。

## 11. 批准状态与执行起点

用户已确认内容决策、Fact 范围与修改语义、SQLite 向量方案、旧索引重建策略以及 V1.5/V2 模型边界，并于 2026-08-23 明确批准开始执行 V1.5.0。本 PLAN 自该日期起是 V1.5.0 唯一开发指令。

执行从 T0 开始：先获取执行时最新的公开 `origin/main`，记录精确 base commit，证明 `v1.4.2` 是其祖先并完成 clean preflight；随后才创建 `version/v1.5.0` 和固定 current worktree、向开发 Agent 交接。当前 planning checkout 不能沿用为开发基线，本文档批准也不等于任何 V1.5.0 源码已经实现或验收。

## 12. 文档 Agent 前置审核返工补充（2026-08-23）

> 性质：本节是对首次实现候选的返工契约，只追加、不覆盖或改写上文最初批准的 PLAN。
> 审核对象：`version/v1.5.0` 首次开发交接 HEAD `81357200fc6e58714d6b7ce3d6ad497a2775935c`；`0fe1513` 只是其 T6 前序提交，不是最终交接 HEAD。
> 当前结论：首次候选在进入 WorkBuddy 独立验收前被文档前置审核打回；开发侧 `215 pass / 0 fail` 只证明已执行断言，不等于候选可验收。
> 证据边界：以下文件与行为证据来自前置审核交接材料；Traework 负责修复和补齐开发自测，WorkBuddy 必须在新的 clean 候选上独立读取源码、推导失败场景并复核。

本轮不得拆成零散补丁或新增分项文档。所有返工仍写入本 PLAN 与同版本 RESULT；PLAN 规定接下来必须做什么，RESULT 只记录实际发生的修复、测试和验收状态。

### 12.1 集中返工顺序

| Task | 依赖 | 集中返工目标 | 完成条件 |
|---|---|---|---|
| R1 Experience/Fact 生命周期 | 无 | 统一新旧 Experience 的 Fact、Embedding、失效、失败与重试语义 | CRUD 后派生数据立即可核对；失败不产生假成功或孤儿 |
| R2 可操作升级与重建入口 | R1 | 为全新库、V1.4.2 升级库和 CRUD 后状态提供唯一受支持入口 | 正常用户不需要 import 私有 service 即可迁移、查状态、重试和重建 |
| R3 迁移与资源安全 | R2 | 数据库与旧索引备份、fail closed、完整资源释放 | 任一备份/核对/cleanup 失败均非零失败且不继续破坏性步骤 |
| R4 Fact 修改一致性 | R1 | Fact 更新与派生失效形成不可分割的一致性边界 | 不存在“新 Fact 已提交但旧 Embedding 仍 VALID” |
| R5 教育/校园语义与确定性排序 | R1 | 区分正式教育和校园活动；固定补位、排序及缺失日期规则 | 输入乱序不改变结果，校园改写真正进入最终文档 |
| R6 检索健康与故障可见性 | R3、R4 | 区分健康低相关与索引/模型故障 | 维度、fingerprint、revision/hash 故障阻断，不回退全部 Fact 掩盖 |
| R7 bullet 来源映射与最终链路 | R5、R6 | 保留每条最终 bullet 的 fact_refs 到响应、ResumeDocument/sidecar 和 DOCX 核对 | 逐 bullet 可追溯；越界引用失败；最终文档而非中间集合通过 |
| R8 旧实现退出与对外一致 | R2、R7 | 清理活动残留，分类兼容残留与历史档案 | 新状态、旧状态退出和回归三类证据齐全；不改写历史版本事实 |
| R9 集成验证与冻结交接 | R1–R8 | 汇总矩阵、形成 clean 新候选并外部交接 | RESULT 更新、全量测试通过、精确 HEAD 通过外部消息交接 |

依赖主线为 `R1 → (R2、R4、R5) → R3 → R6 → R7 → R8 → R9`。可以并行实现互不重叠的测试，但必须在 R9 一次性集成，不能修完单个症状就提前进入 WorkBuddy 验收。

### 12.2 R1：Experience CRUD 全生命周期

- **前置证据**：`backend/services/experience_service.py` 的 create/update/delete 只提交 Experience；新建不产生 Fact/Embedding，更新依赖“下次迁移”，但 `SchemaVersion` 已应用后该迁移会跳过；删除后的 FactEmbedding 清理、失败重试和重建语义没有闭环。
- **必须实现**：把 Experience 与其 Fact 派生/对账纳入同一服务层生命周期。create 立即生成确定性 Fact；update 对新增、修改、删除的来源项做 reconciliation，更新 revision/hash 并失效旧引用；delete 清理或明确失效 Fact、FactEmbedding 与引用，不留孤儿。SchemaVersion 只门控一次性 schema/data 升级，不得承担日常 CRUD 同步。
- **正向验收**：全新 Experience、V1.4.2 迁移 Experience 和迁移后新增 Experience 均能按 ID 回查 Fact；更新 description/achievements 的新增、改写、删除分别得到确定性 Fact 数量与 revision/hash；删除后 Fact/Embedding/选材引用均不可用；失败项可重试并可由全量重建收敛到同一结果。
- **反向验收与完成标准**：分别注入 Fact 写入、Embedding 计算、状态提交和删除清理失败，接口不得返回无条件成功，不得留下 VALID 旧向量或孤儿；重复 create/update/delete/retry/rebuild 幂等。只有新旧 Experience 的增删改、失效、失败、重试、重建行为一致才完成 R1。

### 12.3 R2：正常可操作入口

- **前置证据**：生成链路的 `_ensure_migrations_applied` 只检查 SchemaVersion 并提示显式迁移；API、根 README 与正常启动路径没有迁移、状态检查或 Embedding 重建入口，且错误文案不能代替可执行入口。
- **必须实现**：提供一个唯一受支持的本地维护入口（CLI 或本地管理 API，最终名称和参数在 RESULT 固化），统一完成迁移、状态诊断、失败重试和 Embedding 重建；根 README 在源码验收通过后的文档收口阶段只介绍这个入口，不要求用户 import 私有 service。
- **正向验收**：全新空库按正常快速开始可初始化并形成可生成状态；V1.4.2 数据库副本经同一入口备份、迁移和重建后可生成；CRUD 后 PENDING/INVALID/FAILED 可被同一入口诊断并恢复。
- **反向验收与完成标准**：缺 Key、升级未执行、备份失败、部分 FAILED 或维度错误时入口给出非零/领域错误与下一步，不得让生成继续或返回空结果。上述三类库均形成从准备数据到 JD → DOCX 的可重复闭环才完成 R2。

### 12.4 R3：迁移 fail closed 与资源生命周期

- **前置证据**：`backend/database/migrations.py` 忽略 `vectorstore_dir`；SQLite/旧索引备份异常只收集到 `errors` 后继续；`session.close()` / `engine.dispose()` 异常被 `pass` 吞掉，无法证明备份有效或资源已释放。
- **必须实现**：任何 schema/data 变更前同时备份源 SQLite 与旧索引；对备份做存在性、可读性、数量/hash 或等价完整性核对，并保存不含履历正文的 manifest。任一备份或核对失败必须 fail closed。成功、业务异常、依赖/导入失败、提前退出与 cleanup 失败都必须释放 session、engine、client、文件句柄和临时资源；cleanup 失败经有限重试仍失败时整体非零。
- **正向验收**：数据库与含嵌套文件的旧索引均产生可读取、可恢复、与源匹配的只读副本；迁移成功后 SchemaVersion、Fact 数量/hash、孤儿与 Embedding 状态核对通过；重复迁移/提前退出均不破坏原副本。
- **反向验收与完成标准**：注入 copy2/copytree、备份校验、session.close、engine.dispose、文件占用和 cleanup 失败，断言后续 schema/data 步骤没有继续、退出非零、错误可见且相邻哨兵不变。仅打印 warning 或把错误放进 summary 不算完成。

### 12.5 R4：Fact 修改与失效一致性

- **前置证据**：`fact_service.modify_fact` 先 commit Fact 再执行钩子；钩子异常降级为 warning；`embedding_service.wire_fact_invalidation` 同样吞掉异常，且活动入口未证明必然完成注册，可能留下“Fact 已更新、旧 Embedding 仍 VALID”。
- **必须实现**：用同事务失效、持久化 outbox/任务状态或等价可恢复机制，把 Fact revision/hash 更新与旧派生数据失效组成一个可证明的一致性边界；失效失败不得被 warning 消化。生产路径不得依赖可选的进程内钩子碰巧已注册。
- **正向验收**：修改 Fact 后，同一可观察完成点上旧 Embedding 不再 VALID，旧 SelectedEvidenceSet 判定过期，重建后只有新 revision/hash 可查询；未改变正文时不误增 revision。
- **反向验收与完成标准**：注入失效写入、任务落盘、commit 和重试失败，修改要么整体回滚，要么进入明确阻断且可重试状态；任何查询都不能继续使用旧向量。不存在 warning-only 不一致窗口才完成 R4。

### 12.6 R5：正式教育、校园补位与稳定排序

- **前置证据**：`selection_service` 把 `education` 与 `campus` 放入同一校园池，并按时间选最近项；`resume_builder.build_v15` 又装配所有未入选 education，校园槽位只写原 description，忽略受约束 bullets/fact_refs。工作同日期、项目相关性与时间同分没有最终 tie-break；缺日期工作仍进入槽位，但 warning 声称已排除。
- **必须实现**：正式教育背景保持确定性结构并独立于校园活动；校园活动只在工作+项目入选合计 `<2` 时，从校园活动中按 JD 相关性补最匹配 1 项。为旧数据给出不混淆的兼容映射。校园入选后的受约束 bullets 与逐 bullet 来源必须进入最终 ResumeDocument/等价 sidecar，并在 DOCX 中可见；未触发时不得把校园活动作为正式教育旁路装配。
- **排序规则**：工作/实习按可核验日期倒序，缺失/不可解析日期排除并给出一致告警；项目按相关性、时间依次排序；工作同日期、项目相关性与时间均同分时使用固定最终键（例如 `experience_id` 升序，具体等价键在 RESULT 固化）。校园按 JD 相关性、时间、固定最终键排序，而不是只取最近。
- **正反向验收与完成标准**：覆盖 0/1/2 合计触发边界、正式教育与校园同时存在、多个校园相关性差异、校园不足材料、缺失日期、同日期/同分及输入多次乱序；每次 CandidateSet、ResumeDocument、响应和 DOCX 集合/顺序一致。正式教育永远按确定性结构保留，校园只有条件触发且最匹配项可见，才完成 R5。

### 12.7 R6：检索健康与零命中故障可见性

- **前置证据**：`ensure_ready` 只凭 fingerprint/status 判 VALID，不验证查询维度与 Fact revision/hash；`query_facts` 遇维度或 BLOB 不匹配会返回零命中；`select_evidence` 再把零命中回退为全部 Fact，掩盖索引或模型错误。
- **必须实现**：查询前/查询时统一验证当前 fingerprint、query/vector 维度、dtype/BLOB 长度、Fact revision/hash 和状态；健康检查失败抛明确领域错误并阻断。健康索引上的真实低相关/零分必须与技术故障使用不同结果类型；只有 PLAN 已批准且 RESULT 明确记录的“索引健康但相关性低”策略才允许使用全部已知 Fact，不得共用故障回退分支。
- **正向验收**：健康索引对高相关与真实低相关分别产生可解释结果；获准的低相关策略只在健康标记为真时触发，并保留来源。
- **反向验收与完成标准**：分别构造 query 维度、存储维度、dtype/BLOB、fingerprint、revision/hash 不匹配及损坏行，全部必须阻断选材和 DOCX，且不得变成“全部 Fact”或空成功。故障与业务低相关可由响应/日志/测试明确区分才完成 R6。

### 12.8 R7：逐 bullet 来源与最终产物闭环

- **前置证据**：`GeneratedBullet` 有 bullet 级 fact_refs，但 `build_v15` 压缩为 Work/Project 经历级集合；raw build_meta 虽有嵌套映射，`BuildMeta` schema 未声明相关字段，`model_validate` 后响应丢失；校园分支不保存改写 bullet 或映射。现有测试主要验证 CandidateSet/EvidenceSet 或 WorkItem 经历级集合，未证明最终响应、ResumeDocument 和 DOCX。
- **必须实现**：每条最终 bullet 保留自身 fact_refs 与稳定顺序，使用 ResumeDocument 的结构化 bullet 或强类型 sidecar；`BuildMeta`/响应 schema 必须显式声明并通过序列化往返。Builder、Renderer 与校园分支不得合并、错位或丢失映射。未知、未选、跨经历、版本过期或空 fact_refs 的非不足 bullet 必须使生成失败，不得只过滤后 warning 继续出 DOCX。
- **正向验收**：从合法 LLM 结构化输出，经 Builder、`BuildMeta.model_validate`、API response 序列化、Renderer 到保存并重新读取 DOCX，逐条核对最终 bullet 文本、顺序、experience_id 与 fact_refs；work、project、campus 均覆盖。
- **反向验收与完成标准**：注入越界/跨经历/旧 revision/hash/未知/空引用和 Builder/Renderer 丢条目，断言领域错误、无 DOCX 成功响应；仅 `CandidateExperienceSet`、`SelectedEvidenceSet` 或经历级 `fact_refs` 通过不能完成 R7。

### 12.9 R8：旧实现退出与对外一致

- **前置证据**：根 README、`backend/.env.example`、`backend/run_stub_demo.py` 及部分旧验证入口仍含 Chroma、`CHROMA_PATH`、RAG/fallback 或旧 Builder 语义；现有 legacy-exit 自测未覆盖所有对外入口。
- **必须实现**：全仓库分类处理三类命中：活动残留必须替换；必要兼容残留必须有明确 guard、不能被正常入口调用；历史 PLAN/RESULT 只保留当时事实，不反向改写。Traework 修正代码、配置样例、脚本和活动测试；根 README 与全局文档由文档 Agent 在 WorkBuddy 通过后按实际结果统一，不提前把 V1.5 能力写入 CURRENT_STATE。
- **正向验收**：SQLite BLOB、唯一维护入口和 V1.5 Stub/正常链路均生效；`.env.example`、运行帮助和活动脚本只描述实际配置与调用链。
- **反向验收与完成标准**：静态扫描 Chroma、CHROMA_PATH、numpy fallback、旧 RAG/Builder 入口，并对每个命中给出“活动/兼容/历史”分类；正常导入和运行不能触达旧实现，V1.3–V1.4.2 历史档案仍保留当时事实，核心回归通过。

### 12.10 R9：开发测试矩阵、冻结与外部交接

| 测试组 | 开发侧必须新增或重跑的最小矩阵 |
|---|---|
| 生命周期 | 新库/升级库/迁移后 CRUD；Fact 新增、修改、删除；Embedding PENDING/VALID/INVALID/FAILED；失败、重试、重建、幂等、无孤儿 |
| 迁移与入口 | DB+旧索引备份成功；copy/verify/close/dispose/cleanup 注入失败；提前退出；同一正常入口覆盖初始化、升级、状态、重试与重建 |
| 选材与排序 | 正式教育+校园并存；合计 0/1/2；多校园 JD 匹配；工作/项目缺日期、同日期、同相关性/同时间；多组输入乱序结果相同 |
| 检索健康 | 健康高/低相关；query/row 维度、dtype/BLOB、fingerprint、revision/hash、状态和损坏行；故障不得回退全部 Fact |
| 来源与最终链路 | work/project/campus 合法逐 bullet 映射；所有越界/过期/空引用失败；ResumeDocument/sidecar、Pydantic response、DOCX 文本与顺序端到端一致 |
| 替换与回归 | 活动残留为 0；兼容 guard 不可达；历史档案未改写；Profile/JD/无 summary、Renderer 不裁剪、测试/runtime 隔离和 JD → DOCX 正常/错误路径 |

Traework 完成 R1–R8 后必须：

1. 在同一 `version/v1.5.0` 分支更新 RESULT，逐项写实际变化、偏差、测试命令与结果；不得把本补充标为已验收，也不得更新 CURRENT_STATE。
2. 形成 clean 候选 commit。RESULT 不回填该 commit 自身 SHA；由开发 Agent 在仓库外的交接消息中提供完整 40 位 HEAD、基线 commit、分支、clean `git status` 和测试汇总，避免自引用循环。
3. 明确 `81357200fc6e58714d6b7ce3d6ad497a2775935c` 是被打回的首次候选，新外部交接 HEAD 才是 WorkBuddy 的唯一审核对象；任何相关修改都会使旧验收失效。
4. 不 push `main`、不创建或移动 tag。WorkBuddy 在 clean review worktree 独立完成源码、失败路径、最终 ResumeDocument/响应/DOCX 与旧实现退出验收，并把绑定精确 commit 的结论交回文档 Agent汇总。

### 12.11 本轮返工完成标准

R1–R9、上文原 T8/T9/T10 仍是串行门禁：开发自测通过后才进入 WorkBuddy，WorkBuddy 阻断项为 0 后才进入人工核心流程验收，人工通过后文档 Agent 才能同步 CURRENT_STATE、根 README、决策与版本索引。`215 pass / 0 fail` 不得继续作为首次候选可验收的替代结论；任何一个生命周期、故障可见性、来源映射或最终 DOCX 闭环未完成，RESULT 状态都必须保持“前置审核打回，待开发返工”。

## 13. WorkBuddy 首轮独立验收返工澄清（2026-08-23）

> 性质：本节只收束 WorkBuddy 对返工候选 `ec872f0f569bdb96c7dad3b5cb9653c45bc42756` 的首轮独立验收阻断项，不改变 §12 的问题类别、边界或完成标准。
> 验收结论：WorkBuddy 已完成 T8 首轮独立验收，但 R1、R2、R5 仍有 3 个阻断项；R3、R4、R6、R7、R8 已在该 commit 上通过。任何相关源码修改后，受影响的旧结论自动失效。

### 13.1 本轮只做三项定向返工

| Task | 对应原契约 | 必须修正 | 完成标准 |
|---|---|---|---|
| W1 CRUD 事务边界 | §12 R1 | create/update 的 Experience 写入与 Fact reconciliation 使用同一事务完成；reconciliation 失败不得先提交 Experience | create 失败后 Experience/Fact 均不存在；update 失败后 Experience、Fact、Embedding 均保持旧一致状态 |
| W2 缺日期工作规则 | §12 R5 | 按已批准规则排除缺失或不可解析日期的工作/实习，并返回与行为一致的告警 | 缺日期项不进入 work 槽位；正常日期排序和最终稳定键无回归；输入乱序结果一致 |
| W3 全新库维护入口 | §12 R2 | `manage.py migrate` 对不存在的 SQLite 文件明确按“全新空库”初始化；只有已存在的升级源才要求迁移前备份 | 不先启动 FastAPI 也能从不存在的库路径完成 migrate/status；重复执行幂等；不可读或损坏的既有源仍 fail closed |

W1、W2、W3 可以并行实现，随后统一执行 W4 集成复验。不得借 W3 放宽升级库备份：不存在的目标是“新建空库”，已存在的 V1.4.2 数据库仍必须先通过 §12 R3 的备份与核对门禁。

### 13.2 强制正反向复验

1. **W1 正向**：create/update 正常路径分别核对 Experience、Fact、revision/hash 与 Embedding 状态；delete、retry、rebuild 原通过项重跑无回归。
2. **W1 反向**：在 create/update 的 Fact 派生、reconciliation、Embedding 失效和 commit 前分别注入异常；create 后数据库保持无新增，update 后所有旧值与旧有效派生保持一致，不得出现孤儿 Experience 或“新 Experience + 旧 Fact/Embedding”。
3. **W2 正反向**：覆盖空日期、不可解析日期、同日期、在职、0/1/2/3/4 次工作及至少 5 组输入乱序；缺日期/不可解析项必须出现在 excluded/warnings 且不在 slots，其他确定性顺序不变。
4. **W3 正向**：临时目录中 SQLite 文件不存在时，唯一维护入口完成建库、SchemaVersion、Fact/Embedding 初始状态与 status 指引；第二次 migrate 幂等。
5. **W3 反向**：既有路径为目录、不可读文件、损坏 SQLite、升级库备份失败和 cleanup 失败时非零退出，不得把异常既有源误判为新库或继续迁移。
6. **W4 回归**：重跑开发矩阵及 WorkBuddy 首轮通过项中所有受 W1–W3 影响的测试；R3/R4/R6/R7/R8 若相关文件或行为被修改，必须重新独立验收，不能沿用 `ec872f0f...` 的通过结论。

### 13.3 新候选与再次交接

- Traework 在同一 `version/v1.5.0` 分支更新 RESULT，追加 W1–W4 的实际修改、失败注入和测试结果，保留 §9 的首轮 WorkBuddy 失败记录。
- 形成 clean 新候选；RESULT 不回填该提交自身 SHA。完整 40 位 HEAD、基线、分支、clean 状态和测试汇总仍通过仓库外消息交接。
- WorkBuddy 只对新 HEAD 复验并把第二轮结论追加到同一 RESULT。阻断项为 0 前，不进入人工验收，不更新 CURRENT_STATE、根 README 或版本索引，不 push `main`，不创建或移动 tag。
