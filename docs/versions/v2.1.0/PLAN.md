# V2.1.0 PLAN：冻结 DS-002 并完成整体界面重构

> 文档状态：Product Owner 已于 2026-09-06 批准；开发启动前必须核对批准 commit/blob
> 当前产品基线：已发布 V2.0.2，annotated tag `v2.0.2` → `78bb909c18ca28e45b54406536aa326887caa1ca`
> 当前源码验收基线：`eb4bd30a2d4c7aac62865924c7b8eab363d282ee`
> 源 Design Snapshot：本地 `D-002`，原型 v1.3.0，Based On `D-001`，主题 A
> 计划 canonical Design Baseline：`DS-002`
> 源 manifest SHA-256：`7ace7413a81d504a16cdfface2faff50b1623dab0f70ceac4edea1c9717c0cfc`
> PLAN 身份：用户批准时由 Documentation Agent 记录批准 commit 与本文件 blob；不得在本文件中回填其自身提交 SHA

## 1. 目标与版本判断

V2.1.0 是当前本地产品的首个整体前端设计基线。版本必须一次完成核心用户界面的整体重构，
使后续小版本以微调为主；开发可以分 Task 和 commit，但最终候选不得形成新旧页面混杂的状态。

本版本同时完成两类工作：

1. 按用户批准的 `DS-002` 一比一实现新的信息架构、视觉、文案、交互和页面状态；
2. 修复 V2.0.2 发布后由 GitHub Windows CI 暴露的编码闭环缺口，恢复统一预检的可信绿灯。

核心用户流程：

~~~text
无经历：欢迎 → 上传 PDF → 真实解析 → 直接抽取进入我的经历 / 推断项待确认
                                         ↓
有经历：身份摘要 + JD → 生成岗位简历 → 真实进度 → 内容预览与事实依据 → 下载 DOCX
~~~

本版本不实现“生成历史”。它是需要保留的后续能力，已进入 V2 需求池；`DS-002` 中相关页面
只作为未来设计参考，不进入本 PLAN 实施矩阵。

## 2. 批准依据与冻结身份

### 2.1 适用决策

- D-001：经历是资产，简历是输出；
- D-019：身份信息使用显式来源，不从经历、模板或 AI 推断；
- D-027：图形交互层只薄包装核心链路，不建立第二业务真源；
- D-029：本地管理接口保持同源写安全边界；
- D-031：长操作使用统一可观测性机制；
- D-033：开发、验收与发布使用固定独立仓库和冻结身份；
- D-034：产品采用 Outcome / Agent 导向，由系统承担专业判断；
- D-035：Career Memory 通过当前任务渐进沉淀；
- D-036：隐私目标是最小暴露和透明边界，不承诺绝对安全；
- D-037：设计持续演进，开发按批准快照冻结同步；
- D-038：用户主动提供的原始材料与模型推断采用不同确认边界。

### 2.2 Design Baseline 导入门禁

正式批准本 PLAN 前，Documentation Agent 必须把本地不可变 `D-002` 原样导入：

~~~text
docs/design/baselines/V2.1.0/DS-002/
~~~

导入必须满足：

- 包含 `SNAPSHOT.md`、`SPEC.md`、`prototype/index.html`、`prototype/README.md`、10 张
  `previews/*.png` 和原 `CHECKSUMS.sha256`；
- 原清单覆盖的 14 个文件逐项 SHA-256 匹配；
- 导入后的 `CHECKSUMS.sha256` 自身 SHA-256 仍为
  `7ace7413a81d504a16cdfface2faff50b1623dab0f70ceac4edea1c9717c0cfc`；
- `prototype/index.html` SHA-256 为
  `548c0ac44a989a550b5f0494f17df15bae9ac27bb524110aaa57ab126cfdd65d`；
- 不加入真实数据、凭据、runtime、依赖、缓存或 Design Agent 临时文件；
- canonical 路径使用 `DS-002`，快照内部原始 `D-002` 身份保持不改。

上述导入已于 2026-09-06 完成：目标共 15 个文件，清单覆盖 14 个文件，逐项 hash、源/目标
文件清单及所有文件 SHA-256 均一致；两个固定 hash 也与本节相符。Product Owner 已于
2026-09-06 批准本 PLAN；Documentation Agent 记录批准 commit/blob 后交给开发。

### 2.3 版本内 Design Freeze

PLAN 获批后，Development Agent 只认本 PLAN 绑定的 `DS-002`，不读取或同步
`<design-workspace>/current/` 及后续快照。普通视觉、文案和非阻塞交互变化进入下一小版本。
只有安全、数据正确性或核心流程无法完成的 P0/P1 设计问题，才允许通过“新工作稿 → 用户批准
新快照 → Documentation Agent 追加 PLAN → 重新冻结”的流程解冻；不得原地修改 `DS-002`。

## 3. 当前已验收现实基线

V2.0.2 当前真实能力包括：

- React + TypeScript + Vite 三页前端：生成工作台、履历库、本地系统；
- PDF 上传、文本解析、结构化经历提取、Experience CRUD 与 Fact reconciliation；
- JD 分析、两层事实选材、受约束改写、ResumeDocument 装配、DOCX 生成与下载；
- Provider 配置、Credential Manager、迁移、Embedding 重建/重试、系统状态、运行活动、日志和
  脱敏诊断；
- 统一操作 `operation_id`、阶段事件、耗时、近期统计和 JSONL 诊断；
- FastAPI 同源托管、SPA fallback、Windows 目录型便携包和统一 `scripts/precheck.py`。

当前明确没有：真实 DOCX 页面渲染预览、持久化 Profile、生成历史、无简历对话补充、意图级
修改、修订差异/回退、局部重新生成、多用户和服务器化 Career Memory。

本版本所称“结果预览”是基于真实 ResumeDocument / 生成结果的**内容预览**，不得称为实际
DOCX 像素预览；下载的 DOCX 仍由现有 Renderer 真实生成。

## 4. 实施范围与能力状态

| 页面或能力 | V2.1.0 目标 | 数据源 | 普通用户可见性 | 完成条件 |
|---|---|---|---|---|
| 欢迎与双冷启动 | Active + Coming Soon | 真实状态 | 显示 | PDF 路径真实可用；无简历对话只显示 Coming Soon |
| PDF 上传与解析 | Active | Real API | 显示 | 真实文件、真实解析、失败可恢复；无假成功 |
| 我的经历主从界面 | Active | Real API | 显示 | CRUD、筛选、搜索、来源、状态和失败路径接通 |
| 身份摘要与 JD | Active | Real API / 单次请求 | 显示 | 身份显式来源、可编辑；JD 分析真实可见 |
| 生成工作台与生成中 | Active | Real API / operation | 显示 | 真实阶段、输入保留、失败/重试可用 |
| 内容预览与事实依据 | Active | Real API | 显示 | 最终 bullet 与 `fact_refs` 可回查，不伪称 DOCX 像素预览 |
| DOCX 下载 | Active | Real output | 显示 | 下载当前真实生成产物，失败状态明确 |
| 个人与隐私 | Active | Real state | 显示 | 准确说明本机存储、第三方模型和删除边界 |
| 开发者后台 | Active 开发入口 | Real API | 普通导航隐藏 | API Key、Provider、系统状态和诊断能力不丢失 |
| AI 进度展示 | Active 展示层 | Real operation events | 显示 | 只显示真实阶段/产物，不显示私有推理或伪进度 |
| 无简历对话补充 | Coming Soon | None | 可见说明 | 不可触发假操作，不写真实数据 |
| 意图级修改 / 修订历史 | Coming Soon | None | 可见说明 | 不可伪装保存或调用真实修改链路 |
| 身份长期自动带入 | Absent | None | 隐藏 | 不从经历、AI 或模板推断身份 |
| 生成历史（简历记录） | Absent / 后续需求 | None | 隐藏 | 不实现、不登记假记录；需求池保留 |

Design Snapshot 中“Approved”只说明设计获批；本表才是 V2.1.0 开发范围真源。

## 5. 明确不做

- 不实现生成历史、任务历史持久化、记录详情、重命名或删除；
- 不实现无简历对话、意图级修改、Revision/差异/回退、逐条锁定或局部重新生成；
- 不实现真实 DOCX/PDF 页面渲染预览，不把 HTML 内容预览冒充 DOCX 预览；
- 不新增登录、多用户、PostgreSQL、对象存储、云同步、生产队列或 V3 服务端能力；
- 不建立新的职业事实真源，不把 Mock、前端缓存或展示状态写成业务事实；
- 不重做 V1.5/V2.0 的事实选择、Builder、Renderer、迁移、Embedding 或配置架构；只有为本 PLAN
  的真实前端契约所必需且经测试覆盖的薄 API / schema 调整可以进入候选；
- 不修改、移动或重建已发布的 `v2.0.2` tag；
- 不因重构删除问题定位能力、失败可见性、Credential Manager 或同源写安全边界。

## 6. 核心产品与技术契约

### 6.1 用户界面与开发者后台分离

普通用户稳定导航为“生成简历”“我的经历”“个人与隐私”。Provider、API Key、模型、迁移、
索引、日志和诊断不进入普通一级导航；开发者后台使用独立隐藏入口。隐藏只改变信息架构，不得
删除既有管理能力或绕过同源写安全、loopback/origin 和敏感信息脱敏规则。

### 6.2 上传事实确认

- 用户主动上传并提交解析的文件是显式提供的来源；
- 能回查原文且没有语义扩张的直接抽取可以自动进入“我的经历”，保留来源文件、原文片段或
  等价稳定引用；
- 推断、补全、冲突、低置信解析和新增回答进入“需确认”，不得覆盖已有事实或静默成为长期
  已确认事实；
- 主流程不增加逐条确认页；需确认项在阻断/风险节点集中处理，或进入“我的经历”的待确认区；
- 重复导入、部分失败、纠正、停用和删除必须有确定状态，不得出现半成功但页面显示成功。

前端不得自行判断并持久化“直接抽取/模型推断”。分类与写入结果必须以后端响应为准；若现有
API 无法表达该边界，Development Agent 先完成 typed contract 和最小后端适配，再实现页面。

### 6.3 Adapter 与状态管理

页面和组件只依赖 typed frontend service；Real API、测试 Mock 和设计 fixture 使用相同契约。
Mock 只能存在于测试或显式隔离的设计环境，不在普通运行模式中自动 fallback。请求失败、解析
失败或响应不合法必须进入 Error/Blocked，不得降级为假数据。

Feature Flag 如确有必要，只控制 Coming Soon / 开发入口可见性，不改变能力真相；每个 Flag
记录 owner、默认值、启用条件、转 Active 条件和清理版本。本版本不为生成历史建立生产 Flag。

### 6.4 真实 AI 进度

- 优先复用 `core.operations` 的真实阶段、耗时和诊断编号；
- 前端可以把技术阶段翻译为用户语言，但不得虚构百分比、模型思维、已完成产物或固定时长；
- 后端只有粗粒度事件时，界面就显示粗粒度状态；
- 自动重试必须显示发生次数和最终结果；最终失败保留用户输入并提供明确重试/返回修改入口；
- Provider、堆栈、原始日志和内部诊断只进入开发者后台。

### 6.5 结果、依据与 DOCX

内容预览必须来自本次真实生成结果；每条最终 bullet 的来源映射必须在 API、前端状态与展示间
保持不丢失，未知或越界 `fact_refs` 必须失败。用户在预览中查看“为什么采用”时，展示可回查
事实、采用理由和所属经历；不展示私有模型推理。

DOCX 下载继续使用现有真实 `generate-docx` / download 主链。下载按钮不得在文件尚未生成时
显示成功；复制纯文本不得再次调用 LLM 或改变当前内容。

### 6.6 视觉、响应式与无障碍

- 主题 A 为唯一生产主题；B/C token 和静默评审参数不得进入用户功能；
- 主参考为 Chrome 1440×900；同时覆盖 1280×800、1024×768、390×844、320×568；
- 使用系统中文字体栈，不增加 CDN 或外部字体运行依赖；
- 核心画面尽量在无操作时展示当前必要信息；桌面核心流程不得依赖整页滚动，长列表和预览使用
  明确的区域滚动；窄屏允许单列和必要纵向滚动，但核心操作可达；
- 键盘完成核心流程、焦点可见、表单有 label、错误不只靠颜色表达、动态状态使用适当 live region；
- 正文、控件和状态满足 WCAG 2.2 AA 对比度；`prefers-reduced-motion` 下关闭非必要动效；
- 自动视觉差异只负责发现问题，不以单一阈值替代 Product Owner 的最终视觉判断。

## 7. 集中实施任务

| Task | 内容 | 依赖 | 风险 | 完成标志 |
|---|---|---|---|---|
| T0 | Documentation Agent 导入并验证 `DS-002`，完成 PLAN/RESULT 身份准备 | 无 | 高：冻结身份 | 14 项 hash、manifest、入口和目录结构全部匹配；用户批准 PLAN commit/blob |
| T1 | 修复 Windows CI 编码闭环并审计同类子进程 | T0 | 高：CI/诊断 | §8.1 全部通过，GitHub Windows CI 真实成功 |
| T2 | 建立主题 A tokens、组件状态、typed service/adapter、路由与全局状态骨架 | T1 | 中 | 无页面直连散落 Mock；错误 fail closed；基础视觉与 `DS-002` 一致 |
| T3 | 重构全局壳层，分离普通用户导航与隐藏开发者后台 | T2 | 高：安全/诊断 | 普通导航无技术配置；后台真实能力、权限和诊断无回退 |
| T4 | 实现欢迎、PDF 上传、D-038 分类写入和“我的经历”主从界面 | T2-T3 | 高：事实/持久化 | 直接抽取与需确认边界、CRUD、来源、失败/重复/删除闭环通过 |
| T5 | 实现身份摘要、JD 输入/分析、生成前检查、生成中真实阶段与恢复 | T2-T4 | 高：核心流程 | 一键生成真实接通；无假进度；失败保留输入并可重试 |
| T6 | 实现真实内容预览、逐 bullet 依据、纸张缩放和 DOCX 下载 | T5 | 高：来源/输出 | `fact_refs` 端到端不丢失；预览不冒充 DOCX；真实下载通过 |
| T7 | 实现个人与隐私、Coming Soon 和 Absent 边界 | T3-T6 | 中 | 无简历对话/意图修改不假接通；生成历史和身份自动带入隐藏 |
| T8 | 完成 Design Fidelity、响应式、键盘与无障碍开发验证 | T3-T7 | 中 | 固定场景截图、交互矩阵和无障碍检查通过 |
| T9 | 完整回归、统一预检、版本元数据、便携包与隐私扫描 | T1-T8 | 高：发布 | §8 全部阻断项通过，包为 2.1.0，无 runtime/PII/私有路径 |
| T10 | 更新 RESULT，冻结 clean 开发候选 H 并交接 | T9 | 高：身份 | RESULT 完整；候选/PLAN blob/基线/clean 状态可追溯 |
| T11 | 独立源码、Design Fidelity 与 Integration 验收 | T10 | 高：独立验收 | 未参与实现者绑定 H，三类结论通过，阻断项 0 |
| T12 | Product Owner 人工验收、文档收口与发布决定 | T11 | 高：发布 | 人工流程通过；CURRENT_STATE 只登记 Active；另行批准后发布 |

主依赖：`T0 → T1 → T2 → T3/T4 → T5 → T6 → T7 → T8 → T9 → T10 → T11 → T12`。
T3 与 T4 可在 T2 契约冻结后局部并行，但必须在 T5 前合并并重新验证。

## 8. 开发验证矩阵

### 8.1 Windows CI 编码闭环

1. 生命周期矩阵全部嵌套 `subprocess.run` 显式使用 UTF-8 解码与 `errors="replace"`；
2. 捕获输出在解析前使用 `proc.stdout or ""`、`proc.stderr or ""` 归一化；
3. 统一预检子进程环境同时固定 `PYTHONUTF8=1` 与 `PYTHONIOENCODING=utf-8`；
4. 受控负向输出中文及不能由 `cp1252` 表示的字符，父进程保持可读诊断和确定性非零退出；
5. 审计其他阻断脚本的嵌套子进程，不只修当前命中行；
6. `pip-audit` 能读取 UTF-8 requirements 并产生真实摘要；漏洞数量仍报告但不自动阻断；
7. 生命周期矩阵保持 **50/0**，完整 `python scripts/precheck.py` 的六个阻断脚本继续严格命中
   **77/0、48/0、20/0、15/0、50/0、12/0/3**；
8. GitHub `windows-ci` 在 V2.1.0 候选 commit 上成功，不以本地绿灯替代。

### 8.2 前端与契约

| 类别 | 必测正向 | 必测反向/失败 |
|---|---|---|
| Adapter | Real API 正确映射 typed domain state | 无效响应、网络失败不得 fallback 到 Mock |
| 导航 | 三个普通入口及隐藏后台入口正确 | 普通导航无 API Key/Provider/日志；未知路由可恢复 |
| 上传 | PDF → 解析 → 直接抽取导入 | 非 PDF、空文件、解析失败、部分失败、重复导入 |
| 事实确认 | 原文直接抽取带来源；推断进入需确认 | 推断不得标已确认、不得覆盖旧事实、越界来源失败 |
| 经历 CRUD | 搜索、筛选、查看、新增、编辑、停用、删除 | 冲突、后端失败、删除取消、Fact/Embedding 回滚 |
| JD | 输入、真实分析、摘要和生成前检查 | 过短、空、分析失败、修改后旧结果失效 |
| 生成 | 真实阶段、完成、自动重试可见 | 并发阻断、Provider 失败、超时、最终失败保留输入 |
| 结果 | 内容、依据、选择/取消、缩放 | 未知 fact、来源缺失、窄屏、长内容、空建议 |
| DOCX | 当前结果真实下载 | 尚未生成、文件缺失、下载失败不得显示成功 |
| Coming Soon | 文案清楚且不产生副作用 | 不调用 API、不保存 Mock、不写 runtime |
| 生成历史 | 正常模式无入口和假记录 | 全仓无本版本持久化/假 Active 声明 |
| 隐私/后台 | 用户信息简洁；后台能力完整 | Key 不回显；日志/诊断不泄露业务正文或凭据 |

### 8.3 视觉与可访问性

- 在 `DS-002` 固定 persona、Scenario 和 1440×900 下生成正式前端截图，与 10 张冻结截图逐页
  对照；欢迎、上传、生成 ready/blocked、processing、result、experience、privacy 必检；
- records 两张截图只作“本版本不得误实现”的反向参考，不要求生产复现；
- 1280×800、1024×768、390×844、320×568 验证布局回退、文本换行、操作可达和无横向溢出；
- 键盘顺序、可见焦点、dialog 焦点、label、aria-live、reduced-motion、状态非纯颜色表达通过；
- 自动差异、axe/等价自动检查与人工检查分别记录；自动工具为 0 不替代人工视觉和键盘验收。

### 8.4 回归、构建与便携包

- V1.5.0 事实链、V2.0.0 图形链、V2.0.1 可观测性、V2.0.2 预检与迁移退出回归继续通过；
- 前端 TypeScript、单元/组件测试、生产 build 和真实 FastAPI 同源托管通过；
- `APP_VERSION`、前端 package 及便携包元数据统一为 2.1.0；
- Windows 目录型便携包启动、健康、主要用户流程、后台入口、退出和二次启动通过；
- 包内无真实简历、数据库、日志、API Key、Cookie、测试 fixture、缓存、源码私有绝对路径或
  Design Workspace 文件；
- ruff、ESLint、pip-audit、npm audit 保持如实报告；工具缺失、崩溃、超时或无摘要不得伪装为
  零问题。是否阻断仍按本版本批准阈值执行。

所有动态验证使用一次性临时副本和隔离 runtime。测试前后默认真实 runtime 哨兵保持一致；
cleanup 失败必须非零退出。

## 9. 独立验收要求

T11 必须由未参与候选实现、自测、源码修复或开发结论编写的验收 Agent 执行，并绑定同一 clean
候选 commit H。至少分别给出：

1. **功能验收**：核心用户流程、Active/Coming Soon/Absent 状态和失败恢复符合 PLAN；
2. **结构变更验收**：用户/后台分层、Adapter、事实确认、Mock 退出、旧导航退出和版本元数据
   完成收口；
3. **Design Fidelity**：相对 `DS-002` 的布局、主题、文案、状态、交互和响应式差异有证据；
4. **Integration**：真实 API、operation、来源映射、DOCX、Feature Flag 和副作用与矩阵一致；
5. **Windows CI 专项**：编码负向、固定计数和 GitHub runner 成功；
6. **隐私与便携包**：无真实数据、Key、私有路径、设计工作区或测试残留。

验收报告只返回给 Documentation Agent，不在仓库新增第三份验收文档。任何验收者落盘修复都会
使其成为该补丁开发者，必须由另一名独立验收者复验。

## 10. Product Owner 人工验收

人工验收至少使用一个全新临时 runtime 和一份虚构 PDF，完成：

1. 首启看到双路径，Coming Soon 不产生假操作；
2. 上传 PDF 后直接原文事实进入“我的经历”，推断/冲突不被静默确认；
3. 在“我的经历”查看来源并完成编辑、停用/恢复和删除取消；
4. 身份摘要可见可编辑，输入 JD 后一键生成，无需处理模板等低层参数；
5. 生成中看到真实阶段和失败恢复，不看到 Provider 内部信息或模型私有推理；
6. 结果内容完整，点击 bullet 可查看事实依据，取消选择与长内容布局正常；
7. 下载真实 DOCX，并确认内容与当前结果一致；
8. 普通导航没有开发配置；隐藏入口可进入后台并完成配置/诊断最小回归；
9. 普通模式不存在生成历史入口或假记录；
10. 1440×900 主流程整体观感、一屏信息、滚动和主题 A 由 Product Owner 明确给出通过/打回。

## 11. 开发交接与 RESULT

开发 Agent 在候选冻结前更新本版本 `RESULT.md`，至少记录：

- 批准 PLAN commit/blob、源 `D-002`、canonical `DS-002`、manifest hash 和开发基线；
- T1-T10 实际完成状态、每项偏差、API/schema/数据/模块/配置/依赖/构建变化；
- Active、Coming Soon、Absent 的最终实现矩阵；
- 开发验证的命令、退出码、固定计数、截图/视觉比较摘要、临时 runtime 与 cleanup 结果；
- Windows CI run 身份和结论；
- 功能、结构、Design Fidelity、Integration 四类开发侧结论，明确不冒充独立验收；
- clean 候选外部交接所需的完整 40 位 HEAD、分支和 `git status`。

RESULT 不回填其所在提交自身 SHA。候选冻结后，开发 Agent 不再修改 RESULT；验收、人工反馈、
文档收口和发布状态由 Documentation Agent 追加。

## 12. 完成定义与发布门禁

以下条件全部满足，V2.1.0 才可以进入发布确认：

- `DS-002` 已原样导入、hash 全匹配且 PLAN 身份已由用户批准；
- T1-T10 全部完成，未批准范围没有混入候选；
- Windows CI 编码负向、完整预检和 GitHub runner 成功；
- 核心页面一次完成整体重构，无新旧导航/视觉混杂；
- D-038 事实分类、真实 AI 进度、逐 bullet 来源和 DOCX 下载闭环通过；
- 生成历史、身份自动带入及其他 Absent 能力没有被假实现或误写为 Active；
- T11 独立功能、结构、Design Fidelity 和 Integration 验收全部通过，阻断项 0；
- Product Owner 人工验收通过；
- CURRENT_STATE 只登记实际 Active，Coming Soon/Absent 不作为已支持能力；
- 最终候选相对被验收源码 H 只有授权文档变化；版本、包、README、RESULT 和 tag 语义一致；
- Product Owner 另行明确批准发布后，Documentation Agent 才更新远端 main 并创建新的 annotated
  tag。PLAN 获批、开发完成或验收通过均不自动等于批准发布。

## 13. Product Owner 人工验收返工补充（2026-09-07）

### 13.1 触发与优先级

Product Owner 在 T12 使用真实生成流程验收候选
`e73f1547d8764e7e60ee57407c06c07db29a4f95` 后明确打回。问题不是零散样式偏好，而是生成阶段
和结果阶段的信息重复、技术明细堆叠、页面滚动，以及实现擅自偏离冻结原型的结构，共同破坏
核心流程直觉，按 P1 可用性与 Design Fidelity 问题处理。

Product Owner 随后用五个设计状态重新明确原意：本版本应按 DS-002 的 `welcome`、上传 parsing、
`generate`、`processing` 和 `result` 结构还原，开发只把 Mock/设计占位映射为当前真实能力，不能以
“实现优化”为由重新设计布局。本节是 Product Owner 已批准的当前版本返工契约；与 DS-002 的
个别演示行为或 PLAN 前文冲突时，以本节明确的真实能力映射为准。其他冻结设计和版本范围继续
有效，不借此扩大功能范围，也不修改原 DS-002 文件或引入新的 Design Snapshot。

### 13.2 五个状态的冻结实现

#### A. 无简历初始页

- 桌面结构、文案层级、两张路径卡和下方三条原则按 `previews/welcome-theme-A.png` 还原；
- “我有一份现有简历”整张左卡是上传 drop zone：单击立即打开系统文件选择器，不先跳转到独立
  upload-idle 页面；拖入 PDF 直接上传；取消选择仍停留原页；
- “我还没有简历”右卡保留占位外观，但暂时不可点击，不进入演示、不产生 toast 或假状态，使用
  明确的 disabled/`aria-disabled` 语义；
- 选中文件后立即进入上传解析状态；格式/读取失败仍要真实可见并可重试。

#### B. 上传后的解析页

- 按原型 `.upload-shell` / `.process-shell` 的左右结构实现：左侧展示上传解析的**完整流程**及各步
  等待、当前、完成、失败状态，右侧固定为“AI 解析过程”流式输出面板；
- 右侧只展示一个选中阶段的用户可理解事件；每个阶段的真实输出按阶段分别保留。进入下一阶段时
  默认自动选中新阶段并切换右侧内容，但不删除旧阶段历史；用户点击左侧已经开始或已经完成的
  阶段，可切回查看该阶段明细。未开始阶段不可选择，也不得生成占位明细；
- 左侧阶段项必须是可识别、可键盘操作的选择控件，并明确当前运行阶段与当前查看阶段；右侧不把
  多个阶段的 operation 同时纵向铺开；
- 文件名、页数、当前步和真实耗时可以在原型对应位置显示，但不得暴露内部迁移、Embedding、
  原始资源类型、私有思维链或虚构进度；
- 解析完成后继续现有 D-038 直接事实/需确认分流，不能为还原原型而取消确认边界。

#### C. 身份与 JD 输入页

- 左侧按 Product Owner 提供的 `generate` 状态原型还原：身份摘要在上，目标岗位与 JD 输入、真实
  JD 分析状态和 chips 在下；不重排为开发自行定义的卡片组合；
- 右侧保持 `generate-blocked` / `generate-ready` 原型结构：生成前检查、产品级说明和生成动作按
  状态显示；检查项只列当前必须处理的问题；
- V2.1.0 使用固定模板，删除“模板”“1 个模板”徽标、模板下拉框及相关用户选择状态。固定模板只
  作为后端实现事实，不在主流程要求用户理解或操作；
- 身份/JD 在失败或返回修改后仍保留，但只在本输入状态显示，不在后续 processing/result 重复。

#### D. 生成处理页

- 复用 B 的视觉语法：左侧显示简历生成的完整四阶段流程，右侧固定为当前阶段的流式输出；
- 每个阶段的真实输出按阶段保留；进入下一高层阶段时右侧默认切换到新阶段，用户可以点击左侧
  已开始/已完成阶段返回查看历史。右侧任一时刻只显示一个选中阶段，不把所有 operation 同时铺开；
- 失败时右侧替换为当前失败阶段、简明原因和可执行恢复入口；
- 阶段和流式文案必须来自真实 `stage_code` / operation timeline 的安全产品映射，不允许计时器
  模拟、虚构百分比、提前点亮或展示模型私有推理。

#### E. 结果预览页

- 按 `previews/result-theme-A.png` 的主从布局还原：左侧为真实简历纸张预览；右侧为固定的
  “依据 / 修改”区域，导出操作位于右侧下方；
- “依据”接真实 bullet/fact 映射；“修改”在真实链路尚未实现时保留清晰的 Coming Soon/disabled
  边界，不得伪装成功；下载 DOCX 保持 Active；
- 右侧在桌面视口中保持 sticky/fixed，不随左侧简历内容滚出视野；切换依据/修改时面板尺寸稳定；
- 删除旧候选的重复页头/说明、已提交输入卡和独立“本次结果”技术摘要，包括文件名复述、AI 优化/
  材料不足计数、原始 Builder/Renderer 警告、页数/匹配经历/渲染经历/模板统计表；
- 原始技术警告、统计和诊断只进入隐藏开发者后台；普通结果页只保留查看结果、核对事实、修改入口
  状态和导出所直接需要的内容。

### 13.3 滚动、固定与响应式边界

1. 1440×900 桌面验收视口下，welcome、上传解析、generate ready/blocked 和 processing 不出现
   浏览器页面级横向或纵向滚动；当前任务所需信息完整可见。
2. result 优先使用 DS-002 `fitPaper` 将一页简历等比适配可用高度，尽量不要求滚轮；不得缩小到
   不可读。内容确实超出一页或较小视口无法可读适配时，只允许左侧预览区域受控滚动或分页，右侧
   依据/修改/导出区域仍固定可见，不能随整页滚动离开。
3. 不得通过裁切关键内容、隐藏真实失败、极端缩放或把整个页面塞入新的内部滚动容器来伪造通过。
4. 窄屏继续按 DS-002 断点降为单列；无横向滚动，信息顺序仍以当前任务为先。桌面结构验收不能
   以窄屏降级规则为由偏离上述左右布局。

### 13.4 Design Fidelity 判定

本轮“还原”首先比较结构和行为，不只比较颜色与 tokens：页面状态、左右栏比例、组件顺序、主要
文案层级、固定区域、阶段切换、首屏信息和滚动行为都必须与上述原型一致。允许的差异只有真实
产品契约所必需的映射，例如右侧无简历入口 disabled、模板固定、Mock 流改为真实阶段、修改功能
标记 Coming Soon。任何其他结构偏差必须先写入 RESULT 并由 Product Owner 明确批准，开发 Agent
不能自行以“更简洁”“更真实”或“组件复用”为理由改变原型。

### 13.5 集中返工任务与完成标准

| Task | 工作 | 完成标准 |
|---|---|---|
| T12-R1 | 还原无简历初始页 | 左卡单击直接打开文件选择器并支持拖放；右卡不可点击且无假操作；选择文件后进入真实解析 |
| T12-R2 | 还原上传解析页 | 左侧完整解析流程；右侧单阶段流式输出；新阶段自动切换、旧阶段历史保留且可从左侧回看；D-038 确认和错误恢复无回退 |
| T12-R3 | 还原身份/JD 页面并退出模板选择 | 左侧身份+JD 按原型结构；右侧检查/说明/生成结构；模板徽标、下拉和用户选择状态计数为 0 |
| T12-R4 | 还原生成处理页 | 左侧完整四阶段；右侧单阶段流；新阶段自动切换、已开始/完成阶段可回看；processing DOM 无重复身份/JD 摘要和全量 operation 同屏列表 |
| T12-R5 | 还原结果主从布局 | 左侧真实预览，右侧固定依据/修改/导出；旧技术摘要与统计退出；依据真实、修改不假接通 |
| T12-R6 | 建立滚动与固定门禁 | 1440×900 四个前置/处理状态无页面滚动；结果优先 fitPaper，必要滚动仅限左侧预览，右侧始终固定；截图和 DOM 尺寸留证 |
| T12-R7 | 重建验证与发布包 | 前端 build、适用回归和完整 precheck 通过；最终 onedir 在源码返工后重建，包内前端文件清单及逐文件 SHA-256 与最终 `frontend/dist` 一致 |
| T12-R8 | 冻结新候选 H2 并重新交接 | RESULT 记录五状态实现、旧状态退出、截图、尺寸、命令/退出码和包哈希；clean H2 由未参与返工者重新验收 |

T12-R1 至 R6 属同一 Design Fidelity 返工，必须一次完成后再验证，不接受只隐藏截图中某个卡片、
只换颜色或在原有纵向页面外再包一层容器。T12-R7 必须特别证明旧便携包已退出：当前 T9 包内
前端资产早于 T8-1/T8-2
最终视觉构建，不能作为 V2.1.0 人工验收或发布包继续使用。

### 13.6 返工后的复验

开发 Agent 只能在固定 `<current-workspace>` 实施并产生新 clean 候选 H2。由于返工会修改前端
源码、样式、构建产物和便携包，原绑定 `e73f1547d8764e7e60ee57407c06c07db29a4f95`
的 Design Fidelity、Integration 和发布包结论不能证明 H2；须由未参与返工的验收 Agent 绑定 H2
复验 T12-R1 至 R7、五状态结构还原、真实阶段映射、诊断保留、滚动/固定边界和包内资产一致性。
Product Owner 随后重新执行 T12；未明确通过前，版本保持“需修正”，不得更新公开事实或发布。

## 14. Product Owner 第二次人工验收返工补充（2026-09-07）

### 14.1 触发、根因与优先级

Product Owner 在 H2-HANDOFF `3d821f2049e1c91fdd4d550bc4fb63686d10359b` 对应实际应用中
重新执行 T12，明确判定人工验收仍不通过。本轮只聚焦结果页与全局卡片几何纪律，但它直接影响
用户对最终交付物的判断，按 P1 Design Fidelity/核心任务可用性问题处理。

开发侧确认根因：T6 的 `ResultPaperPreview` 只把 `doc_preview` 的 section/entry/heading/subhead/
bullets 文本结构画成通用 HTML，没有按 `pm_template v1.2` 的视觉规格装饰。当时使用“内容预览
不等于 DOCX 像素”的边界避免伪造，但该边界被错误扩大为“预览可以与真实模板采用不同结构和
视觉语言”。

本轮修正后的唯一口径是：

> 浏览器预览不冒充 Word 截图，也不承诺不同渲染引擎逐像素完全相同；但它必须使用真实生成
> 内容，并忠实呈现 `pm_template v1.2` 的信息结构、章节顺序、字段位置、排版层级、页面密度、
> 间距、对齐与 bullet 规则。浏览器与 Word/PDF 的轻微字体栅格差异可以存在，结构或视觉规格
> 不一致不再属于允许偏差。

这不是伪造：预览、Word 和 PDF 必须来自同一份真实 `ResumeDocument`/模板契约，并通过一致性
测试证明。PLAN 前文中“不实现真实 DOCX/PDF 页面渲染预览”“内容预览不冒充 DOCX”的表述，
继续禁止把静态截图或假文档当成真实结果，但凡与本节的模板忠实预览要求冲突，均以本节为准。
新增真实 PDF 下载是 Product Owner 在本轮明确批准的 V2.1.0 范围扩展；它不解锁编辑、历史或
其他未来能力。

### 14.2 结果页冻结实现

#### A. 模板忠实预览

- `pm_template v1.2` 是结果预览、Word 与 PDF 的共同视觉真源；禁止继续维护与模板无关的通用
  `ResultPaperPreview` 排版规则；
- 同一生成结果在预览、Word 和 PDF 中的姓名/联系方式、目标岗位、章节顺序、条目标题、时间、
  副标题、bullet 数量与文字必须一致；空章节的显示/隐藏规则也必须一致；
- 预览需还原模板的标题层级、页边距意图、分隔线、字体层级、行高、条目间距、日期与标题对齐、
  bullet 缩进和整体信息密度；不得把模板头部改成“个人信息”普通章节等另一套布局；
- 依据选择、高亮或 hover 只能作为不改变排版尺寸的 overlay/背景状态，不能添加会挤压内容、改变
  换行或形成模板中不存在的粗边框；取消选择后必须完全恢复模板外观；
- 建立固定虚构 fixture，由同一份 `ResumeDocument` 同时生成预览、Word 和 PDF，并保留三者内容
  对照、渲染截图与模板版本证据。不能只用源码类名或肉眼声明证明一致。

#### B. 预览几何

- 结果页预览卡中的简历内容必须填满该卡片的可用宽度；不得再在卡片内居中放置一张明显更窄的
  二级“纸张”而留下大面积灰色边带；
- 预览表面不显示额外边框、圆角或阴影；卡片本身是唯一外层容器，简历内容从其内容区左边缘延伸
  到右边缘。必要内边距来自 `pm_template v1.2`，不是额外纸张边框；
- 缩放以填满可用宽度和保证可读性为先。内容超过卡片固定高度时只在预览卡内部纵向滚动，不得
  让整个页面滚动；禁止裁切、极端缩放或改变模板结构来伪造“一屏”。

#### C. 导出卡

- 结果页可用区域导出卡位置最初冻结为左下角，后由 Product Owner 于 2026-09-08 明确改为
  **右下角**；最终实现只认 §19，旧“左下角”要求不再适用；
- 卡片内部只保留两个主要操作按钮，按 Product Owner 指定文案分别为“下载 Word”和“下载 PDF”；
- 删除“导出”标题、文件名复述、“复制简历全文”、说明文字、生成短码和其他任何辅助内容；
- 两个按钮必须下载当前同一生成结果的真实文件。Word 沿用真实 DOCX 主链；PDF 必须接通真实
  PDF 产物、正确文件名/MIME/失败状态，不能以 disabled、Coming Soon、复制文本、打印对话框或
  Word 文件改后缀冒充；
- 文件尚未生成、文件缺失或生成失败时，按钮状态必须真实且可恢复，但错误信息应使用不改变卡片
  外框尺寸的卡内固定区域或非布局浮层表达。

### 14.3 全局固定卡片与滚动纪律

本节将 PLAN §13.3 的“一屏”要求进一步具体化，并适用于 welcome、上传解析、身份/JD、
processing、经历管理、隐私、结果和普通用户可见错误态：

1. 每个页面状态的卡片外框由视口与布局网格决定，使用固定/受约束的宽高或 `minmax(0, 1fr)`；
   卡片内容从短到长、空态到错误态、阶段切换或 Tab 切换时，外框位置和尺寸不得随内容量跳动。
2. 卡片可以随窗口比例和已批准响应式断点整体改变，但在同一视口与同一页面状态中，不得依赖
   内容 intrinsic size 自动增高、缩小或推挤相邻卡片。
3. 整个普通用户页面在目标桌面视口不得产生横向或纵向滚动；页面 shell 使用确定的可用高度和
   `overflow: hidden`/等价布局约束，不得靠隐藏被截断内容伪造通过。
4. 内容确实超过卡片容量时，允许且必须只在对应卡片的内容区出现内部滚动；标题、阶段选择、
   关键操作和固定底栏按页面任务保持可见。内部滚动条不得改变卡片外框尺寸或导致布局抖动。
5. 至少对 1440×900、1280×720 和 1920×1080 三个桌面视口，分别以短内容、长内容、空态、
   错误态和阶段/Tab 切换留存外框 bounding rect、页面/client/scroll 尺寸和截图证据；三种内容量
   下同一视口对应卡片的外框尺寸必须一致，页面 `scrollHeight == clientHeight` 且
   `scrollWidth == clientWidth`。
6. 窄屏断点可以改为单列，但仍应优先保持页面 shell 不滚动、卡片内部滚动；若受操作系统最小
   窗口限制无法满足，必须明确最小支持视口并由 Product Owner 单独批准，不能由开发自行放宽。

### 14.4 集中返工任务与完成标准

| Task | 工作 | 完成标准 |
|---|---|---|
| T12-R9 | 建立 `pm_template v1.2` 的预览一致性契约 | 同一真实 ResumeDocument 驱动预览/Word/PDF；结构、内容和模板视觉规则一致；固定 fixture、三端对照和截图留证 |
| T12-R10 | 重做结果预览几何 | 预览填满卡片可用宽度；无二级纸张边框/圆角/阴影；依据交互不改变换行或布局；溢出仅卡内滚动 |
| T12-R11 | 收口导出卡并接通 PDF | 历史实现按当时口径放置；最终位置由 §19/T12-R32 改为右下角；仍只保留“下载 Word”“下载 PDF”两个真实产物按钮 |
| T12-R12 | 建立全局固定卡片门禁 | 所有普通用户页面卡片外框不随内容变化；三种桌面视口与短/长/空/错/切换状态无页面滚动，溢出仅指定卡内滚动 |
| T12-R13 | 回归、预检与便携包重建 | 预览/Word/PDF 一致性测试、PDF 下载正反向、既有固定计数、前端 build、完整 precheck 通过；重建 onedir 并证明包内前端和所需 PDF 运行依赖完整 |
| T12-R14 | 更新 RESULT 并冻结 H3 | 记录根因、实现、fixture、截图、bounding rect、滚动尺寸、命令/退出码、包 hash 和偏差；clean H3 由未参与返工者重新验收 |

T12-R9 至 R12 属同一结果页/布局纪律返工，必须整体完成，不能只删除截图里的文字、把预览宽度
设为 `100%` 或给 `body` 加 `overflow:hidden` 就宣称完成。H3 验收必须实际打开同一 fixture 的预览、
Word 和 PDF 做内容与视觉对照，并验证下载文件；源码静态检查、开发截图和单一 1440×900 happy
path 均不能单独替代。

### 14.5 复验与发布边界

H2 的第二轮独立源码/回归结论保留为历史证据，但 Product Owner 的第二次 T12 已推翻其
Design Fidelity 与发布可用性结论。Development Agent 在固定 `<current-workspace>` 完成
T12-R9 至 R14 并冻结 clean H3；文档 Agent 核对源码/RESULT/PLAN/包身份后才更新固定
`<review-workspace>`。未参与 H3 实现或修复的验收 Agent须绑定 H3，重新验证本节、相关 T6/T8/T9、
真实导出、回归和包一致性。Product Owner 最后再次执行 T12。H3 通过前不更新公开事实，不推送
main，不创建发布 tag。

## 15. V2.1.0 预览技术方案定案（2026-09-08）

### 15.1 决策与版本边界

Product Owner 确认：V2.1.0 必须解决“页面预览不能可靠代表最终产物”的问题，但本版本不实施
动态排版能力。PLAN §14 中要求 React/CSS 预览、ReportLab PDF 和 DOCX 三套独立渲染结果持续
保持视觉一致的方案予以撤回；与本节冲突的 §3、§4、§5、§6.5、T6、§8、§10、§13、§14 表述，
均以本节为准。

V2.1.0 的用户承诺调整为：

> 结果页展示本次生成的**真实 PDF 成品预览**。页面预览与“下载 PDF”读取同一份不可变 PDF
> artifact；用户在预览中看到的版式就是所下载 PDF 的版式。Word 是同一份 ResumeDocument 的
> 可编辑导出物，内容与事实来源一致，但不承诺因字体、分页和办公软件渲染差异而与 PDF 像素一致。

本节只替换预览技术链和相应验收，不解锁模板选择、版式设置、逐条改写、修订历史、关键词加粗、
自动压页或字体/行距/字距自适应。上述排版与局部再生成能力进入
`docs/versions/V2_REQUIREMENTS_POOL.md`，由后续版本另行冻结。

### 15.2 唯一预览链路

V2.1.0 冻结以下链路：

~~~text
ResumeDocument + pm_template v1.2
        ├─→ DOCX Renderer → 当前 Word artifact
        └─→ PDF Renderer  → 当前 PDF artifact
                                  ├─→ 结果页内置 PDF viewer
                                  └─→ “下载 PDF”
~~~

具体约束：

1. 后端成功生成 PDF 后返回稳定的 artifact 身份、下载地址、文件大小和 SHA-256；同一生成结果的
   PDF artifact 写成后不可原地覆盖。重新生成必须产生新的身份，避免页面缓存展示旧文件。
2. 前端使用随应用打包的 PDF.js 或等价本地 PDF canvas viewer，直接读取该地址返回的 PDF 字节；
   不依赖 CDN、系统 PDF 插件、Office、LibreOffice、打印对话框或运行时外部服务。
3. 结果页的“下载 PDF”必须下载 viewer 当前绑定的同一 artifact。禁止前端再生成 PDF、下载时
   临时重排、用 Word 改后缀，或用另一 URL/另一份文件冒充。
4. `doc_preview`/section/entry/bullet JSON 只保留为内容核对、事实依据和无障碍辅助数据，不再承担
   简历版式渲染。产品路径不得在 PDF 缺失或 viewer 失败时回退到 `ResultPaperPreview` 通用 HTML
   并继续称为预览。
5. `pm_template v1.2` 仍是本版本 PDF Renderer 的视觉规格。姓名、联系方式、求职意向、章节顺序、
   条目标题、日期、bullet、空节规则与模板 fixture 必须正确；但只维护“PDF 成品”这一条浏览器
   可见版式真源，不再复制一套 React/CSS 模板常量。
6. DOCX 与 PDF 必须来自同一 ResumeDocument、生成操作和事实引用集合；字段文字、章节、条目和
   bullet 内容不得分叉。允许的差异仅为渲染引擎导致的字体、字距、换行和分页差异，并在结果页
   以简短产品文案说明“预览对应 PDF，Word 在不同软件中可能有轻微排版差异”。

### 15.3 预览、依据与几何实现

- PDF canvas 填满结果预览卡的可用宽度；预览卡是唯一外层容器，不再出现模拟纸张的额外边框、
  圆角、阴影或大面积灰色边带。PDF 页本身的白底和模板页边距属于真实产物，不得删改。
- 页面 shell 不滚动。PDF 页超出卡片固定高度时，只允许预览卡内容区纵向滚动；右侧依据/修改区
  与右下角双按钮导出卡保持固定。卡片外框继续遵守 §14.3 的视口网格纪律。该位置修正以 §19 为准。
- PDF Renderer 在绘制时同步输出与该 artifact 绑定的 `PreviewAnchor` 清单，至少包含
  `artifact_id`、`page_index`、矩形坐标、`content_item_id` 和 `fact_refs`。前端依据该坐标在 PDF
  canvas 上增加不参与文档排版的透明命中层/高亮层，实现点击 bullet 查看依据。
- overlay 只能覆盖 PDF canvas，不能改变 canvas 尺寸、文字换行或页面布局；坐标缺失、越界、
  artifact 身份不匹配或未知 `fact_refs` 必须 fail closed，不得用文本模糊匹配猜测来源。
- viewer 加载中显示固定尺寸 loading；PDF 生成失败、下载 4xx/5xx、MIME 错误、hash 不符或解析
  失败时，在固定区域显示“PDF 预览不可用”和重试/返回入口。此时 Word 若已成功可以独立下载，
  但页面不得展示近似 HTML 假预览。

### 15.4 本版本明确不做的排版能力

V2.1.0 不因采用 PDF viewer 而实现以下能力：

- 单个 Fact/ResumeBullet 重新生成、锁定、差异对比或 Revision 回退；
- 将每条 bullet 自动约束为一至两条视觉行；
- 根据超页自动切换全局字体、字号、行距、段距或字距；
- 关键词结构化加粗及其对换行、容量的重新测量；
- 用户选择模板、密度、页数或逐项排版参数；
- 为追求 PDF/Word 像素一致而引入 Office/LibreOffice 运行时依赖。

开发不得以“为未来预埋”为由把这些需求混入 V2.1.0 候选。本版本只要求固定
`pm_template v1.2` 下真实 PDF 的生成、展示、依据联动和下载闭环。

### 15.5 第四轮集中返工任务

| Task | 工作 | 完成标准 |
|---|---|---|
| T12-R15 | 退出 HTML 简历渲染并接入真实 PDF viewer | 产品路径不再使用 `ResultPaperPreview` 绘制版式；内置 viewer 加载真实 PDF artifact，满宽、仅卡内滚动、无外部运行依赖 |
| T12-R16 | 建立 artifact 身份与依据锚点 | viewer、下载按钮和 PreviewAnchor 绑定同一 artifact；点击 PDF bullet 可回查真实 `fact_refs`；旧 artifact、越界坐标和未知来源 fail closed |
| T12-R17 | 完成失败态、回归和便携包 | loading/生成失败/下载失败/MIME/hash/viewer 解析失败均不回退假预览；前端 build、完整 precheck、固定计数和 onedir 重建通过；包内 viewer 依赖完整且无 CDN |
| T12-R18 | 更新 RESULT 并冻结新 H3 | 记录实现、接口、fixture、hash 同一性、截图/几何、错误注入、命令/退出码与包身份；clean 新 H3 交 Documentation Agent 核对 |

`6664e37` 与 `a9a3d56` 只作为被暂停的第三轮实现历史，不得沿用为 H3。Development Agent 必须
基于本 PLAN 新增 R15-R18，完成后交付新的 clean 源码点及 RESULT 记录；Documentation Agent 核对
后再切换固定 `<review-workspace>`，由未参与实现/修复者绑定新 H3 复验。

### 15.6 新 H3 验收证据

新 H3 至少提供并由独立验收者复核：

1. 固定虚构 ResumeDocument 生成 DOCX、PDF、PreviewAnchor；DOCX/PDF 的字段、章节、条目、bullet
   和 `fact_refs` 全量相等，PDF 视觉符合 `pm_template v1.2` 参考；
2. 记录 API PDF 响应、viewer 实际加载字节和“下载 PDF”所得文件的 SHA-256，三者完全一致；
3. 生成两个不同结果并交替打开，证明 URL/artifact/cache 身份不会让新页面显示旧 PDF；
4. 验证 PDF 正向、缺失、非法路径、MIME 错误、截断/损坏、hash 不符与 viewer 解析失败；所有失败
   都诚实显示且不出现 HTML 近似预览；
5. 验证 PreviewAnchor 正向点击、跨页、重复文本、坐标越界、artifact 不匹配和未知 Fact；依据层
   不改变 PDF 版式；
6. 在 1440×900、1280×720、1920×1080 下验证预览满宽、导出卡和右侧固定、页面
   `scrollHeight == clientHeight`、`scrollWidth == clientWidth`，溢出只发生在预览卡内部；
7. “下载 Word”“下载 PDF”均返回当前生成结果的真实文件；界面明确 PDF 预览承诺与 Word
   轻微排版差异边界；
8. 完整统一预检、既有固定计数、前端正式构建、便携包启动与包内前端/PDF viewer/PDF Renderer
   依赖一致性全部通过。

上述源码复验通过后仍需 Product Owner 在实际应用中重新执行 T12，重点确认 PDF 成品视觉、预览
可读性、卡片几何、依据交互和双格式下载。人工验收未通过前不更新公开事实、main、tag 或发布声明。

## 16. Product Owner 第三次 T12 白屏返工补充（2026-09-08）

### 16.1 触发、证据与优先级

H3-SRC `5ea56c4fe0ea4f1eead436bd03439485ea8218e1` 已取得第四轮独立源码验收
Conditional Pass，但 Product Owner 随后在真实 onedir 应用执行第三次 T12 时发现：生成任务与
PDF/DOCX 产物已经成功，浏览器结果页却变为无错误说明、无返回入口的整页白屏。

现场 Console 出现两条同源生产错误：

~~~text
Error: Minified React error #310
Uncaught Error: Minified React error #310
~~~

React 官方 error decoder 将 #310 定义为 `Rendered more hooks than during the previous render.`。
由此确认根因类别是同一组件在前后渲染中改变了 Hook 数量或顺序；生产压缩栈只显示 bundle 与
`useEffect` 调用，尚不能唯一定位具体源码组件和行号。

该问题破坏唯一核心交付流程，定级 **P0**。Product Owner 已于 2026-09-08 批准本节返工；H3
不得发布，本问题不得下移到 V2.1.1。H3 的独立源码验收保留为历史事实，但任何修复提交都形成
新的 H4-SRC，不能自动继承 H3 结论。

### 16.2 根因修复契约

Development Agent 必须在非压缩开发环境使用能够触发现场状态转换的真实/等价成功响应复现
React #310，并记录：

- 发生异常的源码组件与行号；
- 前后两次渲染分别经过的条件分支；
- 发生变化的 Hook 类型、数量或顺序；
- 触发所需的响应字段和页面状态；
- 为什么既有单元、构建、fixture 与第四轮源码验收没有覆盖该路径。

修复必须遵守 React Hooks 的稳定调用顺序：不得在条件分支、循环、事件函数或可能提前 return
之后新增 Hook；不能通过隐藏结果页、吞掉异常、禁用真实 PDF/PreviewAnchor、固定测试数据或
延迟状态更新来规避 #310。若根因来自多个组件或共用 Hook，必须一次审计并修正同类路径。

### 16.3 白屏失败边界

除修复当前根因外，应用还必须建立最外层 React Error Boundary 或等价渲染恢复边界：

1. 工作台或结果页任一子组件抛出未捕获渲染异常时，不得卸载成空白 body；
2. 固定错误界面必须使用普通用户能理解的文案，提供返回工作台或重试**页面渲染**的操作；
3. 恢复操作不得重新提交生成 API、创建新 operation、重复模型调用或产生额外计费；
4. 已成功的 operation 与 PDF/DOCX artifact 不得因前端渲染失败被删除、覆盖或标记为生成失败；
5. 开发者诊断可以记录脱敏错误标识、组件栈和版本，但不得记录 API Key、完整履历、完整 JD、
   生成正文或浏览器本地敏感状态；
6. 错误边界本身必须有稳定最小布局，并在生产 build 与 onedir 中可见；Console error 不能成为
   用户唯一可见的失败说明。

本节只要求当前页面生命周期内的错误恢复，不提前实现 V2.1.1 的跨路由任务状态保持、浏览器刷新
恢复、应用重启续跑或多任务中心。

### 16.4 状态转换与回归矩阵

结果页回归不能只测试静态 mount。至少覆盖同一个真实工作台组件在以下状态间的连续转换：

| 起始状态 | 目标状态 | 必须证明 |
|---|---|---|
| 初始输入 | 生成中 | Hook 顺序稳定，只提交一个生成 operation |
| 生成中 | 生成成功、PDF 可用 | 结果页正常渲染，PDF viewer、依据和双下载可用 |
| 生成中 | 生成成功、PDF 不可用、Word 可用 | 固定失败态可见，不白屏，Word 可独立下载 |
| 生成中 | 业务失败 | 保留输入和原失败信息，不白屏、不伪造成功 |
| 生成成功 | 依据选择/取消 | PreviewAnchor 交互不改变 Hook 顺序或重新生成 |
| 任一结果子组件注入 render exception | Error Boundary | 用户可见恢复界面出现，operation/artifact 不变，无额外 API 调用 |

测试必须使用包含真实 PDF artifact 字段、PreviewAnchor、多个 section、entry、bullet、空/非空
`fact_refs` 的成功响应，并补充能在修复前稳定触发 React #310、修复后通过的回归用例。测试还应
审计 ESLint React Hooks 规则是否实际覆盖产品源码；规则缺失或未执行时必须补齐阻断检查，不能
只报告人工代码审查。

### 16.5 H4 集中返工任务

| Task | 工作 | 完成标准 |
|---|---|---|
| T12-R19 | 复现并定位 React #310 | 非压缩环境取得组件/行号/Hook 分支；记录触发数据和漏测原因；修复前用例稳定失败 |
| T12-R20 | 修复 Hook 顺序及同类路径 | 所有渲染路径 Hook 顺序稳定；真实成功响应正常进入结果页，不隐藏或降级 PDF/依据能力 |
| T12-R21 | 建立应用级白屏恢复边界 | 注入渲染异常时出现用户可见恢复界面；不重复 operation/API/计费，不破坏已成功 artifact |
| T12-R22 | 完成状态矩阵、回归与包验证 | 开发/生产 build/onedir 均完成真实生成到结果页；React #310 为 0；PDF/Word 下载、依据、失败态与既有固定计数通过 |
| T12-R23 | 更新 RESULT 并冻结 H4 | 记录根因、修复、测试、Console、API 调用计数、产物与包身份；形成 clean H4-SRC 和只改 RESULT 的开发交接 |

### 16.6 H4 验收与发布边界

Documentation Agent 收到开发交接后，先核对 H4-SRC、RESULT、PLAN blob、工作区 clean 和
H3..H4 范围；只在文档与候选身份闭合后把固定 `<review-workspace>` detached 到 H4-SRC。

未参与 R19-R23 实现、自测或修复的验收 Agent 至少独立验证：

1. 修复前触发 fixture 在 H3 出现 React #310，在 H4 不再出现；
2. 状态转换矩阵全部通过，实际生成 API/operation 只有一次；
3. 结果子组件异常注入能够命中 Error Boundary，页面不白屏，operation/artifact 未变化；
4. 生产 build 与 onedir 的真实成功响应可进入 PDF 结果页，Word/PDF 下载和依据交互正常；
5. 既有 R9、R17、R17a、完整 precheck、前端 build 与包内资产一致性无回退；
6. 修复没有把 V2.1.1 的跨路由状态保持或其他新功能混入 V2.1.0。

独立源码验收通过后，Product Owner 必须在实际 onedir 进行第四次 T12。第四次人工验收通过、
候选对应的 GitHub Windows CI 成功且 Documentation Agent 完成发布文档收口前，不更新
`CURRENT_STATE.md`、根 README、公开 main、tag 或 GitHub 发布声明。

## 17. 白屏定位与专项风险验收补充（2026-09-08）

### 17.1 适用关系与候选身份

Product Owner 进一步确认：保留 PLAN §15 的真实 PDF artifact 预览路线，先把 React #310 视为
新预览方案的前端集成缺陷定位和修复，不因一次 Hook 崩溃回退到 HTML 模拟预览。只有在完成本节
定位后发现 PDF viewer 仍存在不可控的独立技术阻断，才重新提交预览降级方案给 Product Owner
选择；Development Agent 不得自行改回旧链路。

固定开发路径已在本节写入前产生声称的 H4-SRC `aecafc9` 及后续 RESULT 提交。它们先于本节新的
批准 PLAN commit/blob，不能自动视为满足本节，也不能直接送验收。Development Agent 必须先同步
本节，逐项复核现有修复并补齐缺失证据；因 H4-SRC 名称已经被使用，下一次正式冻结的 clean
候选统一记为 **H5-SRC**，即使最终产品源码字节相对 `aecafc9` 没有变化，也必须包含本节批准的
PLAN 身份并重新记录交接关系。

Product Owner 补充确认：H4 开发过程中曾按人工要求执行过一次回滚/撤回尝试，但再次真实生成
仍然白屏。当前尚未取得该次回滚所针对的 commit、文件、逻辑范围和前后 Console 对照。因此该
尝试只能证明“当时撤回的那部分变化不足以消除问题”，不能证明 PDF.js、结果页状态切换或其他
新预览集成代码已经排除。H4 按失败候选保留，禁止围绕同一未证实假设继续反复回滚。

### 17.2 开发侧具体定位方法

1. **建立动态最小复现**：同一个已挂载工作台必须实际经历“初始 → 生成中 → 成功响应 → PDF
   预览与依据”。不能只把最终成功对象静态 mount。正式 fixture 使用虚构内容，但字段形态覆盖
   `pdf_download_url`、`pdf_artifact_id`、`pdf_sha256`、PreviewAnchor、多 section/entry/bullet、
   空与非空 `fact_refs` 及双下载地址；现场真实响应只允许在本机临时定位，不进入仓库。
2. **取得非压缩源码栈**：在 development build 复现 #310，记录组件、源码行号、Hook 类型和
   React 给出的前后 Hook 顺序差异；生产 bundle 的压缩函数名不能代替源码定位。
3. **按变更范围审计**：从 H2 到 H3 的结果状态切换、PDF viewer、PreviewAnchor overlay、依据栏、
   worker 初始化、下载区和新 custom Hook 开始，检查条件/循环/回调中的 Hook，以及提前 return
   前后 Hook 数量变化；审计不能只限于报错栈最上层组件。
4. **必要时提交二分**：若源码栈仍不能确认引入点，使用上述自动复现测试在 H2 与 H3 间执行
   `git bisect`；不可构建的中间提交标记 skip，不得臆测为 good/bad。
5. **还原回滚事实**：记录已执行回滚的目标 commit/文件/行为、回滚前后实际 bundle、Console
   与复现结果；如果只是部分撤回、重新构建缺失或运行的仍是旧包，必须明确，不得写成“回滚无效”
   后跳过定位。
6. **先证据后修复**：Development Agent 的 RESULT 必须先记录修复前可重复失败、具体根因和漏测
   原因，再记录修复。只写“调整 useEffect 后恢复”不满足交接。

### 17.3 结构修复与同类风险

页面阶段应由稳定组件边界承载。推荐由父级只选择 `InputView`、`ProcessingView`、`FailureView`
和 `ResultView`，并让 `ResultView` 内的 `PdfPreview`、依据区和导出区各自保持固定 Hook 顺序；具体
组件命名不是硬性要求，但外部行为和 Hook 不变量必须相同。

所有 Hook 必须在组件顶层无条件调用，不得位于条件分支、循环、事件函数或可能提前 return 之后；
custom Hook 内部同样适用。Development Agent 必须确认 React Hooks ESLint 规则真实覆盖全部产品
前端源码，并把 Hooks 规则错误升级为阻断，不能混在既有普通 ESLint 债务中报告后继续通过。

Error Boundary 分成结果区域与应用外层两个恢复边界时，应避免内层 viewer 错误拖垮工作台，也要
避免外层 fallback 重新创建生成 operation。错误边界不能吞掉根因、隐藏真实 PDF 能力，或把
Console 无异常替换成“用户看不到异常”。

### 17.4 专项风险检查矩阵

新的独立验收必须对以下风险做动态检查：

| 风险组 | 必测状态 | 阻断条件 |
|---|---|---|
| Hook 顺序 | 初始→生成中→成功/失败、PDF loading→ready/error、依据选择/取消 | 任一 #310、Hooks warning 或不同渲染路径 Hook 顺序变化 |
| PDF 生命周期 | URL 从空到有效、更换 artifact、anchors 空→非空、加载中卸载、请求中止、worker 失败 | 白屏、旧 PDF、异步更新已卸载组件、overlay 与 artifact 串用 |
| 错误隔离 | `PdfPreview`、overlay、依据区、导出区分别注入 render exception | 空白 body、无恢复界面、错误扩散到整个应用 |
| 调用幂等 | 成功切页、viewer 重试、Error Boundary 恢复、React StrictMode 双执行 | 第二次生成 POST、新 operation、重复模型调用或计费 |
| 产物保持 | 前端渲染异常、viewer 失败、返回工作台 | 已成功 PDF/DOCX 被删除、覆盖或错误标为生成失败 |
| 生产差异 | development、production build、onedir 使用同一成功 fixture | 只在开发环境通过，生产 bundle/onedir 白屏或行为分叉 |

### 17.5 独立验收角色与不可 SUSPEND 项

Development Agent 负责定位、方案选择、修复和自测。H5 完成后应使用一个**新的独立验收任务**；
验收 Agent 不提前参与根因分析、实现方案或源码修复。若确需在修复前增加只读风险顾问，该角色
不得再承担 H5 的独立验收。

H5 验收必须在可运行真实浏览器的环境完成以下项目，不允许标记 SUSPEND 后给出 Conditional Pass：

1. 同一组件实例从生成中进入成功结果，页面与 Console 均无 React #310/Hook warning；
2. PDF viewer 生命周期矩阵至少覆盖 URL/anchors 变化、加载失败和组件卸载；
3. 四个结果子区域异常注入均命中 Error Boundary，页面可恢复且不新增 operation；
4. production build 与 onedir 实际显示 PDF 结果页，可选择依据并下载 Word/PDF；
5. 生成请求计数、operation 身份和产物 hash 证明没有重复调用或旧 artifact 污染。

验收还须复跑 R9、R17、R17a、完整 precheck、前端 build 和包内资产一致性，证明专项修复没有
破坏 H3 已通过的 PDF/字体/授权边界。无法提供浏览器运行条件时，结论只能是“验收未完成”，
不得把静态源码检查、CSS 推断或开发截图替代本节动态门禁。

### 17.6 H5 集中任务

| Task | 工作 | 完成标准 |
|---|---|---|
| T12-R24 | 还原回滚事实并建立动态复现 | 记录回滚对象/包身份/前后 Console；H3 或等价旧状态稳定触发 #310，虚构 fixture 可重复 |
| T12-R25 | 定位根因并复核现有 H4 修复 | 非压缩栈、组件/行号、Hook 差异和漏测原因闭合；现有修复不足时完成结构修正与同类审计 |
| T12-R26 | 完成 Hooks、PDF 生命周期与错误隔离矩阵 | Hooks lint 为阻断；六组动态风险在 development、production build、onedir 通过且无重复 operation |
| T12-R27 | 更新 RESULT、重建包并冻结 H5 | 交接证据完整；新 PLAN 身份进入候选；形成 clean H5-SRC 与只改 RESULT 的开发交接提交 |

### 17.7 开发交接补充

H5 RESULT 至少包含：修复前/后 Console、非压缩组件栈、失败测试、Hooks lint 输出、六组风险矩阵、
生成 API 调用计数、operation/artifact 身份、production/onedir 浏览器证据、Word/PDF 下载 hash、
完整命令与退出码。Documentation Agent 只核对交接身份和文档/产物机械闭环，不替代专项源码
验收。H5 独立验收与 Product Owner 第四次 T12 均通过前，继续禁止发布。

## 18. H6 可移交测试资产与 onedir 分层门禁修订（2026-09-08）

### 18.1 修订原因与适用关系

Product Owner 审阅 H5 补证后批准调整 PLAN §17 的执行边界。H5 已证明旧态 #310 可由虚构 fixture
确定性复现，也完成 development/production 的部分动态矩阵；但 fixture、控制脚本和详细步骤仍在
ignored 本地目录，固定 review 无法从候选重建同一用例。同时，要求最终 onedir 对四个结果区域逐一
注入源码异常，会迫使正式包携带测试后门，或要求只读验收者修改源码后重建另一个包；两种做法都
不能证明最终交付二进制本身，故本节以分层门禁取代 §17.5/§17.6 中“六组风险全部在 onedir 注入”
的字面要求。

§17 的根因、风险组和不可 SUSPEND 原则继续有效；只调整“哪一层负责哪种动态验证”。H5-SRC
`012242c` 已被使用，补齐可移交测试资产后的新 clean 候选统一记为 **H6-SRC**。H6 不得借测试
收口修改用户交互、PDF 方案、生成业务或 V2.1.1 功能。

### 18.2 必须进入候选的测试资产

Development Agent 必须把以下内容整理为仓库内稳定、可审计、可重复运行的测试资产，而不是继续
依赖 ignored `validation-artifacts/`：

1. 仅含虚构姓名、经历、JD、PDF、DOCX、PreviewAnchor 与 operation/artifact 的确定性 fixture；
2. 能驱动同一工作台实例完成初始、生成中、成功、业务失败、PDF loading/ready/error 与依据切换
   的自动化或半自动化 runner；
3. 能在**测试环境**分别让 `PdfPreview`、overlay、依据区、导出区抛出 render exception 的注入
   机制；该机制不得进入正式应用路由、普通构建入口、生产包或对外 API；
4. 生成 POST 计数、operation/artifact 身份、PDF/DOCX hash、Console/Hook warning、页面非空与
   Error Boundary 恢复断言；
5. 一条从干净 checkout 安装依赖并运行全部专项用例的入口，退出码非零即阻断。

测试资产不得包含真实用户数据、真实 API Key、本机绝对路径、历史 Console 中的个人信息或在线
服务依赖。H6 的统一预检必须调用该入口，至少覆盖不需要 GUI 人工判断的确定性断言。

### 18.3 development 与 production test build 门禁

同一份已提交 fixture 必须在 development 和不含源码热更新的 production test build 中完整覆盖
PLAN §17.4 六组风险，并明确验证：

- H3 或等价旧态稳定触发 #310，H6 同一 fixture 无 #310、Hook warning 或白屏；
- PDF URL 空→有效、artifact 更换、anchors 空↔非空、加载中卸载、请求中止、worker/字节失败；
- `PdfPreview`、overlay、依据区、导出区四处异常分别命中预期边界并可恢复；
- React StrictMode、成功切页、viewer 重试和 Error Boundary 恢复均不新增生成 POST/operation；
- viewer 或 UI 失败不删除、不覆盖已成功 PDF/DOCX，下载字节与记录 hash 一致。

production test build 只用于测试，不得被复制进最终 onedir。最终生产 build 必须重新从 clean H6
源码生成，并由文件清单和 hash 证明不含 fixture server、故障注入入口、测试路由或调试数据。

### 18.4 最终 onedir 非侵入式门禁

最终 onedir 只验证真实交付二进制能够观察到的行为，不修改候选源码，也不携带故障注入后门。
Development Agent 与独立验收 Agent 均须在隔离 runtime 中执行：

1. 初始→生成中→成功结果的完整链路，页面和 Console 无 #310/Hook warning，PDF viewer、依据与
   Word/PDF 下载可用；生成 POST 和 operation 各为一次；
2. 重复打开结果、切换依据、viewer 重试和返回工作台不触发第二次生成，不改变 artifact 身份；
3. 通过浏览器请求阻断、隔离 runtime 中临时移走/损坏本轮 PDF 等非源码手段，验证 PDF 不可用态
   诚实可见、Word 保持可下载、页面不白屏；测试后恢复或清理隔离数据；
4. 下载 PDF/DOCX 的 hash 与后端记录及 viewer artifact 一致，旧 bundle/旧 artifact 不得混入；
5. onedir 内前端、worker、字体和授权材料与 clean H6 最终生产 build 逐文件一致，且不存在测试
   fixture、注入开关、测试路由或本机路径。

四区域源码级 render exception 注入只在 §18.3 的可移交测试环境重复，不要求最终 onedir 注入。
若 onedir 的正常链路或上述非侵入式失败路径无法执行，仍不得 SUSPEND 后给出通过结论。

### 18.5 H6 集中任务与交接

| Task | 工作 | 完成标准 |
|---|---|---|
| T12-R28 | 固化虚构 fixture 与 runner | 测试资产进入候选、无隐私/密钥/绝对路径；干净 checkout 可运行，失败为非零退出 |
| T12-R29 | 完成 dev/production test build 全矩阵 | 六组风险、四区域异常、Hook/幂等/artifact/hash 全部命中；记录命令、计数和退出码 |
| T12-R30 | 重建并验证最终 onedir | 使用 clean 正式 build；完成 §18.4 五项，证明包内无测试后门且资产逐文件一致 |
| T12-R31 | 更新 RESULT 并冻结 H6 | 形成新的 clean H6-SRC 与只改 RESULT 的 H6-DEV；交接材料足以让 review 原样重建 |

H6 RESULT 至少记录测试入口、依赖安装、各矩阵计数、浏览器/视口、Console、API/operation/artifact
身份、下载 hash、最终包文件清单与退出码。Documentation Agent 只在这些身份与材料机械闭合后
移动固定 review。独立验收者不得参与 H6 实现，须从 H6-SRC 的已提交测试资产重跑 §18.3，并在
最终 onedir 独立执行 §18.4；两层均不得以开发截图或静态源码检查代替。

H6 独立验收与 Product Owner 下一次 T12 均通过前，继续禁止更新 `CURRENT_STATE.md`、根 README、
公开 main、tag 或 GitHub 发布声明。

## 19. Product Owner 第四次结果页修正：导出位置、PDF 忠实度与下载链（2026-09-08）

### 19.1 触发事实、优先级与适用关系

Product Owner 在真实生成结果页发现三类问题：

1. 只含“下载 Word / 下载 PDF”的导出卡没有位于期望的右下角；
2. 同一结果的 Word 打开后排版和观感正常，但真实 PDF artifact 中照片占位框位置与 Word/模板
   关系不一致，且文字/页面观感明显模糊；结果页加载的是真实 PDF，故预览与 PDF 呈现同样问题；
3. 正常结果的 PDF 下载 URL 出现一次 HTTP 404 和后续 HTTP 405，界面显示“PDF 下载失败
   （HTTP 405）”，核心 PDF 交付不可用。

本节形成 **H7**，任务编号 T12-R32 至 R35。它是 V2.1.0 发布前新的人工验收阻断，与 H6 分轨：
H6 继续只处理白屏复现/风险 runner 的可信性，H7 处理真实产品布局、PDF artifact 与下载协议。
H6 runner 修正不得顺带宣称 H7 已解决；H7 候选必须建立在最终 H6 clean 候选之后。

优先级：PDF 正常下载 404/405 为 P0；PDF 本体模糊和占位框错位为 P1；导出卡位置不符为 P1。
三项全部关闭前，Product Owner 人工验收仍不通过，禁止发布 V2.1.0。

本节明确覆盖 PLAN §14.2/C、§14.4/T12-R11、§15.3 中所有“左下角导出卡”表述：最终口径为
**结果页可用区域右下角固定**。其他既有要求继续有效：页面 shell 不滚动、卡片外框不因内容变化、
卡内只保留两个按钮、预览与下载绑定同一不可变 PDF artifact。

### 19.2 导出卡冻结布局

- 导出卡固定占据结果页右侧栏的最下方网格单元，即结果页可用区域右下角；它随视口网格缩放，
  但不得漂到左侧、悬在内容中部或因上方依据内容多少改变外框位置/尺寸；
- 卡内只保留“下载 Word”“下载 PDF”两个按钮，不增加标题、文件名、说明、复制全文、短码或统计；
- 两按钮在卡内水平并列；错误文案如需显示，只能使用预留固定错误区，不得把卡片撑高或推动按钮；
- 1440×900、1280×720、1920×1080 三个桌面视口均须证明页面 `scrollWidth==clientWidth`、
  `scrollHeight==clientHeight`，导出卡右边/下边与结果页内容网格对齐，卡内溢出不产生页面滚动。

### 19.3 PDF 问题的根因方向、定位顺序与禁止假设

Product Owner 已进一步确认：**下载/独立打开的 PDF 与结果页预览呈现一致，而 Word 正常**。因此
这里不是“PDF 正常、viewer 单独显示错误”，预览反而证明它忠实显示了当前 PDF artifact；核心缺陷
位于 **PDF artifact 生成结果相对 Word/模板失真**。开发必须优先检查和修复 PDF Renderer/字体/
几何/绘制链，不能先通过调整 PDF.js 掩盖错误 PDF。当前仍未知的是 PDF 生成链内部哪一环导致失真，
以及 404/405 的具体请求方法和生命周期根因。

开发按以下顺序保留可复核证据：

1. 对同一 operation 保存 ResumeDocument、DOCX、PDF、artifact_id、文件名、URL、MIME、size 和
   SHA-256；确认 viewer 实际字节与下载/独立打开的 PDF 字节完全相同，以固定“viewer 忠实显示错误
   PDF”这一事实，不再把主因在 PDF 与 viewer 之间平均分配；
2. 以正常 Word 和 `pm_template v1.2` 为版式参考，直接检查 PDF artifact 的字体嵌入/字重、坐标、
   照片框、分隔线、页面缩放与文本绘制方式，修复 PDF 生成链；
3. PDF artifact 修复并在独立阅读器确认清晰、位置正确后，再验证结果页 viewer 没有引入额外模糊；
   只有修复后的同一 PDF 在独立阅读器清晰、viewer 仍额外变糊时，才把 PDF.js viewport/canvas DPR
   作为第二个独立问题处理；
4. 从 Network/服务端日志记录每个失败请求的 method、完整 URL、状态码、响应 MIME、artifact 文件
   是否存在及生成/清理时间。404 与 405 必须分别解释，禁止把二者笼统归为“网络问题”；
5. 核对正常链路是否发出 GET、HEAD 或 Range 请求。最终可由后端支持实际需要的方法，也可删除
   无必要的前端探测，但正常 viewer 与下载不得产生 4xx/5xx、不得重生成或切换 artifact。

禁止通过回退 HTML 伪预览、截图整页写入 PDF、吞掉 404/405、把失败按钮伪装成功、禁用 PDF、
依赖 CDN/Office/LibreOffice 或让下载时临时生成另一份 PDF 来绕过问题。PLAN §15 的真实 PDF
artifact 路线保持不变。

### 19.4 PDF 视觉与画质完成标准

- `pm_template v1.2` 仍是共同模板规格。Word 与 PDF 不要求办公软件层面的像素完全一致，但姓名、
  联系方式、求职意向、章节顺序、条目、日期、bullet、照片占位框的尺寸和版面关系必须一致；
- 照片占位框必须位于页首右侧信息区，与 Word/模板参考保持同一顶边、右边和宽高关系；其底边不得
  穿过“教育背景”标题或首个章节分隔线，正文不得进入占位框；几何测试使用模板单位比较，允许
  不超过 2 mm 的渲染容差；
- PDF 正文应保持可选择/可提取的矢量文字，不得把整页或正文栅格化。独立 PDF 阅读器在 100% 与
  150% 下不得出现截图所示的明显发虚、重影、异常粗黑、字形粘连或裁切；
- viewer 必须按实际 DPR 设置 canvas backing store 与 CSS 展示尺寸，DPR 1/2、浏览器 100% 缩放下
  均保持清晰；改变 viewer 宽度或滚动不得重新生成 PDF；
- PDF 与 DOCX 继续来自同一 ResumeDocument/operation，内容与事实引用集合一致；视觉修复不得
  改写事实、丢 bullet、改变生成文案或破坏 PreviewAnchor 与当前 artifact 的绑定。

### 19.5 PDF 下载协议与失败边界

正常生成完成后必须满足：

- PDF artifact 在响应 URL 暴露前已原子写入最终位置；GET 下载返回 200、`application/pdf`、正确
  `Content-Length`，文件以 `%PDF-` 开头且 SHA-256 与响应、viewer 当前字节一致；
- 若产品路径实际需要 HEAD，则 HEAD 返回与 GET 一致的成功元数据；若不需要，则前端不得发送会
  产生 405 的探测。若 PDF.js 使用 Range，请求须返回有效 200 全量或符合协议的 206，不得破坏 viewer；
- 正常生成、打开 viewer、点击“下载 PDF”全过程 Network/Console 中该 artifact URL 的 404/405
  计数均为 0；点击下载不得触发新的 generate POST/operation；
- 缺失、损坏、MIME 错误或 hash 不符仍须 fail closed：固定区域显示明确失败，Word 若成功仍可
  下载；不得白屏、不得删除或覆盖已成功 DOCX、不得回退旧 PDF。

### 19.6 H7 集中任务与交接

| Task | 工作 | 完成标准 |
|---|---|---|
| T12-R32 | 修正导出卡位置 | 右侧栏最下方固定卡，只含两个按钮；三桌面视口外框稳定、页面零滚动 |
| T12-R33 | 修复 PDF artifact 生成链 | 以 Word/模板为参考优先修 PDF Renderer/字体/几何；照片框符合 §19.4、PDF 矢量文字清晰；随后证明 viewer 未额外降质 |
| T12-R34 | 修复 PDF 下载 404/405 | 记录并解释 method/URL/生命周期根因；正常 GET/viewer/download 全部成功且 hash 同源，404/405 为 0 |
| T12-R35 | 回归、包重建与 RESULT | 固定 fixture、视觉/协议正反向、三视口、现有预检通过；重建 onedir 并在 RESULT 冻结 H7-SRC/H7-DEV |

H7 的 Development Agent 必须在 RESULT 记录根因、修改文件、HTTP 方法与状态码矩阵、PDF/DOCX/
viewer/download hash、照片框几何数据、DPR/视口截图、回归计数和包身份。Documentation Agent 只做
身份、范围、证据完整性与文档事实核对；独立 Acceptance Agent 必须实际打开 standalone PDF 与
结果页、执行两个下载，并复核正常链路零 404/405。Product Owner 最后再次进行 T12 视觉确认。

## 20. Product Owner 第五次返工：DOCX→PDF 单一排版链与生成计时修正（2026-09-09）

### 20.1 触发事实、结论与覆盖关系

Product Owner 使用同一次真实生成得到的 DOCX 与 PDF 进行人工对照后确认：DOCX 在 Microsoft Word
中排版和画面正常，应用生成的 PDF 及结果页 PDF.js 预览彼此一致，但二者相对 DOCX 存在明显的
字体、换行、间距、照片占位框位置和清晰度差异。进一步核对表明，当前 PDF 并非由最终 DOCX 转换，
而是 ReportLab 根据 `ResumeDocument` 另行手绘；因此“DOCX 正常、PDF 与预览一致但错误”是两个
并行排版实现发生漂移，不是 PDF.js 单独渲染错误。

同轮人工体验还确认生成页计时失真：顶部“已用时”持续增长，而正在执行的用户阶段显示 `—`，右侧
可能仍显示上一阶段的静态耗时；终态前后，四个用户阶段之和也不能解释总耗时。源码核对确认：

1. 输入页粘贴 JD 后自动调用 `/jd/analyze`，点击生成后 `/resume/generate-docx` 又执行一次严格 JD
   分析；前一次结果没有作为后端可信分析 artifact 复用，形成重复 LLM 调用；
2. 后端总耗时从 operation 开始计算，包含 `migration_check`、`embedding_ready`、`jd_analysis`、
   `sql_readback`，但当前四个用户阶段从 `select_experiences` 才开始，存在未显示耗时；
3. 前端阶段耗时只求和已完成事件的 `elapsed_ms`，未把后端已有的活动阶段
   `stage_elapsed_ms` 纳入，所以执行中不实时，完成后才跳成最终值；
4. 右侧允许回看历史阶段本身符合已批准交互，但没有明确区分“当前运行阶段”和“当前查看阶段”，
   导致历史阶段耗时被误解为当前耗时。

本节形成新的发布阻断和下一候选 **H8**。H7 及其内部 fixture 证据保留为历史记录，但不足以证明
真实下载 artifact 的 Word/PDF 一致性，H7 不再具备进入独立验收或发布的资格。

本节明确覆盖以下旧口径：

- 覆盖 §19.3、§19.4 中“继续修复独立 PDF Renderer/ReportLab 使其接近 Word”的技术方向；
- 保留 §15 的“结果页只预览真实 PDF artifact”和 §19.5 的下载协议要求，但 PDF 的来源改为最终
  DOCX 经固定转换器导出；
- 保留页面固定布局、依据回看、PreviewAnchor、Word/PDF 双下载和 fail-closed 要求；
- 本版本仍不实现内容流式写入预览。未来生成中的 HTML 结构化草稿可以替换处理中视图，但生成完成后
  仍必须以“DOCX→PDF→PDF.js”作为最终预览与交付链；“PDF 来自 DOCX”是稳定产品契约。

### 20.2 文档、转换器与最终视觉真源

V2.1.0 从 H8 起采用以下唯一产品链：

```text
ResumeDocument
  → DOCX Builder / pm_template
  → 已持久化、不可变 DOCX artifact
  → DocxToPdfConverter
  → 已持久化、不可变 PDF artifact
  → PDF.js 预览该 PDF
  → “下载 PDF”下载同一 PDF
```

真源边界如下：

- `ResumeDocument` 是结构化内容与事实引用真源；
- 最终 DOCX artifact 是本次结果的内容、模板和可编辑交付真源；
- 本版本冻结的 DOCX→PDF 转换器是排版执行器，不得另写第二套模板规则；
- 转换完成后的 PDF artifact 是结果页视觉预览与 PDF 下载的共同真源；
- PDF.js 只负责显示该 PDF，不承担修正版式、重新排版或生成另一份 PDF。

`services/pdf_renderer.py`/ReportLab 的简历排版路径必须从产品生成链完全退出。不得把
`ResumeDocument` 同时送入 DOCX Renderer 和 ReportLab Renderer，不得在转换失败时回退到旧 PDF，
不得通过 HTML、截图或 Canvas 导出伪装成功。若 ReportLab 在仓库中仍有与简历交付无关的用途，开发
必须列出引用；否则移除产品依赖、打包项和对应旧渲染测试，保留历史授权记录但不伪称仍在使用。

### 20.3 V2.1.0 本地转换器冻结方案

V2.1.0 是 Windows 本地测试/演示版本，当前唯一转换实现冻结为：

```text
DocxToPdfConverter
└── MicrosoftWordComConverter
```

具体契约：

1. Builder 必须先完整保存并关闭 DOCX，计算 `docx_sha256` 后，转换器只读取这份已持久化的确切
   字节；允许复制到隔离临时目录供 Word 打开，但复制前后 hash 必须一致；
2. 使用独立 Word COM 实例，以只读、不可见方式打开 DOCX，通过 Word 原生
   `ExportAsFixedFormat` 导出标准打印质量 PDF；禁止保存或修改原 DOCX；
3. 转换进程必须关闭宏、外部链接自动更新和交互弹窗，只接受本产品 Builder 生成的 `.docx`，不得
   把任意用户上传文件直接交给 Word 自动化；
4. DOCX→PDF 转换采用单 worker/互斥执行，设置具名超时和确定性清理。超时或异常只能终止本次转换
   所拥有的 Word 实例/子进程，禁止结束用户已经打开的其他 `WINWORD.EXE`；
5. PDF 先写入隔离临时文件；验证 `%PDF-` 文件头、非零页数、合理大小和可解析性后，原子移动到
   最终 artifact 路径，再计算 `pdf_sha256` 并向响应暴露 URL；
6. 必须记录但不得向普通用户暴露：转换器标识、Word 完整版本/build、OS、模板版本、必需字体清单、
   `docx_sha256`、`pdf_sha256`、页数、字节数、开始/结束时间和诊断码；
7. 启动或首次生成前执行转换能力检查：Word COM 可创建、所需字体存在、固定无隐私样例能在超时内
   导出并被读取。检查失败不阻断 Word 生成，但必须把 PDF 能力标记为不可用；
8. Word 未安装、字体缺失、COM 启动失败、弹窗/超时、PDF 校验失败时均 fail closed：保留并允许
   下载已经成功的 DOCX，PDF URL 留空，结果页在固定错误区明确显示 PDF 不可用；严禁 ReportLab、
   LibreOffice、旧 PDF、空 PDF 或其他转换器静默回退。

Word COM 只批准用于当前交互式 Windows 本地版本，不自动继承为服务器生产方案。上线前须对
Microsoft 云端转换、自托管商业 DOCX 引擎和 LibreOffice 等候选做真实模板专项比较，再冻结新的
`DocxToPdfConverter` 实现；服务端不得直接照搬无人值守 Office COM。替换转换器不得改变
“PDF 由最终 DOCX 转换而来”这一上层契约。

### 20.4 Artifact 身份、依据锚点与下载协议

每次生成成功必须形成同一 revision 下的一对不可变 artifact：

```text
result_revision_id
├── DOCX artifact: path + sha256 + size
└── PDF artifact:  path + sha256 + size + converter fingerprint
```

- 转换输入必须是响应中“下载 Word”指向的同一 DOCX 字节；预览输入必须是“下载 PDF”指向的同一
  PDF 字节；任何一处 hash 不同均为阻断失败；
- 打开结果页、PDF.js 重试、切换依据、下载 Word/PDF 和路由往返均不得重新生成或重新转换；
- 单条 Fact 重生成属于未来的新 revision，届时必须生成新的 DOCX/PDF 对，不得覆盖旧 artifact；
- Word 转换完成后，PreviewAnchor 必须从该确切 PDF 的文本层/坐标重新建立并绑定
  `pdf_sha256 + content_item_id/fact_refs`。禁止继续使用 ReportLab 推算的旧坐标；
- 中文空格、换行和 PDF text span 可被规范化后匹配，但不得用错误坐标假装命中。某条无法可靠定位时
  须记录 `anchor_status=unavailable` 并诚实降级为可查看依据、不高亮；H8 正常 fixture 的既定锚点
  应全部可定位；
- GET/HEAD/Range、MIME、404/405、原子发布与损坏/缺失失败边界继续执行 §19.5；正常链路中的
  viewer 字节、下载字节和 `pdf_sha256` 必须完全一致。

### 20.5 单次 JD 分析与性能归因

H8 的普通用户主链必须保持“一次点击后等待结果”，并取消输入页的重复 LLM 分析：

- JD 输入页只做字符数、空值和本地格式检查；普通用户粘贴 JD 时不再自动调用 LLM；
- 点击“生成岗位简历”后创建唯一 operation，由该 operation 在第一用户阶段执行且只执行一次严格
  JD 分析；分析结果在同一 operation 后续选材、改写和 Builder 中复用；
- `/jd/analyze` 可为开发者/API 兼容保留，但普通生成页不得在一次生成前后调用它；若未来恢复预分析，
  必须先建立后端持久化的 `jd_analysis_id + jd_sha256 + prompt/model fingerprint`，生成端校验后复用，
  不得直接信任前端提交的分析 JSON，也不得再次调用 LLM；
- 确定性 stub 和真实日志均须统计每个 operation 的 JD LLM 调用次数。正常生成必须为恰好 1；本地
  校验失败为 0；重试/新 revision 必须具有新的 operation 身份并单独计数；
- Fact 召回耗时只计算事实选择相关步骤，禁止把 JD 分析或当前内容改写时间记到“挑选事实”。性能
  结论必须来自阶段事件，不再根据页面总时长猜测。

### 20.6 用户阶段与后端计时真源

后端必须直接提供稳定的用户阶段投影；前端不得继续用硬编码数组自行拼接内部 stage code 后计算时间。
本版本冻结为四个覆盖完整 operation 的用户阶段：

| 用户阶段 | 用户文案 | 包含的当前内部工作 |
|---|---|---|
| P1 `job_understanding` | 理解目标岗位 | 生成准备、就绪检查、唯一一次 JD 分析、履历读取 |
| P2 `fact_selection` | 从你的履历中挑选相关事实 | Experience 选择、Fact/证据选择 |
| P3 `content_drafting` | 生成并润色简历内容 | 基于已选事实的受约束改写 |
| P4 `artifact_build` | 排版并生成 Word/PDF | ResumeDocument 构建、DOCX 渲染/保存、Word→PDF 转换、响应发布 |

实现可以保留内部技术 stage 用于开发者诊断，但每个内部 stage 必须归属于一个用户阶段。operation
创建后必须立即开始 P1；昂贵调用之前先发出用户阶段 `STARTED`；P4 发布响应后立即结束 operation。
终态不得存在无法归属的长时间空洞。

计时规则：

- `operation.elapsed_ms` 是从 operation 创建到终态的服务端单调总时间，是“总用时”唯一真源；
- 每个用户阶段由后端返回 `status`、`started_at`、`ended_at`、`elapsed_ms`；活动阶段另返回持续增长的
  `live_elapsed_ms`（或语义等价字段），前端只展示，不用本地时钟重新推算；
- 用户阶段包含多个内部步骤时，已完成部分与当前活动部分必须连续累计，不得等到整个阶段完成才显示；
- 可见页面轮询间隔保持约 1 秒，活动阶段与总用时在正常网络下至少每 1.5 秒更新一次；后台标签页
  可以降频，但恢复可见后下一次轮询必须立即校正；
- 阶段完成后耗时冻结。终态时四阶段耗时之和与总耗时的差值必须不超过 250ms；超过阈值须把空洞
  归入真实阶段或明确诊断并使门禁失败，不得仅在前端改数字；
- P4 必须包含 Word→PDF 的实际转换时间，不能因切换转换技术再次产生不可见等待。

### 20.7 当前阶段、历史回看与时间标签

处理页继续遵守已批准交互：“右侧默认显示当前阶段；跨阶段时切换到新阶段；旧阶段可点击左侧切回”。
补充以下冻结规则：

1. 新 operation 从 P1 开始；每次后端用户阶段发生变化，右侧默认自动切换到新的活动阶段；
2. 用户点击已经开始或完成的旧阶段后，右侧保留其完整历史事件和冻结耗时，允许随时回看；
3. 查看阶段不等于运行阶段。二者不同的时候，右侧必须显示“历史阶段”，并同时提供不抢占内容的
   “当前正在执行：P<n> <名称> · <实时阶段耗时>”提示；
4. 顶部统一写“总用时”，右侧统一写“本阶段用时”，不得都使用无主语的秒数；
5. 用户正在回看历史阶段时，当前阶段继续计时；下一次真正跨阶段仍自动展示新阶段，用户之后仍可
   再次点回任意已开始阶段；
6. 不得使用假进度、预估秒数或前端动画代替后端事件。轮询暂时失败时保留最后快照并显示连接状态，
   不得把旧阶段时间当成仍在增长。

### 20.8 H8 开发验证与独立验收门禁

Development Agent 必须先在 clean 工作树完成以下证据，全部通过后才允许命名 H8-SRC：

1. **真实 artifact 对照**：至少使用 Product Owner 本轮暴露问题的同类型真实生成路径和一个无隐私
   固定 fixture；保存 Builder 输出 DOCX、应用转换 PDF、独立打开截图/栅格、字体清单、页数和 hash。
   姓名/联系方式/求职意向、章节顺序、条目、日期、bullet、照片框和换行均以最终 DOCX 在冻结 Word
   环境中的表现为基准；应用 PDF 必须来自该 DOCX，禁止只比较内部结构对象；
2. **转换来源负向**：注入 Word 缺失、字体缺失、COM 启动失败、超时、输出空/损坏、hash/path
   错配，逐项证明 Word 可独立下载、PDF fail closed、无 ReportLab/LibreOffice/旧 artifact 回退；
3. **同一 artifact**：后端响应、PDF.js 实际请求、独立下载的 PDF hash 三者一致；重复预览/下载
   不增加转换次数；GET/必要 HEAD/Range 正常，404/405 为 0；
4. **锚点**：正常 fixture 的全部 `content_item_id/fact_refs` 在 Word 转换后的确切 PDF 上重新定位；
   点击依据不触发生成或转换。无法定位负向须诚实降级，不得加载旧坐标；
5. **JD 调用计数**：普通输入→生成完整链中 `/jd/analyze` 前置调用为 0，生成 operation 内严格 JD
   LLM 调用恰好 1；修改 JD 后新生成仍为新 operation 内恰好 1；
6. **确定性时间矩阵**：为四阶段注入已知延迟，机器断言活动阶段实时增长、完成后冻结、跨阶段自动
   切换、历史回看不影响当前计时、所有内部 stage 有归属、终态阶段和与总时长差值 ≤250ms；
7. **真实时间证据**：在真实模型链记录 operation、四用户阶段、内部步骤、LLM 请求次数、首个可见
   阶段时间和总时长；明确区分 JD 分析、Fact 选择、内容改写、DOCX 与 PDF 转换，禁止用截图推断；
8. **回归与包**：完成 H6 runner 的开发侧方案 A 或逐场景方案 B、六项阻断预检、前端 build、真实
   onedir 重建与包内运行；任何 mandatory 项不得后台未结束、SUSPEND 或移交给验收者代跑。

独立 Acceptance Agent 必须绑定 clean H8-SRC，从已提交 runner 重跑同一转换、协议、锚点、JD 次数、
计时和 onedir 矩阵；不得参与 H8 实现，不得以开发截图代替实际下载与打开。Product Owner 最终重新
检查真实 Word/PDF/预览一致性、四阶段理解和实时时间。三方全部通过前，不更新 `CURRENT_STATE.md`、
根 README、公开 main、tag 或发布声明。

### 20.9 H8 集中任务与交接

| Task | 工作 | 完成标准 |
|---|---|---|
| T12-R36 | 固定真实差异证据并撤销 H7 门禁资格 | 真实 DOCX/PDF/预览来源与差异可复核；RESULT 明示 H7 未通过，不再沿用内部 fixture 结论 |
| T12-R37 | 建立转换器边界并退出 ReportLab 产品链 | `MicrosoftWordComConverter` 读取确切 DOCX；旧简历 PDF Renderer 零调用、零回退 |
| T12-R38 | 完成 Word→PDF artifact、协议与失败边界 | 原子发布、双 hash、环境 fingerprint、GET/Range、viewer/download 同源及全部负向通过 |
| T12-R39 | 重建 Word PDF 上的 PreviewAnchor | 锚点绑定 `pdf_sha256 + content_item_id/fact_refs`，正常 fixture 全命中，失败诚实降级 |
| T12-R40 | 消除重复 JD 分析并建立完整用户阶段投影 | 普通输入页零 LLM 预分析；每 operation 恰好一次 JD 分析；所有内部步骤归入 P1–P4 |
| T12-R41 | 修正实时计时与历史回看 | 总用时/本阶段用时口径明确，活动时间实时、终态差值达标，跨阶段与历史查看符合 §20.7 |
| T12-R42 | 完成开发侧专项矩阵、回归和 onedir | §20.8 八组证据全部由开发侧先通过，无待运行/移交/SUSPEND；包内转换能力与源码一致 |
| T12-R43 | 更新 RESULT 并冻结 H8 | 先形成 clean H8-SRC，再形成只改 RESULT 的 H8-DEV；记录命令、计数、hash、版本、偏差与包身份 |

H8 RESULT 顶部必须提供机器可读门禁摘要，至少包含：候选/父提交、工作树状态、PLAN blob、转换器与
Word build、模板/字体 fingerprint、DOCX/PDF/viewer/download hash、转换次数、JD LLM 次数、四阶段
耗时与总和差、全部测试入口/计数/退出码、onedir 身份，以及 `pending/running/suspend = 0`。任何字段
缺失或与证据不一致，Documentation Agent 不得移动固定 review，也不得向独立验收交接。
