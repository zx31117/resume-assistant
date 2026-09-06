# V2.1.0 RESULT：执行记录（初始化）

> 当前状态：待验收（T0 已完成；开发待启动）
> 当前产品基线：已发布 V2.0.2
> 计划 Design Baseline：`DS-002`（源本地 Snapshot `D-002`，主题 A）
> PLAN 批准 commit：`4755ebe5a6a37ef40fc3179c1740eb8b5d22ae27`
> PLAN blob：`45fe3a2c3c6d99098ad2ba7fcb4996f7f7ca7e36`
> 发布结论：不适用

## 1. 本文件用途

本文件从 V2.1.0 立项阶段开始持续记录实际执行、验证证据、计划偏差和验收结论。它不以
PLAN 中的目标代替实现事实；尚未完成的工作必须保持“未开始”或“未通过”，不得提前写入
`CURRENT_STATE.md` 或对外 README。

## 2. 初始化结果

本轮只完成文档准备：

- 根据已发布 V2.0.2、全局决策、V2 需求池和用户已批准的本地设计快照形成正式 PLAN；
- 将本地 `D-002` 原样导入 canonical `DS-002`，完成文件清单和逐文件 hash 验证；
- 明确 V2.1.0 是一次完成核心用户界面整体重构的版本，开发可分 Task，但候选不得新旧混杂；
- 明确用户界面与开发者后台分离、真实链路优先、Mock/Adapter 隔离和三层功能状态；
- 将“生成历史”保留在 V2 需求池，不纳入本版本实施；
- 把 Windows GitHub CI 编码问题列为 T1，要求在候选提交上恢复统一预检绿灯；
- 建立 Design Fidelity、Integration、Regression、Accessibility 与人工场景验收门禁。

本轮未修改产品源码、测试、依赖、配置、构建、数据库、API 或公开产品事实。

## 3. 冻结身份状态

| 项目 | 计划值 | 当前结果 |
|---|---|---|
| 源 Design Snapshot | 本地 `D-002`，Based On `D-001`，主题 A | 已由 Product Owner 批准 |
| Canonical Design Baseline | `docs/design/baselines/V2.1.0/DS-002/` | 已导入；15 个文件 |
| manifest SHA-256 | `7ace7413a81d504a16cdfface2faff50b1623dab0f70ceac4edea1c9717c0cfc` | 源与目标一致 |
| `prototype/index.html` SHA-256 | `548c0ac44a989a550b5f0494f17df15bae9ac27bb524110aaa57ab126cfdd65d` | 源与目标一致 |
| PLAN 批准 commit/blob | Product Owner 批准后记录 | `4755ebe5a6a37ef40fc3179c1740eb8b5d22ae27` / `45fe3a2c3c6d99098ad2ba7fcb4996f7f7ca7e36` |
| 开发候选 commit | 开发结束后冻结 | 尚未产生 |
| 独立验收对象 | 与开发候选完全一致 | 尚未产生 |

导入结果：原清单覆盖的 14 个文件全部匹配；源和目标文件清单一致，15 个文件逐文件 SHA-256
一致；源快照没有被改写。Product Owner 已于 2026-09-06 批准 PLAN，批准 commit/blob 已记录。
设计基线由局部 `.gitattributes` 按 binary 保存，确保跨工作区检出时不发生换行归一化。

## 4. Task 状态

| Task | 状态 | 当前证据或下一门禁 |
|---|---|---|
| T0 设计基线与 PLAN 身份冻结 | 已完成 | `DS-002` 导入、逐文件 hash、批准 commit/blob 均已冻结 |
| T1 Windows CI 编码闭环 | 开发完成，待独立验收 | 编码修复与同类子进程审计已提交（见 §6，commit `7ddfa92`）；本地统一预检 exit 0 六脚本固定计数 + F3 哨兵通过；GitHub Windows CI 真实成功仍待 T11 独立验收时在 CI 侧核对 |
| T2 tokens、adapter、路由与状态骨架 | 开发骨架完成，待独立验收 | 主题 A tokens / typed service 端口与注入 / 全局状态骨架已提交（见 §7，commit `3839402`→`27512ea`）；Profile/System 页面与路由壳层顺延 T3 一并重构 |
| T3 用户界面与开发者后台分离 | 开发骨架完成，待独立验收 | 侧栏壳层 + 普通导航三项 + 隐藏 dev 入口已提交（见 §8，commit `0a16c78`）；SystemPage 能力与安全边界保留 |
| T4 上传、D-038 确认边界与经历管理 | 开发中（T4a 完成） | D-038 provenance 契约与自动整理分流已提交（见 §9，commit `03d9871`）；DS-002 上传/我的经历视觉重构待 T4b |
| T5 一键生成与真实进度 | 未开始 | 等待 T2/T3 |
| T6 内容预览、事实依据与 DOCX 下载 | 未开始 | 等待 T4/T5 |
| T7 隐私、Coming Soon 与缺席能力边界 | 未开始 | 等待 T3 |
| T8 Design Fidelity 与可访问性 | 未开始 | 等待 T3–T7 |
| T9 回归、统一预检与便携包 | 未开始 | 等待 T1–T8 |
| T10 RESULT 与冻结候选 | 未开始 | 等待 T9 |
| T11 独立验收 | 未开始 | 等待 T10 |
| T12 Product Owner 人工验收与发布 | 未开始 | 等待 T11 |

## 5. 开发交接

T0 已完成。Development Agent 启动前必须：

1. 在固定 `<current-workspace>` 同步包含本 RESULT 记录的 canonical 最新基线；
2. 核对批准 commit `4755ebe5a6a37ef40fc3179c1740eb8b5d22ae27` 与 PLAN blob
   `45fe3a2c3c6d99098ad2ba7fcb4996f7f7ca7e36`；
3. 重新验证 `DS-002` 的 14 项 manifest 和两个固定 hash；
4. 按 PLAN 从 T1 开始执行，候选冻结前持续更新本 RESULT 的实施、自测与偏差。

开发、自测或页面存在都不自动等于独立验收通过或发布；状态迁移继续遵守 PLAN 门禁。

## 6. T1 Windows CI 编码闭环（开发实施与自测，候选 G）

> 本节为开发侧实施与自测记录，非独立源码验收。独立验收由 T11 的验收 Agent 绑定最终
> clean 候选执行；本节结论不冒充 T11。

### 6.1 修改文件

| 文件 | 变更 |
|---|---|
| `backend/_v2_lifecycle_matrix.py` | ① 全部嵌套 `subprocess.run` 增加 `encoding="utf-8", errors="replace"` 与 `proc.stdout or ""` / `proc.stderr or ""` 归一化（§8.1.1/2）；② `_run_one`、幂等与句柄占用子进程环境注入 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`（§8.1.3）；③ 新增受控中文负向输出 `_UNICODE_NEGATIVE_OUTPUT`，`SystemExit(字符串)` 用例打印中文+`❌` 后 `sys.exit('boom')`，并断言父进程能读到该 UTF-8 诊断（§8.1.4） |
| `backend/_v14_t7_regression.py` | RUNTIME-2 子进程环境注入 `PYTHONUTF8=1`/`PYTHONIOENCODING=utf-8`，`encoding="utf-8", errors="replace"`（§8.1.3/4） |
| `scripts/precheck.py` | `_strip_env()` 在既有 `PYTHONIOENCODING=utf-8` 基础上补 `PYTHONUTF8=1`，与世界 `cd` 子进程契约一致（§8.1.3） |
| `backend/_v14_release_check.py` | `_run_git` 由裸 `text=True` 改为 `encoding="utf-8", errors="replace"` 并 `(out.stdout or "").strip()`；阻塞脚本同类子进程审计（§8.1.5）发现的一处遗留 |

### 6.2 编码正反向证据

- **反向（修复必要性）**：不设 `PYTHONUTF8` 时 Windows 默认 `preferred encoding=cp936`，对 UTF-8
  中文注释的 `requirements.txt` 运行 pip-audit 报
  `UnicodeDecodeError: 'gbk' codec can't decode byte 0x8e ...`（§8.1.6 触发场景）。
- **正向**：`PYTHONUTF8=1`（+`PYTHONIOENCODING=utf-8`）下 pip-audit 正常读取 requirements 并产生
  真实摘要 `Found 5 known vulnerabilities in 3 packages`（langchain 0.3.30 / langchain-core 0.3.86 /
  langchain-openai 0.3.35；`--no-deps --disable-pip` 模式，网络到 OSV 可达）。漏洞数量如实报告，不自动阻断。
- **矩阵负向断言**：生命周期矩阵 `SystemExit(字符串)` 用例在子进程打印中文+`❌` 后，父进程能读回
  该 UTF-8 诊断行并断言其存在（§8.1.4 通过）。

### 6.3 验证数据

- 生命周期矩阵独立运行：`矩阵合计 50 项，失败 0`（exit 0）。
- `_v14_t7_regression.py` 独立运行：`total=15 PASS=12 FAIL=0 SUSPEND=3`（exit 0；3 SUSPEND 为
  ARK Key 门禁）。
- 完整 `python scripts/precheck.py`（系统 Python 3.10.11，后台运行）：exit 0 —— 编译通过；六阻断脚本
  严格命中固定计数 `77/0、48/0、20/0、15/0、50/0、12/0/3`；前端正式构建通过；F3 真实 runtime 哨兵
  「内容快照一致（空标准骨架目录新增放行）」。
- 非阻断如实报告（不伪装清零）：ruff 370、ESLint 6、npm audit 4、pip-audit 本次超时（>900s）如实标注；
  均为 V2.0.2 既有非阻断基线。

### 6.4 偏差与 CI 状态

- §8.1.8 的「GitHub windows-ci 在 V2.1.0 候选 commit 上成功」：本工作树 push 被禁用且无 `gh` CLI，
  无法在本机直接发起 GitHub runner。已按 workflow 只读约束完成静态审阅（PR / main push / dispatch 触发，
  共用同一 `scripts/precheck.py`）；真实 GitHub run 证据留给 T11 独立验收与文档收口阶段在 canonical 侧核对。
  本地完整预检绿灯是本阶段可提供的确定性证据，不等于 CI 已成功。
- 无 API、数据表/模型、模块职责、业务规则、依赖版本或打包 spec 变化；仅测试/预检/发布检查三类脚本的
  子进程编码与静态审计改动。

## 7. T2 主题 A tokens / typed service / 全局状态骨架（开发实施与自测）

> 本节为开发侧实施记录，非独立源码验收。提交链见 §4 Task 表；均在 `version/v2.1.0`，工作区 clean。

### 7.1 实施内容与提交

| 提交 | 内容 |
|---|---|
| `3839402` T2-a | `frontend/src/styles/tokens.css` 重写为 DS-002 主题 A：canvas #F7F7F5 / surface #FFF / border 系 / primary 系（#1F5C4B、hover #184A3D、focus #2F7E68）/ tint #E7F2EE / 暖铜 --copper #C46A3D / 语义 ok-warn-error-info + wash / 中文字体栈 / 正文 16 与 1.65 行高 / 圆角 8 12 16 / 控件 44 48 / field 最小 220 / sidebar 208 / 断点 900-520 / z 与过渡 token。V2.0.2 旧变量保留为过渡别名（旧 --accent 系映射到 primary 系；暖铜以 --copper 提供），组件逐 T 迁移后删除 |
| `b56d9a2` T2-b-1 | 新增 `frontend/src/services/`：`ports.ts`（AppServices + 六域端口，签名复用 ../api/types wire 类型，不建第二套领域类型）、`real.ts`（组合现有 typed endpoints，无 Mock 分支）、`ServiceContext.tsx`（ServicesProvider + useServices，provider 缺失时抛错 fail closed）、barrel；main.tsx 注入 realServices |
| `017168d` T2-b-2 | GeneratePage 迁移到 `useServices()`（template/system/jd/resume），示范「页面只依赖 typed 端口」闭环 |
| `27512ea` T2-c | 新增 `frontend/src/state/`：AppStateProvider + useAppState——runtime 就绪（首启拉 system.status + refresh，失败显式暴露 error 不假就绪）+ 统一 notices 通道（状态与 UI 解耦，toast 呈现随 T3 壳层） |

前端生产 build 全部通过（strict tsc + vite；最终 53 modules）。

### 7.2 计划偏差与说明

1. **ProfilePage / SystemPage 未在本 Task 切换到 useServices**：与 V2.1.0「一次完成整体重构、候选不得新旧混杂」一致，
   两个页面在 T3-T7 各自重做时切换；GeneratePage 已示范端口依赖与注入闭环。
2. **路由与壳层重排顺延 T3**：DS-002 的 208px 侧栏 + 隐藏开发者后台属于「重构全局壳层，分离普通用户导航与开发者后台」
   （PLAN T3），T2 只完成 tokens/service/全局状态地基，避免提前铺旧路由造成重复返工。
3. **T2 完成标志中的「基础视觉与 DS-002 一致」**：tokens 已为主题 A；逐页视觉对照属 T8 Design Fidelity 门禁，
   随 T3-T7 页面重做后进行。
4. 构建环境限制（非源码问题）：WorkBuddy 安全删除层拦截 `rm -rf`/vite 清空 `frontend/dist`，本地以
   PowerShell `Remove-Item` 先删 dist 再 `npm run build`；不影响 CI（GitHub runner 无此拦截）。

### 7.3 验证数据

- 前端生产 build：`tsc -b && vite build` 通过，产物 dist/index.html + assets（CSS 14.38kB / JS 约 204kB）。
- 类型与 lint 契约：strict tsc 通过；useServices/useAppState 缺 provider 抛错的 fail-closed 分支为显式代码路径。
- 未做运行期联调（需后端 + runtime）；联调与 Design Fidelity 属 T3-T9。

## 8. T3 全局壳层重构（开发实施与自测）

> 开发侧实施记录，非独立源码验收。提交 `0a16c78`（version/v2.1.0，工作区 clean）。

### 8.1 内容

- **AppShell 顶栏 → DS-002 侧栏**：桌面 208px `app-sidebar`（brand + `app-nav`：生成简历/我的经历/个人与隐私，带图标、NavLink 高亮），主区 `app-main` 承载 Outlet；<900px（`--bp-side`）折叠为顶部横排导航，<520px 页头转纵向。
- **开发者后台隐藏**：`/system` 仅通过侧栏脚注 `.dev-link`「开发者后台 ›」进入，不出现在普通一级导航；SystemPage 全部管理/诊断能力与 loopback 同源写安全边界不回退（PLAN §6.1）。
- **路由**：`/` generate、`/profile` experience、`/privacy` privacy、`/system` 隐藏 dev；未知路由回 `/`。
- **PrivacyPage 基础版**：仅陈述已验收的产品隐私事实（本机存储、模型调用、删除边界），不虚构能力；DS-002 精修在 T7。
- **global.css**：`.shell` 改 grid 侧栏布局；新增 app-sidebar/app-nav/nav-item/dev-link 主题 A 样式；移除旧 topbar/brand/nav 布局规则；响应式断点替换为 899/519px。

### 8.2 验证与偏差

- 前端生产 build 通过（strict tsc + vite，54 modules，CSS 14.94kB / JS 206.49kB）。
- 偏差：① 页面正文仍为 V2.0.x 内容与视觉（T4-T7 逐个按 DS-002 重构，GeneratePage 已用 useServices）；② PrivacyPage 为真实事实基础版，非最终信息架构；③「我的经历」侧栏计数（memory-count）待经历域状态落地后接入。

## 9. T4a D-038 来源证据契约与自动整理（开发实施与自测）

> 开发侧实施记录，非独立源码验收。提交 `03d9871`（version/v2.1.0，工作区 clean）。
> 执行口径已由用户确认（2026-09-06）：薄契约、零 DB 迁移；需改库/迁移的来源持久化增强留后续版本。

### 9.1 内容

- **schemas.py**：新增 `ExperienceProvenance`（classification direct|inferred + source_snippets）与 `ExtractExperienceItem(ExperienceItem)`；`ExtractResponse.experiences` 与 `ExperienceExtractionResult.experiences` 改用它。`create/update` 请求体仍为 `ExperienceItem`——experiences 表不加列、迁移不动。fail-closed：缺失/非法 → inferred；direct 无任何 source_snippet → 自动降级 inferred。
- **prompts/experience_extract.py**：指导 LLM 输出 provenance，source_snippets 必须逐字摘自原文；拿不准一律 inferred。
- **api/types.ts**：ExperienceProvenance / ExtractExperienceItem / ExtractResponse 同步。
- **ProfilePage 导入流程分流**（D-038）：extract 返回后 direct 条目自动逐条 create（X-Operation-Group-ID 聚合），进入「我的经历」；自动保存失败项与 inferred 条目进入「需确认」review 列表，展示来源原文引用，用户核对/编辑后保存；「暂不使用」不写库。无半成功假象，失败可重试。
- **global.css**：`.exp-source` 引用样式。

### 9.2 验证与偏差

- 后端 schema 行为单测 8/8（默认 inferred、direct 无证据降级、非法值兜底、响应携带 provenance、ExperienceItem 写库结构未变）；编译与路由导入通过。
- 前端生产 build 通过（strict tsc + vite，54 modules）。
- 偏差：① 未新增 experiences 来源列——条目级原文片段仅 extract 会话内回查，长期溯源依赖既有 Fact.source（用户确认接受，后续版本增强）；② ProfilePage 尚未切换 useServices 与 DS-002 视觉（T4b 页面重构时一并做）；③ 未做真实 LLM 端到端联调（需 Key），交由 T11/人工联调。
