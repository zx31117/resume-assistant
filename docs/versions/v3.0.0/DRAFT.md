# AI Career Resume Assistant V3.0.0 草稿：网页本地优先与模型服务平台

> 文档角色：远期产品与架构草稿，供用户审核
> 状态：DRAFT，非开发指令，不改变当前版本状态
> 草稿日期：2026-08-19
> 假定前置：V1.5.0 完成事实级内容决策与本地索引收束，V2 完成相关性、生成和排版体验优化
> 核心方向：网页/PWA 提供产品界面，用户履历默认保存在用户浏览器；服务端提供账号、额度、LLM、Embedding 和必要的无持久化计算服务

## 1. 核心判断

V3.0.0 不采用“服务器保存每个用户完整履历和向量库”的传统 SaaS 作为默认方案，而采用网页本地优先架构：

- 用户的 Profile、Experience、Fact、Embedding 和生成记录默认保存在当前设备的浏览器本地数据库；
- 浏览器本地完成履历 CRUD、硬规则预筛、向量检索和事实边界校验；
- 服务端保存账号、订阅、额度和必要的非内容型运行元数据；
- 服务端按请求临时处理 Embedding、LLM 改写和初期 DOCX 渲染，不长期保存用户履历正文；
- V3.0.0 在 V2 本地管理员模型/API 配置的基础上，提供账号级、权限隔离的供应商配置，兼容云端和本地模型；
- 本地优先表示“用户资料不进入本项目的长期云端资料库”，不表示调用云端模型时文本永远不离开设备。

产品体验应接近“通过网址打开的本地应用”：用户无需安装传统客户端，打开固定域名即可继续使用当前浏览器内的职业资料库。

## 2. 目标用户体验

### 2.1 首次使用

~~~text
访问固定 HTTPS 域名
→ 登录服务账号或进入本地访客模式
→ 创建与当前账号绑定的本地 Vault
→ 请求浏览器持久化存储
→ 导入简历 PDF 或手工录入经历
→ AI 提取后由用户确认
→ 保存 Experience / Fact / Embedding 到浏览器本地 SQLite
→ 提醒导出首份加密备份
~~~

页面必须明确说明：

1. 哪些数据只保存在当前设备和当前浏览器；
2. 哪些内容会在调用云端 AI 时临时发送；
3. 换设备、换浏览器、换域名或清除站点数据不会自动恢复本地资料；
4. 用户应通过导出备份或未来可选同步恢复资料。

### 2.2 日常生成

~~~text
打开网页 → 读取本地资料库
→ 粘贴 JD
→ 本地预筛和事实级向量检索
→ 形成自包含 SelectedEvidenceSet
→ 只发送 JD + 入选事实给 LLM 服务
→ 返回带 fact_refs 的 bullets
→ 浏览器回查本地事实并验证边界
→ Builder / Renderer 生成 DOCX
→ 输出和任务记录保存在本地
~~~

页面应显示本次数据使用范围，例如“本次从 126 条本地事实中选择 12 条发送给 AI 服务”。

### 2.3 离线、换设备与退出账号

- 离线时允许查看和编辑本地 Profile / 履历、管理备份；需要云端模型的功能进入待处理状态；
- 如用户配置本地模型，可在其能力允许时完成离线 Embedding 和 LLM 调用；
- 同一账号在新设备登录后默认没有履历，需要导入备份；V3.0.0 初始版本不默认提供云端履历同步；
- 退出账号只锁定当前本地 Vault，不自动删除本地资料；删除账号和删除本地 Vault 是两个明确操作；
- 同一浏览器切换账号时，不得自动打开上一账号的 Vault。

## 3. 总体架构

~~~text
┌──────────────────────── 用户浏览器 / PWA ────────────────────────┐
│                                                                  │
│  UI                                                              │
│   ↓                                                              │
│  Local Vault                                                     │
│  SQLite WASM + OPFS（单一客户端事实库）                           │
│  ├── user_profile                                                │
│  ├── experiences                                                 │
│  ├── experience_facts                                            │
│  ├── fact_embeddings                                             │
│  ├── vector_index_jobs                                           │
│  ├── generation_tasks                                            │
│  └── local_settings / schema_version                             │
│   ↓                                                              │
│  本地预筛 → 本地精确向量检索 → SelectedEvidenceSet → 本地边界复核 │
│                                                                  │
└───────────────────────────┬──────────────────────────────────────┘
                            │ HTTPS；最小必要数据
                            ↓
┌──────────────────────── 无履历持久化服务 ────────────────────────┐
│  账号 / 订阅 / 额度 / 幂等状态                                   │
│  Embedding Provider Gateway                                      │
│  LLM Provider Gateway                                            │
│  初期 PDF 解析 / DOCX 渲染                                       │
│  非内容型监控与安全审计                                          │
└───────────────────────────┬──────────────────────────────────────┘
                            ↓
               云端供应商 / 用户本地模型 Endpoint
~~~

## 4. 数据事实所有权

| 数据 | V3.0.0 事实源 | 服务端长期保存 | 说明 |
|---|---|---|---|
| 账号、订阅、额度 | 服务端账号库 | 是 | 不包含履历正文 |
| 姓名、电话、邮箱、所在地 | 浏览器本地 Profile | 否 | UI 每次生成时展示并作为 request 明确提交 |
| 完整职业履历 | 浏览器本地 Experience / Fact | 否 | 用户长期资产 |
| 求职意向 | 当前 JD 或用户本次明确指定 | 否 | 不进入稳定 Profile |
| Embedding | 浏览器本地 fact_embeddings | 否 | 派生索引，可重建 |
| JD | 浏览器本地当前任务 | 否 | 发送模型时临时处理 |
| SelectedEvidenceSet | 浏览器本地决策结果 | 否 | 是客户端—服务端的事实约束包 |
| 生成 bullets | 模型返回后由浏览器校验 | 否 | 每条必须携带 fact_refs |
| DOCX / PDF 输出 | 浏览器下载或本地记录 | 否 | 服务端渲染时只允许短期临时处理 |
| 请求状态、计费和幂等信息 | 服务端 | 是，最小化 | 默认不包含请求正文 |

用户选择云端供应商时，供应商仍会收到完成该次任务所需的文本。产品必须分别说明“本项目是否长期保存”和“第三方模型如何处理请求数据”，不得把两者混为一谈。

## 5. 浏览器本地资料库

### 5.1 存储方案

V3.0.0 首选 SQLite WASM + Origin Private File System（OPFS）：

- SQLite 继续承担结构化事实、任务状态、向量 BLOB 和 Schema 迁移；
- SQLite 运行在 Web Worker，UI 不直接操作数据库；
- OPFS 保存数据库文件；
- 页面请求 `navigator.storage.persist()` 并展示实际授权状态；
- 稳定正式域名一旦承载真实用户数据，不轻易改变协议、域名或端口；
- `localStorage` 只可保存少量非敏感 UI 状态，不保存履历、向量或 API Key。

### 5.2 本地表草案

~~~text
local_vaults
  vault_id, account_subject, created_at, locked_at

user_profile
  vault_id, name, phone, email, location, updated_at

experiences
  experience_id, vault_id, type, title, company, time, raw_text, ...

experience_facts
  fact_id, experience_id, fact_type, source_text, source_hash, ...

fact_embeddings
  fact_id, embedding_fingerprint, dimensions, vector_blob, source_hash, updated_at

vector_index_jobs
  job_id, fact_id, operation, status, retry_count, error_code, ...

generation_tasks
  task_id, request_hash, status, provider, created_at, completed_at, ...

local_meta
  schema_version, app_version, active_embedding_fingerprint, backup_state
~~~

V3.0.0 不在浏览器中引入第二套长期向量存储。向量和事实处于同一 SQLite 文件，但向量仍是可重建派生数据，不改变 Experience / Fact 的事实源地位。

### 5.3 本地检索

- 数据规模预期为几百至几千 Fact，默认使用精确余弦检索；
- 计算放入 Web Worker，不能阻塞页面主线程；
- 向量以 float32 BLOB 保存，查询时转换为 TypedArray；
- 预筛先减少候选集合，再计算语义相似度；
- V3.0.0 不默认引入远程向量数据库；只有真实规模和性能证据证明需要时才评估额外索引。

### 5.4 Fact 与向量一致性

每条向量至少记录：

- `fact_id`；
- `source_hash`；
- `embedding_fingerprint`；
- `dimensions`；
- 生成状态和时间。

检索时，Fact 当前 `source_hash` 与向量记录不一致即视为 STALE，不允许静默使用旧向量。Embedding 调用失败时保留事实并记录待重试任务，不伪装成索引成功。

切换 Embedding 模型时：

~~~text
验证新供应商能力
→ 生成新 fingerprint
→ 全量重建到新索引世代
→ 全部完成并核验维度/数量
→ 原子切换 active fingerprint
→ 旧向量进入可清理状态
~~~

不同模型生成的向量禁止混合检索，即使维度相同。

## 6. 客户端—服务端事实边界

V1 当前通过“RAG ID 回服务端 SQL”确认事实。V3.0.0 服务端没有用户 SQL，因此必须改为自包含事实包：

~~~text
SelectedEvidenceSet / EvidenceBundle
├── experience_id
├── fact_id
├── source_text
├── source_hash
├── selection_reason
├── expression_focus
└── 本次允许的变换边界
~~~

服务端只允许：

- 根据 Bundle 内事实进行压缩、重组和针对 JD 的表达；
- 返回已知 `experience_id` / `fact_id`；
- 在材料不足时显式失败或返回缺口。

服务端不得：

- 查询不存在的云端履历补全事实；
- 使用未包含在 Bundle 中的历史用户信息；
- 为了完整性新增身份信息、项目、指标或结果。

浏览器收到响应后必须再次核对所有 fact_refs 和来源映射。未知 ID、无来源 bullet 或越界结果丢弃并告警。客户端本地 SQL 是 V3.0.0 的最终事实校验点。

## 7. 服务端职责与无履历持久化约束

### 7.1 服务端保留能力

- 账号、登录、订阅、额度和计费；
- 请求鉴权、限流和滥用防护；
- LLM / Embedding Provider Gateway；
- 幂等请求状态和必要的短期恢复能力；
- 初期无持久化 PDF 解析与 DOCX 渲染；
- 不含正文的耗时、token、错误码和健康监控。

### 7.2 禁止隐性留存

“业务数据库不保存”不足以证明没有留存。V3.0.0 必须检查完整链路：

- CDN、反向代理和 API Gateway 不记录正文；
- 应用日志、异常堆栈和 APM 不打印 Prompt、JD 或履历；
- 响应使用合适的 `Cache-Control`，避免代理缓存用户内容；
- 临时 PDF / DOCX 使用隔离随机目录，成功、失败和异常退出后均可清理；
- 消息队列、重试系统和备份不能无期限保存正文；
- 服务端幂等状态默认保存 request hash、状态和计费结果，不保存完整请求；
- 如为长任务恢复而短期保存加密内容，必须定义明确 TTL、删除验证和用户提示。

## 8. LLM / Embedding 供应商能力

### 8.1 V3.0.0 用户目标

V2 已为本地管理员提供受支持供应商、模型和兼容 Endpoint 的图形化配置。V3.0.0 将该能力迁移为账号级设置，并补齐权限隔离、额度、平台 Provider Gateway、云端 BYOK 与跨设备安全边界。业务链路继续只依赖统一 Provider 契约，不能直接依赖具体供应商 SDK、请求格式或响应结构。

内部统一契约：

~~~text
LLMProvider
  health_check
  generate_text
  generate_structured
  capabilities

EmbeddingProvider
  health_check
  embed_documents
  embed_query
  fingerprint
  capabilities
~~~

### 8.2 接入模式

| 模式 | 调用路径 | Key 位置 | 适用场景 |
|---|---|---|---|
| 平台模型 | 浏览器 → 本项目服务 → 供应商 | 服务端 | 默认付费服务 |
| 本地模型 | 浏览器 → localhost / 局域网兼容 Endpoint | 用户设备 | 完全本地或自有算力 |
| BYOK 云端 | 浏览器直连或经无持久化代理 | 待定 | 取决于 CORS、鉴权和安全策略 |

“任意供应商即填即用”是用户目标，不等于任意私有协议天然兼容：

- OpenAI-compatible Endpoint 可优先作为通用入口；
- 非兼容供应商必须由对应 Adapter 支持；
- UI 只展示已经通过能力检测的功能；
- 不支持结构化输出的 LLM 使用 Prompt + Schema 校验和有限重试，仍不满足契约时显式失败；
- 不允许为了兼容供应商恢复关键阶段的空模型兜底。

### 8.3 Key 安全

- 平台供应商 Key 永远不下发浏览器；
- 用户自带 Key 不写入 `localStorage`；
- 浏览器长期保存 BYOK 时需要口令派生密钥加密、解锁和遗忘处理，具体方案在正式 PLAN 前确认；
- 浏览器直连受 CORS 和供应商协议限制，不能把所有供应商都设计成前端直接请求；
- 页面发生 XSS 时，已经解锁的 Key 和本地数据仍可能被窃取，因此加密不能代替 CSP、输入转义和供应链防护。

## 9. PDF 与 DOCX 处理

V3.0.0 初期优先复用已验证的 Python 能力：

~~~text
PDF → 无持久化解析服务 → 返回文本/结构
ResumeDocument → 无持久化渲染服务 → 返回 DOCX bytes
~~~

服务端不得把上传 PDF 和生成 DOCX 写入长期用户目录。临时处理必须有失败清理、进程异常清理和日志审计。

后续是否将 PDF 文本解析或 DOCX 生成迁入浏览器，取决于隐私、兼容性和排版验证，不作为 V3.0.0 初始网页化的前置条件。

## 10. 浏览器生命周期与版本升级

### 10.1 Origin 约束

浏览器数据绑定协议、域名和端口。正式承载数据前必须确定稳定 HTTPS origin。域名迁移、`www` / 非 `www` 切换、子域调整或端口变化，都需要显式导出/导入迁移方案。

### 10.2 Schema 与前端版本

- 本地数据库保存 `schema_version`；
- Schema 迁移必须在事务中执行，破坏性迁移前创建可恢复备份；
- 旧前端不得修改已被新版本升级的数据库；
- 新前端不得静默破坏无法识别的旧数据；
- PWA / Service Worker 检测到数据库迁移时提示用户保存并重新加载，不强制在旧标签页仍运行时激活；
- 发布回滚必须说明是否支持回退数据库 Schema。

### 10.3 多标签页

- SQLite 运行于 Worker；
- 使用浏览器锁或消息机制协调多个标签页；
- V3.0.0 初始版本同一 Vault 只允许一个编辑标签页，其他标签页只读；
- 遇到锁冲突显示明确提示，不进行无限自动重试；
- 关闭、崩溃和异常终止后能够恢复锁状态。

## 11. 备份、恢复与跨设备

V3.0.0 初始版本采用本地备份，不默认保存云端履历：

- 导出包含 Profile、Experience、Fact、设置和 Schema 版本；
- 向量是派生数据，可选择不备份并在恢复后重建；
- 备份默认加密，恢复前验证格式、版本、校验和与解密口令；
- 恢复采用“导入到新 Vault → 校验 → 切换”，不能直接覆盖唯一现有数据库；
- 首次完成履历录入后提醒备份；长期未备份时显示状态；
- 新设备登录只恢复账号权益，不自动出现履历，用户通过备份导入；
- 可选端到端加密同步属于后续能力，需单独处理密钥恢复、冲突合并和服务端不可读验证。

## 12. 安全要求

- Vault 页面使用严格 Content Security Policy；
- 用户 PDF、JD、履历和模型输出统一按不可信输入处理；
- 不使用 `innerHTML` 直接渲染用户或模型文本；
- 尽量不在 Vault 页面加载第三方分析、广告或客服脚本；
- 前端依赖锁定并进行供应链扫描；
- 账号会话优先使用安全、HttpOnly、SameSite Cookie；
- 服务端执行 CSRF、CORS、速率限制、配额和请求大小限制；
- 本地 Vault 与登录账号严格隔离，防止共享设备串库；
- 本地数据库加密只能降低静态文件泄露风险，不能防止页面在已解锁时被恶意脚本读取；
- 隐私说明必须列出本项目服务和第三方模型各自的数据处理边界。

## 13. 可靠性与高风险场景

| 场景 | 预期行为 |
|---|---|
| 浏览器拒绝 persistent storage | 明确提示风险，仍可使用但要求导出备份 |
| 用户清除站点数据 | 无法自动恢复；通过备份恢复，不声称服务器有副本 |
| 同一浏览器切换账号 | 锁定原 Vault，新账号不得读取 |
| 两个标签页同时编辑 | 一个可写，其余只读或明确报锁冲突 |
| Fact 已保存但 Embedding 失败 | Fact 保留，向量 STALE/FAILED，不使用旧向量 |
| Embedding 模型改变 | 全量重建并原子切换，禁止新旧混用 |
| LLM 请求成功但响应丢失 | 通过幂等键查询状态，不重复计费或重复执行 |
| 前端更新包含 Schema 迁移 | 备份、事务迁移、旧标签页阻止写入 |
| 服务端渲染失败 | 返回明确错误，临时文件可验证清理 |
| 服务中断 | 本地资料仍可查看和编辑，云端任务进入待恢复状态 |
| 域名迁移 | 先导出/导入或提供受控迁移，不让用户误以为数据消失 |

## 14. 与 V1.5.0 / V2 的衔接

以下是 V3.0.0 对前置版本提出的拟议兼容条件，不在本草稿中反向修改 V1.5.0 / V2：

### V1.5.0 应提供

- 稳定 `fact_id` 和可回查的 Fact 事实模型；
- 自包含、可序列化的 SelectedEvidenceSet / EvidenceBundle，不只返回服务端 SQL ID；
- 每条 bullet 到 fact_refs 的来源映射；
- Fact、向量 `source_hash` 和 Embedding fingerprint；
- SQLite 作为事实和向量的唯一持久化载体，删除 Chroma 与 numpy + JSON 故障后端；
- Builder、事实校验、渲染之间使用纯数据契约，避免绑定进程内状态。

### V2 应提供

- 时间预筛、事实相关性、内容决策和排序的效果评测；
- 稳定的小型评测集和质量回归；
- LLM 改写质量、事实越界和排版体验优化；
- 统一 LLMProvider / EmbeddingProvider 边界；
- 本地管理员可用的模型/API 图形化配置、能力检测和安全切换；
- 不含用户正文的 Token UsageRecord 与聚合统计；
- 在真实规模证明必要前，不引入新的远程向量数据库。

### V3.0.0 负责

- 将本地数据和检索运行位置迁入浏览器；
- 建立账号、订阅、无履历持久化服务与生产安全能力；
- 将 V2 本地管理员模型配置升级为账号级供应商设置、权限隔离、额度与生产 Provider Gateway；
- 完成本地备份、恢复、PWA、浏览器兼容和生产运行体验。

## 15. V3.0.0 分阶段草案

### V3.0.0-A：网页本地 Vault

- SQLite WASM + OPFS；
- Profile、Experience、Fact、Embedding 本地 CRUD；
- 单标签页写入和 Schema 迁移；
- 持久化状态、导出和导入；
- 从现有本地数据格式迁移的验证工具。

### V3.0.0-B：无履历持久化服务

- 账号、订阅、额度；
- EvidenceBundle 驱动的 LLM 改写；
- Embedding 服务；
- 无持久化 PDF/DOCX 处理；
- 幂等、限流、日志和临时文件审计。

### V3.0.0-C：供应商与本地模型

- Provider 配置与能力探测；
- OpenAI-compatible 云端 / 本地 Endpoint；
- 供应商 Adapter；
- BYOK 安全策略；
- Embedding 模型切换和本地全量重建体验。

### V3.0.0-D：生产体验与安全收口

- PWA；
- 浏览器支持矩阵；
- 多账号与共享设备；
- 离线/断网恢复；
- CSP、XSS、供应链、日志和隐私审计；
- 备份恢复演练和域名迁移预案。

是否使用 V3.0.0-A/B/C/D 作为实际子版本，需要在 V2 完成后根据当时资源重新确认；本草稿只记录合理实施顺序。

## 16. 明确不做或不默认承诺

- 不默认在服务器保存用户完整履历、Profile、向量和生成文件；
- 不默认提供跨设备实时同步；
- 不默认支持多人协作编辑同一履历；
- 不承诺任意私有协议无需 Adapter 即可调用；
- 不承诺所有浏览器、移动设备和无痕模式具有完全一致能力；
- 不把“业务数据库不保存”表述为“任何服务器、模型供应商或日志都看不到数据”；
- 不在真实规模和性能证据出现前重新引入远程向量数据库；
- 不为了网页化重写已经稳定的事实选择、Builder 和模板业务规则。

## 17. 验收草案

V3.0.0 每个实际版本仍按全局规则分别记录功能验收与结构变更验收，并绑定具体 commit。以下高风险项目必须由可读取客户端、服务端和部署配置的高性能 Agent 独立验收。

### 17.1 本地数据

- [ ] Profile、Experience、Fact、Embedding 和生成记录默认只存在浏览器 Vault；
- [ ] persistent storage 获批、拒绝和不可用三种状态均有正确体验；
- [ ] 清除站点数据、无痕关闭、换 origin 的后果有明确提示和恢复路径；
- [ ] 导出、加密、导入、损坏备份和跨 Schema 版本恢复通过；
- [ ] 同一浏览器两个账号不会串库；退出账号不会误删 Vault；
- [ ] 多标签页不会静默覆盖或损坏数据库。

### 17.2 事实与向量

- [ ] Fact 修改后旧 source_hash 向量不能参与检索；
- [ ] Embedding 失败可见、可重试，不伪装成功；
- [ ] 模型切换前后不存在不同 fingerprint 混合检索；
- [ ] EvidenceBundle 自包含且每条输出可追溯到本地 Fact；
- [ ] 服务端和浏览器都拒绝未知 ID、无来源 bullet 和越界事实。

### 17.3 服务端数据边界

- [ ] 账号库、应用日志、网关、APM、缓存、队列和备份不长期保存履历正文；
- [ ] PDF、JD、EvidenceBundle 和 DOCX 临时数据在成功、失败、超时和崩溃场景均按策略清理；
- [ ] 响应和代理缓存策略不会缓存用户内容；
- [ ] 请求重试具备幂等性，不重复计费；
- [ ] 第三方模型数据处理边界在 UI 和隐私说明中准确展示。

### 17.4 网页安全与兼容

- [ ] CSP、XSS、CSRF、CORS、依赖供应链和请求大小限制通过专项审查；
- [ ] 旧标签页、新前端和数据库 Schema 升级组合测试通过；
- [ ] 目标浏览器矩阵完成首次使用、CRUD、生成、备份、恢复和断网测试；
- [ ] PWA 更新不会在用户编辑或迁移中途破坏本地数据；
- [ ] 性能测试证明几千 Fact 的本地预筛和精确检索不阻塞 UI。

## 18. 正式 PLAN 前待确认

1. 首发浏览器是否限定 Chromium 桌面端，何时支持 Firefox、Safari 和移动端；
2. 本地 Vault 是否要求口令加密，忘记口令时是否接受无法恢复；
3. BYOK 采用浏览器直连、短期代理还是不在首发支持；
4. PDF 解析和 DOCX 渲染何时从无持久化服务迁入浏览器；
5. 幂等恢复允许服务端短期保存哪些加密内容、TTL 多长；
6. 是否提供可选端到端加密同步，以及同步是否属于 V3.0.0 初始范围；
7. V3.0.0-A/B/C/D 是否作为子版本逐步上线；
8. 正式域名和 origin 迁移策略；
9. 账号与匿名 Vault 的绑定、转移和共享设备解锁方式；
10. 用户数据和第三方模型请求的隐私说明及用户授权交互。

## 19. 当前调研依据

- [SQLite WASM 持久化与 OPFS](https://sqlite.org/wasm/doc/trunk/persistence.md)
- [SQLite WASM/JS 项目说明](https://sqlite.org/wasm/doc/trunk/index.md)
- [浏览器存储配额、持久化与回收](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria)
- [OPFS 行为与限制](https://developer.mozilla.org/en-US/docs/Web/API/File_System_API/Origin_private_file_system)
- [SQLite 适用场景](https://www.sqlite.org/whentouse.html)

这些资料只支持当前草稿的可行性判断。V3.0.0 正式立项时需要重新核对浏览器支持、SQLite WASM、供应商 API、安全标准和部署环境。
