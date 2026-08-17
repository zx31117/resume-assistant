# V1.4 T1 只读框架审计与 A/B/C/D 分类（baseline）

> 审计时间：2026-08-16  
> 分支：`feat-generate-code-wiki-qOQiu7`，HEAD `4271809`  
> 基线：V1.3 已验收；当前 docs/sources 已删除（历史遗留）  
> 范围：整个 worktree（tracked + untracked + ignored + 隐藏文件）

## 1. 审计结论速览（回答 PLAN 第 3.1 的 6 个问题）

### Q1 哪些是可公开源码 / 不可变模板 / 公开文档

全部位于 `backend/`（源码）、`backend/templates/pm_template.json`（不可变模板规格）、`backend/config/template_mapping.json`（模板映射）、`docs/`（公开文档）、`backend/requirements.txt`（精确锁定依赖）、`backend/.env.example`（配置样例）、根 `.gitignore`、`backend/_v13_stub_e2e.py`（可公开的离线 Stub 回归）。

### Q2 哪些脱敏/整理后可公开

| 文件 | 当前问题 | 整理方向 |
|---|---|---|
| `backend/_diag_docx.py / _e2e_v12_p0.py / _e2e_v13_full.py / _v13_validation.py / fill_user_data.py` | 命名 `_e2e/_diag` 带"一次性诊断"语义；内部可能引用本机路径；未在 Stub 路径中声明用途 | 进入 D 类隔离，逐项查调用关系与硬编码路径，确认长期价值与 PII 安全 |
| `backend/templates/pm_template.docx`（build 产物） | 当前被 `backend/.gitignore` 忽略；需要确认 docx 内元数据不含 PII；构建脚本应随 build 产物一并审查 | 单独进入 T6 容器/二进制审查；doc 正文无占位符泄露方可发布 |
| `backend/pip_freeze_baseline.txt` | 被 `backend/.gitignore` 忽略；若用于基线锁定应整合进 requirements.txt | 与 `requirements.txt` 对齐后由 T5 决定是否替换或删除 |
| `backend/config/template_mapping.json` 中 docx 相对路径 | 引用的 docx 是 build 产物，需确保 build 流程可复现 | docx 生成方式不改变，仅审查 docx 内容即可 |

### Q3 哪些是运行时私有数据（必须与源码隔离）

以下全部属于 C 类，永不进入发布仓库：

| 路径 | 说明 | 当前默认位置 |
|---|---|---|
| `backend/data/app.db` + `backend/data/chroma/` | SQLite 事实源 + Chroma/numpy 向量索引 | `backend/data/`（BASE_DIR 下） |
| `backend/output/*.docx`、`*.json`、`*.txt` | 用户 PDF→简历 DOCX 产物、验证报告 | `backend/output/`（BASE_DIR 下） |
| `backend/.env`（若存在） | API Key | `backend/.env`（BASE_DIR 下） |
| `backend/.venv/` | Python 虚拟环境（第三库大量二进制） | `backend/.venv/` |
| `backend/validation_*.log`、各目录 `__pycache__/` | 运行日志 + Python 字节码缓存 | `backend/*.log`、各 `__pycache__/` |
| `input/JD.txt`、`input/模板.docx`、`input/用户上传PDF.pdf`、`input/简历.pdf` | 根 `input/` 目录含真实用户输入 | 仓库根 `input/`（非 backend 下） |

### Q4 脚本/二进制/第三方资源用途不清（进入 D 隔离）

| 文件 | 疑点 | 判定 |
|---|---|---|
| `backend/_diag_docx.py` | 文件名带"诊断"；只在 V1.3 验证场景被调用 | 先隔离查调用链；确认仅本地排错工具则排除 |
| `backend/_e2e_v12_p0.py` | 后缀 `_p0`，疑似 V1.2 一次性预演脚本，不属于可发布回归 | 查代码内硬编码 PII 与路径；仅本地工具则排除 |
| `backend/_e2e_v13_full.py` | 全链路真实 E2E，**需要真实 API Key 和真实数据**才能跑通 | 默认排除；若作为 README 的"冒烟脚本"必须完全虚构输入 |
| `backend/_v13_stub_e2e.py` | 可公开（Mock LLM/Embedding，无敏感依赖），属于 PLAN T5 的"Stub E2E" | 归入 A 类 |
| `backend/_v13_validation.py` | 自动化 §8.2 验证脚本，**需要真实 LLM 与真实 DB 内容** | 默认排除；脚本逻辑可改写为"虚构 Demo"路径 |
| `backend/fill_user_data.py` | 用途：填充用户数据；文件名本身带"用户数据"语义 | 必须查硬编码 PII/绝对路径；大概率排除 |
| `backend/templates/_build_templates.py` | 构建 docx 模板；doc 来源需要单独审查许可证 | 保留并归入 T6 模板资产审核 |

### Q5 代码创建/读取/写入运行数据的位置；是否存在硬编码路径或"源码目录兼作数据目录"

**统一结论：存在**。当前所有可变数据路径均基于 `BASE_DIR = Path(__file__).resolve().parent.parent`（即 `backend/` 目录）通过 `_resolve()` 解析相对路径，因此默认都会直接写入源码树 `backend/data/`、`backend/output/`，源码目录兼作数据目录的问题真实存在——这正是 V1.4 T2 需要解耦的核心目标。

具体数据读写入口清单（已追代码）：

| 代码位置 | 路径变量 | 默认值 | 行为 |
|---|---|---|---|
| [core/config.py](../../../backend/core/config.py#L6-L39) | `SQLITE_PATH / CHROMA_PATH / DOCX_OUTPUT_DIR` | `./data/app.db`、`./data/chroma`、`./output` | 用 `_resolve()` 拼到 BASE_DIR 下；`.env` 也从 BASE_DIR 直接 load |
| [database/session.py](../../../backend/database/session.py#L10-L22) | `settings.SQLITE_PATH` | 同上 | `_ensure_parent()` 在初始化时自动 mkdir data/，导致首次启动就污染源码树 |
| [vectorstore/chroma_store.py](../../../backend/vectorstore/chroma_store.py#L25-L46) | `settings.CHROMA_PATH` + `_NP_FILE` | 同上 | 模块加载即 `os.makedirs(CHROMA_PATH)`，保证可写；numpy 回退写 `vectors.json` 到同目录 |
| [api/routes/template.py](../../../backend/api/routes/template.py#L30-L32) | 自己硬编码 `BACKEND_ROOT = ... os.pardir, os.pardir` + `OUTPUT_DIR = join(BACKEND_ROOT, "output")` | `backend/output` | **绕过 settings**，模板路由自己又独立 mkdir output，存在双路径源 |
| [services/docx_writer.py](../../../backend/services/docx_writer.py#L146-L174) `load_template_assets()` | `backend_root` 形参（调用方传） | 模板 docx/json（公开资产，非用户数据） | 只读模板资产目录；属于 A 类；没问题 |
| [services/template_renderer.py] / [resume_generation_service.py] / [generate.py] / [docx download 接口] | 最终写入 `DOCX_OUTPUT_DIR` + 返回路径 | `backend/output` | 通过 settings；与 template 路由的硬编码 OUTPUT_DIR 语义相同但来源不同 → T2 统一 |

**额外问题**：
- `api/routes/template.py` 的 `OUTPUT_DIR` 绕过了 `settings.DOCX_OUTPUT_DIR`，即使配置统一 runtime root，模板调试接口仍会继续写 `backend/output`——T2 必须消除该硬编码。
- `input/` 目录位于**仓库根**而非 backend 下，但它存放真实 PDF/JD，用户上传路径（upload/resume API）需要进一步查 T2 中解析；T1 仅记录其存在与分类（C 类）。

### Q6 从全新 clone 启动，哪些目录和文件应由程序自动生成

| 目录/文件 | 当前位置 | 自动生成方式 |
|---|---|---|
| SQLITE parent dir / app.db | runtime `data/` | `session.py` `_ensure_parent(sqlite_path)`；DB tables 由 `init_db.py` 负责 |
| Chroma dir（+ numpy 回退 vectors.json） | runtime `data/chroma/` | `chroma_store.py` 模块加载 `os.makedirs` |
| DOCX output dir | runtime `output/` | 统一在 settings 初始化或 template/generate 路由调用前统一 mkdir |
| 日志（若使用） | 未配置；当前只是脚本写的 `validation_*.log` | T2 统一 log dir 到 runtime，或仅让脚本自行处理 |
| 缓存目录（numpy/torch/transformer） | 未出现独立 cache dir | 保持 Python 默认用户缓存（`~/.cache`），不进 runtime 也不进 repo |
| `.env`（若从 example 复制） | 用户手动复制 `.env.example` | **不应自动生成**；README 明确步骤 |

注意：当前 `init_db.py` 是否在 startup 自动被调用尚未看到；T2 必须在解耦路径后同时保证"空 runtime 启动时 DB/Schema 自动建"（对应 PLAN 验证项"首次启动"）。

---

## 2. A/B/C/D 分类总表（T1 最终产出）

### 分类图例

| 类别 | 含义 | 发布结论 |
|---|---|---|
| **A：可公开源码** | API/services/models/prompts/config/依赖/公开配置样例/Stub 回归 | 审计通过直接进入发布仓库 |
| **B：整理后公开** | 文档、模板、fixture、示例配置 | 脱敏/改相对路径/替换虚构数据或确认许可证后进入 |
| **C：运行时私有数据** | .env、用户 PDF/JD、DOCX 输出、DB、向量、日志、缓存、.venv、__pycache__ | 移出源码资产边界；默认写入统一 runtime root；永不进入发布仓库 |
| **D：隔离审查** | 未跟踪诊断脚本、来源不明二进制、一次性报告、用途不明大文件 | 先隔离 + 查调用关系；确认长期价值和安全后方可进入 A/B，否则不发布 |

### 按文件逐项枚举

| 路径（相对 repo 根） | 类别 | 去留 | 依据 / 备注 |
|---|---|---|---|
| `.gitignore` | A | 发布 | 全局忽略规则，T2 后可能新增 runtime root 默认路径，但文件本身公开 |
| `backend/__init__.py` 不存在？ | A | — | repo 无顶层；发布根按 V1.4 README 决定是"flat"还是"带 backend"，T5 定结构 |
| `backend/requirements.txt` | A | 发布 | 精确锁定依赖 |
| `backend/.env.example` | A | 发布 | 全字段占位符，无真实值；已通过快速目视 |
| `backend/.gitignore` | A | 发布 | backend 层级忽略（目前只忽略 pip_freeze_baseline.txt），需与根 `.gitignore` 对齐审查 |
| `backend/main.py` | A | 发布 | FastAPI 入口；仅导入/初始化 |
| `backend/fill_user_data.py` | D | **默认不发布** | 文件名明示"填充用户数据"用途；查代码再确认；大概率是本地一次性工具 |
| `backend/_diag_docx.py` | D | **默认不发布** | 诊断脚本；若 T5 需要独立诊断工具再重写为公开工具 |
| `backend/_e2e_v12_p0.py` | D | **默认不发布** | V1.2 预演；与发布版本不对应 |
| `backend/_e2e_v13_full.py` | D | **默认不发布** | 真实 E2E 依赖真实 Key+真实数据；如需公开 Demo 需完全虚构 |
| `backend/_v13_stub_e2e.py` | A | 发布（移至 tests/ 或 examples/） | Mock LLM+Embedding；可作为公开最小可运行回归；T4 调整位置 |
| `backend/_v13_validation.py` | D | **默认不发布** | §8.2 验证脚本需真实 API 和真实 DB；可拆出公开的"最小虚构用例" |
| `backend/api/**` （全部 routes + schemas） | A | 发布 | 纯请求/响应与路由调度；无用户数据硬编码 |
| `backend/config/template_mapping.json` | B | 发布 | 模板 ID → docx/json 相对路径映射；T6 确认 docx 内容安全 |
| `backend/core/config.py` | A | 发布 + **T2 修改对象** | 当前 BASE_DIR 为 backend 目录；T2 在此引入统一 `RESUME_DATA_DIR` |
| `backend/core/errors.py` | A | 发布 | V1.3 统一 DomainError 定义；不含数据 |
| `backend/database/init_db.py / models.py / session.py` | A | 发布 + T2/T3 适配 | session.py 是路径副作用点；T2 解耦后初始化不变 |
| `backend/models/resume_document.py / template_schema.py` | A | 发布 | 纯结构定义 |
| `backend/prompts/**` | A | 发布 | Prompt 文本；不含真实用户数据 |
| `backend/services/**`（全部 16 个 service） | A | 发布 | 业务编排；路径副作用全部经 settings → 统一 T2 收口 |
| `backend/vectorstore/__init__.py` + `chroma_store.py` | A | 发布 | 路径读取 settings；无 PII |
| `backend/templates/_build_templates.py` | B | 发布 | T6 审查模板来源与 License |
| `backend/templates/pm_template.json` | B | 发布 | 模板规格 JSON；纯结构 |
| `backend/templates/pm_template.docx` | B | **发布条件通过 T6** | 构建产物；需扫描正文无 PII、无未替换占位符、元数据无本机路径 |
| `docs/README.md` | B | 发布（已修复版本引用） | 稳定产品目标；已将活动版本从 V1.3.1 修正为 V1.4 |
| `docs/CURRENT_STATE.md` | B | 发布 | 当前已验收事实；活动版本已修正 |
| `docs/DECISIONS.md` | B | 发布 | 跨版本决策；含 D-020 解耦决策 |
| `docs/HUMAN_AI_WORKFLOW.md` | B | 发布 | 人-机协作说明；无 PII |
| `docs/versions/**`（v1.0～v1.4 PLAN+RESULT） | B | 发布 | 开发经验档案；T6 需扫描历史文档残留真实 PII 文本 |
| **docs/sources/ 已删除（历史遗留）** | — | — | 本版本开始清理 |
| `input/`（4 个真实文件：JD.txt、模板.docx、用户上传PDF.pdf、简历.pdf） | **C** | **永不发布** | 真实 JD+PDF；敏感且非源码 |
| `backend/data/app.db`（SQLite） | **C** | **永不发布** | 事实源 SQL；敏感用户数据 |
| `backend/data/chroma/`（Chroma 数据 + chroma.sqlite3） | **C** | **永不发布** | 可重建向量索引；含经历文本副本 |
| `backend/output/**`（DOCX/JSON/TXT 验证报告/产物） | **C** | **永不发布** | 用户简历生成产物；直接可识别 PII |
| `backend/.venv/`（虚拟环境） | **C** | **永不发布** | 第三方依赖；体积大，可从 requirements.txt 重建 |
| `backend/**/__pycache__/`（所有字节码缓存） | **C** | **永不发布** | Python 运行产物，不携带也无价值 |
| `backend/validation_*.log`（4 个 .log） | **C** | **永不发布** | 一次性本地验证日志；可能含本机路径 |
| `backend/pip_freeze_baseline.txt` | D | **默认不发布** | 与 requirements.txt 功能重叠，需要 T4 比对是否锁定同一版本 |
| 所有 `.env`（若存在） | **C** | **永不发布** | Secret；仅 `.env.example` 可发布 |
| 根目录缺失的 LICENSE / 顶层 GitHub README | — | T5 补齐 | V1.4 PLAN 要求 MIT + 面向 GitHub 的根 README，当前 docs/README.md 是面向项目内部的产品总览，需区分 |

### 剩余未判定项（T5/T6 之前先放 D）

| 路径 | 未判定点 |
|---|---|
| `backend/templates/pm_template.docx` 的**内部元数据**与**作者/公司占位符文本** | T6 容器扫描通过后才能最终入 B |
| `docs/versions/**` 中历史文档是否仍引用真实 PII 文本（V1.2 已确认早期版本有 PII，当时只清理当前，未清历史） | T6 语义扫描；若存在则必须在干净首发中修改，或使用"新建干净 Git 历史 + 文档副本脱敏后重新提交"策略 |
| `_v13_full / _v13_validation / fill_user_data / _diag_docx / _e2e_v12_p0` 是否能转化为"完全虚构公开版" | T4+T5 再判；T1 默认排除 |

---

## 3. 高风险项与 T2 前置输入

1. **源码目录兼作数据目录（已确认）**：`BASE_DIR=backend/` 直接写 data+output，新 clone 只要运行就污染源码树。T2 必须引入 `RESUME_DATA_DIR` 作为唯一可变根。
2. **双路径写入 output（已确认）**：`settings.DOCX_OUTPUT_DIR` 与 `api/routes/template.py` 自算的 `OUTPUT_DIR` 语义重复但来源不同；T2 必须消除后者硬编码。
3. **根 `input/` 目录真实存在**（在 repo 根，不是 BASE_DIR 子目录）：上传接口与离线脚本都可能读该目录；T2 决定默认映射为 runtime/input，或仅作示例被忽略。
4. **历史 Git 含 PII（已知风险，PLAN §2 已点出）**：因此 T8 干净首发**必须全新初始化 `.git`**，不能把旧 `.git` 复制到发布仓库。本 T1 不触及 Git 历史。
5. **D 类 5 个 `_*.py` 脚本 + pip_freeze + 验证 log 大**：T4 执行期逐个 open/read 验证。

—— T1 只读结论完成，下一步 T2：建立仓库外 runtime root + 统一路径配置。
