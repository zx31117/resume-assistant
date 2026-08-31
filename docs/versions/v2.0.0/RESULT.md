# V2.0.0 RESULT：本地全流程图形交互首版

> 文档角色：V2.0.0 实际实现与验收结论唯一真源
> 顶部状态：**T9 独立源码验收已通过（第五轮，2026-08-28），待 T10 人工产品验收**
> 当前进度：第五轮 S4-1 / S4-2 两个 fail-closed 阻断项由共享测试 runner + 双脚本负向矩阵关闭（§10.11）；验收 Agent 已在新 detached clean 工作树按 PLAN §11（F5）独立复验通过（§10.12），T9 完成、阻断项 0；T10 人工产品验收、T11 文档收口待开展
> 交付对象基线：公开 `main@4b7ac340d580d47cb163cfe4cf4b04e9759eb8bd`（祖先含 annotated tag `v1.5.0` → `8d3aac6369146052f819c414cc18f53b11a778fc`）
> 开发分支：`version/v2.0.0`
> 第三轮候选：`e9f5d52c799dba5b724c75d6c3e26f59cbb007b5`（源码返工）→ `4114d48bf8679bb8d4c77005db6f310e896a5f55`（追加便携包证据与文档记录的被验收对象）
> 第四轮候选：`080eba44ca770b92fb723adc1d84060e1bb80f88`（S3-1/S3-2 验证脚本返工）→ `8c5bd0f2ebaf751f99fbc28e6ab171edaca0028f`（分支 HEAD，追加文档记录的被验收对象）
> 第五轮候选（源码返工）：`7795ec608c4eb6f0c661bb9dd95d0e05e5abd9b7`（S4-1/S4-2 验证脚本生命周期返工）→ `d7a8c1bfc83f8244ce123e8c9d30c48418143e9e`（分支 HEAD，追加文档记录的被验收对象）
> 当前文档状态：§10.5–§10.8 保留第三、第四轮交接记录；§10.9 / §10.10 为第四轮验收与补充复核记录；§10.11 为第五轮开发侧返工记录；§10.12 为验收 Agent 第五轮独立复验结论；候选源码未被验收 Agent 修改

## 1. 实现标识

| 项目 | 值 |
|---|---|
| 版本 | V2.0.0 |
| 公开基线 commit | `4b7ac340d580d47cb163cfe4cf4b04e9759eb8bd`（`main`） |
| 祖先发布 tag | `v1.5.0` → `8d3aac6369146052f819c414cc18f53b11a778fc` |
| 开发分支 | `version/v2.0.0` |
| 基线 HEAD | `086af41`（PLAN 批准提交） |
| 既有开发提交 | `844707a84edcd6f346edeb809be40fcb8eba0900`（T2–T8 首次实现）→ `a2c6775f1100f1e0bc7be487c4615b08df4aeb54`（开发侧自查修复，见 §8.2） |
| 第二轮候选 commit | `50909111f3b33d311627adf61ec49be828cce5c5`（仓库外交接并现场核验） |
| 第三轮候选 commit | `e9f5d52c799dba5b724c75d6c3e26f59cbb007b5`（S2-1/S2-2 返工）→ 被验收对象 `4114d48bf8679bb8d4c77005db6f310e896a5f55`（便携包证据与文档记录） |
| 第四轮候选 commit | `080eba44ca770b92fb723adc1d84060e1bb80f88`（S3-1/S3-2 验证脚本返工）→ 被验收对象 `8c5bd0f2ebaf751f99fbc28e6ab171edaca0028f`（分支 HEAD，便携包证据与文档记录） |
| 第五轮候选 commit | `7795ec608c4eb6f0c661bb9dd95d0e05e5abd9b7`（S4-1/S4-2 验证脚本生命周期返工）→ 被验收对象 `d7a8c1bfc83f8244ce123e8c9d30c48418143e9e`（分支 HEAD，追加文档记录） |
| 候选 clean 状态 | 是；开发工作树与 detached review 工作树均无未提交文件 |
| 第二轮变更 | 相对 `cd3201b` 共 11 个文件：5 个产品源码、`backend/_v20_smoke.py` 与 5 个文档文件 |
| 第三轮变更 | 相对 `5090911`：`backend/_v20_smoke.py`（S2-1 自隔离）与 `docs/versions/v2.0.0/RESULT.md`（S2-2 证据记录）；业务源码未变 |
| 第四轮变更 | 相对 `8a2a629`：`backend/_v20_smoke.py` 与 `backend/_v2_t5_crud_check.py`（S3-1/S3-2 完整资源生命周期）＋ `docs/versions/v2.0.0/RESULT.md`（§10.8）；业务源码、前端产物、便携包输入均未变 |
| 第五轮变更 | 相对 `8c5bd0f`：重构 `backend/_v20_smoke.py` / `_v2_t5_crud_check.py` 并新增 `_v2_test_runner.py`（共享 runner）、`_v2_lifecycle_matrix.py`（双脚本生命周期矩阵），＋ `docs/versions/v2.0.0/PLAN.md`（§11 契约）与 `RESULT.md`（§10.10/§10.11）；业务源码、前端产物、便携包输入均未变 |

## 2. T1 源码与契约映射完成情况

PLAN §6 T1 完成条件：明确直接复用、薄 API、替换/退出项和风险偏差；不先改业务。逐条对照：

- [x] 对照现有 API、服务、配置、生命周期、静态资源和测试建立实现地图（见 §3）
- [x] 明确直接复用、薄 API、替换/退出项（§3.1–§3.4）
- [x] 明确风险偏差及可能触发的 PLAN 调整（§3.5）
- [x] 不先改业务：本轮未改动任何源码、测试、配置或依赖，仅新增本文档
- [x] 建立 RESULT 骨架（本文档）

## 2.5 T2 前端骨架与同源托管完成情况

PLAN §6 T2 完成条件：开发与生产入口明确；三页可导航；无第二业务真源；Chrome/Edge 基础 E2E 可运行。逐条对照：

- [x] **React + TypeScript + Vite 工程**：新建 `frontend/`，含 `package.json` / `tsconfig.json` / `tsconfig.node.json` / `vite.config.ts` / `index.html` / `.gitignore`。
- [x] **三个顶层路由**：`/`（生成工作台）、`/profile`（履历库）、`/system`（本地系统），react-router 的 `<Routes>` + `AppShell` 顶栏导航；未知路径 `*` 重定向 `/`。
- [x] **设计系统**：`styles/tokens.css`（编辑式文具视觉令牌）+ `styles/global.css` + `ui/Button、Card、Badge、Field`、`PageHeader`、`layout/AppShell` 基础组件。克制配色、无装饰堆叠。
- [x] **强类型 API Client**：`api/types.ts`（对齐 `backend/api/schemas.py` 契约）、`api/client.ts`（统一 fetch 封装，非 2xx 解析 `DomainError` 抛 `ApiError`）、`api/endpoints.ts`（resume/experience/jd/template/config/system 端点封装）。
- [x] **统一错误**：`ApiError` 携带 `status/error_code/stage/retryable/details`；用户/模型输出仅按文本渲染，无 `innerHTML` 注入。
- [x] **同源托管**：`backend/main.py` 生产构建产物存在时挂载 `frontend/dist` 静态资源 + SPA fallback；新增 `GET /api/health`；未构建时回退纯 JSON 根路由。
- [x] **开发与生产入口明确**：开发 `npm run dev`（Vite:5173，`/api` 代理 → `127.0.0.1:8000`）；生产 `npm run build` → FastAPI 同源托管。
- [x] **无第二业务真源**：前端仅声明类型与薄 client，不实现选材/改写/Builder/Renderer/Fact 推导。

## 2.6 T3 首次设置、配置与本地安全完成情况

PLAN §6 T3 完成条件：无 Key 泄漏或明文降级；错误候选不覆盖可用配置；非 loopback/跨来源写入被拒绝。逐条对照：

- [x] **单一 resolver**：`core/config_resolver.py` 统一解析，优先级固化——API Key：Credential Manager > env/.env；非密钥三项（Base URL / LLM model / Embedding model）：runtime 版本化配置（`RESUME_DATA_DIR/config/connection.json`）> env > 内置默认。`snapshot()` 只回脱敏元数据；`activate` 校验→持久化→更新内存快照。
- [x] **Credential Manager**：`core/credential_manager.py` 用 ctypes 直接调用 `advapi32` 的 `CredReadW/CredWriteW/CredDeleteW`（`CRED_TYPE_GENERIC`，无第三方依赖）；失败显式抛 `CredentialError`，绝不退回明文 SQLite/JSON/日志/浏览器缓存；非 Windows 平台显式报告不可用（阻止激活写入，不破坏源码读取入口）。
- [x] **安全中间件**：`core/security.py` + `main.py security_middleware`。写操作（POST/PUT/PATCH/DELETE）校验 Host（仅 loopback）、Origin（loopback 或缺失）、启动会话 Cookie（`secrets.token_urlsafe`，HttpOnly + SameSite=Strict）；令牌不通过 URL 传输。生产无 CORS 头。
- [x] **连接测试**：`services/connection_test.py` 用候选配置发起最小 LLM / Embedding 调用，逐项返回结果且错误信息脱敏截断；`POST /api/config/test` 不落任何持久化配置。
- [x] **激活闭环**：`POST /api/config/activate` 校验字段 → 写凭据（最易失败项先写）→ 写 runtime 配置（失败则回滚凭据）→ 更新 settings 内存快照；凭据失败 → `CredentialStorageError`(500)。
- [x] **llm_service 惰性化**：`services/llm_service.py` 移除 import 期模块级单例，改每次调用按当前 settings 快照惰性构建 client，配置激活对后续请求生效，错误候选不覆盖可用配置。
- [x] **embedding 显式配置**：`services/embedding_service.py` 新增 `embed_text_with_config(text, api_key, base_url, model)`，连接测试与生产共用同一无 fallback 计算路径。

验证证据：`_v20_smoke.py` §[2] 配置快照脱敏（masked/source 存在、无 value 明文）20/20；§[5] 无会话令牌写请求 403 + `error_code=FORBIDDEN`；`_v2_t5_crud_check.py` §[1] 错误 Host 被拒 403。

## 2.7 T4 系统维护图形闭环完成情况

PLAN §6 T4 完成条件：全新库、V1.5.0 升级库、索引异常均可图形处理；行为与 CLI 一致且 fail closed。逐条对照：

- [x] **薄 API**：`api/routes/system.py` 提供 `GET /api/system/status`（版本/迁移/Experience/Fact/Embedding 汇总/下一步）、`POST /api/system/migrate`（`run_migrations(backup=True)`）、`POST /api/system/rebuild`（`rebuild_embeddings`）、`POST /api/system/retry`（复用 rebuild）。全部包装与 `manage.py` 完全相同的 service/迁移函数。
- [x] **并发门禁**：`core/concurrency.py` `exclusive_operation` 非阻塞全局锁；迁移/重建/重试/生成共享，占用时抛 `ConcurrencyConflictError`(409/`OPERATION_IN_PROGRESS`)，拒绝并发而非排队。`generate.py` 生成入口同样接入。
- [x] **前端闭环**：`frontend/src/pages/SystemPage.tsx` 提供连接配置表单（测试/激活）、系统状态展示、迁移/重建/重试操作及二次确认、受限模式 Badge。
- [x] **受限设置模式**：`main.py` lifespan 仅 `init_db()`（建表不硬失败迁移），DB 未迁移/索引未就绪时 status 返回 `ready=false` 与 `next_steps`，生成由既有 `MigrationRequiredError`/索引检查阻断，页面仍可进入 `/system` 维护。

验证证据：`_v20_smoke.py` §[3] status 六字段齐备 20/20；`_v15_w_rework.py` W3 全新库 migrate/幂等/fail-closed 37/37。

## 2.8 T5 履历导入与 Experience UI 完成情况

PLAN §6 T5 完成条件：不用 Swagger 完成导入与 CRUD；增删改仍走原事务/失效链路；部分失败可核对。逐条对照：

- [x] **Experience 汇总状态**：`services/experience_service.py` 新增 `_annotate_summary`（批量聚合，避免 N+1），为每个 Experience 计算 `fact_count` 与 `summary_status ∈ empty|pending|ready|failed`；`api/schemas.py` `ExperienceOut` 增加 `fact_count`/`summary_status` 字段（前端只读展示，不推导 Fact 明细）。
- [x] **CRUD 复用原事务/失效链路**：create/update/delete 仍走 `experience_service` 原事务与 reconciliation/Embedding 失效/清理逻辑，仅追加汇总注解，不复制业务。
- [x] **前端履历库**：`frontend/src/pages/ProfilePage.tsx` 覆盖 Experience 列表/新增/编辑/删除/PDF 上传→文本解析→经历提取→逐项检查，及汇总状态展示；删除前二次确认。

验证证据：`_v2_t5_crud_check.py` 15/15（create→list→update→delete→空列表；fact_count 聚合、summary_status=pending、skills 数组回读）；`_v15_r_rework.py` R1 CRUD 全生命周期 48/48（含 Fact reconciliation、同事务失效、无孤儿、幂等 delete）；`_v15_w_rework.py` W1 create/update 同事务正反向 37/37。

## 2.9 T6 生成工作台完成情况

PLAN §6 T6 完成条件：不用 Swagger 完成 JD → DOCX；失败可见；无重复调用、路径越界或身份来源回归。逐条对照：

- [x] **前端工作台**：`frontend/src/pages/GeneratePage.tsx` 实现身份/JD 输入、JD 分析（七字段）、模板选择（`GET /api/template/list`）、生成提交（唯一 `POST /api/resume/generate-docx`）、提交/生成/成功/失败状态、warnings/build_meta 摘要与安全下载，并防止重复提交。
- [x] **核心链路唯一入口**：前端只调用 V1.5.0 核心 `generate-docx`，不调用已退出 Markdown 主链；身份只来自本次请求，求职意向只来自 JD（无个人总结回归）。
- [x] **下载安全**：下载复用 `GET /api/template/download` 既有 basename 归一化 + `../` 穿越拒绝，只允许 `DOCX_OUTPUT_DIR` 一级文件。

验证证据：`_v13_stub_e2e.py` 18/18（JD→DOCX happy path、JD_INVALID/LLM_OUTPUT_INVALID 错误分支、身份边界 A1–A4/B1–B2、渲染不裁剪、build_meta 诊断）；`_v15_t5_rewrite.py` 40/40（受约束改写、build_v15 收缩、Profile 只取 request）。

## 2.10 T7 便携启动器与发行包完成情况

PLAN §6 T7 完成条件：干净 Windows 环境无 Python/Node 可运行；退出释放资源；包内无凭据/PII/runtime。逐条对照：

- [x] **图形启动器**：`packaging/launcher.py` 以 loopback 起 uvicorn（复用 `main.app`）→ 等 `GET /api/health` 就绪 → 打开默认浏览器 → tkinter 图形窗口（重新打开界面 / 退出）。单实例用 Windows 命名互斥量（重复启动只重开浏览器）；端口被占向后扫描安全可用端口；退出释放 server/DB 引擎/互斥量/日志流/锁文件，幂等。
- [x] **windowed 模式 stdio 重定向**：`console=False` 下 `sys.stdout/stderr` 为 `None` 时重定向到 runtime 日志文件，避免 uvicorn/logging 写 None 句柄崩溃。
- [x] **onedir 打包**：`packaging/resume_assistant.spec` 目录型便携包；`datas` 打 frontend/dist、templates、config；`collect_all`/`collect_submodules` 显式收集 langchain/openai/tiktoken/certifi/uvicorn/自身模块；`console=False`。
- [x] **冻结路径适配**：`core/config.py` BASE_DIR、`main.py` FRONTEND_DIST 在 `sys.frozen` 时指向 `_MEIPASS`，保证模板/config/prompts/frontend 打包后可定位。
- [x] **构建脚本**：`packaging/build.ps1` 三阶段（前端构建 → 确保 pyinstaller → onedir 打包 + 产物校验）。

验证证据：`dist/ResumeAssistant/ResumeAssistant.exe`（约 15.8 MB）已产出；`_internal/frontend/dist/index.html`、`_internal/templates/pm_template.docx`、`_internal/templates/pm_template.json`、`_internal/config/template_mapping.json` 均就位；包内容扫描无 `.env`/`.db`/`.sqlite`/真实 DOCX/API Key。干净 Windows x64 无 Python/Node 双击启动的最终验证与包 hash 由 T9/T10 在独立/干净环境复核（§7.4 属开发侧部分证据，结论不在此自行扩大为最终验收）。

## 3. 实现地图

### 3.1 直接复用（无改动）

业务核心链路与事实所有权全部保持 V1.5.0 实现，前端不得重建：

| 维度 | 复用对象 |
|---|---|
| 生成链路 | `resume_generation_service.generate_docx`（迁移检查 → JD 分析 → 两层选材 → 受约束改写 → Builder → Renderer → 保存 DOCX） |
| 选材/改写/装配/渲染 | `selection_service`、`constrained_rewrite`、`resume_builder`、`template_renderer`、`layout_optimizer` |
| 经历与事实 | `experience_extractor`、`experience_service`、`fact_service` |
| 数据模型 | `User`、`Experience`、`Fact`、`SchemaVersion`、`FactEmbedding`（不变） |
| 向量 | `embedding_service`（fingerprint/status_summary/rebuild_embeddings/ensure_ready/query_facts） |
| 迁移 | `database.migrations.run_migrations` + `verify_migration` + 备份核对 |
| 现有 API | `POST /api/resume/upload`、`POST /api/experience/extract`、`POST/GET/PUT/DELETE /api/experience`、`POST /api/jd/analyze`、`POST /api/resume/generate-docx`、`GET /api/template/list`、`GET /api/template/download` |

### 3.2 薄 API（新增，包装现有 service，不复制业务逻辑）

| 新 API | 包装的现有能力 |
|---|---|
| `GET /api/config` | `config_resolver.snapshot()`（脱敏，永不返回完整 Key） |
| `POST /api/config/test` | `connection_test.test_connection`（候选 LLM+Embedding，不落库） |
| `POST /api/config/activate` | `config_resolver.apply_active_config`（校验+持久化+内存快照） |
| `GET /api/system/status` | `embedding_service.status_summary` + SchemaVersion/Fact 统计 |
| `POST /api/system/migrate` | `run_migrations(backup=True)`（同 `manage.py migrate`） |
| `POST /api/system/rebuild` | `embedding_service.rebuild_embeddings`（同 `manage.py rebuild`） |
| `POST /api/system/retry` | 复用 `rebuild_embeddings`（同 `manage.py retry`） |
| `GET /api/health` | 同源健康检查（版本元数据 `2.0.0`） |

### 3.3 替换 / 退出

| 现状 | 目标 | 状态 |
|---|---|---|
| `llm_service._llm` import 期模块级单例 | 惰性按配置快照创建（fingerprint 感知） | ✅ T3 完成 |
| 配置仅 `.env`/环境变量 | 单一 resolver 统一 env/runtime/Credential Manager 并显示来源 | ✅ T3 完成 |
| 便携包长期 Key 走明文 `.env` | Windows Credential Manager；`.env` 仅开发/自动化入口 | ✅ T3 完成 |
| `core/version.APP_VERSION = "1.5.0"` | `2.0.0` | ✅ T8 完成 |

### 3.4 全新新增（不影响既有业务）

| 模块 | 说明 |
|---|---|
| 前端 React + TS + Vite | 三顶层路由 `/`、`/profile`、`/system`；设计系统；强类型 API Client |
| FastAPI 静态托管 | 生产静态资源同源 + SPA fallback；开发 Vite 代理 |
| 安全中间件 | Host/Origin 校验 + 启动会话/CSRF 令牌（仅写操作）；loopback 绑定 |
| 配置 resolver + Credential Manager | §3.3；Windows 用 ctypes 调凭据库 |
| 连接测试 | `connection_test`（候选 LLM/Embedding，脱敏） |
| 并发门禁 | `concurrency.exclusive_operation`（迁移/重建/重试/生成非阻塞拒绝） |
| 便携启动器 | `packaging/launcher.py` 图形启动/重开/退出/单实例/端口/runtime 隔离 |
| 受限设置/维护模式 | DB 未就绪时 status `ready=false` + next_steps，生成阻断，`/system` 可进入 |

### 3.5 风险与偏差（T1 标记，T2–T8 逐项收盘）

1. **LLM 单例缓存重构**：✅ 已闭环（§2.6 llm_service 惰性化）。
2. **测试基线非 pytest**：✅ 固化复跑命令（§6）；回归脚本各自 `python <file>.py` 独立运行，退出码 0=通过。
3. **模板构建依赖 subprocess**：见下（偏差 3）。
4. **PyInstaller 打包可行性**：✅ 已验证，onedir 产物 `dist/ResumeAssistant/ResumeAssistant.exe` 产出，未切换 onefile。
5. **Credential Manager 实现选型**：✅ 冻结为 ctypes + advapi32（无第三方依赖）。
6. **开发模式跨域**：✅ 开发用 Vite 代理，生产同源，不启用 CORS。

### 3.6 偏差记录（T1 标记为「可能触发 PLAN 调整」的项，收盘结论）

1. **版本元数据升级**：✅ 已随 T8 升级 `APP_VERSION=2.0.0`（`/api/health` 返回 2.0.0，`_v20_smoke.py` 校验通过）。
2. **真实浏览器 E2E**：开发侧已用 TestClient 验证同源托管/SPA fallback 与 CRUD/配置/系统闭环；Chrome/Edge 三页主流程属 §7.4，留待 T9/T10 在便携包与干净环境复核，开发侧不以 TestClient 结果扩大解释为浏览器验收。
3. **`template.py::_ensure_template_docx` 依赖 subprocess `_build_templates.py`**：T7 未在便携包内动态调用子进程解释器——`pm_template.docx` 作为已固化产物随 `datas` 打进 `_MEIPASS/templates`，模板渲染走既有已固化 `.docx`，不触发打包内 subprocess 构建。该判断未发现阻断，无需请求 PLAN 调整。

## 4. PLAN Task 对照

| Task | 内容 | 状态 |
|---|---|---|
| T0 文档与基线冻结 | 文档 Agent | 已完成 |
| T1 源码与契约映射 | 开发 Agent | 已完成（§2） |
| T2 前端骨架与同源托管 | 开发 Agent | 已完成（§2.5） |
| T3 首次设置、配置与本地安全 | 开发 Agent | 已完成（§2.6） |
| T4 系统维护图形闭环 | 开发 Agent | 已完成（§2.7） |
| T5 履历导入与 Experience UI | 开发 Agent | 已完成（§2.8） |
| T6 生成工作台 | 开发 Agent | 已完成（§2.9） |
| T7 便携启动器与发行包 | 开发 Agent | 已完成（§2.10） |
| T8 开发验证与候选 | 开发 Agent | 第五轮 clean candidate 已冻结：`7795ec6…`（§10.11） |
| T9 独立源码验收 | 验收 Agent | 第五轮已通过，阻断项 0，绑定 `d7a8c1b…`（§10.12） |
| T10 人工产品验收 | 用户 | 已有阶段性反馈；正式验收待开展（§11） |
| T11 文档收口与发布 | 文档 Agent | 待开展 |

## 5. 实际全局变化

| 类别 | 变化 |
|---|---|
| API | 新增 `GET /api/health`；`GET /api/config`、`POST /api/config/test`、`POST /api/config/activate`；`GET /api/system/status`、`POST /api/system/migrate`、`/rebuild`、`/retry`。既有业务接口无变化（`/api/resume/generate-docx` 仅加并发门禁） |
| 数据表/模型 | 无新表；`ExperienceOut` 仅增 `fact_count`/`summary_status` 响应字段（非持久化列） |
| 模块职责 | `main.py` 增安全中间件 + 同源托管；新增 `core/{config_resolver,credential_manager,security,concurrency}`、`api/routes/{config,system}`、`services/connection_test`；`llm_service` 惰性化；`embedding_service` 增显式配置函数；`experience_service` 增汇总注解 |
| 配置来源/优先级 | 单一 resolver：Key 走 Credential Manager > env；非密钥走 runtime 版本化配置 > env > 默认；版本化配置位于 `RESUME_DATA_DIR/config/connection.json` |
| 依赖 | 后端 Python 依赖无新增（Credential Manager 走 ctypes）；新增前端 npm 依赖（react/react-dom/react-router-dom/vite/typescript） |
| 前端构建 | 新增 `frontend/`；生产构建产物 `frontend/dist`（`npm run build` 通过，46 模块，JS 约 192 KB） |
| 便携打包 | 新增 `packaging/{launcher.py,resume_assistant.spec,build.ps1}`；onedir 产物 `dist/ResumeAssistant/ResumeAssistant.exe`（约 15.8 MB） |
| 版本元数据 | `core/version.APP_VERSION = "2.0.0"` |

## 6. 验证矩阵

### 6.1 命令与环境

- 环境：Windows x64；Python 3.10（`C:\...\Python310`）；Node 24.11.1 / npm 11.6.2；浏览器验收待 T9/T10。
- 前端构建：`cd frontend && npm run build`（`tsc -b && vite build`）→ 通过。
- V2.0.0 冒烟：`cd backend && python _v20_smoke.py` → **20 PASS / 0 FAIL**（同源 health、配置脱敏、系统 status、模板列表、写安全 403、同源托管回退）。
- V2.0.0 CRUD：`cd backend && python _v2_t5_crud_check.py` → **15 PASS / 0 FAIL**（写安全 403、create/list/update/delete、汇总状态，隔离 runtime）。
- V1.5.0 回归：各脚本 `cd backend && python <file>.py` → 汇总见 §6.2。

### 6.2 V1.5.0 回归结果（§7.5）

| 测试脚本 | 覆盖 | PASS | FAIL |
|---|---|---|---|
| `_v15_t2_fact_migration.py` | Fact 迁移/upsert/幂等/revision | 35 | 0 |
| `_v15_t3_embedding.py` | Embedding/fingerprint/维度/失效/无 Key PENDING | 54 | 0 |
| `_v15_t4_selection.py` | 两层选材/槽位/稳定排序/工作窗口 | 53 | 0 |
| `_v15_t5_rewrite.py` | 受约束改写/build_v15/Profile 只取 request | 40 | 0 |
| `_v15_t6_legacy_exit.py` | 旧向量实现退出/无导入/无 vector_id | 24 | 0 |
| `_v13_stub_e2e.py` | JD→DOCX happy path + 错误分支 + 身份边界 | 18 | 0 |
| `_v15_r_rework.py` | R1 CRUD 生命周期 / R3 备份 fail-closed / R7 逐 bullet 来源 | 48 | 0 |
| `_v15_w_rework.py` | W1 同事务 / W2 缺日期工作 / W3 全新库维护入口 | 37 | 0 |
| **合计** | | **309** | **0** |

- 附 `_v14_t7_regression.py`：**12 PASS / 0 FAIL / 3 SUSPEND**（3 项 SUSPEND 依赖干净首发包或本机 ARK_API_KEY，属环境门禁，非失败）。
- 旧 V1.3/V1.4 脚本（`_v13_validation.py`/`_e2e_v13_full.py`/`_v14_t3_migrate.py`）在 V1.5.0 已加 guard 不适用于 V2.0.0；三者仍存在「guard 代码插入在 `from __future__ import annotations` 之前导致 SyntaxError」的 V1.5.0 既有问题（本版未改动这三者，非 V2.0.0 回归），记录为遗留，不纳入回归计数。

### 6.3 便携包与包内容（§7.4 开发侧部分证据）

- onedir 产物：`dist/ResumeAssistant/ResumeAssistant.exe`（约 15.8 MB）。
- 关键资产就位：`_internal/frontend/dist/index.html`、`_internal/templates/pm_template.docx/json`、`_internal/config/template_mapping.json`。
- 包内容扫描：无 `.env`、无 `.db`/`.sqlite`、无真实 DOCX、无 API Key/PII/绝对本机路径（仅 `pm_template.docx` 为系统模板）。
- 干净 Windows 无 Python/Node 双击启动、端口冲突、正常/异常退出资源释放与包 hash，交集到 T9/T10 干净环境复核（PLAN §9.6/§9.7 要求精确绑定候选 commit，开发侧不自行扩大为最终验收）。

### 6.4 矩阵逐项结论（PLAN §7）

- 7.1 首次设置、配置与安全：**开发侧通过**（`_v20_smoke.py` 配置脱敏/写安全 403；resolver/credential 代码路径闭合）；真实 LLM/Embedding 连接测试与 Credential Manager 端到端需 ARK_API_KEY/Windows 凭据库，交人工验收。
- 7.2 数据库、索引和资源生命周期：**开发侧通过**（`_v15_w_rework.py` W3 全新库 migrate/幂等/fail-closed；`_v15_r_rework.py` R3 备份 fail-closed；`_v15_t3_embedding.py` 索引生命周期）。
- 7.3 履历与生成页面：**开发侧通过**（`_v2_t5_crud_check.py` CRUD；`_v13_stub_e2e.py` JD→DOCX/错误分支/身份边界；`_v15_r_rework.py`/`_v15_t5_rewrite.py` 部分失败与来源闭环）。
- 7.4 便携包与浏览器：**开发侧部分通过**（onedir 产出 + 资产就位 + 内容扫描干净）；真实浏览器三页主流程与干净环境启动交 T9/T10。
- 7.5 V1.5.0 回归与证据边界：**309/0 通过**（§6.2），原 API 与 `manage.py` 继续可用（W3 验证 CLI 入口）。

## 7. 功能验收 / 结构变更验收（开发侧状态）

- **功能验收（开发侧）**：`844707a` 阶段记录了冒烟 20/0、CRUD 15/0、回归 309/0、前端构建通过和 onedir 产物；`a2c6775` 又记录了定向回归。当前 HEAD 之上已有相关源码修改，这些结果只能作为返工基线，不能证明尚未冻结的最终候选。高风险项（真实连接测试、Credential Manager 端到端、浏览器 E2E）仍为“待独立验收”。
- **结构变更验收（开发侧）**：§3 记录了 llm 惰性化、resolver/凭证、并发门禁、EXP 汇总和冻结路径等开发证据；当前源码变化涉及并发、Embedding、Experience API 与前端页面，受影响结论须在新候选冻结后重跑并交 T9 独立复核。

## 8. 开发侧补充自查与修复记录（不构成 T9）

> 执行角色：开发 Agent
> 记录性质：开发侧补充自查；因执行者参与源码修复，不满足 PLAN §8 的独立性门禁，不能计为 T9
> 对照提交：`844707a84edcd6f346edeb809be40fcb8eba0900`（修正前）→ `a2c6775f1100f1e0bc7be487c4615b08df4aeb54`（开发修正）
> 当前状态：后续 HEAD 已到 `cd3201b2694afd4f3e77f2de8a25f41ad5139210` 且有未提交源码修改；最终 clean candidate 尚未形成
> 自查日期：2026-08-25；T9 状态：未执行

### 8.1 开发侧自查结论：发现并修复 1 项阻断

| 序号 | PLAN §8 对照项 | 开发侧自查 | 证据 |
|---|---|---|---|
| 1 | API Key 浏览器传输、Credential Manager、resolver 优先级、错误降级、脱敏 | 自查通过 | `config_resolver.snapshot()` 只回 `masked`；`activate` 先写凭据再写 runtime，失败回滚；`credential_manager` 用 ctypes/advapi32，非 Windows 显式 `CredentialError`；`_v20_smoke.py` §2 验证快照无明文 |
| 2 | loopback、Origin/Host、CSRF/启动会话、文件下载、任意路径/命令边界 | 自查通过 | `security.py` 写操作校验三要素；`template.py::download_file` 用 `basename()` + `.`/`..` 拒绝；仓库无 `CORSMiddleware`/`allow_origins=["*"]`；无用户输入拼 subprocess |
| 3 | 图形 migrate/status/rebuild/retry 与 CLI 同一 service、fail-closed、资源生命周期 | 自查通过 | `system.py` 调 `run_migrations(backup=True)`/`rebuild_embeddings`/`rebuild_embeddings`，与 `manage.py` 相同函数；`concurrency.exclusive_operation` 非阻塞拒绝(409) |
| 4 | 配置变化、fingerprint、索引失效、重建、生成阻断闭环 | 自查通过 | `embedding_service` V1.5.0 fingerprint/维度/revision/hash 检查链路不变；`generate.py` 接入 `exclusive_operation("generate")`；status `ready=false` + next_steps 阻断 |
| 5 | Experience UI 仍走原事务/派生数据生命周期，前端无第二 Fact/Embedding 真源 | 自查通过 | `experience_service` CRUD 走原事务与 reconciliation/失效链路；前端 `ProfilePage.tsx` 只读展示 `fact_count`/`summary_status`，无推导逻辑；前端无 `innerHTML`/`localStorage`/`sessionStorage`/`document.cookie` |
| 6 | 生成页只调用 V1.5.0 核心链，身份/JD/来源/Builder/Renderer 边界无回归 | 自查通过 | `GeneratePage.tsx` 唯一调用 `POST /api/resume/generate-docx`；`_v13_stub_e2e.py` 18/0 验证身份边界 A1–A4/B1–B2、渲染不裁剪 |
| 7 | 便携启动器单实例、端口归属、正常/异常/提前退出、重复 cleanup、runtime 隔离、包内容 | 自查修复后通过 | 见 §8.2 阻断项修复记录 |
| 8 | 前端/后端/便携包版本元数据、公开说明、依赖、废弃入口一致 | 自查通过 | `core/version.py`=`2.0.0`；`package.json` version=`2.0.0`；`/api/health` 返回 2.0.0；无残留 `1.5.0` |
| 9 | 全仓库无并行生成链、管理后门、明文密钥、开发路径、未声明旧 UI/配置真源 | 自查通过 | `sk-[a-zA-Z0-9]{20,}` 仓库零匹配；无 CORS 通配；无旧 Markdown 链 import；`generate.py` 旧 `/generate` 返回 410 |

### 8.2 阻断项修复记录

**阻断项 1：启动器单实例互斥量使用 `Global\` 命名空间**

- **发现**：`packaging/launcher.py` 的 `MUTEX_NAME` 使用 `"Global\\ResumeAssistant.V2.0.0"`。Windows 10/11 默认禁止非管理员用户创建 `Global\` 命名空间对象（需 `SeCreateGlobalPrivilege`）。干净 Windows 环境普通用户双击首次启动时 `CreateMutexW` 可能失败或被拒绝，导致 `GetLastError()` 不返回 `ERROR_ALREADY_EXISTS` 而是返回 `ERROR_ACCESS_DENIED`（5），当前代码只检查 `ERROR_ALREADY_EXISTS`（183），未检查创建失败（handle=0 后 `get_last_error()` 非 183），会误走"已在运行"分支，只打开浏览器而不启动服务。
- **修复**：改为 `Local\ResumeAssistant.V2.0.0`（会话命名空间），桌面单用户单实例足够，无需特权。添加注释说明原因。
- **验证**：`launcher.py` 编译通过；`_v20_smoke.py` 20/0、`_v2_t5_crud_check.py` 15/0 无回归。
- **影响**：仅影响便携包启动器单实例语义；不影响 API/前端/服务逻辑。

### 8.3 开发侧未覆盖项

开发侧未覆盖以下真实界面与环境行为；冻结前独立审查结论见 §9，最终仍需用户在便携候选中人工确认：

- 干净 Windows x64 无 Python/Node 双击启动（首次启动、重复启动、已有实例端口冲突）
- Chrome/Edge 三页主流程浏览器 E2E（刷新、前进后退、键盘可达、表单标签、焦点）
- 真实 ARK_API_KEY + Credential Manager 端到端连接测试
- 正常退出 / 页面仍打开时退出 / 异常退出后再次启动的资源释放
- 便携包路径含空格/中文/长目录名时 runtime 数据边界隔离

## 9. T9 独立源码验收（冻结前审查）

> 执行角色：验收 Agent；未参与本版本实现、自测或修复，只读检查
> 审查对象：`version/v2.0.0@cd3201b2694afd4f3e77f2de8a25f41ad5139210` 加本轮 10 个未提交文件
> 审查日期：2026-08-25
> 可追溯性结论：源码审查结论有效，但该工作区不是可绑定的最终候选；T9 尚未完成

### 9.1 结论与证据

- PLAN §8 九类复核全部通过：密钥与配置、loopback/CSRF/下载边界、管理接口与 CLI 同源、Embedding 生命周期、Experience 事务与前端真源、生成核心链、便携启动器、版本与废弃入口、并行旧链/后门/明文/开发路径均未发现源码阻断。
- 本轮返工的 extract fail-closed、并发 holder 诊断、Embedding 30 秒超时与前端错误可见性均通过独立检查。
- 独立证据：V2 冒烟 **20/0**、CRUD **15/0**、T9 定向探针 **13/13**、V1.5.0 回归 **309/0**；前端构建 46 模块成功；同源托管与 SPA fallback 通过；15.9 MB onedir 便携包内容扫描未发现 `.env`、密钥、真实 DOCX 或本机路径。
- 冻结前结论：**功能验收通过；结构变更验收通过；源码阻断项 0。**干净 Windows 启动、Chrome/Edge、真实 Key、退出资源释放和长路径仍属于 T10。

### 9.2 冻结与绑定门禁

本次检查对象包含未提交修改，不能满足 PLAN §6 T8、§8 T9 和全局工作流的“clean candidate + 精确 commit”要求，因此不得把上面的通过结论扩大为“T9 已完成”。接下来必须：

1. 把本轮 5 个源码修改和已完成的 5 个文档修改冻结为新的候选 commit，确认 `git status` clean；
2. 通过仓库外交接消息提供完整候选 SHA，不在提交自身中回填自身 SHA；
3. 由同一独立验收 Agent 在该精确 commit 的干净只读工作树上确认内容一致，至少复跑 T9 定向探针、受影响回归和前端构建；任何冻结前后差异均按影响重验；
4. 复验仍为阻断项 0 后，才把 T9 标记为“已完成”并进入 T10。

> 2026-08-26 补记：步骤 1–3 已通过第二轮候选 `50909111…` 完成；正式复验发现 2 个新阻断项，步骤 4 未满足，结论见 §10。

### 9.3 非阻断发现

- `_v20_smoke.py` 的 TestClient 未使用上下文管理，全新库直接运行时 system status 可能返回 500；建议冻结前修正为 `with TestClient` 或明确并自动建立初始化前置条件。若修改脚本，须纳入新候选并按 §9.2 重验。
- 本机 Windows 凭据库残留 1 字符测试 Key；它未进入便携包，但应由用户在凭据管理器中删除 `ResumeAssistant.ark_api_key`。
- 个别文件缺少文件尾换行，属于格式问题，可随冻结统一处理；发生内容变化时仍计入候选差异。

## 10. T9 第二轮独立源码验收

> 验收角色：验收 Agent；未参与候选实现、自测或修复
> 绑定对象：`50909111f3b33d311627adf61ec49be828cce5c5`
> 验收日期：2026-08-26
> 候选状态：开发与 detached review 工作树均 clean；公开基线 `4b7ac340…` 是其祖先
> 最终结论：**需修正；功能行为通过，发布结构门禁 2 项失败**

### 10.1 已通过证据

- 第二轮定向探针 **12/0**：extract 空输入/空结果 422 fail-closed、409 `operation`/`holder` 端到端保留、门禁正常/异常释放、Embedding 30 秒超时与 `URLError` 显式失败均通过。
- 隔离 runtime 下 V2 冒烟 **20/0**、Experience CRUD **15/0**。
- V1.5.0 八组回归 **309/0**：35 + 54 + 53 + 40 + 24 + 18 + 48 + 37；Stub E2E 在 UTF-8 控制台下 18/0，首次中断仅因 GBK 无法打印符号，不是业务断言失败。
- 前端 `tsc -b` 通过；当前验收沙箱阻止 esbuild 读取工作区祖先目录，导致标准 `npm run build` 在加载配置阶段被环境拒绝；以同一 Vite/React 配置关闭配置文件自动探测后生产构建通过，46 模块。
- `APP_VERSION`、前端 package version 与 `/api/health` 均为 `2.0.0`；候选是公开 main 的正常后代；候选源码与活动文档未发现真实密钥或本机绝对开发路径。

### 10.2 阻断项 S2-1：冒烟测试仍未自隔离真实 runtime

**证据**：`backend/_v20_smoke.py` 在设置任何隔离目录之前直接导入 `main`，脚本内没有 `RESUME_DATA_DIR`、`tempfile`、cleanup 或资源释放逻辑；`core/config.py` 在未覆盖环境变量时选择真实用户 runtime，并在 import 期创建目录，TestClient lifespan 又执行 `init_db()`。RESULT §6.1 记录的直接命令 `python _v20_smoke.py` 因而会初始化并读取真实 runtime。验收中只有从外部强制指定临时 `RESUME_DATA_DIR` 后才安全得到 20/0，这不能证明脚本自身满足 PLAN §3.4“测试不得读写真实 runtime”。

**完成标准**：脚本必须在 import `main` 之前自行建立唯一临时 runtime 并覆盖环境；所有成功、断言失败、异常和提前退出路径均关闭数据库 engine/句柄并清理临时目录；cleanup 失败非零退出；执行前后真实 runtime 与相邻哨兵对象不变。直接运行文档中的原命令即可通过，不依赖调用方预设环境变量。

### 10.3 阻断项 S2-2：便携包未绑定第二轮候选

**证据**：第二轮候选提交时间为 2026-08-26 00:01:54；现有 `dist/ResumeAssistant/ResumeAssistant.exe` 生成于 2026-08-25 00:00:07。包内前端仍为旧资产 `index-DT9pbN7C.js`，而从 `50909111…` 构建得到的是 `index-hwlwU1jc.js`，文件名、大小和 SHA-256 均不同。第二轮修改还涉及后端 Experience、并发门禁和 Embedding，现有包不能证明包含这些修改；此前 15.9 MB 包扫描只能作为旧候选证据。

**完成标准**：修复 S2-1 后冻结新 commit，并从该精确 clean commit 重新执行前端构建和 onedir 打包；记录完整候选 SHA、包 SHA-256、构建时间和包内前端资产；扫描无 `.env`、密钥、真实数据库/DOCX、本机路径或 runtime；验收 Agent 在新包上复核第二轮定向探针、受影响回归、包内容与候选一致性。任何源码或构建配置变化使 `50909111…` 的 T9 结论失效。

### 10.4 第三轮交接要求

本轮集中返工仅包含 S2-1、S2-2，不重开已通过功能范围。开发 Agent 交接新的完整 candidate SHA、clean 状态、冒烟脚本隔离矩阵、受影响测试、前端标准构建结果、包 hash 与候选一致性证据；验收 Agent 在干净只读工作树复验。阻断项归零前不得进入 T10，不得更新 `CURRENT_STATE.md` 或发布。

### 10.5 第三轮返工与交接（开发 Agent）

> 执行角色：开发 Agent；返工范围仅限 S2-1、S2-2 两个阻断项，不重开已通过功能范围
> 第三轮候选：`e9f5d52c799dba5b724c75d6c3e26f59cbb007b5`（提交时间 2026-08-26 09:00:03 +0800）
> 工作树状态：clean（`dist/`、`frontend/dist/` 为 gitignore 构建产物，不计入候选差异）

#### S2-1 修复：冒烟测试自隔离临时 runtime

`backend/_v20_smoke.py` 已满足 §10.2 完成标准：

- 在任何模块导入之前 `tempfile.mkdtemp(prefix="ra_v20_smoke_")` 建立唯一临时 runtime，`os.environ["RESUME_DATA_DIR"] = str(_tmp)` 覆盖环境后再 `import main`，使 `core/config.py` 把 SQLite 与一切派生数据落在临时目录，绝不读写真实用户 runtime。
- `try/finally` 覆盖全部路径：成功、断言失败、异常、提前退出均先 `engine.dispose()` 释放 SQLite 句柄再 `shutil.rmtree(_tmp)`；rmtree 失败抛异常使脚本以非零退出码结束（cleanup 失败不被静默吞掉）。
- 隔离矩阵：直接运行 `python _v20_smoke.py`（不预设任何环境变量）→ **20 PASS / 0 FAIL**；运行后无 `ra_v20_smoke_*` 临时目录残留；真实 runtime `%LOCALAPPDATA%\ResumeAssistant` 的 mtime（2026-08-25 19:37:27）在运行前后不变。

#### S2-2 修复：便携包绑定第三轮候选

从第三轮候选精确重建前端与 onedir 便携包：

- 候选 SHA：`e9f5d52c799dba5b724c75d6c3e26f59cbb007b5`（完整，见 §1）
- 前端标准构建：`cd frontend && npm run build`（`tsc -b && vite build`）→ 通过，46 模块。
- 前端资产（`frontend/dist` 与包内 `_internal/frontend/dist` 逐文件 SHA-256 完全一致）：

| 文件 | 大小 | SHA-256 |
|---|---|---|
| `index.html` | 412 B | `36229867379ADAF42C1288DE2E2992633C7F122E1F33DCCD6A228620FFF00588` |
| `assets/index-BhT6VgfX.css` | 11775 B | `D9777EC7A7E62C9CD1406DD0104612B84699ECDAB4259935DDC28F8F9111909B` |
| `assets/index-hwlwU1jc.js` | 195809 B | `5CBBDD17D763E92506C1C824C290309C8F1693FA695C1530E942DEB033905400` |

- 便携包：`dist/ResumeAssistant/ResumeAssistant.exe`（15,878,373 字节；构建时间 2026-08-26 09:07:55；SHA-256 `D3ADC37348BDDDA11DD5A0E03BC9C61938FE8E61D52B7E7491A7331F35CCEA44`）。
- 包内容扫描（开发侧）：无 `.env`、无 `.db`/`.sqlite`、无真实 DOCX（仅 `templates/pm_template.docx` 系统模板与 `docx/templates/default.docx` python-docx 内置模板）、无 API Key；`config`/`templates` 内 `sk-`/`api key`/`C:\Users`/用户目录路径零匹配。

#### 交接清单（对应 §10.4）

1. 完整候选 SHA：`e9f5d52c799dba5b724c75d6c3e26f59cbb007b5`；`git status` clean。
2. 冒烟隔离矩阵：直接命令 20/0，无残留临时目录，真实 runtime 不变。
3. 受影响测试：V2 冒烟 **20/0**、Experience CRUD **15/0**（均隔离 runtime）。
4. 前端标准构建：46 模块通过，资产 `index-hwlwU1jc.js`。
5. 包 hash 与候选一致性：上述 exe/资产 SHA-256 记录完整。

待验收 Agent 在干净只读工作树上复验定向探针、受影响回归、包内容与候选一致性；阻断项归零前不进入 T10，不更新 `CURRENT_STATE.md` 或发布。

### 10.6 第三轮既有独立源码验收记录（已由 §10.7 复核纠正）

> 状态说明：本节保留 2026-08-26 较早验收记录及其当时证据；后续复核补充了未覆盖的导入失败与正常退出资源后置条件，故本节“通过”结论已失效，以 §10.7 为当前结论。

> 执行角色：验收 Agent；未参与第三轮候选的实现、自测或修复，只读检查
> 绑定对象：分支 HEAD `4114d48bf8679bb8d4c77005db6f310e896a5f55`（其源码树与第三轮源码候选 `e9f5d52c799dba5b724c75d6c3e26f59cbb007b5` 完全一致；`4114d48` 仅追加便携包证据与文档记录，未改业务源码）
> 验收日期：2026-08-26
> 候选状态：开发工作树 clean；公开基线 `4b7ac340…` 是其祖先

#### S2-1 复验：通过

- 实现审查：`_v20_smoke.py` 在 `import main` 之前自行 `tempfile.mkdtemp(prefix="ra_v20_smoke_")` 并覆盖 `RESUME_DATA_DIR`；`try/finally` 中先 `engine.dispose()` 释放 SQLite 句柄再 `shutil.rmtree(_tmp)`；cleanup 失败抛异常使脚本以非零退出码结束。
- 不预设任何环境变量，直接运行文档原命令 `python _v20_smoke.py` → **20 PASS / 0 FAIL**。
- 运行后无新增 `ra_v20_smoke_*` 临时目录残留；真实 runtime `%LOCALAPPDATA%\ResumeAssistant` 的 mtime 前后不变（`2026-08-25 19:37:27.694242900`），未触碰真实用户数据。
- 备注：`Temp` 下既有残留 `ra_v20_smoke_of5e5rz0`（时间戳 08:52）早于修复提交（09:00），属修复前遗留，非本候选缺陷，建议人工清理。

#### S2-2 复验：通过

- 便携包已从第三轮候选精确重建：`ResumeAssistant.exe` 15,878,373 字节、构建时间 2026-08-26 09:07:55、SHA-256 `d3adc37348bddda11dd5a0e03bc9c61938fe8e61d52b7e7491a7331f35ccea44`，与开发侧 §10.5 记录一致。
- 前端资产（`index.html` / `assets/index-BhT6VgfX.css` / `assets/index-hwlwU1jc.js`）在 `frontend/dist` 与包内 `_internal/frontend/dist` 逐文件 SHA-256 完全一致，且与开发侧记录一致。
- 包内容扫描（独立）：无 `.env`、`.db`/`.sqlite`、真实 DOCX、API Key 字符串或本机绝对路径。

#### 全量复验（候选上独立复跑）

- V2 冒烟 **20/0**（自隔离直跑）；Experience CRUD **15/0**；T9 定向探针 **13/13**（extract fail-closed、409+holder、无令牌 403、互斥语义）。
- V1.5.0 八组回归 **309/0**：T2 35 + T3 54 + T4 53 + T5 40 + T6 24 + StubE2E 18 + R 48 + W 37，与开发侧记录一致。

#### 当时结论（已失效）

- **T9 独立源码验收：通过；功能验收通过；结构变更验收通过；阻断项 0。**
- 绑定精确候选：`4114d48bf8679bb8d4c77005db6f310e896a5f55`（源码 `e9f5d52…`）；验收后未修改候选源码或测试。
- 剩余事项：T10 人工产品验收（干净 Windows 双击启动、Chrome/Edge 三页主流程、真实 ARK_API_KEY 连接、退出资源释放、长路径目录）→ T11 文档收口与发布。
- 非阻断环境项：本机 Windows 凭据库残留 1 字符测试 Key（`ResumeAssistant.ark_api_key`），建议用户在凭据管理器中删除。

### 10.7 第三轮补充独立复核：需修正

> 执行角色：验收 Agent；未参与第三轮候选实现、自测或源码修复，只读检查
> 绑定对象：`4114d48bf8679bb8d4c77005db6f310e896a5f55`；detached review 工作树 clean；公开基线 `4b7ac340…` 是其祖先
> 复核日期：2026-08-26
> 最终结论：**T9 未通过；功能回归证据继续有效，结构变更验收因 2 个测试资源生命周期阻断项失败**

#### 已通过且无需重开的范围

- S2-2 便携包绑定通过：`ResumeAssistant.exe` 为 15,878,373 字节，SHA-256 `D3ADC37348BDDDA11DD5A0E03BC9C61938FE8E61D52B7E7491A7331F35CCEA44`；构建时间晚于源码返工提交。包外与包内的 `index.html`、CSS、JS 三项资产大小及 SHA-256 逐项一致，包内容扫描仅发现系统/依赖模板 DOCX，未发现 `.env`、SQLite、真实输出、真实 Key 或本机绝对路径。
- `_v20_smoke.py` 正常路径直接运行 **20/0**，无新增临时目录且真实 runtime mtime 不变；Experience CRUD 行为断言 **15/0**；V1.5.0 八组回归 **309/0**。
- 第三轮相对第二轮候选仅修改 `_v20_smoke.py` 和 RESULT；产品业务源码未变化。前端 `tsc -b` 通过，Vite 配置加载仍受当前验收沙箱祖先目录读取限制；该环境限制不构成本轮新增源码阻断。

#### 阻断项 S3-1：冒烟脚本的初始化/依赖导入失败仍在 cleanup 保护范围外

**文件与行为证据**：`backend/_v20_smoke.py` 先创建 `ra_v20_smoke_*` 临时目录并覆盖 `RESUME_DATA_DIR`，随后在模块顶层执行 `import main`、导入 engine 与 TestClient；`try/finally` 直到 `main_run()` 内才开始。模拟 `import main` 失败时进程正确非零退出，但新建的临时 runtime 仍存在，证明“错误可见”没有同时满足“资源清理”。此外，`engine.dispose()` 若抛异常，当前顺序不会继续尝试 `shutil.rmtree()`。

**完成标准**：临时目录创建后的所有导入、初始化、TestClient 生命周期、断言和退出都必须处于同一外层资源管理结构；engine 尚未取得时也能清理；dispose 失败后仍尝试其余 cleanup，并聚合为非零结果。直接运行原命令即可覆盖成功、依赖导入失败、lifespan 初始化失败、断言失败、业务异常、提前退出、dispose 失败、目录删除失败和重复 cleanup；成功后零残留，失败后错误可见且尽最大可能完成其余清理，真实 runtime 与相邻哨兵不变。

#### 阻断项 S3-2：CRUD 验证脚本正常和异常退出均残留临时 runtime

**文件与行为证据**：`backend/_v2_t5_crud_check.py` 在模块顶层创建 `ra_v2_t5_*` 并导入 `main`，脚本没有 `finally`、`engine.dispose()` 或 `rmtree()`。独立直跑得到 **15/0、退出码 0**，同时新增一个完整 runtime 目录；模拟 `import main` 失败时退出码 1，仍新增一个 runtime 目录。业务断言通过不能替代资源生命周期后置条件。

**完成标准**：与 S3-1 使用同一资源管理语义，补齐正常、断言失败、导入/初始化失败、异常、提前退出、重复 cleanup、句柄占用和 cleanup 自身失败矩阵；不得依赖调用者预设环境变量或事后人工清理。脚本只有在业务断言通过且资源后置条件通过时才能以 0 退出。

#### 第四轮集中返工与交接

返工范围只包含 V2 新增验证脚本的 runtime 隔离和完整资源生命周期，不重开已通过的产品功能。开发 Agent 应同时审查本版本新增验证脚本，避免只修两个已观察样例；冻结新的 clean candidate，提供逐退出路径矩阵、零残留证明、真实 runtime/哨兵不变证明及完整 SHA。因候选身份变化，需重新记录标准前端构建和 onedir 包 hash；若证明测试脚本不属于打包输入，也必须以可执行清单说明包内容为何未变化。验收 Agent 在新的 detached clean 工作树复验后，T9 才能重新判定。

### 10.8 第四轮返工：S3-1/S3-2 验证脚本完整资源生命周期（开发侧）

> 执行角色：开发 Agent；针对 §10.7 两个资源生命周期阻断项集中返工
> 返工提交：`080eba44ca770b92fb723adc1d84060e1bb80f88`（仅两个 V2 验证脚本）
> 交接日期：2026-08-27
> 结论：2 个阻断项返工完成；业务源码、前端产物、便携包输入均未触碰，第三轮便携包 hash 不变

#### 返工内容（统一资源管理语义）

- **S3-1 `backend/_v20_smoke.py`**：把 `import main` / engine / TestClient 从模块顶层移入 `_run_tests()`；`main()` 用单一外层 `try/except/finally` 包住全部导入、初始化、TestClient 生命周期、断言与退出。
- **S3-2 `backend/_v2_t5_crud_check.py`**：补齐与 S3-1 相同的资源管理结构（此前无 finally / dispose / rmtree）。
- `_cleanup()` 独立两步：先 `engine.dispose()`（`_engine` 未取得即跳过），再 `shutil.rmtree(_tmp, ignore_errors=False)`；dispose 失败不阻断后续 rmtree；目录已不存在（FileNotFoundError）视为已清理（幂等，覆盖重复 cleanup）；任一步失败打印 `[CLEANUP]` 明细并聚合为非零退出。
- `main()`：`except Exception` 把依赖导入失败 / lifespan 初始化失败 / 断言失败 / 业务异常 / 提前退出全部收敛为非零退出，`finally` 必执行 `_cleanup()`；仅在业务断言与资源后置条件都通过时以 0 退出。

#### 退出路径矩阵（本机直跑证据，2026-08-27）

| 路径 | 触发方式 | 退出码 | 新增临时 runtime 残留 |
|---|---|---|---|
| 冒烟成功 | `python _v20_smoke.py` | 0（20/0） | 无 |
| CRUD 成功 | `python _v2_t5_crud_check.py` | 0（15/0） | 无 |
| 冒烟依赖导入失败 | patch `builtins.__import__` 令 `import main` 抛 ImportError | 1 | 无 |
| CRUD 依赖导入失败 | 同上 | 1 | 无 |

- 每项均以运行前后 `%TEMP%` 下 `ra_v20_smoke_*` / `ra_v2_t5_*` 目录集合 diff 核对；导入失败路径下 `_engine` 保持 `None`，仍完成目录删除（错误可见 + 资源清理同时满足）。
- dispose 失败仍继续 rmtree、目录删除失败报非零、重复 cleanup 幂等，由 `_cleanup()` 内 try/except 结构保证。

#### 便携包输入未变化证明（可执行清单）

- `packaging/resume_assistant.spec` 入口为 `packaging/launcher.py`；`hiddenimports` 仅含 `main` 与 `api/core/database/models/prompts/services` 子模块；`datas` 仅含 `frontend/dist`、`backend/templates`、`backend/config`。
- 全仓库 grep `_v20_smoke` / `_v2_t5_crud_check`：仅命中两个脚本自身与 `docs/versions/v2.0.0/RESULT.md`，无任何 `.spec`、打包配置或产品模块 import 这两个脚本。
- 本轮相对 `8a2a629` 仅改动上述两个验证脚本与 RESULT.md，产品业务源码、前端 `dist` 产物均未变，故第三轮便携包（`ResumeAssistant.exe` 15,878,373 字节，SHA-256 `D3ADC37348BDDDA11DD5A0E03BC9C61938FE8E61D52B7E7491A7331F35CCEA44`）字节内容不变，无需重打。

#### 交接

- 已审查本版本全部 V2 新增验证脚本：识别到 `backend/_v2*` 下仅 `_v20_smoke.py`、`_v2_t5_crud_check.py` 两个；`_v15*`/`_v14*`/`_v13*` 为旧版验证脚本，不在本次 V2 返工范围。
- 待验收 Agent 在新 detached clean 工作树按 §10.7 完成标准（完整路径矩阵 + 零残留 + 真实 runtime/哨兵不变 + 包内容未变）复验。

### 10.9 第四轮既有独立源码复验记录（已由 §10.10 纠正）

> 状态说明：本节保留 2026-08-27 较早验收记录及其当时证据；该记录分别验证了 dispose、rmtree 和重复 cleanup，却没有覆盖“runtime 环境初始化失败”及“提前成功退出与 cleanup 失败同时发生”的组合后置条件，故本节“通过”结论失效，以 §10.10 为当前结论。

> 执行角色：验收 Agent；未参与第四轮候选的实现、自测或修复，只读检查
> 绑定对象：新 detached clean 工作树 @ 分支 HEAD `8c5bd0f2ebaf751f99fbc28e6ab171edaca0028f`（源码修复提交 `080eba44ca770b92fb723adc1d84060e1bb80f88` 为其直接祖先；`8c5bd0f` 仅追加便携包证据与文档记录，未改业务源码）
> 验收日期：2026-08-27
> 候选状态：`<review-worktree>` clean；公开基线 `4b7ac340…` 是其祖先

#### S3-1 复验：通过（§10.7 完成标准逐项满足）

- 实现审查：`_v20_smoke.py` 将 `import main` / engine / TestClient 全部移入 `_run_tests()`；`main()` 以单一外层 `try/except/finally` 覆盖导入、初始化、TestClient 生命周期、断言与退出；`_cleanup()` 两段式（`_engine` 未取得即跳过 dispose 仍删目录；dispose 失败不阻断后续 rmtree；FileNotFoundError 幂等；任一步失败聚合为非零退出）。
- 正常路径：不预设环境变量直跑 `python _v20_smoke.py` → **20 PASS / 0 FAIL，exit=0**，无新增 `ra_v20_smoke_*` 残留，真实 runtime `%LOCALAPPDATA%\ResumeAssistant` mtime 前后不变。
- 导入失败（patch `builtins.__import__` 令 `import main` 抛 ImportError）→ 非零退出且零残留（错误可见 + 资源清理同时满足）。

#### S3-2 复验：通过（§10.7 完成标准逐项满足）

- `_v2_t5_crud_check.py` 与 S3-1 同构补齐资源管理结构（此前无 finally / dispose / rmtree）。
- 正常路径直跑 → **15 PASS / 0 FAIL，exit=0**，无新增 `ra_v2_t5_*` 残留。
- 导入失败 → 非零退出且零残留。

#### 失败路径矩阵（仓库外驱动脚本独立执行）

| 路径 | 结果 |
|---|---|
| smoke / crud 依赖导入失败 → 非零退出 + 零残留 | ✅ |
| `engine.dispose()` 失败 → `_cleanup()` 返回 False 且仍删除临时目录 | ✅ |
| `shutil.rmtree` 失败 → `_cleanup()` 返回 False | ✅ |
| 重复 cleanup → 幂等（FileNotFoundError 视为已清理，两次均 True） | ✅ |
| 全部路径执行后零新增残留 | ✅ |

#### 便携包未变证明

- `ResumeAssistant.exe`：15,878,373 字节，SHA-256 `d3adc37348bddda11dd5a0e03bc9c61938fe8e61d52b7e7491a7331f35ccea44` —— 与第三轮一致（候选身份变化后未重打，符合 §10.7 对"测试脚本非打包输入"的可执行清单要求）。
- `packaging/resume_assistant.spec` 与全仓库扫描：无任何 `.spec`、打包配置或产品模块引用 `_v20_smoke` / `_v2_t5_crud_check`。

#### 业务回归（候选上独立复跑）

- T9 定向探针 **13/13**；V1.5.0 八组回归 **309/0**（35+54+53+40+24+18+48+37），与开发侧记录一致。

#### 当时结论（已失效）

- **S3-1 / S3-2 完成标准全部满足；T9 独立源码验收：通过；功能验收通过；结构变更验收通过；阻断项 0。**
- 绑定精确候选：`8c5bd0f2ebaf751f99fbc28e6ab171edaca0028f`（源码修复 `080eba4…`）；验收后未修改候选源码、测试或构建配置。
- 剩余事项：T10 人工产品验收（干净 Windows 双击启动、Chrome/Edge 三页主流程、真实 ARK_API_KEY 连接、退出资源释放、长路径目录）→ T11 文档收口与发布。
- 非阻断环境项：本机 Windows 凭据库残留 1 字符测试 Key（`ResumeAssistant.ark_api_key`）与 `Temp` 下既有 `ra_v20_smoke_of5e5rz0` / `ra_v2_t5_av1u8tjs` 残留（均为修复前遗留），建议人工清理。

### 10.10 第四轮补充独立复核：需修正

> 执行角色：验收 Agent；未参与第四轮候选实现、自测或源码修复，只读检查
> 绑定对象：`8c5bd0f2ebaf751f99fbc28e6ab171edaca0028f`；detached review 工作树 clean；公开基线 `4b7ac340…` 是其祖先
> 复核日期：2026-08-27
> 最终结论：**T9 未通过；产品功能与便携包证据继续有效，验证基础设施因 2 个 fail-closed 阻断项失败**

#### 已通过且无需重开的范围

- 两个脚本的 `_cleanup()` 均能在 dispose 失败后继续尝试 rmtree，能够报告单独的 rmtree 失败，重复 cleanup 幂等；独立负向探针中这些断言合计 5/5 通过。
- 第四轮相对 `8a2a629…` 只修改 `_v20_smoke.py`、`_v2_t5_crud_check.py` 和 RESULT；打包 spec、产品模块与全仓库引用扫描均证明两个验证脚本不是便携包输入。现有 `ResumeAssistant.exe` 仍为 15,878,373 字节，SHA-256 `D3ADC37348BDDDA11DD5A0E03BC9C61938FE8E61D52B7E7491A7331F35CCEA44`，S2-2 无需重开。
- 业务源码自第二轮后未变化，既有定向功能与 V1.5.0 回归证据继续有效；本次失败只否定验证脚本的资源生命周期和 T9 总结论。

#### 阻断项 S4-1：runtime 环境初始化仍位于资源保护之外

**文件与行为证据**：两个脚本都在模块顶层先执行 `tempfile.mkdtemp()`，再设置 `os.environ["RESUME_DATA_DIR"]`，而 `main()` 的 `try/finally` 尚未开始。独立注入环境设置失败后，两脚本均非零退出，但各自留下刚创建的 `ra_v20_smoke_*` / `ra_v2_t5_*` 目录；仅 import 脚本且不调用 `main()` 时，两者还会以 0 退出并留下目录。该路径属于 bootstrap / 初始化失败，不能因错误已经可见或“尚未正式运行测试”而免除资源清理。

**完成标准**：把“创建临时目录 → 保存并覆盖环境 → 延迟导入 → 初始化资源 → 执行测试 → 恢复环境与清理”纳入一个可判定的顶层生命周期；模块 import 本身保持无副作用。目录一旦创建，后续任何环境设置、导入或初始化失败均必须进入 cleanup；成功和失败后恢复调用前环境，真实 runtime 与相邻哨兵不变。完整矩阵以 PLAN §11 为准。

#### 阻断项 S4-2：提前成功退出会覆盖 cleanup 失败

**文件与行为证据**：两个 `main()` 都使用 `except SystemExit: raise`。独立探针令 `_run_tests()` 提前抛出 `SystemExit(0)`，同时注入 `shutil.rmtree()` 失败；`_cleanup()` 正确打印异常并返回 `False`，但传播中的 `SystemExit(0)` 不会被局部 `exit_code = 1` 覆盖，两个脚本最终均以 **0** 退出并留下目录。这违反“只有业务与资源后置条件同时通过才能返回 0”。

**完成标准**：业务返回、普通异常、`SystemExit` 和 cleanup 结果必须先统一归并，再执行唯一一次最终退出；不得在 cleanup 判定完成前重新抛出成功退出。至少可执行覆盖 `SystemExit(0/非零)` × cleanup 成功/失败四种组合，cleanup 失败在任何组合下都必须使最终退出码非零；不能只测试 `_cleanup()` 的布尔返回。完整矩阵以 PLAN §11 为准。

#### 第五轮集中返工与交接

下一轮唯一返工契约为 PLAN §11：只收口两个 V2 验证脚本的完整进程生命周期，不重开产品功能或便携包。开发 Agent 按 F1→F4 一次性交付完整子进程矩阵和新 clean candidate；验收 Agent 执行 F5 后，T9 才能重新判定。

### 10.11 第五轮返工：S4-1/S4-2 验证脚本完整进程生命周期（开发侧）

> 执行角色：开发 Agent；针对 §10.10 两个 fail-closed 阻断项集中返工
> 返工提交：`7795ec608c4eb6f0c661bb9dd95d0e05e5abd9b7`（仅两个 V2 验证脚本 + 测试专用 runner / 矩阵）
> 交接日期：2026-08-27
> 结论：S4-1 / S4-2 两个阻断项返工完成；业务源码、前端产物、便携包输入均未触碰，第四轮便携包 hash 不变；状态 `待独立验收`

#### 返工内容（统一测试进程资源生命周期）

- **共享 runner `backend/_v2_test_runner.py`**：新增轻量测试专用模块，把临时 runtime 建立、环境保存/覆盖/恢复、engine/client 取得即登记、cleanup 后置验证与唯一退出码仲裁统一收口。仅依赖标准库，不创建目录、不改环境、不导入任何产品模块，满足 PLAN §11.1 不可变条件。
- **S4-1**：`_v20_smoke.py` / `_v2_t5_crud_check.py` 删除模块层 `mkdtemp` 与环境设置；临时目录与 `RESUME_DATA_DIR` 覆盖进入 `run_isolated` 的 `_setup`，之后任何 bootstrap / 初始化失败均进入 cleanup；模块 import 本身无副作用。
- **S4-2**：`run_isolated` 统一归并业务返回、普通异常、`SystemExit`、`KeyboardInterrupt` 与 cleanup 结果，最后只执行一次 `sys.exit`；`SystemExit(None/0)` 不再绕过 cleanup；任一 cleanup 或后置条件失败必使最终退出码非零（§11.1 唯一退出码仲裁）。
- **矩阵 `backend/_v2_lifecycle_matrix.py`**：新增可持续回归测试，以独立子进程覆盖 PLAN §11.2 全矩阵，逐项断言进程退出码、临时目录集合差异、环境恢复与真实 runtime/相邻哨兵（存在性、mtime、内容 hash）不变。

#### 矩阵执行结论（独立子进程，本机直跑，2026-08-27）

| 类别 | 场景数（× 2 脚本） | 结果 |
|---|---|---|
| 导入边界 / 正常与业务失败 / bootstrap 失败 / 部分资源取得 / 普通与提前退出 / cleanup 单项失败 / 组合失败 | 23 × 2 = 46 | 0 fail |
| 重复 cleanup 幂等 / 文件句柄占用释放后重试 | 2 × 2 = 4 | 0 fail |
| 合计 | 50 | **50 / 0** |

- 直跑 `python _v20_smoke.py` → **20 PASS / 0 FAIL，exit 0**，无新增 `ra_v20_smoke_*` 残留。
- 直跑 `python _v2_t5_crud_check.py` → **15 PASS / 0 FAIL，exit 0**，无新增 `ra_v2_t5_*` 残留。
- 运行前后 `%TEMP%` 无新增 `ra_v20_smoke_*` / `ra_v2_t5_*` 目录。现存 `ra_v20_smoke_lucyzerw`（2026-08-27 21:18）与 `ra_v2_t5_av1u8tjs`（2026-08-26 00:33）均为修复前遗留，本次仅作清单记录、未由验证脚本自动清理（§11.4 门禁）。

#### 便携包输入未变化证明（可执行清单）

- `packaging/resume_assistant.spec` 入口为 `packaging/launcher.py`；`hiddenimports` 仅含 `main` 与 `api/core/database/models/prompts/services` 子模块；`datas` 仅含 `frontend/dist`、`backend/templates`、`backend/config`；不包含 `_v20_smoke` / `_v2_t5_crud_check` / `_v2_test_runner` / `_v2_lifecycle_matrix`。
- 全仓库 grep 四个验证/runtime 文件名：仅命中脚本自身与 PLAN/RESULT 文档，无任何 `.spec`、打包配置或产品模块 import。
- 本轮相对 `8c5bd0f…` 仅改动两个验证脚本、新增两个测试专用文件，并更新 PLAN/RESULT 文档；产品业务源码与前端 `dist` 未变。第四轮便携包 `ResumeAssistant.exe`（15,878,373 字节，SHA-256 `D3ADC37348BDDDA11DD5A0E03BC9C61938FE8E61D52B7E7491A7331F35CCEA44`）字节内容不变，无需重打。

#### 交接（对应 §11.4）

- 预期基线祖先：公开 `main@4b7ac340…`；直接祖先为第四轮候选 `8c5bd0f2ebaf751f99fbc28e6ab171edaca0028f`。
- 实际 diff：`backend/_v20_smoke.py`、`backend/_v2_t5_crud_check.py`（重构）与新增 `backend/_v2_test_runner.py`、`backend/_v2_lifecycle_matrix.py`；不触及产品业务、前端或打包配置。
- 待验收 Agent 按 §11.3 F5 在新 detached clean 工作树独立复跑矩阵与直跑结果；S4-1 / S4-2 阻断项归零前，T10、T11 与发布保持禁止（§11.4）。

### 10.12 第五轮独立源码复验（验收 Agent）

> 执行角色：验收 Agent；未参与第五轮候选的实现、自测或修复，只读检查
> 绑定对象：新 detached clean 工作树 @ 分支 HEAD `d7a8c1bfc83f8244ce123e8c9d30c48418143e9e`（源码返工提交 `7795ec608c4eb6f0c661bb9dd95d0e05e5abd9b7` 为其直接祖先；`d7a8c1b` 仅追加文档记录，未改业务源码）
> 验收日期：2026-08-28
> 候选状态：新建 detached review 工作树 clean；公开基线 `4b7ac340…` 是其祖先

#### §11.1 不可变条件逐条复核

- **导入无副作用**（S4-1）：独立验证仅 import 两个验证脚本（不调 `main()`）→ 无新增临时目录、无环境变化、未导入产品 `main`、未设置 `RESUME_DATA_DIR`。
- **取得即登记 / 清理独立可核对**：`_v2_test_runner.py` 的 `_RuntimeState` 保存 tmp / 原环境 / engine / client；`_cleanup()` 依次 dispose → close client → rmtree（且显式核对 `exists()`，防“无异常但未删除”）→ 恢复环境，前一步失败不阻止后一步。
- **唯一退出码仲裁**（S4-2）：`run_isolated` 归并业务返回 / 普通异常 / `SystemExit`（`_systemexit_code` 归一）/ `KeyboardInterrupt`(130) / cleanup 结果，最后仅一次 `sys.exit`；cleanup 失败且原结果为 0 时强制置 1。
- **真实 runtime 不可触碰 / 边界声明**：环境在导入产品模块前由 `_setup` 覆盖，退出时 `_restore_env` 恢复；注释明确 `os._exit` 等不属于本契约。

#### 进程级复验（新工作树独立执行）

| 项 | 结果 |
|---|---|
| 直跑 `python _v20_smoke.py` | **20 PASS / 0 FAIL，exit 0**，无新增 `ra_v20_smoke_*` 残留 |
| 直跑 `python _v2_t5_crud_check.py` | **15 PASS / 0 FAIL，exit 0**，无新增 `ra_v2_t5_*` 残留 |
| 生命周期矩阵 `python _v2_lifecycle_matrix.py` | **50 / 0**（bootstrap 失败 / 部分资源 / SystemExit 组合 / cleanup 单项与组合失败 / 重复 cleanup / 句柄占用，独立子进程断言退出码 + 后置条件） |
| 独立定向探针（仓库外，不依赖矩阵代码） | **8/8**：调用前环境变量存在/不存在均能恢复；`SystemExit(0)` 正常清理返回 0；叠加 rmtree 或 client close 失败后最终非零；engine 与 client 同时失败仍继续删目录并恢复环境；rmtree 无操作和环境恢复 `pop` 失败均被后置条件捕获 |
| 真实 runtime | 两条原始命令运行前后目录修改时间完全一致，未触碰真实用户数据 |
| 业务回归 | V1.5.0 八组独立复跑 **309/0**（35+54+53+40+24+18+48+37）；第四轮已通过的 T9 定向探针 13/13 继续有效，本轮精确 diff 仅含四个验证基础设施文件与 PLAN/RESULT |

#### 便携包未变证明

- `ResumeAssistant.exe`：15,878,373 字节，SHA-256 `d3adc37348bddda11dd5a0e03bc9c61938fe8e61d52b7e7491a7331f35ccea44` —— 与第四轮一致（候选身份变化后未重打，符合 §11.4 对“测试基础设施变更、打包输入未变”的可执行清单要求）。
- `packaging/resume_assistant.spec` 与全仓库扫描：`_v20_smoke` / `_v2_t5_crud_check` / `_v2_test_runner` / `_v2_lifecycle_matrix` 均未被 spec、打包配置或产品模块引用（仅两个验证脚本自身引用 runner）。

#### 最终结论

- **S4-1 / S4-2 完成标准全部满足；T9 独立源码验收：通过；功能验收通过；结构变更验收通过；阻断项 0。**
- 绑定精确候选：`d7a8c1bfc83f8244ce123e8c9d30c48418143e9e`（源码返工 `7795ec6…`）；验收后未修改候选源码、测试或构建配置。
- 剩余事项：T10 人工产品验收（干净 Windows 双击启动、Chrome/Edge 三页主流程、真实 ARK_API_KEY 连接、退出资源释放、长路径目录）→ T11 文档收口与发布。
- 非阻断环境项：本机 Windows 凭据库残留 1 字符测试 Key（`ResumeAssistant.ark_api_key`）与 `Temp` 下既有 `ra_v20_smoke_lucyzerw` / `ra_v2_t5_av1u8tjs` 残留（均为修复前遗留），建议人工清理。

## 11. 人工验收反馈 / 文档验收

- 人工阶段性反馈（2026-08-25）：用户确认 V2.0.0 已实现“把原有功能做成图形化交互”的首版目标；现有页面与预期交互流程仍有差异，后续将重新设计具体页面。该反馈确认产品方向，不替代最终候选上的 T9 独立源码验收及 §8.3 人工矩阵。
- 人工验收（T10）：T9 第五轮已通过（§10.12）；正式人工产品验收待开展。
- 文档验收（T11）：当前仅完成独立性规则与状态纠偏；正式收口待 T9、T10 和最终候选一致后开展。

## 12. 建议写入全局文档的已验证事实

> 下列内容仅为开发侧候选事实。待最终 clean candidate 的 T9、T10 均通过后，才由文档 Agent（T11）统一核验并回填 `CURRENT_STATE`/`README`/`DECISIONS`/索引。

开发侧可交接的候选事实（供 T9 复核、T11 收口）：

- V2.0.0 版本元数据 `APP_VERSION=2.0.0`（`core/version.py`），`/api/health` 返回 2.0.0。
- 新增连接配置（`/api/config`）、系统维护（`/api/system`）薄 API，均包装与 `manage.py` 相同 service。
- Windows 便携版长期 API Key 进入 Credential Manager；非密钥配置进入 runtime 版本化配置；单一 resolver 与来源显示。
- 写操作安全边界（loopback Host / Origin / 启动会话 Cookie）与生成/迁移/重建/重试并发门禁（409 拒绝）。
- 前端 React+TS+Vite 三页 + 同源托管 + 强类型 client；onedir 便携包（`packaging/`）。
