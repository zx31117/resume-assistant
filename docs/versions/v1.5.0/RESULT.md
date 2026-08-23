# V1.5.0 RESULT：事实级内容决策、两层选材与 SQLite 持久化收束

> 状态：开发中
> 分支：`version/v1.5.0`
> 基线 commit：`8c4a0058a4b0a96f6235d3cb09382956c25f39a2`（执行时最新公开 `origin/main`，`v1.4.2` 是其祖先）
> 候选 commit：待 T7 填入
> PLAN：`docs/versions/v1.5.0/PLAN.md`（已批准执行，2026-08-23）

## 1. PLAN Task 对照

| Task | 状态 | 实际结果 |
|---|---|---|
| T0 基线与文档冻结 | 完成 | 从 `origin/main@8c4a005...` 建立 `version/v1.5.0`；`v1.4.2` 是其祖先；批准文档形成增量提交 `92ac0ae` + `bc30f18` |
| T1 源码现状与契约映射 | 完成 | 见 §2；实际文件范围、旧路径和 PLAN 偏差已记录 |
| T2 Fact Schema 与迁移框架 | 待执行 | — |
| T3 SQLite Embedding 与索引任务 | 待执行 | — |
| T4 两层选材与 SelectedEvidenceSet | 待执行 | — |
| T5 改写与 Builder 收缩 | 待执行 | — |
| T6 旧向量实现退出 | 待执行 | — |
| T7 开发验证与候选 | 待执行 | — |

## 2. 源码现状与契约映射（T1）

### 2.1 实际文件范围

**事实源（Experience / 索引 Job）**
- `backend/database/models.py`：`Experience`（id/user_id/type/title/company/time/role/description/skills(JSON)/achievements(JSON)/raw_text/vector_id/timestamps）；`VectorIndexJob`（experience_id/user_id/operation[UPSERT/DELETE]/status[PENDING/RUNNING/DONE/FAILED]/retry_count/last_error/timestamps）；`User`。
- `backend/database/session.py`：SQLite engine（`sqlite:///{settings.SQLITE_PATH}`）+ `SessionLocal` + `get_db` 依赖。
- `backend/database/init_db.py`：`init_db()` → `Base.metadata.create_all`，由 `main.py` lifespan 启动时调用。

**向量持久化（待退出）**
- `backend/vectorstore/chroma_store.py`：Chroma + numpy+JSON 双后端。对外接口 `upsert(exp_id, embedding, document, metadata)` / `delete(exp_id)` / `query_by_embedding(embedding, n_results, where)` / `backend()` / `migration_available()` / `migrate_numpy_to_chroma(overwrite)` / `get_backend_stats()`。模块加载时 try Chroma，失败回退 numpy（`vectors.json`）。
- `backend/vectorstore/__init__.py`：空。

**豆包调用（LLM/Embedding，保留）**
- `backend/services/llm_service.py`：`langchain_openai.ChatOpenAI`（model=`doubao-seed-evolving`，指向 Ark endpoint）。`chat` / `chat_json` / `chat_structured(strict)`。全仓库仅本文件与 `rag_service.py` import langchain。
- `backend/services/rag_service.py`：`_embed(text)` 直接 `urllib` 调用豆包 multimodal embedding API（`/embeddings/multimodal`，model=`doubao-embedding-vision-251215`）；`index_experience` / `delete_experience` / `retrieve`（多因素评分 语义0.5+技能0.3+岗位0.2，TopK）。
- `backend/services/jd_analyzer.py`：`analyze_jd(strict=True)` → `JDAnalysisOut`（7 字段：position/industry/required_skills/preferred_skills/responsibilities/keywords/experience_preferences）。

**索引同步编排（待改造）**
- `backend/services/vector_index_sync.py`：`execute_job`（单 Job 幂等执行）/ `ensure_user_index_ready`（生成前 PENDING+FAILED 重试）/ `rebuild_user_index_from_sql`（从 SQL 全量重建）。
- `backend/services/experience_service.py`：CRUD + `build_index_text` / `metadata`。Experience 写入与 VectorIndexJob 创建同事务，再同步执行 Job。

**Builder / 生成（待收缩）**
- `backend/services/resume_builder.py`：`ProfileResolver.resolve`（身份字段只取 request，求职意向只取 JD）+ `build(...)`（唯一内容选择入口：按 experience_id 合并 AI bullets，否则 SQL description+achievements 回退；按 priority 降序并按 `max_*` 截断）。
- `backend/services/resume_content_generator.py`：`generate_content(strict=True)` → `(GeneratedResumeContent, warnings)`。strict 校验 experience_id 必须在命中集合内，否则丢弃。
- `backend/services/resume_generation_service.py`：`generate_docx` 编排：索引检查 → JD 分析 → RAG TopK → SQL 回读 → ResumeContentGenerator → ResumeBuilder → TemplateRenderer → LayoutOptimizer → 保存 DOCX。
- `backend/models/resume_document.py`：`ResumeDocument` / `Profile` / `EducationItem` / `WorkItem` / `ProjectItem` / `SkillGroup`（渲染无关纯事实层，含 V1.1→V1.2 旧字段 `to_standard()` 迁移）。
- `backend/api/schemas.py`：`GeneratedExperienceItem(experience_id, bullets)` / `GeneratedResumeContent` / `MatchedExperience` / `BuildMeta` / `ResumeDocxGenerateRequest/Response` 等。

**API 路由**
- `backend/api/routes/generate.py`：`POST /api/resume/generate`（V1.1 deprecated，Markdown）/ `POST /api/resume/generate-docx`（V1.3 唯一核心入口）。
- `backend/api/routes/{experience,jd,resume,template}.py`：经历 CRUD、JD 分析、模板填充。

**配置 / 版本 / 入口**
- `backend/core/config.py`：`Settings`（ARK_API_KEY/ARK_BASE_URL/LLM_MODEL/EMBEDDING_MODEL；SQLITE_PATH/CHROMA_PATH/DOCX_OUTPUT_DIR；BASE_DIR 只读源码资产根；RESUME_DATA_DIR 统一 runtime root）。
- `backend/core/version.py`：`APP_VERSION = "1.4.2"`（单一真源）。
- `backend/main.py`：FastAPI app + lifespan(`init_db`) + DomainError handler + routes。
- `backend/requirements.txt`：`chromadb==1.5.9` / `numpy==2.2.6`（待退出）；`langchain==0.3.30` / `langchain-openai==0.3.35` / `openai==1.109.1`（保留）。

**测试入口**
- `backend/_v13_stub_e2e.py`：Stub E2E（独立临时 runtime，atexit cleanup + try/finally）。
- `backend/_v14_t7_regression.py`：V1.4 T7 回归矩阵。
- `backend/run_stub_demo.py` / `backend/_e2e_v13_full.py` / `backend/_v13_validation.py`：其余验证入口。

### 2.2 旧路径（T6 退出目标）

| 旧路径 | 位置 | 退出动作 |
|---|---|---|
| Chroma 活动后端 | `vectorstore/chroma_store.py`（`_chroma_*` + `_BACKEND="chroma"`） | 删除 Chroma 分支与 `import chromadb`；不迁移旧向量字节 |
| numpy+JSON 活动后端 | `vectorstore/chroma_store.py`（`_np_*` + `vectors.json`） | 删除 numpy 持久化与 `migrate_numpy_to_chroma`；numpy 仅作计算库保留 |
| Experience.vector_id | `database/models.py` | 语义改为 Fact 派生（或移除），不再关联 Chroma 文档 id |
| VectorIndexJob（针对 Experience 向量） | `database/models.py` + `vector_index_sync.py` | 改造为 Fact Embedding 重建任务（T3） |
| rag_service.retrieve TopK 内容选择 | `rag_service.py` | 改为第一层固定槽位选材（T4），不再做 TopK 内容决策 |
| Builder priority 排序裁剪 | `resume_builder.py` | 收缩为只装配，不做 JD 相关性选择（T5） |

### 2.3 PLAN 偏差与契约观察

1. **无偏差**：T1 只做映射，未修改源码；PLAN 要求的模块均已定位。
2. **契约缺口（待 T2-T5 补齐）**：
   - `GeneratedExperienceItem` 仅有 `bullets`，无 `fact_refs` —— T5 需扩展为每条 bullet 返回 `fact_refs`。
   - 无 `CandidateExperienceSet` / `SelectedEvidenceSet` 数据结构 —— T4 新建。
   - 无 Fact 表与 schema version —— T2 新建。
   - 无 SQLite BLOB Embedding 派生表 —— T3 新建。
3. **保留项（PLAN §3.3 明确不重构）**：
   - `llm_service` 的 `langchain_openai.ChatOpenAI` 保留，不切换 Provider、不引入多模型。
   - `rag_service._embed` 的 urllib 豆包 multimodal embedding 调用保留。

## 3. 实际全局变化

> T2-T7 完成后填入。按 PLAN §7 / §10 要求记录 API、数据表/模型、模块职责、测试、配置/依赖、版本的实际变化。

| 类别 | 实际变化 |
|---|---|
| API | 待填 |
| 数据表/模型 | 待填 |
| 产品业务链路 | 待填 |
| 模块职责 | 待填 |
| 测试 | 待填 |
| 配置/依赖 | 待填 |
| 版本 | 待填 |

## 4. 替换型变更闭环

> T6 完成后填入：Chroma/numpy+JSON 退出、SQLite BLOB 新状态生效、无并行向量真源。

| 变更 | 新状态 | 旧状态退出 | 回归证据 |
|---|---|---|---|
| 向量持久化 | 待填 | 待填 | 待填 |

## 5. 开发 Agent 验证

> T7 完成后填入测试矩阵结果（按 PLAN §8：Fact/选择/改写、SQLite 与迁移生命周期、回归）。

## 6. PLAN 偏差汇总

> 开发过程中如有字段名调整或实现细节固化，在此记录并给出等价映射。

- 暂无。
