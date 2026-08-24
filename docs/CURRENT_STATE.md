# 当前实现状态

> 文档角色：当前已验收实现事实的唯一真源
> 已验收版本：V1.5.0
> 源码验收对象：`448d21a2c51fc47ac61fca647104c18c787d9e77`
> 发布标识：annotated tag `v1.5.0` 指向 `8d3aac6369146052f819c414cc18f53b11a778fc`；发布后补录提交只前移 `main`，不移动该 tag
> 状态日期：2026-08-24

## 1. 当前结论

V1 核心架构已经收口。系统可以从职业经历建立可回查的 Experience / Fact 事实库，根据目标 JD 先确定经历名单，再在入选经历中选择可用事实，完成受约束改写、确定性装配和 DOCX 输出。

V1.5.0 已完成开发验证、验收 Agent 源码验收、人工确认、文档验收和版本发布。源码验收绑定上方精确 commit，发布身份绑定 annotated tag；后续如修改相关源码、测试、配置或公开元数据，受影响范围必须重新验收。版本过程、失败候选、返工、测试与发布证据保存在 [V1.5.0 RESULT](./versions/v1.5.0/RESULT.md)，本文不重复流水账。

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
| API | `GET /` | 健康检查 |
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

## 7. 验收基线

- 最终源码验收对象为 `448d21a2c51fc47ac61fca647104c18c787d9e77`；开发侧最终矩阵为 309 pass / 0 fail，验收 Agent 独立复跑 9 组矩阵并用独立探针复核首轮阻断项，最终阻断项为 0；
- Experience / Fact / Embedding 的增删改、失效、失败、重试、重建、迁移备份和全新库入口已经覆盖正向与失败路径；
- 工作、项目、论文、正式教育和校园补位规则已经覆盖边界、同分、缺日期与输入乱序；
- 逐 bullet 来源映射通过 Builder、响应模型、ResumeDocument / sidecar 和最终 DOCX 链路核对，越界引用阻断；
- Chroma、numpy + JSON 活动持久化路径和旧 Markdown 主链已经退出；Profile、JD、无个人总结、Renderer 不裁剪和 runtime 隔离无回归；
- 用户于 2026-08-23 明确确认完成 V1.5.0 验收。详细证据见 [V1.5.0 RESULT](./versions/v1.5.0/RESULT.md)。

## 8. 已知边界与后续方向

以下不是 V1.5.0 缺陷：

1. 不保证严格一页纸、像素级字号、间距和跨软件分页一致；排版体验属于 V2。
2. 不生成个人总结或自我评价；仅在 V2/V3 有明确低履历场景时重新评估。
3. 固定槽位、事实来源和失效边界已验收，但召回质量、相关性权重、措辞效果和招聘效果没有进入 V1.5.0 PASS 条件，属于 V2。
4. 不包含交互式素材补充、Draft/Revision、跨修订 content_item_id、局部重生成、预览或完整管理 UI；属于 V2。
5. 不包含登录、多用户、持久化 Profile、PostgreSQL、对象存储、异步 Worker、监控和生产部署；属于 V3。
6. 不包含多模型、BYOK、Provider Gateway、Token/费用统计或 LangGraph 工作流扩展；后续按 V2/V3 计划重新评估。

版本过程和开发经验由 [版本档案](./versions/README.md) 保存，不继续堆入本文。
