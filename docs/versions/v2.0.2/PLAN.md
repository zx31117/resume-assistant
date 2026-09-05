# V2.0.2 PLAN：工程基线与旧迁移契约退出

> 文档角色：V2.0.2 实施范围与验收契约
> 当前状态：已获用户批准；开发 Agent 可按本 PLAN 开始实施
> 计划日期：2026-09-05
> 批准日期：2026-09-05
> 发布基线：annotated tag `v2.0.1` → `f4e69aae0577ea723e9ef5427b20287add76d06c`
> 计划分支：`version/v2.0.2`
> 后续边界：V2.1.0 保留 React + TypeScript + Vite，完全重构现有页面、交互流程、组件和视觉表现；不在本版本提前实施

## 1. 背景与目标

V2.0.1 已完成本地流程可观测性并正式发布。V2.0.2 不新增业务能力，目标是先建立可重复的 Windows 工程检查，再完整退出生产迁移中的旧 vectorstore 兼容契约，并修正一条会被开发机历史目录掩盖的干净环境假通过。

PLAN 前只读扫描已确认：

- `run_migrations()` 与备份函数仍接收但不读取 `vectorstore_dir`，生产 API 与 CLI 均不传该参数；
- 迁移摘要中的 `backup.vectorstore` 恒为 `None`，当前后端与前端无消费方；
- 当前 `config.py` 不定义、不读取、也不创建 vectorstore 目录；正常导入只建立 `database`、`output`、`logs`、`cache`，`diagnostics` 由 tracker 生命周期建立；
- `_v14_t7_regression.py` 的 RUNTIME-2 仍错误要求空 runtime 自动出现 `vectorstore` 目录。开发机残留目录可令它意外通过，干净环境真实结果为 `11 PASS / 1 FAIL / 3 SUSPEND`；
- `run_stub_demo.py` 仍主动清除无人读取的 `CHROMA_PATH`，属于可删除的活动兼容残留；
- 四个 V1.5 单点验证脚本仍传 `vectorstore_dir`，未进入 V2.0.1 当前聚合入口，但从当前 checkout 运行会在删参后 `TypeError`；
- 仓库目前没有 GitHub workflow；现有零真实密钥验证可以组成 Windows CI，但必须同时校验退出码和固定汇总计数。

本版本完成后，应当得到一套本地与 GitHub 共用的最小检查入口，并使当前生产代码、活动 Demo、当前回归和当前 checkout 中保留的可执行验证资产都不再依赖旧迁移参数或旧目录假设。

## 2. 范围

### 2.1 必须完成

1. 建立 Windows 最小 CI 与同源本地预检入口；
2. 删除迁移函数中的 `vectorstore_dir` 死参数和摘要中的旧 `vectorstore` 死字段；
3. 修正 RUNTIME-2 干净环境目录断言，证明 vectorstore 目录不会由当前配置创建；
4. 删除 `run_stub_demo.py` 中无读取方的 `CHROMA_PATH` 防御性清理；
5. 机械适配当前 checkout 中仍传旧参数的四个 V1.5 单点验证脚本，使其继续可执行；
6. 建立 ruff、ESLint 与依赖漏洞扫描的固定非阻断基线；
7. 更新 2.0.2 版本元数据、便携包、RESULT 和公开文档说明；
8. 完成开发验证、独立源码验收和用户最小人工回归。

### 2.2 明确不做

- 不重构现有前端页面、路由、组件、CSS、信息架构或视觉语言；
- 不提前实现 V2.1.0 的 ErrorBoundary、Field、Button、Modal 或界面分层方案；
- 不改变 Experience / Fact、两层选材、生成、Builder、Renderer 或 Embedding 业务规则；
- 不引入新的向量后端，不删除或迁移用户目录中的历史空文件夹；
- 不把 ruff、ESLint 或漏洞发现一次性全部修复，不执行全仓自动格式化；
- 不升级 LangChain、Provider 或其他无关依赖；
- 不反向改写历史 tag、历史 PLAN/RESULT 或其当时事实；
- 不将版本验证产物写入 `docs/versions/v2.0.2/`，该目录只能保留 PLAN 与 RESULT。

## 3. 已确认决策

### 3.1 当前脚本与历史事实的边界

历史 tag 和历史 PLAN/RESULT 保留当时事实，不移动、不重写。当前 checkout 中的 Python 文件属于当前源码树；本版本允许对四个 V1.5 单点脚本做最小机械适配，只删除旧关键字参数及其专用临时变量，不改变原业务断言。适配后仍以当前代码运行；历史 `v1.5.0` tag 中的原脚本自然保持不变。

### 3.2 CI 触发与平台

- GitHub workflow 在 pull request、公开 `main` 更新和手动运行时触发；
- 活动版本候选合并前必须本地执行同一检查入口，不强制为了触发 CI 而推送每个活动分支；
- 首轮只使用 `windows-latest`、Python 3.10 和受支持的 Node LTS；
- workflow 使用最小 `contents: read` 权限、明确超时，不读取仓库 Secret，不上传数据库、日志、DOCX、环境文件或其他运行 artifact；
- 测试不调用真实 LLM/Embedding，但依赖安装和漏洞数据库查询需要网络，不能宣称整个 CI 离线。

### 3.3 必检与报告分离

编译、零密钥回归、固定计数、前端正式构建、隔离与清理属于阻断检查；ruff、ESLint 和依赖漏洞扫描首版只生成非阻断报告。非阻断步骤执行器自身失败、配置无效或报告无法生成时必须可见，不能被吞成“零问题”。

### 3.4 生命周期矩阵

`_v2_lifecycle_matrix.py` 提供退出码仲裁、cleanup 失败、真实 runtime 哨兵、环境恢复、导入副作用、重复 cleanup 和句柄释放等负向证据，不以普通 smoke/CRUD 单跑替代。本版本保持已验收的 **50 项 / 0 失败**契约，不为节省少量 CI 时间改写其编排结构；后续只有在有独立等价证明时才能缩减。

## 4. 计划中的全局变化

| 范围 | 计划变化 |
|---|---|
| 用户 API | 路由、请求和正常响应不变；迁移摘要不再包含无意义的 `backup.vectorstore` |
| Python 内部契约 | `run_migrations()` 与备份函数不再接受 `vectorstore_dir`；旧关键字调用显式失败 |
| 数据库 | 无 schema 和业务数据迁移；SQLite `fact_embeddings` 唯一向量持久化不变 |
| Runtime | 当前配置继续只创建有效目录；不创建、扫描或删除用户历史 vectorstore 目录 |
| Demo | 不再处理无人读取的 `CHROMA_PATH` 环境变量 |
| 自动化 | 新增 Windows GitHub workflow 和一个可由本地直接执行的统一预检入口 |
| 静态/依赖检查 | 固定工具版本和首份非阻断基线；不自动修复、不上传原始扫描 artifact |
| 前端 | 业务页面不变，仅验证 TypeScript 与正式 build；版本元数据更新为 2.0.2 |
| 便携包 | 从冻结候选重新构建，版本、前端资产和隐私边界一致 |
| 文档 | 根 README 说明已验收档案、需求池与未批准草稿的区别；验收后同步当前状态和索引 |

## 5. 集中实施任务

| Task | 执行内容 | 依赖 | 完成标准 |
|---|---|---|---|
| T1 | 建立统一 Windows 预检入口与 GitHub workflow | 无 | 本地和 GitHub 调用同一检查逻辑；权限、超时、触发器和无 artifact 边界明确 |
| T2 | 删除迁移死参数与死摘要字段，适配四个当前 V1.5 单点脚本 | T1 基线 | 新签名生效；旧关键字失败；当前生产/验证活动调用为零；四脚本可运行 |
| T3 | 修正 RUNTIME-2，删除 Demo 的 `CHROMA_PATH` 清理残留 | T1 | 干净 runtime 精确验证有效目录且 vectorstore 不存在；开发机历史目录不能制造假通过 |
| T4 | 建立 ruff、ESLint 和依赖漏洞非阻断基线 | T1 | 工具版本、范围、数量、分类和延期理由可重复；执行异常不伪装成无问题 |
| T5 | 更新版本元数据、公开说明和便携构建输入 | T2-T4 | API/health/package/前端为 2.0.2；根 README 不把草稿写成已实现能力 |
| T6 | 完成迁移失败路径、全量适用回归、前端 build、包扫描和资源清理 | T2-T5 | §7 矩阵通过；无真实数据、Key、私有路径或测试残留 |
| T7 | 完成 RESULT、冻结候选 commit 和交接 | T6 | RESULT 记录精确命令、计数、偏差、两类开发侧结论和 clean commit |
| T8 | 独立源码验收 | T7 | 验收 Agent 绑定冻结 commit，功能与结构变更分别通过，阻断项 0 |
| T9 | 用户最小人工回归、文档收口与发布决定 | T8 | 现有三页和 V2.0.1 诊断无可见回退；用户确认；文档一致 |

依赖主链：`T1 → T2/T3/T4 → T5 → T6 → T7 → T8 → T9`。T2、T3、T4 可在 T1 基线冻结后并行，但必须合并到同一候选重新执行完整预检。

## 6. 阻断要求

### R1 干净 runtime 不得依赖历史残留

RUNTIME-2 必须在全新临时 runtime 下执行。导入配置后应存在当前规定的目录，不应出现 vectorstore；预先在开发机真实 runtime 留有同名目录不得影响测试结果。测试不得读取或删除真实 `%LOCALAPPDATA%` 数据。

### R2 旧迁移契约完整退出

新调用无旧参数时，全新库、既有库、备份和重复运行正常；传入 `vectorstore_dir` 必须显式失败；迁移摘要不再返回 `vectorstore` 字段。生产代码、API、CLI、Demo、当前回归和已适配的当前验证资产不得再把旧名称作为活动配置或调用契约。

说明“独立 vectorstore 已退出”的注释和遗留退出测试可以保留；必须区分当前边界说明、反向断言与活动兼容行为，不能要求文本全仓绝对零匹配。

### R3 迁移安全不回退

备份、迁移应用、后置核验或资源释放失败继续 fail-closed；成功、异常、提前退出和重复 cleanup 后资源均释放。删除死字段不能改变 SQLite 备份位置、核对逻辑、schema version、Fact reconciliation 或 Embedding 状态。

### R4 CI 不能只看退出码

每个阻断脚本必须同时满足退出码和固定汇总计数。至少固定：

| 脚本 | 期望汇总 |
|---|---|
| `_v201_validation.py` | `PASS=77 FAIL=0` |
| `_v15_r_rework.py` | `PASS=48 FAIL=0 (total=48)` |
| `_v20_smoke.py` | `PASS=20 FAIL=0` |
| `_v2_t5_crud_check.py` | `PASS=15 FAIL=0` |
| `_v2_lifecycle_matrix.py` | `矩阵合计 50 项，失败 0` |
| `_v14_t7_regression.py` | `total=15 PASS=12 FAIL=0 SUSPEND=3` |

任何少跑、额外 SUSPEND、输出格式消失或非零退出都必须使阻断入口失败。RUNTIME-2 修正前干净环境的 `11/1/3` 必须作为修复前负向证据保存到 RESULT 摘要，不能再用开发机残留目录得到的 `12/0/3` 充当前基线。

### R5 CI 与本地运行数据隔离

所有测试使用临时 `RESUME_DATA_DIR`、临时 SQLite 和虚构数据。成功、失败、KeyboardInterrupt、SystemExit、导入失败和 cleanup 失败均验证资源边界；测试不得读取、覆盖或清理真实 runtime。日志和长输出不进入版本目录或发布包。

### R6 非阻断报告必须可追溯

RESULT 记录工具与规则版本、扫描范围、问题总量和类别、执行是否成功及延期理由。既有问题可以不阻断 V2.0.2，但本版本新增问题不得被混入旧基线；原始报告保留在临时运行环境，不成为长期文档真源。

### R7 前端与业务无回退

前端源码除版本或自动化所需配置外不做页面重构。三页、同源安全、Experience CRUD、生成、迁移、Embedding 维护、V2.0.1 操作阶段/日志/诊断和便携启动退出均须保持原行为。

## 7. 开发验证矩阵

| # | 场景 | 必须证明 |
|---|---|---|
| D1 | 从 `v2.0.1` 干净基线执行统一预检 | 无真实 Key/数据即可完成；固定计数全部匹配 |
| D2 | 人为令一个阻断命令非零、少跑一项或增加 SUSPEND | 本地入口和 workflow 均失败，不出现假绿 |
| D3 | 空临时 runtime 导入 config | 当前有效目录存在，vectorstore 不存在，真实 runtime 哨兵不变 |
| D4 | 预先在真实或相邻位置放置同名历史目录 | RUNTIME-2 仍只判断隔离临时 runtime，不被残留污染 |
| D5 | 无旧参数的全新库、V2.0.1 升级库和重复迁移 | schema、备份、摘要与资源释放正确 |
| D6 | 传入旧 `vectorstore_dir`、读取旧摘要字段 | 旧关键字显式失败；摘要字段不存在，调用方不依赖 |
| D7 | 备份、应用、核验、session close、engine dispose 分别失败 | 保持 fail-closed，原异常与 cleanup 结果可判定 |
| D8 | 四个当前 V1.5 单点脚本完成机械适配后运行 | 不再传旧参数，原业务断言不弱化；历史 tag 未变 |
| D9 | `CHROMA_PATH` 注入环境后运行当前 Demo/服务 | 当前代码不读取或处理它；Demo 与真实 runtime 隔离仍通过 |
| D10 | 生命周期矩阵完整执行 | 恰好 50 项、0 失败；退出码、残留、哨兵和环境恢复契约不弱化 |
| D11 | V1.5 八组全矩阵与 V2.0/V2.0.1 当前回归 | 原事实链、三页、诊断与安全无回退；精确计数写入 RESULT |
| D12 | `npm ci`、TypeScript 与正式前端 build | 构建成功，产物版本为 2.0.2，无页面功能变更 |
| D13 | ruff、ESLint、Python/Node 依赖扫描 | 工具正常执行并形成固定基线；发现项非阻断但不可消失或伪装 |
| D14 | workflow 权限、触发、超时、Secret、artifact 与日志反向检查 | 最小权限；无真实凭据、用户正文、绝对私有路径或运行产物上传 |
| D15 | Windows 便携包构建、启动、退出和内容扫描 | 版本 2.0.2；前端资产一致；无测试、数据库、日志、Key 或私有路径 |

真实 LLM/Embedding 正向调用不进入无密钥 CI。它们在本版本没有行为修改，使用 V2.0.1 已验收结果与回归证明；若实现触及模型适配、生成或 Embedding 业务代码，必须停止并扩展 PLAN、重新安排对应真实或受控 Stub 验证。

## 8. 独立源码验收要求

本版本修改迁移内部契约、运行环境验证和发布自动化，属于结构与基础设施变更。T8 必须由未参与实现、自测或源码修复的验收 Agent 独立完成。

验收至少复核：

1. 发布候选确实以 `v2.0.1` 为祖先，工作树 clean；
2. RUNTIME-2 在干净临时 runtime 由失败转为通过，且不访问真实 runtime；
3. `config.py` 没有 vectorstore 符号或创建行为，Demo 没有 `CHROMA_PATH` 活动兼容分支；
4. 迁移死参数与死摘要字段退出，API/CLI 正常，旧关键字失败；
5. 四个当前 V1.5 单点脚本只做机械适配，业务断言没有弱化；
6. 迁移备份、核验、资源释放和失败路径继续 fail-closed；
7. CI 固定计数、少跑/额外 SUSPEND 负向、最小权限、超时和无 artifact 边界有效；
8. 非阻断扫描的工具失败与“发现问题”可区分，基线未伪装为零；
9. V1.5/V2.0/V2.0.1 回归、前端 build、便携启动退出与隐私扫描通过。

验收结论必须绑定冻结 commit，并分别写“功能验收”和“结构变更验收”。验收后任何源码、测试、workflow、依赖、配置或构建变化都会使结论失效并需重验。

## 9. 用户人工确认

本版本没有新页面，用户不需要检查 CI 源码，也不应为了验收在真实数据库上反复迁移。独立源码验收通过后，人工确认只需：

1. Windows 便携应用正常启动和退出；
2. 生成工作台、履历库、本地系统三页可打开；
3. 本地系统状态可读取；
4. V2.0.1 的运行活动、阶段耗时、后台日志和诊断摘要仍可显示；
5. 需要时完成一次普通生成，确认无可见回退。

## 10. 开发交接要求

开发 Agent 在 RESULT 中必须记录：

- 基线 tag/commit、分支、冻结候选 commit 和 clean 状态；
- T1-T7 实际完成情况及所有计划偏差；
- API、内部函数契约、数据模型、runtime、依赖、自动化、前端和便携包的实际变化；
- 修复前 RUNTIME-2 干净环境 `11/1/3` 与修复后固定计数；
- D1-D15 精确命令、退出码、PASS/FAIL/SUSPEND 和未执行原因；
- 四个 V1.5 单点脚本的具体机械适配清单及运行结果；
- 必检与非阻断报告分离后的结果，不能把 advisory 发现写成全部通过；
- 功能验收与结构变更验收的开发侧结论，不得写成独立验收；
- 便携包大小、SHA-256、前端资产绑定和隐私反向扫描；
- 建议同步到 CURRENT_STATE、DECISIONS、根 README 或版本索引的已验证事实。

开发 Agent 不操作公开 `main` 或正式 tag。机读报告、长日志、数据库、DOCX 和临时产物留在临时目录或 runtime data root，不在版本目录新增第三份文档。

## 11. 完成定义与发布门禁

V2.0.2 只有同时满足以下条件才可标记完成：

- T1-T7 与 D1-D15 适用项完成，所有阻断检查通过；
- 干净 runtime 不创建 vectorstore，RUNTIME-2 不受开发机历史目录影响；
- 旧迁移参数、旧摘要字段和 Demo 的活动 CHROMA_PATH 兼容分支退出；
- 当前四个 V1.5 单点脚本完成机械适配，历史 tag/文档未改；
- CI 以固定总量和退出码双重判定，少跑、额外 SUSPEND 和 cleanup 失败均不能假绿；
- 非阻断扫描基线真实、可重复且不掩盖工具执行失败；
- V1.5/V2.0/V2.0.1 回归、前端 build、便携包和隐私扫描通过；
- 功能验收与结构变更独立验收均通过，绑定同一冻结候选；
- 用户完成最小人工回归并明确确认；
- 文档 Agent 完成 RESULT、CURRENT_STATE、两个版本索引和必要公开文档收口；
- 用户再次确认发布后，才可快进公开 `main` 并创建 annotated tag `v2.0.2`。

## 12. 2026-09-05 文档 Agent 发布前复核返工补充

> 性质：首次候选 `a40c14d` 的集中返工契约；补充已批准 PLAN R4/R5 的可执行边界，不覆盖或弱化原 PLAN
> 当前状态：前置审核打回，待开发返工；原 T8 独立验收结论失效

### 12.1 已确认根因

首次候选只把 `_v14_t7_regression.py` 的 RUNTIME-2 单项放进隔离子进程。脚本自身仍在开头移除 `RESUME_DATA_DIR`，`main()` 创建 `clean_runtime` 后也没有在首次导入 `core.config` / `database.session` 前启用它；`scripts/precheck.py` 又会从子进程环境移除外部 `RESUME_DATA_DIR`。因此 CORE-3 与 V13-3 实际连接 Windows 默认 `%LOCALAPPDATA%/ResumeAssistant/database/app.db`，会在真实 runtime 建表并插入、删除固定测试夹具。

真实数据库可写时会产生 `12 PASS / 0 FAIL / 3 SUSPEND` 假通过；在禁止写真实 runtime 的环境中，V13-3 稳定触发 `sqlite3.OperationalError: attempt to write a readonly database`，实际为 `11 PASS / 1 FAIL / 3 SUSPEND`。此外，RUNTIME-2 的嵌套临时目录仍用 `ignore_errors=True` 吞 cleanup 失败，整个脚本也没有覆盖成功、失败、提前退出与 cleanup 失败的释放闭环。

统一预检还有一项 Windows 本地错误诊断缺陷：子进程默认 GBK 输出被固定按 UTF-8 解码后产生替换字符，父进程向 GBK 控制台打印时可能再触发 `UnicodeEncodeError`。非零退出没有假绿，但错误原因无法稳定、可读地呈现。

### 12.2 集中返工任务

| Rework | 必须完成 | 依赖 | 完成标准 |
|---|---|---|---|
| F1 | 让 `_v14_t7_regression.py` 全进程使用独立临时 runtime | 无 | 在任何 `core.*` / `database.*` 导入前冻结隔离路径；所有 SQLite、output、logs、cache 均位于该路径；输出的 `clean RDD` 与实际 settings/engine 一致 |
| F2 | 闭合该脚本及 RUNTIME-2 嵌套临时目录的资源与清理生命周期 | F1 | 成功、断言失败、导入异常、KeyboardInterrupt、SystemExit 和重复 cleanup 均释放 session/engine/文件句柄；cleanup 失败非零退出，不使用 `ignore_errors=True` 吞错 |
| F3 | 给统一预检增加真实 runtime 不变的外层证明 | F1-F2 | 以隔离的“默认 runtime 陷阱”或等价哨兵证明：即使默认数据库已存在、只读或含哨兵，六个阻断脚本也不读取、不建表、不写入、不删除它；测试后字节/hash 与目录集合不变 |
| F4 | 修正默认中文 Windows 控制台的失败输出编码 | 无 | 子进程与父进程编码契约明确；中文失败输出、无效字节和缺依赖场景均可读、非零退出且不出现二次 `UnicodeEncodeError` |
| F5 | 更新 RESULT、形成新候选并重新独立验收 | F1-F4 | 精确记录修改文件、负向证据和新 commit；验收 Agent 绑定新候选复核完整差异、原九项与本节全部要求 |

依赖顺序：`F1 → F2 → F3`，F4 可并行；随后统一执行 F5。不得借返工修改产品业务、页面、依赖版本、打包 spec 或便携资产；如确需越界，先更新 PLAN，并使既有便携包与人工验收结论重新进入待验状态。

### 12.3 开发侧正反向验证

1. 在进程外准备一个与源码树分离的“默认 runtime 陷阱”，其中数据库文件只读并带字节级哨兵；不把它当测试数据库使用。运行 `_v14_t7_regression.py` 后必须仍为精确 `total=15 PASS=12 FAIL=0 SUSPEND=3`，陷阱目录与哨兵 hash 完全不变。
2. 在 V13-3 写入前记录或拦截 SQLAlchemy engine URL，证明路径严格位于本次 `clean_runtime/database/app.db`；不得仅依据控制台打印的 `clean RDD` 推断。
3. 分别注入配置导入失败、数据库写失败、普通断言失败、KeyboardInterrupt、SystemExit、session close/engine dispose 失败、临时目录删除失败和重复 cleanup；主业务失败与 cleanup 失败均可判定，真实 runtime 不变，清理失败不能只打印 warning。
4. RUNTIME-2 的嵌套子进程正常、异常、超时和清理失败均有断言；残留检测失败时整体非零退出。
5. 从默认中文 Windows `cmd` 或 PowerShell 运行一个会输出中文并失败的受控子脚本，再运行缺少一项前置依赖的负向场景；统一预检必须返回非零、保留原错误摘要且不出现乱码导致的二次异常。
6. 修复后执行完整 `python scripts/precheck.py`：六脚本退出码与固定计数全部匹配，前端 build 通过；advisory 基线继续真实报告，不要求本轮清零。
7. 重新执行四个机械适配脚本、生命周期矩阵、V1.5/V2.0/V2.0.1 回归与隐私扫描。若产品源码、依赖、spec 和前端资产相对 `a40c14d` 均未变，可用静态 diff 与包内 hash 证明便携包/人工界面结论仍适用；否则重建便携包并重新人工确认。

### 12.4 新候选交接与重新验收门禁

- 开发 RESULT 必须把 `a40c14d` 标为首次返工基线，记录新冻结候选 commit，不得覆盖本次打回证据；
- 交接必须附 F1-F4 的正向、反向和真实 runtime 哨兵结果，以及完整预检固定计数；
- 验收 Agent 不得只在可写的真实用户 runtime 上复跑。验收环境必须让默认路径成为不可写陷阱或使用等价连接拦截，独立证明所有数据库访问只发生在临时 runtime；
- 原 T8 结论不能复用。新候选的功能验收与结构变更验收必须分别给出结论，阻断项为 0 后才能恢复文档收口；
- 用户已经完成的界面人工验收暂时保留。仅当返工严格限制在测试/预检且静态证明产品与包不变时无需重做；任何产品、依赖、spec 或便携包变化都使人工结论失效。

### 12.5 F3 哨兵口径补充（文档 Agent，2026-09-05 已获用户批准）

> 性质：对 §12.2 F3“测试后字节/hash 与目录集合不变”的明确化补充。此补充不放行任何文件变化或真实 runtime 数据访问，只消除全新机器上标准空目录初始化造成的误报。

全新 Windows 机器或 CI runner 可能尚无默认 runtime。`core.config` 首次导入会初始化标准骨架目录；即使六个阻断脚本的实际数据工作全部位于独立临时 runtime，也可能因此在默认 runtime 下新增空的 `database`、`output`、`logs`、`cache` 或 `diagnostics` 顶层目录。若机械要求目录集合完全不变，这类无文件、无数据访问的初始化会产生假阻断。

F3 哨兵因此只放行一种变化：**新增的顶层空标准骨架目录**。允许名称限定为 `database`、`output`、`logs`、`cache`、`diagnostics`，且 after 快照中该目录整棵子树必须为空。以下任一变化仍必须 fail-closed：

- 任何文件新增、删除或内容变化；
- 任何既有目录删除；
- 任何非标准目录新增，包括 `vectorstore`；
- 标准骨架目录非空，或其下新增任何子目录。

该补充不改变 F3 的数据隔离目标：六个阻断脚本不得读取、建表、写入或删除默认真实 runtime。验收须同时覆盖已有默认 runtime 的字节/hash 不变，以及空默认 runtime 陷阱只产生上述允许的空骨架目录。
