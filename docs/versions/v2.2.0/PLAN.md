# ResumeAssistant V2.2.0 PLAN

> Plan Revision：2
> Supersedes：Revision 1（批准 PLAN blob `324302a0ef6d81214c752d12281c221f2550f320`）
> 状态：已获 Product Owner 批准
> 日期：2026-09-15
> 产品源码基线：annotated tag `v2.1.0` → `5d72a2e08ebd4fa416b4b1dcdd79c1d08dfc7cfd`
> Revision 1 开发候选 H：`09ee23651161afe7dc24f2e839618f49213e4217`
> Revision 1 文档交接：`DOC_ALIGNED`，文档提交 `e4f9e499d1013fd03bf150bd9f50c8476cd01cbb`
> 开发路径：`<current-workspace>` 的 `version/v2.2.0`
> 本 Revision 授权：第二批可见界面、Design Snapshot 集成、最终纵切与发布候选
> Design Baseline：源 `D-003` → canonical `DS-003`
> Product Owner 批准内容基线：commit `af2f8f9bc193fbe78e77e5d6009b5ad7836d6f3e` / PLAN blob `7104bfbd430cefb66cfc29bb92520c2ff65aeaff`

## Required Reading（Development Agent 必读）

按顺序读取，完成后在 RESULT 身份区逐项确认；缺一项不得开始 Revision 2 实现：

1. `docs/README.md` §0、§1～§5；
2. `docs/CURRENT_STATE.md`；
3. 本 PLAN 全文；
4. `docs/HUMAN_AI_WORKFLOW.md` §3.1、§3.2、§3.3、§3.4、§6、§11；
5. `docs/versions/v2.2.0/RESULT.md` §6～§9；
6. `docs/design/baselines/V2.2.0/DS-003/SNAPSHOT.md`、`SPEC.md`、
   `prototype/README.md` 和 `prototype/index.html`。

不得读取或跟随 Design Agent 的 `current/`、后续工作稿或新快照。无需默认重读 DRAFT、完整 HISTORY、
完整 DECISIONS 或历史版本 RESULT；遇到本 PLAN 点名的冲突时才定向读取。

## 0. 合同性质

本文件获批后成为 V2.2.0 唯一可执行开发合同。Revision 1 已完成设计无关的 Task、SSE、生成、性能、
内容模型和 artifact 基础；Revision 2 只在该 checkpoint 上实现批准设计、真实前后端集成和最终门禁。

本 Revision 仍采用单一 Development Integrator 修改产品源码；测试、构建和不冲突的只读验证可以
并行，但不得由多个开发角色并行改同一产品链。目标导向冻结允许在不改变用户结果、Design Baseline、
事实真源、调用公式、并发上限和成本上限的前提下调整实现细节。

Revision 2 已取代 Revision 1，Development Agent 只能在本合同和 `DS-003` 实施矩阵内继续实现。
实现证据否定路线时按 `HUMAN_AI_WORKFLOW.md` §3.4 开启 `CHALLENGE_OPEN`。

## 1. 已冻结基线

### 1.1 Revision 1 checkpoint

- 开发候选 H：`09ee23651161afe7dc24f2e839618f49213e4217`；
- 文档交接：`DOC_ALIGNED`；
- 已完成：任务持久化、输入 revision、SSE 恢复、实际取消、Experience 并发 2、逐 Fact 发布、
  reason 增量、内容字段修正、短输入修复、DOCX/PDF 后端链、容量清理与真实性能矩阵；
- 本 Revision 必须复用上述单一实现，不得另建第二套任务、事件、生成或 artifact 链。

### 1.2 Design Snapshot 导入身份

| 字段 | 冻结值 |
|---|---|
| 源 Snapshot | `<design-workspace>/snapshots/D-003` |
| 源状态 | `Approved / Immutable` |
| 批准者 | Product Owner |
| 批准证据 | `R-D003-12`；明确“审批通过，按文档要求做下一步” |
| canonical Baseline | `docs/design/baselines/V2.2.0/DS-003` |
| canonical ID | `DS-003` |
| 入口 | `prototype/index.html` |
| 主题 | A，单一生产主题 |
| 现实产品基线 | `v2.1.0` / `5d72a2e08ebd4fa416b4b1dcdd79c1d08dfc7cfd` |
| 源 manifest SHA-256 | `cc699466af400ee603a7e9fe39ef22e75bc7db37bd7150f41a0f0718ac9d0a61` |
| 导入文件 | 28 个：manifest 登记 27 个文件，加 `CHECKSUMS.sha256` 本身 |
| 导入校验 | 源与 canonical 逐文件 SHA-256 一致，mismatch=0 |

导入保持源快照字节不变。`SNAPSHOT.md`、`SPEC.md`、`DESIGN_QA.md`、`SCREENSHOT_MATRIX.md`、
`THEME_EVALUATION.md`、10 张主题 A 参考图及完整 `prototype/` 均纳入。Snapshot 中标为 Design-only
的能力只有进入 §3 实施矩阵后才构成本版本开发任务。

精确导入清单：

- 根目录：`CHECKSUMS.sha256`、`DESIGN_QA.md`、`SCREENSHOT_MATRIX.md`、`SNAPSHOT.md`、
  `SPEC.md`、`THEME_EVALUATION.md`；
- `previews/`：`empty-theme-A-1440x900.png`、`experiences-theme-A-1440x900.png`、
  `failed-theme-A-1440x900.png`、`p1-theme-A-1440x900.png`、`p2-theme-A-1440x900.png`、
  `p3-theme-A-1440x900.png`、`p4-theme-A-1440x900.png`、`privacy-theme-A-1440x900.png`、
  `saved-theme-A-1440x900.png`、`success-theme-A-1440x900.png`；
- `prototype/`：`index.html`、`README.md`、`server.cjs`；
- `prototype/assets/`：`app.js`、`fixture.json`、`sample-resume.docx`、`sample-resume.pdf`、
  `theme-tokens.css`、`workbench.css`；
- `prototype/assets/vendor/`：`pdf.mjs`、`pdf.worker.mjs`、`PDFJS-LICENSE.txt`。

## 2. 最终用户结果与不变量

### V220-G01 连续任务工作台

- 四步为“身份与目标 → 理解岗位 → 匹配经历 → 润色、预览与导出”；界面按 `DS-003` 呈现；
- 路由切换、浏览器刷新和页面重开不停止后端任务；只恢复后端已确认输入、权威快照和真实状态；
- dirty 输入必须明确显示“未保存”，不得把前端本地值冒充已保存；
- 关闭整个应用/后端、崩溃、系统重启或关机后的未完成任务续跑不在 V2.2.0 范围。

### V220-G02 保存、取消和新任务

- 姓名必填；电话、邮箱、所在地、目标岗位选填；JD 至少 60 字，最终有效性与容量以服务端为准；
- 每个新任务重新填写，不自动从 Profile、Career Memory、模板或上一任务回填身份；
- 取消停止本产品可控的 Provider 流、排队、事件、Word worker 和 artifact 发布，迟到结果被 fence；
- 释放活动槽后允许立即开始新任务；新任务不删除历史简历或 Career Memory。

### V220-G03 真实渐进结果

- P1 逐项显示已校验的 JD 业务条目；P2 逐项显示入选 Experience/Fact 与业务匹配依据；
- P3 每条 `headline + body + fact_refs` 完整校验后整条进入 HTML 过程预览；随后在同一 Fact 旁侧
  对绑定 `fact_id` 流式显示 reason；断流使用明确 fallback；
- 已完成阶段可回看最终业务结果，当前阶段自动选中且不可点击，未来阶段禁用；回看不暂停后台任务；
- 不展示模型私有思维链、评分或置信度。

### V220-G04 最终预览与 artifact

- P3 HTML 是过程展示，只读权威 `display_snapshot/ResumeDocument`，不是排版或下载真源；
- P4 成功后切换到真实 PDF.js viewer；viewer 与 PDF 下载读取同一不可变 PDF artifact；
- DOCX 继续是唯一排版真源，PDF 只由同一 DOCX 经 Microsoft Word COM 转换；
- Word/PDF 独立失败时 fail closed，只保留真实可用的下载，不显示残缺成功。

### V220-G05 内容和性能

- Revision 1 的联系方式、技能 2～4 类、Fact 加粗短标题、`fact_refs`、教育字段和短输入修正必须
  在最终 UI、ResumeDocument、DOCX、PDF 和下载链保持一致；Career Memory 不因生成润色而改变；
- 用户提交后真实状态反馈 ≤1 秒；短/典型/长 × cold/warm 首个完整 Fact 的 `n>=3` 中位数和最大值
  均 ≤15 秒；有 V2.1.0 基线的总耗时中位数降低至少 25%；
- 不得移动计时起点、降低模型质量、删合法事实或增加正常调用公式达标。

### V220-G06 失败不白屏

输入保存、P1、P2、单 Experience、reason、P4/PDF 和下载失败必须落在对应卡片的稳定错误态，保留
已成功结果和可恢复动作。任何组件异常必须由 ErrorBoundary 接住，不得整页白屏、重复生成或清空
已保存输入。

## 3. `DS-003` 实施矩阵

| 页面/状态 | Revision 2 状态 | 真实数据与行为 | 明确不实施 |
|---|---|---|---|
| 顶栏、当前任务、四步轨道 | REAL | 绑定当前 `task_id`、状态和历史回看 | 主题切换、评审条、批注工具 |
| 身份与目标 | REAL | Task API 保存确认；姓名/JD校验；选填联系方式和目标岗位 | 身份长期持久化、自动回填 |
| P1 理解岗位 | REAL | 权威快照 + SSE 完成项，刷新后恢复 | 输入页提前调用模型 |
| P2 匹配经历 | REAL | Experience/Fact 与匹配依据逐项显示 | 用户逐条采用、改变冻结顺序 |
| P3 润色履历 | REAL PROCESS PREVIEW | 完整 Fact 原子出现；reason 在旁侧增量；依据可查看原始 Fact | HTML 导出、HTML 作为排版真源 |
| P4 预览与导出 | REAL | 同 artifact PDF.js、下载 Word、下载 PDF、anchor/依据定位 | 固定样张、伪造可用链接 |
| 取消/取消后/新任务 | REAL | 确认对象与影响；迟到拒收；立即新任务 | 撤销 Provider 已发生的计费承诺 |
| insufficient/partial/failed | REAL | 保留输入及已完成经历；按失败范围重试或返回经历补充 | 编造事实补齐、全任务静默重跑 |
| 我的经历 | REAL（既有 Career Memory） | 头像菜单进入；查看/纠正已有 Experience/Fact；修改只影响未来任务 | 新上传、OCR、导入查重、删除新语义 |
| 我的简历 | REAL（既有记录能力） | 查看已生成记录和真实可用 artifact | 新的版本管理、回退、批量删除 |
| 个人与隐私 | REAL（限定） | 准确说明本地/第三方边界；可清当前未运行草稿 | 账户级删除、云隐私承诺 |
| 自然语言修改/“开始编辑” | HIDDEN | N/A | 意图修订、单 Fact 重生成、锁定、修改后重制文件 |

“我的经历”“我的简历”“个人与隐私”采用 `DS-003` 外观和导航，但只能连接现有真实能力；不存在的
API 不得用 fixture 冒充。经历纠正不修改当前冻结 InputRevision、正在生成内容或已导出文件。

## 4. 冻结技术路线

### 4.1 单一状态链

前端以 `task_id + input_revision + seq` 为唯一任务身份：进入或重连先 GET 权威快照，再订阅 SSE；
重复 seq 忽略，缺口/缓冲过期/artifact 变化重取快照。路由组件不得各自复制一套生成状态或再次调用
LLM。只恢复服务端已确认输入，dirty 本地输入在保存成功前保持可见未保存状态。

### 4.2 过程预览与最终 PDF

```text
P1/P2/P3 权威业务快照
→ HTML 过程预览（可恢复、可回看、不可导出）
→ ResumeDocument
→ DOCX（唯一排版真源）
→ Word COM PDF
→ PDF.js viewer / PDF 下载（同一 artifact）
```

HTML 可使用模板视觉骨架，但不得声称与 Word 像素一致。Fact 的显示宽度、换行或字体差异不得反向
改写内容；P4 完成后以真实 PDF 替换过程预览。依据 overlay 必须绑定当前 artifact/anchor，错配时
诚实不可用。

### 4.3 布局与响应式

- 主题 A；桌面为顶栏 + 步骤轨道 + 主卡 + 辅助卡，卡片外框不随内容量跳动；
- 1920×1080、1440×900、1280×800、1024×768 保持稳定工作面；
- 720×450、390×844、320×568 改为单主卡和横向步骤，详情使用弹窗或内部区域；
- `html/body` 不产生整页滚动；只允许 PLAN/`DS-003` 指定的主卡、PDF、详情等内部滚动容器；
- PDF 适应卡片宽度，不增加装饰性纸张边框；导出区固定且只显示真实可用动作。

### 4.4 不变的生成与成本边界

默认模型 `deepseek-v4-pro-ga-260813`、Ark 北京、`temperature=0`、JSON structured output、
`reasoning_effort=minimal`；Experience 最大并发 2，同一 Experience 内 Fact 串行；正常逻辑调用
`1 + 2F`，单任务 completion ≤16k，单逻辑调用最多 3 attempts。Revision 2 不为 UI 再调用模型。

## 5. Revision 2 开发任务与依赖

| ID | 开发结果 | 关键依赖 | 完成证据 |
|---|---|---|---|
| V220-R2-T01 | 身份/PLAN/DS-003/Revision1 checkpoint 核对；Pre-mortem | 无 | commit/blob/manifest/clean；3个失败模式与停止点 |
| V220-R2-T02 | 顶栏、头像菜单、四步轨道、固定工作面与路由壳 | T01 | DS-003 DOM/截图对照；无旧常驻侧栏 |
| V220-R2-T03 | 身份/JD保存确认、dirty边界、刷新/页面重开恢复 | T02 | native input/粘贴/刷新/重开；不重复调用 |
| V220-R2-T04 | P1/P2 逐项输出、历史阶段回看与缺口重取 | T03 | SSE重复/乱序/断线/回看；调用增量0 |
| V220-R2-T05 | P3 HTML过程预览、完整Fact、reason旁侧增量与依据 | T04 | 原子Fact/reason绑定/fallback/恢复；HTML不可导出 |
| V220-R2-T06 | P4真实PDF切换、anchor、双下载；首条完整纵切后的 Architecture Check | T05 | DOCX/PDF/viewer hash；Challenge记录 |
| V220-R2-T07 | 我的经历/我的简历/个人与隐私真实能力映射 | T06 | 无fixture；当前任务返回；作用范围断言 |
| V220-R2-T08 | 取消、新任务、insufficient/partial/failed、范围重试与 ErrorBoundary | T06-T07 | P1-P4失败矩阵；不白屏/不丢状态/不重复POST |
| V220-R2-T09 | 全视口、键盘、焦点、reduced-motion、卡片与滚动收口 | T02-T08 | 7视口截图+DOM；focus/dialog/menu/overflow |
| V220-R2-T10 | 真实模型、性能、回归、precheck、clean onedir 与隔离 E2E | T01-T09 | 全部门禁 PASS；最终包 identity |
| V220-R2-T11 | Falsification Check、RESULT、clean 候选 H2 冻结 | T10 | RESULT完整、无开放Challenge、clean |

T06 完成首条真实纵切后必须暂停做 Architecture Check；存在双真源、只能靠 CSS/重试逼近、fixture
冒充真实能力、HTML/PDF 内容漂移或职责转移时进入 `CHALLENGE_OPEN`，关闭前不得铺开 T07～T11。

## 6. 风险预案与反思门禁

Pre-mortem 至少覆盖：

1. 前端路由状态与后端 Task 形成双真源，刷新后 UI 看似恢复但重复生成；
2. HTML 过程预览与 ResumeDocument/DOCX 分叉，用户看到的 Fact 与最终 PDF 不一致；
3. Design-only fixture、固定样张或无效按钮被误接入正式产品；
4. 响应式仅靠压缩导致卡片跳动、整页滚动、下载区丢失或 PDF 模糊；
5. 失败/取消/重试触发第二次 POST、跨 task 写入或白屏。

每项必须给最小证伪实验、最迟决策点和替代路线。T06 Architecture Check 与 T11 Falsification Check
必须明确回答证据验证的是最终用户结果还是代理指标；只写“测试通过/未发现风险”不算完成。

## 7. 开发 Gate

### 7.1 Design Fidelity

- 与 `DS-003` 主题 A 对照 workbench empty/saved/P1/P2/P3/P4/failed/success、experiences、records、
  privacy；不得出现评审工具、主题切换、fixture 提示或自然语言修改入口；
- 当前阶段自动选中不可点、已完成阶段可回看、未来阶段禁用；卡片位置和主操作不随内容量跳动；
- 7 个冻结 viewport 检查 DOM、截图、整页 overflow=0、指定内部滚动容器、PDF 清晰度和下载区；
- 菜单、dialog、详情、返回焦点、Tab、Escape、方向键、错误关联和 reduced-motion 可操作。

### 7.2 Task、SSE 与用户流程

- 原生 setter + input/change、键盘、粘贴、保存中刷新、保存后刷新、路由切换、页面重开；
- 点击生成前 LLM/Embedding/operation=0；点击一次只创建一个 task operation；
- P1/P2完成项、P3完整Fact/reason增量、历史回看、断流fallback、重复/乱序/缺口/缓冲过期；
- 取消 P1/P2/P3/P4、迟到拒收、立即新任务；partial/failed只重试失败范围；ErrorBoundary不白屏；
- 返回我的经历/简历/隐私后当前 task/input/阶段不丢失、不新增调用。

### 7.3 内容、预览与 artifact

- 联系方式全组合、目标岗位、技能2～4类、Fact标题/正文/fact_refs、教育字段、short/typical/long；
- 每个已进入 HTML 的完整 Fact 与最终 ResumeDocument/DOCX/PDF 文本一致；reason 不进入简历正文；
- HTML无下载端点、无打印/导出真源；P4前后切换不丢内容；PDF.js与下载PDF字节相同；
- DOCX→Word COM→PDF 单一路径；GET/HEAD/Range/MIME/hash/404/405；失败保留独立可用的Word；
- anchor绑定当前artifact，空/错配诚实不可用；P4无控制台/Word闪窗，worker/WINWORD泄漏0。

### 7.4 性能、回归与包

- 短/典型/长 × cold/warm 真实模型每格 `n>=3`；首完整Fact中位数与最大值≤15秒；
- typical/long 同格总耗时中位数相对 V2.1.0 降低≥25%；short全部成功并记录绝对耗时；
- 正常调用 `1+2F`、Embedding 0/1、SSE/路由/回看增量0；成功不重试，失败最多3 attempts；
- Revision1固定计数回归、前端类型/build/Hooks、统一precheck、包审计全部通过；
- 从 H2 clean 源码重建 onedir，在隔离 runtime 用真实模型完成输入→P1-P4→viewer/双下载 E2E；
- 包内无Key、真实数据、设计fixture、评审工具、测试注入、开发机路径、ReportLab产品链或旧bundle。

所有必做项必须给出 PASS/FAIL 和退出码。FAIL、NOT_RUN、缺最终包真实纵切、环境限制未定位或把
开发自测转给 Acceptance 均不能形成 H2。真实模型不可用时进入 `BLOCKED`，不得用 mock 代替。

## 8. RESULT Delivery Contract

Development Agent 在候选冻结前更新同一 `RESULT.md`，顶部状态保持“待验收”，并标记
`REV2_DEV_VERIFYING` 或 `REV2_DEV_VERIFIED`；不得写独立验收通过、人工验收通过或可发布。

RESULT 必须一次性包含：

1. Plan Revision 2 批准 commit/blob、H2/唯一父/branch/clean、相对 H 的完整 diff；
2. `DS-003` 源/导入身份、manifest hash、实施矩阵实际状态及逐项偏差；
3. `V220-G01～G06` 与 `V220-R2-T01～T11` 的“用户结果→开发理解→实际交付→证据→偏差”；
4. API/schema/领域模型/模块职责/配置依赖/打包/前端可见变化；无变化写“无”；
5. Pre-mortem、Architecture Check、Falsification Check、所有假设和 Challenge 最终状态；
6. 真实模型六格样本、首Fact/总时长、调用/attempt/Token、SSE增量、DOCX/PDF/viewer/hash摘要；
7. Design Fidelity 的状态/viewport/截图与 DOM 断言汇总；
8. 全部命令、退出码、固定计数、最终包路径/文件数/总字节/EXE SHA-256/manifest；
9. 待独立验收问题：任务恢复与幂等、取消清理、流式绑定、HTML/DOCX/PDF一致、设计符合度、
   失败边界、性能、包身份和隐私扫描；
10. 建议进入全局文档的已验证事实；未经独立验收不得提前更新全局文档。

## 9. 冻结、验收与发布门禁

Revision 2 开发完成必须同时满足：T01～T11 全部完成、开发 Gate 无 FAIL/NOT_RUN、RESULT 完整、
工作区 clean、无开放 `CHALLENGE_OPEN`、未超出实施矩阵。形成 H2 后冻结，不再由开发修改。

随后按顺序执行：

1. Documentation Agent 只依据 PLAN、RESULT、机械身份和证据入口给出 `DOC_ALIGNED`；
2. 未参与 H2 实现、自测或修复的 Acceptance Agent 在隔离副本和最终 onedir 上完成 Design Fidelity、
   Integration、失败矩阵、真实性能、artifact、资源清理与包审计；
3. Documentation Agent 将绑定 H2 的验收结论写入 RESULT；
4. Product Owner 使用同一候选包完成人工验收；
5. 全部通过后才收口 CURRENT_STATE、docs索引和根README；Product Owner 另行批准发布后才推送
   remote `main` 并创建 annotated tag `v2.2.0`。

任一源码、测试、依赖、配置、构建或入包文件在验收后变化，原验收自动失效并重新冻结 H2。

## 10. 明确延期/排除

- 后端/应用退出、崩溃、系统重启后的未完成任务续跑；多前台任务、跨设备恢复；
- 登录、多用户、PostgreSQL、对象存储、分布式队列和云部署；
- Profile身份长期保存或自动回填；简历上传、OCR、导入查重和重复合并；
- 自然语言意图修订、单Fact重生成/锁定、修改后重制文件和修订历史；
- 新模板、任意Word模板解析、自动全局字号/行距/字距适配；
- 生产主题切换、Design批注工具、固定fixture/样张、完整WCAG/屏幕阅读器认证。

上述内容进入后续需求池，不得以“Design Snapshot 中可点击”为由在 V2.2.0 隐含实现。
