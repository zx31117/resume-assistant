# 当前实现状态

> 文档角色：当前已验收实现事实的唯一真源
> 已验收版本：V2.0.2
> 源码验收对象：`eb4bd30a2d4c7aac62865924c7b8eab363d282ee`
> 发布标识：annotated tag `v2.0.2` → `78bb909c18ca28e45b54406536aa326887caa1ca`
> 状态日期：2026-09-05

## 1. 当前结论

V1 核心架构已经收口。系统可以从职业经历建立可回查的 Experience / Fact 事实库，根据目标 JD 先确定经历名单，再在入选经历中选择可用事实，完成受约束改写、确定性装配和 DOCX 输出。

V2.0.0 在该核心链路之上完成本地全流程图形交互首版：React + TypeScript + Vite 三页前端（生成工作台、履历库、本地系统）、同源托管、连接配置与 Credential Manager、系统维护薄 API、并发门禁和 Windows 目录型便携启动器。核心生成链路、两层选材、Fact 生命周期和向量持久化继续直接复用 V1.5.0 实现，前端没有建立第二业务真源。

V2.0.1 为生成、提取、Experience CRUD、迁移、Embedding 重建和失败重试增加统一操作记录：页面可以查看当前阶段、资源类型、已用时间、最终各阶段耗时、近期同类统计和脱敏诊断摘要；运行活动与日志读取不获取业务共享门禁。诊断 JSONL 位于 runtime data root，只承载有界、脱敏的问题定位证据，不成为第二业务真源。

V2.0.1 已完成开发验证、独立源码验收、用户人工验收和文档验收。用户于 2026-09-02 明确确认通过；源码验收绑定上方候选，发布身份绑定 annotated tag。版本范围、测试、证据边界和人工真实生成记录见 [V2.0.1 RESULT](./versions/v2.0.1/RESULT.md)。

V2.0.2 在不改变产品业务流程和界面的前提下完成工程基线收束：Windows 本地与 CI 使用同一预检入口和固定回归计数；测试数据库、输出、日志与缓存强制位于临时 runtime，默认真实 runtime 由 fail-closed 哨兵保护；迁移 API、备份摘要、配置和 Demo 中的旧 vectorstore 活动契约已经退出。版本已完成独立源码验收、人工确认、文档验收和公开发布。详细打回、返工和证据见 [V2.0.2 RESULT](./versions/v2.0.2/RESULT.md)。

## 2. 已实现核心流程

### 经历数据准备

~~~text
PDF 上传 → 文本解析与预处理 → 分段 LLM 经历提取
→ Experience 写入 SQLite → 确定性 Fact reconciliation
→ FactEmbedding 状态更新 → SQLite 向量重建
~~~

### JD 到 DOCX

~~~text
POST /api/resume/generate-docx
→ 迁移与索引就绪检查 → JDAnalysis
→ 第一层固定槽位选择 CandidateExperienceSet
→ 第二层事实选择 SelectedEvidenceSet
→ 只使用已选 fact_refs 的受约束改写
→ ResumeBuilder 确定性装配 → ResumeDocument
→ TemplateRenderer 完整渲染 → 本地 DOCX → 下载地址
~~~

关键失败会返回统一领域错误，不会退化为空成功、旧索引或“全部 Fact”故障兜底。生成结果保留逐 bullet 的事实来源映射。

### 图形交互流程

~~~text
启动 Windows 便携应用 → 浏览器打开本地同源页面
→ 本地系统：连接测试/激活、状态、迁移、重建、重试
→ 履历库：PDF 上传、经历提取、Experience 查看/新增/编辑/删除
→ 生成工作台：身份信息、目标 JD、模板、生成状态、warnings、下载 DOCX
~~~

三个页面只提交请求和展示状态；配置、维护、Experience 事务与 JD → DOCX 仍由后端既有服务完成。数据库或索引未就绪时页面可进入受限维护模式，生成保持阻断。

长操作通过统一 `operation_id` 关联后台状态、阶段事件和脱敏日志。浏览器刷新后可在“本地系统”的运行活动中重新选择仍由当前后台进程保存的操作；已知 `operation_id` 的诊断摘要可以从 JSONL 重建。近期阶段统计按操作类型和阶段代码比较既往样本，并排除当前操作自身。

## 3. 已验收事实与选择边界

| 数据或阶段 | 当前规则 |
|---|---|
| 经历事实 | 公司、学校、岗位、项目、时间和原始素材来自 SQL Experience / Fact |
| Fact 身份 | Fact 保留稳定 ID、来源、revision 与 hash；正文修改会使旧向量和旧选材结果失效 |
| 工作/实习 | 只选日期可解析的最近最多 3 次；缺失或不可解析日期排除并告警；同日期使用稳定最终键 |
| 项目/论文 | 使用同一候选池，只从生成基准日前 3 年内按 JD 相关性选择最多 2 项；不足不补 |
| 教育与校园 | 正式教育背景保持确定性结构；仅当工作与项目合计少于 2 项时，补最匹配的 1 项校园经历 |
| 第二层选材 | 只能引用第一层已入选经历中版本匹配且有来源的 Fact |
| AI 输出 | 只做受事实约束的表达改写；未知、跨经历、未选或过期 fact_refs 被拒绝；不写回事实库 |
| 身份信息 | 姓名、电话、邮箱、所在地只取本次请求；缺失留空，不从 DB、AI、模板或经历库回填 |
| 求职意向 | 只取当前 `JDAnalysis.position`；职业经历库不保存该字段 |
| 个人总结 | V1 不生成、不渲染 |
| Builder | 只按冻结的选择结果确定性装配、排序和保存来源映射，不再执行第二套 JD 相关性选择 |
| Renderer | 完整展示 ResumeDocument，不删除、截断或改写业务内容 |

## 4. 数据与基础设施

| 项目 | 当前实现 |
|---|---|
| 关系数据库 | SQLite + SQLAlchemy |
| Runtime data root | `RESUME_DATA_DIR`；Windows 默认 `%LOCALAPPDATA%\ResumeAssistant`，macOS 默认 `~/Library/Application Support/ResumeAssistant`，Linux 默认 `~/.local/share/resume-assistant` |
| 配置管理 | 单一 resolver；API Key：Windows Credential Manager > env/.env；非密钥：runtime 版本化配置 > env/.env > 内置默认 |
| 前端 | React + TypeScript + Vite；生产构建由 FastAPI 同源托管并提供 SPA fallback |
| 便携发行 | Windows x64 PyInstaller `onedir`；图形启动器负责启动、重开、单实例、端口选择和退出释放 |
| 操作诊断 | `core.operations` 是统一操作状态与阶段计时机制；脱敏 JSONL 位于 `<runtime data root>/diagnostics`，最多保留 7 天且受 10 MiB 上限约束 |
| 事实表 | `users`、`experiences`、`facts` |
| 迁移表 | `schema_versions` |
| 向量派生表 | `fact_embeddings`；保存 fingerprint、dimension、dtype、float32 BLOB、Fact revision/hash、状态与错误 |
| 向量计算 | 从 SQLite 读取候选向量，在内存执行 numpy 精确余弦计算；numpy 不承担持久化或 fallback |
| 旧向量实现 | Chroma 与 numpy + JSON 活动后端、依赖和配置已退出；旧向量字节不迁移，由当前 Fact 重建 |
| 一致性 | Experience create/update 与 Fact reconciliation 同事务；Fact 修改与旧 Embedding 失效同事务；失败回滚或进入明确可重试状态 |
| 迁移安全 | 既有数据库迁移前备份并核对；全新不存在的 SQLite 路径按空库初始化；备份、核对或 cleanup 失败时 fail closed |
| Profile 持久化 | 未实现；V1 身份字段来自单次请求 |
| Embedding / LLM | 豆包模型；关键结构化阶段 strict failure |
| 模板与输出 | 系统内置 DOCX + TemplateSpec JSON；输出位于 `<runtime data root>/output`，可用 `DOCX_OUTPUT_DIR` 覆盖 |
| 用户形态 | 本地单用户；服务器化和多用户属于 V3 |

主要契约：

- `CandidateExperienceSet`：生成基准日、规则版本、固定槽位、选择依据、排除项和告警；
- `SelectedEvidenceSet`：JD hash、规则版本、基准日、槽位、Fact revision/hash、选择原因与表达侧重；
- `GeneratedBullet`：bullet 文本及其逐条 `fact_refs`；
- `ResumeDocument`：profile、education、work、projects、skills、awards，并保留最终来源映射或等价强类型 sidecar；
- `ResumeDocxGenerateResponse`：文件信息、下载地址、阶段状态、build_meta、逐 bullet 来源、render_stats 和 warnings；
- `TemplateSpec`：模板元数据、章节、原型 style、必填状态和容量提示。

## 5. 当前 API 与维护入口

| 类型 | 方法或命令 | 当前状态 |
|---|---|---|
| API | `GET /` | 生产构建存在时返回 SPA 首页；未构建时保留 JSON 健康响应 |
| API | `GET /api/health` | 同源健康检查与版本元数据 |
| API | `GET /api/config` | 返回连接配置脱敏快照，不返回完整 Key |
| API | `POST /api/config/test` | 测试候选 LLM / Embedding 配置，不激活失败候选 |
| API | `POST /api/config/activate` | 激活已验证配置并按类型写入凭据库或 runtime 配置 |
| API | `GET /api/system/status` | 汇总迁移、Experience/Fact、Embedding、就绪状态和下一步 |
| API | `POST /api/system/migrate` | 调用与 CLI 相同的迁移 service |
| API | `POST /api/system/rebuild` | 全量重建 Embedding |
| API | `POST /api/system/retry` | 重试失败 Embedding 项 |
| API | `GET /api/system/operations` | 查询活动与最近操作，可按固定状态和类型筛选 |
| API | `GET /api/system/operations/{operation_id}` | 查询单次操作状态、阶段事件和近期同类统计 |
| API | `GET /api/system/logs` | 按事件序号增量读取脱敏结构化日志 |
| API | `GET /api/system/diagnostics/{operation_id}` | 获取或从 JSONL 重建脱敏诊断摘要 |
| API | `DELETE /api/system/logs` | 清理历史诊断日志；不改变业务记录或活动操作 |
| API | `POST /api/resume/upload` | PDF → 文本 |
| API | `POST /api/experience/extract` | 文本 → 结构化经历 |
| API | `POST/GET /api/experience/` | 创建、列出经历；创建同步形成 Fact |
| API | `PUT/DELETE /api/experience/{id}` | 更新或删除经历，并同步 reconciliation / 失效 / 清理 |
| API | `POST /api/jd/analyze` | JD → 7 字段分析 |
| API | `POST /api/resume/generate-docx` | V1 唯一核心 JD → DOCX 接口 |
| API | `POST /api/resume/generate` | 旧 Markdown 路径已退出，返回 410 |
| API | `GET /api/template/list` | 系统模板列表 |
| API | `POST /api/template/generate-docx` | 直接 ResumeDocument → DOCX，仅模板调试/internal |
| API | `GET /api/template/download` | 下载 output 下文件 |
| CLI | `python manage.py migrate` | 初始化全新库或迁移既有库；既有库先备份并核对 |
| CLI | `python manage.py status` | 检查 schema、Fact 与 Embedding 状态并给出下一步 |
| CLI | `python manage.py rebuild` | 从当前 Fact 全量重建 Embedding；缺 Key 时非零退出 |
| CLI | `python manage.py retry` | 重试失败的 Embedding 项 |

## 6. 当前模块职责

| 模块 | 当前职责 |
|---|---|
| `resume_parser` / `text_preprocessor` | PDF 文本解析、清洗和章节切分 |
| `core.version` | `APP_VERSION` 对外版本元数据单一真源 |
| `experience_extractor` / `experience_service` | 经历提取、SQL CRUD、Fact reconciliation 与派生数据生命周期 |
| `fact_service` | Fact 查询、显式修改、revision/hash 与失效一致性 |
| `database.migrations` | schema version、备份核对、确定性 Fact 迁移、幂等与 fail-closed 资源释放 |
| `embedding_service` | SQLite BLOB 向量、fingerprint、健康检查、失效、重试、重建和内存精确检索 |
| `selection_service` | 第一层固定经历槽位和第二层事实选择；产出可序列化、可过期的选择结果 |
| `jd_analyzer` | JD 强类型分析；无有效岗位时显式失败 |
| `constrained_rewrite` | 只基于 SelectedEvidenceSet 生成带逐 bullet fact_refs 的受约束表达 |
| `resume_builder` | 按冻结名单确定性装配 ResumeDocument、来源映射和告警 |
| `resume_generation_service` | 编排迁移检查、两层选材、受约束改写、装配、渲染和保存 |
| `template_renderer` / `docx_writer` | 完整渲染 ResumeDocument 并保存 DOCX，不选择业务内容 |
| `layout_optimizer` | 轻量样式处理和页数诊断；不为一页纸删除内容 |
| `core.config_resolver` | 统一解析凭据库、runtime 配置、env/.env 与内置默认，并提供脱敏来源快照 |
| `core.credential_manager` | 通过 Windows Credential Manager 保存长期 API Key；失败显式可见，不降级为明文 |
| `core.security` | 校验 loopback Host、Origin 和启动会话 Cookie，保护本地写操作 |
| `core.concurrency` | 为迁移、重建、重试和生成提供共享非阻塞并发门禁 |
| `core.operations` | 统一记录生成、提取、Experience CRUD、迁移、重建与重试的操作状态、阶段、单调耗时、近期统计和脱敏 JSONL；诊断故障降级但不改写业务结果 |
| `services.connection_test` | 测试候选 LLM / Embedding 连接，不落库失败候选 |
| `packaging.launcher` | 图形启动器：单实例、端口、健康等待、浏览器、重开与退出释放 |

## 7. 验收基线

- V1.5.0 的 Experience / Fact / Embedding、两层选材、受约束改写、Builder、逐 bullet 来源、Renderer、迁移和旧实现退出继续通过八组 **309/0** 回归；核心事实链路未被 V2 图形层改写。
- V2.0.0 独立源码验收绑定 `a9c66db14a4fa2a60f2ef9b85a61538da46079f1`：生命周期矩阵 **50/0**、冒烟 **20/0**、Experience CRUD **15/0**、V1.5.0 回归 **309/0**；功能和结构变更验收均通过，阻断项 0。
- 配置/密钥、loopback 写安全、管理 service 同源、索引门禁、Experience 原事务、生成核心链、便携启动器、版本元数据和旧入口退出均已完成阶段性全局架构复核。
- 便携包 `ResumeAssistant.exe` 为 15,878,373 字节，SHA-256 `D3ADC37348BDDDA11DD5A0E03BC9C61938FE8E61D52B7E7491A7331F35CCEA44`；包内无 `.env`、数据库、真实用户输出或凭据。
- 用户于 2026-08-31 明确确认 V2.0.0 人工验收通过；详细证据、返工过程和公开历史脱敏说明见 [V2.0.0 RESULT](./versions/v2.0.0/RESULT.md)。
- V2.0.1 独立源码验收绑定 `9319782d5f1a8d5f543e6795f2f024143fa9dbc7`：开发验证 `_v201_validation.py` **77/0**，独立定向探针 **20/0**，V1.5/V2.0 核心回归继续通过；功能和结构变更验收均通过，阻断项 0。
- 用户于 2026-09-02 以真实生成完成人工验收：11 个阶段均出现开始与完成，可见阶段耗时合计约 178.3 秒，其中两段 LLM 约占 99.7%；用户明确确认当前界面足以支持问题定位。详细证据边界见 [V2.0.1 RESULT](./versions/v2.0.1/RESULT.md)。
- V2.0.2 独立源码验收绑定 `eb4bd30a2d4c7aac62865924c7b8eab363d282ee`：六个阻断脚本固定计数为 **77/0、48/0、20/0、15/0、50/0、12/0/3**，默认 runtime 空陷阱仅新增允许的空标准骨架目录且无文件；功能与结构变更验收均通过，源码阻断项 0。
- V2.0.2 旧迁移契约退出完成：`vectorstore_dir` 活动契约计数为 0，配置与 Stub Demo 不再创建或使用旧 vectorstore 路径；迁移失败继续 fail-closed。集中返工只涉及测试、预检与文档，因此既有便携包和人工界面验收继续适用。
- V2.0.2 Windows x64 便携包 `ResumeAssistant.exe` 为 15,972,628 字节，SHA-256 `9F39874AEA9FCC59F0AEBC37C8354B33E5B1589BCCA609948B464CB2B4BB8FA7`；包版本 2.0.2，模板按冻结文件打包，无 `__pycache__`、`.pyc` 或开发机私有路径。

## 8. 已知边界与后续方向

以下不是当前版本缺陷或降级：

1. V2.0.0 达成“已有功能全流程图形化”的首版目标；当前页面与用户理想交互流程仍有差距，具体页面重新设计属于后续版本。
2. 不包含实际 DOCX/PDF 预览、Draft/Revision、条目锁定、差异/回退、局部重新生成或用户手工覆盖选材结果。
3. 不保证严格一页纸、像素级排版或跨软件分页一致，也不生成个人总结；相关性权重、措辞和招聘效果没有被宣称为已经优化。
4. 不包含多 Provider、任意兼容 Endpoint、Token/费用统计、质量评测后台、后台任务、取消或断点恢复。
5. Windows x64 是本版便携发行范围；Firefox、macOS/Linux 便携和完整移动端适配不属于本版 PASS 条件。
6. 不包含登录、多用户、持久化 Profile、PostgreSQL、对象存储、云端同步、生产监控或公网部署；这些仍属于 V3。
7. V2.0.1 用于暴露耗时与故障位置，不优化外部 LLM/Embedding 响应时间；人工实测的主要等待来自两次 LLM 调用。
8. 当前诊断界面将在 V2.1.0 整体界面重设计时重新评估展示方式，但整个 V2 阶段的问题定位能力不得无替代地删除。

版本过程和开发经验由 [版本档案](./versions/README.md) 保存，不继续堆入本文。
