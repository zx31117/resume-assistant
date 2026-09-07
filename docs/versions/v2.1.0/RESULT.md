# V2.1.0 RESULT：执行记录（初始化）

> 当前状态：第二轮返工完成（H2 `a917de2`），待复验（见 §21）
> 当前产品基线：已发布 V2.0.2
> 计划 Design Baseline：`DS-002`（源本地 Snapshot `D-002`，主题 A）
> PLAN 批准 commit：`4755ebe5a6a37ef40fc3179c1740eb8b5d22ae27`（返工契约：`8d9034e6921f5f3d9f601a39bbc108fc009b280c` / blob `93523888d36164ecb5352f49af182d7155b53230`）
> PLAN blob：`45fe3a2c3c6d99098ad2ba7fcb4996f7f7ca7e36`
> 发布结论：不发布（待 H2 复验与 Product Owner 再次 T12）

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
| 开发候选 commit | 开发结束后冻结 | 旧 H `e73f154…`/源码冻结点 `c5612ee…` 已失效；第二轮返工候选 **H2 = `a917de2`**（见 §21） |
| 独立验收对象 | 与开发候选完全一致 | 旧 H T11 结论失效；H2 待未参与返工者复验（PLAN §13.6） |

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
| T4 上传、D-038 确认边界与经历管理 | 开发完成，待独立验收 | D-038 契约与自动整理分流（`03d9871`）+「我的经历」DS-002 布局重构（`fc2870e`）见 §9/§10；真实 CRUD/筛选/搜索/来源/失败路径接通 |
| T5 一键生成与真实进度 | 第二轮返工完成，待复验 | processing 左右结构+单阶段明细回看（R4 `e4e2068`）；真实阶段映射保留，见 §21 |
| T6 内容预览、事实依据与 DOCX 下载 | 第二轮返工完成，待复验 | result 主从+技术摘要退出（R5 `b1a32d1`）；preview/evidence/DOCX 保留，见 §21 |
| T7 隐私、Coming Soon 与缺席能力边界 | 开发完成，待独立验收 | 欢迎双冷启动 + 隐私精修 + Coming Soon/Absent 边界（`b088f26`，见 §13）；无假接通 |
| T8 Design Fidelity 与可访问性 | 第二轮返工完成，待复验 | R1–R6 五状态结构还原 + 1440×900 滚动门禁截图（见 §21）；复验绑定 H2 |
| T9 回归、统一预检与便携包 | 第二轮重建完成，待复验 | precheck exit 0；onedir 重建且包内 frontend 与最终 dist 逐文件 SHA-256 一致（见 §21） |
| T10 RESULT 与冻结候选 | H2 冻结完成，待复验 | H2 `a917de2` + 返工记录见 §21；复验由未参与返工者执行 |
| T11 独立验收 | 历史结论：有条件通过（旧 H） | 绑定旧 H `e73f154…` 的结论在 H2 上失效；H2 待未参与返工者重新复验 |
| T12 Product Owner 人工验收与发布 | 未通过（旧 H）；待 H2 复验 | 打回记录 §20；H2 复验通过后 Product Owner 重新执行 T12 |
| T12-R1 至 R8 | R1–R7 开发完成（待 H2 复验） | R1–R6 `4fb3453`/`e4e2068`/`b1a32d1`/`63e8708`/`a917de2`；R7 precheck+onedir 哈希一致；R8 记录见 §21 |

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

## 10. T4b「我的经历」DS-002 布局重构（开发实施与自测）

> 开发侧实施记录，非独立源码验收。提交 `fc2870e`（version/v2.1.0，工作区 clean）。
> 本 Task 由独立执行体按完整约束清单实施，开发 Agent 复核提交与关键逻辑后记录。

### 10.1 内容

- 页头改「我的经历 · 长期事实库 / 新事实经确认后写入」；actions 提供「上传 PDF」（primary，打开导入 Modal 并聚焦 file input）与「新增经历」（ghost）。
- typeFilter 下拉替换为 全部/工作/项目/教育 四个 tab（value 直接匹配后端真实 type 值域 education/work/project；含 items 真实计数；选中态 --tint + --primary）。不渲染原型中后端不存在的 internship/activity/skill/deferred 假筛选。
- 信息架构：工具条（tab + 搜索 + 刷新）+ 单列列表区域内滚动；每条保留 typeLabel/time/company 摘要、summary_status 徽章、fact_count、编辑/删除。
- 空态区分「无任何经历（含新增/上传 CTA）」与「无匹配（清除筛选）」。
- 删除确认、notice、crudActive 操作轮询展示、导入 review（D-038 需确认列表 + .exp-source 原文引用 + 批量保存/失败重试/全部直入空态）全部原样保留。

### 10.2 验证

- 前端生产 build 通过（strict tsc + vite，exit 0）；git status 干净；提交 `fc2870e` 内容经复核与报告一致。
- 偏差：页面为「工具条 + 单列列表」而非原型 360px 主从双栏（避免窄列表降低可用性，双栏/视觉细调归 T8 Design Fidelity）；ProfilePage 仍直连 endpoints（service 迁移归其后续重做）。

## 11. T5 生成工作台 DS-002 重构（开发实施与自测）

> 开发侧实施记录，非独立源码验收。提交 `39be12f`（version/v2.1.0，工作区 clean）。
> 由独立执行体按完整约束清单实施，开发 Agent 复核提交与关键锚点后记录。

### 11.1 内容

- 输入视图：身份摘要默认一行（姓名·电话·邮箱·所在地，姓名必填缺失行内提示）可展开编辑（仅本次请求）；目标 JD 大文本 ≥60 字自动 `jd.analyze`（600ms 防抖、竞态丢弃、JD 变短清空摘要），chips 展示真实 JDAnalysis 字段；右侧生成前检查只列前端可判定阻断项（姓名缺失 / `counts.experience===0` / JD<60 字），全过显示「事实与输入已就绪」并放行主按钮；保留轻量模板选择（默认 is_default）。
- processing：大标题 + 目标岗位 +「已提交输入 · 保留中」摘要 + 真实已用时 + 4 个用户语言阶段（从你的经历中挑选相关事实 / 受约束起草表达 / 排版装配 / 完成 DOCX 装配）+ 真实阶段明细（OperationTimeline）。
- 4 阶段点亮规则（真实映射，宁可少点亮不猜）：阶段1=`select_experiences`+`select_evidence`、阶段2=`content_generation`、阶段3=`resume_build`、阶段4=`render`+`save_docx`+`response_assembly`（后端 resume_generation_service 真实 stage_code），仅对应 stage 全部 COMPLETED 才点亮。
- 失败：保留输入、后端错误可见（ApiError message/stage）、diagnostic/重试信息若可得则显示；「重新生成」与「返回修改」可用；成功展示真实 download_url 下载 + warnings + 关键 stats。
- 全程 useServices 端口；无假进度/假状态。

### 11.2 验证

- 前端生产 build 通过（strict tsc + vite，exit 0）；git status 干净；提交 `39be12f` 复核通过（关键锚点 13 处）。
- 偏差：生成中「返回修改」在同步长链路未取消能力下置灰（后端无取消/断点，属既有边界，如实呈现）；身份仍未持久化 Profile（后续版本）。

## 12. T6 内容预览 / 逐 bullet 事实依据 / DOCX 下载（开发实施与自测）

> 开发侧实施记录，非独立源码验收。提交 `1e25e10`（version/v2.1.0，工作区 clean）。
> 由独立执行体按完整约束清单实施，开发 Agent 复核提交并独立复跑验证脚本后记录。

### 12.1 内容

- **后端薄透出（业务零改动）**：schemas 新增 `DocPreviewSection/DocPreviewEntry/EvidenceFact`；`ResumeDocxGenerateResponse` 增 `doc_preview` 与 `evidence` 可选字段（默认 None，旧调用方不受影响）。`resume_generation_service` 新增两个只读函数：`_build_doc_preview(resume_doc)`（1:1 投影真实 ResumeDocument 的 profile/work/projects/education/skills/awards）与 `_build_evidence_map(db, fact_ids)`（按 fact_id 只读查 Fact 原文，按 experience_id 聚合）；response_assembly 处装配。per-fact「采用理由」本流水线无真实记录 → reason 字段留空/不返回，**不编造**。
- **前端 result 视图**（GeneratePage 成功态扩展）：纸张样式内容预览区（来自本次真实 doc_preview），明确「内容预览 · 下载的 DOCX 为最终正式文件」，不冒充像素预览；bullet 可选中，依据栏展示真实 evidence（原文/所属经历）；无独立引用时显示「本条没有可回查的独立事实引用」；导出为真实 download_url 下载；预览区区域内滚动，窄屏不横向溢出；doc_preview 为 null 时给友好空态。
- 前端 types 同步（DocPreview/Evidence 类型，可选字段）。

### 12.2 验证

- 后端零密钥验证脚本 `backend/_v21_t6_doc_preview.py`：固定 PASS=15/FAIL=0，exit 0（含 DTO 序列化、默认/携带响应、真实 ResumeDocument 投影、空/内存 SQLite 注入 Fact 边界、py_compile、route import）；开发 Agent 独立复跑一致。
- 前端生产 build 通过（strict tsc + vite，exit 0）；提交 `1e25e10` 复核通过，git status 干净。
- 偏差：无 per-fact 采用理由真实来源（后端选择流程未持久化逐条理由），依据栏如实只展示原文与所属经历；真实 LLM 端到端联调（需 Key）交由 T11/人工联调。

## 13. T7 欢迎双冷启动 / 隐私精修 / Coming Soon 与 Absent 边界（开发实施与自测）

> 开发侧实施记录，非独立源码验收。提交 `b088f26`（version/v2.1.0，工作区 clean）。
> 由独立执行体按完整约束清单实施，开发 Agent 复核提交与锚点后记录。

### 13.1 内容

- **WelcomeGate（路由 / 门控）**：真实调 `experience.list()` 判空——无经历渲染欢迎视图（hero + 双路径卡 + 三原则），有经历渲染既有 GeneratePage；未取到状态前轻量提示，读取失败显示错误与重试，不落假状态。
- 欢迎卡 A「我有一份现有简历」Active → `/profile?import=1`（ProfilePage 首次挂载读一次 query 自动打开导入弹窗并聚焦文件选择）；卡 B「我还没有简历」Coming Soon：仅展开可见说明，不调 API、不落状态。
- **PrivacyPage 精修**：五卡——数据保存位置（本机 SQLite/runtime data root/输出目录/凭据库）、第三方模型调用边界、缺失信息真实规则、三层可靠性说明、删除与清理**真实路径**（逐条删除经历 / 开发者后台清理诊断日志 / 删除数据目录）。后端无清空业务数据 API → 不提供「一键清空」假按钮。
- **边界清点**：普通界面无生成历史/简历记录入口与假列表；GeneratePage 结果区无意图级修改假残留；身份摘要补充「身份自动带入为后续版本功能」诚实说明。未发现假接通，无新 API 调用。
- 新增 `pages/WelcomeGate.tsx`；改 App.tsx / ProfilePage / PrivacyPage / GeneratePage / global.css。

### 13.2 验证

- 前端生产 build 通过（strict tsc + vite，exit 0）；提交 `b088f26` 复核通过（锚点命中），git status 干净。
- 偏差：无（视觉细调与像素对照归 T8）。

## 14. T8 Design Fidelity / 响应式 / 可访问性开发验证

> 开发侧验证记录，非独立验收；视觉最终判定归 T11 独立验收与 T12 人工验收。
> 无源码改动（未发现需修复 bug），因此本节无新提交；证据文件在 `validation-artifacts/t8/`（不入库）。

### 14.1 环境与截图（agent-browser / Chromium，FastAPI 同源托管）

- 主实例 8000（真实 runtime：159 经历 / 291 facts / 迁移齐全 / LLM Key 已配置）；空实例 8001（迁移后 0 经历，用于冷启动欢迎）。
- 截图 19 张：welcome 双卡+Coming Soon 展开（8001）、/profile?import=1 导入弹窗与空列表（8001）、generate 就绪态、JD≥60 自动分析 chips、processing 真实 4 阶段、experience / privacy / dev 三页、响应式 4 分辨率（1280×800 / 1024×768 / 390×844 / 320×568）。
- 端到端真实生成证据：首次触发成功产出 `resume_demo-user_pm_template.docx`（39,935 B）。

### 14.2 结果

- 响应式：四分辨率均无横向溢出（scrollWidth ≤ innerWidth：1280/1024 相等，390→375，320→305）；<900px 侧栏折叠为顶部导航。
- 键盘/语义：Tab 首焦点入侧栏链接，沿主区推进；snapshot 可访问性树 nav/heading/link/button/textbox 完整；生成/经历页输入均有 label/aria-label/placeholder，无可访问名缺失的按钮，SVG 均 aria-hidden 或由文本命名。
- 语义对照 DS-002：整体框架/主题一致；结构性差异（单列列表 vs 360px 双栏、真实类型筛选值域、processing 无原型流式侧栏、records 反向不实现）逐条记录于 notes/fidelity.md。
- 偏差/限制：axe 自动扫描未运行（CDN 不可达，如实记录不视为通过）；第二次真实生成在 content_generation 阶段长时间未收尾（首次成功证明链路可用，疑似 LLM 长请求/限流）——已记 notes/bugs.md，建议验收时以 LLM 可用窗口复测。

## 15. T9 回归、统一预检与便携包（开发实施与自测）

> 开发侧实施记录，非独立源码验收。提交 `bda5870`（版本 2.1.0）、`e7ad146`（D-038 白名单 payload 修 2 处 lint）。

### 15.1 版本元数据（2.1.0）

- `backend/core/version.py` APP_VERSION → 2.1.0（单一真源）；运行期断言脚本 `_v20_smoke`/`_v201_validation`（含消息文本）→ 2.1.0；`frontend/package.json` → 2.1.0。
- 根 README 版本标识由文档 Agent 发布收口更新（开发侧不写，记录偏差）。

### 15.2 统一预检（完整，两轮）

- 首轮仅前端构建因环境安全删除层拦截 vite 清空已存在 `frontend/dist` 而失败（tsc 与 transform 已通过，CI 无此问题）；`PowerShell Remove-Item` 删 dist 后第二轮**阻断检查全部通过，precheck exit 0**：Python 编译、六阻断脚本固定计数全部匹配（含 2.1.0 版本断言后 _v201 77/0、_v20 20/0 等）、前端正式构建通过、F3 默认 runtime 哨兵一致。
- 报告项（非阻断，如实记录）：ruff 383（较基线 370 +13：T4a/T6 新增验证脚本）、pip-audit 执行超时（>900s，同 V2.0.2 环境限制）、ESLint 11（10 errors + 1 warning；较基线 6 增加：react-hooks v7 `set-state-in-effect` 规则在 T5–T7 页面的既有模式，未为此重构页面逻辑；本轮已修复开发引入的 2 处 unused-vars）、npm audit 4（3 moderate + 1 high，同基线）。

### 15.3 便携包（PyInstaller onedir）

- `python -m PyInstaller --noconfirm --clean packaging/resume_assistant.spec` 成功（2m15s），产物 `dist/ResumeAssistant/`（git 忽略，不入库）。
- 结构校验 4/4：入口 exe、_internal/frontend/dist/index.html、templates/pm_template.docx、config/template_mapping.json。
- 包内隐私扫描：无开发机绝对路径、无真实 API Key/凭据、无 `.env`/数据库/输出 docx、无输入简历内容样本；仅第三方依赖的正常公共证书（certifi/grpc CA bundle）与库内 `your-api-key` 占位字符串。

## 16. T10 RESULT 收口与候选身份（开发侧）

- 开发候选 commit：**`e7ad146`**（version/v2.1.0，工作区 clean；祖先链覆盖 T1–T9 全部提交）。
- **视觉重塑补做（2026-09-07）**：global.css 组件层按 DS-002 视觉规格系统性重写（`2997160`）+ SystemPage 整页重构为 dev 视图（`c5612ee`），最终候选更新为 **`c5612ee`**（祖先含视觉重塑全部提交）。详细见 §17。
- 开发侧偏差汇总（截至候选）：① T1 GitHub Windows CI 真实 run 需 canonical 侧/验收阶段核对；② 根 README 版本标识待发布收口；③ D-038 未持久化 experiences 来源列（零迁移口径，用户已确认）；④ per-fact 采用理由无真实来源（不编造）；⑤ axe 未运行/生成长链路二次不稳定（T8 bugs 记录）；⑥ 报告项（ruff/ESLint/pip-audit/npm audit）基线如实记录如 §15。**原偏差②（SystemPage 视觉）已通过 T8-1/T8-2 补做消除。**
- T11（独立验收）与 T12（Product Owner 人工验收 + 发布）为角色门禁，非开发 Agent 可执行。

## 17. 视觉重塑补做（DS-002 完整落地）

> 由用户质询触发：原"页面按 DS-002 重塑"的表述对主用户流程页面成立，但组件层与 SystemPage 视觉仍带 V2.0 旧风，未达 PLAN「完全重构现有页面、交互流程、组件和视觉表现」承诺。补做后候选更新为 `c5612ee`。

### 17.1 三块交付

- **T8-1 组件视觉层**（`2997160`，`frontend/src/styles/global.css` 仅此文件，577+/478-）：按 DS-002 冻结基线系统性重写——按钮 44/48（圆角 8/12/16）、primary 深松绿/hover/ghost/secondary、input/textarea 44 高 1px border-strong + `:focus` 2px `--focus` 焦点环 + 2px offset、badge/tag 药丸 wash+语义字+彩色边框（状态非纯色）、notice ok/warn/error wash、exp-item/kv/table/diag/modal/empty、欢迎双卡、隐私/结果/依据栏；保留 `:focus-visible`、reduced-motion、899/519 响应式断点。删除 JSX 未引用的死类；类名与 JSX 全部兼容（仅改样式不破坏结构）。
- **T8-2 dev 后台重构**（`c5612ee`，`frontend/src/pages/SystemPage.tsx` 仅此文件，475+/329-）：从 V2.0 单页管理台改为 DS-002 dev 视图——顶部 PageHeader「开发者后台」+ 隐藏入口说明；双列网格承载「Provider 配置」「数据库与索引」+ 整行宽「最近运行活动」「诊断」；操作详情改模态（Esc/遮罩关闭）；Key 掩码、空态/失败可见、轮询区 aria-live 保留。**所有原能力零回退**（连接配置/测试激活/迁移/重建/重试/活动列表/详情弹窗/日志流/清空），同步从直连 endpoints **切换到 useServices() 端口**（config/system）。
- **逐页视觉抽查**：在主 runtime 重启同源服务并用 agent-browser 截 `validation-artifacts/t8/shots/v2_generate.png` / `v2_experience.png` / `v2_dev.png`，对比新视觉与冻结基线：组件规格一致、卡片 1px 边框+白底+圆角 12、状态药丸+ dot、焦点环深松绿，整体达到"克制职业工作台"；未发现需大改的明显视觉偏差。

### 17.2 验证

- 前端生产 build（strict tsc + vite）：两处均 exit 0。
- git 状态：两提交后 `git status --porcelain` 空；分支 ref 已固化 `.git/refs/heads/version/v2.1.0 → c5612ee`。
- 原 §16 偏差②（SystemPage 视觉）已消除；其他偏差继续保留如 §16。
- 体验：前端产物已由前轮 precheck 重建（组件类名兼容，旧 dist 无需另作处理）；若需在干净环境重跑 precheck（验证视觉重塑不破坏六脚本），可由验收阶段在 CI 触发（本地重跑约 17 分钟）。

## 18. 验收交接（给 T11 独立验收 Agent 的路径与结果同步）

> 本节由开发 Agent 在候选冻结时写入，供未参与本候选实现的验收 Agent 启动；验收结论在验收后由
> 文档 Agent/验收记录追加，开发侧不预填“通过”。参与本候选实现、自测或源码修复的开发 Agent
> 不得兼任验收 Agent（docs/README.md §“独立验收”）。

### 18.1 验收入口与绑定对象

- 候选 commit：**`c5612ee`**（分支 `version/v2.1.0`）；验收绑定对象 = 与开发候选完全一致
  （工作树需 clean；若验收环境检出后有任何差异，以差异为验收阻断项并记录）。
- 只读材料（候选冻结后不再由开发修改）：
  - 本 RESULT（执行/验证/偏差；§6–§17 为开发侧自测记录，非独立验收结论）
  - `docs/versions/v2.1.0/PLAN.md`（批准 commit `4755ebe5a6a37ef40fc3179c1740eb8b5d22ae27` / blob `45fe3a2c3c6d99098ad2ba7fcb4996f7f7ca7e36`）
  - 冻结设计基线 `docs/design/baselines/V2.1.0/DS-002/`（manifest `7ace7413a81d504a16cdfface2faff50b1623dab0f70ceac4edea1c9717c0cfc`；prototype SHA-256 `548c0ac44a989a550b5f0494f17df15bae9ac27bb524110aaa57ab126cfdd65d`）
  - 产品事实基线 `docs/CURRENT_STATE.md`（V2.0.2 已验收状态，V2.1.0 新能力在验收通过前不得进入）
- 候选提交链（供逐 Task 对照）：`7ddfa92`(T1) → `3839402`→`27512ea`(T2) → `0a16c78`(T3) → `03d9871`/`fc2870e`(T4) → `39be12f`(T5) → `1e25e10`(T6) → `b088f26`(T7) → `bda5870`/`e7ad146`(T9 版本与修正) → `2997160`/`c5612ee`(视觉重塑 T8-1/T8-2)；祖先含 RESULT 收口记录提交（`cf3cf0f`、`906cd98` 等，不改变产品源码）。

### 18.2 本版本实际全局变化（验收“结构变更”对象）

| 类别 | 变化 |
|---|---|
| API / Schema | `backend/api/schemas.py`：新增 `ExperienceProvenance`/`ExtractExperienceItem`（extract 响应条目带 D-038 证据，零 DB 迁移）；新增 `DocPreviewSection/DocPreviewEntry/EvidenceFact` 并给 `ResumeDocxGenerateResponse` 加可选 `doc_preview`/`evidence`（默认 None，旧调用兼容）。其余既有 API 未变 |
| 数据表 / 迁移 | **无变化**（未新增 experiences 来源列；D-038 证据仅在 extract 会话内，长期溯源依赖既有 Fact.source） |
| 提示词 | `backend/prompts/experience_extract.py`：输出携带 provenance（direct/inferred + source_snippets），LLM 拿不准一律 inferred |
| 模块职责（后端） | `resume_generation_service` 新增只读 `_build_doc_preview`/`_build_evidence_map`；extract 路由/提取器逻辑不变 |
| 前端结构 | 新增 `src/services/`（typed 端口+注入）、`src/state/`（AppState）、`pages/WelcomeGate.tsx`；重构 AppShell（208px 侧栏+隐藏 dev 入口）、全部页面（Generate/Profile/Privacy/System）信息架构与视觉；`styles/tokens.css` 主题 A、`global.css` 组件视觉 DS-002 化；路由含 /privacy 与隐藏 /system |
| 配置 / 依赖 | 版本元数据 2.1.0（`backend/core/version.py`、`frontend/package.json`）；无新增运行依赖 |
| 验证/脚本 | 新增 `backend/_v21_t6_doc_preview.py`（零密钥 15/0）；历史门禁 `_v20_smoke`/`_v201_validation` 运行期版本断言文本同步 2.1.0 |
| 对外文档 | 根 README 版本标识由文档 Agent 发布收口更新（开发未写） |

### 18.3 验证总表（开发侧状态；验收结论由验收 Agent 记录）

| 验收对象 | 开发侧证据 | 功能验收 | 结构变更验收 |
|---|---|---|---|
| T1 编码闭环 / CI | §6；本地 precheck 绿灯；GitHub CI run 待 canonical 侧核对 | 待独立验收 | 见 §18.2（无子进程编码结构变化之外变更） |
| T2 tokens/service/state | §7；build 通过 | 待独立验收 | 待独立验收 |
| T3 壳层/开发者后台分离 | §8 | 待独立验收 | 待独立验收 |
| T4 上传/D-038/我的经历 | §9/§10；schema 行为 8/8 | 待独立验收 | 待独立验收 |
| T5 生成工作台/真实进度 | §11 | 待独立验收 | — |
| T6 预览/依据/DOCX | §12；`_v21_t6_doc_preview.py` 15/0 | 待独立验收 | 待独立验收 |
| T7 欢迎/隐私/边界 | §13 | 待独立验收 | — |
| T8 视觉/无障碍 | §14/§17；截图 `validation-artifacts/t8/` | 待独立验收 | 待独立验收 |
| T9 版本/预检/便携包 | §15；precheck exit 0 | 待独立验收 | 待独立验收（版本元数据） |
| T10 收口 | §16/本 § | 待独立验收 | — |

已知待验收阶段核对项：GitHub Windows CI 真实 run（本工作树不可 push，需 canonical 侧/CI 记录）；LLM 端到端真实生成在 LLM 可用窗口复测（§14 bugs 记录：曾一次成功、一次 content_generation 长挂）；axe 自动扫描未运行（CDN 不可达）。

## 19. T11 独立验收结论（2026-09-07）

### 19.1 执行角色与绑定身份

本轮由未参与 V2.1.0 候选实现、自测、源码修复或开发结论编写的独立验收 Agent 执行，只在
聊天中返回报告，未修改仓库或远端。报告绑定：

- 固定 review 路径：`<review-workspace>`；
- 验收交接 commit H：`e73f1547d8764e7e60ee57407c06c07db29a4f95`；
- 源码与视觉实现冻结点：`c5612eebd7f02db021da2eab28c074a98a1985e0`；
- `c5612ee..e73f154` 仅修改本 RESULT，源码、测试、配置、依赖和构建内容一致；
- PLAN blob、DS-002 manifest 与 prototype SHA-256 均与 §3 的冻结值一致；
- 验收开始和结束时 review 均为 detached H，tracked、index、untracked、ignored clean。

### 19.2 验收结论与独立证据

| Gate | 结论 | 独立验收摘要 |
|---|---|---|
| 功能 | 通过 | 欢迎双冷启动、PDF 导入、D-038 分流与确认、经历 CRUD、JD 分析、一键生成、真实阶段、内容预览、事实依据和 DOCX 下载边界成立 |
| 结构变更 | 通过 | 用户界面与开发者后台分离；typed service/Real API 边界成立；无正常路径 Mock 回退；零 DB 迁移与事实真源边界符合批准口径 |
| Design Fidelity | 有条件通过 | DS-002 信息架构、主题 A、侧栏、核心页面、响应式、键盘和焦点语义成立；最终视觉判断仍归 T12；axe 未独立运行 |
| Integration | 有条件通过 | 页面到 Real API、WelcomeGate、JD 竞态、stage 映射、preview/evidence/DOCX 与开发者后台链路成立；真实 LLM 二次稳定性待受控复测 |
| 回归 | 通过（有限独立复跑） | 隔离副本中六个阻断脚本命中 `77/0、48/0、20/0、15/0、50/0、12/0/3`，`_v21_t6_doc_preview.py` 为 `15/0`，前端 `npm ci` 后正式 build 和 PLAN 范围 Python 编译通过 |
| 隔离与隐私 | 通过 | 未使用真实 `.env`、数据库、凭据或用户输出；未发现本机路径、真实 Key 或用户数据入库；临时副本和 runtime 已清理 |

验收 Agent 没有把开发侧自测冒充独立证据：本轮未把完整 `scripts/precheck.py` 作为单一入口重跑，
也未独立重建 PyInstaller onedir 包；前者由各阻断脚本、前端 build、编译和隔离检查分别覆盖，
后者仅核对 spec/结构并引用 §15.3 开发证据。该限制不推翻 T11 的源码、功能和结构结论，但必须
与未确认的远端 CI 一起保留到发布门禁。

### 19.3 未完成门禁与非阻断项

1. 候选 H 尚无可独立确认的 GitHub Windows CI 成功 run；不得以本地预检代替，也不得未经用户
   授权由 Agent 推送。该项不推翻 T11 源码结论，但阻断正式发布。
2. 开发侧真实 LLM 生成曾一次成功产出 DOCX，另一次在 `content_generation` 长时间未结束；验收侧
   未读取真实凭据，保持 SUSPEND，须在受控 LLM 可用窗口复测。
3. axe 自动扫描未运行；静态语义、键盘与焦点检查通过，但最终视觉和无障碍判断仍归 T12。
4. P0：0；P1：0。P2 包括未确认 CI、LLM 稳定性 SUSPEND、axe 缺失、如实报告的非阻断 lint/audit、
   三份已明确排除且非本版本引入的 V1.x 存档脚本编译问题，以及未形成并行视觉结构的 tokens 过渡别名。

### 19.4 文档 Agent 判定

接受独立验收 Agent 的“有条件通过”结论：T11 不要求立即回到开发返工，但 V2.1.0 仍保持
“待验收”，不更新 `CURRENT_STATE.md`、根 README 或公开版本声明。下一阶段为 T12 Product Owner
人工验收；正式发布前还必须获得绑定候选 H 的 GitHub Windows CI 成功证据、完成受控真实 LLM
稳定性复测，并由 Product Owner 对最终视觉与无障碍结果作明确判断。任何相关源码、测试、依赖、
配置或构建变化都会使本轮结论失效并要求重新冻结候选和独立复验。

## 20. T12 Product Owner 人工验收打回（2026-09-07）

### 20.1 实际反馈

Product Owner 在 `<current-workspace>` 运行真实生成流程并提供三个页面截图，明确判定人工验收
不通过：

1. **生成开始后仍显示重复输入卡**：页面继续占用大块空间复述姓名、目标岗位和 JD。要求进入
   processing 后立即移除该视觉区；输入只在状态层保留，用于失败恢复。
2. **生成阶段与明细纵向堆叠**：四阶段总览在上、全部真实 operation 明细在下，用户必须滚动且
   同时面对过多技术信息。要求改为左右结构：左侧四阶段，右侧每次只展示一个选中阶段；新阶段
   开始时自动切换，旧阶段明细按阶段保留并可通过点击左侧已开始/已完成阶段回看。
3. **结果页存在大量非核心信息**：重复页头和输入摘要、文件名复述、黄色原始技术警告，以及
   页数/匹配经历/渲染经历/模板统计占据首屏，真实简历结果被推到下方。要求普通结果页全部删除
   这些区域，只保留真实预览、事实核对入口和完成任务所需操作；技术诊断继续留在隐藏后台。
4. **滚动与信息纪律不合格**：生成主流程必须严格控制为一屏完成，不用滚轮寻找当前信息；任何
   与当前动作无直接关系的内容都不应出现在普通用户页面。

该反馈已转写为 PLAN §13 的集中返工契约。它覆盖并替代旧候选在 processing/result 布局上的
冲突实现，不改变真实阶段、事实来源、DOCX、用户/后台分离和其他已批准产品边界。

### 20.2 额外发布包阻断

文档 Agent 在提供人工验收入口前核对发现，当前 onedir 包并非最终候选界面：

| 对象 | 前端资产 | 生成时间 | 结论 |
|---|---|---|---|
| 最终源码构建 `frontend/dist` | `index-C5qpaybd.js` / `index-t64tPsmK.css` | 2026-09-07 17:10 | 包含 T8-1/T8-2 后构建 |
| 现有 onedir 包内 `frontend/dist` | `index-B-7P6qZU.js` / `index-D5nuZd0I.css` | 2026-09-07 16:38 | 早于最终视觉构建，文件名、大小和 SHA-256 均不同 |

逐文件证据：最终源码 JS/CSS 分别为 245101/23969 bytes，SHA-256 为
`97bd896d35e82f9b2b8ae97919bc695991c7b514f082cdfbb5f8a07e80af7b66` /
`47ea47b066a3ca04207808eb97ebe922261e64c9f521194fffac0e197700bbc6`；现有包内 JS/CSS 分别为
242859/22478 bytes，SHA-256 为
`46ebc06a6723728fd344edcf9826a2fd785477ce56c907cb2f39d2e7de9d37d3` /
`e813a1b342ba1031dee8d54ab5167eca1700a42258165a0e8cb66b72720da3c8`。

因此 `dist/ResumeAssistant/ResumeAssistant.exe` 不能代表冻结候选，不得用于最终 T12 或发布。
返工后必须重新执行前端 build 与 PyInstaller onedir，并证明包内前端目录与最终
`frontend/dist` 文件清单及逐文件 SHA-256 一致。

### 20.3 状态与下一交接

- Product Owner 于 2026-09-07 直接给出并批准本轮页面返工要求；承载 PLAN §13 返工契约的固定
  commit 为 `dd381585aa73858f3ab3531da1319e9afbc1a2b1`，对应 PLAN blob 为
  `d6b5e71cc4b62763baa7cfed688df11986cec529`。开发返工必须同时核对原 PLAN 批准身份和本补充身份；
- 当前版本状态改为“需修正”，发布结论为“不发布”；
- 不更新 `CURRENT_STATE.md`、根 README、公开 main 或 tag；
- 不要求推翻已通过的事实链、D-038、服务 Adapter 或用户/后台分离，只集中修改 PLAN §13；
- 开发 Agent 在固定 `<current-workspace>` 完成 T12-R1 至 R7，更新本 RESULT 的实施、反向退出、
  无滚动截图、测试和新包证据后，冻结新候选 H2；
- 文档 Agent 接收 H2 后更新固定 `<review-workspace>`；未参与返工的验收 Agent 重新执行定向源码、
  Design Fidelity、Integration、回归和包内资产一致性验收；
- Product Owner 最后重新执行 T12。新候选与再次人工验收均完成前，本轮不进入发布流程。

## 21. T12 五状态原型还原补充（2026-09-07）

Product Owner 进一步提供五个设计状态，明确人工验收的本意是“按冻结原型还原”，不是由开发
重新解释页面结构。PLAN §13 已据此细化；本节记录实际需求边界：

1. **无简历初始页**：结构与 `DS-002/previews/welcome-theme-A.png` 一致；左侧整张“我有一份
   现有简历”卡单击直接打开系统文件选择器，同时接受 PDF 拖放；右侧“我还没有简历”暂时不可
   点击，不进入演示或产生假状态。
2. **上传解析页**：采用原型的左右布局。左侧展示文件解析完整流程和真实状态，右侧每次显示一个
   选中阶段的用户可理解事件；新阶段开始时自动切换，旧阶段输出按阶段保留，可点击左侧已开始或
   已完成阶段回看。未开始阶段没有伪造明细，多个阶段不会同时纵向展开。
3. **身份/JD 页**：左侧按原型保留身份摘要、目标岗位与 JD 输入、真实分析结果；右侧按原型保留
   生成前检查、产品说明和生成动作。V2.1.0 已固定模板，模板徽标、下拉框和用户选择全部退出。
4. **生成处理页**：继续使用与上传解析相同的左右视觉语法；左侧为完整四阶段，右侧为单阶段
   明细查看器。真实新阶段开始时自动切换，用户可从左侧返回查看旧阶段历史；进入 processing 后
   不再显示身份/JD 输入摘要。
5. **结果预览页**：采用 `DS-002/previews/result-theme-A.png` 的主从布局，左侧真实简历纸张，右侧
   固定“依据 / 修改”与下方导出；依据接真实事实，修改保持 Coming Soon/disabled，不假接通。
   删除旧候选的重复输入、技术告警和统计摘要。

滚动口径同时得到澄清：普通桌面主流程应尽量一屏完成；一页简历优先通过 `fitPaper` 适配而不
要求滚轮。内容超长或较小视口确实无法保持可读时，只允许左侧简历预览受控滚动或分页，右侧
依据/修改/导出必须固定可见，不允许跟随整页滚走。该口径替代 §20 中“任何内部滚动均禁止”的
概括性解释。

本补充不改变真实能力边界：流式输出只能展示真实 stage/operation 的安全产品化摘要，不显示模型
私有推理；D-038 确认、失败可见、输入保留、真实依据、DOCX 和隐藏开发者诊断必须继续成立。
除上述真实能力映射外，页面状态、左右比例、组件顺序、文案层级、固定区域和首屏信息均以原型
为准，开发 Agent 不再自行改版。

五状态结构最初冻结于 `200bc7a379bdf526c4dc6f2035bbc8d4af462881`；Product Owner 随后澄清
阶段历史必须保留并可回看，修正后的当前返工 PLAN commit 为
`8d9034e6921f5f3d9f601a39bbc108fc009b280c`，PLAN blob 为
`93523888d36164ecb5352f49af182d7155b53230`。该身份取代 §20.3 和本节较早的返工 PLAN identity，
作为开发 T12-R1 至 R8 的当前唯一补充契约；最初批准 PLAN commit/blob 继续作为版本初始基线保留。

## 22. 第二轮返工实施（T12-R1 至 R7，开发侧；候选 H2）

> 开发侧实施与自测记录，非复验结论。返工契约：PLAN §13 + §21 补充（8d9034e/93523888）。
> 旧 H（e73f154/c5612ee）的 T11 Design Fidelity / Integration / 发布包结论在本候选上失效；
> 复验须绑定 H2 = `a917de2`（version/v2.1.0，工作区 clean）。

### 22.1 R1–R6 五状态结构还原（提交与内容）

| 步骤 | 提交 | 内容 |
|---|---|---|
| R3 身份/JD 页 | `4fb3453` | generate input 态按原型 .gen-grid/.gen-main/.gen-rail 还原（身份摘要一行+可编辑、JD 自动分析 chips）；删除模板徽标/下拉/用户选择 state（模板仅后端 is_default 内部传参） |
| R4 生成处理页 | `e4e2068` | processing 改 .process-shell 左右：左四阶段 radiogroup（roving tabindex/方向键、等待/当前/完成/失败、可回看已开始阶段），右单阶段 PhaseStream/FailurePanel（按 phase.codes 过滤真实 stage 事件，自动切换）；删除「已提交输入」摘要卡与全量 operation 同屏堆叠（OperationTimeline 从 processing 退出） |
| R5 结果页 | `b1a32d1` | result 主从：左纸张预览（ResultPaperPreview + fitPaper 等比、仅 .preview-scroll 受控滚动），右 sticky「依据/修改/导出」（依据=真实 bullet/fact；修改=disabled+「即将上线」不假接通；下载 Active）；删除重复页头/输入摘要/文件名复述/warnings/页数-匹配-渲染-模板统计/OperationTimeline |
| R1+R2 欢迎与上传解析 | `63e8708` | 欢迎左卡整卡=上传 drop zone（单击/拖放即选择 PDF，不跳独立页），右卡 disabled/aria-disabled 无假操作；新增 `/upload` 视图（UploadPage）按 .process-shell 左右：左真实阶段（读取文件/本机解析/结构化提取/分类整理，radiogroup 可回看），右单阶段 PhaseOutput（仅真实结果事实，无虚构中间流）；D-038 分流与错误重试迁移保留；ProfilePage 旧导入弹窗删除，「上传 PDF」进入同一视图 |
| R1 微调 | `a917de2` | 欢迎右卡 CTA 文案「进入演示 →」→「即将上线 · 暂不可用」（disabled 占位语义） |

阶段→真实调用映射（诚实，无伪造流）：①读取文件=本地 File 事实；②本机解析=`POST /api/resume/upload` 成功→文本长度/首行摘要；③结构化提取=`POST /api/experience/extract`→条数+direct/inferred 计数；④分类整理=provenance 分流→direct 自动落库、inferred 待确认。失败显示真实错误并可重试；不暴露迁移/Embedding/资源类型/私有思维链。

### 22.2 R6 滚动与固定门禁（1440×900，agent-browser 实测）

截图：`validation-artifacts/t8/shots/h2_welcome.png`、`h2_generate_blocked.png`、`h2_generate_ready.png`、`h2_processing.png`、`h2_result.png`。DOM 尺寸（`document.documentElement.scrollHeight/Width` @1440×900）：

- welcome（空 runtime）：sw=1440、sh=900 → 无页面滚动
- generate blocked / ready：sw=1440、sh=900 → 无页面滚动
- processing（真实生成中）：sh=900 → 无页面滚动（.process-shell 存在）
- result（真实生成成功）：整页 sh=900 无滚动；右栏 computed position=sticky；仅左侧 `.preview-scroll` 受控滚动（fitPaper 生效）

### 22.3 R7 重建验证（precheck 与发布包）

- 完整统一预检：**阻断检查全部通过，precheck exit 0**（Python 编译、六阻断脚本计数匹配、前端正式构建、F3 默认 runtime 哨兵一致）。报告项：ruff 383；ESLint 17 errors（较前 11 增 6，全部为 react-hooks v7 `set-state-in-effect`/`purity` 规则噪音，抽查确认非真实缺陷，沿用既有"不为此重构页面逻辑"决策）；npm audit 4；pip-audit 本次返回 7 known/4 packages（网络波动，非阻断）。
- onedir 重建：`python -m PyInstaller --noconfirm --clean packaging/resume_assistant.spec` 成功（首跑因安全层拦截旧包删除失败，PowerShell 删 `dist/ResumeAssistant` 后成功）。
- **包一致性**：`_internal/frontend/dist` 与最终 `frontend/dist` 文件清单一致（index.html + assets JS/CSS，3 文件），逐文件 SHA-256 **MATCH**：index-CqKehJQh.js `e63cdb7f…`、index-DhZa9fFP.css `0cd110e0…`、index.html `eba1101c…`。旧包阻断（§20.2）已消除。

### 22.4 偏差与遗留（如实）

- 欢迎右卡仍显示描述文案但整体灰化 disabled（aria-disabled、无 onClick 副作用）；「即将上线·暂不可用」占位。
- UploadPage `/upload` 无文件直达时的空态未做专项截图（正常路径经欢迎左卡进入）；复验可覆盖。
- result 右下显示「已生成 <operation_id 短码>」作为状态标识保留（非技术统计）。
- 复验范围（未参与返工者绑定 H2 执行）：T12-R1–R7、五状态结构与冻结预览一致、真实阶段映射、诊断保留、滚动/固定边界、包内资产一致性；随后 Product Owner 重新执行 T12。
