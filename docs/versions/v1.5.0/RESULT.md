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
| T2 Fact Schema 与迁移框架 | 完成 | 新增 `Fact`/`FactType`/`SchemaVersion` 模型、`database/migrations.py`（备份+顺序迁移+幂等 Fact 生成+核对）、`services/fact_service.py`（显式修改+失效钩子）、`_v15_t2_fact_migration.py` 验证（35/35）；errors 增 `FactNotFoundError`/`FactModificationError`/`MigrationError` |
| T3 SQLite Embedding 与索引任务 | 完成 | 新增 `FactEmbedding`/`EmbeddingStatus` 模型（`fact_embeddings` 表：fact_id+embedding_fingerprint 唯一、BLOB float32 向量、dimension/dtype/revision/hash/status）；新增 `services/embedding_service.py`（fingerprint、BLOB 编解码、upsert、失效钩子 wire、rebuild 全量重建、ensure_ready 阻断、query_facts 内存精确 cosine、status_summary）；`_v15_t3_embedding.py` 验证 45/45 通过 |
| T4 两层选材与 SelectedEvidenceSet | 完成 | 新增 `services/selection_service.py`：第一层 `select_experiences` 固定槽位（工作/实习最近最多3、项目/论文三年窗口内相关性最多2、合计<2 补1校园）、`CandidateExperienceSet`/`ExperienceSlot` 数据结构；第二层 `select_evidence` 只在入选经历中用 `embedding_service.query_facts` 选 fact_refs、`SelectedEvidenceSet`/`EvidenceEntry`/`FactRef` 可序列化可核对、`is_expired`（jd_hash/rule_version/baseline_date/fact revision-hash 变化即过期）；确定性日期解析与相关性评分（不依赖旧向量后端）；`_v15_t4_selection.py` 验证 53/53 通过 |
| T5 改写与 Builder 收缩 | 完成 | 新增 `prompts/constrained_rewrite.py`（受约束改写 prompt）；新增 `services/constrained_rewrite.py`（`rewrite_with_evidence`：LLM 只接收入选经历+表达侧重+可使用事实，每条 bullet 返回 fact_refs，越界经历/越界 fact_refs 拒绝并告警，材料不足返回 insufficient=true 不补造，不写回 Fact）；扩展 `api/schemas.py`（`GeneratedBullet`/`GeneratedExperienceItemV15`/`GeneratedResumeContentV15`）；`models/resume_document.py` WorkItem/ProjectItem 增 `fact_refs` 字段；`resume_builder.py` 新增 `build_v15`（Builder 收缩：按 candidate_set slot 顺序装配、不排序、不裁剪、不做第二套 JD 相关性判断、fact_refs 保留到 WorkItem/ProjectItem）；`_v15_t5_rewrite.py` 验证 40/40 通过 |
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
   - ~~无 `CandidateExperienceSet` / `SelectedEvidenceSet` 数据结构~~ —— T4 已新建（`selection_service.py`）。
   - 无 Fact 表与 schema version —— T2 新建。
   - ~~无 SQLite BLOB Embedding 派生表~~ —— T3 已新增 `fact_embeddings` 表与 `embedding_service`。
3. **保留项（PLAN §3.3 明确不重构）**：
   - `llm_service` 的 `langchain_openai.ChatOpenAI` 保留，不切换 Provider、不引入多模型。
   - `rag_service._embed` 的 urllib 豆包 multimodal embedding 调用保留。

## 3. 实际全局变化

> T2-T7 完成后填入。按 PLAN §7 / §10 要求记录 API、数据表/模型、模块职责、测试、配置/依赖、版本的实际变化。

| 类别 | 实际变化 |
|---|---|
| API | 无（T2 不动 API） |
| 数据表/模型 | 新增 `facts` 表（`Fact`：fact_id/experience_id/fact_type/text/source_text/source_field/source_index/content_hash/source_hash/revision/timestamps）；新增 `schema_versions` 表（`SchemaVersion`：version/applied_at/description）；`Experience` 增 `facts` 反向关系（无新列） |
| 产品业务链路 | 无（T2 只建事实源与迁移，不改主链路；T3-T5 接入） |
| 模块职责 | 新增 `database/migrations.py`（备份+顺序迁移+幂等 Fact 生成+核对+资源释放）；新增 `services/fact_service.py`（只读 get/list + 显式 modify_fact + 失效钩子注册）；`core/errors.py` 增 3 个领域异常 |
| T3 模块职责 | 新增 `services/embedding_service.py`（compute_fingerprint 基于 EMBEDDING_MODEL+ARK_BASE_URL；_embed_text 调豆包 multimodal API 无 fallback；BLOB float32 编解码；upsert_embedding 幂等；invalidate_fact_embedding 标记 INVALID；wire_fact_invalidation 注册到 fact_service 钩子；rebuild_embeddings 全量重建；ensure_ready 阻断非 VALID；query_facts 内存精确 cosine；status_summary 诊断） |
| 测试 | 新增 `_v15_t2_fact_migration.py`：空库迁移、fixture 迁移、幂等、部分失败重试、modify_fact 失效钩子、资源释放、隐私（产物不含履历正文）—— 35/35 通过 |
| T3 测试 | 新增 `_v15_t3_embedding.py`：fingerprint 稳定、schema 初始化、BLOB round-trip、幂等 upsert、query_facts cosine 排序、维度不匹配排除、fingerprint 变化排除、Fact 修改失效钩子→INVALID、ensure_ready 阻断/放行、rebuild 无 Key 停 PENDING、rebuild 注入 embedder 重建 VALID、无隐藏 fallback、孤儿/空文本 FAILED、status_summary、资源释放 —— 45/45 通过 |
| T4 模块职责 | 新增 `services/selection_service.py`（parse_experience_time 日期解析、score_relevance 确定性 Jaccard+子串评分不依赖旧向量后端、select_experiences 第一层固定槽位、select_evidence 第二层事实选材、CandidateExperienceSet/SelectedEvidenceSet dataclass 可序列化、is_expired 过期核对、verify_evidence_set） |
| T4 测试 | 新增 `_v15_t4_selection.py`：工作0/1/2/3/4次→最近最多3缺位不补、在职=最新、项目三年窗口（边界前/后/正好/进行中/日期缺失）、候选超额最多2、校园补位（合计0/1/2分支、无素材告警不虚构）、序列化、第二层 fact_refs 只引用入选经历+版本匹配、Fact 修改/JD/rule_version/baseline_date 变化→过期、ensure_ready 阻断 PENDING、不写回 Fact —— 53/53 通过 |
| T5 模块职责 | 新增 `prompts/constrained_rewrite.py`（SYSTEM/USER_TEMPLATE：只接收入选经历+可用事实，每条 bullet 返回 fact_refs，材料不足 insufficient）；新增 `services/constrained_rewrite.py`（rewrite_with_evidence：构造 evidence payload、调用 LLM（生产 llm_service.chat_structured / 测试注入 mock llm）、experience_id 边界校验拒绝越界经历、fact_refs 边界校验过滤越界引用、缺失经历补 insufficient、不写回 Fact）；`resume_builder.py` 新增 `build_v15`（Builder 收缩：按 CandidateExperienceSet slot 顺序装配 WorkItem/ProjectItem，fact_refs 保留到模型字段，不做 priority 排序/max_items 裁剪/JD 相关性选择，事实字段仍来自 SQL） |
| T5 测试 | 新增 `_v15_t5_rewrite.py`：合法改写无告警、越界经历拒绝、越界 fact_ref 过滤、不写回 Fact（revision/text 不变）、材料不足 insufficient=true 不补造、缺失经历补 insufficient、Builder 按 slot 顺序装配不排序、不裁剪、fact_refs 来源映射保留、事实字段来自 SQL、Profile 只取 request、build_v15 不改事实源 —— 40/40 通过 |
| 配置/依赖 | 无（T2 不引入新依赖；迁移用现有 SQLAlchemy/stdlib） |
| 版本 | 无（T2 不改 APP_VERSION） |
| T3 数据表/模型 | 新增 `fact_embeddings` 表（`FactEmbedding`：id/fact_id/embedding_fingerprint/dimension/vector_blob(LargeBinary)/vector_dtype/fact_revision/fact_content_hash/status(EmbeddingStatus)/error/updated_at + UniqueConstraint(fact_id,embedding_fingerprint)）；新增 `EmbeddingStatus` 枚举（PENDING/VALID/INVALID/FAILED）；`models.py` 导入增 `LargeBinary`/`UniqueConstraint` |

## 4. 替换型变更闭环

> T6 完成后填入：Chroma/numpy+JSON 退出、SQLite BLOB 新状态生效、无并行向量真源。

| 变更 | 新状态 | 旧状态退出 | 回归证据 |
|---|---|---|---|
| 向量持久化 | 待填 | 待填 | 待填 |

## 5. 开发 Agent 验证

> T7 完成后填入测试矩阵结果（按 PLAN §8：Fact/选择/改写、SQLite 与迁移生命周期、回归）。

## 6. PLAN 偏差汇总

> 开发过程中如有字段名调整或实现细节固化，在此记录并给出等价映射。

- **fact_type 粗粒度映射（T2）**：迁移为确定性、不调 LLM（PLAN §6.1），因此 fact_type 按来源字段粗粒度赋值：`description` → `RESPONSIBILITY`，`achievements[i]` → `RESULT`。PLAN §5.2 明确"粗粒度 bullet 可作为一个较粗 Fact 参与流程，粒度粗不阻断架构验收"，且 fact_type 不是选材 PASS 条件。等价映射：原 description 块保留为较粗 Fact（§6.1.3 不拆细），原成就项保留为结果类 Fact。后续服务层修改不改 fact_type。
