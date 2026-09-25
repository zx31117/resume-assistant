# AI Career Resume Assistant V3.0.0 草稿：免费多用户邀请制 Beta

> 文档角色：版本范围草稿，供 Product Owner 审核
> 状态：DRAFT，非开发指令，不改变当前版本状态
> 重写日期：2026-09-25
> Supersedes：2026-08-19 local-first Career Memory 探索及 2026-09-19 自动化投递入口候选；旧路线由
> Git 历史保存
> 并行发布列车：V2.3.0 底座工作流 ∥ V2.4.0 质量/装配工作流 ∥ V3.0.0 产品工作流；Day 3/6
> 完成合并 Gate，Day 9 形成唯一 V3.0.0 冻结候选并统一独立验收
> 核心目标：第一次通过正式 HTTPS 域名提供免费、多用户、服务器化邀请制 Beta；
> 首发不接入人民币支付

## 1. 核心判断

V3.0.0 是项目第一次面向受邀真实用户的服务器化、多用户版本，不开放自由注册。产品长期方向仍是以 Career Memory 为
事实底座，围绕用户主动选择的目标岗位完成岗位理解、事实选材、信息补充和针对性简历。

V2.3/V2.4 不再形成独立发布候选或独立验收结论。模块测试、合同测试和 Day 3/6 真实纵切是持续合并
Gate；V3.0.0 的正式 Acceptance 必须一次覆盖底座隔离、生成质量、本地一页纸、产品体验、埋点和生产
运行。“统一验收”不等于把验证推迟到 Day 9。

首发硬结果是：

> 用户能在正式账号中建立或恢复低敏 Career Memory，在产品 Web 端输入目标岗位，并在浏览器本地
> 获得事实可信、岗位相关、一页纸、专业排版且可直接投递的 Preview、DOCX 和 PDF。

## 2. 首发用户旅程

### 2.1 建立 Career Memory 与免费基础简历

~~~text
访问正式 HTTPS 域名
→ 通过一次性邀请激活或登录账号
→ 在浏览器本地选择已有简历，或手工录入经历
→ 本地移除 Resume Identity 与真实实体名称
→ 服务器接收低敏 Experience / Fact / entity_ref
→ 用户处理需确认项
→ 服务器生成无身份基础简历内容
→ 浏览器用 Local Resume Identity / Local Entity Map 本地装配
→ 预览并下载一页 DOCX/PDF
~~~

原始简历字节、姓名、电话、联系邮箱、地址和用户履历中的真实公司/学校/客户/项目名称不得发送业务服务器。
基础简历必须达到正常投递下限，不能通过更差模型、水印、事实缺陷或不可读排版迫使用户消耗积分。

### 2.2 针对目标岗位

~~~text
在产品 Web 端粘贴 JD / 输入岗位信息
→ 创建 ApplicationCase
→ 冻结 JobModelSnapshot
→ EvidenceSelection
→ 必要的信息缺口追问
→ ResumeContentPlan / ResumeRevision / LayoutPlan
→ 浏览器本地补回 Resume Identity 与真实实体名称
→ Preview
→ 本地 DOCX / PDF
→ 下载
~~~

普通岗位 URL 可以作为用户输入和 JobModelSnapshot 来源字段，但 V3.0.0 不自动访问、抓取或解析招聘
网站页面。

### 2.3 状态、历史与事实回流

- 保存 ApplicationCase、岗位快照、低敏简历内容修订、模板/LayoutPlan 和 ArtifactMetadata；
- 用户可以记录准备中、已下载、已投递、稍后处理、放弃或面试等基础状态；
- 当前任务补充的信息只有用户明确确认后才写回服务器 Career Memory；
- 写回前移除 Resume Identity 与真实实体名称，使用 opaque entity_ref 和批准低敏描述；
- Job Model、Company Context 和模型推测永远不能写入 Person Model；
- 最终带身份文件只保存在当前设备；历史“再次下载”是重新本地装配，不是下载服务器旧文件；
- 换设备后 Career Memory 可恢复，Local Resume Identity 与 Local Entity Map 暂由用户重新输入。

## 3. 产品模型

### 3.1 Person Model

~~~text
服务器确认事实层：Experience / Fact / opaque entity_ref
服务器派生理解层：Embedding / 标签 / 摘要 / Stable Evidence
服务器行为偏好层：历史选择 / 表达偏好 / ApplicationCase 状态

本地装配层：Local Resume Identity / Local Entity Map
~~~

确认事实层是生成事实依据。派生层必须可重建、带版本和来源；行为偏好不能冒充职业事实。本地装配
层不属于 Career Memory，也不向服务器、第三方模型、日志或埋点发送。

### 3.2 Job Model

~~~text
Job Model
= JD 明示要求
+ Role Prior 岗位基本素养
+ 有来源的 Company / Business Context
~~~

- JD 明示要求可以作为招聘方明确条件；
- Role Prior 和 Company Context 可以补召回、排序和表达重点，但必须标注来源；
- Company Context 首版只使用 JD 明示内容、用户主动粘贴/确认的信息和人工审核 Role Profile，不自动
  搜索、访问或抓取公司网页；
- 无来源推测不能进入选材；
- 每次任务冻结 JobModelSnapshot，记录 JD hash、Role Profile、Company Context、规则、模型和时间。

### 3.3 ApplicationCase

`ApplicationCase` 是专项准备、权益、埋点和内容版本的共同聚合根：

~~~text
ApplicationCase
├── account / target_job / status
├── JobModelSnapshot
├── EvidenceSelection
├── information_gaps / proposed_facts
├── ResumeContentPlan / ResumeRevision / LayoutPlan
├── ArtifactMetadata
├── application_status
├── nullable external client source fields
└── entitlement / analytics correlation
~~~

一个 ApplicationCase 默认对应一个目标公司类别、一个岗位和一条主 JD 演进链。真实目标公司名称如
需出现在最终文件，由 Local Entity Map 在本地补回，不进入服务器聚合对象。

## 4. 三个身份与数据域

### 4.1 Account / Auth Identity

- 只服务邀请激活、登录、账号恢复、授权、风控和安全审计；
- 认证邮箱、OIDC subject 等保存在独立 Auth 安全域；
- 即使认证邮箱与简历联系邮箱相同，也不得自动复制到业务数据或本地简历身份；
- 普通业务查询不能把 Auth Identity 当作 Career Memory Profile。

### 4.2 Career Memory（服务器）

服务器可账号级持久化：

- 低敏 Experience / Fact；
- Fact enrichment、Embedding 和派生索引；
- opaque entity_ref 与 V2.3.0 冻结的低敏白名单：学校层级、学历层级/宽口径专业、企业行业/类型/
  规模区间、岗位族/职级、年月粒度时间、技能/工具/业务场景及已移除专有名称的职责/量化成果；
- 省、市、大区首版不保存；白名单外字段不得通过自由文本、来源片段、日志或 Embedding 绕过；
- ApplicationCase、JobModelSnapshot、EvidenceSelection；
- ResumeContentPlan、无身份 ResumeRevision、LayoutPlan；
- Task、ArtifactMetadata、UsageRecord、权益和脱敏事件；
- 用户确认后的长期职业事实。

Career Memory 支持跨设备恢复、检索、导出和删除，但不包含 Resume Identity、真实实体名称或原始
身份文件。

### 4.3 Local Resume Identity / Local Entity Map

以下数据只保存在用户设备：

- 姓名、手机号、简历联系邮箱、地址；
- 个人网站、LinkedIn/GitHub 等直接身份入口及其他可直接识别/联系用户的字段；
- 用户履历中的公司、学校、客户、项目等真实实体名称与 entity_ref 的映射；
- 最终 Preview、DOCX、PDF 文件字节。

本地字段不得进入服务器业务数据库、Career Memory、ResumeRevision、模型请求、日志、埋点、APM、
错误报告或质量评测。新设备不从服务器恢复这些字段，V3.0.0 暂由用户重新输入。

### 4.4 原始简历导入

用户在浏览器本地选择原始简历。客户端先完成解析、身份/真实实体识别和去除，再把低敏结构化事实、
必要来源片段和来源 hash 发送服务器。不能确定是否已清除时 fail closed，不上传原始字节或不确定片段。

模型推断、冲突合并、低置信解析和新增回答仍需用户确认；直接抽取也必须保留不含本地身份的可回查
来源关系。

## 5. 多用户数据库、向量与文件边界

### 5.1 PostgreSQL / pgvector

- PostgreSQL 是服务器业务真源；
- pgvector 保存可从低敏 Fact 重建的派生向量；
- 所有业务数据具有非空 account_id，父子对象使用账号维度复合外键防止跨账号引用；
- Row-Level Security 必须 ENABLE/FORCE；普通应用角色不是表 owner、superuser 且无 BYPASSRLS，
  无事务级可信账号上下文时默认拒绝；
- Embedding 与源 Fact 使用同账号复合外键；向量检索先在 SQL 层限定账号、状态、revision/hash 和模型
  版本，再执行相似度排序，禁止跨账号向量去重、缓存或结果复用；
- fingerprint、dimension、Fact revision/hash 或模型版本不匹配时禁止使用旧向量；
- production、staging 和 test 数据面物理隔离。

### 5.2 服务器结构化内容与产物元数据

- 服务器只在 PostgreSQL 保存明确允许的低敏来源片段、结构化 ResumeRevision 和 ArtifactMetadata；
  首发不建立内容文件对象存储；
- 原始身份简历与最终带身份 DOCX/PDF 不进入对象存储、缓存、备份或 CDN；
- URL、文件名或已知对象 ID 不能替代账号授权；
- 首发不提供服务器文件 Range/HEAD 下载；结构化对象读取继续经过会话、账号和 RLS 授权；
- 删除、失败、超时和崩溃场景均有资源清理；
- 账号导出/删除只覆盖服务器实际持有内容，并明确本地文件需由用户自行管理。

## 6. 方案 B：网页本地固定模板装配

### 6.1 首发边界

- 一套版本化生产模板；
- 桌面 Chromium 为首发基准；
- Local Resume Identity 与 Local Entity Map 只在浏览器本地受控存储和内存出现；
- 身份、联系方式及真实实体名称只进入模板固定槽位，不在正文任意散落；
- 超长字段要求用户本地提供简写，不静默截断、不上传原值；
- 手机端与其他浏览器保证官网和结果可读，完整文件装配范围由正式 PLAN 冻结。

### 6.2 本地文件流程

~~~text
Server ResumeRevision + LayoutPlan + Template Version
+ Local Resume Identity Revision
+ Local Entity Map Revision
→ Local Document Assembler
→ Preview
→ DOCX Blob
→ PDF Blob
→ 一页/溢出/可读性检查
→ Download
~~~

浏览器不得把最终文件字节回传服务器。下载使用本地 Blob/Object URL；临时内存和失效 Blob 按状态
清理。本地敏感数据不得明文写入 localStorage，正式 PLAN 必须冻结 IndexedDB/OPFS、WebCrypto、
密钥生命周期、清除、迁移、无痕模式和浏览器回收后的失败语义。

### 6.3 DOCX/PDF 同源

同源表示 Preview、DOCX 和 PDF 使用同一 JobModelSnapshot、EvidenceSelection、ResumeContentPlan、
ResumeRevision、LayoutPlan、模板版本及本地 identity/entity map revision；不再要求包含真实身份的
最终 PDF 由服务端 Word 转换最终 DOCX。

本地 PDF 必须实际一页；DOCX 必须在批准 Word/字体环境中实际一页。V2.4.0 的合成身份和实体名称
边界矩阵是首发回归基线，不承诺所有办公软件和缺失字体环境像素级一致。

### 6.4 本地安全

- 页面禁止不必要第三方脚本和分析 SDK；
- CSP、依赖锁定、出站白名单、敏感 sink 审计和网络负向探针必须通过；
- 错误处理不得附带字段值、文件字节、DOM、截图或完整异常对象；
- 埋点只能记录枚举状态和脱敏计数，不记录原值或可反推出身份的长度组合；
- 前端发布资产被篡改或完整性无法确认时，Local Resume Identity 功能 fail closed。

## 7. 针对性简历与质量

- V2.4.0 冻结的 Role Prior、Company Context、混合召回、内容计划、润色和一页纸闭环进入生产；
- Stable/Adaptive 复用与 Fast/Precision 双通道是质量候选机制，只有在 Day 3 前证明比单通道有稳定
  正收益且不威胁一页纸、延迟和事实边界时才进入首发；否则按 §16.3 CUT-02 使用单生成通道；
- 服务器每条内容保留 fact_refs 和 opaque entity_ref，未知、跨账号、过期和无来源内容被拒绝；
- ResumeContentPlan 为本地固定槽位预留明确空间预算；
- 本地超页只向服务器提交批准的内容预算/溢出类别，不提交身份、真实名称或原始长度明细；
- 服务器真实环境持续采集首结果、最终内容、缓存命中、模型调用、Token 和成本；
- 本地装配持续采集隐私安全的成功/失败枚举和耗时。

成功成品必须：

- 事实可信、岗位相关，不需要用户大段重写；
- 无占位符、空章节、重复 bullet、调试文字、溢出、遮挡、裁切或隐藏内容；
- 本地 PDF 和批准 Word 环境 DOCX 都恰好一页；
- 使用获批模板并达到最小字号、行距、字距、页边距和层级可读性；
- 无法同时满足事实、一页和可读性时明确失败或请求用户确认取舍。

V3.0.0 后可以微调召回权重、top-k、阈值、Prompt、模型、表达风格、内容预算和批准范围内版式参数；
不得再重做事实真源、三个数据域、核心生成对象关系和本地装配合同。

## 8. 免费权益

V3.0.0 不接支付，但启用完整免费权益语义：

- Career Memory 和可投递基础简历免费；
- 专项 ApplicationCase 按完整任务消耗积分，不按模型调用次数扣减；
- 同一任务内正常修改、失败重试、刷新恢复和失败范围续试不重复扣减；
- 高成本任务 reserve，首份可用内容形成后 settle；未产生可用结果时 release；
- 系统故障可以 refund，所有变化进入不可变账本；
- 新账号按冻结规则赠送免费积分；周期恢复、签到和 Early User 额外赠送留到后续版本；
- 充值、订单、支付、订阅和人民币价格明确不做。

首发数值冻结为：新账号赠送 10 积分；新建专项 ApplicationCase 预留 1 积分，首份可用结果形成后
结算；技术失败、失败范围续试、同任务恢复和再次下载不重复扣减；成功后用户主动完整重算作为新任务
再扣 1 积分。基础简历始终不扣积分。

本地重新装配或再次下载同一冻结内容不产生新的权益扣减。

## 9. 埋点、质量与实验

### 9.1 产品漏斗

~~~text
注册/登录
→ Career Memory 建立
→ 免费基础简历
→ ApplicationCase 创建
→ 首结果
→ 最终内容
→ 本地装配成功
→ 下载
→ 投递状态
→ 再次自然使用
~~~

### 9.2 运行与质量

- 各阶段 P50/P95、错误、重试、Token、成本和资源；
- 召回候选数、最终选择数、规则/模型/模板/装配器版本和缓存命中；
- 信息缺口回答、跳过、仅本次、确认回流和后续复用；
- 本地装配结果、超页类别、失败阶段和下载事件；
- 免费赠送、邀请和其他补贴行为与自然行为分开；
- 质量评测不保存用户正文、Resume Identity 或真实实体名称。

## 10. 生产运行

- 正式 HTTPS 域名和稳定 origin；
- 邀请制、最多 20 个账号、最多 5 个并发生成任务；超过上限排队或明确拒绝；
- 认证、授权、管理角色、会话失效、限流和滥用防护；
- 服务端 Provider Gateway 与密钥管理，平台 Key 不下发前端；
- 数据库迁移、备份核验、恢复演练、账号删除和版本回滚；
- 应用、数据库、队列、模型、磁盘和证书监控；
- 脱敏日志、告警、审计、保留上限和事件响应；
- 请求体、并发、队列、任务时限、Token 和免费成本配额；
- 前端静态资产完整性、CSP、依赖供应链和出站网络监控；
- 真实服务器、真实 Web 浏览器、真实模型和本地最终文件验收；
- 管理后台从普通导航退出，并由服务端角色和部署边界保护。

## 11. V3.0.0 首发范围

### 11.1 必须具备

- 正式账号、登录、退出和恢复；
- 多用户 PostgreSQL/pgvector 隔离；
- 低敏 Career Memory 服务端持久化与跨设备恢复；
- 原始简历本地处理和低敏事实导入；
- 免费一页纸基础简历；
- ApplicationCase 与 Job Model v1；
- 针对性召回、润色和信息缺口；
- 方案 B 本地 Preview/DOCX/PDF；
- 固定模板、固定槽位和一页纸质量门禁；
- 用户确认后的低敏事实回流；
- ApplicationCase 状态与历史；
- 免费积分账本和任务级结算；
- 产品、运行和质量埋点；
- 服务器数据导出、删除、注销、隐私和第三方模型说明；
- Career Memory 保留至用户删除/注销；活动库目标 24 小时内删除，备份最长 30 天退出，脱敏运行日志
  保留 14 天；
- 备份恢复、监控、告警、限流和回滚。

### 11.2 后续增强

- 更多岗位 Role Profile 与 Company Context；
- 模拟面试、开放题和网申材料；
- 更完整的投递状态和提醒；
- Early User、邀请、签到和弱感知等级实验；
- 手机端查看、提醒和轻量补充；
- 用户自管的本地身份/实体映射导入导出；
- 真实行为驱动的 Career Memory 深化。

### 11.3 明确不做

- 人民币充值、订单、支付、订阅和自动续费；
- 自动点击最终提交或后台批量海投；
- 任意 Provider/BYOK、本地模型和完整离线 PWA；
- 多人协作编辑同一 Career Memory；
- 把推断、Role Prior 或 Company Context 静默写成用户事实；
- 把 Resume Identity、真实实体名称、原始身份简历或最终文件发送业务服务器。

## 12. Release Gate 候选

### 12.1 多用户与服务器数据

- [ ] 跨账号 SQL、向量、任务、元数据和账本泄漏为 0；
- [ ] 非空 account_id、账号维度复合外键和 FORCE RLS 同时成立，运行角色无 BYPASSRLS；
- [ ] 已知其他账号对象 ID 仍不能读取、修改或下载；
- [ ] 相同文本、近似向量、相同 fingerprint 和已知对方 Embedding ID 不造成跨账号召回、缓存命中、
  重建、删除、统计或存在性泄漏；
- [ ] 连接池、后台任务、失败回滚和管理员路径保持隔离；
- [ ] 账号导出、删除、注销和恢复覆盖全部服务器持有数据；
- [ ] production、staging 和 test 无共享数据面；
- [ ] 服务器请求、数据库、文件、备份、模型、日志和埋点中的 Resume Identity/真实实体名称为 0。

### 12.2 ApplicationCase 与内容

- [ ] JobModelSnapshot 区分 JD、Role Prior 和 Company Context；
- [ ] 召回和润色达到 V2.4.0 批准阈值，无跨账号或事实越界；
- [ ] PROPOSED Fact 未确认前不进入 Career Memory；
- [ ] 基础简历免费可用，专项任务积分只结算一次；
- [ ] 服务器内容对象绑定同一 ResumeRevision/LayoutPlan，只有 opaque entity_ref；
- [ ] Product Owner 在代表性真实岗位完成人工验收。
- [ ] 固定 12 案例覆盖技术、产品/运营、通用职能；针对版盲评优于 V2.2 基线不少于 70%；每名真实
  测试者至少获得一份可直接投递成品。

### 12.3 本地身份与最终文件

- [ ] 原始简历在本地解析和清除，身份/真实实体名称不会进入网络；
- [ ] Local Resume Identity 和 Local Entity Map 不从 Auth/Career Memory 自动填充；
- [ ] 新设备明确要求重新输入本地字段；
- [ ] Preview、DOCX、PDF 使用同一冻结内容、模板、LayoutPlan 和本地 revision；
- [ ] 成功成品在本地 PDF 与批准 Word 环境均为一页；
- [ ] 超长槽位、字体替代、无痕模式、存储拒绝、清缓存和崩溃恢复矩阵通过；
- [ ] 前端 XSS/依赖/出站负向测试证明本地身份和最终文件未外发；
- [ ] 再次下载不重复扣减权益。

### 12.4 生产与埋点

- [ ] 正式域名、HTTPS、认证授权、限流、管理隔离和安全头通过；
- [ ] 数据库恢复、账号恢复、部署回滚和资源清理实操通过；
- [ ] 产品漏斗、运行遥测和质量事件完整且去重；
- [ ] 日志、埋点、网关、APM 和错误报告无正文、身份、真实实体名称和密钥泄漏；
- [ ] 服务器真实模型纵切、并发、容量、故障注入和 Web E2E 通过；
- [ ] Product Owner 完成真实账号、真实岗位和本地一页纸成品人工验收。

## 13. Release Train PLAN 输入状态

Product Owner 输入已由 D-043—D-048 冻结：邀请制 Beta、20 账号/5 并发、香港区域、12 案例和质量
硬线、3—5 名真实测试者、免费积分规则、数据保留/删除目标、Company Context 来源、DS-003 视觉基底、
单模板以及 Local-only 身份边界均不再作为待选项。

PLAN 必须技术化冻结：ApplicationCase 有效期与公平使用限流、运行 SLO、活动库/备份删除作业、账号
恢复、隐私与第三方模型说明、Local Identity/Entity Map 存储和失败语义、模板/槽位和浏览器/Word/字体
版本、服务器/数据库/备份实现、最小 Design Snapshot、并行工作流所有权和 Day 3/6/9 统一验收矩阵。

## 14. 与既有决策的关系

- D-034：系统承担事实边界内的专业判断；
- D-035：Career Memory 通过当前任务渐进沉淀；
- D-036：服务端 Career Memory 方向继续有效；身份、真实实体名称和最终文件边界由 D-044 取代；
- D-038：用户材料直接抽取与模型推断使用不同确认边界；
- D-039：公开上线前实施真实认证、授权、审计和部署隔离；
- D-044：Career Memory 服务端化，Resume Identity/Entity Map 与最终装配 Local-only；
- D-045：V2.3.0 香港邀请制 Alpha、低敏白名单及共享 PostgreSQL/pgvector 强隔离基线；
- D-046：三条工作流并行开发，V3.0.0 统一正式验收；
- D-047：邀请制 Beta、质量门槛、免费积分、数据保留与设计基线；
- D-048：九天首发技术收敛包。

## 15. Post-V3 Future Direction

V2.3.0 已预留 ApplicationCase 外部客户端接入合同，未来 Browser Assistant 可作为新入口接入现有
平台而无需重构 Career Memory/ApplicationCase，具体版本号、站点和能力范围均未冻结。

在范围、配额、安全、部署、本地装配和必要 Design Snapshot 获批前，本文不授权开发；授权后由一份
V3.0.0 Release Train PLAN 统一管理三条并行工作流、集成 Gate、冻结候选和最终验收。

## 16. PLAN 前统一技术预演与可达性结论

### 16.1 当前结论

完整实现本文所有候选机制并在九天内稳定上线不可控；在邀请制 Beta、单模板和既有隐私/质量硬线不变的
前提下，采用 §16.3 的首发收敛包后目标可达。V3 PLAN 不得把以下结构性差异当成开发细节：

1. 当前 V2.2 是 SQLite + 固定 owner + loopback token + 进程内线程 + Windows/Word 本地产物；V3 是
   PostgreSQL/RLS + 真实账号 + 持久 worker + Web Local-only 产物，属于五条新纵切；
2. 免费基础简历和专项简历必须是同一正式状态机中的不同 `case_type`。`BASE` 不要求 JD、不扣积分；
   `TARGETED` 绑定 JobModelSnapshot/ApplicationCase 并按 D-047 结算，不能复用“姓名 + JD 必填”的旧合同；
3. 用户履历真实公司/学校属于 Local Entity Map；目标岗位公司名若来自 JD，可作为 Job Model 的岗位
   上下文保存，但不得反向写入 Career Memory 的用户履历实体；
4. 服务器不需要保存最终文件，也不需要首发对象存储。结构化 Revision/任务/账本/埋点进入 PostgreSQL，
   最终 Preview/DOCX/PDF 只在浏览器装配；
5. “最多 5 个并发生成任务”解释为容量/排队上限；初始真实模型执行并发建议为 2，由香港实例实测和
   供应商限流证据调整，不以并发压垮质量或月度预算。

### 16.2 统一 P0 Gate

| 时间 | 必须形成的真实证据 | 失败处理 |
|---|---|---|
| Day 1 | 目标香港实例到真实模型/Embedding 的延迟、错误、Token/费用探针；共享 schema/API/event owner 冻结 | 不继续假设网络和成本可用，立即换规格/供应商或缩小运行容量 |
| Day 2 | 浏览器固定模板生成 DOCX/PDF Blob，嵌入固定字体，同一 LayoutPlan，同源 hash；原始文件和身份零出站 | 方案 B 不成立即 `CHALLENGE_OPEN`；禁止改成服务器处理身份文件 |
| Day 3 | 两账号 SQL/Embedding/缓存/账本负向矩阵；Web/worker 重启、lease reclaim、RLS 事务与连接池复用通过 | 不合并后续功能；先修底座 |
| Day 6 | 香港正式域名、真实邀请账号、真实模型、真实岗位、浏览器本地恢复身份、PDF/DOCX 一页完整纵切 | 未通过则停止首发，不能以模块测试替代 |
| Day 7 | 功能冻结；12 案例和 3—5 名真实测试者进入统一回归 | 只修 P0/P1，不新增功能 |
| Day 9 | 单一 clean commit 候选、生产配置/回滚/恢复证据和独立验收 | 任一硬 Gate 失败即不发布 |

### 16.3 首发收敛包（已由 D-048 冻结）

| ID | V3 首发范围 | 保留到后续的内容 |
|---|---|---|
| CUT-01 | 简历导入只支持有文本层 PDF 与手工录入 | 扫描件 OCR、DOCX 导入 |
| CUT-02 | 单生成通道；账号内精确向量 + 简单关键词/评分 | Fast/Precision 双通道、复杂 Stable/Adaptive 缓存、ANN 索引 |
| CUT-03 | PostgreSQL 保存结构化 Revision 和 ArtifactMetadata | 对象存储、服务器最终文件 |
| CUT-04 | 5 个任务可在途/排队，初始最多 2 个真实模型任务执行 | 更高实际执行并发 |
| CUT-05 | 旧 V2.2 数据不整库自动迁移；用户在网页本地清除后导入或重录 | 自动 SQLite 迁移工具 |
| CUT-06 | 只做 CLI/最小受保护运维入口 | 完整运营后台、自助找回和自动邮件 |
| CUT-07 | 新账号仅赠送冻结的 10 积分，不启用周期自动恢复 | 签到、自然恢复、Early User 额外赠送 |

这七项不改变邀请制、真实多用户、积分、埋点、账号隔离、生成效果、一页纸和可直接投递的硬目标。其余
数据库角色、任务 lease、Cookie/CSRF、RLS transaction wrapper、CSP、SSE 代理、日志白名单和备份
作业均属工程强制项，不再作为 Product Owner 选项。

### 16.4 已选路径的残余风险

以下风险不是恢复 CUT-01—CUT-07 的理由，而是当前选定路径必须在 PLAN 中显式封口的语义缺口：

| ID | 路径隐患 | 若忽略会发生什么 | PLAN 强制控制 |
|---|---|---|---|
| PATH-01 | PostgreSQL worker 是至少一次执行，不是模型调用恰好一次 | worker 在模型返回后、结果落库前崩溃会重复调用和增加成本 | claim/lease/attempt_id；阶段幂等；在调用前、调用后未落库、落库后未确认三个崩溃点故障注入；用户积分仍只结算一次 |
| PATH-02 | 本地装配成功由浏览器上报，服务器无法独立验证最终 Blob | 客户端关闭会留下 reserve；恶意/故障客户端可虚报成功或失败 | 区分服务器内容成功与客户端装配成功；reserve 超时回收；Beta 可接受 client-attested artifact 事件，但不得作为安全或付费真源 |
| PATH-03 | 同一 LayoutPlan 不保证不同 Word/WPS/字体环境相同分页 | 批准环境一页，用户打开后可能变两页 | PDF 为视觉权威；DOCX 只承诺 PLAN 冻结的 Word/字体环境；预留分页安全余量，WPS/其他环境明确为 best effort |
| PATH-04 | 历史重下载依赖旧模板、字体、LayoutPlan 和渲染器 | 部署升级后同一 Revision 无法重建原成品 | ArtifactMetadata 固定全部版本/hash；旧渲染器和资产按 Career Memory 保留期可寻址；跨版本重装配回归 |
| PATH-05 | Local-only 清除存在漏检和过度清除，低敏字段组合仍可能重新识别个人 | 身份或真实实体进入服务器/模型，或事实被清空导致不可用 | 文本层解析 + 规则/实体扫描 + 用户逐项确认；不可消歧 fail closed；明确“低敏不等于匿名”，最小化来源片段 |
| PATH-06 | Job Model 公司实体与用户履历实体若共用占位符命名空间 | 目标公司名可能被错误补入个人经历，形成事实污染 | `job_entity` 与 `person_entity_ref` 类型/命名空间分离；模型 schema 和本地恢复均拒绝跨域引用 |
| PATH-07 | 自建邀请账号在小规格单机上同时承担 Argon2、会话和恢复 | 登录洪峰触发内存压力；弱重置流程造成接管 | Argon2id 参数按目标机器压测；一次性邀请、会话撤销、CSRF、限流；首发只允许管理员辅助重置并审计 |
| PATH-08 | 单机香港部署同时承载 Web、worker、PostgreSQL | OOM/磁盘满会同时中断所有链路，RTO 可能达不到 4 小时 | 资源上限、磁盘水位、worker 并发 2、数据库本机仅私网/loopback、离机备份和从空机恢复演练；不宣称 HA |
| PATH-09 | 服务器低敏 Career Memory 和模型输入仍可能属于个人信息；香港部署还存在数据出境适用性 | 真实朋友测试缺少充分告知/同意和处理边界 | 真实账号启用前完成隐私说明、第三方模型/地域/字段清单、删除方式和必要同意；由有资格人员确认适用义务 |
| PATH-10 | 12 个质量案例若被开发用于调 Prompt/权重，再拿来验收会产生评测污染 | 70% 盲评线失真，V3 后真实岗位效果回落 | 调优集与锁定验收集分离；12 个 Gate 案例在冻结前不可向开发暴露期望结果；70% 明确为至少 9/12 |
| PATH-11 | 一页率可通过事后把失败样本标成“不支持”被架空 | 100% 指标形式通过但真实用户不可用 | 支持范围和排除理由在执行前冻结；所有已接受输入进入分母；失败不得事后改标签 |
| PATH-12 | 去正文埋点无法证明内容质量，客户端事件也不可信 | 仪表盘看似正常但成品质量下降 | 自动埋点只做漏斗/性能/错误码；质量由锁定离线集和明确同意的人工评测承担，不用生产埋点替代 |
| PATH-13 | 三工作流并行但共享 schema/API/事件，Integration Owner 可能成为单点瓶颈 | 每日集成停滞，Day 7 才暴露合同冲突 | Day 1 字段级 owner 表、破坏性变更窗口、合同测试和每日集成；owner 缺席时停止共享合同变更 |
| PATH-14 | 网页 Local-only 仍信任服务器下发的前端代码；WebCrypto 不能抵御被攻破的同源脚本 | 站点或供应链被攻破时，本地身份可能在解密后被读取并外发 | 自托管全部脚本/字体、严格 CSP、依赖锁与审计、可复现前端构建和发布 hash；隐私说明只承诺正常受控版本零外发，不宣称能抵御源站完全失陷 |

除上述风险外，PLAN 还必须冻结首结果、最终结果、排队等待和本地装配的 SLO；没有 SLO 就无法判断
“单通道 + 2 执行并发”是否在真实 Web 体验上达标。
