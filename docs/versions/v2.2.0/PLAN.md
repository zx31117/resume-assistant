# ResumeAssistant V2.2.0 PLAN

> Plan Revision：3（待 Product Owner 批准）
> Supersedes：Revision 2（批准 PLAN blob `e134703ce6e37a2f4d5df389662119f38638fae8`）
> 状态：`PLAN_REVISION_REQUIRED`；本文获批前不授权开发
> 日期：2026-09-23
> 产品实现基线：H6-HANDOFF `81bf8c27583675133f9ac3e2ec3efd623fe31131`
> 产品源码基线：H2-SRC `bfcab15c172804fc32b9a11761be7da5077eba20`；H3～H6 未修改产品源码或入包对象
> 失效冻结包：`<acceptance-staging>/53fbc6f`，4045 files / 170,356,115 B，EXE SHA-256 `133A1394189BF008AFEFCCADD5B27F626AB49CA1E6A9BD4F2DE15255F6486B12`
> 开发路径：`<current-workspace>` 的 `version/v2.2.0`
> 本 Revision 范围：当前用户 Career Memory 归属、内容完整性、发布门禁、runtime 隔离及两项前端体验收口
> Design Baseline：源 `D-003` → canonical `DS-003`；本 Revision 不修改冻结视觉基线
> Revision 3 批准 commit/blob：待 Product Owner 批准后登记

## Required Reading（Development Agent 必读）

按顺序读取并在 RESULT 身份区逐项确认；缺一项不得开始：

1. `docs/README.md` §0～§7；
2. `docs/CURRENT_STATE.md`；
3. 本 PLAN 全文；
4. `docs/HUMAN_AI_WORKFLOW.md` §3.1～§3.4、§6、§8.1～§8.8、§11；
5. `docs/versions/v2.2.0/RESULT.md` 的 `R3-*` 当前结论；
6. `docs/design/baselines/V2.2.0/DS-003/SNAPSHOT.md`、`SPEC.md`、`prototype/README.md` 和 `prototype/index.html`；
7. 与本 PLAN 任务直接相关的产品源码和测试。

不要求开发默认读取完整 HISTORY、全部旧 RESULT 或私有审计长报告。本 PLAN 已把当前执行所需范围、
技术路线和 Gate 收口为唯一合同；历史事件只在需要核对身份或事故来源时定向读取。

## 0. 合同性质与停止条件

Revision 3 在获批后取代 Revision 2，成为 V2.2.0 唯一可执行合同。Revision 2 完成的 Task/SSE、四阶段
渐进生成、Word/PDF、Design Fidelity、性能和 package audit 实现作为返工基线保留，但绑定旧候选的
`ACCEPTANCE_PASS` 不覆盖本 Revision，也不能证明内容归属正确。

本 Revision 不是 V2.3.0 的账号/服务器化多用户建设。它只为现有本地单用户产品建立不可绕过的“当前
本地用户”归属，使工作台、履历库、任务、记录和 artifact 使用同一个服务端身份。不得新增登录、账号
注册、PostgreSQL、云存储或客户端可指定的任意 `user_id`。

仍由单一 Development Integrator 修改产品源码。测试、构建和只读分析可以并行，但不得由多个开发角色
并行修改同一产品链。开发前必须完成 Pre-mortem；首次真实 V2.2 Task 纵切后必须执行 Architecture
Check；冻结前必须执行 Falsification Check。

出现以下任一情况立即登记 `CHALLENGE_OPEN` 并暂停候选冻结：

- 任务归属仍依赖前端传入或全表查询；
- 只能依靠清理真实 runtime 才能生成正确内容；
- 教育、联系方式或其他源中非空字段仍会被 Renderer 静默丢弃；
- 必须继续让结构性 warning 通过才能得到 `SUCCEEDED`；
- 测试只能走旧 `/api/resume/generate-docx`，无法证明 V2.2 `/api/task` 主链；
- 修复要求自动删除无法确认归属的用户数据或 artifact。

## 1. 已冻结事实与返工基线

### 1.1 仍须保持的能力

- `DS-003` 主题 A、四步连续工作台、P1～P4 回看、失败态、二级页面和七视口布局；
- `task_id + input_revision + seq` 单一任务状态链、SSE 恢复、取消 fence 和失败范围续试；
- Experience 最大并发 2，同一 Experience 内 Fact 串行，正常逻辑调用 `1 + 2F`，单任务 completion ≤16k；
- ResumeDocument → DOCX → Microsoft Word COM → PDF → PDF.js/viewer/download 单一产物链；
- 首个完整 Fact ≤15 秒及既有六格性能目标；
- H6 package audit 已验证的路径词法、URI 区分、fail-closed 与脱敏能力。

### 1.2 已确认的发布阻断

Product Owner 在最终包真实操作中确认：生成结果没有使用当前履历库，而使用了真实 runtime 中遗留的
测试身份数据；当前履历库的教育、工作和项目未进入成品。独立源码根因审计进一步确认：Task 没有用户
归属、默认 selector 全表查询、education 未进入任务装配、assembler 只按 ID 回查且不验归属、结构性
warning 不阻断发布。该问题单独构成 P0，旧候选不可发布。

同一次实际生成还确认：所在地为空时电话和邮箱整行消失；等价经历重复进入槽位；来源非空的 role/
degree 等字段未完整进入标题行；空照片框和大量无信息留白进入成品。前端另有品牌区不能返回工作台、
步骤 1 在常见桌面视口出现短行程无意义内滚动的问题。

### 1.3 runtime 与数据边界

- 冻结包不包含 fixture、stub 数据或预置数据库；污染来自历史测试/演示脚本曾写入默认真实 runtime；
- 修复必须在“其他身份和测试数据仍存在”的隔离复制环境中保持正确，不能把删库作为正确性前提；
- 开发、测试和验收不得修改真实用户 runtime；需要验证污染形态时只使用只读查询或脱敏副本；
- 不自动删除真实 runtime 中任何 Experience、Fact、Task 或 artifact。数据处置必须先生成只读报告、备份
  方案和精确删除范围，另由 Product Owner 明确授权。

## 2. 最终用户结果

### V220-R3-G01 当前履历库是唯一选材范围

- 当前本地用户身份由服务端可信配置产生，客户端请求不得指定或覆盖；
- `DEFAULT_USER_ID` 必须对应唯一有效的本地身份记录；既有 Experience 与该身份的引用一致，不能继续
  依赖关闭外键或“有数据、无身份行”的悬空状态；
- 新 Task 必须绑定该身份；P2 候选、Fact、P3 输出、P4 条目、记录和 artifact 全部继承同一归属；
- 任一候选 ID、Fact 或 artifact 无法证明属于当前 Task owner 时立即失败，不允许过滤后继续“部分成功”；
- 在数据库同时存在当前用户、其他用户和 `stub-user` 数据时，成品只能出现当前用户的内容。

### V220-R3-G02 教育、联系方式和标题字段完整

- 正式教育不参与 JD 相关性竞争，按当前用户确定性装配；最多 3 条，使用稳定时间排序；
- 姓名、电话、邮箱、所在地仍只来自当前冻结输入；phone/email/location 的 8 种空值组合均逐字段处理，
  非空字段必须保留，只有三者全空时才删除联系方式整行；不得留下空标签或孤立分隔符；
- work/project/education 源中非空的 company/name/role/school/major/degree/time 必须进入 ResumeDocument 和
  模板对应字段；缺失可以诚实留空，但不得由 Builder 硬编码清空已有数据；
- V2.2.0 没有照片输入，因此最终模板不得显示空白照片占位框；summary/awards 为空可以不展示。

### V220-R3-G03 内容级去重

- 同一用户下完全等价的 Experience 使用确定性内容键识别；创建完全重复内容返回稳定
  `DUPLICATE_EXPERIENCE`（或等价明确结果），不得再次写入 Fact/Embedding；
- 既有重复记录不自动删除，但选材层必须按同一内容键去重后再执行 3 个 work / 2 个 project 槽位；
- 不做模糊语义合并；公司、角色、时间或正文存在实质差异时仍视为独立经历。

### V220-R3-G04 结构错误不能发布为成功

- P4 在发布前执行归属、来源完整性、必需章节、未替换占位符、原型文字和 artifact 可读性校验；
- `owner mismatch`、当前用户有教育但成品缺教育、冻结输入非空联系方式丢失、源中非空标题字段丢失、
  模板原型泄漏、DOCX/PDF 内容来源不一致均为结构性错误，任务进入 `FAILED` 且不发布 artifact；
- awards/summary 无内容、anchor 诚实不可用等允许状态必须使用明确非阻断代码，不能与结构错误共用模糊
  warning 文本；“任一字段为空”不得写成“全部为空”；
- 成功终态和 artifact 引用必须由一个原子 finalize 边界提交，不允许先置 `SUCCEEDED` 再补发布引用。

### V220-R3-G05 记录、CRUD、续试和下载归属一致

- Experience/Fact 的读取、更新和删除都校验当前本地用户；知道其他 ID 也不能查看、修改或删除；
- “我的简历”只列当前用户已发布任务；未绑定 owner 的历史任务从用户列表隔离，不自动删除文件；
- 失败范围续试继承源 Task owner，不能复用其他 owner 的 subtask、Fact 或 snapshot；
- 用户 artifact 使用 task-scoped 下载并校验 owner；通用模板调试下载不得继续承担用户简历下载入口。
- Task/artifact 容量清理按 owner 和明确 retention 处理；当前用户清理不能删除其他 owner 或
  `LEGACY_UNOWNED` 对象，后者只进入单独的维护报告/策略。

### V220-R3-G06 runtime 与测试隔离

- 所有测试、demo、验证脚本在导入产品配置前建立独立 `RESUME_DATA_DIR`；不得 `pop` 用户现有覆盖后回退
  默认 runtime；初始化、import、异常和 cleanup 失败路径都必须证明真实 runtime 未变化；
- 会写 Experience/Fact/Task/artifact 的测试或 demo 在隔离目录缺失、等于默认 runtime 或无法确认时必须
  拒绝启动，不能靠调用者记得传参；
- 提供只读 runtime ownership audit，报告 owner 计数、无归属 Task、已知测试身份及受影响记录，不输出
  正文、直接身份或本机绝对路径；
- 如提供清理工具，必须默认 dry-run、先备份、只接受精确 owner/ID 清单并要求显式确认；不纳入自动启动、
  迁移或测试流程。

### V220-R3-G07 两项前端体验收口

- WorkbenchShell 与 AppShell 的完整品牌区域可点击并可键盘触发，返回工作台根路由；具备可见焦点、
  `aria-label` 和足够热区，不创建新任务、不清空当前 Task、不新增模型调用；
- 1686×1076 的步骤 1 回看态使用约 800 字 JD 时，主内容区不得出现只有少量位移的独立滚动条；通过
  自适应高度、响应式密度或页面级空间分配吸收内容，不能用 `overflow:hidden` 截断；冻结小视口与真实
  长内容仍须完整可达并允许必要的内部滚动；
- 下载区不得保留空的 hash 标签/占位元素；有可验证 hash 时展示真实值，无值时整个元素退出布局。

## 3. 冻结技术路线

### 3.1 本地 owner 契约

服务端建立单一 `LocalOwnerContext`（名称可由开发决定），其值来自受信配置 `DEFAULT_USER_ID`，不来自
请求体。`Task` 新增 `user_id` 作为 owner 字段；所有新 Task 在服务层和持久化层都必须非空，InputRevision、Subtask、
Snapshot、Event、ResumeRevision 和 artifact 通过 Task 归属关联。迁移前既有 Task 保持空 owner 并标记为
`LEGACY_UNOWNED` 隔离态，不能盲目回填为当前用户或出现在“我的简历”；除迁移读取外，空 owner 不得
由任何新写入路径产生。

迁移在干净数据库显式创建默认本地身份；在既有数据库中，若 `DEFAULT_USER_ID` 已有 Experience 但身份
表缺行，只补同 ID 的最小身份行，不改写 Experience owner、不合并其他身份、不复制正文。`task_id` 与
`user_id` 必须作为不同参数和语义贯穿调用链；artifact 文件名可以使用 task ID，但不能把 task ID 冒充
用户身份。

Experience/Fact 继续是 Career Memory 唯一事实源。所有查询以 owner 为第一过滤条件，再按 ID、时间、
相关性或 revision/hash 处理。向量候选也必须先限定当前 owner 的 Experience/Fact ID 集合。
旧 `/api/resume/generate-docx` 如继续保留，只能复用同一个 owner-scoped 选材/装配服务；其请求中的
`user_id` 必须拒绝或忽略并使用 `LocalOwnerContext`，不得保留第二套全表 selector，也不得让兼容入口
绕过 Task 主链新增的归属和结构校验。

### 3.2 选材与装配

```text
LocalOwnerContext
→ current-owner Experience/Fact set
→ exact-content dedup
→ work/project 固定槽位 + deterministic education
→ Generated Fact（fact_refs 必须属于当前 owner）
→ ResumeDocument（逐字段来源守恒）
→ structural validation
→ DOCX → Word PDF → atomic success publish
```

P2 不对 education 调模型，调用公式保持不变。Builder 不重新做 JD 相关性选择；Renderer 不选择、删除或
补写业务事实。输出条目必须携带可追溯的 Experience/Fact 引用，供成品内容门禁核对。

精确重复键由 Experience 类型及全部用户来源业务字段组成；只统一首尾空白、换行和等价空值，不包含
ID、创建/更新时间、Fact、Embedding 或模型派生字段。教育稳定顺序为结束时间降序、开始时间降序、ID
升序，缺失日期置后；同一输入重复运行必须得到相同最多 3 条结果。

### 3.3 warning 与失败分类

开发必须用稳定代码区分：

- `OWNER_SCOPE_VIOLATION`：跨 owner 或归属未知；
- `SOURCE_CONTENT_LOST`：源中非空字段/章节在 ResumeDocument 或 artifact 丢失；
- `TEMPLATE_STRUCTURE_INVALID`：未替换占位符、原型泄漏或必需结构错误；
- `ARTIFACT_INVALID`：DOCX/PDF 缺失、不可读或同源不成立；
- `OPTIONAL_CONTENT_ABSENT`：允许的 summary/awards 等缺失；
- `ANCHOR_UNAVAILABLE`：不影响正文与下载时的诚实降级。

前三类及 artifact invalid 必须 fail closed；后两类不得冒充结构性错误。错误态保留已完成 P1～P3 和明确
恢复动作，但不能产生可下载的“成功简历”。

artifact 先写入 task-scoped staging 并完成内容/可读性校验，再在一个数据库事务中同时登记不可变引用
和 `SUCCEEDED`；任一步失败都不得暴露下载入口，并清理本轮 staging。不能用先成功、后补 artifact 的
补偿逻辑冒充原子发布。

### 3.4 现有设计和性能不变

除 `V220-R3-G07` 两项 Product Owner 反馈外，继续按 `DS-003` Theme A 一比一实现，不新增设计能力。Revision 3
不得用 owner 校验、内容检查或去重增加正常 LLM 调用；真实性能继续执行 Revision 2 的六格门禁。

## 4. 开发任务与依赖

| ID | 开发结果 | 依赖 | 完成证据 |
|---|---|---|---|
| V220-R3-T01 | 身份/PLAN/基线核对；Pre-mortem；真实 runtime 哨兵 | 无 | commit/blob/clean；3 个失败模式与停止点 |
| V220-R3-T02 | Task owner schema、本地身份一致性、迁移与 legacy-unowned 隔离 | T01 | 干净库/旧库迁移正反向、悬空身份修复、rollback/cleanup |
| V220-R3-T03 | Experience/Fact/records/continue/artifact 全链 owner scope | T02 | 三身份越权矩阵；IDOR 反例；task-scoped 下载 |
| V220-R3-T04 | 当前用户选材、精确去重、确定性 education | T03 | ID 集合包含关系、重复矩阵、教育排序与上限 |
| V220-R3-T05 | 字段守恒、联系方式组合、照片占位退出、结构校验与原子 publish | T04 | DOCX/PDF 文本、8 组合、结构失败不得发布 |
| V220-R3-T06 | Logo 导航和步骤 1 自适应滚动 | T01 | click/keyboard/focus/route；目标视口和小视口证据 |
| V220-R3-T07 | 测试/demo 隔离、只读 runtime audit 与内容级回归 | T02-T06 | 默认 runtime 未变；多身份/污染副本矩阵 |
| V220-R3-T08 | 全回归、真实模型、Design Fidelity、failure matrix、clean build/package | T01-T07 | 全部门禁 PASS；最终包 identity |
| V220-R3-T09 | Architecture/Falsification Check、RESULT、clean 新候选冻结 | T08 | 无开放 Challenge；RESULT 完整；工作树 clean |

## 5. 开发 Gate

### 5.1 当前用户内容与归属（新增阻断 Gate）

隔离 runtime 必须同时存在 `current-user`、`other-user`、`stub-user` 三组互不相同的唯一哨兵内容，覆盖
education/work/project 和重复记录。以 V2.2 `/api/task` 主链执行：

1. 当前履历库 ID 集合包含全部候选 ID，且候选/Fact/P4 条目的 owner 全等于 Task owner；
2. P2 snapshot、subtask、ResumeDocument、DOCX 和 PDF 均包含当前用户独有哨兵，不含其他用户或 stub 哨兵；
3. 当前用户教育进入成品；work/project 源中非空标题字段守恒；`fact_refs` 回查当前用户 Fact；
4. 完全重复记录在保存层产生明确重复结果，既有重复在选材层只占一个槽位；
5. legacy-unowned Task 不进入 records，不能通过用户 artifact 路由下载；continue 不能改变 owner；
6. 任一 owner/source/structure 注入失败时任务不得 `SUCCEEDED`，不得发布 DOCX/PDF。

只验证状态、文件存在、下载 200、hash 或 PDF ready 均不能替代以上内容断言。

### 5.2 字段与模板矩阵

- phone/email/location 全 8 组合；每个非空值在 ResumeDocument、DOCX、PDF 中恰好出现一次；
- 当前用户有/无 education，两种都给确定判定；有教育不得被“短输入宽容”移除；
- work/project/education 的 role/degree/major/name/company/time 分别覆盖非空与空值；
- 无照片输入时空照片框为 0；summary/awards 为空时无原型文字、无空标题、无结构性 warning；
- 未替换占位符、模板样例文字、其他 owner 哨兵和源字段丢失均为 0。
- 下载区空 hash 元素为 0；展示 hash 时必须与实际下载 artifact 一致。

### 5.3 API、状态与失败

- 三身份 CRUD/known-ID 越权、records、continue、task snapshot、download 全部反向覆盖；下载还须覆盖
  换 task/owner、伪造文件名和路径穿越，不允许绕过 task-scoped artifact 引用；
- 容量/retention 清理在混合 owner 与 `LEGACY_UNOWNED` 数据中不跨 owner 删除，失败和重复执行保持幂等；
- atomic finalize 在 DB commit、文件写入、Word/PDF、取消和迟到结果失败点均不产生假成功；
- P1～P4 失败矩阵、取消、新任务、SSE 重连/缺口/重复/乱序、ErrorBoundary 和资源清理全部回归；
- runtime ownership audit 只读、脱敏、结构化；真实 runtime 前后文件/hash/mtime 哨兵不变。

### 5.4 前端与 Design Fidelity

- workbench empty/saved/P1/P2/P3/P4/failed/success、experiences、records、privacy 与 `DS-003` 对照；
- 品牌区 mouse click、Enter/Space、focus-visible 和返回工作台路由全部通过；不丢当前 task；
- 1686×1076 的约 800 字 JD 回看态 `.wb-panel__scroll` 无实际 overflow（`scrollHeight <= clientHeight + 1`）；
  1440×900 等冻结视口按 DS-003 稳定，小视口和超长输入可滚动且最后一个控件/提示可达；
- 整页 overflow、内部滚动、固定 footer、PDF viewer 和下载区按冻结视口矩阵复核。

### 5.5 真实模型、回归与最终包

- 真实模型纵切必须走最终包的 `/api/task` 新链；旧 `/api/resume/generate-docx` 只能做兼容回归，不能
  作为 V2.2 主链通过证据；
- 短/典型/长 × cold/warm 每格 `n>=3`；首完整 Fact 中位数和最大值 ≤15 秒，typical/long 总时长相对
  V2.1.0 同格中位数降低 ≥25%；正常调用 `1 + 2F`、Embedding 0/1、成功不重试；
- compile/regression、前端 type/build/Hooks、统一 precheck、H6 package audit、failure matrix 全部通过；
- 从 clean 新候选重建 onedir，以多身份污染 runtime 副本和干净 runtime 各完成一次主链内容级 E2E；
- 包内无 Key、真实数据、fixture、测试注入、开发机路径、预置 DB、旧 bundle 或 ReportLab 产品链。

所有必做项给出 PASS/FAIL 与退出码。任一 FAIL、NOT_RUN、缺内容级断言、缺最终包主链或真实 runtime
隔离无法证明，都不能冻结候选。

## 6. runtime 数据处置交付

开发侧只交付安全工具和证据，不直接处置 Product Owner 真实 runtime：

1. 只读 audit：按 owner 汇总 Experience/Fact/Task/artifact 数量，识别已知测试身份和 unowned 记录；
2. dry-run 清理计划：列出将删除/保留的 ID 数量、依赖顺序、备份位置语义和回滚办法，不输出正文/PII；
3. 显式执行入口：只有 Product Owner 另行批准精确范围后才可运行；默认无参数必须拒绝写入；
4. 清理失败必须回滚或停止，不能留下部分删除；清理后重新运行 owner/content Gate；
5. 即使不执行清理，新候选也必须在污染仍存在时正确生成当前用户简历。

## 7. RESULT Delivery Contract

Development Agent 在候选冻结前更新同一 `RESULT.md`，顶部状态保持“待验收”，不得写 `DOC_ALIGNED`、
独立验收通过、人工通过或可发布。RESULT 必须一次性包含：

1. Revision 3 批准 commit/blob、返工基线、新候选/唯一父/branch/clean 与完整 diff；
2. V220-R3-G01～G07、T01～T09 的“用户结果→开发理解→实际交付→证据→偏差”映射；
3. schema/migration、owner 传播、查询过滤、legacy-unowned、artifact 路由和旧入口实际变化；
4. 当前用户 ID 集合→候选→Fact→ResumeDocument→DOCX/PDF 的内容与归属证明；
5. education、重复、联系方式 8 组合、标题字段、照片占位和 warning 分类结果；
6. runtime 隔离、只读 audit、dry-run 清理计划和真实 runtime 未变证据；
7. Logo/键盘/焦点/路由、1686×1076 和冻结视口滚动证据；
8. 全回归、六格真实性能、Design Fidelity、failure matrix、包审计、最终包双 runtime E2E；
9. Pre-mortem、Architecture Check、Falsification Check 及 Challenge 最终状态；
10. 全部命令、退出码、证据入口、最终包文件数/字节/EXE hash 与 cleanup；
11. 待独立验收问题：owner/IDOR、内容来源、迁移、原子发布、真实模型主链、UI、隔离和包身份；
12. 已知偏差；任何未完成强制项必须写 FAIL/NOT_RUN，不能转交 Acceptance Agent 补跑。

RESULT 不粘贴源码、长日志、真实简历正文、联系方式或本机绝对路径。

## 8. 冻结、独立验收与人工验收

Revision 3 获批后，T01～T09 和 §5 全部完成、RESULT 完整、工作区 clean、无开放 Challenge 才能冻结
新候选。由于本轮修改产品 schema、后端、前端、测试和入包文件，旧候选、旧包及旧产品行为
`ACCEPTANCE_PASS` 均不得继承；H6 package audit 的既有行为只作为必须保持的回归基线。

顺序固定：

1. Documentation Agent 依据 PLAN、RESULT、机械身份和证据入口给出一次集中 Gate；
2. 未参与实现、自测或修复的 Acceptance Agent 在隔离副本与最终 onedir 上完成源码、迁移、内容来源、
   多身份越权、真实模型主链、Design Fidelity、失败矩阵、性能、artifact、cleanup 和包审计；
3. Acceptance 报告必须直接核对“当前用户履历 ID → 候选 ID → 成品文本”，不能只复述开发 PASS；
4. Documentation Agent 将绑定新候选的独立结论写入 RESULT；
5. Product Owner 使用同一精确包和自己的当前履历库重新人工生成并验收；
6. 全部通过后才更新 CURRENT_STATE、索引和根 README；另获发布批准后才操作 remote `main` 和 tag。

任一源码、测试、依赖、配置、构建或入包文件变化，原验收自动失效。

## 9. 明确延期与排除

- 登录、注册、多账号 UI、服务器化多用户、PostgreSQL、对象存储、云部署和跨设备恢复；
- 自动删除或自动合并真实 runtime 中的历史 Experience/Fact/Task/artifact；
- 模糊语义重复合并、用户可视的重复候选处理界面、简历上传/OCR/导入查重；
- 自然语言意图修订、单 Fact 重生成/锁定、修改后重制文件和修订历史；
- 新模板、任意 Word 模板解析、照片上传、生产主题切换、Design 批注工具；
- 后端退出、系统重启后的运行中任务续跑、多前台任务。

上述排除项不得用来解释或接受当前用户履历未进入成品、源字段丢失、跨 owner 访问或假成功发布。
