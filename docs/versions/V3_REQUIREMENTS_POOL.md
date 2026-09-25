# AI Career Resume Assistant V3 阶段需求池

> 文档角色：V3 阶段产品、增长与架构候选需求池，供后续版本草稿和 PLAN 选取
> 状态：非版本计划、非开发指令，不改变当前版本状态
> 首次整理：2026-09-19
> 核心方向：从 AI 简历生成器演化为以 Career Memory 为底座的 Job Application Agent
> 当前发布列车：V2.3.0 多用户底座 → V2.4.0 生成质量冻结 → V3.0.0 免费多用户首发

## 1. 使用规则

本需求池保存长期方向和候选能力，不表示 V3.0.0 必须一次完成全部条目。只有被当前版本 DRAFT
选中、经过 Product Owner 批准并写入正式 PLAN 的要求才构成开发指令。

状态标签：

| 标签 | 含义 |
|---|---|
| `V3.0-MUST` | 当前候选首发闭环必须具备，仍需正式 PLAN 批准 |
| `V3.x-CANDIDATE` | 首发后根据真实用户与证据逐步建设 |
| `V2-PREP` | 必须在 V2.3/V2.4 建立底座或证据，否则 V3 无法安全上线 |
| `RESEARCH` | 技术、合规、价值或站点兼容性尚未证实 |
| `OUT` | 当前明确不做或禁止 |

## 2. 总体产品模型

### 2.1 长期定位

`V3.0-MUST`

> 以 Career Memory 为事实底座，围绕用户主动选择的目标岗位完成岗位理解、事实选材、信息补充和
> 可直接投递的一页纸针对性简历；网页表单辅助按证据逐步增加，由用户审核并完成最终提交。

### 2.2 Person Model × Job Model

`V2-PREP` / `V3.0-MUST`

~~~text
Person Model
= 确认的 Profile / Experience / Fact
+ 可重建的标签、Embedding、摘要和 Stable Evidence
+ 不可冒充事实的行为偏好

Job Model
= JD 明示要求
+ Role Prior
+ 有来源的 Company / Business Context
~~~

系统可以依据 Job Model 改变召回、排序和表达重点，不能因此改变用户事实命题。

### 2.3 ApplicationCase

`V2-PREP` / `V3.0-MUST`

一次专项投递是积分、任务、埋点、材料和状态的共同聚合对象，不再把一次 LLM 调用或一个 DOCX
文件当作完整用户价值单位。

## 3. 账号、多用户与服务器

| ID | 需求 | 状态 | 说明 |
|---|---|---|---|
| V3-ACC-01 | 注册、登录、退出、账号恢复 | V3.0-MUST | 正式账号生命周期 |
| V3-ACC-02 | Profile 与 Career Memory 跨设备恢复 | V3.0-MUST | 服务端账号级持久化 |
| V3-ACC-03 | 普通用户、运营、管理员角色分离 | V3.0-MUST | 隐藏入口不算权限隔离 |
| V3-ACC-04 | 账号导出、删除与注销 | V3.0-MUST | 覆盖 SQL、向量、文件、任务和可删除分析关联 |
| V3-ACC-05 | 多人协作编辑同一 Career Memory | OUT | 当前不做 |
| V3-ACC-06 | 社交关系、关注和公开主页 | OUT | 与首发核心价值无关 |

## 4. 数据库、向量与文件隔离

| ID | 需求 | 状态 | 说明 |
|---|---|---|---|
| V3-DATA-01 | PostgreSQL 服务器业务真源 | V2-PREP | 替代服务器模式下活动 SQLite |
| V3-DATA-02 | pgvector 派生向量 | V2-PREP | 与事实同事务边界，暂不增加第二向量系统 |
| V3-DATA-03 | 所有用户数据非空 account_id | V2-PREP | 包括任务、快照、产物、账本和助手会话 |
| V3-DATA-04 | PostgreSQL RLS 默认拒绝 | V2-PREP | 请求、后台任务、连接池和异常路径均验收 |
| V3-DATA-05 | 向量先按账号过滤再排序 | V2-PREP | 跨账号召回容忍度为 0 |
| V3-DATA-06 | 账号级备份、恢复、删除和导出 | V3.0-MUST | SQL、向量和文件边界一致 |
| V3-DATA-07 | production/staging/test 物理隔离 | V2-PREP | 不共享数据库、凭据和文件目录 |
| V3-DATA-08 | 远程独立向量数据库 | RESEARCH | 只有真实规模证明 pgvector 不足时评估 |
| V3-DATA-09 | 账号级文件隔离与短时授权 | V2-PREP | URL 或文件名不能替代权限检查 |

## 5. Career Memory / Person Model

| ID | 需求 | 状态 | 说明 |
|---|---|---|---|
| V3-CM-01 | Experience / Fact 唯一事实源 | V3.0-MUST | 不建立平行用户画像真源 |
| V3-CM-02 | Profile 持久化 | V3.0-MUST | 联系方式和身份字段有独立访问边界 |
| V3-CM-03 | OBSERVED/DERIVED/PROPOSED/CONFIRMED/REJECTED | V2-PREP | 区分事实、派生和待确认内容 |
| V3-CM-04 | 真实任务中发现信息缺口 | V3.0-MUST | 不要求用户先完善数据库 |
| V3-CM-05 | 用户确认后写回 Fact | V3.0-MUST | 未确认只服务当前任务 |
| V3-CM-06 | 冲突不覆盖旧事实 | V3.0-MUST | 用户选择修改、合并或并存 |
| V3-CM-07 | 能力/技能/行业/场景 enrichment | V2-PREP | 带版本、来源、置信度，可重建 |
| V3-CM-08 | 模拟面试驱动 Fact acquisition | V3.x-CANDIDATE | 需单独验证价值和成本 |
| V3-CM-09 | 自动推断后静默写入事实 | OUT | 明确禁止 |

## 6. Job Model 与岗位知识

| ID | 需求 | 状态 | 说明 |
|---|---|---|---|
| V3-JOB-01 | 保存 JD 原文、revision 和来源 | V3.0-MUST | 形成可复现岗位快照 |
| V3-JOB-02 | Role Profile Library v1 | V2-PREP | 首批高频岗位，版本化和人工审核 |
| V3-JOB-03 | Role Prior 补召回 | V2-PREP | 不冒充 JD 硬要求 |
| V3-JOB-04 | Company Context 来源、缓存和 TTL | V2-PREP | 同公司不重复无界研究 |
| V3-JOB-05 | Company Context Recall Booster | V2-PREP | 发现文本相似度较低的业务相关 Fact |
| V3-JOB-06 | Company Context Expression Context | V2-PREP | 改变 emphasis，不改变 proposition |
| V3-JOB-07 | 无边界联网岗位研究 Agent | RESEARCH | 首发只允许批准来源与受控范围 |
| V3-JOB-08 | JobModelSnapshot | V2-PREP | 冻结来源、规则、模型和版本 |

## 7. 基础简历与专项投递

| ID | 需求 | 状态 | 说明 |
|---|---|---|---|
| V3-APP-01 | 免费可投递的一页纸基础简历 | V3.0-MUST | 不故意降质、不加水印或制造事实缺陷 |
| V3-APP-02 | 通用简历作为 Career Memory 展示层 | V3.0-MUST | 事实仍落回 Experience / Fact |
| V3-APP-03 | ApplicationCase 创建与生命周期 | V2-PREP | 一个目标岗位的一次专项准备 |
| V3-APP-04 | JobModelSnapshot + EvidenceSelection | V3.0-MUST | 结果可解释、可复现 |
| V3-APP-05 | 一页纸针对性 Word/PDF | V3.0-MUST | 同一冻结 ResumeRevision/LayoutPlan，真实 Word/PDF 页数均为一页 |
| V3-APP-06 | 投递状态记录 | V3.0-MUST | 稍后、已投、放弃、面试等基础状态 |
| V3-APP-07 | 开放题和网申材料 | V3.x-CANDIDATE | 围绕同一 ApplicationCase |
| V3-APP-08 | 模拟面试 | V3.x-CANDIDATE | 结果和新事实回流需确认 |
| V3-APP-09 | 自动批量海投 | OUT | 不符合用户控制和安全边界 |

## 8. 浏览器插件或等价助手

### 8.1 能力级别

| 级别 | 需求 | 状态 |
|---|---|---|
| L0 | 产品内复制 JD、下载、手工填写和手工上传 | V3.0-MUST |
| L1 | 用户主动读取当前岗位并创建 ApplicationCase | V3.x-CANDIDATE |
| L2 | 展示字段映射，用户确认后填充网页 | V3.x-CANDIDATE |
| L3 | 用户单独确认后选择并上传生成简历 | RESEARCH；证实后按站点启用 |
| L4 | 自动点击最终提交 | OUT |

### 8.2 约束

| ID | 需求 | 状态 | 说明 |
|---|---|---|---|
| V3-AST-01 | 当前标签页或站点 allowlist 最小权限 | V2-PREP | 不申请无边界浏览历史 |
| V3-AST-02 | 岗位读取前预览和确认 | V3.x-CANDIDATE | 提取失败不静默猜测 |
| V3-AST-03 | 字段填充前显示内容、来源和敏感性 | V3.x-CANDIDATE | 用户可逐项取消 |
| V3-AST-04 | 短时 ApplicationCase/Artifact 授权 | V2-PREP | 插件不保存 Provider Key |
| V3-AST-05 | 适配器版本、站点和失败回退 | V3.x-CANDIDATE | DOM 改版 fail closed 到 L0 |
| V3-AST-06 | 密码/Cookie/MFA/验证码采集 | OUT | 禁止 |
| V3-AST-07 | 绕过访问控制或反自动化机制 | OUT | 禁止 |
| V3-AST-08 | 文件自动上传探针 | RESEARCH | 站点、浏览器安全模型和用户确认分别验证 |
| V3-AST-09 | 最终提交由用户完成 | V3.0-MUST | 不后台代投 |
| V3-AST-10 | 适配器更新签名、审计和撤销 | V3.x-CANDIDATE | 任何公开 Beta 前必须完成 |

浏览器助手不是 V3.0.0 首发硬门禁。若某版决定公开 Beta，支持的网站、浏览器和字段只能由正式
PLAN 的能力矩阵确定；“任意官网一键通用”不是可接受的完成标准。

## 9. 召回、润色与性能

| ID | 需求 | 状态 | 说明 |
|---|---|---|---|
| V3-QLT-01 | JD + Role Prior + Company Context 混合召回 | V2-PREP | V2.4.0 调优主线 |
| V3-QLT-02 | 固定评测集与 Recall@K/nDCG | V2-PREP | 反例、长短材料和缺失 JD |
| V3-QLT-03 | Stable Evidence | V2-PREP | 可复用通用成熟表达 |
| V3-QLT-04 | Adaptive Evidence | V2-PREP | 目标岗位差异化内容 |
| V3-QLT-05 | Fast Lane / Precision Lane | V2-PREP | 新能力不线性增加等待 |
| V3-QLT-06 | fact_refs 与事实越界门禁 | V3.0-MUST | 质量提升不能放宽事实边界 |
| V3-QLT-07 | 用户保留率、重生成率和偏好 | V3.0-MUST | 与离线评测互证 |
| V3-QLT-08 | 服务器 P50/P95、cold/warm、缓存矩阵 | V2-PREP | 不把单一样例当性能结论 |
| V3-QLT-09 | ResumeContentPlan | V2-PREP | 冻结章节、优先级和内容预算 |
| V3-QLT-10 | 单一生产模板与 LayoutPlan | V2-PREP | 模板和全局排版参数版本化 |
| V3-QLT-11 | Word 实际渲染与一页纸收敛 | V2-PREP / V3.0-MUST | DOCX/PDF 实测一页，不靠截断或不可读缩字 |
| V3-QLT-12 | 可直接投递成品门禁 | V3.0-MUST | 无占位符、重复、空章节、调试文字或大段人工返工 |
| V3-QLT-13 | 代表性真实岗位人工验收 | V2-PREP / V3.0-MUST | Product Owner 按冻结判分表验收 |
| V3-QLT-14 | V3 后生成合同稳定 | V3.0-MUST | 以后只做权重、检索、润色和有界版式微调 |

## 10. 积分、等级、增长与商业化

| ID | 需求 | 状态 | 说明 |
|---|---|---|---|
| V3-ENT-01 | 基础简历免费 | V3.0-MUST | 保证正常使用下限 |
| V3-ENT-02 | 专项投递消耗积分 | V3.0-MUST | 按 ApplicationCase，不按模型调用 |
| V3-ENT-03 | 不可变权益账本 | V2-PREP | grant/reserve/settle/release/refund/expire |
| V3-ENT-04 | 失败、重试和恢复不重复扣减 | V3.0-MUST | 幂等结算 |
| V3-ENT-05 | 初始赠送和自然恢复 | V3.0-MUST | 具体数量待真实成本冻结 |
| V3-ENT-06 | 积分储存上限 | V3.x-CANDIDATE | 奖励长期关系而非无限日成本 |
| V3-ENT-07 | 弱感知等级 | V3.x-CANDIDATE | 自动升级，不让用户花积分买等级 |
| V3-ENT-08 | Early/Founding User 权益 | V3.x-CANDIDATE | 永久承诺前必须冻结政策 |
| V3-ENT-09 | 签到召回实验 | V3.x-CANDIDATE | 看后续任务和自然留存，不只看签到率 |
| V3-ENT-10 | 有效邀请奖励 | V3.x-CANDIDATE | 需要反作弊与有效用户定义 |
| V3-ENT-11 | 充值、订单和支付 | V3.x-CANDIDATE | V3.0.0 明确不做 |
| V3-ENT-12 | 按 Token 向用户计费 | OUT | Token 只用于内部成本和公平使用 |

## 11. 埋点、实验和运营判断

### 11.1 三类数据

| 类别 | 需求 | 状态 |
|---|---|---|
| 产品事件 | 注册、导入、基础简历、岗位捕获、专项投递、填充、投递状态、回访 | V3.0-MUST |
| 运行遥测 | 延迟、错误、重试、Token、成本、队列、资源、适配器失败 | V2-PREP |
| 质量事件 | 候选、排序版本、保留、重生成、信息补充、用户反馈 | V2-PREP |

### 11.2 原则

- 事件带版本、环境、应用版本、幂等 ID 和账号伪标识；
- 补贴、邀请、签到和测试行为与自然行为分开；
- 不采集密码、Cookie、MFA、验证码、整页 DOM、完整表单、简历/JD 正文和模型完整响应；
- 运营指标不能替代真实结果质量、自然留存或用户人工验收；
- 用户删除和分析保留策略在正式 PLAN 前冻结。

## 12. 隐私、安全与生产运行

| ID | 需求 | 状态 |
|---|---|---|---|
| V3-OPS-01 | HTTPS、稳定域名和安全会话 | V3.0-MUST | Cookie、CSRF、CORS、Host、Origin |
| V3-OPS-02 | Provider Gateway 与服务端密钥管理 | V3.0-MUST | Key 不下发浏览器 |
| V3-OPS-03 | 限流、配额、请求和文件上限 | V3.0-MUST | 免费服务仍需成本控制 |
| V3-OPS-04 | 脱敏日志、监控、告警和审计 | V3.0-MUST | 内容与诊断分离 |
| V3-OPS-05 | 数据库备份、恢复和部署回滚 | V2-PREP | 必须实操，不只写方案 |
| V3-OPS-06 | 正式账号删除和事件响应 | V3.0-MUST | 可验证完成 |
| V3-OPS-07 | 第三方模型数据边界说明 | V3.0-MUST | 与本项目服务端保存分开说明 |
| V3-OPS-08 | 管理后台真实认证与部署隔离 | V3.0-MUST | 普通用户不可见且不可直接访问 |
| V3-OPS-09 | 完整离线 PWA / 本地模型 / BYOK | RESEARCH | 不属于首发必做 |

## 13. PC 与手机

| ID | 需求 | 状态 | 说明 |
|---|---|---|---|
| V3-UI-01 | PC 深度工作台 | V3.0-MUST | Career Memory、岗位和专项投递主流程 |
| V3-UI-02 | Chromium 桌面浏览器助手 | V3.x-CANDIDATE | 不阻断 V3.0.0；公开 Beta 前另冻范围 |
| V3-UI-03 | 手机响应式查看 | V3.x-CANDIDATE | 查看结果、提醒和轻量补充 |
| V3-UI-04 | 手机完整深度编辑工作台 | RESEARCH | 不作为首发目标 |
| V3-UI-05 | 原生移动应用 | RESEARCH | 等真实移动需求证据 |

## 14. 发布列车映射

| 版本 | 从需求池选取的重点 | 不承担 |
|---|---|---|
| V2.3.0 | ACC/DATA 底座、ApplicationCase、账本、埋点、服务器、助手协议 | 公开用户、质量调优、支付 |
| V2.4.0 | Job Model、召回/润色、内容预算、单一模板、真实 Word/PDF 测量和一页纸质量冻结 | 全面公开、支付、插件承诺 |
| V3.0.0 | 免费多用户首发、一页纸基础/专项简历、积分、埋点、数据权利与生产运行 | 支付、自动提交、插件硬依赖 |
| V3.x | 浏览器助手、面试、开放题、更多站点、增长实验、手机轻交互和商业化 | 由真实证据逐版选择 |

## 15. 当前拒绝的扩大解释

- “Job Application Agent”不等于后台自动海投；
- “一键填充”不等于读取密码、Cookie 或绕过验证码；
- “上传简历候选”不等于所有站点都能脚本上传；
- “Job Model”不等于把公司信息或岗位先验写成用户经历；
- “Career Memory 服务端化”不等于全部资料发送给第三方模型；
- “免费”不等于无配额、无成本控制或故意降低结果质量；
- “积分”不等于 V3.0.0 已经接入支付；
- “埋点”不等于收集用户正文和第三方账号秘密；
- “一页纸”不等于静默删减必要事实、裁切内容或使用不可读字号；
- “V3.0.0 首发”不等于必须同时发布浏览器插件；
- “V3 需求池”不等于所有候选已经批准进入 V3.0.0。

## 16. 后续进入正式 PLAN 前的共同输入

1. 首发账号、并发、地域、SLO 和服务器部署目标；
2. 首批 Role Profile、评测集、单一生产模板、一页纸与人工验收阈值；
3. Company Context 批准来源、缓存和失效策略；
4. V2.4.0 生成冻结基线、V3 后可调参数白名单与禁止大改合同；
5. 免费积分、ApplicationCase 有效期和公平使用上限；
6. 直接身份、Career Memory、产物和埋点的保存、导出和删除策略；
7. 正式隐私说明、第三方模型边界和招聘网站辅助提示；
8. 对应版本获批 Design Snapshot；
9. 若某版公开浏览器助手 Beta，再补形态、首批站点、字段与 L2/L3 能力矩阵；
10. 每版开发前风险证伪、真实纵切后的架构复查和冻结前反证合同。

以上内容在 Product Owner 审核并进入对应版本 PLAN 前，均保持 DRAFT/CANDIDATE 语义。
