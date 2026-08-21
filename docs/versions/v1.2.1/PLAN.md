# AI Career Resume Assistant V1.2.1 技术方案

> 文档角色：V1.2.1 历史执行计划  
> 状态：已实施；实际结果见 [RESULT.md](./RESULT.md)  
> 基线：[V1.2.0 RESULT](../v1.2.0/RESULT.md)
> 经验阅读：本版本以“业务行为不变”为约束，实施中实际追加了 T8 Chroma 专项  
> 当前全局上下文：[项目总览](../../README.md) · [决策记录](../../DECISIONS.md)；本文本身保留 V1.2.1 当时语境

> 版本：V1.2.1
> 版本定位：历史遗留清理版
> 更新日期：2026-08-15
> 前序版本：V1.2.0 / V1.2.0（PDF 布局复刻完成，验收通过）
> 当时后续设想：V1.3.0（功能演进版，含 GitHub 发布计划）；该设想后来被当前 V1.3.0 核心链路收口计划替代

---

## 0. 版本定位与必读说明

### 0.1 本版本是什么，不是什么

**是**：
- V1.2.0.x 分支上的**代码质量与可维护性修复版本**
- 不引入任何新功能、不改动业务行为、不破坏 API 契约
- 为后续 V1.3.0（功能演进 + 开源发布）扫清代码层面的历史包袱

**不是**：
- ❌ 不是 V2（不做多用户、不做新模板语法、不做 Chroma 升级）
- ❌ 不碰 Embedding / LangChain 相关链路（纯向量模型不可用 + LangChain 与豆包接口不兼容，两条问题已明确接受现状，**不在 V1.2.0.x 范围内修复**）
- ❌ 不做任何功能体验优化（技能匹配分偏低、JD 分析超时等性能/质量问题，留到 V2）

### 0.2 不修复清单（避免范围蔓延）

以下问题在 V1.0.0/V1.1.0 验收报告中已标记为 "⚠️ 暂缓"，在 V1.2.1 中**依然不修**，留待 V2：

| # | 问题 | 推迟原因 |
|---|------|---------|
| ~~1~~ | ~~Chroma → numpy 回退未切回~~ | ✅ **V1.2.1 已处理**：Chroma 后端已正常初始化（BACKEND=chroma），并修复了初始化时 `os.makedirs` 在 `try/except` 之外导致崩溃时无法回退 numpy 的隐患；同时已确认 `.gitignore` 覆盖全部 Chroma 持久化产物（chroma.sqlite3、UUID 目录下的 *.bin、vectors.json）。「未切回」描述已与实际状态不符，实际 numpy 回退仅在 Chroma 真不可用时触发（环境保护路径）。 |
| 2 | Embedding 模型 vision-251215 非文本专用 | 用户明确：纯向量模型不能用 |
| 3 | LangChain 封装 vs 原生 urllib HTTP | 用户明确：LangChain 不兼容豆包 |
| 4 | AI 依赖锁死在 langchain 0.3 / openai 1.x | 同上 |
| 5 | Prompt 模板 few-shot JSON 示例未加回 | 性能 > 质量的权衡已接受 |
| 6 | 多用户隔离（DEFAULT_USER_ID = "demo-user"）| V2 功能 |
| 7 | 三层防护中 Structured Output 第一层有效性未验证 | 留到 AI 依赖升级时一并验证 |
| 8 | 技能匹配分最高仅 5%（区分度不足）| V2 改进 |
| 9 | 模板 JSON 扩展语法（layout_rules / join / skip_if_empty）| V2 渐进加入 |
| 10 | JD 分析 / 简历生成响应略超时 | V2 调优 |

### 0.3 版本线（明确版本边界）

```
V1.0.0 → V1.1.0 → V1.2.0 → V1.2.1（历史遗留清理）→ V1.3.0（功能演进 + 开源发布）→ V2.0（架构升级）
```

- V1.0.0：初始功能版本
- V1.1.0：迭代修复
- V1.2.0 / V1.2.0：PDF 布局复刻完成，验收通过（本版本前序）
- V1.2.1：历史遗留清理版（本版本，纯代码清理，不改业务行为）
- V1.3.0：功能演进版（能力扩展 + GitHub 发布准备）
- V2.0：功能演进（多用户、新模板语法、AI 链路重构等）

> 版本边界说明：本版本严格限定为 V1.2.1，不与 V1.3.0 的 Git 历史清理工作混淆。V1.2.1 只动源码与配置文件，不执行任何 `git filter-branch` / `git rm --cached`。

### 0.4 修复清单（最终实际为 8 个 Task，T8 在实施中追加）

从之前的遗留问题报告中，筛选出**不涉及功能变更、可安全清理、与开源发布强相关**的条目，按优先级分层：

**P0：安全与可发布性**

| Task ID | 问题 | 风险等级 | 是否触达业务 API |
|---------|------|---------|----------------|
| T1 | `fill_user_data.py` 硬编码真实用户 PII（真实用户（已脱敏）） | 高 | 否（仅脚本） |
| T2 | `.gitignore` 覆盖不全 + 根目录为 Node.js 模板（原 T2 + T9 合并） | 高 | 否（仅 Git） |
| T3 | `requirements.txt` 非 AI 栈依赖未钉版本 | 高 | 间接（环境可重现性） |

**P1：API 正确性**

| Task ID | 问题 | 风险等级 | 是否触达业务 API |
|---------|------|---------|----------------|
| T4 | `/template/generate-docx` 响应体 `download_url` 指向 `/api/file/download`，实际路由是 `/api/template/download`（404 Bug） | 中 | 是（辅助字段） |

**P2：代码卫生**

| Task ID | 问题 | 风险等级 | 是否触达业务 API |
|---------|------|---------|----------------|
| T5 | `docx_writer.py` 4 个死代码函数 + 未使用 OxmlElement import | 中 | 否 |
| T6 | `template_schema.py` 3 个无调用方的旧路线类（StyleInfo / TemplateSection / TemplateSchema） | 中 | 否 |
| T7 | 杂项清理：`template.py` 未使用 import + 常量 / `resume_document.py` 兼容方法 / `template_renderer.py` 未使用变量（原 T7 + T8 合并） | 低 | 否 |

**P2+：鲁棒性修复（Chroma 专项）**

| Task ID | 问题 | 风险等级 | 是否触达业务 API |
|---------|------|---------|----------------|
| T8 | `chroma_store.py` 初始化隐患：`os.makedirs(CHROMA_PATH)` 在 try/except 之外，目录权限异常时模块加载直接崩溃，无法触发 numpy 回退 | 中 | 间接（模块 import 失败会使 experience / RAG 整条链路不可用） |

> 注：以下两项未列入本版本：① `template.py` 中两个 deprecated 接口（返回 410）仍保留（等 V2 时统一删，避免在清理版里引入路由变化）；② `pm_template.json` 中的「含冒号自动加粗」描述错误（涉及模板资产描述，与后续模板重建一起改）。

---

## 1. Baseline 建立与回归对比方法（修改前必做）

**目的**：在 V1.2.1 任何代码修改之前，必须先建立可对比的 Baseline，形成完整的「业务行为不变证明」。每个 Task 修改后再执行一次，对比 Baseline → Modification → Regression，确保核心业务行为一致。

### 1.1 Baseline 采集步骤

在未做任何 V1.2.1 修改的干净工作区上执行：

1. **E2E 运行**：
   ```
   python backend/_e2e_v12_p0.py
   ```

2. **记录以下 Baseline 数据**（写入 `docs/baseline-v1.2.1.md`）：
   - 退出码（exit code）
   - 生成的文件列表（含路径、大小）
   - 诊断报告内容（`backend/output/诊断报告_e2e_v12_p0.txt`）
   - 关键接口响应（generate-docx 接口的请求/响应 body、download_url 字段值）
   - 运行耗时（可选）

3. **Baseline 文件归档**：把 Baseline 运行生成的 docx 与诊断报告 txt 拷贝到 `docs/baseline/` 下，作为后续对比的基准快照。

### 1.2 修改后回归对比

每个 Task 组完成后，执行同样的 E2E 脚本，记录 Modification 数据，与 Baseline 逐项对比：

| 对比项 | 通过标准 |
|--------|---------|
| exit code | 与 Baseline 一致（应为 0） |
| 生成文件路径与扩展名 | 一致（文件名按 T1 调整为 `resume_user_mock.docx`） |
| 诊断报告关键指标 | 业务字段一致（条目数、bullet 数等不丢） |
| download_url 前缀 | T4 修改后预期变为 `/api/template/download`（其他 Task 不应变化） |
| 关键接口响应结构 | 字段集合不变 |

### 1.3 回归执行节点

```
Baseline（修改前）→ T1-T3 → 回归对比 → T4 → 回归对比 → T5-T7 → 最终回归对比 → V1.2.1 PASS
```

任何一轮回归与 Baseline 不一致（除预期变化外），暂停后续 Task，先排查根因。

---

## 2. 任务详细设计

> 所有 Task 统一采用 Agent 执行契约格式。执行前请先完成 §1 Baseline 建立。

### T1：移除 fill_user_data.py 的真实 PII

**目标**：清理源码中硬编码的真实用户 PII，产物文件名改为 mock 命名，并完成三层 PII 扫描确认零泄漏。

**允许修改**：
- `backend/fill_user_data.py`
- `backend/_e2e_v12_p0.py`（仅同步 mock 文件名依赖，不改业务逻辑）

**禁止修改**：
- 任何业务 API 路由代码
- docx 渲染逻辑（docx_writer.py / template_renderer.py 等）
- 数据结构定义（Pydantic 模型字段不变）

**前置条件**：§1 Baseline 已建立并归档。

**执行动作**：
1. 注释中明确说明「本脚本仅供本地验收使用，不包含真实 PII」。
2. Profile 数据改为完全虚构的 mock 数据（虚构姓名、手机号、邮箱、学校、公司、项目经历），不出现任何真实机构名。结构（字段数 / 字段名）与原数据保持一致，仅替换具体值。
3. Education / Work / Project 改为虚构公司（如「示例科技有限公司」「ABC 大学」），保留 bullet 数量与结构。
4. 产物文件名从 `resume_user_real_user（已脱敏）.docx` 改为 `resume_user_mock.docx`（在 `fill_user_data.py` 的输出路径处修改）。
5. 同步修改 `_e2e_v12_p0.py` 中对该路径的依赖引用，保持 E2E 链路可运行。
6. 不采用「真实数据移到 gitignore 的本地 JSON」方案。理由：推送 GitHub 时，PII 绝不应以「只要 ignore 就安全」的方式存在，因为 gitignore 只防未来提交，**已入库的历史 commit 依然泄漏**，所以必须源码中就不出现。

**验收条件**：
- **Level 1 源码扫描**：`backend/` 目录全文本 grep 手机号 `真实手机号（已脱敏）`、邮箱域名 `真实邮箱域名（已脱敏）`（特指真实用户（已脱敏）邮箱）、真实姓名「真实用户（已脱敏）」、真实学校「真实学校（已脱敏）」、真实公司「真实公司A（已脱敏）」「真实公司B（已脱敏）」 → **0 命中**。
- **Level 2 运行产物扫描**：`backend/output/` 下生成的 `resume_user_mock.docx` 与诊断报告 txt 中，grep 上述真实 PII 关键字 → **0 命中**（docx 用 unzip + 文本提取后扫描）。
- **Level 3 Git tracked files 扫描**：`git grep` 在已追踪文件中搜索上述真实 PII 关键字 → **0 命中**。
- `python backend/fill_user_data.py` 依然成功生成 `backend/output/resume_user_mock.docx`。
- `_e2e_v12_p0.py` 运行不受影响（白晓的数据是虚构样例，不需要改）。

**回归条件**：执行 §1 回归对比，生成的 docx 路径与 Baseline 仅文件名不同（`resume_user_mock.docx` vs 原 `resume_user_real_user（已脱敏）.docx`），诊断报告关键业务指标一致。

**失败处理**：mock 数据结构与真实数据结构不对齐导致渲染报错 → 回到 fill_user_data.py 检查字段数/字段名是否完整对齐；不要为了绕过而修改业务渲染代码。

**回滚方式**：`git revert <T1 commit>`，fill_user_data.py 与 _e2e_v12_p0.py 单 commit 回滚。

**影响面**：`backend/fill_user_data.py`、`backend/_e2e_v12_p0.py`。

---

### T2：重构并补全 Git 忽略规则（原 T2 + T9 合并）

**目标**：根目录 `.gitignore` 从 Node.js 模板重写为 Python 项目模板，`backend/.gitignore` 精简，补全 runtime output / DB / env / docx template / IDE / cache 等忽略规则。

**允许修改**：
- `.gitignore`（根目录）
- `backend/.gitignore`

**禁止修改**：
- 任何已入库的源码文件
- `backend/templates/_build_templates.py`（必须通过 `!` 排除规则保留追踪）
- `backend/.env.example`（必须通过 `!.env.example` 保留追踪）

**前置条件**：§1 Baseline 已建立。

**执行动作**：
1. 根目录 `.gitignore` 完全重写为 Python 项目模板（删除原 Node.js 条目 `node_modules/`、`.next/`、`coverage/` 等）。
2. `backend/.gitignore` 精简，避免与根目录重复（根目录已覆盖 `data/`、`output/`）。
3. 补全以下规则类别：
   - **Python**：`__pycache__/`、`*.py[cod]`、`*.egg-info/`、`.pytest_cache/`、`.mypy_cache/`、`.ruff_cache/`
   - **Virtual Envs**：`.venv/`、`venv/`、`env/`、`ENV/`
   - **IDE**：`.vscode/`、`.idea/`、`*.swp`、`*.swo`、`*~`
   - **OS**：`.DS_Store`、`Thumbs.db`、`*.log`
   - **Secrets**：`.env`、`.env.local`、`.env.*`、`!.env.example`
   - **Runtime output**：`backend/output/`
   - **DB**：`*.db`、`*.db-journal`、`*.db-wal`、`*.db-shm`、`*.sqlite`、`*.sqlite3`、`vectors.json`
   - **docx template**：`backend/templates/*.docx`、`!backend/templates/_build_templates.py`
4. 推荐根目录 `.gitignore` 内容：
   ```
   # ===== Python =====
   __pycache__/
   *.py[cod]
   *$py.class
   *.so
   *.egg-info/
   *.egg
   .eggs/
   dist/
   build/
   *.whl
   .pytest_cache/
   .mypy_cache/
   .ruff_cache/
   .tox/
   *.manifest
   *.spec

   # ===== Virtual Envs =====
   .venv/
   venv/
   env/
   ENV/

   # ===== IDE =====
   .vscode/
   .idea/
   *.swp
   *.swo
   *~

   # ===== OS =====
   .DS_Store
   Thumbs.db
   *.log

   # ===== Secrets =====
   .env
   .env.local
   .env.*
   !.env.example

   # ===== Runtime Data / Build Output =====
   data/
   *.db
   *.db-journal
   *.db-wal
   *.db-shm
   *.sqlite
   *.sqlite3
   vectors.json
   backend/output/
   backend/templates/*.docx
   !backend/templates/_build_templates.py
   ```
5. **已入库但应忽略文件的清理**：`.gitignore` 生效后，对已入库的构建产物执行 `git rm --cached`（保留本地文件，仅从索引移除）：
   - `backend/output/resume_e2e_pm_template.docx`
   - `backend/output/resume_user_mock.docx`（T1 改名后）
   - `backend/output/诊断报告_e2e_v12_p0.txt`
   - `backend/output/验收报告_用户数据填充.txt`
   - `backend/templates/pm_template.docx`（`_build_templates.py` 的构建产物）

> 注：T2 的「已入库文件 git rm --cached」+ Git 历史清理步骤，具体执行放在 **V1.3.0**（因为需要配合 `git filter-branch` 一起做，见后续 V1.3.0 方案），V1.2.1 只写 `.gitignore` 文件本身。

**验收条件**：
- 根目录 `.gitignore` 不再出现 `node_modules/`、`.next/`、`coverage/` 等 Node.js 条目。
- `.gitignore` 中明确包含：`__pycache__/`、`.venv/`、`*.db-journal`、`.env.*`、`!.env.example`、`backend/output/`、`backend/templates/*.docx`、`!backend/templates/_build_templates.py` 等条目。
- `git check-ignore -v backend/output/resume_e2e_pm_template.docx` → 命中 ignore 规则。
- `git check-ignore -v backend/templates/pm_template.docx` → 命中 ignore 规则。
- `git check-ignore -v .env.prod` → 命中 ignore 规则。
- `git check-ignore -v backend/.env.example` → **不命中**（`!.env.example` 生效）。
- `git check-ignore -v backend/templates/_build_templates.py` → **不命中**（`!` 排除规则生效）。

**回归条件**：`.gitignore` 仅影响 Git 索引，不影响 E2E 运行；执行 §1 回归对比，业务行为应与 Baseline 完全一致。

**失败处理**：`!` 排除规则失效（如 `_build_templates.py` 被误忽略）→ 检查 `.gitignore` 中规则顺序，`!` 否定规则必须在对应通配规则之后。

**回滚方式**：`git revert <T2 commit>`，两个 `.gitignore` 文件单 commit 回滚。

**影响面**：`.gitignore`（根目录）、`backend/.gitignore`。

---

### T3：锁定 requirements.txt 已验证环境版本（环境事实优先策略）

**目标**：先获取 V1.2.0 已验收环境的真实版本（pip freeze / pip list），锁定当前已验证版本，确保环境可重现。V1.2.1 不做依赖升级策略设计，V2 再做依赖升级。

**允许修改**：
- `backend/requirements.txt`

**禁止修改**：
- 任何源码文件（不为了适配版本而改业务代码）
- AI 栈依赖版本范围（langchain / langchain-core / langchain-openai / openai / httpx / python-docx 等已正确钉版的原样保留）

**前置条件**：
- §1 Baseline 已建立。
- V1.2.0 已验收环境的 Python 解释器与依赖可访问（可在该环境执行 `pip freeze` / `pip list`）。

**执行动作**：
1. **环境事实优先**：在 V1.2.0 已验收通过的环境中执行 `pip freeze`（或 `pip list --format=freeze`），导出当前已验证可用的真实版本。
2. **不做「按代码 API 特征反推最低兼容版本」**：以环境实际安装版本为准，不设计依赖升级策略，不反推版本下限。
3. **锁定当前已验证版本**：对非 AI 栈依赖（`pydantic` / `fastapi` / `sqlalchemy` / `chromadb` / `pdfplumber` / `numpy` / `python-dotenv` / `uvicorn` 等）按环境实际版本钉版（使用 `==<实际版本>` 精确钉版，或保守的 `>=实际版本,<下一个major` 范围，优先 `==` 精确钉版以保证可重现）。
4. 已有约束的 AI 栈条目（langchain / langchain-core / langchain-openai / openai / httpx / python-docx）**原样保留，不改动版本范围**。
5. 在 `requirements.txt` 中以注释说明每条约束的来源（如 `# pydantic: 锁定 V1.2.0 验证环境实际版本`、`# 不在 V1.2.1 做升级，留待 V2`）。
6. **不引入**依赖升级设计文档、不写「建议升级到 pydantic 2.x」之类的迁移说明（这是 V2 的工作）。

> 策略说明：V1.2.1 的目标是「确定并锁定已验证环境版本」，让推 GitHub 后任何人在干净 venv 中 `pip install -r requirements.txt` 都能复现 V1.2.0 的运行环境。依赖升级与版本演进统一在 V2 处理。

**验收条件**：
- `backend/requirements.txt` 中每条依赖都显式带版本约束，无裸 `pydantic`、裸 `fastapi` 等无版本条目。
- `pip install -r backend/requirements.txt` 在**干净 venv**（新建空虚拟环境）中安装成功，无版本冲突报错。
- 干净 venv 安装完成后，执行 `python backend/_e2e_v12_p0.py` → E2E PASS。
- AI 栈原钉版条目未被改动（diff 验证）。

**回归条件**：干净 venv 安装 + E2E 通过即视为回归通过；与 §1 Baseline 对比业务行为一致。

**失败处理**：
- 干净 venv 安装失败（版本冲突）→ 回到 V1.2.0 验证环境，再次确认 `pip freeze` 输出，修正钉版条目；不要为了通过安装而放宽到无版本约束。
- 某依赖在干净 venv 中实际安装版本与 V1.2.0 环境不一致（如 PyPI 已无该版本）→ 记录差异，寻找最接近的可用版本钉版，并在注释中说明。

**回滚方式**：`git revert <T3 commit>`，`requirements.txt` 单文件回滚。

**影响面**：`backend/requirements.txt`。

---

### T4：修复 generate-docx 响应体中 download_url 路径错误（含真实 HTTP smoke test）

**目标**：统一 `download_url` 到实际路由 `/api/template/download`，并通过真实 HTTP smoke test 验证下载链路端到端可用。

**允许修改**：
- `backend/api/routes/template.py`（顶部注释 + download_url 拼接字符串）
- 可新增 `backend/_smoke_download_url.py`（仅当 E2E 未覆盖该链路时）

**禁止修改**：
- router prefix 挂载位置（保持 `/api/template`）
- 不新增 `/api/file` 路由（清理版最小改动原则）
- generate-docx 接口的请求/响应数据结构（只改 download_url 字段值）

**前置条件**：§1 Baseline 已建立；T1-T3 已完成并通过回归（P0 优先）。

**执行动作**：
1. 更正 `template.py` 顶部注释（第 7 行附近）`GET /api/file/download` → `GET /api/template/download`。
2. 更正 `download_url` 拼接字符串，把 `/api/file/download` → `/api/template/download`。
3. 不单独创建 `/api/file` 路由。
4. **真实 HTTP smoke test**（必做，不走代码静态检查 + 代码搜索交叉验证）：
   - 启动服务：`uvicorn main:app --app-dir backend --port 8000`
   - `POST /api/template/generate-docx`（最小入参）→ 拿到响应 body 中的 `download_url`
   - `GET <download_url>` → 必须返回 **HTTP 200**
   - 校验响应 `Content-Type` 正确（应为 docx 对应的 MIME，如 `application/vnd.openxmlformats-officedocument.wordprocessingml.document`）
   - 校验文件确实存在（响应 body 非空，且本地 `backend/output/` 下对应 docx 文件存在）
5. 如果 `_e2e_v12_p0.py` 已覆盖此「POST generate-docx → GET download_url → 文件存在」链路，则该 smoke test 作为 E2E 回归的一部分，无需单独加最小测试；否则在 `backend/` 下补一个最小 smoke test 脚本（如 `_smoke_download_url.py`）覆盖该链路。

**验收条件**：
- 代码全文 grep `/api/file/download` → **0 命中**。
- `template.py` 顶部注释 `GET /api/template/download` 与 main.py 的 router prefix 一致。
- `download_url` 生成值形如 `/api/template/download?path=backend%2Foutput%2Fresume_xxx.docx`。
- **真实 HTTP smoke test 通过**：POST generate-docx → 拿到 download_url → GET download_url → HTTP 200 → Content-Type 正确 → 文件存在。
- 若新增 smoke test 脚本，脚本退出码 0 且输出包含明确通过标识。

**回归条件**：执行 §1 回归对比，download_url 前缀预期从 `/api/file/download` 变为 `/api/template/download`（这是 T4 的预期变化）；其他业务行为与 Baseline 一致。

**失败处理**：
- GET download_url 返回 404 → 检查 router prefix 与拼接路径是否一致，检查 main.py 的 router include 路径。
- GET 返回非 200 → 检查文件是否实际生成（fill_user_data / docx_writer 链路是否正常）。
- Content-Type 不正确 → 检查 FileResponse 的 media_type 参数。

**回滚方式**：`git revert <T4 commit>`，`template.py` 单文件回滚（若新增了 smoke test 脚本，一并回滚）。

**影响面**：`backend/api/routes/template.py`（可能新增 `backend/_smoke_download_url.py`）。

---

### T5：清理 docx_writer.py 死代码（四层验证）

**目标**：删除 docx_writer.py 中 4 个死代码函数 + 1 个未使用 import，删除前通过四层验证确认无调用方。

**允许修改**：
- `backend/services/docx_writer.py`

**禁止修改**：
- docx_writer.py 的活跃代码（load_template_assets / _docx_clone_fill / TemplateDocxWrapper 等）
- 任何业务渲染逻辑

**前置条件**：§1 Baseline 已建立；T1-T4 已完成并通过回归。

**执行动作**：
1. **四层验证（删除前必做，不能只用 grep）**：
   - ① **全仓库文本搜索（grep）**：对以下符号执行 `grep -rn`：
     - `estimate_page_count`
     - `apply_keyword_bold`
     - `_r_set_text`
     - `_r_set_bold`
     - `OxmlElement`（在 docx_writer.py 中的引用）
     - 范围：全仓库（含 `backend/`、`docs/`、根目录脚本）
   - ② **import 搜索**：grep `from services.docx_writer import` / `import docx_writer`，列出所有引用方，逐一确认这些引用方不引用待删除符号。
   - ③ **IDE / 静态分析**：执行 `pyflakes backend/services/docx_writer.py`（或 `ruff check` / `mypy`），确认待删除符号被识别为 unused。
   - ④ **E2E 回归**：执行 `python backend/_e2e_v12_p0.py`，确认 E2E PASS（证明删除后业务行为不变）。
2. 四层验证全部通过后，删除以下 4 个函数体：
   - `estimate_page_count()`（L181 附近）—— layout_optimizer.py 自带同名功能，重复实现
   - `apply_keyword_bold()`（L202 附近）—— V1.2.0 明确取消关键词加粗功能
   - `_r_set_text()`（L256 附近）—— 仅被死代码 apply_keyword_bold 调用
   - `_r_set_bold()`（L268 附近）—— 同上
3. 删除文件顶部 `from docx.oxml import OxmlElement` 这行 import。
4. 保留 docx_writer.py 的其他活跃代码。

**验收条件**：
- 四层验证记录齐全（① grep 结果、② import 引用方列表、③ 静态分析输出、④ E2E 通过证明）写入 [RESULT.md](./RESULT.md)。
- 删除后 docx_writer.py 顶部 import 中不再出现 `OxmlElement`。
- 全文 grep `estimate_page_count\|apply_keyword_bold\|_r_set_text\|_r_set_bold` → **0 命中**（允许在 layout_optimizer.py 的 `estimate_pages` 同名不同函数保留，需在验收报告中明确区分）。
- `_e2e_v12_p0.py`、`fill_user_data.py`、`generate-docx` 接口三个调用 docx_writer 的路径都**不引用被删除函数**（通过 ② import 搜索 + ③ 静态分析交叉验证）。

**回归条件**：执行 §1 回归对比，业务行为与 Baseline 完全一致（死代码定义就是「0 调用方」，删除后业务行为不应变化）。

**失败处理**：四层验证中任一层发现调用方 → **暂停删除**，先确认调用方是否为有效业务路径；若确为有效调用方，则该符号不是死代码，从本 Task 移除，不删。

**回滚方式**：`git revert <T5 commit>`，docx_writer.py 单文件回滚。

**影响面**：`backend/services/docx_writer.py`。

---

### T6：清理 template_schema.py 旧路线死类（全仓库 0 命中，含注释）

**目标**：删除 template_schema.py 中 3 个无调用方的旧路线类，确保全仓库 0 命中（含注释，不允许历史注释里继续出现这些类名）。

**允许修改**：
- `backend/models/template_schema.py`

**禁止修改**：
- `SECTION_TYPES` 常量（被新路线 `SectionSpec._validate_type` 引用，保留不删）
- `TemplateSpec` / `SectionSpec` / `RowSpec` / `CellSpec` / `LayoutSpec` 等新路线类

**前置条件**：§1 Baseline 已建立；T1-T5 已完成并通过回归。

**执行动作**：
1. **四层验证（同 T5）**：对 `StyleInfo`、`TemplateSection`、`TemplateSchema` 三个类名执行 ① grep / ② import 搜索 / ③ 静态分析 / ④ E2E 回归，确认全仓库无调用方。
2. 删除 3 个旧类的类定义：
   - `StyleInfo`（L18-41 附近）
   - `TemplateSection`（L44-77 附近）
   - `TemplateSchema`（L93-98 附近）
3. `SECTION_TYPES` 常量（L80-90 附近）被新路线引用，**保留不删**，可上移到文件顶部 import 之下作为独立常量。
4. **清理历史注释**：删除文件顶部 docstring 中「保留兼容」的描述，以及代码中任何提到 `StyleInfo` / `TemplateSection` / `TemplateSchema` 的注释。
5. 文件顶部 docstring 改为：「V1.2.0 主用：TemplateSpec / SectionSpec / RowSpec / CellSpec / LayoutSpec；旧路线类已在 V1.2.1 清理」。
6. **如果需要记录历史**（如旧路线设计原因、迁移说明），放在 `docs/` 下的文档中，**不要放在代码文件注释里**。

**验收条件**：
- **全仓库 0 命中（含注释）**：`grep -rn "TemplateSection\|StyleInfo\|TemplateSchema" backend/` → **0 命中**（包括 template_schema.py 自身的历史注释也不允许出现这三个类名）。
- 删除后，template_schema.py 的有效代码从约 177 行精简到约 100 行。
- `from models.template_schema import TemplateSpec, SectionSpec, RowSpec, CellSpec, LayoutSpec` 的 import 在现有代码中仍然可用（grep 现有 import 语句验证是否只引用新类）。
- `SECTION_TYPES` 常量保留且被 `SectionSpec._validate_type` 正常引用（E2E 回归验证）。
- 历史记录若需要，已迁移到 `docs/` 下文档（不在代码文件中）。

**回归条件**：执行 §1 回归对比，业务行为与 Baseline 完全一致；四层验证记录齐全。

**失败处理**：
- 四层验证发现调用方 → 暂停删除，确认调用方有效性。
- 全仓库 grep 在注释中发现类名 → 清理注释；若注释在 `docs/` 文档中是合理的历史记录，可保留在 `docs/` 但代码文件中必须 0 命中。

**回滚方式**：`git revert <T6 commit>`，template_schema.py 单文件回滚。

**影响面**：`backend/models/template_schema.py`（可能新增 `docs/` 下历史记录文档）。

---

### T7：清理无效 import / 无调用兼容代码（原 T7 + T8 合并）

**目标**：合并清理三类无效代码：template.py 未使用 import + 常量、resume_document.py 兼容方法、template_renderer.py 未使用变量。

**允许修改**：
- `backend/api/routes/template.py`
- `backend/models/resume_document.py`
- `backend/services/template_renderer.py`

**禁止修改**：
- 任何业务逻辑（只删未使用代码，不改活跃代码行为）
- template.py 中两个 deprecated 接口（返回 410）保留（V2 统一删）

**前置条件**：§1 Baseline 已建立；T1-T6 已完成并通过回归。

**执行动作**：

**子任务 A：template.py 未使用 import + 常量**
1. 四层验证以下符号无引用：
   - L15 `import shutil`
   - L16 `import uuid`
   - L17 `from datetime import datetime`
   - L18 `from pathlib import Path`
   - L316 `_USER_ID = "default_user"`
2. 验证通过后删除 4 行 import + 1 个常量定义。
3. 保留活跃 import（`import json` / `import os` / `typing.Optional` 等）。

**子任务 B：resume_document.py 兼容方法**
1. 四层验证以下方法 0 外部调用方：
   - `selected_education(self) -> List[EducationItem]`（L193-199 附近）
   - `selected_work(self) -> List[WorkItem]`
   - `selected_projects(self) -> List[ProjectItem]`
2. 验证通过后删除这 3 个方法。

**子任务 C：template_renderer.py 未使用变量**
1. 四层验证以下变量赋值后未使用：
   - L244 附近：`row_spec, proto_p = block[0]`（`row_spec` 赋值后整个函数内未使用）
   - L291 附近：同上模式
2. 验证通过后改为 `_, proto_p = block[0]` 或 `proto_p = block[0][1]`（保持 Python 约定，下划线表示忽略）。

**验收条件**：
- **子任务 A**：template.py 删除后，`pyflakes` / `ruff` unused-import 检查不再对这 4 个 import 报警；grep `shutil\|uuid\|from datetime import datetime\|from pathlib import Path` 在 template.py 内 0 命中；`_USER_ID` 在 template.py 内 0 命中。
- **子任务 B**：grep `selected_education\|selected_work\|selected_projects` 全仓库 → **0 命中**（定义处已删除）。
- **子任务 C**：template_renderer.py 的 `_render_skills` / `_render_awards` 函数内不再出现 `row_spec` 变量名。
- 三类清理的四层验证记录齐全。

**回归条件**：执行 §1 回归对比，业务行为与 Baseline 完全一致。

**失败处理**：四层验证中任一层发现调用方 → 暂停对应子任务删除，确认调用方有效性；确为有效调用方则该子任务项不删。

**回滚方式**：`git revert <T7 commit>`，三个文件单 commit 回滚（子任务 A/B/C 合在一个 commit 也可，但 commit message 中分项说明）。

**影响面**：`backend/api/routes/template.py`、`backend/models/resume_document.py`、`backend/services/template_renderer.py`。

---

## 3. 任务执行顺序与依赖

```
执行顺序：
Baseline（修改前）→ T1-T3（P0）→ 回归对比 → T4（P1）→ 回归对比 → T5-T7（P2）→ 最终回归对比 → V1.2.1 PASS
```

**优先级分层**：

**P0：安全与可发布性**（必须先做，阻塞后续 GitHub 推送）
- T1：PII 清理
- T2：.gitignore 重构
- T3：requirements 锁定

**P1：API 正确性**（P0 完成后做）
- T4：download_url 修复

**P2：代码卫生**（P1 完成后做，可一次完成统一回归）
- T5：docx_writer 死代码
- T6：template_schema 旧类
- T7：杂项清理

**依赖关系**：
- T1-T3 之间无依赖，可并行（但建议按 T1→T2→T3 顺序，便于 PII 改名后再写 .gitignore 引用 mock 文件名）。
- T4 依赖 T1-T3 完成（P0 优先）。
- T5-T7 依赖 T1-T4 完成。
- 每个 Task 完成后执行 §1 回归对比。

**回归节点**：
1. Baseline 建立（修改前）
2. T1-T3 完成后回归
3. T4 完成后回归
4. T5-T7 完成后最终回归
5. V1.2.1 PASS

每完成一组，执行 §4 验收清单的对应项。

---

## 4. 验收方法与通过标准

### 4.1 静态检查（必做）

| 检查项 | 命令/方法 | 通过标准 |
|--------|----------|---------|
| PII 残留扫描（Level 1 源码） | `grep -rn "真实用户（已脱敏）\|真实手机号（已脱敏）\|真实邮箱域名（已脱敏）\|真实公司A（已脱敏）\|真实公司B（已脱敏）\|真实学校（已脱敏）" backend/` | 0 命中 |
| PII 残留扫描（Level 2 运行产物） | 解压 `backend/output/resume_user_mock.docx` 后 grep + grep 诊断报告 txt | 0 命中 |
| PII 残留扫描（Level 3 Git tracked） | `git grep "真实用户（已脱敏）\|真实手机号（已脱敏）\|真实邮箱域名（已脱敏）\|真实公司A（已脱敏）\|真实公司B（已脱敏）\|真实学校（已脱敏）"` | 0 命中 |
| 死代码删除确认（四层验证） | 对每类删除项执行 grep + import 搜索 + 静态分析 + E2E | 四层均 0 命中/无调用方 |
| template_schema 旧类全仓库 0 命中（含注释） | `grep -rn "TemplateSection\|StyleInfo\|TemplateSchema" backend/` | 0 命中（含注释） |
| download_url 一致性 | `grep -rn "api/file/download" backend/` | 0 命中；`grep -rn "api/template/download" backend/` 至少出现在注释 + URL 拼接两处 |
| requirements 钉版完整性 | 逐条检查 `backend/requirements.txt` | 每条都有版本约束，无裸 `pydantic`、裸 `fastapi` 等 |
| .gitignore 覆盖率 | `git check-ignore -v backend/output/a.docx backend/templates/b.docx .env.prod backend/app.db-journal` | 4 个路径全部命中 ignore 规则；`.env.example` 不命中 |

### 4.2 运行时回归（必做）

依赖安装完成后（至少完成 `pip install -r backend/requirements.txt`，建议在干净 venv 中验证），执行：
```
python backend/_e2e_v12_p0.py
```
通过标准：
- 脚本退出码 0
- 生成 1 个 docx（`resume_user_mock.docx`）+ 1 份诊断报告 txt（V1.2.0 的原有产物路径不变，只是不在 git 里追踪）
- 脚本输出最后一行 `✅ E2E PASSED` 或等价提示（按当前脚本行为）
- 与 §1 Baseline 对比，业务行为一致

若有单元测试或 pytest：执行 `pytest backend/ -x`（如无则跳过，本项目暂未引入测试框架）。

### 4.3 真实 HTTP smoke test（T4 必做）

```
uvicorn main:app --app-dir backend --port 8000
curl http://127.0.0.1:8000/ → 返回健康检查
curl -X POST http://127.0.0.1:8000/api/template/generate-docx ...（最小入参）→ 拿到 download_url
curl -X GET "<download_url>" → HTTP 200 + Content-Type 正确 + 文件存在
```

### 4.4 Baseline 对比验证（必做）

见 §1。每个回归节点产出 Baseline → Modification 对比表，证明业务行为不变。

### 4.5 最终交付物

本版本完成后应产出：
- 修改的源码文件（约 8-10 个：`fill_user_data.py` / `_e2e_v12_p0.py` / `.gitignore` / `backend/.gitignore` / `requirements.txt` / `template.py` / `docx_writer.py` / `template_schema.py` / `resume_document.py` / `template_renderer.py`；可能新增 `_smoke_download_url.py`）
- `docs/baseline-v1.2.1.md`：Baseline 数据归档
- `docs/baseline/`：Baseline 运行产物快照
- [RESULT.md](./RESULT.md)：验收报告，每 Task 一项，记录「通过 / 问题 / 解决」，含四层验证记录与 Baseline 对比表

---

## 5. 风险与回滚

| Task | 风险点 | 概率 | 影响 | 缓解措施 |
|------|-------|------|------|---------|
| Baseline | Baseline 采集不完整，后续无法对比 | 中 | 高（无法证明业务行为不变） | 严格按 §1.1 采集，归档到 `docs/baseline/` |
| T1 | mock 数据的结构与真实数据结构不完全对齐（如字段数/字段名），导致渲染流程报错 | 低 | 中（本地验收脚本失败） | 删除前先跑一次 _e2e_v12_p0.py 作为 baseline，改完再跑对比；保持字段结构对齐 |
| T2 | .gitignore 写得太宽，误把 `_build_templates.py` 也忽略了 | 极低 | 低 | 写 `!backend/templates/_build_templates.py` 排除规则；用 check-ignore 逐条验证 |
| T3 | 钉版后某依赖在干净 venv 中实际安装版本与 V1.2.0 环境不一致，或 PyPI 已无该版本 | 中 | 中（pip install 失败） | 以 V1.2.0 验证环境 `pip freeze` 为准；冲突时记录差异，寻找最接近可用版本；先在干净 venv 验证一次 |
| T4 | 前端如果硬编码了旧的 /api/file/download 路径（即使本来 404），沟通不到位会导致前端同学困惑；smoke test 服务起不来 | 低 | 低 | 验收报告中专门附一条「Breaking Note：download_url 前缀变更」；smoke test 失败时检查 uvicorn 启动日志 |
| T5-T7 | 删错了其实有调用方的代码 | 极低 | 低 | 四层验证（grep + import 搜索 + 静态分析 + E2E 回归）双重确认；保留 git commit 随时 revert |

**统一回滚策略**：所有改动合入时**每个 Task 一个 commit**（不要混在一个大 commit 里），出问题时精准 `git revert <commit-sha>` 单个 Task 即可，不影响其他修复。每个 Task 可独立回滚（见各 Task 的「回滚方式」字段）。

---

## 6. 当时计划的后续衔接（已被当前 V1.3.0 重新定义）

> 历史状态说明：以下内容是 V1.2.1 编写和验收时对下一版本的设想，当时准备把 V1.3.0 用于 Git 历史清理和 GitHub 发布。后续架构审核发现 JD 驱动 DOCX 主链路仍未闭环，用户重新明确 V1/V2/V3 边界，因此当前 V1.3.0 改为核心链路收口。原设想保留用于回顾和学习决策过程，但不再是当前开发指令。当前计划见 [../v1.3.0/PLAN.md](../v1.3.0/PLAN.md)。

V1.2.1 只是「代码层」清理，**不碰 Git 历史**。V1.3.0 将完成：
1. 对 T1 已清理的 PII，用 `git filter-branch`（或 BFG Repo-Cleaner）把 Git 历史中的 PII 一并抹除
2. 对 T2 新 ignore 规则覆盖的已入库文件（output/ 下 4 个文件 + pm_template.docx），执行 `git rm --cached` 并重新提交
3. 最终 GitHub 上传前的项目结构审计、许可证文件、README（如果要）、Contributor Guide 等
4. GitHub 推送三步确认：remote / branch / 首次 commit 顺序

引用更新说明（相对原方案）：
- 原 T2 + T9 → 合并为 V1.2.1 的 T2（.gitignore 重构）
- 原 T7 + T8 → 合并为 V1.2.1 的 T7（杂项清理）

因此：
- V1.2.1 完成并合入后，**不要立即推到公开仓库**
- 先跑 V1.3.0 的 Git 历史清理流程，再做最终推送

---

## 7. 最终质量门（V1.2.1 PASS 条件）

完成所有 Task 后，逐项核对以下质量门清单。全部勾选通过方可标记 V1.2.1 PASS：

```
V1.2.1 PASS
[ ] 版本边界正确（V1.2.1，前序 V1.2.0/V1.2.0，后续 V1.3.0）
[ ] Baseline 已建立（docs/baseline-v1.2.1.md + docs/baseline/ 快照）
[ ] PII 源码 = 0（Level 1）
[ ] PII 运行产物 = 0（Level 2）
[ ] PII Git tracked files = 0（Level 3）
[ ] .gitignore 正确（Node→Python 重构 + 覆盖率验证通过）
[ ] requirements 可安装（干净 venv）
[ ] download_url 真正可访问（HTTP 200）
[ ] 死代码无调用方（四层验证）
[ ] 无意外 API 变化
[ ] E2E PASS
[ ] 修改前后核心业务行为一致（Baseline 对比）
[ ] 每个 Task 可独立回滚
```

---

## 8. 结论

V1.2.1 是一次纯清理版本，**不改变任何用户可感知的功能**，核心收益：
- 消除了推上 GitHub 后最直接的两个高危风险：**PII 泄漏 + 构建环境不可重现**
- 修复了一个实际存在的 API 响应 Bug（download_url 404），并通过真实 HTTP smoke test 验证
- 删掉约 200+ 行死代码，降低后续维护的认知负担
- 通过 Baseline 对比验证形成「业务行为不变证明」
- 把后续 V2 开发时会被问「这 3 个旧类为什么存在」的对话成本提前消除

下一步：用户确认本方案后，按 §3 顺序进入开发，完成后执行 §4 验收并产出 [RESULT.md](./RESULT.md)。当时计划验收后进入 GitHub 发布准备；该计划后来被当前 V1.3.0 核心链路收口方案替代。
