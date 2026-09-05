# V2.0.2 RESULT：工程基线与旧迁移契约退出

> 当前状态：**集中返工 F1–F4 已完成，待 T8 独立源码验收**
> 当前阶段：首次候选被发布前复核打回后，开发完成 F1–F4 集中返工并形成新冻结候选；等待验收 Agent 重新独立验收
> 计划日期：2026-09-05
> 批准日期：2026-09-05
> 发布基线：annotated tag `v2.0.1` → `f4e69aae0577ea723e9ef5427b20287add76d06c`
> 计划分支：`version/v2.0.2`
> 首次返工基线 commit：`a40c14df7d48b322aa761b494cdd08678f18830e`（含 `7a7cdfd` T1–T6 与模板按文件打包修复；祖先含 `v2.0.1`/`f4e69aa`，已降为返工基线，不得作为发布候选）
> 新冻结候选 commit：`c413b4ec5a59cf19c85eb9ee2e0d40b55565c721`（F1–F4 集中返工，父提交 `b5da7bc`）

## 1. 当前实际发生的事

V2.0.2 依据已批准 PLAN 完成 T1–T6 实施，并在 `version/v2.0.2` 上形成首次源码候选 `a40c14d`（工作树 clean、`v2.0.1` 为祖先）。独立源码验收曾绑定该候选给出通过结论，用户于 2026-09-05 明确确认人工验收完成；但文档 Agent 在发布前复跑统一预检时发现测试实际访问真实 runtime，违反 PLAN R5。原候选和原独立验收结论因此失效，当前等待集中返工。

首次候选已实现的源码变化仍保留为返工基线：

- **T1** 统一 Windows 预检入口 `scripts/precheck.py` 与 GitHub workflow `.github/workflows/windows-ci.yml`，本地与 CI 共用同一检查逻辑；

- **T2** 旧迁移契约完整退出：`run_migrations()` 与 `_backup_sources()` 删除 `vectorstore_dir` 死参数，迁移摘要删除 `backup.vectorstore` 死字段，并机械适配四个当前 V1.5 单点脚本；

- **T3** RUNTIME-2 改为隔离子进程验证，修正干净环境假通过；删除 `run_stub_demo.py` 对 `CHROMA_PATH` 的防御性清理；

- **T4** 建立 ruff / ESLint / pip-audit / npm audit 四项固定非阻断基线；

- **T5** 后端与前端版本元数据统一更新为 2.0.2；

- **T6** 开发与首次独立验收曾记录全部阻断检查通过，D15 便携包也已重建并隐私复扫干净；发布前复核已证明其中 `_v14_t7_regression.py` 的 `12/0/3` 不具备真实 runtime 隔离，故“全部通过”结论撤销。

## 2. PLAN Task 当前状态

| Task                             | 状态   | 实际结果                                                                                |
| -------------------------------- | ---- | ----------------------------------------------------------------------------------- |
| T1 统一 Windows 预检与 workflow       | 需返工  | 入口与 workflow 已建立，但 `_v14_t7_regression.py` 子进程实际连接真实 runtime；失败输出在 GBK 控制台还可能二次编码异常 |
| T2 迁移死契约退出与脚本适配                  | 完成   | 迁移签名/摘要退出 vectorstore；四个 V1.5 单点脚本机械适配后运行通过                                         |
| T3 RUNTIME-2 与 CHROMA\_PATH 残留修正 | 部分完成 | RUNTIME-2 单项与 Demo 残留已修正，但同一回归脚本后续 CORE/V13 用例仍访问默认真实 runtime，环境闭环未完成               |
| T4 非阻断静态/依赖基线                    | 部分完成 | 四项基线已记录；本地预检错误诊断的 Windows 编码鲁棒性需返工                                                  |
| T5 版本、公开说明与构建输入                  | 完成   | backend/前端版本 2.0.2；health 断言同步                                                      |
| T6 完整验证与便携包                      | 需返工  | 文档复跑稳定得到 `_v14_t7_regression.py` `11/1/3`；便携包证据可保留，但整体阻断检查未通过                       |
| T7 RESULT 与冻结候选交接                | 需返工  | `a40c14d` 降为首次返工基线；修复后必须形成新冻结候选并更新本文                                                |
| T8 独立源码验收                        | 结论失效 | 原验收未发现真实 runtime 写入；新候选必须由未参与返工实现的验收 Agent 重新验收                                     |
| T9 人工确认、文档收口与发布                  | 部分完成 | 用户人工界面验收保留；文档收口和发布阻断，等待返工与重新独立验收                                                    |

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
| 文档          | PLAN 追加发布前复核返工契约，RESULT 与两个版本索引记录打回；CURRENT\_STATE、DECISIONS 和根 README 不写入未经重新验收的 V2.0.2 能力                                                 |

## 4. 首次候选开发与原独立验收记录（已被 §7 推翻）

下表保留首次候选当时提交的证据，便于返工对照；它不再代表当前候选通过状态。凡依赖统一预检、`_v14_t7_regression.py` 或“所有测试均隔离”的结论，均以 §7 发布前复核为准。

| D   | 场景                          | 命令 / 证据                                                                                                                     | 结果                                                                                                                  |
| --- | --------------------------- | --------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| D1  | 干净基线统一预检                    | `python scripts/precheck.py`                                                                                                | **原记录失效**：发布前复跑显示旧回归脚本访问真实 runtime，并得到 `11/1/3`                                                                     |
| D2  | 计数不匹配假绿反向                   | `precheck._run_blocking_script('_v20_smoke.py', r'PASS=999 FAIL=0')`                                                        | 触发 `_Failure`「汇总计数不匹配」，fail-closed 证实                                                                               |
| D3  | 空临时 runtime 首 import config | `_v14_t7_regression.py` RUNTIME-2                                                                                           | database/output/logs/cache 存在，vectorstore 不存在                                                                       |
| D4  | 历史目录不污染                     | RUNTIME-2 隔离子进程只判临时 runtime                                                                                                 | **只证明 RUNTIME-2 单项**；未覆盖同一脚本后续 CORE/V13 数据库读写，不能证明整脚本隔离                                                             |
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

**D15 构建与隐私复扫**：模板按文件打包修复形成最终源码候选 `a40c14d`，随后以 `python -m PyInstaller --noconfirm --clean packaging/resume_assistant.spec` 干净重建便携包。产物 `dist/ResumeAssistant/ResumeAssistant.exe`：size=15,972,628 B，SHA-256=`9F39874AEA9FCC59F0AEBC37C8354B33E5B1589BCCA609948B464CB2B4BB8FA7`；全目录递归扫描 `__pycache__` 目录数=0、私有路径（子串 `31117`）命中=0，无开发机绝对路径泄漏。

### 4.1 精确固定计数（PLAN §6 R4）

| 脚本                        | 期望汇总                                | 实测                                        | 状态 |
| ------------------------- | ----------------------------------- | ----------------------------------------- | -- |
| `_v201_validation.py`     | `PASS=77 FAIL=0`                    | 退出码 0，计数匹配                                | ✅  |
| `_v15_r_rework.py`        | `PASS=48 FAIL=0 (total=48)`         | 退出码 0，计数匹配                                | ✅  |
| `_v20_smoke.py`           | `PASS=20 FAIL=0`                    | 退出码 0，计数匹配                                | ✅  |
| `_v2_t5_crud_check.py`    | `PASS=15 FAIL=0`                    | 退出码 0，计数匹配                                | ✅  |
| `_v2_lifecycle_matrix.py` | `矩阵合计 50 项，失败 0`                    | 退出码 0，计数匹配                                | ✅  |
| `_v14_t7_regression.py`   | `total=15 PASS=12 FAIL=0 SUSPEND=3` | 文档复跑为 `11/1/3`，退出码 1；真实 runtime 数据库只读暴露越界 | ❌  |

**首次修复前负向证据（PLAN §6 R4）**：RUNTIME-2 修复前，干净环境真实结果为 `11 PASS / 1 FAIL / 3 SUSPEND`（被开发机历史 `vectorstore` 目录误导可假象到 `12/0/3`）。首次候选虽然把 RUNTIME-2 单项放入隔离子进程，但没有把整个脚本的 CORE/V13 数据库用例切到 `clean_runtime`；因此首次候选的 `12/0/3` 仍不是满足 PLAN R5 的干净证明。

### 4.2 四个 V1.5 单点脚本机械适配清单

| 脚本                          | 变更                                                  | 实测               |
| --------------------------- | --------------------------------------------------- | ---------------- |
| `_v15_t2_fact_migration.py` | 删 `_VS_DIR`；`r1`/`r2`/`r5` 三处去掉 `vectorstore_dir=`  | 35 pass / 0 fail |
| `_v15_t3_embedding.py`      | 删 `_VS_DIR`；`run_migrations` 去掉 `vectorstore_dir=`  | PASS=54 FAIL=0   |
| `_v15_t4_selection.py`      | 删 `_VS_DIR`；`_run_migrations` 去掉 `vectorstore_dir=` | PASS=53 FAIL=0   |
| `_v15_t5_rewrite.py`        | 删 `_VS_DIR`；`_run_migrations` 去掉 `vectorstore_dir=` | PASS=40 FAIL=0   |

均为删除旧关键字参数及其专用临时变量，未改动任何业务断言；历史 `v1.5.0` tag 中的原脚本不变。

### 4.3 首次候选开发侧结论（已失效）

**功能验收（开发侧）**：六脚本固定计数全部通过，四个 V1.5 单点脚本与 `_v15_w_rework.py`/`_v15_t6_legacy_exit.py` 运行通过，前端正式 build 成功且产出版本母本 2.0.2；API health、系统状态、模板、写操作安全边界、同源托管等冒烟断言无回退。**此结论为开发侧自证，不等同 T8 独立验收。**

**结构变更验收（开发侧）**：迁移函数签名/摘要字段干净退出（活动调用 0、旧关键字显式失败）；`config.py` 无 vectorstore 符号或创建行为；`run_stub_demo.py` 无 `CHROMA_PATH` 活动兼容分支；CI 固定计数 + 退出码双重判定并经 D2 负向证实 fail-closed；workflow 最小权限/超时/无 artifact。**此结论为开发侧自证，不等同 T8 独立验收。**

## 5. 当前结论

V2.0.2 首次候选 `a40c14d` 的旧迁移契约退出、便携模板打包和人工界面结果可作为定向返工基线，但统一预检和测试隔离不满足已批准 PLAN。当前结论为：

- **功能验收：原结论随候选失效，待新候选重新独立验收。** 人工界面验收可暂时保留，因为已发现问题位于测试与预检；若返工触及产品源码、依赖、spec 或便携包则必须重新人工确认。

- **结构变更验收：不通过。** 阻断测试会写入真实 runtime，固定 `12/0/3` 不能证明干净隔离。

- **文档验收：不通过。** 当前已记录返工契约，等待开发与重新独立验收后再收口。

- **发布阻断项：2 类。** 真实 runtime 隔离/清理闭环；默认中文 Windows 控制台错误输出稳定性。

公开 `main`、annotated tag `v2.0.2` 和远端发布核验不得执行。

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

### 6.3 原结论及失效说明

- 原记录为：**T8 独立源码验收通过，功能与结构变更验收通过，阻断项 0。** 发布前复核发现 §7 阻断证据后，该结论失效。

- 原验收绑定精确候选 `a40c14df7d48b322aa761b494cdd08678f18830e`；问题属于该候选已有实现，并非验收后的代码漂移。

- 用户后来已确认人工验收完成，但人工界面结果不能替代测试隔离和源码结构验收。

## 7. 文档 Agent 发布前复核与打回（2026-09-05）

### 7.1 阻断证据

1. `_v14_t7_regression.py` 在进程开头移除 `RESUME_DATA_DIR`；`main()` 虽创建 `clean_runtime`，却没有在第一个 `core.config` / `database.session` 导入前把环境指向该目录。
2. `scripts/precheck.py` 的子进程环境同样移除调用方的 `RESUME_DATA_DIR`。因此 RUNTIME-1 首次导入配置后，CORE-3 和 V13-3 实际使用 Windows 默认 `%LOCALAPPDATA%/ResumeAssistant/database/app.db`，不是输出中展示的 `clean RDD`。
3. 文档工作树在不允许写真实 runtime 的环境中复跑：编译、V2.0.1 `77/0`、V1.5 R `48/0`、V2.0 smoke `20/0`、CRUD `15/0`、生命周期矩阵 `50/0` 均通过；随后 V13-3 向默认数据库插入 `t7_fallback_user` 时触发 `sqlite3.OperationalError: attempt to write a readonly database`，汇总稳定为 `total=15 PASS=11 FAIL=1 SUSPEND=3`、退出码 1。
4. 该失败不是业务断言回归，而是测试越过隔离边界的直接证据。真实数据库可写的开发机上，测试插入/删除固定 User 与 Experience 夹具并得到 `12/0/3`，反而掩盖了真实 runtime 被访问。
5. RUNTIME-2 新增子进程自己的临时目录使用 `shutil.rmtree(..., ignore_errors=True)`；整个脚本的 `clean_runtime` 也没有完整的成功、失败、提前退出和 cleanup 失败闭环，继续违反 PLAN R5。
6. 使用缺少项目依赖的默认中文 Windows Python 触发阻断失败时，子进程 GBK 输出被按 UTF-8 解码为替换字符，父进程再次打印时发生 `UnicodeEncodeError`。虽然退出码仍非零，但本地预检未稳定提供可读错误诊断。

前端 build 在本轮补充复跑中还因文档 Agent 沙箱禁止读取工作区上级目录而失败；独立验收已在正常工作树完成前端 build，因此这条只登记为当前执行环境限制，不作为源码返工项。

### 7.2 当前处理

- 用户于 2026-09-05 给出的人工验收完成结论保留，但不覆盖上述源码阻断。

- 首次候选 `a40c14d` 和绑定它的原 T8 结论失效；开发返工后必须形成新候选，验收 Agent 必须重新检查完整差异与 PLAN §12，而不是只复读原 `12/0/3`。

- 未将 V2.0.2 能力写入 `CURRENT_STATE.md` 或根 README；版本索引状态改为“前置审核打回，待开发返工”。

- ruff 370 项、pip-audit 7 个已知漏洞、ESLint 6 项和 npm audit 4 个漏洞仍按批准 PLAN 作为非阻断基线，不因本次打回伪装为已解决。

**当前结论：打回证据保留；集中返工已完成（见 §8），形成新冻结候选** **`c413b4e`，待 T8 重新独立验收；不得发布。**

## 8. 集中返工记录（F1–F4）与新冻结候选（2026-09-05）

按 PLAN §12 返工契约执行，未改动产品业务、页面、依赖版本、打包 spec 或便携资产；仅修改测试与预检。

### 8.1 修改文件

| 文件                              | 返工项          | 变更                                                 |
| ------------------------------- | ------------ | -------------------------------------------------- |
| `backend/_v14_t7_regression.py` | F1 / F2 / F4 | 全进程隔离 `clean_runtime`；清理生命周期闭合；强制 UTF-8 输出         |
| `scripts/precheck.py`           | F3 / F4      | 默认 runtime 不变外层哨兵；子进程 `PYTHONIOENCODING` 与自身 UTF-8 |

### 8.2 F1–F4 完成情况

| 返工项              | 结果                                                                                                                                            |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| F1 全进程隔离         | `main()` 在任何 `core.*` / `database.*` 导入前写入 `RESUME_DATA_DIR`；CORE-3 / V13-3 在写入前断言 `engine.url.database` 严格等于 `clean_runtime/database/app.db` |
| F2 清理生命周期        | 移除两处 `ignore_errors=True`；`finally` 内 gc 枚举全部 SQLAlchemy Engine 逐一 dispose 后 `rmtree`；清理失败强制非零退出                                              |
| F3 默认 runtime 哨兵 | precheck 在阻断检查前后对默认 `%LOCALAPPDATA%/ResumeAssistant` 做目录集合 + 文件字节 SHA-256 快照；前后不一致即阻断                                                         |
| F4 编码鲁棒性         | 脚本与 precheck 自身 `reconfigure(encoding="utf-8", errors="replace")`；子进程环境注入 `PYTHONIOENCODING=utf-8`；父进程以 `errors="replace"` 读取                 |

### 8.3 返工验证结果

- 精确固定计数：`python scripts/precheck.py` 六脚本退出码 0 且计数匹配；`_v14_t7_regression.py` 稳定 `total=15 PASS=12 FAIL=0 SUSPEND=3`。

- 真实 runtime 哨兵：本机默认 runtime 含 27 个文件，预检前后目录集合与字节 SHA-256 快照一致（未被读取/改写）。

- 负向证据（返工前，§7.1 保留）：受限环境 `11/1/3` 与真实读写越界为本次返工的直接触发证据。

- 非阻断基线：ruff 370、pip-audit 7、ESLint 6、npm audit 4，维持 §4 D13 基线，未伪装清零。

### 8.4 状态更新（取代 §2 中返工前状态）

| Task                             | 状态                                                              |
| -------------------------------- | --------------------------------------------------------------- |
| T1 统一 Windows 预检与 workflow       | 完成                                                              |
| T3 RUNTIME-2 与 CHROMA\_PATH 残留修正 | 完成                                                              |
| T4 非阻断静态/依赖基线                    | 完成                                                              |
| T6 完整验证与便携包                      | 完成（阻断检查全部通过；产品/deps/spec/前端相对 `a40c14d` 未变，故 D15 便携包与人工界面结论仍适用） |
| T7 RESULT 与冻结候选交接                | 完成                                                              |
| T8 独立源码验收                        | 待重新验收（绑定 `c413b4e`）                                             |
| T9 人工确认、文档收口与发布                  | 待重新收口与发布决定                                                      |

**当前结论：F1–F4 返工完成，形成新冻结候选** **`c413b4e`；等待验收 Agent 绑定该候选重新独立验收，阻断项清零前不得发布。**
