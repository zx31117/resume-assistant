# AI Career Resume Assistant V2.3.0 草稿：多用户服务器底座与专项投递契约

> 文档角色：版本范围草稿，供 Product Owner 审核
> 状态：DRAFT，非开发指令，不改变当前版本状态
> 草稿日期：2026-09-19
> 最近修订：2026-09-25（冻结香港内部 Alpha、低敏白名单与 SQL/Embedding 多用户隔离）
> 假定前置：V2.2.0 已完成本地 owner 归属、当前履历到成品的内容来源闭环、渐进生成和真实结果预览收口
> 发布列车角色：V3.0.0 Release Train 的底座工作流，与 V2.4.0 质量/装配和 V3 产品工作流并行
> 核心目标：在不公开面向用户的前提下，把本地单用户产品迁入可验证的多用户服务器底座，并为
> `ApplicationCase`、生成/产物身份、Job Model、积分权益和埋点建立唯一数据契约

## 1. 版本判断

V2.3.0 不是把现有本地服务直接监听到公网，也不是 V3.0.0 的缩小版页面。它负责建立其他工作流
不能绕过的正确底座：账号身份、用户数据隔离、服务器持久化、专项投递聚合、质量与产品埋点、
部署和恢复。该工作流与 V2.4.0/V3 并行开发，只在受控内部环境运行，不单独发布或独立验收；其硬
Gate 由 V3.0.0 冻结候选统一接受独立验收。

长期产品方向仍是围绕目标岗位建立专项准备，但 V2.3.0、V2.4.0 和 V3.0.0 均不开发 Browser
Assistant、招聘网站 DOM 读取、字段填充、文件上传或站点 Adapter。V2.3.0 只为未来外部客户端预留
稳定 ApplicationCase API、来源、幂等、授权和审计字段；能力未实现，接口预留不得描述成插件能力。

## 2. 用户结果

V2.3.0 完成时，内部测试者应能够：

1. 使用独立账号登录受控服务器；
2. 各自导入和维护 Career Memory，任何账号都不能读取另一账号的事实、向量、任务或文件；
3. 粘贴 JD 或通过内部岗位导入入口创建 `ApplicationCase`；
4. 生成并恢复一份绑定该账号和岗位的无身份针对性内容任务；
5. 在产品、运行和质量三类埋点中看到脱敏事件，但看不到简历正文、JD、直接身份或密钥；
6. 在服务重启、数据库备份恢复和版本回滚后保持账号与任务边界正确；

## 3. 范围

### 3.1 账号、身份与访问边界

- V2.3.0 的账号模型从 V2.2.0 已验收的本地 owner 契约演进；若 PLAN 保留旧数据导入，不得把 V2.2.0
  的隔离身份、未归属历史记录或测试身份静默合并为首个真实账号，也不得仅凭文件存在或迁移行数判断
  归属正确；
- 内部 Alpha 采用邀请制：管理员创建一次性、可过期、可撤销的邀请，受邀者激活账号后使用自建
  服务端会话；本版不开放公众注册、不依赖 OIDC，也不要求接入自动邮件发送；
- 建立账号、会话、登录、退出、凭据重置和受控测试账号生命周期；
- 普通 API 的 `account_id` 只能来自服务端验证后的会话主体，禁止信任请求体中的 `user_id`；
- 管理接口、普通接口和后台任务使用不同角色与授权边界；
- 本地开发者入口不进入公开导航；隐藏入口不能替代服务端鉴权；
- Account/Auth Identity 只服务认证与授权，不得复制成简历身份或普通业务 Profile；
- Local Resume Identity 与 Local Entity Map 只保存在用户设备，不进入服务器、模型、日志或埋点；
- Career Memory、任务、权益、产物元数据和埋点使用独立业务访问边界。

### 3.2 PostgreSQL 与向量隔离

首版采用共享 PostgreSQL 数据库、共享业务 schema，并使用同库 `pgvector` 保存派生向量。这里的
“共享”只表示节省内部 Alpha 的部署成本，不表示共享访问：账号数据必须在 schema、RLS、事务上下文、
Repository、后台任务和验收六层同时隔离。V2.3.0 不为每个账号建立独立数据库，也不为服务器模式保留
SQLite 作为活动业务真源，不另行引入 Qdrant、Milvus 或第二个持久化向量系统。

所有用户拥有的数据必须显式携带非空 `account_id`，至少包括：

~~~text
accounts / account_settings（不得包含 Resume Identity）
experiences / facts / fact_enrichments / fact_embeddings / low_sensitivity_entity_descriptors
application_cases / job_model_snapshots / evidence_selections / resume_content_plans
generation_tasks / task_input_revisions / task_subtasks / task_snapshots / task_events
resume_revisions / layout_plans / artifact_metadata
usage_records / entitlement_ledger
~~~

隔离规则：

- 每张账号所有表都使用非空 `account_id`；父子关系以 `(account_id, id)` 复合唯一键/外键约束，禁止
  仅凭全局对象 ID 建立跨账号引用；
- PostgreSQL Row-Level Security 必须 `ENABLE` 且 `FORCE`，无账号上下文默认返回空或拒绝；应用运行
  角色不得是表 owner、superuser 或持有 `BYPASSRLS`，迁移角色与运行角色分离；
- 服务端从已验证会话取得 `account_id`，在显式事务内通过 `SET LOCAL` 写入账号上下文；Repository
  仍须显式接收账号，不提供“可选账号过滤”或普通业务可调用的全表方法；
- 连接池归还、异常回滚和账号切换后不能残留上一账号上下文；后台 worker 的队列领取与账号业务事务
  分离，执行任务时必须从可信任务归属重新建立事务级账号上下文；
- `fact_embeddings` 与源 Fact 使用同一非空 `account_id` 和复合外键，唯一键至少覆盖账号、Fact、
  内容 revision/hash 与 Embedding 模型版本；不存在跨账号向量去重、共享缓存或共享结果复用；
- 向量检索候选集先限定当前 `account_id`、有效状态、Fact revision/hash 和模型版本，再做距离排序；RLS
  作为不可绕过的第二道边界。已知其他账号的 Fact/Embedding ID 也不得返回记录、距离或存在性差异；
- 向量生成只接收当前账号已降敏 Fact；向量重建、失效、统计、缓存、删除和备份恢复均按账号执行，
  不存在全局普通用户维护入口；
- `production`、`staging`、`test` 使用不同数据库、凭据、文件存储和向量索引边界；
- 用户删除、备份恢复和迁移同时覆盖 SQL 事实、向量派生、任务与文件引用；
- 任何已知其他账号 ID 的请求仍必须不可见，不能只依靠前端不展示 ID。

初期不采用“每用户一个数据库/一个向量索引”。若后续出现法规、企业租户或容量证据需要更强物理
隔离，再按版本迁移到独立 schema、数据库或专用向量服务；迁移前不得降低本节的逻辑隔离和反证 Gate。

### 3.3 Account/Auth、Career Memory 与本地身份

~~~text
Account / Auth Identity
    仅用于认证与授权

Career Memory（服务器）
    Experience / Fact / enrichment / Embedding / 低敏实体描述

Local Resume Identity + Local Entity Map（用户设备）
    姓名 / 电话 / 联系邮箱 / 地址 / 个人链接等直接身份
    用户履历中的公司 / 学校 / 客户 / 项目等真实实体名称映射
~~~

- SQL `Experience / Fact` 继续作为服务器职业事实真源，不建立平行自由文本画像；
- Career Memory 只使用不可反查的 `entity_ref` 和以下首版白名单：学校层级（如 `985`、`211`、
  `双一流`、`双非`、`海外`）、学历层级与宽口径专业、企业行业/类型/规模区间、岗位族/职级、
  年月粒度起止时间、技能/工具/业务场景，以及已经移除专有名称的职责和量化成果；
- 省、市、大区和其他地理字段首版均不保存；低敏白名单不是“匿名”承诺，组合后仍按用户数据保护；
- 白名单外字段默认拒绝进入服务器，新增类别必须经版本化 schema、隐私检查和 Product Owner 决策，
  不能把原值塞入备注、source fragment、日志或 Embedding 绕过；
- 用户履历中的真实公司、学校、客户和项目名称保存在 Local Entity Map，不进入服务器 Career Memory；
- Auth 邮箱或 OIDC subject 属于独立认证域，即使与简历联系邮箱取值相同也不得自动复制；
- 用户选择原始简历文件时先在本地处理；服务器只接收已移除 Resume Identity 与真实实体名称的结构化
  Experience/Fact、必要来源片段和来源 hash，原始文件不得上传业务服务器；
- 用户材料的直接抽取、模型推断和确认边界继续遵守 D-035、D-038；
- Fact enrichment 是带来源、版本、置信度和可重建状态的派生数据，不反向覆盖 Fact；
- 模型提出的新事实先进入 `PROPOSED`，只有用户明确确认后才能成为长期 `CONFIRMED` 事实；
- 数据导出、删除、备份和恢复只覆盖服务器实际持有的数据；换设备后 Career Memory 可恢复，Local
  Resume Identity 与 Local Entity Map 暂由用户重新输入。

### 3.4 ApplicationCase 与 Job Model 契约

`ApplicationCase` 是一个账号针对一个目标岗位进行专项准备的聚合根：

~~~text
ApplicationCase
├── account_id / status / source
├── target_job（company / position / URL / JD revisions）
├── JobModelSnapshot
├── EvidenceSelection
├── information_gaps / proposed_facts / confirmed_facts
├── ResumeRevision / ArtifactMetadata
├── nullable external_client_source / external_session_id / adapter_version
└── entitlement_transaction / analytics correlation
~~~

本版只冻结数据与生命周期，不宣称完整 Job Application Agent 已实现。`JobModelSnapshot` 至少为后续
预留 JD 明示要求、Role Prior、Company Context、来源、置信度、版本和更新时间；V2.3.0 可以只用
JD 建立第一份快照。

### 3.5 Future External Client Contract

本版提供正式创建 ApplicationCase 的服务端 API，并为未来外部客户端预留：

- `ApplicationCase.source`、target job source URL/source type 和外部客户端来源类型；
- nullable `external_session_id`、nullable `adapter_version`；
- 幂等键、短时授权、来源审计和无身份内容/ArtifactMetadata 受控获取契约。

V2.3.0 不实现任何外部客户端、浏览器扩展、招聘网站 DOM 解析、权限请求、字段填充、文件上传或
Adapter。所有字段均允许为空，产品 Web 端粘贴 JD/输入岗位信息是当前唯一正式创建路径。

### 3.6 积分与权益底座

建立不可变权益账本，但本版不启用人民币支付：

~~~text
grant / reserve / settle / release / refund / expire / adjustment
~~~

账本必须支持账号、ApplicationCase、幂等键、原因码、数量、有效期和来源。余额不能通过普通业务
接口直接覆盖。V2.3.0 可以只在内部账号中发放测试额度，不向用户承诺价格、等级、签到或永久权益。

### 3.7 埋点与评测底座

分开记录三类数据：

| 数据 | 用途 | 禁止内容 |
|---|---|---|
| 产品事件 | 登录、导入、建岗、生成、预览、下载、返回 | 简历/JD 正文、Resume Identity、真实实体名称 |
| 运行遥测 | 延迟、错误、重试、Token、成本、队列、资源 | Prompt、模型完整响应、密钥 |
| 质量事件 | 候选数、选择数、排序版本、保留/重生成、反馈 | 未经处理的用户正文 |

所有事件带 `event_id`、`event_version`、环境、应用版本、账号伪标识、会话/任务关联、发生时间和
幂等语义。补贴行为与自然行为预留独立字段，不能把运营赠送制造的行为误判为自然留存。

### 3.8 服务器运行与发布

- 内部 Alpha 部署在香港单一区域，首版基础设施经常性月费目标不超过人民币 100 元；模型 Token/API
  按量费用、域名和一次性费用单独记录，不用基础设施预算掩盖。每个版本复核资源与成本后再决定扩容；
- 为满足上述成本目标，V2.3.0 可以使用单台小规格服务器承载反向代理、应用与 PostgreSQL/pgvector，
  但服务进程、运行账号、持久卷、数据库凭据和备份边界必须分离；本版不承诺高可用或跨区域容灾；
- 固定服务器操作系统、服务账户和持久目录；服务器只生成不含本地身份/真实实体名称的内容与元数据；
- 反向代理、HTTPS、Host/Origin/CORS/CSRF/Cookie 策略进入服务器基线；
- 配置和供应商 Key 使用服务器密钥管理，不沿用交互式本机凭据假设；
- 建立数据库迁移、备份核验、恢复演练、健康检查、日志轮转和版本回滚；
- 服务器实际持有的低敏来源片段、PostgreSQL 结构化 Revision 和元数据按账号/任务隔离；首发不建立
  内容文件对象存储，成功、失败、超时和崩溃均有清理策略；
- 限制请求体、并发任务、队列、磁盘、模型调用和单任务成本；
- 初始容量目标为最多 20 个邀请账号、最多 5 个并发生成任务；超过容量时排队或明确限流，不以串用账号
  上下文或跳过隔离检查换取吞吐；
- 数据库及必要服务器状态的目标为 `RPO ≤ 24h`、`RTO ≤ 4h`；每日加密离机备份、恢复演练和账号边界
  复核必须有实操证据；
- 真实生产部署前仍必须另做安全与容量验收。

### 3.9 验收判定、歧义策略与一次性返工

V2.3.0 同时涉及账号鉴权、RLS、本地/服务器数据分界、隐私扫描、埋点脱敏、权益账本和资源清理。此类 Gate
不能先由测试样本定义“对错”，再反向补产品规则；正式 PLAN 必须先冻结组件目标和歧义策略，开发与
验收再据此判定。测试标签与报告结论不得取代合同。

对迁移后的简历核心链路，状态成功、文件存在、hash、预览和下载可用仍不足以证明结果正确。验收必须
贯通“会话账号 → 当前账号履历 ID → Fact/选择快照 → ResumeRevision/ArtifactMetadata”，并用第二
账号、身份/真实实体名称哨兵证明没有跨账号选材或本地字段外泄；旧兼容入口或单账号 fixture 不能
替代当前主链。最终本地一页 PDF、同字节 Preview/Download 与 DOCX 可编辑副本由 V2.4.0 另行验收。

#### 3.9.1 打回前四类定性

任何验收异常必须先归入以下一类：

| 分类 | 定义 | 处置 |
|---|---|---|
| `CONTRACT_VIOLATION` | 明确违反已批准 PLAN、架构不变量或已冻结安全策略 | 阻断；形成可复现、可确定的最小返工 |
| `POLICY_AMBIGUITY` | 纯输入或环境不足以可靠区分两种合法解释 | 先由 Documentation Agent 收口策略；涉及用户结果或风险取舍时交 Product Owner，不直接要求开发猜测 |
| `EVIDENCE_CONTRADICTION` | 计数、正文、观察与 PASS/FAIL 总结互相冲突 | 暂停继承结论；按合同重新分类样本并修正报告，不以多数通过掩盖失败，也不把错误预期升级为缺陷 |
| `NON_BLOCKING_OBSERVATION` | 不违反合同且不改变安全、用户结果、候选或包身份 | 记录边界或未来增强，不创建返工轮次 |

只有同时满足以下三项，Documentation Agent 才能把问题交回开发：

1. 能指向明确合同、架构或安全要求；
2. 有独立可复现的实际偏差，而不是仅与测试作者直觉不同；
3. 修复结果可确定，不要求程序解决本质不可判定的语义歧义。

缺任一项时，先解决策略或证据问题，不得形成源码返工任务。

#### 3.9.2 高风险组件的歧义矩阵

正式 PLAN 必须为每个高风险 Gate 预登记判定表，至少包含：组件目标、明确允许、明确阻断、不可消歧
输入、fail-open / fail-closed 策略、代表性正反例、退出码/结构化证据以及对候选身份的影响。最低覆盖：

- 鉴权主体缺失、会话失效、账号上下文不一致：默认拒绝；
- RLS/连接池账号上下文缺失或不确定：默认拒绝并阻断连接复用；
- Resume Identity、真实实体名称或原始身份文件是否已经移除无法确定：不得发送到服务器；
- 隐私/包审计输入可能承载真实凭据、直接身份或机器绝对路径但无法可靠消歧：fail-closed；
- 埋点字段是否含正文、Resume Identity 或真实实体名称不确定：丢弃敏感字段并记录可判定错误；
- 权益扣减状态不确定：不重复结算，进入幂等恢复或人工核对；
- 临时资源归属或清理状态不确定：阻断发布并保留脱敏诊断，不把未知写成成功。

对于隐私和安全阻断器，保守命中不自动等于实现误报；必须先判断它是否属于已冻结的 fail-closed
范围。对于用户可见功能，不能以 fail-closed 为名静默吞掉结果，必须按 PLAN 规定展示失败或下一步。

#### 3.9.3 首次失败后的完整问题类别

首次独立验收失败后，不得只为已观察到的单一样本补丁式返工。Documentation Agent 必须在同一轮把
症状提升为完整问题类别，并一次性冻结：

- 正向、反向、越权、失败、重试、恢复和 cleanup 矩阵；
- 编码、转义、引号、键值、空白、多条目、长输入、畸形/二进制及并发边界；
- 明确输入与不可消歧输入的不同策略；
- 已通过且不得回退的能力；
- 不需要重跑的门禁及其 blob/候选/包身份证明；
- 什么新证据才足以再次打回，什么只属于既定保守策略。

开发提示词发出前必须完成一次反证审查：修复是否会破坏已通过能力、是否要求系统解决不可判定问题、
是否只需文档定性，以及不改源码是否仍满足产品和安全目标。未完成该审查，不得创建下一返工轮次。

#### 3.9.4 报告一致性与角色门禁

- 探针必须在执行前登记预期分类和依据；执行后不得因结果不符合预期而临时改变合同；
- `x/y` 计数、逐项结果、非阻断观察和最终 PASS/FAIL 必须机械一致；不一致时先解决
  `EVIDENCE_CONTRADICTION`；
- `DOC_ALIGNED` 只证明交付资料可进入独立验收，不表示实现正确；
- Acceptance Agent 只报告事实与结论，不修改候选；Documentation Agent 负责策略归类和当前 Gate；
- Product Owner 只处理真实用户结果、风险取舍和发布决定，不替代源码与安全验收；
- 已接受的歧义策略进入 RESULT/HISTORY，并在后续 PLAN 中成为稳定用例，不因新代理或新措辞重复打回。

### 3.10 关键业务不变量治理

V2.3.0 必须防止的不只是某一次越权、错选数据或错误成功，而是“关键业务不变量只存在于需求文字或
开发者记忆中，未进入数据模型、接口约束和最终结果验收”的整类根因。正式 PLAN 必须先建立
`Critical Invariant Register`，再允许新增账号、ApplicationCase、生成入口、后台任务、迁移或兼容链路。

每条关键不变量至少登记：业务含义、可信主体、适用数据和阶段、允许状态、禁止状态、失败策略、
运行时证据以及独立验收方法。最低覆盖账号归属、内容来源、阶段状态、产物发布、权限边界、隐私字段、
权益结算和资源生命周期。

实现与验证必须同时满足以下要求：

1. **让非法状态难以表达**：账号上下文由服务端可信会话产生；用户拥有的数据使用非空账号归属、
   外键/RLS 和必要数据库约束；Repository、Service 和后台任务接口显式接收账号上下文，不保留普通
   业务可调用的全表读取、可选账号过滤或调用方自报 `account_id` 入口。
2. **单一业务真源与单一核心链**：同一生成、迁移或发布能力只能有一个核心服务；旧 API、内部探针和
   兼容入口只能作为薄适配器调用同一核心链，不得各自维护身份、选材、装配或发布规则。
3. **阶段合同与来源账本**：每一阶段显式传递账号、ApplicationCase、源 Experience/Fact、选择快照、
   ResumeRevision 和 ArtifactMetadata 的关联；禁止依赖“本阶段暂时忽略、后续会补齐”的隐式约定。
   服务器内容必须能够反向追溯到输入账号和实际采用的低敏事实记录。
4. **语义失败关闭与原子发布**：身份、来源、结构或阶段状态缺失/冲突时不得降级为 warning 后继续
   `SUCCEEDED`。任务只能在产物完成、来源校验和发布条件全部满足后原子进入成功；失败不能暴露半成品。
5. **用业务结果作为测试 oracle**：核心链最低测试基线必须同时存在两个账号、未归属旧数据、可辨识
   的账号正负哨兵和 Resume Identity/真实实体名称哨兵；测试解析服务器 ResumeRevision 与导出结果，
   证明只有目标账号低敏事实进入，本地字段、其他账号和未归属内容均未进入，并核对来源账本。
   HTTP 200、任务成功、记录存在或模型调用成功均不能单独证明内容正确。
6. **隔离测试与脏环境反证并存**：测试、demo 和迁移工具必须使用独立数据根、数据库和凭据，不能回退
   到真实 runtime；同时必须有专门的脏数据、多身份和遗留记录用例，避免干净单身份 fixture 掩盖边界缺失。
7. **先语义门禁，后昂贵门禁**：账号隔离、来源闭环、状态发布和成品内容断言必须先于完整 build、真实
   模型矩阵、Design Fidelity、性能与打包门禁。基础语义失败时立即停止，不以昂贵门禁通过稀释缺陷。
8. **变更影响可机械复核**：新增入口、聚合、后台任务、迁移或兼容路径时，开发交付必须附关键不变量
   覆盖矩阵，逐项说明其在 schema、接口、运行时校验、结构化证据和负向测试中的落点；缺少任一落点
   不能进入独立验收。

该机制不以“防止测试数据污染”为目标；环境隔离只是其中一层。即使运行库存在其他账号、测试身份、
未归属历史数据或恶意构造 ID，架构本身仍必须保证它们无法进入当前账号的选择、文档与产物链。

### 3.11 向 V2.4.0 交接的生成合同

V2.3.0 不负责完成召回、润色或一页纸算法，但必须避免 V2.4.0 为质量闭环再次重做身份和持久化。
以下对象须具备稳定 ID、版本、账号归属、来源关系和可审计状态：

~~~text
服务器：
JobModelSnapshot
→ EvidenceSelection
→ ResumeContentPlan
→ ResumeRevision（无 Resume Identity / 真实实体名称）
→ LayoutPlan
→ ArtifactMetadata

V2.4.0 本地装配：
Local Resume Identity + Local Entity Map
→ 单一固定模板与固定槽位
→ 冻结最终装配输入
→ final.pdf Blob → PDF.js Preview / PDF Download（同一字节）
→ DOCX Editable Copy（独立副本 writer）
~~~

- `ResumeContentPlan` 保存章节、条目优先级和内容预算，不保存第二份职业事实真源；
- `ResumeRevision` 的每个内容条目保留 `fact_refs` 和 opaque `entity_ref`，不得保存本地真实名称；
- `LayoutPlan` 保存模板版本和全局排版参数；PDF 是唯一视觉真源，Preview 与 PDF 下载必须复用同一
  `final.pdf` Blob，DOCX 只从同一冻结输入生成内容一致的可编辑副本；
- 服务器 `ArtifactMetadata` 只记录无身份内容版本、模板/LayoutPlan 和状态，不持有最终本地文件字节；
- `UsageRecord` 保存阶段、供应商/模型版本、调用、Token、延迟和成本，但不得成为用户按调用扣费依据；
- 上述服务器对象全部继承账号隔离、来源账本、原子发布、删除、备份恢复和负向哨兵验收；V2.4.0
  必须另证浏览器本地装配期间 Resume Identity 与真实实体名称没有网络外发。

V2.3.0 可以只建立最小可用字段和一次 JD-only 纵切，不得伪称已经完成 V2.4.0 的质量冻结。

### 3.12 内部 Alpha 与最小设计范围

- 首轮 Alpha 目标为 3—5 名受邀真实测试者，可使用本人真实经历和真实岗位进行测试；自动化、迁移、
  越权和脏数据反证仍只使用独立环境中的合成数据，不能混入真实账号；
- 真实测试者在进入前必须看到服务器持有字段、Local-only 字段、第三方模型数据流、删除边界和当前
  非公开测试性质，并可要求删除其服务器数据；
- V2.3.0 只新增完成 Alpha 必需的登录/邀请激活、账号状态与退出、简历本地导入/迁移状态、错误与恢复
  状态；沿用已批准工作台，不建设公开官网、营销页、完整运营后台或视觉品牌重做；
- 必要 Design Snapshot 只覆盖上述新增状态和现有工作台的接入关系，不为 V2.4.0 本地成品装配或
  V3.0.0 邀请激活/登录界面提前扩张范围。

## 4. 明确不做

- 不公开注册或接受真实公众流量；
- 不启用充值、订单、支付或订阅；
- 不把 Role Prior、Company Context、召回/润色调优或一页纸质量冻结宣称为本版完成；
- 不开发 Browser Assistant、浏览器扩展、招聘网站读取、字段填充、文件上传或站点 Adapter；
- 不把 Resume Identity、真实实体名称或含这些内容的原始简历/最终文件发送到业务服务器；
- 不建设多人协作编辑、完整移动端、离线 PWA 或任意 Provider/BYOK；
- 不修改 `CURRENT_STATE.md` 把草稿能力写成当前事实。

## 5. Release Train Day 1—3 底座工作流候选

| 阶段 | 重点 | 退出条件 |
|---|---|---|
| Day 1 | PostgreSQL/pgvector、账号上下文、Schema 和迁移纵切 | 双账号事实与向量隔离成立 |
| Day 2 | ApplicationCase、生成公共合同、本地/服务器数据分界、埋点与积分账本 | 一次无身份内部专项任务完整落库 |
| Day 3 | 服务器部署、备份恢复、回滚和反向测试 | 内部 Alpha 核心 Gate 全部可复核 |

Day 3 退出条件是发布列车合并阻断 Gate，不是 V2.3.0 独立验收或发布结论。该节不构成减少测试、
反思或最终独立验收的授权。高风险迁移、RLS、身份清除和文件隔离必须设置开发前证伪、真实纵切后的
Architecture Check 和 V3 候选冻结前 Falsification Check。

## 6. 验收候选

- [ ] 两个账号的 Career Memory、Embedding、Task、ArtifactMetadata 和账本互不可见；
- [ ] 所有账号所有表均为非空 `account_id`，复合外键阻止跨账号引用；应用角色强制 RLS 且不具备
  owner/superuser/`BYPASSRLS` 权限；
- [ ] 若保留旧数据导入，V2.2.0 本地 owner 到目标账号的映射可审计；隔离/未归属/测试身份不被静默
  并入真实账号，且“账号履历 ID → Fact/选择快照 → ResumeRevision/ArtifactMetadata”来源闭环成立；
- [ ] 注入其他账号的已知 ID、Fact ID、Task ID 和 ArtifactMetadata ID 均不能越权；
- [ ] RLS 在普通请求、后台任务、异常回滚和连接池复用后保持有效；
- [ ] 向量查询先按账号过滤，不可能从其他账号召回结果；
- [ ] 两个账号拥有相同文本、近似向量、相同 fingerprint 和已知对方 Embedding ID 时，检索、缓存、
  重建、删除和统计均不跨账号复用或泄漏存在性；
- [ ] PostgreSQL schema 迁移、校验、回滚和失败清理可复核；若 PLAN 保留旧数据导入，另证本地清除、
  用户确认、幂等导入和失败清理；
- [ ] ApplicationCase、JobModelSnapshot 和 ResumeRevision 具备稳定版本关系；
- [ ] ResumeContentPlan、ResumeRevision、LayoutPlan、ArtifactMetadata 和 UsageRecord 的身份、账号与来源关系可复核；
- [ ] 原始简历在本地完成身份/真实实体名称清除，服务器请求、数据库、文件、模型、日志和埋点均无残留；
- [ ] 服务器只接受批准的低敏白名单：允许年月，不保存省/市/大区；白名单外字段 fail closed；
- [ ] Future External Client 字段与 API 可为空且有来源/幂等/授权契约，不存在客户端、DOM 或站点实现；
- [ ] 产品、运行、质量事件分流，正文、Resume Identity 与真实实体名称泄漏为 0；
- [ ] 积分预留、结算、释放和重试幂等，不重复扣减；
- [ ] 服务重启、数据库恢复和部署回滚后账号边界及任务状态正确；
- [ ] 香港内部 Alpha 在 20 个邀请账号/5 个并发任务容量下可排队或限流，月度基础设施成本可核对，
  且 `RPO ≤ 24h`、`RTO ≤ 4h` 恢复演练通过；
- [ ] 鉴权、RLS、身份清除、隐私扫描、埋点、权益与 cleanup 均有预登记歧义矩阵；验收报告的计数、
  逐项结果、观察和最终结论一致，首次失败按完整问题类别一次性返工；
- [ ] `Critical Invariant Register` 覆盖账号归属、内容来源、阶段状态、产物发布、权限、隐私、权益和
  资源生命周期；每条不变量均有 schema/接口强制点、运行时证据和独立负向验收；
- [ ] 双账号、未归属旧数据和正负哨兵同时存在时，服务器 ResumeRevision 只包含目标账号低敏事实，
  且可沿来源账本追溯至 ApplicationCase、选择快照和源 Experience/Fact；
- [ ] V2.2.0 已验收的 owner/当前履历来源、事实链、渐进状态、PDF 预览和下载能力无回归。

## 7. 正式 PLAN 输入状态

Product Owner 范围输入已齐，可以起草正式 PLAN（产物语义另由 D-049 冻结）：

1. 香港单区域内部 Alpha；基础设施经常性月费目标 `≤ RMB 100`，按版本根据证据扩容；
2. 邀请制、非公开注册；V2.3.0 采用管理员发邀请和自建服务端会话，不接 OIDC；
3. 低敏字段按 §3.3 白名单；允许年月，不保存省/市/大区；真实实体和 Resume Identity 继续 Local-only；
4. 3—5 名受邀朋友使用本人真实数据测试；自动化和越权反证使用隔离合成数据；
5. 初始容量 20 个邀请账号、5 个并发生成任务，`RPO ≤ 24h`、`RTO ≤ 4h`；
6. 设计只补 Alpha 必需的登录、账号、导入/迁移、错误与恢复状态。

PLAN 作者仍须把以下技术合同机械化，但不再把它们作为 Product Owner 待选项反复回问：

- PostgreSQL/pgvector 具体版本、迁移、加密离机备份、恢复与回滚命令；
- ResumeContentPlan、LayoutPlan、ArtifactMetadata 和 UsageRecord 的最小字段、版本与状态；
- 各高风险 Gate 的明确允许、明确阻断、不可消歧输入及 fail-open/fail-closed 矩阵；
- `Critical Invariant Register` 的正式字段、维护责任、变更触发条件，以及 schema、接口、运行时证据与
  独立验收覆盖矩阵；
- 香港供应商与实例规格的实现选择；若在安全、恢复或预算约束下不可同时成立，应以证据升级给 Product
  Owner，不得静默削弱隔离、备份或隐私边界。

本文仍为 DRAFT，不单独授权开发；下一步是把本工作流纳入 V3.0.0 Release Train PLAN 与统一验收矩阵。

## 8. PLAN 前技术预演与阻断风险

2026-09-25 对 V2.2.0 候选源码的只读预演显示，当前运行形态仍是 SQLite、固定 owner、loopback
process-token、Web 进程内 daemon thread 和 Windows/Word 本地产物链。V2.3 不是替换数据库连接串；以下
迁移若未写入 Release Train PLAN，Day 3 双账号纵切不可认为可达：

| 级别 | 风险 | PLAN 必须冻结的控制 |
|---|---|---|
| P0 | 旧模型含姓名、邮箱、电话、地点、原文和产物路径，且大量关系没有 `account_id` | 新建 server schema v1 和显式 DTO；禁止把旧 SQLite 或原始简历整体上传；只允许经本地清除后的低敏导入 |
| P0 | 当前固定 owner 与 loopback token 不是互联网账号系统 | 邀请生命周期、Argon2id 密码、服务端 session、Secure/HttpOnly/SameSite Cookie、CSRF、登录限流、会话撤销与管理员辅助重置 |
| P0 | daemon thread 随 Web 进程退出，且锁/状态不跨进程 | PostgreSQL 持久任务表 + 独立 worker；claim/lease/heartbeat/reclaim、阶段幂等和重启恢复；Web 与 worker 使用不同角色 |
| P0 | `SET LOCAL` 只在当前事务有效，而现有服务中途多次 commit | tenant-aware transaction wrapper 在每个事务重设账号上下文；无上下文 fail closed；连接池复用/异常回滚反证 |
| P0 | PostgreSQL 外键/唯一约束检查不等同于 RLS，错误差异可能泄漏其他账号对象存在性 | 所有父子关系使用 `(account_id, id)` 复合键；接口统一不存在/冲突语义，负向测试不得只检查“拿不到正文” |
| P0 | 旧数据自动迁移会把真实身份和实体名称带到服务器 | V3 首发默认不做旧 SQLite 整库迁移；若保留迁移，只能由浏览器本地清除后导入并逐项确认 |
| P1 | 共享近似向量索引可能在账号过滤后降低召回并扩大调参面 | 20 账号首发使用 `account_id` 先过滤的精确向量检索；V3 不启用全局 HNSW/IVFFlat |
| P1 | “5 个并发任务”会放大真实模型调用、成本和供应商限流 | 区分最多 5 个在途/排队任务与初始最多 2 个实际模型任务；记录排队时间、调用/Token/成本并可限流 |
| P1 | 香港实例到第三方模型的延迟、出站和失败率尚未实测 | Day 1 从目标香港实例完成真实模型/Embedding 探针并记录 P50/P95、错误、费用和数据流，不等到 Day 6 |
| P1 | 当前仓库没有 Linux 服务、反向代理、证书、迁移和备份的可复现部署基线 | PLAN 固定镜像/依赖、Web/worker 启停、健康检查、迁移前置、回滚、证书续期和离机备份命令；从干净服务器演练 |
| P1 | SSE 经反向代理可能被缓冲或超时，刷新后重复/丢失事件 | 同源 Cookie 鉴权；关闭事件流缓冲，定义 heartbeat、event id、断线重连和权威快照恢复 |
| P1 | 当前异常日志可能包含完整异常对象，模型/解析错误可能夹带正文 | 结构化错误码与字段白名单；禁止正文/JD/身份/实体/响应体进入日志、埋点和告警；用哨兵扫描验证 |
| P1 | 备份无法对单账号立即物理擦除 | 对外说明活动库 24 小时内删除、备份只随最长 30 天保留期退出；恢复演练必须重放删除墓碑 |

首发不需要对象存储：服务器只保存结构化 Revision 和 ArtifactMetadata；最终 `final.pdf` 与 DOCX
可编辑副本留在浏览器本地，服务器不持有其字节。
单机最小拓扑为反向代理 + Web + worker + PostgreSQL/pgvector + 离机加密备份；不因低预算删除 worker、
RLS、备份恢复或 HTTPS。
