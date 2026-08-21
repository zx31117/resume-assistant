# 当前实现状态

> 文档角色：当前已验收实现事实的唯一真源
> 已验收版本：V1.4.1
> 下一候选版本：[V1.5.0 草稿](./versions/v1.5.0/DRAFT.md)；尚未转为开发 PLAN
> 状态日期：2026-08-22

## 1. 当前结论

V1 核心链路已经闭环。系统可以在一次核心请求中完成 JD 分析、经历匹配、SQL 事实回读、受约束内容生成、ResumeBuilder 构建、模板渲染和 DOCX 保存，并返回下载地址与阶段诊断。

V1.3.0 经历三轮收口：初始实现、完整流程返工与源码验收、产品来源边界修正。第三轮 T3 / T4 修正通过针对性高性能源码复核，用户已完成人工 E2E 验收。详细证据见 [V1.3.0 RESULT](./versions/v1.3.0/RESULT.md)。

V1.4.0 已将数据库、向量索引、输出、日志和缓存统一迁移到仓库外 runtime data root，完成可回滚数据迁移、安全复核、Private 干净 clone 验证和 Public 首发，发布标签为 `v1.4`。详细证据见 [V1.4.0 RESULT](./versions/v1.4.0/RESULT.md)。

V1.4.1 将对外版本号收束到 `backend/core/version.py` 的 `APP_VERSION`，删除了与身份事实边界冲突的经历正则提取死代码，并以独立反向场景确认姓名、电话、邮箱和所在地只来自本次 request，求职意向只来自当前 JD。Stub E2E 的 mock 启动顺序同时完成修正，在无真实 API Key 环境复跑 20/20。详细证据见 [V1.4.1 RESULT](./versions/v1.4.1/RESULT.md)。

V1.4.1 最终 N4 已完成：历史版本目录统一为三段式，V1.4.0 分项证据收束到 RESULT，源码中的旧文档路径和交付清单同步完成。高性能源码验收绑定 T8 commit `317c52660335a9dc35107d4627c25739c8eb4f9f`，manifest、Git 清单和 SHA256 为 88/88/88；T7 12 PASS / 0 FAIL / 3 SUSPEND，干净 runtime Stub E2E 20/20。首轮纯文档冻结候选 `2b6e8f9ad69ca8ee481c824e38461bb698f671e7` 完成 88/88 全量核对，但因候选包仍保留“待最终冻结”文字，且文档复核另发现两处历史 GitHub 用户名未脱敏而退出发布。发布档案现已完成稳定语义和隐私收口：最终发布包从本状态机械冻结，不重跑功能或高性能源码验收；annotated tag `v1.4.1` 的目标 commit 作为最终发布标识，冻结后不再回写自身 SHA。

## 2. 已实现核心流程

### 经历数据准备

~~~text
PDF 上传 → 文本解析与预处理 → 分段 LLM 经历提取
→ Experience 写入 SQLite → VectorIndexJob 同步执行 → Chroma 索引
~~~

### JD 到 DOCX

~~~text
POST /api/resume/generate-docx
→ 索引就绪检查 → JDAnalysis → RAG 匹配
→ 按命中 ID 回 SQL 读取事实 → AI 只改写经历 bullets
→ ResumeBuilder 选择/排序/裁剪 → ResumeDocument
→ TemplateRenderer 完整渲染 → 本地 DOCX → 下载地址
~~~

关键失败会返回统一领域错误，不会伪装成空成功。核心接口不要求调用方直接构造 `ResumeDocument`。

旧的 Markdown 生成接口和直接 `ResumeDocument → DOCX` 路径仍保留用于兼容或模板调试，但已标记 deprecated/internal，不代表核心业务链路。

## 3. 已验收事实边界

| 数据 | 当前规则 |
|---|---|
| 经历事实 | 公司、学校、岗位、项目和时间只从 SQL Experience 读取 |
| AI 输出 | 只包含命中 Experience ID 对应的 bullets；未知 ID 丢弃并告警 |
| 身份信息 | 姓名、电话、邮箱、所在地只取本次请求；缺失留空，不从 DB、AI、模板或经历库回填 |
| 求职意向 | 只取当前 `JDAnalysis.position`；职业经历库不保存该字段 |
| 个人总结 | V1 不生成、不渲染 |
| 内容集合 | 只有 ResumeBuilder 可以选择、排序和限制数量 |
| 模板渲染 | Renderer 不删除或截断业务条目；容量和超页只告警 |

## 4. 数据与基础设施

| 项目 | 当前实现 |
|---|---|
| 关系数据库 | SQLite + SQLAlchemy |
| Runtime data root | `RESUME_DATA_DIR`；Windows 默认 `%LOCALAPPDATA%\ResumeAssistant`，macOS 默认 `~/Library/Application Support/ResumeAssistant`，Linux 默认 `~/.local/share/resume-assistant` |
| 事实表 | `users`、`experiences` |
| 索引任务表 | `VectorIndexJob`，支持 UPSERT / DELETE、状态、重试和错误记录 |
| Profile 持久化 | 未实现；V1 身份字段来自单次请求 |
| 向量主后端 | Chroma `PersistentClient` |
| 故障回退 | numpy + JSON |
| 一致性 | Experience 变更与 VectorIndexJob 同事务提交；请求内同步执行；生成前检查并重试；可从 SQL 全量重建 |
| Embedding / LLM | 豆包模型；关键结构化阶段 strict failure |
| 模板 | 系统内置 DOCX + TemplateSpec JSON |
| 输出 | `<runtime data root>/output` 本地 DOCX；可用 `DOCX_OUTPUT_DIR` 显式覆盖 |
| 公开发布 | GitHub Public；MIT；V1.4.0 发布标识为 `v1.4`；V1.4.1 发布标识为 annotated tag `v1.4.1`，最终 commit 以 tag 目标为准 |
| 用户形态 | 本地单用户；服务器化和多用户属于 V3 |

主要契约：

- `JDAnalysisOut`：position、industry、required_skills、preferred_skills、responsibilities、keywords、experience_preferences；
- `GeneratedResumeContent`：只含 `experiences[]`，每项只有 `experience_id + bullets[]`；
- `ResumeDocument`：profile、education、work、projects、skills、awards；
- `ResumeDocxGenerateResponse`：文件信息、下载地址、阶段状态、匹配/渲染 ID、build_meta、render_stats 和 warnings；
- `TemplateSpec`：模板元数据、章节、原型 style、必填状态和容量提示。

## 5. 当前 API

| 方法 | 路径 | 当前状态 |
|---|---|---|
| GET | `/` | 健康检查和向量后端状态 |
| POST | `/api/resume/upload` | PDF → 文本 |
| POST | `/api/experience/extract` | 文本 → 结构化经历 |
| POST/GET | `/api/experience/` | 创建、列出经历 |
| PUT/DELETE | `/api/experience/{id}` | 更新、删除经历，并同步索引任务 |
| POST | `/api/jd/analyze` | JD → 7 字段分析 |
| POST | `/api/resume/generate-docx` | V1.3.0 唯一核心 JD → DOCX 接口 |
| POST | `/api/resume/generate` | 旧 Markdown 路径，deprecated |
| GET | `/api/template/list` | 系统模板列表 |
| POST | `/api/template/generate-docx` | 直接 ResumeDocument → DOCX，仅模板调试/internal |
| POST | `/api/template/generate-report` | 模板路径诊断报告 |
| GET | `/api/template/download` | 下载 output 下文件 |
| POST | `/api/template/upload` | 已废弃，返回 410 |
| GET | `/api/template/{id}/schema` | 已废弃，返回 410 |

## 6. 当前模块职责

| 模块 | 当前职责 |
|---|---|
| `resume_parser` / `text_preprocessor` | PDF 文本解析、清洗和章节切分 |
| `core.version` | `APP_VERSION` 对外版本元数据单一真源 |
| `experience_extractor` / `experience_service` | 经历提取、SQL CRUD 和索引任务创建 |
| `vector_index_sync` | 索引任务执行、重试、就绪检查和从 SQL 全量重建 |
| `rag_service` / `chroma_store` | Embedding、向量 CRUD、检索和重排；不是事实源 |
| `jd_analyzer` | JD 强类型分析；无有效岗位时显式失败 |
| `resume_content_generator` | 只生成带 Experience ID 的经历 bullets |
| `resume_builder` | 合并 SQL 事实和 AI bullets；唯一负责内容选择、排序和数量限制；执行 Profile 来源规则 |
| `resume_generation_service` | 编排核心 JD → DOCX 八阶段流程 |
| `template_renderer` / `docx_writer` | 完整渲染 ResumeDocument 并保存 DOCX，不选择业务内容 |
| `layout_optimizer` | 轻量样式处理和页数诊断；不为一页纸删除内容 |

## 7. 验收基线

- V1.3.0 核心链路：Stub E2E 15/15、Real API Smoke、PLAN §8.2 自动化 10/10、第三轮源码复核和人工 E2E 通过；
- V1.4.0 T7：12 PASS / 0 FAIL / 3 SUSPEND；3 项为干净首发包缺少旧本地数据或 API Key 的预期挂起；
- V1.4.0 T9：三轮高性能源码、安全、迁移与发布复核通过；
- MIG-3：从迁移后 SQL 重建向量，5 upserted / 0 failed；
- T10：Private 干净 clone、Python 3.10.11 新 venv 安装和 Stub E2E 通过；Windows GBK 状态输出兼容问题已修正；
- T11：仓库转 Public，annotated tag `v1.4` 已推送；关闭凭据助手后匿名 `ls-remote` 与全新 clone 均通过；
- 公开 clone：91 个跟踪文件，必要 DOCX 模板已跟踪，`pip_freeze_baseline.txt` 未跟踪，工作区干净。
- V1.4.1 高性能源码验收：版本真源、死代码退出和身份事实边界通过；N4 后源码验收 T8 commit `317c5266`，manifest/Git/SHA256 88/88/88；T7 12 PASS / 0 FAIL / 3 SUSPEND；身份边界最终独立反向推导 10/10；干净 runtime 无真实 Key Stub E2E 20/20。

发布标识：源码冻结 `d99d1bc22a86c3c9b016dc266dac11353cdb3386`；T10 修正 `e631531d93f23f0d4f3bc37f43aee2a0b982fc82`；`v1.4` 解引用到发布记录 commit `c5d9f6ebc54045a4553d9a113e0406584f4ac763`。

## 8. 已知边界与后续方向

以下不是 V1 缺陷：

1. 不保证严格一页纸、像素级字号、间距和跨软件分页一致；排版体验属于 V2。
2. 不生成个人总结或自我评价；仅在 V2/V3 有明确低履历场景时重新评估。
3. 不包含匹配质量、措辞、性能和交互体验的系统性调优；属于 V2。
4. 不包含登录、多用户、持久化 Profile、PostgreSQL、对象存储、异步 Worker、监控和生产部署；属于 V3。
5. 索引就绪与全量重建当前是 service 层能力；服务器化后可再提供运维接口。

当前维护缺口（不阻断 V1.4.1 产品发布）：`_v13_stub_e2e.py` 的清理逻辑仍指向 V1.4.0 前的 `backend/data`，污染过的 runtime 会累积 `stub-user` 数据并使个别断言波动；独立临时 runtime 下稳定 20/20。后续修改测试时，应让该脚本强制使用独立临时 `RESUME_DATA_DIR`，或按用户清理 runtime 测试数据。

## 9. 已验收历史

| 版本 | 已验收结果 |
|---|---|
| V1.0.0 | PDF → 经历库 → JD → RAG → Markdown 端到端通过 |
| V1.1.0 | 分段并发、7 字段 JD、多因素评分和结构化输出通过 |
| V1.2.0 | 标准模板路径 A、布局和内容填充通过；JD 路径尚未闭环 |
| V1.2.1 | PII、ignore、依赖、下载、死代码和 Chroma 专项通过 |
| V1.3.0 | JD → RAG → 受约束内容 → Builder → DOCX 核心链路通过；第三轮产品规则修正和人工 E2E 通过 |
| V1.4.0 | 源码与 runtime 数据物理解耦、可回滚迁移、安全复核、Public 首发和匿名 clone 通过 |
| V1.4.1 | 版本元数据单一真源、身份提取死代码退出、request/JD 事实边界、N4 三段式档案收束和最终 88/88/88 发布复核通过 |

后续收到新需求时，以本文为基线创建下一版本 PLAN。版本过程和证据保留在对应 PLAN / RESULT，不继续堆入本文。
