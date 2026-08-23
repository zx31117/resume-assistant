# AI Career Resume Assistant V1.3.0 技术方案

> 文档角色：V1.3.0 已验收执行计划
> 状态：ACCEPTED，第三轮产品规则修正、针对性源码复核和人工 E2E 已通过
> 基线：[V1.2.1 RESULT](../v1.2.1/RESULT.md)  
> 开发必读：[项目总览](../../README.md) → [当前状态](../../CURRENT_STATE.md) → 本文  
> 重要依据：[D-015 至 D-017](../../DECISIONS.md#d-015-v13-改为核心链路收口)  
> 文档日期：2026-08-15

本文只描述 V1.3.0 相对 V1.2.1 的变化。未列入 Architecture Delta 的当前行为保持不变。

## 1. 版本目标

V1.3.0 是 V1 核心链路收口版：让一次核心接口调用完成 JD 分析、经历匹配、受约束内容生成、ResumeDocument 构建和 DOCX 输出。

完成标准：

1. JD → RAG → 结构化内容 → ResumeBuilder → DOCX 全链可运行；
2. 公司、学校、岗位、项目和时间等事实正确；
3. 核心失败明确可见，不产生空成功或错误 DOCX；
4. SQL 与向量索引不一致可识别、可重试、可恢复；
5. DOCX 可打开且大体结构完整。

本版本不做：

- 严格一页纸、像素级排版、字号和分页精修；
- 性能、RAG 权重、技能分和措辞质量调优；
- 用户自定义模板；
- 个人总结、自我评价及其模板章节；
- 注册、鉴权、多用户、持久化 Profile；
- PostgreSQL、Alembic、对象存储、异步 Worker、监控和云部署；
- LangChain、OpenAI SDK、Chroma 等依赖升级。

## 2. V1.2.1 基线缺口

1. `/api/resume/generate` 只输出 Markdown；DOCX 接口要求调用方直接传 ResumeDocument。
2. Markdown 路线和 DOCX 路线没有组成一个核心用例。
3. 核心 DOCX 路径可以绕过 ResumeBuilder。
4. TemplateRenderer 仍可能按 `max_items` 截断条目。
5. SQL 和向量写入失败可能形成不可见半成功。
6. 数据库没有 `user_profile` 表，但历史文档曾把它描述为已实现来源。
7. 关键结构化 LLM 输出失败时可能静默返回空模型。
8. 应用版本仍停留在 1.2.0。

## 3. Architecture Delta

### 3.1 唯一核心链路

~~~text
POST /api/resume/generate-docx
→ ResumeGenerationService
→ 索引就绪检查
→ JDAnalyzer
→ RAGService
→ SQL 回读命中 Experience
→ ResumeContentGenerator
→ ResumeBuilder
→ ResumeDocument
→ TemplateRenderer / LayoutOptimizer
→ 保存 DOCX 并返回下载地址
~~~

### 3.2 变化清单

| 变化 | V1.2.1 | V1.3.0 目标 |
|---|---|---|
| 核心入口 | Markdown 与直接 DOCX 两条路线 | 新增 `ResumeGenerationService` 和唯一 JD 驱动 DOCX 接口 |
| 内容契约 | Markdown 字符串 | 带 `experience_id` 的 `GeneratedResumeContent` |
| 文档构建 | 可由调用方直接传 ResumeDocument | 核心流程必须经过 ResumeBuilder |
| 内容选择 | Builder 与 Renderer 都可能裁剪 | 只有 Builder 可以选择、排序和限制数量 |
| 姓名与联系方式 | 来源描述不一致 | 只使用请求显式值，缺失留空，不做 fallback |
| 求职意向 | 可能来自 Profile 或其他来源 | V1.3.0 只使用当前 JD 的 `JDAnalysis.position` |
| 个人总结 | 可能由 AI 生成但模板不展示 | V1.3.0 不生成、不渲染 |
| 索引一致性 | 失败可能隐藏 | 新增同步 `VectorIndexJob` 状态和重建能力 |
| LLM 失败 | 可能回退为空模型 | JD 和内容生成使用 strict failure |
| 排版 | Renderer 可截断，页数可影响结果 | Renderer 不截断；超页只告警 |

### 3.3 事实边界

- SQL Experience 是经历事实源；
- Chroma 只用于检索，最终内容必须按命中 ID 回 SQL 读取；
- 姓名、电话、邮箱和所在地只来自请求；字段缺失就留空；
- 求职意向只来自当前 JD 的 `JDAnalysis.position`，不从职业经历库读取；
- V1.3.0 不生成或渲染个人总结/自我评价；
- AI 只能生成已有经历的 bullets；
- 最终条目集合由 ResumeBuilder 决定；
- 模板只提供结构和样式。

以下基础设施不变：SQLite、Chroma 主后端与 numpy 故障回退、豆包模型、内置标准模板、本地文件输出和单用户模式。

## 4. 核心契约

### 4.1 请求

新增 `ResumeDocxGenerateRequest`：

~~~json
{
  "user_id": "demo-user",
  "template_id": "pm_template",
  "jd_text": "目标岗位 JD 原文",
  "profile": {
    "name": "张示例",
    "phone": "13800001111",
    "email": "zhangshili@example.com",
    "location": "示例市"
  },
  "top_k": 5
}
~~~

规则：`jd_text` 必填；`profile` 可省略或只提供部分字段，姓名和联系方式缺失时保持空值；V1.3.0 的目标岗位固定取 `JDAnalysis.position`；`user_id`、`template_id` 可使用当前默认值；`top_k` 范围 1–20。

### 4.2 JD 与生成内容

核心链路使用强类型 `JDAnalysisOut`，不得传递裸 dict。`position` 为空属于关键失败。

新增：

~~~text
GeneratedResumeContent
  experiences:
    - experience_id: string
      bullets: list[string]
~~~

约束：

- `experience_id` 必须属于本次 RAG 命中集合；
- 未知 ID 丢弃并记录 warning；
- AI 不得修改公司、学校、岗位、项目名和时间，也不得生成身份信息或个人总结；
- 单条 bullets 缺失时回退 SQL 的 description + achievements；
- 整体结构化输出失败时终止，不生成空简历。

### 4.3 响应与错误

成功响应至少包含：`file_path`、`file_name`、`download_url`、各阶段状态、匹配 ID、渲染 ID、来源诊断和 warnings。来源诊断至少能表明身份信息来自 request、求职意向来自 JD；不得输出暗示 DB 或 AI 回填身份信息的来源值。

失败响应统一包含：

~~~json
{
  "ok": false,
  "error_code": "LLM_OUTPUT_INVALID",
  "stage": "content_generation",
  "message": "结构化简历内容生成失败",
  "retryable": true
}
~~~

核心错误至少覆盖：LLM 调用/校验失败、索引未就绪、无匹配经历、构建失败、模板失败和文件保存失败。身份字段为空不属于错误。

## 5. SQL 与向量一致性

新增最小 `VectorIndexJob`：

~~~text
id, experience_id, user_id
operation: UPSERT | DELETE
status: PENDING | RUNNING | DONE | FAILED
retry_count, last_error, created_at, updated_at
~~~

规则：

1. Experience 变更和 Job 创建在同一 SQL 事务提交；
2. V1.3.0 在请求内同步执行 Job，不引入 Worker；
3. 成功标记 DONE，失败标记 FAILED 并返回明确错误；
4. 重试必须幂等；
5. 生成前处理 PENDING，并显式重试 FAILED；仍失败则返回 `VECTOR_INDEX_NOT_READY`；
6. 提供按用户从 SQL 全量重建向量的本地函数或脚本，并输出失败 ID。

## 6. 模块与 API 边界

| 模块 | V1.3.0 职责 |
|---|---|
| `ResumeGenerationService` | 唯一核心用例编排；不直接操作 Word XML |
| `JDAnalyzer` | 返回有效 `JDAnalysisOut` |
| `ResumeContentGenerator` | 只生成带 Experience ID 的经历 bullets |
| `ResumeBuilder` | 合并 SQL 事实、排序、选择并构建 ResumeDocument；身份字段只取 request，求职意向取 JD |
| `TemplateRenderer` | 完整渲染 ResumeDocument；`max_items` 仅告警 |
| `LayoutOptimizer` | 轻量样式处理；超页只告警，不删除内容 |
| API Route | 请求校验、调用应用服务、领域错误到 HTTP 映射 |

API 调整：

- 新增 `POST /api/resume/generate-docx`，作为唯一产品主路线；
- 保留上传、经历 CRUD、JD 分析、模板列表和下载接口；
- `/api/resume/generate` 保留一版并标记 deprecated；
- 直接 ResumeDocument → DOCX 接口仅用于模板调试，标记 internal/deprecated，不能替代核心 E2E；
- FastAPI version 更新为 1.3.0。

## 7. 开发任务

标记为“高风险，需源码验收”的任务完成后，必须由可读取源码的验收 Agent 检查相关源码、测试和失败路径。简短结论写入同一份 V1.3.0 RESULT；未通过前版本不能完成。

### P0：核心链路

| Task | 内容 | 完成要求 |
|---|---|---|
| T1 | 建立 V1.2.1 Baseline | 保存 Experience CRUD、RAG、模板、下载和关键内容结果 |
| T2 | 建立强类型契约 | 请求、JD 和 GeneratedResumeContent 不使用裸 dict |
| T3 ⚠️ | ResumeContentGenerator | 只生成 bullets；结构化输出、ID 约束、strict 校验；高风险：事实正确性，需源码验收 |
| T4 ⚠️ | ResumeBuilder | 经历事实只取 SQL；身份字段只取 request 且可为空；求职意向只取 JD；唯一负责选择和裁剪；高风险：事实正确性，需源码验收 |
| T5 | ResumeGenerationService | 串联完整流程；关键失败立即停止 |
| T6 | 核心 API | 新接口、统一错误、旧接口 deprecated、版本更新 |

### P1：正确性与交付

| Task | 内容 | 完成要求 |
|---|---|---|
| T7 ⚠️ | SQL/向量一致性 | VectorIndexJob、同步执行、幂等重试和全量重建；高风险：数据持久化，需源码验收 |
| T8 | 渲染边界 | Renderer 不截断、超容量告警、扫描未替换占位符 |
| T9 | 关键失败显式化 | strict 模式和统一领域异常覆盖关键失败 |
| T10 | 实施汇总 | 开发 Agent 创建状态为“待验收”的 `RESULT.md`，满足 README 的最低交付契约 |

开发 Agent 不更新 README、CURRENT_STATE 或 DECISIONS。V1.3.0 RESULT 至少记录：

- 对应分支、Git commit；未提交时记录工作区状态；
- 实际完成内容、T1–T10 对照、计划偏差和遗留问题；
- API、数据表/模型、模块职责、配置/依赖的实际变化；无变化的类别明确写“无”；
- 验证表，每项标记“通过”“失败”“未执行”或“待独立验收”，并附简短证据或原因；
- T3、T4、T7 的源码验收结论；
- 建议写入 CURRENT_STATE、README 或 DECISIONS 的已验证事实。

## 8. 验收

### 8.1 验证层级

1. 单元测试：Builder 合并、身份字段空值与来源边界、事实保护、Renderer 不截断；
2. 组件测试：VectorIndexJob 状态、失败重试、CRUD 幂等；
3. Stub E2E：固定 LLM/Embedding，保证可重复；
4. Real API Smoke：真实 Ark API 完整跑通一次；耗时不作为 PASS 门槛；
5. 高风险源码验收：检查 T3、T4、T7；
6. 人工验收：确认实际生成内容正确且 DOCX 可用。

### 8.2 必测结果

- 单次核心接口可生成并下载可打开的 DOCX；
- 姓名、电话、邮箱和目标岗位不来自模板；
- 身份字段未提供时保持为空，不从 DB User、AI 或经历库回填；
- 求职意向等于本次 `JDAnalysis.position`，职业经历库不保存该字段；
- V1.3.0 不生成或渲染个人总结/自我评价；
- 最终经历 ID 属于当前用户 SQL 和本次匹配集合；
- 公司、学校、岗位、项目和时间与 SQL 一致；
- 定制 bullets 缺失时正确回退；
- Renderer 输入和输出条目集合一致；
- 模板示例数据和未替换占位符为 0；
- JD 无效、无匹配、索引失败、LLM 非法输出、模板或保存失败均返回明确错误且不生成成功文件；身份信息缺失不属于失败；
- 全量重建前后检索 ID 集合一致；
- Experience 创建、更新、删除重复执行后 SQL 与向量最终一致。

不阻塞 V1.3.0：是否一页、像素级字号/间距、跨软件分页差异、性能和匹配质量调优。

## 9. 实施顺序与质量门

~~~text
T1 → T2 → T3 → T4 → T7 → T5 → T6 → T8 → T9 → T10
→ Stub E2E / Real API Smoke
→ 高风险源码验收
→ 人工验收
→ 文档验收与全局状态更新
~~~

V1.3.0 PASS：

- [x] 唯一核心接口完成 JD → RAG → 结构化内容 → Builder → DOCX；
- [x] 核心接口不要求调用方传 ResumeDocument；
- [x] Builder 是唯一内容选择入口，Renderer 不裁剪；
- [x] SQL/向量失败可见、可重试、可重建；
- [x] 关键 LLM 阶段 strict failure 生效；
- [x] DOCX 可打开，事实正确，无模板数据和占位符残留；
- [x] Stub E2E 全通过，Real API Smoke 至少通过一次；
- [x] T3、T4 事实正确性源码验收通过；
- [x] 用户决定导致的 T3、T4 变更已经完成针对性源码复核；
- [x] T7 持久化与一致性源码验收通过；
- [x] Experience CRUD 和下载回归通过；
- [x] 开发 Agent 已提交“待验收”RESULT，包含实现标识、实际全局变化和分类验证表；
- [x] 人工验收通过；
- [x] 文档 Agent 完成验收，将 RESULT 标记为“已验收”并更新 CURRENT_STATE；必要时更新 README 或 DECISIONS。
