# V1.5.0 RESULT：事实级内容决策、两层选材与 SQLite 持久化收束

> 状态：前置审核打回，待开发返工
> 分支：`version/v1.5.0`
> 基线 commit：`8c4a0058a4b0a96f6235d3cb09382956c25f39a2`（执行时最新公开 `origin/main`，`v1.4.2` 是其祖先）
> 首次实现候选 / 开发交接 HEAD：`81357200fc6e58714d6b7ce3d6ad497a2775935c`（已被前置审核打回）
> 实现链说明：`0fe1513` 是 T6 旧向量退出的前序提交；`8135720` 才是包含 T7 开发验证、RESULT 更新与版本号更新的实际交接 HEAD
> PLAN：`docs/versions/v1.5.0/PLAN.md`（已批准执行，2026-08-23）

> 2026-08-23 前置审核说明：§1–§6 保留首次候选的开发侧实施与 `215 pass / 0 fail` 自测记录，用于追溯“实际发生过什么”；这些记录不代表功能验收、结构变更验收或 WorkBuddy 独立验收通过。接下来必须执行 PLAN §12 的集中返工契约。

## 1. PLAN Task 对照

| Task | 状态 | 实际结果 |
|---|---|---|
| T0 基线与文档冻结 | 完成 | 从 `origin/main@8c4a005...` 建立 `version/v1.5.0`；`v1.4.2` 是其祖先；批准文档形成增量提交 `92ac0ae` + `bc30f18` |
| T1 源码现状与契约映射 | 完成 | 见 §2；实际文件范围、旧路径和 PLAN 偏差已记录 |
| T2 Fact Schema 与迁移框架 | 完成 | 新增 `Fact`/`FactType`/`SchemaVersion` 模型、`database/migrations.py`（备份+顺序迁移+幂等 Fact 生成+核对）、`services/fact_service.py`（显式修改+失效钩子）、`_v15_t2_fact_migration.py` 验证（35/35）；errors 增 `FactNotFoundError`/`FactModificationError`/`MigrationError` |
| T3 SQLite Embedding 与索引任务 | 完成 | 新增 `FactEmbedding`/`EmbeddingStatus` 模型（`fact_embeddings` 表：fact_id+embedding_fingerprint 唯一、BLOB float32 向量、dimension/dtype/revision/hash/status）；新增 `services/embedding_service.py`（fingerprint、BLOB 编解码、upsert、失效钩子 wire、rebuild 全量重建、ensure_ready 阻断、query_facts 内存精确 cosine、status_summary）；`_v15_t3_embedding.py` 验证 45/45 通过 |
| T4 两层选材与 SelectedEvidenceSet | 完成 | 新增 `services/selection_service.py`：第一层 `select_experiences` 固定槽位（工作/实习最近最多3、项目/论文三年窗口内相关性最多2、合计<2 补1校园）、`CandidateExperienceSet`/`ExperienceSlot` 数据结构；第二层 `select_evidence` 只在入选经历中用 `embedding_service.query_facts` 选 fact_refs、`SelectedEvidenceSet`/`EvidenceEntry`/`FactRef` 可序列化可核对、`is_expired`（jd_hash/rule_version/baseline_date/fact revision-hash 变化即过期）；确定性日期解析与相关性评分（不依赖旧向量后端）；`_v15_t4_selection.py` 验证 53/53 通过 |
| T5 改写与 Builder 收缩 | 完成 | 新增 `prompts/constrained_rewrite.py`（受约束改写 prompt）；新增 `services/constrained_rewrite.py`（`rewrite_with_evidence`：LLM 只接收入选经历+表达侧重+可使用事实，每条 bullet 返回 fact_refs，越界经历/越界 fact_refs 拒绝并告警，材料不足返回 insufficient=true 不补造，不写回 Fact）；扩展 `api/schemas.py`（`GeneratedBullet`/`GeneratedExperienceItemV15`/`GeneratedResumeContentV15`）；`models/resume_document.py` WorkItem/ProjectItem 增 `fact_refs` 字段；`resume_builder.py` 新增 `build_v15`（Builder 收缩：按 candidate_set slot 顺序装配、不排序、不裁剪、不做第二套 JD 相关性判断、fact_refs 保留到 WorkItem/ProjectItem）；`_v15_t5_rewrite.py` 验证 40/40 通过 |
| T6 旧向量实现退出 | 完成 | 删除 `chroma_store.py`/`vector_index_sync.py`/`rag_service.py`；`config.py` 移除 `CHROMA_PATH`；`models.py` 移除 `VectorIndexJob`/`vector_id`；`migrations.py` 移除 vectorstore 备份；`experience_service.py` 移除向量同步副作用；`resume_generation_service.py` 重写为 V1.5.0 链路（迁移检查→两层选材→受约束改写→build_v15）；`generate.py` 移除 rag_service 依赖、`/generate` 返回 410；`main.py` 移除 chroma_store import；`schemas.py` 移除 `vector_id`；`requirements.txt` 移除 `chromadb`；旧测试文件加 guard；新增 `_v15_t6_legacy_exit.py` 验证 24/24 通过；Stub E2E 适配 V1.5.0 链路 18/18 通过 |
| T7 开发验证与候选 | 完成开发自测；候选被打回 | 测试矩阵声明 T2(35)+T3(45)+T4(53)+T5(40)+T6(24)+StubE2E(18)=215 pass / 0 fail；APP_VERSION 更新为 1.5.0；开发交接时工作区 clean；实际交接 HEAD 为 `81357200fc6e58714d6b7ce3d6ad497a2775935c`，但前置审核发现结构闭环与最终产物验收不足 |
| T8 高性能源码/数据验收 | 未进入 | 首次候选在前置审核阶段打回；须完成 PLAN §12 R1–R9 并形成新的外部交接 HEAD 后，才由 WorkBuddy 独立验收 |
| T9 人工核心流程验收 | 未执行 | 等待开发返工与 WorkBuddy 独立验收 |
| T10 文档与发布 | 未执行 | CURRENT_STATE、全局文档、`main` 和 tag 均未因 V1.5.0 候选更新或发布 |

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
| 配置/依赖 | T6：`requirements.txt` 移除 `chromadb==1.5.9`（numpy 保留为计算库）；`config.py` 移除 `CHROMA_PATH` 设置（向量持久化统一走 SQLite BLOB 派生表）；`core/version.py` APP_VERSION 更新为 `1.5.0` |
| 版本 | `APP_VERSION = "1.5.0"`（PLAN §8.3） |
| T6 删除模块 | `vectorstore/chroma_store.py`（Chroma+numpy+JSON 双后端）；`services/vector_index_sync.py`（向量索引同步）；`services/rag_service.py`（RAG 检索+embedding）；`models.py` 中 `VectorIndexJob`/`IndexOperation`/`IndexJobStatus`/`Experience.vector_id`；`generate.py` 中 `/generate` 路由 rag_service 调用改为 410 |
| T6 测试适配 | `_v13_stub_e2e.py` 重写为 V1.5.0 链路（mock `embedding_service._embed_text` + `llm_service.chat_structured`）；`_v14_t7_regression.py` 更新模块导入列表与表检查（`facts`/`schema_versions`/`fact_embeddings`）；`_v13_validation.py`/`_e2e_v13_full.py`/`_v14_t3_migrate.py` 加 V1.5.0 guard 退出 |
| T6 核心链路重写 | `resume_generation_service.generate_docx`：迁移检查(`_ensure_migrations_applied`)→JD分析→第一层`select_experiences`→第二层`select_evidence`→受约束改写`rewrite_with_evidence`→`build_v15`收缩装配→渲染→DOCX；`MigrationRequiredError`(412) 替代旧 `VectorIndexNotReadyError` 阻断 |
| T3 数据表/模型 | 新增 `fact_embeddings` 表（`FactEmbedding`：id/fact_id/embedding_fingerprint/dimension/vector_blob(LargeBinary)/vector_dtype/fact_revision/fact_content_hash/status(EmbeddingStatus)/error/updated_at + UniqueConstraint(fact_id,embedding_fingerprint)）；新增 `EmbeddingStatus` 枚举（PENDING/VALID/INVALID/FAILED）；`models.py` 导入增 `LargeBinary`/`UniqueConstraint` |

## 4. 替换型变更闭环

> T6 完成后填入：Chroma/numpy+JSON 退出、SQLite BLOB 新状态生效、无并行向量真源。

| 变更 | 新状态 | 旧状态退出 | 回归证据 |
|---|---|---|---|
| 向量持久化 | SQLite `fact_embeddings` 表（BLOB float32, fact_id+embedding_fingerprint 唯一, EmbeddingStatus: PENDING/VALID/INVALID/FAILED） | `chroma_store.py` 删除（Chroma + numpy+JSON 双后端退出）；`CHROMA_PATH` 配置移除；`chromadb` 依赖移除 | T6 legacy exit 24/24；T3 embedding 45/45；Stub E2E 18/18 |
| 向量检索 | `embedding_service.query_facts` 内存精确 cosine 排序（从 SQLite 读取候选 Fact 向量） | `rag_service.retrieve` TopK 多因素评分删除 | T4 selection 53/53 |
| 内容选材 | 两层选材：`select_experiences`(固定槽位) + `select_evidence`(事实选材) | `rag_service.retrieve` TopK 内容决策删除 | T4 selection 53/53 |
| 生成链路 | `generate_docx`：迁移检查→JD分析→两层选材→受约束改写→build_v15 | 旧链路：索引检查→JD分析→RAG TopK→SQL回读→ContentGenerator→Builder.build | Stub E2E 18/18 |
| 索引同步 | `embedding_service.rebuild_embeddings`（无 API Key 停 PENDING, 生成阻断） | `vector_index_sync.ensure_user_index_ready` + `VectorIndexJob` 删除 | T3 embedding 45/45 |
| 测试契约 | `_v15_t*.py` 系列（T2-T6 共 197 assertions） + `_v13_stub_e2e.py` V1.5.0 适配 | `_v13_validation.py`/`_e2e_v13_full.py`/`_v14_t3_migrate.py` 加 guard 退出；`_v14_t7_regression.py` 更新模块列表 | 全量 215/0 |

## 5. 开发 Agent 验证

> T7 完成后填入测试矩阵结果（按 PLAN §8：Fact/选择/改写、SQLite 与迁移生命周期、回归）。
> 当前证据等级：以下均为首次候选 `81357200fc6e58714d6b7ce3d6ad497a2775935c` 的开发侧自测声明；因前置审核打回，不得解读为候选可验收或独立验收结论。

### 5.1 Fact、选择与改写（§8.1）

| 验证项 | 结果 | 证据 |
|---|---|---|
| 新旧 Experience 形成 Fact | 通过 | T2: 4 experiences → 5 facts, 幂等 upsert, 确定性 fact_id(uuid5) |
| Fact 修改后 revision/hash 更新+旧向量失效 | 通过 | T2: revision 自增, content_hash 变化, 失效钩子触发; T3: INVALID 向量被 query 排除 |
| LLM/生成链路不写回 Fact | 通过 | T5: rewrite_with_evidence 不改 Fact revision/text; build_v15 不改事实源 |
| 工作0/1/2/3/4次→最近最多3缺位不补 | 通过 | T4: 所有分支 |
| 项目三年窗口+最多2 | 通过 | T4: 边界前/后/正好/进行中/日期缺失/候选超额 |
| 校园补位 | 通过 | T4: 合计0/1/2分支, 无素材告警不虚构 |
| 第二层只接收入选经历+fact_refs 版本匹配 | 通过 | T4: fact_ref 属于入选经历, revision/hash 匹配 |
| 越界经历/越界 fact_refs 拒绝 | 通过 | T5: 越界被拒绝并告警 |
| 材料不足 insufficient=true 不补造 | 通过 | T5: bullets 为空, insufficient_reason 有值 |
| 换 JD 不改 Fact/Experience | 通过 | T4: 换 JD 不改事实源 |

### 5.2 SQLite 与迁移生命周期（§8.2）

| 验证项 | 结果 | 证据 |
|---|---|---|
| 全新空库初始化 | 通过 | T2: 空库迁移无错误 |
| V1.4.2 数据库副本迁移 | 通过 | T2: fixture 4 experiences → 5 facts |
| 重复迁移（版本门控跳过） | 通过 | T2: 第二次 created=0, noop=5 |
| Schema 部分创建后安全重试 | 通过 | T2: 删除 version + 1 fact, 重试 created=1, facts=5 |
| 无 API Key 停 PENDING+生成阻断 | 通过 | T3: skipped_no_key=True, PENDING 行>0; ensure_ready 阻断 |
| Fact revision/hash 变化→向量 INVALID | 通过 | T3: 修改后 INVALID 行≥1, query 排除 |
| fingerprint 变化→旧向量不可用 | 通过 | T3: 只匹配当前 fingerprint |
| 维度不匹配排除 | 通过 | T3: 查询向量维度不匹配→排除 |
| 备份/核对/孤儿检查/资源释放 | 通过 | T2: SQLite 备份生成, orphan_facts=0, engine.dispose; T3: 孤儿 FAILED |
| 旧索引备份不被活动代码读取 | 通过 | T6: chroma_store/vector_index_sync/rag_service 删除, 0 活动路径 |
| 活动 Chroma/numpy+JSON 路径为 0 | 通过 | T6: 24/24 legacy exit 验证 |

### 5.3 回归（§8.3）

| 验证项 | 结果 | 证据 |
|---|---|---|
| Profile 只取 request | 通过 | Stub E2E: Profile边界 A1-A4, B1-B2 |
| 求职意向只来自 JD | 通过 | Stub E2E: target_position 来自 JD |
| 不生成个人总结 | 通过 | Stub E2E: summary 恒空 |
| 当前豆包 LLM/Embedding 继续服务 | 通过 | Stub E2E: mock LLM/embedding 通过 V1.5.0 链路 |
| 旧 Markdown 接口不成为新主链 | 通过 | T6: /generate 返回 410 Gone |
| 核心 JD→DOCX 正常路径 | 通过 | Stub E2E: 10/10 happy path |
| 主要错误分支通过 | 通过 | Stub E2E: JD_INVALID(422), LLM_OUTPUT_INVALID(502) |
| Stub 测试独立临时 runtime | 通过 | Stub E2E: 隔离+cleanup 成功 |
| APP_VERSION 统一为 1.5.0 | 通过 | core/version.py APP_VERSION="1.5.0" |

### 5.4 测试矩阵汇总

| 测试 | 断言数 | 通过 | 失败 |
|---|---|---|---|
| `_v15_t2_fact_migration.py` | 35 | 35 | 0 |
| `_v15_t3_embedding.py` | 45 | 45 | 0 |
| `_v15_t4_selection.py` | 53 | 53 | 0 |
| `_v15_t5_rewrite.py` | 40 | 40 | 0 |
| `_v15_t6_legacy_exit.py` | 24 | 24 | 0 |
| `_v13_stub_e2e.py`（V1.5.0 适配） | 18 | 18 | 0 |
| **合计** | **215** | **215** | **0** |

## 6. PLAN 偏差汇总

> 开发过程中如有字段名调整或实现细节固化，在此记录并给出等价映射。

- **fact_type 粗粒度映射（T2）**：迁移为确定性、不调 LLM（PLAN §6.1），因此 fact_type 按来源字段粗粒度赋值：`description` → `RESPONSIBILITY`，`achievements[i]` → `RESULT`。PLAN §5.2 明确"粗粒度 bullet 可作为一个较粗 Fact 参与流程，粒度粗不阻断架构验收"，且 fact_type 不是选材 PASS 条件。等价映射：原 description 块保留为较粗 Fact（§6.1.3 不拆细），原成就项保留为结果类 Fact。后续服务层修改不改 fact_type。

## 7. 2026-08-23 文档 Agent 前置审核打回记录

### 7.1 审核对象与结论

| 项目 | 当前实际状态 |
|---|---|
| 分支 | `version/v1.5.0` |
| 基线 | `8c4a0058a4b0a96f6235d3cb09382956c25f39a2` |
| 首次开发交接 HEAD | `81357200fc6e58714d6b7ce3d6ad497a2775935c` |
| 前序实现提交 | `0fe1513`；仅代表 T6，不是最终交接 HEAD |
| 开发自测声明 | 215 pass / 0 fail；未等同为独立验收 |
| 功能验收 | 失败；正常迁移/重建入口、CRUD 后事实闭环及最终 DOCX 证据不足 |
| 结构变更验收 | 失败；迁移 fail-closed、失效一致性、检索故障可见、逐 bullet 来源与旧实现退出未闭环 |
| WorkBuddy 独立验收 | 未进入；须先完成开发返工并形成新的 clean 候选 |
| 当前状态 | **前置审核打回，待开发返工** |

### 7.2 打回证据摘要

1. Experience create/update/delete 只改变 Experience；新建 Fact/Embedding、更新后 reconciliation、删除派生数据清理及失败重试没有形成统一生命周期。
2. 生成只检查 SchemaVersion，API、README 和正常运行入口没有迁移、状态、重试和 Embedding 重建闭环；全新库、V1.4.2 升级库与 CRUD 后库不能按现有说明完成生成。
3. 迁移忽略旧索引备份参数，备份失败后仍可能继续，session/engine 释放异常被吞掉；不满足 PLAN 与 D-024 的 fail-closed 生命周期要求。
4. Fact 修改先提交再运行 warning-only 失效钩子，存在新 Fact 已提交但旧 Embedding 仍 VALID 的一致性窗口。
5. 正式教育与校园活动被混为一池；校园按最近而非 JD 最匹配；Builder 旁路装配 education 且校园改写 bullets/fact_refs 未进入最终文档。
6. 工作/项目同分同日期缺少最终稳定键；缺日期工作实际入选却被告警描述为排除，输入乱序结果未被证明稳定。
7. 检索健康检查没有覆盖查询维度等完整契约；维度/模型故障造成的零命中会被全部 Fact 回退掩盖。
8. bullet 级 fact_refs 在 Builder 被压成经历级集合，未声明的 BuildMeta 字段在响应校验后丢失，校园分支也无映射；越界引用没有作为生成失败处理。
9. 根 README、`.env.example`、Stub/旧验证入口仍有 Chroma、CHROMA_PATH、RAG 或旧 Builder 语义；首次 legacy-exit 自测未覆盖完整对外入口与分类证据。
10. RESULT 原把 `0fe1513` 写成最终候选，和实际开发交接 HEAD `81357200fc6e58714d6b7ce3d6ad497a2775935c` 不一致，现已纠正。
11. 现有自测主要证明中间 CandidateSet/EvidenceSet 或局部 Builder 行为，没有覆盖最终 ResumeDocument、Pydantic 响应序列化与 DOCX 的逐 bullet 来源闭环，因此 215/0 不能推出候选可验收。

### 7.3 当前等待项与下一次交接

- Traework 按 [PLAN §12](./PLAN.md#12-文档-agent-前置审核返工补充2026-08-23) 一轮完成 R1–R9，并在本 RESULT 追加实际修复、偏差与新测试结果；不得删除本次失败记录，也不得提前更新 CURRENT_STATE。
- 新候选必须 clean。为避免提交自回填自身 SHA，RESULT 不写入该提交自身标识；Traework 通过仓库外的交接消息提供完整 40 位 HEAD、分支、基线、clean 状态与测试汇总。
- WorkBuddy 只验收新的外部交接 HEAD，在 clean review worktree 独立检查源码、失败路径、最终 ResumeDocument/响应/DOCX 和旧实现退出；结论必须绑定该精确 commit。
- 当前未进行人工验收、全局文档收口、`main` 快进或 `v1.5.0` tag；未经 WorkBuddy 与人工验收的 V1.5.0 能力不得写入 CURRENT_STATE。
