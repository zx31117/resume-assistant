# AI Career Resume Assistant V3.0.0 草稿：免费多用户 Public Release

> 文档角色：版本范围草稿，供 Product Owner 审核
> 状态：DRAFT，非开发指令，不改变当前版本状态
> 重写日期：2026-09-25
> Supersedes：2026-08-19 local-first Career Memory 探索及 2026-09-19 自动化投递入口候选；旧路线由
> Git 历史保存
> 假定前置：V2.3.0 完成多用户服务器底座和低敏 Career Memory 数据合同；V2.4.0 完成 Job Model、
> 召回/润色、固定模板、网页本地装配与一页纸成品质量冻结
> 核心目标：第一次公开提供免费、多用户、服务器化 AI Career Resume / Job Preparation 产品；
> 首发不接入人民币支付

## 1. 核心判断

V3.0.0 是项目第一次面向真实用户的服务器化、多用户版本。产品长期方向仍是以 Career Memory 为
事实底座，围绕用户主动选择的目标岗位完成岗位理解、事实选材、信息补充和针对性简历。

首发硬结果是：

> 用户能在正式账号中建立或恢复低敏 Career Memory，在产品 Web 端输入目标岗位，并在浏览器本地
> 获得事实可信、岗位相关、一页纸、专业排版且可直接投递的 Preview、DOCX 和 PDF。

## 2. 首发用户旅程

### 2.1 建立 Career Memory 与免费基础简历

~~~text
访问正式 HTTPS 域名
→ 注册或登录账号
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

- 只服务注册、登录、账号恢复、授权、风控和安全审计；
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

### 5.2 服务器文件与产物元数据

- 服务器只保存明确允许的低敏来源片段、无身份内容文件和 ArtifactMetadata；
- 原始身份简历与最终带身份 DOCX/PDF 不进入对象存储、缓存、备份或 CDN；
- URL、文件名或已知对象 ID 不能替代账号授权；
- 代理、缓存和 Range/HEAD 请求保持相同授权；
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
- Stable Evidence 优先复用，Adaptive Evidence 针对当前岗位重新处理；
- Fast Lane 提供高置信完整内容，Precision Lane 完成扩展召回和精排；
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
- 新用户、自然恢复、Early User 和受控邀请可以发放免费积分；
- 充值、订单、支付、订阅和人民币价格明确不做。

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

## 13. 正式 PLAN 前待冻结

1. 免费积分、ApplicationCase 有效期、完整重算和公平使用上限；
2. Public 或 Invite-only 发布方式；
3. 首发目标账号数、并发、地区和 SLO；
4. Role Profile、Company Context 来源和首发岗位范围；
5. 服务端数据导出、删除、保留期和注销说明；低敏字段白名单已由 D-045 冻结；
6. Local Resume Identity/Entity Map 本地存储、重新输入、清除和失败体验；
7. 固定模板、固定槽位、桌面 Chromium、DOCX/PDF 生成器和 Word 兼容范围；
8. 隐私说明、第三方模型数据处理和本地数据风险说明；
9. 正式服务器、对象存储、数据库和灾难恢复方案；
10. V3.0.0 必要 Design Snapshot。

Resume Identity 是否服务端保存已经冻结，不再列为待决策。

## 14. 与既有决策的关系

- D-034：系统承担事实边界内的专业判断；
- D-035：Career Memory 通过当前任务渐进沉淀；
- D-036：服务端 Career Memory 方向继续有效；身份、真实实体名称和最终文件边界由 D-044 取代；
- D-038：用户材料直接抽取与模型推断使用不同确认边界；
- D-039：公开上线前实施真实认证、授权、审计和部署隔离；
- D-044：Career Memory 服务端化，Resume Identity/Entity Map 与最终装配 Local-only；
- D-045：V2.3.0 香港邀请制 Alpha、低敏白名单及共享 PostgreSQL/pgvector 强隔离基线。

## 15. Post-V3 Future Direction

V2.3.0 已预留 ApplicationCase 外部客户端接入合同，未来 Browser Assistant 可作为新入口接入现有
平台而无需重构 Career Memory/ApplicationCase，具体版本号、站点和能力范围均未冻结。

在范围、配额、安全、部署、本地装配和必要 Design Snapshot 获批前，本文不授权开发。
