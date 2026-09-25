# AI Career Resume Assistant V3 阶段需求池

> 文档角色：V3 阶段产品、增长与架构候选需求池，供后续版本草稿和 PLAN 选取
> 状态：非版本计划、非开发指令，不改变当前版本状态
> 首次整理：2026-09-19
> 最近重整：2026-09-25
> 核心方向：以低敏 Career Memory 为服务器底座，以网页本地身份装配交付可投递简历
> 当前发布列车：V2.3.0 底座工作流 ∥ V2.4.0 质量/装配工作流 ∥ V3.0.0 产品工作流 → V3.0.0 统一验收与首发

## 1. 使用规则

只有被当前版本 DRAFT 选中、经过 Product Owner 批准并写入正式 PLAN 的要求才构成开发指令。

| 标签 | 含义 |
|---|---|
| `V3.0-MUST` | 当前候选首发闭环必须具备，仍需正式 PLAN 批准 |
| `V3.x-CANDIDATE` | 首发后根据真实用户与证据逐步建设 |
| `V2-PREP` | 必须在 V2.3/V2.4 建立底座或证据 |
| `POST-V3` | V3.0.0 之后另立版本，当前不冻结具体版本号 |
| `RESEARCH` | 技术、合规或价值尚未证实 |
| `OUT` | 当前明确不做或禁止 |

## 2. 总体产品模型

### 2.1 首发定位

`V3.0-MUST`

> 以服务器低敏 Career Memory 为事实底座，在邀请制 Web Beta 中围绕用户选择的目标岗位完成岗位理解、
> 事实选材、信息补充和一页纸针对性简历；真实身份与真实实体名称只在浏览器本地装配。

### 2.2 三个数据域

`V2-PREP` / `V3.0-MUST`

~~~text
Account / Auth Identity
    仅用于认证和授权

Server Career Memory
    低敏 Experience / Fact / enrichment / Embedding / opaque entity_ref

Local-only
    Local Resume Identity
    Local Entity Map
    final.pdf → PDF.js Preview / PDF Download（同一字节）
    DOCX Editable Copy
~~~

Auth Identity 不得复制成 Resume Identity。用户履历中的真实公司、学校、客户和项目名称不进入
服务器 Career Memory，只保存在本地映射。

### 2.3 Person Model × Job Model

~~~text
Person Model
= 低敏 Experience / Fact
+ 可重建的标签、Embedding、摘要和 Stable Evidence
+ 不可冒充事实的行为偏好

Job Model
= JD 明示要求
+ Role Prior
+ 有来源的 Company / Business Context
~~~

Job Model 只能改变召回、排序和表达重点，不能改变用户事实命题。

## 3. 账号、多用户与服务器

| ID | 需求 | 状态 | 说明 |
|---|---|---|---|
| V3-ACC-01 | 邀请激活、登录、退出、账号恢复 | V3.0-MUST | 首发不开放自由注册 |
| V3-ACC-02 | 低敏 Career Memory 跨设备恢复 | V3.0-MUST | 不包含 Local Resume Identity/Entity Map |
| V3-ACC-03 | 普通用户、运营、管理员角色分离 | V3.0-MUST | 隐藏入口不算权限隔离 |
| V3-ACC-04 | 服务器数据导出、删除与注销 | V3.0-MUST | 只覆盖服务器实际持有数据 |
| V3-ACC-05 | Auth Identity 与业务数据域隔离 | V3.0-MUST | 认证邮箱不得自动成为简历邮箱 |
| V3-ACC-06 | 多人协作编辑同一 Career Memory | OUT | 当前不做 |

## 4. 数据库、向量与元数据隔离

| ID | 需求 | 状态 | 说明 |
|---|---|---|---|
| V3-DATA-01 | PostgreSQL 服务器业务真源 | V2-PREP | 服务器模式不保留活动 SQLite 真源 |
| V3-DATA-02 | pgvector 派生向量 | V2-PREP | 从低敏 Fact 重建 |
| V3-DATA-03 | 所有业务数据非空 account_id | V2-PREP | 任务、快照、元数据、账本均覆盖，父子关系使用账号维度复合外键 |
| V3-DATA-04 | PostgreSQL RLS 默认拒绝 | V2-PREP | 应用角色 FORCE RLS 且无 BYPASSRLS；请求、后台任务、连接池和异常路径验收 |
| V3-DATA-05 | 向量账号内派生与检索 | V2-PREP | 与 Fact 同账号外键；先按账号过滤再排序，禁止跨账号去重/缓存，跨账号召回容忍度为 0 |
| V3-DATA-06 | 服务器备份、恢复、删除和导出 | V3.0-MUST | 不声称恢复本地身份/文件 |
| V3-DATA-07 | production/staging/test 物理隔离 | V2-PREP | 不共享数据库、凭据和文件目录 |
| V3-DATA-08 | 低敏来源片段和元数据隔离 | V2-PREP | 原始身份简历和最终文件不上服务器 |
| V3-DATA-09 | 远程独立向量数据库 | RESEARCH | pgvector 不足时再评估 |

## 5. Career Memory

| ID | 需求 | 状态 | 说明 |
|---|---|---|---|
| V3-CM-01 | Experience / Fact 唯一服务器事实源 | V3.0-MUST | 不建立平行业务画像真源 |
| V3-CM-02 | opaque entity_ref | V2-PREP | 维持经历归属，不保存真实名称 |
| V3-CM-03 | 低敏字段白名单 | V2-PREP | 学校/学历/宽口径专业、企业类型、岗位族、年月、技能场景及去专名成果；省/市/大区首版不保存 |
| V3-CM-04 | OBSERVED/DERIVED/PROPOSED/CONFIRMED/REJECTED | V2-PREP | 区分事实、派生和待确认内容 |
| V3-CM-05 | 真实任务中发现信息缺口 | V3.0-MUST | 不要求用户先完善数据库 |
| V3-CM-06 | 用户确认后写回低敏 Fact | V3.0-MUST | 未确认只服务当前任务 |
| V3-CM-07 | 冲突不覆盖旧事实 | V3.0-MUST | 用户选择修改、合并或并存 |
| V3-CM-08 | 能力/技能/行业/场景 enrichment | V2-PREP | 带版本、来源、置信度，可重建 |
| V3-CM-09 | 模拟面试驱动 Fact acquisition | V3.x-CANDIDATE | 需独立验证价值和成本 |
| V3-CM-10 | 自动推断后静默写入事实 | OUT | 明确禁止 |

## 6. Job Model 与岗位知识

| ID | 需求 | 状态 | 说明 |
|---|---|---|---|
| V3-JOB-01 | 保存 JD、revision 和来源 | V3.0-MUST | JD 是岗位数据，不是本地身份 |
| V3-JOB-02 | Role Profile Library v1 | V2-PREP | 首批高频岗位，版本化和人工审核 |
| V3-JOB-03 | Role Prior 补召回 | V2-PREP | 不冒充 JD 硬要求 |
| V3-JOB-04 | Company Context 来源、缓存和 TTL | V2-PREP | 同公司不重复无界研究 |
| V3-JOB-05 | Company Context Recall Booster | V2-PREP | 发现低文本相似度的业务相关 Fact |
| V3-JOB-06 | Company Context Expression Context | V2-PREP | 改变 emphasis，不改变 proposition |
| V3-JOB-07 | 无边界联网岗位研究 Agent | RESEARCH | 只允许批准来源与受控范围 |
| V3-JOB-08 | JobModelSnapshot | V2-PREP | 冻结来源、规则、模型和版本 |

## 7. ApplicationCase、基础简历与专项简历

| ID | 需求 | 状态 | 说明 |
|---|---|---|---|
| V3-APP-01 | 免费可投递的一页纸基础简历 | V3.0-MUST | 不故意降质、不加水印 |
| V3-APP-02 | ApplicationCase 创建与生命周期 | V2-PREP | Web 端粘贴 JD/输入岗位信息 |
| V3-APP-03 | JobModelSnapshot + EvidenceSelection | V3.0-MUST | 可解释、可复现 |
| V3-APP-04 | ResumeContentPlan + ResumeRevision + LayoutPlan | V2-PREP | 服务器内容不含本地字段 |
| V3-APP-05 | 本地一页 PDF Preview/Download + DOCX 可编辑副本 | V3.0-MUST | PDF 为唯一视觉真源 |
| V3-APP-06 | ApplicationCase 状态与历史 | V3.0-MUST | 再次下载为重新本地装配 |
| V3-APP-07 | 投递状态记录 | V3.0-MUST | 已下载、已投、放弃、面试等 |
| V3-APP-08 | 开放题和网申材料 | V3.x-CANDIDATE | 围绕同一 ApplicationCase |
| V3-APP-09 | 自动批量海投 | OUT | 不符合用户控制和安全边界 |

## 8. Local Resume Identity、Entity Map 与方案 B

| ID | 需求 | 状态 | 说明 |
|---|---|---|---|
| V3-LOC-01 | Local Resume Identity | V2-PREP / V3.0-MUST | 姓名、电话、联系邮箱、地址、个人链接等 |
| V3-LOC-02 | Local Entity Map | V2-PREP / V3.0-MUST | entity_ref 到用户履历公司/学校/客户/项目真实名称 |
| V3-LOC-03 | 原始简历本地处理 | V3.0-MUST | 去除身份/真实实体名后才发送结构化事实 |
| V3-LOC-04 | 单一生产模板与固定槽位 | V2-PREP | 真实字段只进入批准槽位 |
| V3-LOC-05 | 桌面 Chromium 本地装配 | V2-PREP / V3.0-MUST | final.pdf 与 DOCX 副本只在设备生成 |
| V3-LOC-06 | 本地敏感存储 | V2-PREP | IndexedDB/OPFS + WebCrypto；禁止明文 localStorage |
| V3-LOC-07 | 换设备重新输入 | V3.0-MUST | 首发不通过服务器同步本地字段 |
| V3-LOC-08 | 超长字段本地简写 | V3.0-MUST | 不截断、不上传原值 |
| V3-LOC-09 | 本地文件不回传 | V3.0-MUST | Blob/Object URL 下载，服务器只存元数据 |
| V3-LOC-10 | XSS/依赖/出站负向门禁 | V3.0-MUST | 本地化不等于天然安全 |
| V3-LOC-11 | 用户自管本地导入/导出 | V3.x-CANDIDATE | 首发先重新输入 |

PDF 是唯一视觉真源：浏览器从冻结输入只生成一次 `final.pdf` Blob，PDF.js Preview 与 PDF Download
复用同一字节。DOCX 从同一冻结输入生成内容一致、可编辑、ATS 友好的副本，不承诺一页、像素级同版、
反向还原 PDF 或由办公软件另存为同一 PDF。

## 9. 召回、润色、一页纸与性能

| ID | 需求 | 状态 | 说明 |
|---|---|---|---|
| V3-QLT-01 | JD + Role Prior + Company Context 混合召回 | V2-PREP | V2.4.0 调优主线 |
| V3-QLT-02 | 固定评测集与 Recall@K/nDCG | V2-PREP | 反例、长短材料和缺失 JD |
| V3-QLT-03 | Stable / Adaptive Evidence | RESEARCH | 有正收益证据后再进入首发候选 |
| V3-QLT-04 | Fast / Precision Lane | RESEARCH | 首发默认单通道，不为机制牺牲质量死线 |
| V3-QLT-05 | fact_refs 与事实越界门禁 | V3.0-MUST | 质量提升不能放宽事实边界 |
| V3-QLT-06 | ResumeContentPlan 与内容预算 | V2-PREP | 为本地槽位预留空间 |
| V3-QLT-07 | PDF 一页且 Preview/Download 同字节 | V2-PREP / V3.0-MUST | DOCX 仅按可编辑副本合同验收 |
| V3-QLT-08 | 可直接投递成品门禁 | V3.0-MUST | 无占位符、重复、空章节或大段返工 |
| V3-QLT-09 | 代表性真实岗位人工验收 | V2-PREP / V3.0-MUST | Product Owner 按冻结判分表验收 |
| V3-QLT-10 | 服务器与本地 P50/P95 | V2-PREP | cold/warm、缓存、装配和成本矩阵 |
| V3-QLT-11 | V3 后生成合同稳定 | V3.0-MUST | 以后只做权重、检索、润色和有界版式微调 |

## 10. 积分、增长与商业化

| ID | 需求 | 状态 | 说明 |
|---|---|---|---|
| V3-ENT-01 | 基础简历免费 | V3.0-MUST | 保证正常使用下限 |
| V3-ENT-02 | 专项 ApplicationCase 消耗积分 | V3.0-MUST | 新账号 10 分；新任务 1 分；失败/同任务恢复/下载不重复扣减 |
| V3-ENT-03 | 不可变权益账本 | V2-PREP | grant/reserve/settle/release/refund/expire |
| V3-ENT-04 | 重试、恢复和本地重装配不重复扣减 | V3.0-MUST | 幂等结算 |
| V3-ENT-05 | 新账号初始赠送 | V3.0-MUST | 新账号 10 积分 |
| V3-ENT-06 | 周期恢复、签到和 Early User 额外赠送 | POST-V3-CANDIDATE | V3 首发不启用自动恢复 |
| V3-ENT-06 | 弱感知等级、签到、邀请 | V3.x-CANDIDATE | 由真实留存证据决定 |
| V3-ENT-07 | 充值、订单和支付 | V3.x-CANDIDATE | V3.0.0 明确不做 |
| V3-ENT-08 | 按 Token 向用户计费 | OUT | Token 只用于内部成本和公平使用 |

## 11. 埋点、实验和运营判断

| 类别 | V3.0.0 范围 | 禁止内容 |
|---|---|---|
| 产品事件 | 注册、导入、基础简历、ApplicationCase、最终内容、本地装配、下载、状态、回访 | 正文、本地字段、文件 |
| 运行遥测 | 延迟、错误、重试、Token、成本、队列、资源 | Prompt、模型完整响应、密钥 |
| 质量事件 | 候选、排序版本、保留、重生成、信息补充、脱敏页数/失败类别 | 真实名称、DOM、截图、原始长度组合 |

- 事件带版本、环境、应用版本、幂等 ID 和账号伪标识；
- 补贴、邀请和测试行为与自然行为分开；
- 用户删除和分析保留策略在正式 PLAN 前冻结；
- 运营指标不能替代真实成品质量和人工验收。

## 12. 隐私、安全与生产运行

| ID | 需求 | 状态 | 说明 |
|---|---|---|---|
| V3-OPS-01 | HTTPS、稳定域名和安全会话 | V3.0-MUST | Cookie、CSRF、CORS、Host、Origin |
| V3-OPS-02 | Provider Gateway 与服务端密钥管理 | V3.0-MUST | Key 不下发前端 |
| V3-OPS-03 | 限流、配额、请求和任务上限 | V3.0-MUST | 免费服务仍需成本控制 |
| V3-OPS-04 | 脱敏日志、监控、告警和审计 | V3.0-MUST | 内容与诊断分离 |
| V3-OPS-05 | 数据库备份、恢复和部署回滚 | V2-PREP | 必须实操 |
| V3-OPS-06 | 正式账号删除和事件响应 | V3.0-MUST | 可验证完成 |
| V3-OPS-07 | 第三方模型数据边界说明 | V3.0-MUST | 与服务器持久化分开说明 |
| V3-OPS-08 | 管理后台真实认证与部署隔离 | V3.0-MUST | 普通用户不可见且不可访问 |
| V3-OPS-09 | 前端 CSP、依赖完整性和出站控制 | V3.0-MUST | 防止本地字段被网页代码外传 |
| V3-OPS-10 | 完整离线 PWA / 本地模型 / BYOK | RESEARCH | 不属于首发必做 |

## 13. PC 与手机

| ID | 需求 | 状态 | 说明 |
|---|---|---|---|
| V3-UI-01 | PC 深度工作台 | V3.0-MUST | Career Memory、岗位和生成主流程 |
| V3-UI-02 | 桌面 Chromium 本地文件装配 | V3.0-MUST | 具体版本由 PLAN 冻结 |
| V3-UI-03 | 手机响应式查看 | V3.x-CANDIDATE | 查看结果、提醒和轻量补充 |
| V3-UI-04 | 手机完整文件装配/深度编辑 | RESEARCH | 不作为首发目标 |
| V3-UI-05 | 原生移动应用 | RESEARCH | 等真实需求证据 |

## 14. Post-V3 Browser Assistant

Browser Assistant、招聘网站读取、字段填充、站点 Adapter 和用户确认后的文件上传统一标记
`POST-V3`，不属于 V2.3.0、V2.4.0 或 V3.0.0。

V2.3.0 只预留 ApplicationCase.source、source URL/type、external client type、nullable session/adapter、
幂等、授权、来源审计和 Artifact 获取合同。Capability not implemented; integration contract reserved.

自动提交、密码/Cookie/MFA/验证码采集和绕过站点控制仍为 `OUT`。

## 15. 并行发布列车映射

| 工作流 | 从需求池选取的重点 | 不承担 |
|---|---|---|
| V2.3 底座 | 多用户底座、低敏 Career Memory、可选本地清除后导入、ApplicationCase、权益/埋点/部署、外部客户端合同 | 生成质量冻结、Browser Assistant |
| V2.4 质量/装配 | Job Model、召回/润色、Stable/Adaptive、Fast/Precision、方案 B 本地装配、质量 Beta | 支付、Browser Assistant |
| V3 产品 | 免费多用户首发、基础/专项简历、账号体验、历史、权益、埋点和生产运行 | 支付、Browser Assistant |
| V3 统一验收 | 上述三条工作流的隔离、质量、一页纸、产品和生产硬 Gate | 不接受模块证据代替真实完整纵切 |
| Post-V3 | Browser Assistant、招聘网站集成、字段填充、确认上传 | 具体版本另行冻结 |

V2.3/V2.4 不单独发布或独立验收。Day 3/Day 6 是合并阻断 Gate；只有冻结的 V3.0.0 候选进入独立
Acceptance，且必须一次覆盖全部工作流。

## 16. 当前拒绝的扩大解释

- “Career Memory 服务端化”不等于保存 Resume Identity、真实实体名称或原始身份简历；
- “Local-only”不等于网页天然安全，前端代码和出站网络必须独立验收；
- “一页纸”不等于静默删减事实、裁切或不可读缩字；
- “免费”不等于无配额、无成本控制或故意降低结果质量；
- “积分”不等于 V3.0.0 已接入支付；
- “外部客户端合同”不等于 Browser Assistant 已经实现；
- “V3 需求池”不等于所有候选已经批准。

## 17. Release Train PLAN 共同输入状态

D-043—D-049 已冻结发布方式、账号/并发/地域、低敏白名单、质量集范围和硬线、真实测试者、积分、
Company Context 来源、保留/删除目标、模板与设计基底。PLAN 负责补齐运行 SLO、公平使用限流、确切
评测样本、模板/槽位、浏览器/PDF 字体、DOCX 副本兼容、本地存储与生成器、第三方模型说明、服务器/备份实现、Design
Snapshot，以及开发前证伪、真实纵切架构复查和冻结前反证合同。

以上内容在正式 PLAN 获批前仍保持 DRAFT/CANDIDATE 语义。

## 18. 九天首发技术收敛（D-048 Accepted）

源码预演确认 V3 不是在 V2.2 上直接换数据库和部署方式：真实账号、PostgreSQL/RLS、持久 worker、浏览器
本地清除、单一 `final.pdf` 与 DOCX 副本、BASE/TARGETED 双任务合同均需要新的完整纵切。为保护生成效果、一页纸、
多用户隔离和埋点死线，D-048 已冻结七项收敛：文本层 PDF/手工输入、单生成通道、不建对象存储、
5 在途/2 执行、不自动整库迁移、最小运维入口、首发不启用自动积分恢复。正式 PLAN 必须直接按此编排；
未经新决策不得恢复后置机制。
