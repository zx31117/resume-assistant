# V2.0.2 RESULT：工程基线与旧迁移契约退出

> 当前状态：**T8 独立源码验收已通过（2026-09-05），待 T9 用户最小人工回归与文档收口**
> 当前阶段：T1–T6 实施完成、T7 RESULT 与冻结候选完成、T8 独立源码验收通过（§6）；T9 待开展
> 计划日期：2026-09-05
> 批准日期：2026-09-05
> 发布基线：annotated tag `v2.0.1` → `f4e69aae0577ea723e9ef5427b20287add76d06c`
> 计划分支：`version/v2.0.2`
> 冻结候选 commit：`a40c14df7d48b322aa761b494cdd08678f18830e`（含 `7a7cdfd` T1–T6 与模板按文件打包修复；祖先含 `v2.0.1`/`f4e69aa`）

## 1. 当前实际发生的事

V2.0.2 依据已批准 PLAN 完成 T1–T6 实施，并在 `version/v2.0.2` 上冻结候选 commit（`7a7cdfd`，工作树 clean、`v2.0.1` 为祖先）。核心产出：

- **T1** 统一 Windows 预检入口 `scripts/precheck.py` 与 GitHub workflow `.github/workflows/windows-ci.yml`，本地与 CI 共用同一检查逻辑；

- **T2** 旧迁移契约完整退出：`run_migrations()` 与 `_backup_sources()` 删除 `vectorstore_dir` 死参数，迁移摘要删除 `backup.vectorstore` 死字段，并机械适配四个当前 V1.5 单点脚本；

- **T3** RUNTIME-2 改为隔离子进程验证，修正干净环境假通过；删除 `run_stub_demo.py` 对 `CHROMA_PATH` 的防御性清理；

- **T4** 建立 ruff / ESLint / pip-audit / npm audit 四项固定非阻断基线；

- **T5** 后端与前端版本元数据统一更新为 2.0.2；

- **T6** 全部阻断检查通过；D15 便携包已从冻结候选重建并隐私复扫干净。

## 2. PLAN Task 当前状态

| Task                             | 状态  | 实际结果                                                                                          |
| -------------------------------- | --- | --------------------------------------------------------------------------------------------- |
| T1 统一 Windows 预检与 workflow       | 完成  | `scripts/precheck.py` + `.github/workflows/windows-ci.yml`；最小权限、60min 超时、无 artifact，本地与 CI 同源 |
| T2 迁移死契约退出与脚本适配                  | 完成  | 迁移签名/摘要退出 vectorstore；四个 V1.5 单点脚本机械适配后运行通过                                                   |
| T3 RUNTIME-2 与 CHROMA\_PATH 残留修正 | 完成  | RUNTIME-2 改为隔离子进程；Demo 不再 pop CHROMA\_PATH                                                    |
| T4 非阻断静态/依赖基线                    | 完成  | 四项非阻断基线已记录（见 §4 D13）                                                                          |
| T5 版本、公开说明与构建输入                  | 完成  | backend/前端版本 2.0.2；health 断言同步                                                                |
| T6 完整验证与便携包                      | 完成  | 全部阻断检查通过；D15 便携包已从冻结候选重建并隐私复扫干净                                                               |
| T7 RESULT 与冻结候选交接                | 完成  | 冻结候选 `7a7cdfd` + 便携修复 `a40c14d`；本 RESULT                                                      |
| T8 独立源码验收                        | 未开始 | 待验收 Agent 绑定最终代码冻结 `a40c14d`（含 `7a7cdfd`）                                                     |
| T9 人工确认、文档收口与发布                  | 未开始 | 待 T8                                                                                          |

## 3. 当前实际全局变化

| 范围          | 实际变化                                                                                                                                        |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| 用户 API      | 迁移摘要不再含无意义 `backup.vectorstore`；其余路由、请求与正常响应不变                                                                                              |
| Python 内部契约 | `run_migrations(db_path=None, *, backup=True, recording=None)` 与 `_backup_sources(sqlite_path)` 不再接受 `vectorstore_dir`；旧关键字调用显式 `TypeError` |
| 数据库         | 无 schema 与业务数据变更；SQLite `fact_embeddings` 唯一向量持久化不变                                                                                         |
| Runtime     | 当前配置只创建 database / output / logs / cache；不创建、扫描或删除 vectorstore                                                                              |
| Demo        | 不再清除无人读取的 `CHROMA_PATH`                                                                                                                     |
| 自动化         | 新增 Windows GitHub workflow 与统一本地预检入口                                                                                                        |
| 静态/依赖检查     | ruff / pip-audit / eslint / npm-audit 首份非阻断基线；不自动修复、不上传原始扫描 artifact                                                                        |
| 前端          | 业务页面不变，仅版本元数据 2.0.2 与 `lint` 脚本；`eslint.config.js` 新增                                                                                       |
| 便携包         | 已从候选重建（onedir）；模板改为按文件打包，排除 `__pycache__` 私有路径泄漏                                                                                            |
| 文档          | 本 RESULT；CURRENT\_STATE / DECISIONS / 根 README / 版本索引留待文档 Agent 收口                                                                          |

## 4. 验证状态（D1–D15）

| D   | 场景                          | 命令 / 证据                                                                                                                     | 结果                                                                                                                  |
| --- | --------------------------- | --------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| D1  | 干净基线统一预检                    | `python scripts/precheck.py`                                                                                                | 阻断项全部通过：编译、6 脚本固定计数、前端 build                                                                                        |
| D2  | 计数不匹配假绿反向                   | `precheck._run_blocking_script('_v20_smoke.py', r'PASS=999 FAIL=0')`                                                        | 触发 `_Failure`「汇总计数不匹配」，fail-closed 证实                                                                               |
| D3  | 空临时 runtime 首 import config | `_v14_t7_regression.py` RUNTIME-2                                                                                           | database/output/logs/cache 存在，vectorstore 不存在                                                                       |
| D4  | 历史目录不污染                     | RUNTIME-2 隔离子进程只判临时 runtime                                                                                                 | 通过，不受开发机残留目录影响                                                                                                      |
| D5  | 全新库/升级库/重复迁移                | `_v15_r_rework.py`                                                                                                          | PASS=48 FAIL=0 (total=48)                                                                                           |
| D6  | 旧关键字失败/旧摘要字段                | 签名检查 + `rg vectorstore_dir --glob '!_*.py'`                                                                                 | 签名无 `vectorstore_dir`；活动调用 0；旧关键字 `TypeError`                                                                       |
| D7  | 迁移失败路径 fail-closed          | `_v2_lifecycle_matrix.py`                                                                                                   | 矩阵合计 50 项，失败 0                                                                                                      |
| D8  | 四个 V1.5 单点脚本                | 分别运行 t2/t3/t4/t5                                                                                                            | 35/54/53/40 通过，均 exit 0                                                                                             |
| D9  | CHROMA\_PATH 注入             | 静态核实 + 回归                                                                                                                   | 无活动读取方；仅剩防御剥离 / 测试断言 / 历史归档                                                                                         |
| D10 | 生命周期矩阵完整执行                  | `_v2_lifecycle_matrix.py`                                                                                                   | 50 项，失败 0                                                                                                           |
| D11 | V1.5/V2.0/V2.0.1 回归         | `_v15_r_rework.py`/`_v15_w_rework.py`/`_v15_t6_legacy_exit.py`/`_v20_smoke.py`/`_v2_t5_crud_check.py`/`_v201_validation.py` | 48/37/24/20/15/77 通过，均 0 fail                                                                                       |
| D12 | 前端 build                    | `npm run build`                                                                                                             | dist/index.html 存在；`index-BQ8NVfq6.js` 已从当前源码重建（11:06）；前端 `src` 自 `16ceac2` 无变更故 JS 哈希与早前产物一致；package.json 版本 2.0.2 |
| D13 | 非阻断扫描                       | ruff / pip-audit / eslint / npm audit                                                                                       | 见下方基线                                                                                                               |
| D14 | workflow 反向检查               | 审阅 `windows-ci.yml`                                                                                                         | contents:read；60min 超时；无 artifact；不读 Secret                                                                         |
| D15 | 便携包构建/启动/内容扫描               | `python -m PyInstaller --noconfirm --clean packaging/resume_assistant.spec`                                                 | 构建成功；`ResumeAssistant.exe` size=15972628 B、SHA-256=`9F39874A…B8FA7`；`__pycache__` 目录=0、私有路径 `31117` 命中=0            |

**D13 非阻断基线（首版，不阻断发布，RESULT 记录）**

| 工具        | 版本固定               | 结果                                                 |
| --------- | ------------------ | -------------------------------------------------- |
| ruff      | 0.16.6             | Found 370 errors（退出码 1）                            |
| pip-audit | 2.10.1             | Found 7 known vulnerabilities in 4 packages（退出码 1） |
| ESLint    | 前端 devDependencies | 6 problems (6 errors, 0 warnings)（退出码 1）           |
| npm audit | 前端 devDependencies | 4 vulnerabilities (3 moderate, 1 high)（退出码 1）      |

以上均以「发现问题」显式报告，绝不伪装成零问题；工具缺失/超时/未匹配摘要行会显式标记（见 `scripts/precheck.py` `_run_nonblocking`）。

**D15 构建与隐私复扫**：从冻结候选 `7a7cdfd` 干净重建便携包（`python -m PyInstaller --noconfirm --clean packaging/resume_assistant.spec`），并应用便携修复 `a40c14d`（模板改为按文件打包 `pm_template.docx`/`pm_template.json`，排除 `backend/templates/__pycache__` 及其内嵌开发机绝对路径）。产物 `dist/ResumeAssistant/ResumeAssistant.exe`：size=15,972,628 B，SHA-256=`9F39874AEA9FCC59F0AEBC37C8354B33E5B1589BCCA609948B464CB2B4BB8FA7`；全目录递归扫描 `__pycache__` 目录数=0、私有路径（子串 `31117`）命中=0，无开发机绝对路径泄漏。

### 4.1 精确固定计数（PLAN §6 R4）

| 脚本                        | 期望汇总                                | 实测         | 状态 |
| ------------------------- | ----------------------------------- | ---------- | -- |
| `_v201_validation.py`     | `PASS=77 FAIL=0`                    | 退出码 0，计数匹配 | ✅  |
| `_v15_r_rework.py`        | `PASS=48 FAIL=0 (total=48)`         | 退出码 0，计数匹配 | ✅  |
| `_v20_smoke.py`           | `PASS=20 FAIL=0`                    | 退出码 0，计数匹配 | ✅  |
| `_v2_t5_crud_check.py`    | `PASS=15 FAIL=0`                    | 退出码 0，计数匹配 | ✅  |
| `_v2_lifecycle_matrix.py` | `矩阵合计 50 项，失败 0`                    | 退出码 0，计数匹配 | ✅  |
| `_v14_t7_regression.py`   | `total=15 PASS=12 FAIL=0 SUSPEND=3` | 退出码 0，计数匹配 | ✅  |

**修复前负向证据（PLAN §6 R4）**：RUNTIME-2 修复前，干净环境真实结果为 `11 PASS / 1 FAIL / 3 SUSPEND`（被开发机历史 `vectorstore` 目录误导可假象到 `12/0/3`）。修复后以上 `12 PASS / 0 FAIL / 3 SUSPEND` 是隔离子进程下的真实固定计数，不再受残留目录影响。

### 4.2 四个 V1.5 单点脚本机械适配清单

| 脚本                          | 变更                                                  | 实测               |
| --------------------------- | --------------------------------------------------- | ---------------- |
| `_v15_t2_fact_migration.py` | 删 `_VS_DIR`；`r1`/`r2`/`r5` 三处去掉 `vectorstore_dir=`  | 35 pass / 0 fail |
| `_v15_t3_embedding.py`      | 删 `_VS_DIR`；`run_migrations` 去掉 `vectorstore_dir=`  | PASS=54 FAIL=0   |
| `_v15_t4_selection.py`      | 删 `_VS_DIR`；`_run_migrations` 去掉 `vectorstore_dir=` | PASS=53 FAIL=0   |
| `_v15_t5_rewrite.py`        | 删 `_VS_DIR`；`_run_migrations` 去掉 `vectorstore_dir=` | PASS=40 FAIL=0   |

均为删除旧关键字参数及其专用临时变量，未改动任何业务断言；历史 `v1.5.0` tag 中的原脚本不变。

### 4.3 开发侧结论

**功能验收（开发侧）**：六脚本固定计数全部通过，四个 V1.5 单点脚本与 `_v15_w_rework.py`/`_v15_t6_legacy_exit.py` 运行通过，前端正式 build 成功且产出版本母本 2.0.2；API health、系统状态、模板、写操作安全边界、同源托管等冒烟断言无回退。**此结论为开发侧自证，不等同 T8 独立验收。**

**结构变更验收（开发侧）**：迁移函数签名/摘要字段干净退出（活动调用 0、旧关键字显式失败）；`config.py` 无 vectorstore 符号或创建行为；`run_stub_demo.py` 无 `CHROMA_PATH` 活动兼容分支；CI 固定计数 + 退出码双重判定并经 D2 负向证实 fail-closed；workflow 最小权限/超时/无 artifact。**此结论为开发侧自证，不等同 T8 独立验收。**

## 5. 当前结论

V2.0.2 T1–T7（D1–D15 适用项）已完成，最终代码冻结为 `a40c14d`（含 `7a7cdfd` T1–T6 与便携修复），工作树 clean。所有阻断检查通过，固定计数与退出码双重判定有效，非阻断基线真实可追溯，D15 便携包已重建并隐私复扫干净。剩余交付为：

1. **T8** 独立源码验收 Agent 绑定最终代码冻结 `a40c14d`（含 `7a7cdfd`），分别给出功能与结构变更验收；
2. **T9** 用户最小人工回归、文档收口与发布决定（由用户与文档 Agent 完成）。

开发 Agent 未操作公开 `main`、未推送、未创建 tag。CURRENT\_STATE、DECISIONS、根 README 与版本索引的收口建议留待 T8 通过后由文档 Agent 执行。

## 6. T8 独立源码验收（验收 Agent）

> 执行角色：验收 Agent；未参与 V2.0.2 候选实现、自测或修复，只读检查
> 绑定对象：`a40c14df7d48b322aa761b494cdd08678f18830e`（含 `7a7cdfd` T1–T6；相对已复核 `7a7cdfd` 仅新增 `packaging/resume_assistant.spec` 模板打包变更与 RESULT 记录）
> 验收日期：2026-09-05
> 工作树：新 detached clean 工作树 `resume-assistant-v202-review`（先 @`7a7cdfd`，后复核对象含 `a40c14d`）；祖先含 `v2.0.1` 发布链 `f4e69aa`

### 6.1 spec 变更专项复核（本轮复核面）

用户指定复核 `a40c14d` 相对 `7a7cdfd` 的打包变更：**确认** **`packaging/resume_assistant.spec`** **只打包** **`pm_template.docx`** **/** **`pm_template.json`，不再整目录拷贝** **`templates`**。

- ✅ diff 确认：`datas.append((str(backend_dir / "templates"), "templates"))` 替换为两条按文件打包 `templates/pm_template.docx`、`templates/pm_template.json`；注释说明动机为排除 `__pycache__`（.pyc 内嵌开发机绝对路径）与 `_build_templates.py` 入包。

- ✅ 运行时依赖完整：`backend/config/template_mapping.json` 仅引用 `templates/pm_template.docx` 与 `templates/pm_template.json`（`default: true`），无其他模板文件依赖；`templates/` 下其余内容（`_build_templates.py`、`__pycache__/`）不属运行时资产。

- ✅ 包内容实测：重建后 `dist/ResumeAssistant/_internal/templates/` 仅含 `pm_template.docx`（38468 B）与 `pm_template.json`（6185 B）；全包 `__pycache__` 目录数 = 0、`.pyc` = 0、私有路径子串 `31117` 命中 = 0 —— 原整目录拷贝会带进的开发机绝对路径泄漏已消除。

### 6.2 其余九类复核与回归（基于已复核 `7a7cdfd` + 本轮补充）

| 项                  | 结果                                                                                                                                                                                    |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 候选祖先/clean         | ✅ `a40c14d` 祖先含 `7a7cdfd`→`16ceac2`→`v2.0.1`；验收工作树 clean                                                                                                                              |
| RUNTIME-2 干净环境     | ✅ 修复后隔离子进程只建 database/output/logs/cache、不建 vectorstore，`12/0/3`（3 SUSPEND 为 ARK Key 门禁）                                                                                               |
| 旧迁移契约退出            | ✅ `migrations` 去 `vectorstore_dir`/摘要 `vectorstore` 字段；`run_stub_demo` 去 `CHROMA_PATH`；四 V1.5 脚本仅机械删参、业务断言未弱化；`config` 无 vectorstore 符号/创建                                            |
| 迁移 fail-closed     | ✅ T2 35/0、R-返工 48/0（含备份失败注入）复跑通过                                                                                                                                                      |
| CI 固定计数 + workflow | ✅ precheck 六阻断脚本“退出码 + 固定计数”双重判定；workflow 最小权限 `contents: read`、超时 60、无 secrets/artifact                                                                                              |
| 回归（11 脚本独立复跑）      | ✅ 77/0、48/0、35/0、54/0、53/0、40/0、24/0、20/0、15/0、矩阵 50/0、T7 12/0/3，全部 exit 0                                                                                                            |
| 前端                 | ✅ build 产物 2.0.2 母本；版本 core/package 均 2.0.2；包内 JS 与工作区 `frontend/dist` hash 一致（`9cf13be3…`）                                                                                           |
| D15 便携包            | ✅ 重建 exe 15,972,628 B，SHA-256 `9F39874AEA9FCC59F0AEBC37C8354B33E5B1589BCCA609948B464CB2B4BB8FA7`，与 RESULT §4 记录一致；`__pycache__`=0、私有路径 `31117`=0；包内 `config/template_mapping.json` 就位 |

### 6.3 最终结论

- **T8 独立源码验收：通过。功能验收：通过。结构变更验收：通过。阻断项 0。**

- 绑定精确候选 `a40c14df7d48b322aa761b494cdd08678f18830e`；验收后未修改候选源码、测试、spec、workflow 或构建配置。

- 剩余事项：T9 用户最小人工回归（Windows 便携启动/退出、三页打开、系统状态、V2.0.1 诊断显示、一次生成无回退）→ 文档 Agent 收口 → 用户授权发布（annotated tag `v2.0.2`）。

