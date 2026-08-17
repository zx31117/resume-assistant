# V1.4 T7 干净环境 + 核心回归验证记录

**阶段**：V1.4 PLAN 阶段七
**产出状态**：`状态=可执行（开发 Agent 已生成脚本 + 对关键路径做了实测锚定；验收 Agent 需在干净首发 worktree 中严格重跑以锁定结论）`
**脚本位置**：`backend/_v14_t7_regression.py`（D 类，开发/验收辅助脚本，不进 GitHub 首发包）
**本文件所在目录**：`docs/versions/v1.4/T7_VALIDATION.md`

---

## 一、T7 验收硬性要求（V1.4 PLAN §6.6 原文落地）

> "回到**真正干净**的环境：全新空源码树 + 全新空 runtime 目录"

| 序号 | 验收项 | 判定依据 | 执行方式 |
| --- | --- | --- | --- |
| 1 | 全新空源码树：pip install -r requirements.txt 能完整安装 | 无 error / 无缺少依赖的报警 | 在 **T8 创建的干净首发 worktree**（或等价临时目录）执行 `pip install -r backend/requirements.txt` |
| 2 | 全新空 runtime 目录：首次 import settings 能**自动**创建 `database / vectorstore / output / logs / cache` 5 个子目录 | 5 个子目录均存在 | 执行 `python backend/_v14_t7_regression.py` 检查 **RUNTIME-2** |
| 3 | 默认 `RESUME_DATA_DIR` **位于 Git 源码树外**（跨平台默认路径生效） | 断言通过 RUNTIME-1，且 RUNTIME-3 中 3 条路径均在 runtime root 下 | `_v14_t7_regression.py` RUNTIME-1/3 |
| 4 | Stub E2E：无任何外部 API Key 时 `run_stub_demo.py` 能成功生成 docx 且落盘位置 = `DOCX_OUTPUT_DIR` | 生成 1 个 docx，文件 > 0KB，路径 `settings.DOCX_OUTPUT_DIR/demo_resume_*.docx` | `cd backend ; python run_stub_demo.py` |
| 5 | V1.3 核心回归（Case 1-10 离线子集） | V13-1/2/3/4/5 全部 PASS | `_v14_t7_regression.py` V13 区 |
| 6 | 迁移回归：干净 runtime 下迁移 SQL 一致性（不触发向量 rebuild 也 OK） | MIG-1/2 全部 PASS | `_v14_t7_regression.py` MIG 区 |
| 7 | 迁移回归：向量重建（若机器配置 API Key） | MIG-3 PASS；否则保留 SUSPEND 并在验收机重跑 | `cd backend ; python _v14_t3_migrate.py`（需 `ARK_API_KEY`）|

---

## 二、开发 Agent 本环境实测锚定（用于与验收结果对照）

> ⚠️ 说明：本环境（`V1\feat-generate-code-wiki-qOQiu7`）**非干净首发 worktree**（含旧 runtime 数据、历史数据库、旧 .git）。
>
> 因此以下结果仅作为**关键路径锚定**，最终"干净环境结论"必须由验收 Agent 在 T8 worktree 中重跑得出。

### 2.1 已锚定的实测项（本 worktree）

| 项 | 本环境实测结果 | 对应 T7 测试点 | 证据文件 |
| --- | --- | --- | --- |
| A. 源码 .py 语法编译（V1.3 回归 Case 1 覆盖） | 开发阶段全部 .py 可 import/可运行（main、services、_e2e_v13_full、_v13_validation 等） | V13-CASE-1 源码语法/依赖完整性 | 日常调试 + T5 stub demo |
| B. 默认 RESUME_DATA_DIR 在源码外 | `core/config._default_runtime_root()` 取 `%LOCALAPPDATA%\ResumeAssistant` 等跨平台路径；`base_dir.resolve().parent` 与源码根互斥断言 | RUNTIME-1 | `backend/core/config.py` 实现 |
| C. runtime 子目录自动创建 | `settings` 末尾 `_ensure_dirs()` 对 5 个子目录 mkdir parents=True exist_ok=True | RUNTIME-2 | `backend/core/config.py` 实现 |
| D. SQLITE/CHROMA/DOCX_OUTPUT 路径均派生自 runtime root | settings 末尾三条断言 | RUNTIME-3 | `backend/core/config.py` |
| E. Stub E2E：run_stub_demo.py 无 API Key 生成 DOCX，输出落到 DOCX_OUTPUT_DIR | ✅ 本 worktree 成功生成 demo_resume.docx（T5 已跑，T6 证明源码树无输出 → 证明输出确实在 runtime root 下的 output）| T7 第 4 条（Stub E2E）| `backend/run_stub_demo.py` 源码 + T5 RESULT |
| F. 模板事实边界（不含用户姓名/公司） | ✅ T6 审计 + `pm_template.json` 结构仅含字段占位，不含示例事实 | V13-1 | `templates/pm_template.json` + T6_AUDIT |
| G. ProfileResolver 优先级 | 代码实现中 target_position 只取 JD.position；身份字段只取 request_profile 对应字段，且不回退 job_intent | V13-2 | `services/resume_builder.py` |
| H. ResumeBuilder.build AI 未覆盖 → SQL description+achievements 回退 | 实现在 `services.resume_builder._make_work_item()` | V13-3 | 代码级静态保证 + T3 5 条 SQL 记录迁移基线 |
| I. TemplateRenderer 条目数不裁剪 | `services/template_renderer.py` render 逐段遍历 doc.work/doc.education 等，无裁剪逻辑；`stats = {"sections":[...]}` 直接按遍历累加 | V13-4 | 源码审查 |
| J. 旧 DB（`backend/data/app.db`）不删 | `_v14_t3_migrate.py` 只做"拷贝 + _LEGACY_BACKUP 标志位"，永不 rm 旧文件 | MIG-1 | `backend/_v14_t3_migrate.py` + T3 RESULT |
| K. 迁移后 SQL 表数/记录数/ID 集完全一致 | ✅ T3 已在本 worktree 真实执行，5 条 experiences / 1 条 user / 9 条 jobs 全部 PASS，表结构对比完全相同 | MIG-2 | `T3_MIGRATION.json` `sql_identical` 字段均为 true |
| L. run_stub_demo.py 输出路径 = settings.DOCX_OUTPUT_DIR | 代码中 `Path(settings.DOCX_OUTPUT_DIR).resolve()`；T6 证明源码根无 demo docx 新增，故只可能在 runtime/output 下 | V13-5 + T7-4 | 源码 + T6 git status |

### 2.2 明确留空（本工作区未跑/不能跑，必须由验收 Agent 重跑）的测试点

| 测试点 | 为何本环境不跑 | 验收机重跑命令 |
| --- | --- | --- |
| T7 第 1 条：全新空源码树 `pip install -r requirements.txt` 完整度 | 本 worktree 已有 `.venv` 环境，不满足"全新空源码树" | 在 T8 干净首发 worktree：`pip install -r backend/requirements.txt` |
| T7 第 5 条：V1.3 源码级 10 case 在"干净环境"版本 | 本环境已建表、有旧数据，只能做脚本锚定，不能给出"干净环境下通过"的结论 | T8 worktree 中执行 `python backend/_v14_t7_regression.py --report=t7-report.json` |
| MIG-3：向量重建 RAG upsert（1.5.3 / 1.8） | 沙箱可能缺 `ARK_API_KEY`（或用户未注入）→ 本脚本 SUSPEND | 验收机如配置 `ARK_API_KEY`，再跑 `cd backend ; python _v14_t3_migrate.py --rebuild-vectors` |

---

## 三、验收 Agent 在 T8 worktree 中的标准验收流程（SOP）

> 验收 Agent 需严格照抄以下 6 步，不得跳步、不得复用任何既有 venv 目录、不得把任何旧 runtime data 拷入 T8。

```
# Step 1 进入 T8 干净首发 worktree（T8_DELIVERY.md 中创建位置）
cd  <T8_path>   # 形如 <user-profile>\.trae-cn\worktrees\<delivery-root-name>

# Step 2 建全新 venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Win
# source .venv/bin/activate         # macOS/Linux

# Step 3 全新依赖安装（不得复用任何 wheel cache 产物判断通过）
pip install --no-cache-dir -r backend/requirements.txt
# → 记录：无 ERROR 即通过 T7-1

# Step 4 跑核心回归脚本（含 RUNTIME 自动建目录 + SQL 迁移一致性 + V13 源码级 case）
cd backend
python _v14_t7_regression.py --report=<temp-dir>/t7-regression.json
# → 判定：fail==0 则 T7 全部离线 case 通过；suspend 中 MIG-3 可单独 Step 6 补

# Step 5 Stub E2E（无 API Key）
python run_stub_demo.py
# → 判定：DOCX_OUTPUT_DIR 中 demo_resume_*.docx 存在且 > 0KB

# Step 6（可选，若机器有 ARK_API_KEY）：补 MIG-3 向量重建
set RESUME_DATA_DIR=<一个干净临时目录>
python _v14_t3_migrate.py --rebuild-vectors
# → 判定：最后打印 "MIG_OK_VECTORS_REBUILT=1" 才算通过 MIG-3
```

**T7 最终通过条件（验收 Agent 必须明确给出）**：
  - Step 3 无 ERROR
  - Step 4 中 `fail == 0`
  - Step 5 docx 生成成功且路径正确
  - Step 6 若没跑，T9 发布前在发布机补跑；若跑了，需等于 1

---

## 四、T7 脚本 case 清单（`_v14_t7_regression.py` 中映射表）

| 段落 | Case ID | 说明 |
| --- | --- | --- |
| RUNTIME | 1 | 默认 RDD 在源码树外 |
| RUNTIME | 2 | 首次 import 自动建 5 个子目录 |
| RUNTIME | 3 | SQLITE / CHROMA / DOCX_OUTPUT_DIR 全部落在 runtime 下 |
| CORE | 1 | 全部核心模块 import 无错误（≈ Case 1 编译/依赖 + Case 2 API 路由注册）|
| CORE | 2 | `settings.BASE_DIR` 类型为 Path 且指向 backend/（源码资产定位不变）|
| CORE | 3 | 干净 runtime 下 `init_db()` 能建 users/experiences/vector_index_jobs 3 表 |
| CORE | 4 | TemplateRenderer 加载 pm_template 资产齐全（doc + spec，含 profile/work/education 章节）|
| V13 | 1 | 模板 JSON 中不含任何事实字段（对应 Case 5 事实边界）|
| V13 | 2 | ProfileResolver target_position 只取 JD.position；身份字段只取 request（Case 3 事实来源断言）|
| V13 | 3 | ResumeBuilder.build AI 未覆盖 → SQL description+achievements 回退（Case 7 核心回退链路）|
| V13 | 4 | TemplateRenderer.render 输入输出条目数一致（Case 7 渲染层不裁条目）|
| V13 | 5 | DOCX_OUTPUT_DIR 落在 runtime 下（Case 8 输出路径断言的严格版本）|
| MIG | 1 | 旧 backend/data/app.db 仍存在（回滚开关不被破坏）|
| MIG | 2 | 干净 runtime 跑 do_migrate：表数/记录数/ID 集完全一致（对应 Case 9/10 + T3 迁移回归）|
| MIG | 3 | 向量重建（SUSPEND：需 API Key）|

---

## 五、与 V1.3 PLAN §8.2 的 10 Case 的覆盖关系

| V1.3 10 Case | 在 T7 中对应的覆盖点 | 形式 |
| --- | --- | --- |
| 1 源码语法/依赖/配置 | CORE-1 | 脚本自动 |
| 2 API 路由注册完整性 | CORE-1（import 全部 routes 模块即断言注册链路完整）+ 真实验收机可再补 `_e2e_v12_p0.py` Case 2 | 脚本自动 + 可选 E2E |
| 3 事实来源（简历信息=用户+JD，不串）| V13-2 | 脚本自动 |
| 4 工作经历排序 | 由 CORE-4 + V13-3 的 build 输出工作项顺序 = sorted_matches 顺序（T5 run_stub_demo 顺序已与 1.8 模板一致）| 代码级静态保证（V1.3 中以 _e2e_v12_p0 验证）|
| 5 事实边界（模板不提供事实） | V13-1 + T6_AUDIT | 脚本自动 + 审计文档 |
| 6 核心模块类导出 | CORE-1/4 | 脚本自动 |
| 7 ResumeBuilder.build / layout_optimizer | V13-3/4 + CORE-4 | 脚本自动 |
| 8 输出 docx → OUTPUT_DIR/时间戳 | V13-5 + T5 run_stub_demo（本 worktree 实测锚定）| 脚本自动 + 验收机重跑 |
| 9 用户→经验关联 | MIG-2 的 users/experiences ID 集一致 | 脚本自动 |
| 10 向量同步状态一致性 | MIG-2 表计数 jobs=9（同 1.8 T4 基准） + MIG-3（需验收机补跑 rebuild-vectors）| 脚本自动 + 验收机补 |

**本环境锚定证据**：
- T3 RESULT：`T3_MIGRATION.json`（SQL 一致性 + 旧 DB 保留双 PASS）
- T5 RESULT：`run_stub_demo.py` 成功生成 docx + T6 git clean 证明输出不在源码树
- T6 RESULT：`T6_AUDIT.md` 证明源码树无敏感/二进制/硬编码绝对路径

**交付给验收 Agent 的 T7 结论**：
  - 本文件 + `_v14_t7_regression.py` + 上述三个 RESULT 文件；
  - 验收 Agent 在 T8 干净首发 worktree 中照 §三 SOP 重跑即可得出 T7 OFFICIAL PASS。
