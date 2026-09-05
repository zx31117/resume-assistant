# V2.0.2 RESULT：工程基线与旧迁移契约退出

> 当前状态：**开发候选已冻结，待独立源码验收**
> 当前阶段：T1–T6 实施完成、T7 RESULT 与冻结候选完成；T8 独立源码验收待开始
> 计划日期：2026-09-05
> 批准日期：2026-09-05
> 发布基线：annotated tag `v2.0.1` → `f4e69aae0577ea723e9ef5427b20287add76d06c`
> 计划分支：`version/v2.0.2`
> 冻结候选 commit：`7a7cdfd2777f9497d3633545d21722eb3c6e795c`（工作树 clean，父提交 `16ceac2`）

## 1. 当前实际发生的事

V2.0.2 依据已批准 PLAN 完成 T1–T6 实施，并在 `version/v2.0.2` 上冻结候选 commit（`7a7cdfd`，工作树 clean、`v2.0.1` 为祖先）。核心产出：

- **T1** 统一 Windows 预检入口 `scripts/precheck.py` 与 GitHub workflow `.github/workflows/windows-ci.yml`，本地与 CI 共用同一检查逻辑；
- **T2** 旧迁移契约完整退出：`run_migrations()` 与 `_backup_sources()` 删除 `vectorstore_dir` 死参数，迁移摘要删除 `backup.vectorstore` 死字段，并机械适配四个当前 V1.5 单点脚本；
- **T3** RUNTIME-2 改为隔离子进程验证，修正干净环境假通过；删除 `run_stub_demo.py` 对 `CHROMA_PATH` 的防御性清理；
- **T4** 建立 ruff / ESLint / pip-audit / npm audit 四项固定非阻断基线；
- **T5** 后端与前端版本元数据统一更新为 2.0.2；
- **T6** 全部阻断检查通过；D15 便携包构建仍待从冻结候选执行。

## 2. PLAN Task 当前状态

| Task | 状态 | 实际结果 |
|---|---|---|
| T1 统一 Windows 预检与 workflow | 完成 | `scripts/precheck.py` + `.github/workflows/windows-ci.yml`；最小权限、60min 超时、无 artifact，本地与 CI 同源 |
| T2 迁移死契约退出与脚本适配 | 完成 | 迁移签名/摘要退出 vectorstore；四个 V1.5 单点脚本机械适配后运行通过 |
| T3 RUNTIME-2 与 CHROMA_PATH 残留修正 | 完成 | RUNTIME-2 改为隔离子进程；Demo 不再 pop CHROMA_PATH |
| T4 非阻断静态/依赖基线 | 完成 | 四项非阻断基线已记录（见 §4 D13） |
| T5 版本、公开说明与构建输入 | 完成 | backend/前端版本 2.0.2；health 断言同步 |
| T6 完整验证与便携包 | 完成（D15 便携包构建除外） | 全部阻断检查通过；D15 待从冻结候选构建 |
| T7 RESULT 与冻结候选交接 | 完成 | 冻结候选 `7a7cdfd`；本 RESULT |
| T8 独立源码验收 | 未开始 | 待验收 Agent 绑定 `7a7cdfd` |
| T9 人工确认、文档收口与发布 | 未开始 | 待 T8 |

## 3. 当前实际全局变化

| 范围 | 实际变化 |
|---|---|
| 用户 API | 迁移摘要不再含无意义 `backup.vectorstore`；其余路由、请求与正常响应不变 |
| Python 内部契约 | `run_migrations(db_path=None, *, backup=True, recording=None)` 与 `_backup_sources(sqlite_path)` 不再接受 `vectorstore_dir`；旧关键字调用显式 `TypeError` |
| 数据库 | 无 schema 与业务数据变更；SQLite `fact_embeddings` 唯一向量持久化不变 |
| Runtime | 当前配置只创建 database / output / logs / cache；不创建、扫描或删除 vectorstore |
| Demo | 不再清除无人读取的 `CHROMA_PATH` |
| 自动化 | 新增 Windows GitHub workflow 与统一本地预检入口 |
| 静态/依赖检查 | ruff / pip-audit / eslint / npm-audit 首份非阻断基线；不自动修复、不上传原始扫描 artifact |
| 前端 | 业务页面不变，仅版本元数据 2.0.2 与 `lint` 脚本；`eslint.config.js` 新增 |
| 便携包 | 尚未从此候选重建（D15） |
| 文档 | 本 RESULT；CURRENT_STATE / DECISIONS / 根 README / 版本索引留待文档 Agent 收口 |

## 4. 验证状态（D1–D15）

| D | 场景 | 命令 / 证据 | 结果 |
|---|---|---|---|
| D1 | 干净基线统一预检 | `python scripts/precheck.py` | 阻断项全部通过：编译、6 脚本固定计数、前端 build |
| D2 | 计数不匹配假绿反向 | `precheck._run_blocking_script('_v20_smoke.py', r'PASS=999 FAIL=0')` | 触发 `_Failure`「汇总计数不匹配」，fail-closed 证实 |
| D3 | 空临时 runtime 首 import config | `_v14_t7_regression.py` RUNTIME-2 | database/output/logs/cache 存在，vectorstore 不存在 |
| D4 | 历史目录不污染 | RUNTIME-2 隔离子进程只判临时 runtime | 通过，不受开发机残留目录影响 |
| D5 | 全新库/升级库/重复迁移 | `_v15_r_rework.py` | PASS=48 FAIL=0 (total=48) |
| D6 | 旧关键字失败/旧摘要字段 | 签名检查 + `rg vectorstore_dir --glob '!_*.py'` | 签名无 `vectorstore_dir`；活动调用 0；旧关键字 `TypeError` |
| D7 | 迁移失败路径 fail-closed | `_v2_lifecycle_matrix.py` | 矩阵合计 50 项，失败 0 |
| D8 | 四个 V1.5 单点脚本 | 分别运行 t2/t3/t4/t5 | 35/54/53/40 通过，均 exit 0 |
| D9 | CHROMA_PATH 注入 | 静态核实 + 回归 | 无活动读取方；仅剩防御剥离 / 测试断言 / 历史归档 |
| D10 | 生命周期矩阵完整执行 | `_v2_lifecycle_matrix.py` | 50 项，失败 0 |
| D11 | V1.5/V2.0/V2.0.1 回归 | `_v15_r_rework.py`/`_v15_w_rework.py`/`_v15_t6_legacy_exit.py`/`_v20_smoke.py`/`_v2_t5_crud_check.py`/`_v201_validation.py` | 48/37/24/20/15/77 通过，均 0 fail |
| D12 | 前端 build | `npm run build` | dist/index.html 存在；package.json 版本 2.0.2 |
| D13 | 非阻断扫描 | ruff / pip-audit / eslint / npm audit | 见下方基线 |
| D14 | workflow 反向检查 | 审阅 `windows-ci.yml` | contents:read；60min 超时；无 artifact；不读 Secret |
| D15 | 便携包构建/启动/内容扫描 | **未执行** | 原因见下方 |

**D13 非阻断基线（首版，不阻断发布，RESULT 记录）**

| 工具 | 版本固定 | 结果 |
|---|---|---|
| ruff | 0.16.6 | Found 370 errors（退出码 1） |
| pip-audit | 2.10.1 | Found 7 known vulnerabilities in 4 packages（退出码 1） |
| ESLint | 前端 devDependencies | 6 problems (6 errors, 0 warnings)（退出码 1） |
| npm audit | 前端 devDependencies | 4 vulnerabilities (3 moderate, 1 high)（退出码 1） |

以上均以「发现问题」显式报告，绝不伪装成零问题；工具缺失/超时/未匹配摘要行会显式标记（见 `scripts/precheck.py` `_run_nonblocking`）。

**D15 未执行原因**：便携包为 PyInstaller onedir 重型构建（`packaging/build.ps1` → `dist/ResumeAssistant/`），PLAN §4 要求「从冻结候选重新构建」。本回合交付冻结候选 `7a7cdfd` 与 RESULT，D15 的构建、启动退出验证与内容/隐私扫描将在 T8 独立源码验收前从该 commit 干净检出执行，随后将大小、SHA-256 与扫描结论补入本表。

### 4.1 精确固定计数（PLAN §6 R4）

| 脚本 | 期望汇总 | 实测 | 状态 |
|---|---|---|---|
| `_v201_validation.py` | `PASS=77 FAIL=0` | 退出码 0，计数匹配 | ✅ |
| `_v15_r_rework.py` | `PASS=48 FAIL=0 (total=48)` | 退出码 0，计数匹配 | ✅ |
| `_v20_smoke.py` | `PASS=20 FAIL=0` | 退出码 0，计数匹配 | ✅ |
| `_v2_t5_crud_check.py` | `PASS=15 FAIL=0` | 退出码 0，计数匹配 | ✅ |
| `_v2_lifecycle_matrix.py` | `矩阵合计 50 项，失败 0` | 退出码 0，计数匹配 | ✅ |
| `_v14_t7_regression.py` | `total=15 PASS=12 FAIL=0 SUSPEND=3` | 退出码 0，计数匹配 | ✅ |

**修复前负向证据（PLAN §6 R4）**：RUNTIME-2 修复前，干净环境真实结果为 `11 PASS / 1 FAIL / 3 SUSPEND`（被开发机历史 `vectorstore` 目录误导可假象到 `12/0/3`）。修复后以上 `12 PASS / 0 FAIL / 3 SUSPEND` 是隔离子进程下的真实固定计数，不再受残留目录影响。

### 4.2 四个 V1.5 单点脚本机械适配清单

| 脚本 | 变更 | 实测 |
|---|---|---|
| `_v15_t2_fact_migration.py` | 删 `_VS_DIR`；`r1`/`r2`/`r5` 三处去掉 `vectorstore_dir=` | 35 pass / 0 fail |
| `_v15_t3_embedding.py` | 删 `_VS_DIR`；`run_migrations` 去掉 `vectorstore_dir=` | PASS=54 FAIL=0 |
| `_v15_t4_selection.py` | 删 `_VS_DIR`；`_run_migrations` 去掉 `vectorstore_dir=` | PASS=53 FAIL=0 |
| `_v15_t5_rewrite.py` | 删 `_VS_DIR`；`_run_migrations` 去掉 `vectorstore_dir=` | PASS=40 FAIL=0 |

均为删除旧关键字参数及其专用临时变量，未改动任何业务断言；历史 `v1.5.0` tag 中的原脚本不变。

### 4.3 开发侧结论

**功能验收（开发侧）**：六脚本固定计数全部通过，四个 V1.5 单点脚本与 `_v15_w_rework.py`/`_v15_t6_legacy_exit.py` 运行通过，前端正式 build 成功且产出版本母本 2.0.2；API health、系统状态、模板、写操作安全边界、同源托管等冒烟断言无回退。**此结论为开发侧自证，不等同 T8 独立验收。**

**结构变更验收（开发侧）**：迁移函数签名/摘要字段干净退出（活动调用 0、旧关键字显式失败）；`config.py` 无 vectorstore 符号或创建行为；`run_stub_demo.py` 无 `CHROMA_PATH` 活动兼容分支；CI 固定计数 + 退出码双重判定并经 D2 负向证实 fail-closed；workflow 最小权限/超时/无 artifact。**此结论为开发侧自证，不等同 T8 独立验收。**

## 5. 当前结论

V2.0.2 T1–T6（D1–D14 适用项）已完成并在 `7a7cdfd` 冻结候选，工作树 clean。所有阻断检查通过，固定计数与退出码双重判定有效，非阻断基线真实可追溯。剩余交付为：

1. **D15 便携包**从冻结候选 `7a7cdfd` 干净检出构建，补录大小、SHA-256 与内容/隐私扫描；
2. **T8** 独立源码验收 Agent 绑定 `7a7cdfd`，分别给出功能与结构变更验收；
3. **T9** 用户最小人工回归、文档收口与发布决定（由用户与文档 Agent 完成）。

开发 Agent 未操作公开 `main`、未推送、未创建 tag。CURRENT_STATE、DECISIONS、根 README 与版本索引的收口建议留待 T8 通过后由文档 Agent 执行。