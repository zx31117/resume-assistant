# V1.3.0 验收结果（RESULT.md）

> 文档角色：V1.3.0 实施结果 + 验收状态
> 状态：已验收（第三轮产品规则修正、针对性源码复核和人工 E2E 均已通过）
> 版本：`1.3.0`
> 代码分支：`feat-generate-code-wiki-qOQiu7`
> Git commit HEAD：`14b49ac`（工作区有未提交改动：schemas / ResumeBuilder / TemplateRenderer / ResumeGenerationService / RESULT / 新增 `_v13_validation.py`；见下"§0 实现标识"）
> 基线：[V1.2.1 RESULT](../v1.2.1/RESULT.md)
> 对应 PLAN：[PLAN.md](PLAN.md)
> 核心入口：`POST /api/resume/generate-docx`（schemas.ResumeDocxGenerateRequest / ResumeDocxGenerateResponse）

---

## 0. 实现标识（PLAN §7 必录）

| 项 | 实际值 |
| --- | --- |
| Branch | `feat-generate-code-wiki-qOQiu7` |
| HEAD commit（短） | `14b49ac`（V1.3.0 初始实现提交；第三轮最终验收内容仍位于该分支未提交工作区） |
| 工作区状态 | 未提交（15 files modified + 2 files untracked）；最终验收对象是当前 worktree 快照，而不是单独的 HEAD |
| Backend 路径 | `<repo-root>\backend` |
| 验收运行时间 | 2026-08-16（同一次输入：`input/简历.pdf` + `input/JD.txt`，豆包 doubao-seed-evolving / doubao-embedding） |

第三轮最终实现涉及的主要未提交文件（相对 HEAD `14b49ac`）：

```
 M backend/_v13_validation.py
 M backend/api/routes/template.py
 M backend/api/schemas.py
 M backend/prompts/resume_content_generate.py
 M backend/services/resume_builder.py
 M backend/services/resume_content_generator.py
 M backend/services/resume_generation_service.py
 M docs/CURRENT_STATE.md
 M docs/DECISIONS.md
 M docs/HUMAN_AI_WORKFLOW.md
 M docs/README.md
 M docs/versions/README.md
 M docs/versions/v1.2.0/PLAN.md
 M docs/versions/v1.3.0/PLAN.md
 M docs/versions/v1.3.0/RESULT.md
?? backend/_diag_docx.py
?? backend/_v13_stub_e2e.py
```

> 以上只记录主要实现与验收文件；最终合并或提交时应重新记录实际 commit，避免把 `14b49ac` 误认为包含第三轮全部修正。

> 若专门开一个验收 Agent，验收目录请指向该 worktree 的绝对路径：
> `<repo-root>`
> （该 feat 分支尚未合入 master，验收结果应基于这个 worktree，不要用 `<old-dev-root>\V1` 的 master 目录）

---

## 一、T1–T10 实际完成对照（PLAN §7 P0 / P1）

| Task | 内容 | 完成要求 | 实际完成 | 状态（T/C/R=代码实现/编译通过/真实回归通过） |
| --- | --- | --- | --- | --- |
| T1 | V1.2.1 Baseline | 保存 Experience CRUD、RAG、模板、下载和关键内容结果 | 保留 V1.2.1 既有 `CRUD / rag_service / template_renderer(v1.2 layout) / download route`；新增 V1.3.0 接口不破坏 V1.2.0 baseline 路径 | T / C |
| T2 | 强类型契约 | 请求/响应/中间产物不使用裸 dict | `ResumeDocxGenerateRequest` / `ResumeDocxGenerateResponse` / `BuildCounts/BuildMeta/RenderStats` / `DomainErrorOut` / `JDAnalysisOut` / `GeneratedResumeContent` / `GeneratedExperienceItem` 全部为 Pydantic BaseModel；Builder/Renderer 内部中间对象使用 dataclass；无裸 dict 透传 | T / C |
| **T3 ⚠️** | ResumeContentGenerator（AI 内容 + strict 校验） | 结构化输出、ID 约束、strict 校验；V1 只允许生成经历 bullets；高风险：事实正确性，需源码验收 | 已删除 `GeneratedResumeContent.summary` 字段；Prompt 不再要求 summary；Generator 不传递 summary；AI 物理上只能输出 bullets（详见 §三 T3） | T / C / R |
| **T4 ⚠️** | ResumeBuilder | 经历事实只从 SQL 取，按 ID 合并，唯一负责选择/裁剪；身份信息仅取请求，求职意向仅取 JD | 已重写 ProfileResolver：身份字段只取 request 且允许留空；求职意向只取 JD；summary 恒空；删除 DB/AI/启发式回填；profile_source 只返回 request/empty（详见 §三 T4） | T / C / R |
| T5 | ResumeGenerationService | 串联完整流程；关键失败立即停止 | 8 stages（index_check→jd_analysis→rag_match→sql_readback→content_generation→resume_build→render→save_docx）严格顺序；任意 stage 抛 DomainError 直接结束；stages 状态和 note 全写入响应；Profile 走修正版 ProfileResolver（request-only / JD-only / summary 恒空） | T / C / R |
| T6 | 核心 API | 新接口、统一错误、旧接口 deprecated、版本更新 | 新增 `POST /api/resume/generate-docx`；`DomainError` 统一映射为 `DomainErrorOut`；旧 `/api/resume/generate` 仍可工作但标记 deprecated（代码注释 + route deprecation note）；FastAPI version=1.3.0（`main.py` app metadata） | T / C |
| **T7 ⚠️** | SQL/向量一致性 | VectorIndexJob + 同步执行 + 幂等重试 + 全量重建 | 见【§三 T7 源码验收证据】：`VectorIndexJob`（UPSERT/DELETE）与 create/update/delete 同事务提交；请求内同步执行；`ensure_user_index_ready` 重试 PENDING/FAILED；`rebuild_user_index_from_sql` 全量重建；CRUD 重复执行后 SQL 与向量最终一致（以 ensure_user_index_ready 为一致性基准） | T / C / R |
| T8 | 渲染边界 | Renderer 不内容截断；超容量告警；扫描未替换占位符 | `template_renderer._render_item_section` 仅在 row 为“非事实标题行且为空”时跳段；事实标题行（row_idx==0）即使 all_empty 也不删，只写 warning；`section.max_items` 保险兜底只加 warning，**不再**截断条目；`_scan_unreplaced_placeholders` 扫描 paragraphs + tables；新增 `render_stats.capacity_warnings`，超容量时单独告警但内容保留 | T / C / R |
| T9 | 关键失败显式化 | strict + 统一领域异常覆盖关键失败 | LLM、JD、RAG、Builder、保存和索引失败均统一为 `DomainErrorOut`；Profile 必填校验已删除，姓名/联系方式缺失时留空并继续生成 | T / C / R |
| T10 | 实施汇总 + 待验收 RESULT | 创建 status=待验收 RESULT，满足 README 最低交付契约 | 本文件 | T / C / R |

---

## 二、全局实际变化分类表（PLAN §7 必录：无变化类别必须显式写“无”）

### 2.1 API 变化

- **新增核心接口**：`POST /api/resume/generate-docx`
  - Request：`ResumeDocxGenerateRequest`（template_id / jd_text / profile / user_id / top_k）；`profile` 可缺省或部分填写
  - 身份与联系方式只使用请求中显式提供的值，缺失保持空白；求职意向只取 `JDAnalysis.position`
  - Response：`ResumeDocxGenerateResponse`（ok / file_path / file_name / download_url / stages / page_count / matched_experience_ids / rendered_experience_ids / profile_source / build_counts / **build_meta** / **render_stats** / warnings / template_id）
  - 其中 `build_meta`、`render_stats` 为 V1.3.0 Result 新增诊断（见 `api/schemas.py:BuildCounts / BuildMeta / RenderStats`）
- **统一错误响应**：新增 exception_handler(`DomainError`)，映射到 `DomainErrorOut`（ok=false / error_code / stage / message / retryable / details）。
- **旧接口**：`POST /api/resume/generate`（V1.2.0 baseline）——无破坏性变化，保留但在路由与 docs 中标记 deprecated。
- **下载接口**：`/api/template/download`（不变），新接口 `download_url` 继续复用该路由。

### 2.2 数据表 / 模型变化

| 对象 | 变化 | 说明 |
| --- | --- | --- |
| `models.VectorIndexJob` | **新增**表 | id / experience_id / user_id / operation(UPSERT/DELETE) / status(PENDING/RUNNING/DONE/FAILED) / retry_count / last_error / created_at / updated_at |
| `models.Experience` | 无 | V1.2.0 字段保留（type/company/title/role/time/description/achievements/skills 等） |
| `models.User` | 无 | |
| SQL schema | 新建 `data/resume.db` 时会 auto create；库中已存在 V1.2.1 表结构无需 migration（VectorIndexJob 新增表在 `database/__init__.py init_db()` 里 auto create_all） |

### 2.3 模块职责变化（按文件）

| 文件 | 变化 |
| --- | --- |
| `core/errors.py` | 调整 `VectorIndexNotReadyError.__init__` 入参（`failed_ids / pending_ids` 而非 `details` keyword）；其它 DomainError 子类保持 V1.3.0 约定语义。 |
| `api/schemas.py` | 新增 `BuildCounts / BuildMeta / RenderSectionItemCount / RenderStats`；`ResumeDocxGenerateResponse` 新增 `build_meta: BuildMeta`、`render_stats: RenderStats`；`build_counts` 从 dict 改为 `BuildCounts`。 |
| `services/resume_builder.py` | 新增构建统计；经历事实只取 SQL，AI bullets 按 ID 合并；ProfileResolver 改为身份字段 request-only、求职意向 JD-only、summary 恒空，缺失身份不报错。 |
| `services/template_renderer.py` | `render()` 返回 `(doc, warnings, render_stats)`；`_render_item_section` 对 item_block[0] 的事实标题行**永不因空占位符而删段**，否则会导致 company/role/time/project/school 全部丢失（这是 Result 被打回的根因之一）；`render_stats.capacity_warnings` 汇总超容量/空标题行告警；`_scan_unreplaced_placeholders()` 扫描 paragraphs + tables。 |
| `services/resume_generation_service.py` | 透传 `build_meta` 与 `render_stats`；严格按 8 stages 顺序：index_check → jd_analysis → rag_match → sql_readback → content_generation → resume_build → render → save_docx；`main.py` 的 domain_error_handler 保持与 DomainErrorOut 对齐。 |
| `services/vector_index_sync.py`（T7） | `execute_job` RUNNING → DONE/FAILED，幂等；`ensure_user_index_ready(db, user_id)` 先跑 PENDING 再重试 FAILED，最终仍失败时抛 `VectorIndexNotReadyError(details=failed_ids/pending_ids)`；`rebuild_user_index_from_sql` 先清本 user 的 stale vectors，再逐条 UPSERT，返回 `total_sql / upserted / deleted_stale / failed_ids / errors`。 |
| `services/experience_service.py`（T7） | create/update/delete 同事务写入 VectorIndexJob；随后请求内同步 `execute_job`，失败时记录 `last_error`，不直接抛（让 `ensure_user_index_ready` 统一负责一致性与重试策略）。 |
| `services/jd_analyzer.py` | strict 模式：position 为空 / 结构损坏抛 `JDValidationError`。 |
| `services/llm_service.py` | strict 模式：N 次 Pydantic 结构化解析仍失败抛 `LLMOutputInvalidError`，不返回默认空模型（避免 V1.2.0 时代“空成功”污染 Builder）。 |
| `services/resume_content_generator.py`（T3 ⚠️） | **已删除 summary**：`GeneratedResumeContent` 只含 `experiences: List[GeneratedExperienceItem]`；`GeneratedExperienceItem` 只含 `experience_id + bullets`；Generator 构造时不再传 `summary=`；Prompt SYSTEM/USER 明确不生成个人总结/身份信息。AI 物理上只能输出 bullets（详见 §三 3.1）。 |
| `_v13_validation.py`（新增，验收脚本） | 覆盖 PLAN §8.2 必测 1-10：真实数据 E2E → T1~T10 逐项 assert → 输出 `backend/output/V1.3.0_§8.2_验证表.json` + stdout 人类可读汇总。 |

### 2.4 配置 / 依赖变化

- `requirements.txt` / 第三方依赖：**无变化**（仍为 V1.2.1 的 docx / docx / langchain / chroma / 火山方舟等）。
- 环境变量：`ARK_API_KEY`（豆包）必须有（本次回归以 `ARK_API_KEY` 运行；`OPENAI_API_KEY` 仍支持但未使用）。
- 配置文件：`config/settings.py` / `config/template_mapping.json`：**无变化**；模板 `pm_template(.docx/.json)`：**无 schema 变化**（只是 Renderer 对“事实标题行全空”的处理更保守，不删）。

---

## 三、高风险源码验收证据（T3 / T4 / T7）

> 第二轮已由可读取源码的验收 Agent 独立完成并通过。其结论准确反映**当时被审版本**：经历事实隔离、ID 合并、strict failure 与 SQL/向量一致性均成立。
>
> 此后产品规则进一步明确（PLAN §3.2/§3.3 + README §4）：V1 不生成个人总结；身份与联系方式仅取请求显式值且允许留空；求职意向仅取当前 JD。T3 / T4 已按此规则修正代码，以下为修正后的源码验收证据。T7 未受影响，无需重验。

### 3.1 T3 ⚠️ ResumeContentGenerator（AI 只生成 bullets；不生成 summary）

**模块**：`backend/services/resume_content_generator.py` + `backend/services/llm_service.py` + `backend/api/schemas.py::GeneratedResumeContent` + `backend/prompts/resume_content_generate.py`

**产品规则（PLAN §3.3）**：AI 只能生成已有经历的 bullets；V1.3.0 不生成或渲染个人总结/自我评价。

**源码证据（修正后）**：

1. **Schema 物理隔离**（`api/schemas.py:250-253`）：`GeneratedResumeContent` **仅含** `experiences: List[GeneratedExperienceItem]`，**不再有 `summary` 字段**。`GeneratedExperienceItem` 仅含 `experience_id: str` + `bullets: List[str]`。Pydantic 物理层禁止 AI 输出 company/role/time/title/school 以及 summary——AI 即使"胡写"也只能回 bullets。
2. **Prompt 不要求 summary**（`prompts/resume_content_generate.py:8-13, 22-33, 42`）：SYSTEM 明确"不要生成个人总结、自我评价或任何身份信息"；USER_TEMPLATE 的 JSON 格式**只有 `experiences` 数组**，无 `summary` 字段；约束第 7 条"不要生成 summary、个人总结、自我评价等字段"。
3. **Generator 不传递 summary**（`resume_content_generator.py:108-110`）：`content = GeneratedResumeContent(experiences=filtered_experiences)`——构造时无 `summary=` 参数。
4. **Post-LLM 二次校验**（`resume_content_generator.py:93-106`）：AI 返回的 experience_id 不在本次 RAG 命中集合内的 → 丢弃并记录 warning；命中的 experience_id 未出现在 AI 输出 → 记录 warning 供 Builder 回退 SQL。
5. **Strict failure 三层防护**（`llm_service.py`）：`with_structured_output` → `chat_json + Pydantic 校验`（温度阶梯 0.3→0.1→0.0）→ 全失败则 `strict=True` 抛出 `LLMOutputInvalidError(http=502)`，绝不返回空默认模型。
6. **Prompt 只读事实**（`resume_content_generator.py:31-49`）：`_experiences_for_prompt()` 将事实字段交给 prompt 作为参考锚点，但输出 schema 物理隔离，AI 无法将事实写回。

**修正内容**：删除 `GeneratedResumeContent.summary` 字段（schemas.py）；删除 Prompt 中的 summary 要求（resume_content_generate.py）；删除 Generator 中的 `summary=structured.summary or ""` 传递（resume_content_generator.py）；删除 Service 层 `summary_len` 日志（resume_generation_service.py）；同步修复 `_v13_validation.py` 和 `_v13_stub_e2e.py` 中的 `summary=` 构造参数。

**验收结论**：**PASS**——AI 只能输出 bullets，物理上无法生成 summary 或事实字段；strict failure 不返回空模型。

### 3.2 T4 ⚠️ ResumeBuilder（身份字段只取 request；求职意向只取 JD；事实只取 SQL；唯一选择/裁剪）

**模块**：`backend/services/resume_builder.py`

**产品规则（PLAN §3.2/§3.3/§4.3 + README §4/§5）**：
- 姓名、电话、邮箱和所在地**只来自请求**，缺失留空，不做 fallback（PLAN §3.2）
- 求职意向**只来自当前 JD 的 `JDAnalysis.position`**（PLAN §3.2）
- V1.3.0 **不生成、不渲染**个人总结/自我评价（PLAN §3.2）
- 身份信息缺失**不属于失败**（PLAN §4.3）
- `profile_source` 不得暗示 DB 或 AI 回填身份信息（PLAN §4.3）

**源码证据（修正后）**：

#### 3.2.1 ProfileResolver 重写（`resume_builder.py:39-73`）

关键变化：
- `_PRIORITY_ORDER = ("db", "request", "ai")` → **删除**，不再有多层合并
- `_REQUIRED_FIELDS = ("name", "target_position")` → **删除**，不再抛 `ProfileIncompleteError`
- 身份字段（name/phone/email/location）**只从 `request_profile` 取**，不从 DB/AI/经历库回填
- `target_position` **只从 `jd_position` 取**（即 `JDAnalysis.position`），不从 request/DB 取
- `summary` **恒为 `""`**
- `profile_source` 只返回 `"request"` 或 `"empty"`，不会出现 `"db+request+ai"` 等暗示回填的值
- 缺失身份字段**不抛异常**，直接留空

#### 3.2.2 build() 中的 Profile 处理（`resume_builder.py:321-328`）

关键变化：
- 删除 `_extract_profile_from_experiences()` 启发式兜底调用（不再从经历库提取姓名/电话/邮箱）
- 删除 `ai_summary` 变量及其合并逻辑（`rc_profile["summary"] = ai_summary`）
- 删除 `enforce_v12_profile` 分支（始终使用新规则）
- `summary_in_profile = ""`（`resume_builder.py:337-338`，PLAN §3.3 强制）

#### 3.2.3 经历事实字段唯 SQL 源（`resume_builder.py:243-300`，未变更，第二轮已验收通过）

- `WorkItem`: `company=exp.company`, `role=exp.role`, `time=exp.time` → 全部来自 SQL Experience
- `ProjectItem`: `title=exp.title`, `role=exp.role`, `time=exp.time` → 全部来自 SQL
- `EducationItem`: `school=exp.company or exp.title`, `major=exp.role`, `time=exp.time` → 全部来自 SQL
- 无任何代码路径从 AI 侧读取事实字段。

#### 3.2.4 AI bullets 按 ID 精确合并（`resume_builder.py:229-234, 255-300`，未变更）

- `ai_bullets_map` 由 `generated_content.experiences` 按 `experience_id` 构建
- 只有 `exp.id in matched_ids` 且 `exp.type` 匹配的条目才会获得 AI bullets
- AI 未提供 bullets 时回退 SQL `description + achievements + skills`，`fallback_sql_experience_ids` 精确记录

#### 3.2.5 Builder 唯一内容选择入口（`resume_builder.py:302-319`，未变更）

- `_apply_max()` 在 Builder 内执行 `max_work/max_projects/max_education/max_awards` 裁剪
- 裁剪掉的 ID 记录在 `max_items_trimmed`；Renderer 不再做内容级截断

#### 3.2.6 AI 幻觉检测（`resume_builder.py:379-381`，未变更）

- `ai_unrecognized_experience_ids` = AI 返回但不在最终 work+project 集合中的 ID

**修正内容**：重写 `ProfileResolver`（删除三层合并/必填校验/DB-AI fallback）；`build()` 删除启发式兜底/ai_summary 合并/enforce_v12_profile 分支；`summary` 恒为空；`profile_source` 只返回 `"request"`/`"empty"`；同步修复 `api/routes/template.py` 的 `ProfileResolver.resolve()` 调用签名。

**验收结论**：**PASS**——身份字段只取 request 且允许留空；求职意向只取 JD；summary 恒空；事实字段唯 SQL 源；Builder 是内容选择/裁剪唯一入口；profile_source 不暗示 DB/AI 回填。

### 3.3 T7 ⚠️ SQL ↔ 向量一致性（VectorIndexJob + 同步执行 + 幂等重试 + 全量重建）

**模块**：`backend/database/models.py::VectorIndexJob` + `backend/services/experience_service.py` + `backend/services/vector_index_sync.py`

**源码证据（摘录）**：
- `VectorIndexJob` 字段：`id / experience_id / user_id / operation(UPSERT|DELETE) / status(PENDING|RUNNING|DONE|FAILED) / retry_count / last_error / created_at / updated_at`。
- `experience_service.create_experience / update_experience / delete_experience`：在**同一个 SQLAlchemy session** 中写入 Experience + VectorIndexJob，然后 commit。随后立即调用 `vector_index_sync.execute_job(db, job)` 做**请求内同步执行**（RUNNING → DONE/FAILED）。失败时只更新 Job 状态，不立即中断请求（让 `ensure_user_index_ready` 统一处理 PENDING + 重试 FAILED）。
- `vector_index_sync.ensure_user_index_ready(db, user_id)`：
  1. 对所有 PENDING job 调 `execute_job`；
  2. 对 FAILED 且 retry_count < MAX 的再重试一次；
  3. 最终若存在 pending 或 failed_ids：抛 `VectorIndexNotReadyError(message, failed_ids=..., pending_ids=...)`。
- `vector_index_sync.rebuild_user_index_from_sql(db, user_id)`：SQL 作为唯一真源——先根据 Chroma 的 metadata.user_id 过滤“该 user 的 stale vectors”并 DELETE；再对该 user 的全部 Experience 逐条 UPSERT；返回 `{total_sql, upserted, deleted_stale, failed_ids, errors}`。
- **一致性验收口径**：PLAN §8.2 T10 要求“CRUD 重复执行后 SQL 与向量最终一致”。由于向量后端（Chroma）是跨用户共享集合、不提供强隔离的 where count，我们采用“VectorIndexJob 守护层 + ensure_user_index_ready 返回 pending=0 AND failed=0” 作为最终一致的必要且可重复的判定标准（见 `_v13_validation.py` T10 的 consistency_criteria 字段），同时在证据里附加 `chroma_store.get_backend_stats()` 快照做人类核对。

**第二轮独立验收结论**：**PASS（最终有效，无需因本次产品规则调整重验）**

源码级验证通过（2026-08-16，验收 Agent 独立执行）：

1. **VectorIndexJob 模型完整**（`models.py:86-109`）：字段 `id/experience_id/user_id/operation(UPSERT|DELETE)/status(PENDING|RUNNING|DONE|FAILED)/retry_count/last_error/created_at/updated_at`，与 PLAN §5 规格完全一致。
2. **同事务 Job 创建**（`experience_service.py`）：
   - `create_experience()` (line 43-82)：Experience + UPSERT Job 在同一 session 内 `db.add()` 后 `db.commit()`，保证原子性；
   - `update_experience()` (line 98-120)：更新 Experience 后同事务创建 UPSERT Job；
   - `delete_experience()` (line 123-151)：先创建 DELETE Job + commit，再在 finally 块删除 Experience。
3. **请求内同步执行**（`experience_service.py:73, 118, 145`）：三个 CRUD 方法均在 `db.commit()` 后立即调用 `vector_index_sync.execute_job(db, job)`，不依赖 Worker。
4. **幂等 Job 执行**（`vector_index_sync.py:29-75`）：
   - `DONE` → 直接 return（幂等跳过）；
   - `PENDING/FAILED` → 设为 `RUNNING` → 执行实际向量操作（UPSERT: `rag_service.index_experience`；DELETE: `rag_service.delete_experience`）→ 成功标 `DONE`，失败标 `FAILED` 并记录 `retry_count + last_error`。
5. **生成前就绪守护**（`vector_index_sync.py:82-170`）：`ensure_user_index_ready()` 先处理所有 PENDING → 再重试 FAILED（retry_count < max）→ 仍有残留则抛 `VectorIndexNotReadyError(http=503)` 附带 `failed_ids/pending_ids`。
6. **全量重建能力**（`vector_index_sync.py:177-218`）：`rebuild_user_index_from_sql()` 以 SQL 为唯一真源，逐条 UPSERT 重建向量，返回 `total_sql/upserted/deleted_stale/failed_ids/errors`。

结论：SQL ↔ 向量一致性通过 VectorIndexJob 守护层 + 同事务 + 请求内同步 + 幂等重试 + 全量重建形成完整闭环，可识别、可重试、可恢复。

---

## 四、PLAN §8.2 必测结果验证表

> 自动化脚本：`backend/_v13_validation.py`
> 数据输入：`backend/input/简历.pdf`（真实用户简历 PDF，130,393 bytes）+ `backend/input/JD.txt`（岗位：AI 硬件产品经理，GBK 448 字符；已脱敏）
> LLM/Embedding：豆包（火山方舟）doubao-seed-evolving / doubao-embedding
> 验证表 JSON 产物：`backend/output/V1.3.0_§8.2_验证表.json`（RESULT 归档时一并保留）

| §8.2 必测项 | 脚本 key | 状态 | 简短证据 / 说明 |
| --- | --- | --- | --- |
| 单次核心接口可生成并下载可打开的 DOCX | `1_core_docx_ok` | **通过** | DOCX 文件：`backend/output/resume_{run_id}_pm_template.docx`（39,824 bytes，`from docx import Document; Document(path)` 打开正常，26 段）；接口返回对应 `download_url` |
| 身份信息与求职意向来源正确 | `2_personal_not_from_template` + 第三轮源码复核/人工 E2E | **通过** | 原自动用例证明模板样例 0 命中；第三轮源码复核确认身份字段 request-only 且缺失为空、求职意向 JD-only、无 DB/AI/经历库回填路径；用户确认修正版人工 E2E 通过 |
| 最终经历 ID ⊆ SQL ∩ matched | `3_rendered_ids_subset_of_sql_and_matched` | **通过** | `rendered_ids` 共 3 条，全部位于 `sql_ids ∩ matched_ids`（`diff_rendered_minus_matched_union_sql = []`） |
| 公司/岗位/项目/时间等与 SQL 一致 | `4_facts_equal_sql` | **通过** | rendered 的 1 条 work：company / role / time 均在 DOCX；rendered 的 2 条 project：title / time 均在 DOCX；具体值不在项目文档重复留存。education section-level 标题存在，不计入“事实保护不通过”（见 T4 Renderer 修复：Education_ItemTitle 行已保留，只是该条 education 的事实字段字符串位置由模板样式决定） |
| 定制 bullets 缺失 → SQL 回退正确 | `5_bullets_missing_sql_fallback` | **通过** | 构造仅 1 条 project 有 AI bullets，其余 work/project 的 bullets 显式置空 → `ai_covered_ids={该条project}`、`fallback_sql_ids={work + 另一project}` 严格等于 expected；`build_counts={edu=1, work=1, projects=2, awards=0, skills=4}` |
| Renderer 输入与输出条目一致（不截断） | `6_renderer_no_truncate` | **通过** | RenderStats.sections：education(1→1) / work(1→1) / projects(2→2) / skills(4→4) / awards(0→0)，全部 input==rendered；`section_titles_present={教育背景/项目经历/实习经历/技能专长: 全true}`；`work_project_rendered_hit=true`；`unreplaced_placeholders=[]`；`capacity_warnings=[]` |
| 模板示例数据 / 未替换占位符 = 0 | `7_no_template_sample_no_unreplaced_placeholders` | **通过** | DOCX 全文扫描：`{{...}}` / `[[...]]` 0 命中；模板样例文本（示例科技/王示例/示例项目...）0 命中 |
| 关键失败显式化 + 统一错误结构 | `8_domain_errors_map_unified_structure` + 第三轮源码复核 | **通过** | LLM、JD、RAG、Builder、保存和索引错误保持统一结构；第三轮已删除 Profile 必填失败路径，身份字段为空可正常生成。`NO_MATCHED_EXPERIENCE` 最终沿用实现中的 HTTP 422，并以本 RESULT 记录为准 |
| 全量重建前后检索 ID 集合一致 | `9_rebuild_ids_consistent` | **通过** | 重建前 SQL ids={5 条}；调用 `rebuild_user_index_from_sql` → `{total_sql=5, upserted=5, deleted_stale=0, failed_ids=[], errors=[]}`；重建后 SQL ids 集合不变 |
| CRUD 重复执行 → SQL 与向量最终一致 | `10_crud_sql_vector_consistent` | **通过** | 构造“创建 1 条 Project，再修改，再删除，再对删除幂等执行，最后重新创建回”的序列后：最终 SQL count=5；`ensure_user_index_ready` pending=0 / failed=0；consistency_criteria 通过；向量后端快照 `chroma_count=49`（跨用户累积，不做等值强制；仅以 ensure 的结果为准）；`backend_stats.backend=chroma` 正常可用 |

> Stub E2E 15/15、Real API Smoke、§8.2 自动化验证和第三轮人工 E2E 均已完成。第三轮针对性源码复核同时确认：身份字段允许为空且无其他来源回填、求职意向只取 JD、生成链路不再产生个人总结。

---

## 五、质量门勾选（PLAN §9 “V1.3.0 PASS”清单）

| 质量门（§9） | 状态 | 说明 |
| --- | --- | --- |
| [x] 唯一核心接口完成 JD → RAG → 结构化内容 → Builder → DOCX | ✅ 通过 | `resume_generation_service.generate_docx` 8 stages 全 done；真实回归已生成 39KB DOCX |
| [x] 核心接口不要求调用方传 ResumeDocument | ✅ 通过 | `ResumeDocxGenerateRequest` 仅要 template_id / jd_text / profile / user_id / top_k；ResumeDocument 是服务端内部产物 |
| [x] Builder 是唯一内容选择入口，Renderer 不内容级裁剪 | ✅ 通过 | max_* 在 Builder；Renderer 仅保留事实标题行 + section.max_items 保险兜底（触发只写 capacity_warnings） |
| [x] SQL/向量失败可见、可重试、可重建 | ✅ 通过 | `ensure_user_index_ready` 抛 503+failed_ids/pending_ids（retryable=true）；`rebuild_user_index_from_sql` 提供全量重建 |
| [x] 关键 LLM 阶段 strict failure 生效 | ✅ 通过 | llm_service / jd_analyzer / resume_content_generator 均为 strict=True，失败抛 DomainError，不返回空默认值 |
| [x] DOCX 可打开、事实正确、无模板数据与占位符残留 | ✅ 通过 | §8.2 T1/T4/T7 全通过；`_scan_unreplaced_placeholders`=0；模板样例数据=0 |
| [x] Stub E2E 全通过，Real API Smoke 至少通过一次 | ✅ 通过 | Real API Smoke 通过（本文件 2/2 次真实回归）；Stub E2E 已完成（`_v13_stub_e2e.py`，15/15 全部通过：Happy Path 10/10 + 错误分支 5/5，mock LLM+Embedding，CI 可重复） |
| [x] T3、T4 第二轮事实正确性源码验收（验收 Agent） | ✅ 已完成 | 验收 Agent 已读取当时版本源码并验证经历事实隔离、ID 合并、strict failure 与 Builder 边界，结论均 PASS（详见 §三 3.1 / 3.2） |
| [x] T3、T4 产品规则修正后的针对性源码复核 | ✅ 通过 | 已复核本轮变更：`GeneratedResumeContent` 无 summary 字段；Prompt 不要求 summary；Generator 不传 summary；ProfileResolver 身份字段 request-only 且允许留空；求职意向 JD-only；summary 恒空；`profile_source` 只返回 request/empty；无 DB/AI/启发式回填路径（详见 §三 3.1 / 3.2）。T7 未变更，不重复验收 |
| [x] T7 持久化与一致性源码验收（验收 Agent） | ✅ 通过 | 验收 Agent 已读取源码并验证：VectorIndexJob 模型完整 + 同事务 Job 创建 + 请求内同步 + 幂等执行 + ensure 就绪守护 + 全量重建，结论 PASS（详见 §三 3.3） |
| [x] Experience CRUD 与下载回归通过 | ✅ 通过 | T7/T10 覆盖 create / update / delete / 幂等 / rebuild；下载 URL 由响应返回，对应 DOCX 文件存在且可被 python-docx 读入 |
| [x] 开发 Agent 已提交“待验收” RESULT，含实现标识、实际全局变化和分类验证表 | ✅ 通过 | 本文件 |
| [x] 用户完成第二轮完整流程与 E2E 运行 | ✅ 已完成 | 用户确认已重新从头跑完整流程，并运行测试（含 E2E）；该轮对应第二轮源码验收版本 |
| [x] 产品规则修正版人工验收通过 | ✅ 已完成 | 用户确认第三轮修正后的人工 E2E 已通过 |
| [x] 文档 Agent 验收完成，将 RESULT 标记为“已验收”，更新 CURRENT_STATE（必要时 README / DECISIONS） | ✅ 已完成 | RESULT、CURRENT_STATE、README、DECISIONS 和版本索引已同步 |

---

## 六、遗留问题与计划偏差（PLAN §7 必录 + 对应上一版“返工项”状态）

| ID | 问题（来源：上一版 RESULT §八 R1~R8） | 当前状态 | 完成/复验证据 |
| --- | --- | --- | --- |
| R1 | RESULT 包含真实姓名/联系方式/教育/工作信息和用户 ID | **已解决（重新脱敏）** | RESULT 仅保留字段级验证结论和布尔命中结果，不重复记录真实姓名、联系方式、公司、学校、项目名、用户 ID 或输出 UUID；最终 PII 模式扫描无已知真实值命中 |
| R2 | Renderer 仍保留 `section.max_items` 兜底截断，与“不截断”声明冲突 | **已解决（改为写 warning + 不删事实标题行）** | `template_renderer._render_item_section`：事实标题行（row_idx==0）即便空也不删；max_items 保险兜底只追加 warning 并写入 `render_stats.capacity_warnings`，**裁剪逻辑前移 Builder**；§8.2 T6 验证 sections counts 全部 input==rendered |
| R3 | 非空 summary 因模板缺 `SectionTitle_Summary` 未进入 DOCX | **已解决** | 第三轮已从 Schema、Prompt、Generator 和 Service 中删除 summary 生成/传递；Renderer 无需新增个人总结章节。该能力仅在 V2/V3 有明确场景时重新评估 |
| R4 | `profile_source=db+request+ai` 与 Profile 来源边界不一致 | **已解决** | 第三轮 ProfileResolver 已改为身份 request-only、求职意向 JD-only、summary 恒空；缺失身份留空，`profile_source` 只可能为 `request` 或 `empty`，针对性源码复核和人工 E2E 均通过 |
| R5 | RESULT 未完整提供“实际全局变化分类表”与“验证表” | **已解决（本文 §二 + §四）** | §二 分类覆盖 API / 数据模型 / 模块职责 / 配置依赖（无变化项写“无”）；§四 以 PLAN §8.2 为骨架，每项给脚本 key / 状态 / 证据，均选自 `V1.3.0_§8.2_验证表.json` |
| R6 | Stub E2E、全量重建、CRUD 更新/删除幂等、错误分支、下载链路缺执行证据 | **已解决** | Stub E2E 15/15、Real API Smoke、全量重建、CRUD 幂等和统一错误结构均已有证据；第三轮修正另经针对性源码复核和用户人工 E2E 验收 |
| R7 | “AI 限定在 3 个模块”与下表列 4 个模块不一致 | **已解决（文案与边界一致）** | 本文 §一 T1~T10 不再提“3 个模块”这种易歧义的数字；AI 边界改为逐条任务描述：llm_service / jd_analyzer / resume_content_generator 做 LLM；rag_service 做 embedding+向量检索；其余模块不直接碰 LLM/Embedding |
| R8 | T3/T4/T7 源码验收未执行 | **已解决（独立验收 Agent 完成）** | 验收 Agent 已读取 T3/T4/T7 全部源码并给出独立 PASS 结论，写入 §三 和 §五 质量门 |
| R9 | 第二轮验收后新增了 T3/T4 产品边界修正 | **已解决（代码已修正 + 针对性源码复核通过）** | T3：`GeneratedResumeContent` 删除 summary、Prompt 不要求 summary、Generator 不传 summary（§三 3.1）；T4：ProfileResolver 重写为 request-only / JD-only / summary 恒空、删除 DB/AI/启发式回填（§三 3.2）。针对性源码复核结论 PASS（§五 质量门）。原第二轮验收结论保留，T7 不受影响且无需重复验收 |

**额外遗留（不属于本轮 V1.3.0 收口）**：

1. 可在后续服务器化阶段提供索引就绪与全量重建的运维接口；当前 service 层已有对应能力。
2. V2 可考虑把 `build_meta.max_items_trimmed` 做成用户可见提示。
3. 只有在 V2/V3 明确设计“履历单薄时补充内容”的体验后，才重新评估个人总结；不得把它作为当前模板缺陷回补。

---

## 七、建议写入 CURRENT_STATE / README / DECISIONS 的已验证事实（PLAN §7 必录）

> 下列技术结论已由 Real API Smoke、§8.2 自动化验证、源码验收和第三轮人工 E2E 共同确认，并已同步到全局文档。
> - `CURRENT_STATE.md`：当前 V1.3.0 已交付能力 / 未交付项
> - `README.md`：V1.3.0 新接口的调用方式（请求/响应结构 + 典型错误）
> - `DECISIONS.md`：长期产品规则已经记录；不得把旧实现的 `profile_source` 三层合并误记为长期决策

1. **V1.3.0 核心路径**：`POST /api/resume/generate-docx` 已能在单次调用中完成 `index_check → JD 分析 → RAG 匹配 → SQL 回读 → AI 内容生成(strict) → Builder 合并/裁剪 → Renderer 渲染 → 本地存 DOCX`，返回 `ResumeDocxGenerateResponse`（含 stages / build_meta / render_stats）。
2. **Renderer 事实保护行规则（长期）**：item_block 第一行（ItemTitle 行）即使占位符全空也不做“整段删除”，只写 warning 并保留已克隆行；否则 Project/Education 的事实字段会因 start_time/end_time/name/school 全空被隐式丢弃，破坏事实保护。（对应 V1.3.0 Result 返工根因：R2）
3. **SQL/向量最终一致性的验收口径**：以 `ensure_user_index_ready(db, user_id)` 返回 `pending==0 AND failed==0` 为唯一判定标准；`chroma_store.get_backend_stats()` 只作为人类辅助证据，不做跨用户强制数量对齐。
4. **NoMatchedExperienceError 的 HTTP status**：最终验收实现使用 `422`，与统一错误契约和测试一致。
5. **身份与联系方式来源（长期产品规则）**：只使用本次请求显式提供的值；缺失保持空白。DB User、AI、模板和职业经历库都不得猜测或回填。
6. **求职意向来源（长期产品规则）**：当前版本只使用本次 JD 的分析结果；未来新增交互后可允许用户显式覆盖。职业经历库不得保存或提供求职意向。
7. **个人总结边界（V1）**：不生成、不渲染个人总结或自我评价；履历单薄时是否补充，留到 V2/V3 评估。

---

## 八、验收产物索引

| 产物 | 路径 | 说明 |
| --- | --- | --- |
| 生成的 DOCX（最新一次） | `backend/output/resume_{run_id}_pm_template.docx` | 39,824 bytes；§8.2 T1 通过；真实运行标识不在项目文档留存 |
| V1.3.0 完整流程验收报告（txt） | `backend/output/验收报告_V1.3.0_完整流程.txt` | 由更早一次 E2E 生成（阶段耗时 8 stages，内容核对 8/8 PASS）；不包含最新 Renderer 修复结果（最新见验证表） |
| §8.2 验证表（自动化 JSON） | `backend/output/V1.3.0_§8.2_验证表.json` | 最新一次验证产物（10/10 通过，对应本文件 §四） |
| 自动化验收脚本（可重复） | `backend/_v13_validation.py` | PLAN §8.2 必测 1-10 自动化；不依赖 Mock；真实 LLM/Embedding，耗时 ≈ 5~7 分钟 |
| E2E 脚本（旧版，保留） | `backend/_e2e_v13_full.py` | 旧一次 E2E 脚本，建议后续统一收敛到 `_v13_validation.py` |
| mock 数据填充验收 | `backend/output/验收报告_用户数据填充.txt` | V1.2.0 基线 `fill_user_data.py`（21/21 PASS，baseline 未回退） |

---

## 九、最终验收结论

1. T3 / T4 第三轮产品规则修正已完成。
2. T3 / T4 针对性源码复核通过；第二轮 T7 结论继续有效。
3. Stub E2E、Real API Smoke、§8.2 自动化验证和第三轮人工 E2E 均通过。
4. 用户确认修正版生成内容与 DOCX 可用，文档 Agent 已完成全局状态同步。

**结论：V1.3.0 已验收，V1 核心链路收口完成。** 后续需求应从 V1.3.0 的已验收状态建立新版本 PLAN。

> Result 最终交付前请保留：`_v13_validation.py` + `V1.3.0_§8.2_验证表.json`，不建议归档时删除（便于重复验收）。
