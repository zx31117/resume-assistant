# V1.4 T6 — 源码树安全审计报告

> 审计范围：`worktree root` 下所有将进入「T8 干净首发仓库」的 A/B 类源码文件与文档；
> 审计原则：参考 V1.4 PLAN §6 的七道门（Secret / PII / 二进制与元数据 / 绝对路径 / 许可证 / 运行隔离 / 文件分级）。
> 审计结论：**第三轮复验通过。** 用户选择完整保留历史文档并脱敏；Secret 描述、历史本机路径、验收产物和脱敏脚本自身泄漏均已收口，公开候选内容无已知真实 Secret、PII 或本机绝对路径。

## 1. 扫描方法与范围

| 项 | 方法 |
|---|---|
| 密钥/Token / Private Key | Grep：`sk-*`、`ARK-*`、`api_key = "..."`、`AKIA*`、`-----BEGIN PRIVATE KEY-----` |
| PII / 联系方式 | Grep：1[3-9]\d{9} 手机号 / 17+1 身份证 / 邮箱正则 |
| 真实姓名/公司/学校 | 人工复核"疑似命中项"，区分 Demo 虚构 vs 真用户 |
| 绝对路径 / 盘符 | Grep：`C:\` / `D:\` / `E:\` / `\Users\` / `/Users/` / `/home/` |
| 二进制 / 非文本 | Glob：`*.docx / *.pdf / *.db / *.sqlite* / *.bin / *.png / ...` |
| 运行时隔离 | 用 V1.4 config 默认路径推导 + 代码 REVIEW（确保写入路径不进源码树） |
| 文件分级 | 对照 T1 A/B/C/D 分类表，逐项复核首发目录应包含/排除的文件 |

---

## 2. 审计结果逐门

### 2.1 Secret 扫描

| 命中 | 类型 | 风险 | 判定 | 处置 |
|---|---|---|---|---|
| `backend/.env:2` `ARK_API_KEY=ark-********` | 真实火山方舟 API Key（值已完全脱敏） | ⚠️ 高危（如果被提交） | `.env` 已在根 `.gitignore` 第 38 行忽略；文件仅本地磁盘存在，不会进首发仓库 | ✅ T8 首发仓库会**自动排除**（规则 + 白名单双保险） |
| `backend/.env.example` 等所有模板 | `<your-ark-api-key>` 占位符 | ✅ 安全 | 非真实密钥 | ✅ 无动作 |
| 其他文件（含 `config.py` / `services/*`）| 密钥参数只从 env 读取，代码内无硬编码 | ✅ 安全 | | ✅ 无动作 |

**T6-1 结论：无代码内 Secret 泄漏风险；`.env` 本地文件存在但 gitignore 已保护，不出首发仓库。**

### 2.2 PII 扫描（手机号 / 邮箱 / 姓名 / 真实 JD）

所有命中项逐一复核：

| 命中位置 | 内容 | 判定 | 理由 |
|---|---|---|---|
| `input/demo_profile.json` | `林示例 / 138****0000 / example.demo@example.com` | ✅ **虚构 Demo** | 星号遮罩 + example.com 邮箱 + 公司/学校均为虚构名 |
| `docs/versions/v1.3/PLAN.md` L103-L105 | `张示例 / 13800001111 / zhangshili@example.com` | ✅ **虚构演示** | 1380000 段经典测试号段 + example.com，张示例 是文档专用假姓名 |
| `backend/fill_user_data.py` L31-L33 / L205-L207 | 同上张示例 / 13800001111 / zhangshili@example.com | ✅ **虚构演示** | 脚本名即"fill_user_data"，纯初始化 mock 数据用 |
| `backend/_v13_stub_e2e.py` L44 | `张三 / 13800000001 / zhangsan@example.com / 深圳` | ✅ **虚构演示** | 打桩 E2E 专用 mock 数据，和真实个人无对应 |
| `backend/_e2e_v12_p0.py` L72-L75 | `白晓 / 13812345678 / baixiao@example.com` | ✅ **虚构演示** | V1.2 P0 测试专用人物，不指向真实个人 |

- **未扫描到任何：真实身份证号、真实手机号（非 0/星号测试号段）、真实个人邮箱、真实简历 PDF/真实 JD（input/ 下已移除）**。
- **已确认：旧 `input/模板.docx`、`input/简历.pdf`、`input/用户上传PDF.pdf`、`input/JD.txt` 均已从源码树删除，迁移到 runtime `RESUME_DATA_DIR/input/`，不进仓库**。

**T6-2 结论：源码树无真实 PII 泄漏；仅存 Demo 虚构人物/测试联系方式，符合开源仓库惯例。**

### 2.3 二进制 / 文档 / 元数据

Glob 扫描结果（仅列出 **不在 `.venv/` / `__pycache__/`** 的产物）：

| 文件 | 分类 | T6 结论 | T8 首发仓库是否保留 |
|---|---|---|---|
| `backend/templates/pm_template.docx` | **B 类：模板资产（公开）** | ✅ T4 已审无 PII / 无作者元数据（由 `_build_templates.py` 程序化生成的空白模板） | ✅ 保留 |
| `backend/data/app.db` | **C 类：旧 SQL 真源（保留回滚）** | ⚠️ 磁盘残留但不提交（根 `.gitignore` `*.db` / `data/`） | ❌ **排除**（T8 仅 A/B） |
| `backend/data/chroma/chroma.sqlite3 + *.bin` | **C 类：旧 Chroma 向量库** | ⚠️ 磁盘残留但不提交（`.gitignore` `data/`） | ❌ 排除 |
| `backend/output/resume_*_pm_template.docx` | **C 类：历史运行产物** | ⚠️ 磁盘残留但不提交（`.gitignore` `backend/output/`） | ❌ 排除 |
| 其他 `__pycache__/*.pyc`、`.venv/**`（大量 pyc/exe）| 构建环境 | ✅ `.gitignore` 保护 | ❌ 排除 |

**T6-3 结论：仅 1 份模板 DOCX 应保留，其余所有二进制/数据库/输出文件均已被 .gitignore 覆盖，且 T8 首发目录将只包含 A/B 类 + `.venv` 完全不克隆。**

### 2.4 绝对路径与盘符（硬编码位置）

所有命中（92 条）逐一分类：

| 类别 | 数量 | 代表示例 | T6 结论 |
|---|---|---|---|
| **文档中的历史环境路径**（V1.0–V1.3 RESULT 等） | 初轮有残留 | 已统一替换为 `<old-dev-root>` 等占位符 | ✅ 第三轮扫描无真实用户目录或旧开发盘符字面量；完整历史档案仍保留。 |
| **路径脱敏辅助脚本** `backend/_v14_c2c3_path_redact.py` | 第二轮含本机匹配字面量 | 数字用户名通配符 + 通用用户名兜底 | ✅ 第三轮确认脚本不含原用户名、原绝对路径或真实 key 前缀。 |
| README.md 的 `http://127.0.0.1:8000/docs` | 1 | 本地开发地址（不是文件系统绝对路径） | ✅ 正常 |
| `core/config.py` / `session.py` 中 `"sqlite:///{settings.SQLITE_PATH}"` | 2 | 字符串形参拼接，不是绝对路径字面量 | ✅ 正常 |
| 其他配置默认值：`https://ark.cn-beijing.volces.com/api/v3` | ≈ 10 | 第三方服务公共 URL（API 端点，非盘符路径） | ✅ 正常 |

**T6-4 结论：产品运行源码、公开文档和 D 类脱敏脚本均无已知本机绝对路径；完整历史档案通过占位符保留。**

### 2.5 第三方代码许可证合规

基于 `backend/requirements.txt` 的每个包的官方许可证声明（与 Glob 扫到的 `site-packages/*dist-info/licenses/LICENSE` 文件对应，均为 OSI 批准许可证，MIT/Apache-2.0/BSD 家族）：

| 包名 | 版本 | 许可证 | 允许闭源商业分发 | 是否与 MIT 兼容 |
|---|---|---|---|---|
| langchain | 0.3.30 | MIT | ✅ 是 | ✅ 是 |
| langchain-core / langchain-openai | 0.3.86 / 0.3.35 | MIT | ✅ 是 | ✅ 是 |
| openai | 1.109.1 | Apache-2.0 | ✅ 是 | ✅ 是 |
| httpx | 0.28.1 | BSD-3-Clause | ✅ 是 | ✅ 是 |
| fastapi | 0.141.1 | MIT | ✅ 是 | ✅ 是 |
| uvicorn[standard] | 0.52.3 | BSD-3-Clause | ✅ 是 | ✅ 是 |
| sqlalchemy | 2.0.52 | MIT | ✅ 是 | ✅ 是 |
| pydantic | 2.13.4 | MIT | ✅ 是 | ✅ 是 |
| python-multipart | 0.0.32 | Apache-2.0 | ✅ 是 | ✅ 是 |
| pdfplumber | 0.11.10 | MIT | ✅ 是 | ✅ 是 |
| chromadb | 1.5.9 | Apache-2.0 | ✅ 是 | ✅ 是 |
| numpy | 2.2.6 | BSD-3-Clause | ✅ 是 | ✅ 是 |
| python-dotenv | 1.2.2 | BSD-3-Clause | ✅ 是 | ✅ 是 |
| python-docx | 1.2.0 | MIT | ✅ 是 | ✅ 是 |

全部许可证都与项目的 **MIT License** 兼容，可组合后闭源商业分发，无 GPL/AGPL 传染性许可风险。

**T6-5 结论：开源许可证合规性 ✅ 通过。**

### 2.6 运行时隔离验证（代码级 REVIEW）

对照 V1.4 `core/config.py` + 所有 D 类脚本 + `template.py` 的写路径：

- 所有可变数据路径（`SQLITE_PATH`、`CHROMA_PATH`、`DOCX_OUTPUT_DIR`、`LOGS_DIR`、`CACHE_DIR`）均派生自 `RESUME_DATA_DIR`，默认 `%LOCALAPPDATA%\ResumeAssistant`。
- 只有当用户显式在 `.env` 设置旧路径（回滚开关）时才回落到 `backend/data` / `backend/output`。
- `.gitignore` 覆盖了：`data/`、`*.db*`、`backend/output/`、`backend/templates/*.docx`（除了 `_build_templates.py`）、真实用户文件名、`*.bad-dir-*`。
- T5 `run_stub_demo.py` 的 DB 写入路径：通过 `SessionLocal()` → `settings.SQLITE_PATH` = runtime 下 `database/app.db`，不会写到源码树。
- T4 所有 6 个验收脚本（`_v13_validation.py` / `_v13_stub_e2e.py` / `_e2e_v12_p0.py` / `_e2e_v13_full.py` / `_diag_docx.py` / `fill_user_data.py`）已统一解耦 OUTPUT_DIR 到 `settings.DOCX_OUTPUT_DIR`，不再往 `backend/output` 写。

**T6-6 结论：✅ 通过 —— 默认运行模式下，源码树 git 工作区不会因为运行 Stub Demo 或 API 服务而新增任何数据文件（全落到 runtime root）。**

### 2.7 最终首发文件分级清单（T8 应打包的内容）

基于 T1 A/B/C/D 分类，叠加 T5 新增文件：

| 分类 | 应进入 T8 首发仓库的路径清单 | 数量 |
|---|---|---|
| **A 类：可公开源码（必入）** | `backend/api/**`、`backend/core/**`、`backend/database/**`、`backend/models/**`、`backend/prompts/**`、`backend/services/**`、`backend/vectorstore/**`、`backend/config/**`、`backend/main.py`、`backend/requirements.txt`、`backend/.env.example`、`docs/**`（版本文档）、根 `README.md`、根 `.gitignore`、根 `LICENSE` | 核心源码 30+ 个 .py |
| **B 类：整理后公开（必入）** | `backend/templates/_build_templates.py`、`backend/templates/pm_template.json`、`backend/templates/pm_template.docx`（程序化模板）、`backend/config/template_mapping.json`、`input/demo_profile.json`、`input/demo_experiences.json`、`input/demo_jd.txt`、`backend/run_stub_demo.py`（T5 新增 Demo 入口） | ≈ 8 个 |
| **D 类：隔离审查（可选入，开发 worktree 保留用于 T9 交叉核对）** | `_v14_t3_migrate.py`（一次性迁移）、`_v13_validation.py`、`_v13_stub_e2e.py`、`_e2e_v12_p0.py`、`_e2e_v13_full.py`、`fill_user_data.py`、`_diag_docx.py` | 7 个 |
| **C 类：运行时私有 / 历史真源（**绝对不入首发仓库**）** | ✗ `backend/data/app.db`、✗ `backend/data/chroma/**`、✗ `backend/output/**`、✗ `backend/.env`、✗ `input/模板.docx / 简历.pdf / 用户上传PDF.pdf / JD.txt`（已迁出到 runtime）、✗ 任何 `*.bad-dir-*` 迁移遗留 | 全部排除 |

---

## 3. T6 综合结论

> **结果：第三轮安全复验通过，无遗留高危或弱风险。**
>
> 已知弱风险与对应 T8 处置：
> 1. **历史文档公开策略已定** — 初轮的方案 (a)“不发布旧文档”未采用；按用户决定采用方案 (b)，完整保留 V1.0–V1.4 开发档案。含用户名路径必须脱敏；无用户名旧盘符可作为历史语境保留。
> 2. **脱敏脚本自泄漏已解决** — `_v14_c2c3_path_redact.py` 已改为通用匹配，第三轮确认不含原用户名和原始绝对路径。
> 3. **Secret 描述已收口** — 本文真实 key 前缀已改成 `ark-********`；最终交付 HEAD 仍须纳入该文档修正。
> 4. **磁盘残留 C 类文件（已防提交）** — `backend/data/app.db` / `backend/output` / `.env` 都在磁盘上存在，但 `.gitignore` 全覆盖 + T8 首发时会显式剔除。
> 5. **许可证与运行隔离通过** — 依赖许可证与 MIT 兼容；默认写操作落到仓库外 runtime root。
