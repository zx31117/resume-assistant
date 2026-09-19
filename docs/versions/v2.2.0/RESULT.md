# V2.2.0 RESULT：执行记录

> 文档角色：V2.2.0 Development Agent 执行记录（开发候选冻结前由开发维护实施、自测与偏差）
> 当前状态：**候选冻结（开发侧）** — `REV2_DEV_VERIFIED`（本轮唯一冻结候选 = `0cc444e`，见下）
> 当前阶段：Revision 2（第二批可见界面；Design Snapshot `DS-003` 集成与最终纵切）
> 产品基线：annotated tag `v2.1.0` → `5d72a2e08ebd4fa416b4b1dcdd79c1d08dfc7cfd`
> 开发路径：`<current-workspace>` 分支 `version/v2.2.0`
> 批准 PLAN：Revision 2，blob（见 §R2-1）；历史 Revision 1 blob
> `324302a0ef6d81214c752d12281c221f2550f320` 归档于 HISTORY
> 语义交接：Revision 1 已 `BATCH1_DEV_VERIFIED`（候选冻结）；本版自 Revision 2 获批 checkpoint 起
> 进入第二批实现，已收口至 `REV2_DEV_VERIFIED`（候选冻结，H2 形成）。

> **唯一冻结候选（候选，全部开发 Gate 完成并提交）**：
>
> - **本轮唯一冻结候选 = HEAD `0cc444e`**：`docs(v2.2.0): record H3 dev-side closure - six-grid real-model matrix + rebuilt onedir E2E`（包含全部源码收口 + 六格矩阵运行脚本与证据 + RESULT）
>
> - **源码候选（其父）** `b70d6e6`：`feat(v2.2.0): user-operable failed-scope continuation task (reuse done, retry only failed) + proof`（续试收口实现）
>
> - **唯一父提交**：`0cc444e` 的 parent = `b70d6e6`（`git cat-file` 仅 1 条 parent）
>
> - **相对 H（`47ae33e`）完整 diff**：**43 files changed, 5785 insertions(+), 162 deletions(-)**
>   （`47ae33e`→`0cc444e` 实测 `git diff --shortstat`；含续试实现、六格运行脚本与证据 JSON）
>
> - **最终包身份**：onedir `dist/ResumeAssistant/`（**4045 files / 170,356,413 B**）；EXE SHA-256
>   `9E6DF063E6056E78 47A6FF78F4207BD9 03CD4A23CA97ACB4 0EF0D56841FAF9C6`；前端 bundle `index-BrAu-oeZ.js`
>
> - **工作区**：clean（`git status --porcelain` 空）
>
> - **顶部状态**：`REV2_DEV_VERIFIED`（开发侧全部交付项完成、候选冻结；不代表独立验收/可发布）

> **本文件由 Development Agent 在候选冻结前写实施、自测与偏差。** Revision 2 完成全部开发 Gate 前
> 顶部始终为"待验收"，标记 `REV2_DEV_VERIFYING` → 完成后 `REV2_DEV_VERIFIED` = **开发侧
> T01–T11 全部完成（候选冻结）**，不代表独立验收/可发布：独立 Acceptance 由用户 / Doc Agent 在
> 适当时机另启，本批不进入也不替代。T10 是开发侧 Architecture Check（只读核对产品不变量是否在
> 真实路径成立），**不存在"用户 / Doc Agent 手动 T10"**。全局文档（CURRENT\_STATE / docs/README /
> README / DECISIONS）由用户 / Doc Agent 在适当时机更新，本批不触碰，也不把任何实施过程文档升级
> 为事实真源。

***

## 1. T01 身份与基线核对（Required Reading 确认）

本节确认 Development Agent 在开始实现前已完成本版本强制阅读，缺任一项不得进入源码实现。

| 阅读对象                                                                                           | 结论 |
| ---------------------------------------------------------------------------------------------- | -- |
| `docs/README.md` §0（Agent 执行入口）、§1～§5（产品目标/版本边界/链路/事实所有权/架构不变量）                                | 完成 |
| `docs/CURRENT_STATE.md`（当前已验收实现事实）                                                             | 完成 |
| 本版本 `PLAN.md` 全文（Revision 1 唯一有效合同）                                                            | 完成 |
| `docs/HUMAN_AI_WORKFLOW.md` §3.1（权限）、§3.2（PLAN/候选身份）、§3.4（强制反思与 Challenge）、§6（开发职责）、§11（上下文控制） | 完成 |

| 基线字段               | 值                                                      | 核对                                             |
| ------------------ | ------------------------------------------------------ | ---------------------------------------------- |
| 角色                 | Development Agent（第一批，仅设计无关实现）                         | 一致                                             |
| 开发路径               | `<current-workspace>`，分支 `version/v2.2.0`              | `git branch --show-current` = `version/v2.2.0` |
| 当前 HEAD            | `d75b692c73ebeea91435f1daae996dde974fbf31`（docs 收口链顶部） | 一致                                             |
| 工作树                | clean（`git status --porcelain` 为空）                     | 一致                                             |
| 产品基线               | `v2.1.0` → `5d72a2e08ebd4fa416b4b1dcdd79c1d08dfc7cfd`  | `git rev-list -n1 v2.1.0` 一致                   |
| 批准 PLAN blob       | `324302a0ef6d81214c752d12281c221f2550f320`             | HISTORY VH-010 记录一致                            |
| 本 Revision 授权      | 第一批、仅设计无关实现；Design Gate 关闭                             | 遵守（不读取 Design Agent 工作稿）                       |
| Required Reading 项 | 全部完成                                                   | 见上表                                            |

**身份边界确认（Development Agent）：**

- 只读 PLAN / HISTORY / CURRENT\_STATE / DECISIONS / 全局文档，不修改；在 PLAN 范围修改源码、测试、依赖与构建配置；

- 候选冻结前写 RESULT 实施/自测/偏差；不写"独立验收通过"或"可发布"；

- 不操作 canonical `main`、GitHub remote 或正式 tag；

- 本 Revision 不实现任何可见布局/文案/动效/响应式，不读取或猜测 Design Agent 的 `current/`。

## 2. T01 Pre-mortem（开发前强制反思）

流程冻结的是模块、可观察结果与不变量；技术路线与参数必须经真实证据支持。以下假设最终失败，
列出最可能的失败模式、最小证伪探针、最迟决策点与替代路线。（PLAN §5 风险台账为本节正式宿主，
此处登记 T01 执行时点反思与探针落地计划。）

### 失败模式 1：SSE 恢复与快照在断线/并发下重复调用、交叉绑定或旧 revision 覆盖新任务

- **最小证伪探针**：T04 断线重连探针——在两个并发 Experience 子任务与一次 SSE 断线重连下，
  校验 `fact_id` 绑定不漂移、`seq` 无缺口时快速重放、缺少 seq 时重取权威快照而不是自行拼接，
  且刷新/重连不新增 LLM/Embedding/Word 调用。

- **最迟决策点**：T04 首条授权快照/事件协议落地、T10 首条真实纵切之后。

- **替代路线**：若快照与事件会出现竞态写摊（同一条 completion 既进权威快照又被增量事件重复传递），
  改为"权威快照为唯一真源，增量仅作浮层提示"并弱化增量语义。禁止旧 task/revision 写回当前结果
  （revision fence 必须在写入路径硬校验）。

### 失败模式 2：两阶段调用＋经历并发 2 会让 Token、限流或顺序失控，"15 秒"只在简化探针成立

- **最小证伪探针**：T06 真实模型固定样例——短/典型/长 × cold/warm，每格 `n >= 3`，用最终 schema
  与同一条单调时钟记录点击零点→首 JD 项→首召回 Fact→首完成 Fact→P1–P4→总耗时；仅用最终 schema
  序列化重新测任务状态峰值，不复用 VH-007 的 26.9 KiB 实验值。

- **最迟决策点**：T10 首条真实纵切、T11 冻结前综合 Gate。

- **替代路线**：并发 2 收益不成立或顺序不稳定退回串行，并把 15s/降 25% 性能目标按新基线进入
  Architecture Challenge；不得伪造降低比例或移动计时起点。

### 失败模式 3：清理或取消误删活动/已发布对象，或遗留 Provider/Word/文件与迟到 artifact

- **最小证伪探针**：T05/T09——取消每个阶段（P1/P2/每个并发 P3/P4/Word worker）后验证 Provider 流关闭、
  迟到结果被 fence、能立即开始新任务；T09 cleanup 对 DRAFT/RUNNING/CANCELLING、当前页面引用、
  当前 ResumeRevision 及其 DOCX/PDF 0 误删，未提交孤立草稿及 FAILED/CANCELLED 24h 后清理；
  相邻哨兵文件与跨目录越界防护。

- **最迟决策点**：T09 清理与故障恢复完成后。

- **替代路线**：若 cleanup 无法在"仅限 runtime data root + 幂等 + 失败可见"约束下安全执行，缩小可清理
  对象集合并显式保护活动/发布对象；不得借清理扩大误删或"Ignored 文件影响执行"。

**反思结论（要求）：** 至少给出一个可信失败模式与证伪办法，单写"未发现风险"或重复 PASS 数不算完成。
已登记 3 个可证伪失败模式，分别对应 PLAN §5 Pre-mortem 三条重点与对应最小探针/停止决策点。

## 3. T01 假设台账（承接 PLAN §5 A01–A10）

PLAN §5 已冻结假设身份；本台账在开发执行中逐项维护最终状态，所有 `ASSUMPTION` 在 T11 前必须更新
为 `EVIDENCED` / `REJECTED`，并为每个假设登记开发期验证证据或据此触发的 Challenge。

| ID  | PLAN 状态    | 内容                       | T01 执行确认 / 后续证据入口                         |
| --- | ---------- | ------------------------ | ----------------------------------------- |
| A01 | EVIDENCED  | minimal 可稳定输出绑定 Fact     | T06 最终实现 3+3+3 边界重跑；失败则 Challenge 模型/协议   |
| A02 | REJECTED   | 单复杂流能同时稳定绑定 Fact/reason  | 禁止采用；T06 必须实现两阶段，不得用局部 1/3 PASS 恢复        |
| A03 | EVIDENCED  | 紧凑 JD＋两阶段可在 15s 内首 Fact  | T06 最终集成固定样例 n≥3；max>15s 即不得声称达标          |
| A04 | EVIDENCED  | Experience 并发 2 有收益且绑定稳定 | T06 限流/乱序/单经历失败；异常退回串行并 Challenge         |
| A05 | ASSUMPTION | 16k 总预算覆盖合法长简历           | T06 最大 Fact 数/重试/超限探针；不足不得静默删内容           |
| A06 | ASSUMPTION | 快照限频可同时满足恢复与 512KiB/task | T04/T09 断线中 reason、缺口、容量压力；超限压缩完成事件而非删结果  |
| A07 | EVIDENCED  | 长任务状态峰值约 26.9KiB         | T02/T09 最终 schema 重新序列化，不复用实验值            |
| A08 | EVIDENCED  | 联系方式链可完整保留               | T07 最终 Task→Document→DOCX→PDF/download 重跑 |
| A09 | REJECTED   | 当前教育映射正确                 | T07 必须修复真实 `本科（）` 反例                      |
| A10 | REJECTED   | 合法短输入当前可稳定渲染             | T08 必须关闭 short 7/7 TemplateError          |

> T01 完成证据：本文件身份区（§1）、Pre-mortem（§2）、假设台账（§3）已建立；基线 commit/blob
> clean 状态见候选冻结与 T11 收口记录。三个失败模式、对应探针与停止点已在 §2 登记。

***

## 4. T10 首条真实纵切后的 Architecture Check（只读）

> 依据 `HUMAN_AI_WORKFLOW.md` §3.4 强制反思停顿点②与 `PLAN §4 V220-R1-T10`。本节为只读检查
> 记录：只核对产品不变量是否在真实路径成立，不扩展任何路径；不再读 Design Agent `current/`。

### 4.1 证据范围与可得性（诚实声明）

- **真实外部模型（P1–P3）**：本批执行后段已取得 `ARK_API_KEY` + `LLM_MODEL=deepseek-v4-pro-ga-260813`，
  并在隔离临时 runtime 内打通**真实端到端纵切**：真实 LLM 紧凑 JD → P2 选材 → P3 Fact/reason → P4
  真实 DOCX/PDF（`_e2e_v22_slice.py`）。结果：`status=SUCCEEDED`，DOCX 38,963 B、PDF 4,225,411 B，
  总耗时约 37s。**本节 T10 相关真实性能结论自此由 BLOCKED 升级为 EVIDENCED**，非探针/mock 数字。

- **真实路径暴露并已修复的应用级缺陷**（正是 §4.4 代理指标所警示的"fixture 与真实 artifact"分歧点）：

  1. **Prompt 字面量花括号**：`prompts/task_fact.py` 示例里的 `{experience_id}` 未转义为 `{{experience_id}}`。
     真实链渲染模板时 `ChatPromptTemplate` 把 `{experience_id}` 当未提供变量 → `KeyError`，被
     `invoke_observed_json` 包装为"结构化 JSON 连续失败"。fake-provider 测试不渲染模板，故 T6 未暴露；
     真实 P3 首次调用即暴露。已修复：转义为字面量 `{{experience_id}}/1`。
  2. **SUCCEEDED 发布顺序**：`task_service.run_generation` worker 在 `transition(SUCCEEDED)` **之前**调用
     `publish_artifacts`，而该方法仅允许在 SUCCEEDED 终态写发布引用 → 真实装配链产证 `docx_path` 后即被
     guard 拒绝（`TaskStateError`）。桩装配器不产出 `docx_path`，故 T6 未暴露。已修复：先落 SUCCEEDED 再发布。

  两处修复后 T2–T9 回归仍 **246/0 全绿**，真实纵切 SUCCEEDED 且产物落盘。

- 其余离线可真实运行的证据（Word COM 产物链、短输入宽容渲染、`bold_headline`、教育 `description`
  接入）维持 §4 上文所述，T07/T08 已用真实 Renderer/DOCX 路径验证。

### 4.2 T02–T09 回归门禁基线

| 任务                | 通过/失败 |
| ----------------- | ----- |
| T02 task\_store   | 41/0  |
| T03 task\_api     | 26/0  |
| T04 sse           | 27/0  |
| T05 cancel        | 39/0  |
| T06 generation    | 23/0  |
| T07 document      | 57/0  |
| T08 short\_render | 14/0  |
| T09 cleanup       | 19/0  |

（均为隔离临时 runtime，未触碰真实库/真实输出）

### 4.3 双真源检查

结论：**Revision 1 无已成立的双真源漂移；登记 2 个待 Revision 2 治理的镜像/材料化风险。**

1. **状态与序的真源唯一**：`Task` 行为状态/revision/终态产物引用的唯一权威；`TaskEvent/snapshot/seq`
   `TaskSnapshot` 单条覆盖式。非活动态拒写快照/事件（`assert_writable`）。✓
2. **入参双镜像（受控镜像，非双权威）**：`InputRevision`（冻结、权威历史）与 `TaskSnapshot.payload`
   内的入参镜像并存；snapshot 由 worker 从最新 `InputRevision` 读取再写入，SUCCEEDED 时一致。
   **风险 R1**：两者间无从机制上保证的一致性校验；一旦未来写路径不再统一从 InputRevision 取入参，
   镜像将漂移。Revision 1 不做，登记待治理。
3. **简历内容无 DB 一阶表示**：最终简历内容只材料化为 DOCX/PDF 文件；`Task.published_docx_path/
   pdf_path` 仅持文件指针。Revison 1 无“从 DB 重开/重生成”路径，不构成冲突。
   **风险 R2**：若 Revision 2 增加“生成中 HTML 预览”或“从已发布产物编辑”，无法仅凭 DB 重建
   ResumeDocument，将被迫重跑或解析 DOCX——即从“无冲突”滑向“只能在文件侧重建”的职责转移。

### 4.4 代理指标检查

- **返工前真实首 Fact 观测（当时已形成证据）**：隔离 runtime 真实纵切记录 `jd.done`(P1) 至首个
  `fact.done`(P3) 约 17s（05:30:12 → 05:30:30），端到端 P1–P3+P4 总耗时约 37s。这是真实模型数据，
  非 T06 简化探针；最终 schema 复测归 T11 Gate。

- T06 “26.9KiB 任务峰值”：PLAN 已强制“用最终 schema 重新序列化，不复用实验值”，T11 Gate 复核。

- 自动化门禁以模型/Renderer 中间对象断言为主（如 `unreplaced_placeholders == []`、统计计数、无
  TemplateError），**不是对 DOCX 视觉内容的全量断言**。这证明“模型与渲染不变量”，不证明“视觉正确”。
  因 Revision 1 禁止任何可见布局/文案改动，此代理可接受，但必须如实记录为代理，不得宣传为视觉验收。

### 4.5 fixture 与真实 artifact 冲突

- 显著分支点：`TemplateRenderer.allow_empty_required` 默认 `False`（严格，短输入抛 TemplateError），
  而产品装配链 `document_assembler` 显式置 `True`（宽容，优雅移除空章节）。fixture（严格）与真实短
  输入链（宽容）行为分叉。
  **风险 R3**：两套行为由隐式布尔开关驱动，未来直接调用 `TemplateRenderer` 的路径会意外吃到严格
  TemplateError。这是“特殊分支”味道；T08 已在不改事实/不篡改模板真源前提下验证链上行为正确。
  Transformer 建议：把该开关移到“模板已声明的空章节语义”上，或让链默认行为成为 Renderer 默认值，
  仅对 fixture 保真保留严格模式。

### 4.6 职责转移检查

- P4 已从 T06 桩装配升级为真实 `document_assembler`（`run_generation` 默认 `make_task_assembler`）；
  事实→ResumeDocument→DOCX→PDF 责任由装配链承载，未沉回 API/service 层。✓

- 拆分/事实绑定契约集中在 `resume_document`（含 fact\_refs）；未发现职责被业务层代持。

### 4.7 关键假设评估（承接 §3）

| 假设          | 状态               | 本批证据                                                  |
| ----------- | ---------------- | ----------------------------------------------------- |
| A07 任务状态峰值  | 待最终 schema       | T02/T09 容量边界通过；真实峰值需 final-schema 重测（`BLOCKED`）       |
| A08 联系方式链保留 | EVIDENCED（离线）    | contact → `make_task_assembler` → DOCX/PDF 链已接通，T07 绿 |
| A09 教育映射    | EVIDENCED（含反例修复） | T07 `本科（）` 已修复，无空括号断言通过                               |
| A10 合法短输入渲染 | EVIDENCED（链上）    | T08 短输入 14/0，严格→宽容对照可复现                               |

### 4.8 结论

- **T10 当时未触发** **`CHALLENGE_OPEN`**：无明显双真源漂移、无 fixture 与真实 artifact 的链级冲突、无只能靠
  调参逼近的硬编码；三处监控风险（R1/R2/R3）属 Revision 2 治理项，已登记，不阻断 T11。

- **真实纵切（EVIDENCED，原 BLOCKED 项）**：自 §4.1 起已取得真实模型键并在隔离 runtime 内跑通
  真实端到端纵切（真实 LLM + 真实 DOCX/PDF，`status=SUCCEEDED`，DOCX 38,963 B、PDF 4,225,411 B，
  \~37s）。真实路径另暴露并修复两处应用级缺陷（task\_fact 字面量花括号、publish 顺序），回归 246/0。

- **反思纪律**：R1 是“测试全过但未来仍可能双真源漂移”的弱假设，R2/R3 是“越界后只能靠修补”的路径；
  均已给出最小反证与替代，避免“未发现风险”式空答。本节真实结论只来自真实纵切与非 mock 门禁，不定标。

***

## 5. T11 冻结前 Falsification Check

> 不止补全"完成叙事"；集中寻找"测试全过但用户仍会打回"的路径、代理指标、缺失负向和失败清理。
> 本节结论与 §4.4 的代理指标警告相互印证。

### 5.1 已被真实纵切证伪的假设（确实找到了反例）

两条"单元/桩测试通过 ⇒ 真实路径正确"的隐含假设，均在真实纵切中被**证伪**并已修复：

1. **"Prompt 模板无未转义字面量"（伪）**：`task_fact.py` 把 `{experience_id}` 当示例字面量但未转义。
   真实链渲染模板 → `KeyError` → 被包装成"结构化 JSON 连续失败"。fake provider 测试不渲染模板，故
   T6 全绿却漏掉。→ 这证明 **provider 注入的测试是代理指标**，覆盖不了模板/真实调用公式。
2. **"装配链发布顺序正确"（伪）**：worker 在 `transition(SUCCEEDED)` 前调 `publish_artifacts`，被
   该方法的 SUCCEEDED-only guard 拒绝。桩装配器不产 `docx_path`，故 T6 全绿漏掉真实装配分支。→
   同理，**"has docx\_path ⇒ 走到发布分支"是代理断言**。

这两条反例是 T10 §4.4／§4.5"fixture 与真实 artifact 分歧"的现实命中，说明 Fake/桩门禁对"真实调用
公式、真实装配分支"存在盲区。已新增 `_e2e_v22_slice.py` 作为每次真实模型回归的 smoke（真实 P1–P4 +
DOCX/PDF 落盘），并已使其通过（246/0 回归）。

### 5.2 主动伪造的其余候选（未再发现新反例，如实记录弱项）

- **其他 Prompt 未转义字面量**：`task_fact` 正文其余 `{{ }}` 转义正确；`task_compact_jd` 仅 `{jd_text}`
  （真变量）与转义 JSON，真实 P1 已跑通。反例未复现。

- **短/长输入、取消、容量**：T8 / T5 / T9 用隔离 runtime 证覆盖；未在真实模型下重放取消中断（弱项，
  属 §7.5 待独立验收问题 1/2，不虚报）。

- **视觉正确性**：门禁只断言模型/渲染不变量，不对 DOCX 像素做断言（已如实记为代理，§4.4）。Revision 1
  禁可见改动，此代理在本批成立。

### 5.3 Falsification 结论

- 不存在"测试全过但可演示的链级返工"；两处真实反例均已修复且回归 246/0。

- 仍需依赖真实模型 + 最终完成条件（§8）的核对项，如实移到 §7.5 待独立验收，不以假门禁替标。

- 未发现阻断性 `CHALLENGE_OPEN`（设计/内容/协议路径无阻断）。性能侧首 Fact 曾略超 15s 的偏差已在返工中以
  `CHALLENGE_OPEN` 登记并关闭（见 §7.6）：改为渐进逐 Fact 发布后，首完整 Fact 中位数与最大值均 ≤15s，
  **A03 恢复 EVIDENCED**，不再降级，也不再作为“待独立验收”的遗留偏差（见 §7.5，该项已由 §7.6 源层
  真实矩阵证实；包内最终复核仍属独立验收）。

***

## 6. 开发 Gate（T11 收口现场执行记录）

> 每条必做项给 PASS/FAIL 与证据；"未执行/待验收代跑"不构成 checkpoint。本文档本节为 Development
> Agent 在候选冻结前**自测执行的开发 Gate**，非独立验收 Pass。

### 6.1 状态、协议与取消

| 项目                                      | 结论   | 证据                                                                     |
| --------------------------------------- | ---- | ---------------------------------------------------------------------- |
| schema migration：新库/旧库/重复/回滚/备份/cleanup | PASS | T2:\[M1]全新库、\[M2]幂等、\[M3]旧库升级+备份；T9 cleanup                            |
| Task 状态机全矩阵，非法跳转 fail closed            | PASS | T2:\[R1] 全矩阵（DRAFT→READY→RUNNING→SUCCEEDED/FAILED/CANCELLED），非法/T终态拒跳转 |
| 草稿保存确认/恢复/revision 冻结                   | PASS | T3:\[A2-A4]\[A6]\[A7]；T2:\[R2]                                         |
| SSE seq/去重/缺口/重连/reason 断流              | PASS | T4:\[S1-S8] 27/0                                                       |
| 幂等：刷新重连不增 LLM/Embedding/Word 调用         | PASS | T4:重复/乱序/缺口/缓冲过期/重连不增调用                                                |
| 取消 P1/P2/并发P3/P4，迟到拒收，立即新任务             | PASS | T5:\[C1-C8] 39/0，含注册表无泄漏                                               |
| Provider/后台task/DB/文件/Word worker 无泄漏   | PASS | T5 收尾 registry 回到基线；T9 清理句柄幂等                                          |

### 6.2 生成、性能与成本

| 项目                                 | 结论            | 证据                                                                                                                                                                                                                 |
| ---------------------------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Fact schema/绑定/reason/无外来 ID       | PASS          | T6 typed/binding/顺序/并发/重试/超限；真实纵切绑定门禁                                                                                                                                                                              |
| P1/P2/P3/P4 增量与 fallback           | PASS          | T6:\[T9] run\_generation SUCCEEDED；reason 真增量                                                                                                                                                                      |
| 经历并发 2、顺序稳定、单经历失败隔离                | PASS          | T6 并发门禁；\`MAX\_WORKERS=2\`                                                                                                                                                                                         |
| 调用公式 \`1+2F\`、Embedding 0/1、重连增量 0 | PASS          | T6 调用/Token 观测                                                                                                                                                                                                     |
| 成功不重试；可重试 ≤3；不可重试立即失败              | PASS          | T6                                                                                                                                                                                                                 |
| 任务 16k Completion 上限，超限非截断成功       | PASS          | T6 超限门禁                                                                                                                                                                                                            |
| 固定样例 real 每格 n≥3、中位数/最大值、首 Fact    | **PASS（返工后）** | **本轮新证据（重跑，源层 real 模型）**：①首完整 Fact 见 §7.6 矩阵——每格 n≥3，中位数与最大值均 ≤15s（cold max=14.27，warm max=10.90，与 §7.6 全表一致）；②**总耗时矩阵**见下（折线表）：short 记录绝对耗时，typical/long 相对 V2.1.0 同格基线中位数降幅均 ≥25%，全部达到 PLAN §V220-G04 的 V2.2 上限。 |
| 同一单调时钟记录全阶段                        | PASS          | \`\_e2e\_v22\_profile.py\` 用事件时间戳（jd.done→首 fact.done→reason.delta）与 perf\_counter 同源采样（重跑）                                                                                                                        |

**总耗时矩阵**（本轮新证据，真实模型 deepseek-v4-pro-ga-260813；每格 n=3，采样即
`backend/validation-artifacts/v2.2-rework/matrix/*.jsonl` 的 `total_s`）：

| 格            | 总耗时采样（s）              | 中位数（s） | V2.1.0 基线（s） | V2.2 上限 75%（s） |     降幅 | 判定   |
| ------------ | --------------------- | -----: | -----------: | -------------: | -----: | ---- |
| short-cold   | 25.53 / 25.78 / 25.52 |  25.53 |     —（无成功基线） |              — |   绝对记录 | 成功 ✓ |
| typical-cold | 38.35 / 37.42 / 40.07 |  38.35 |        89.49 |          67.12 | ≈57.1% | ✓    |
| long-cold    | 44.86 / 45.50 / 44.63 |  44.86 |        94.32 |          70.74 | ≈52.4% | ✓    |
| short-warm   | 22.70 / 22.12 / 22.30 |  22.30 |     —（无成功基线） |              — |   绝对记录 | 成功 ✓ |
| typical-warm | 33.96 / 33.55 / 33.77 |  33.77 |        84.48 |          63.36 | ≈60.0% | ✓    |
| long-warm    | 41.05 / 39.58 / 41.98 |  41.05 |        97.92 |          73.44 | ≈58.1% | ✓    |

降幅 = 1 −（V2.2 中位数 / V2.1.0 同格基线中位数）。全部 4 个有基线格（typical/long × cold/warm）中位数
均 ≤ 基线 75%、≥25% 降低；short 两格不再触发 V2.1.0 的 `TemplateRenderer` 错误并全部成功，仅记录绝对耗时。

### 6.3 内容与 artifact

| 项目                                                    | 结论   | 证据                                            |
| ----------------------------------------------------- | ---- | --------------------------------------------- |
| 联系方式全组合（仅姓名/全字段/Unicode 空白归一）                         | PASS | T7 contact 链；docx\_writer 归一                  |
| 技能 2-4 类或诚实减少，均有事实依据                                  | PASS | T7 build\_skill\_groups                       |
| headline/body 加粗边界/冒号/fact\_refs 不扩张/Career Memory 不变 | PASS | T7 bold\_headline，54/57 内容断言                  |
| 教育 major/degree 缺失组合、无空括号/倒置/重复                       | PASS | T7 \`本科（）\` 反例已修复，无空括号断言                      |
| short/typical/long 均生成 DOCX；DOCX→PDF hash             | PASS | T8 14/0；真实纵切 DOCX/PDF hash 落盘                 |
| Word 缺失/COM 失败/超时/并发 busy 均 fail closed               | PASS | T7/T8 DOCX→PDF 链路                             |
| P4 无控制台/Word 闪窗、WINWORD/worker 泄漏 0                   | PASS | 真实纵切+隔离启动后 \`WINWORD\`/ResumeAssistant 进程数为 0 |

### 6.4 容量、回归与构建

| 项目                                                              | 结论              | 证据                                                                                                                                                                               |
| --------------------------------------------------------------- | --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 256KiB/256KiB、20条、16MiB 边界与 +1B                                 | PASS            | T2:\[R6]\[R7]、T9                                                                                                                                                                 |
| 保护对象 0 误删（活动/取消中/页面/Revision/DOCX/PDF）                          | PASS            | T9 保护对象断言                                                                                                                                                                        |
| 启动/终态/阈值 cleanup、幂等、句柄占用、相邻哨兵                                   | PASS            | T9 19/0（含两次 cleanup 零删除）                                                                                                                                                         |
| V2.1.0 事实/单次 JD/DOCX-PDF 同源/ErrorBoundary 回归                    | PASS            | `precheck.py`：compile+V2.0.1/V1.5/V2.0/V2.0T5/生命周期/V1.4T7/H6 全绿，exit=0                                                                                                           |
| **Python compile / 类型检查 / 前端正式 build / 统一 precheck**            | **PASS(带如实说明)** | compileall exit=0；**项目未配置** mypy/pyright（无 pyproject/mypy.ini），后端静态=compileall(阻断)+ruff(非阻断 510 基线)；前端 \`tsc -b && vite\` exit=0 + \`lint:hooks\` exit=0；`precheck.py` 最终 exit=0 |
| **Windows onedir clean 重建 + 隔离启动；包内无 Key/数据/注入/开发路径/ReportLab** | **PASS**        | `PyInstaller --clean` exit=0 重建；`h8_package_audit.py` marker\_hits=0/forbidden=0；`t11_isolated_start.py` 隔离启动 /api/health 2.8s（见下）                                               |

**onedir 隔离启动证据（T11 新增脚本，本轮重建后重跑）**：`scripts/t11_isolated_start.py --exe dist/ResumeAssistant/ResumeAssistant.exe`
→ `/api/health` 200 就绪于 **2.8s**，退出码 0；该脚本剥离 `ARK_API_KEY/SQLITE_PATH/RESUME_DATA_DIR/APP_PORT`
等注入变量并把 runtime 指向仓库外临时目录，证明**包内无 Key、无注入、无开发机路径**即可独立启动。
包审计：4045 文件、170,326,282 B，exe\_sha256=`4b134da1…`，marker\_hits=0、forbidden\_paths=0，ReportLab 目录缺省
（spec excludes=\["reportlab"]）。启动后进程检查：ResumeAssistant=0、WINWORD=0。

**统一 precheck 最终结论**：4 项阻断全部 PASS（compile + 前端 build + Hooks 门禁 + 六回归脚本固定计数），
runtime 隔离哨兵一致，退出码 0。非阻断四项仅报告不阻断：ruff 510、pip-audit 9、ESLint 18、npm-audit 4。

***

## 7. RESULT Delivery Contract

### 7.1 必填身份

- **版本**：V2.2.0（Revision 1，第一批，仅设计无关后端实现）；文档角色：Development Agent 执行记录

- **Plan Revision / 批准基线**：Revision 1，blob `324302a0ef6d81214c752d12281c221f2550f320`（HISTORY VH-010）

- **<current-workspace>** **/ branch**：`d:\demo\resume-assistant\current` / `version/v2.2.0`

- **产品基线**：annotated tag `v2.1.0` → `5d72a2e08ebd4fa416b4b1dcdd79c1d08dfc7cfd`

- **本批返工 checkpoint（继承基础，缓冻结前最后源码态）**：

  - **HEAD**：`d8786457c0422dfbca1ad4f4e81b1c8096de3375`

  - **唯一父提交**：`085c8d84cb25456ffdabbeb0cbd06b66097e6962`

  - **相对批准基线** **`d75b692`** **的 diff**：**35 files changed, 6573 insertions(+), 14 deletions(-)**

- **相对批准基线完整文件清单（35 files，d75b692 → d878645）**：
  `backend/_e2e_v22_matrix.py`、`backend/_e2e_v22_profile.py`、`backend/_e2e_v22_slice.py`、
  `backend/_v22_t2_task_store.py`、`_v22_t3_task_api.py`、`_v22_t4_sse.py`、`_v22_t5_cancel.py`、
  `_v22_t6_generation.py`、`_v22_t7_document.py`、`_v22_t8_short_render.py`、`_v22_t9_cleanup.py`、
  `api/routes/task.py`、`api/schemas.py`、`core/task.py`、`core/task_cancel.py`、
  `database/migrations.py`、`database/models.py`、`main.py`、`models/resume_document.py`、
  `prompts/task_compact_jd.py`、`prompts/task_fact.py`、`prompts/task_reason.py`、
  `services/document_assembler.py`、`services/docx_writer.py`、`services/jd_analyzer.py`、
  `services/llm_service.py`、`services/task_cleanup.py`、`services/task_generation.py`、
  `services/task_repository.py`、`services/task_service.py`、`services/task_sse.py`、
  `services/template_renderer.py`、`docs/versions/v2.2.0/RESULT.md`、`.gitignore`、`scripts/t11_isolated_start.py`

- **本批收口新增/修改（最终候选 checkpoint，本文件最终提交后形成）**：`services/task_generation.py`
  （渐进逐 Fact 发布）、`docs/versions/v2.2.0/RESULT.md`（本文件）、`backend/_e2e_v22_profile.py`、
  `backend/_e2e_v22_matrix.py`、`.gitignore`（托管 `.trae/`）——已在 `d878645` 提交；本轮收口仅以
  最终 RESULT 提交追加更新（最终 checkpoint identity 见 §7.7）。

- **第一批内部包（本轮从返工 checkpoint 重建后的当前构建产物，身份如实）**：

  - 包路径：`dist/ResumeAssistant/`（onedir）；EXE `dist/ResumeAssistant/ResumeAssistant.exe`

  - 文件数：4045；总字节：170,326,282 B

  - **EXE SHA-256**：`4B134DA1BCE7E7BC285D820926A992D02EFAE2097DD6F3F5D8FEE84D5D78EB5A`

  - **manifest / 构建身份**：PyInstaller onedir，spec `packaging/resume_assistant.spec`；
    `name=ResumeAssistant`，`console=False`，`upx=False`，`excludes=["reportlab"]`；无内嵌
    版本资源/额外 EXE manifest（无自定义 version/icon 资源）。

  - **如实说明**：已从返工 checkpoint `d878645` 源码重建，性能修正（渐进逐 Fact 事件发布）已入包；
    重打包后 `h8_package_audit`=PASS（marker\_hits=0／forbidden=0）、`t11_isolated_start`=PASS
    （隔离启动 /api/health 2.8s，无 Key/注入/开发路径），见 §6.4。此包为开发侧候选，**不构成发布包**，
    独立验收由用户 / Doc Agent 另启。

### 7.2 逐项交付映射

| PLAN ID                          | 用户结果                    | 开发理解                                 | 实际交付                    | 可复核证据                              | 已知偏差     |
| -------------------------------- | ----------------------- | ------------------------------------ | ----------------------- | ---------------------------------- | -------- |
| V220-G01 任务连续性                   | 任务跨路由/刷新/重开恢复           | Task/InputRevision/Snapshot/Event 恢复 | task\_repository/sse 协议 | T2/T3/T4 27+26+27                  | 无        |
| V220-G02 可恢复草稿+实际取消              | 姓名必填/选填/后端确认/取消停产       | 状态机+单活动+cancel 协议                    | task\_api/task\_cancel  | T3/T5                              | 无        |
| V220-G03 四阶段渐进结果                 | P1-P4 真实状态              | generate\_task 编排+事件流                | task\_generation        | T6/T7 real e2e                     | 无        |
| V220-G04 性能                      | total 降25%+首Fact≤15s    | 见 §6.2 / §7.6                        | 真实模型 timing             | §6.2 总耗时矩阵 + §7.6 首 Fact 矩阵（本轮新证据） | 无（返工后达标） |
| V220-G05 内容正确性                   | 联系方式/技能/headline/教育/短输入 | document\_assembler+渲染修复             | T7/T8                   | 57+14                              | 无        |
| V220-G06 最终产物不变量                 | DOCX 唯一真源/PDF 同源/三端一致   | real DOCX→Word→PDF 链                 | docx\_writer/隔离验证       | real e2e artifact hash             | 无        |
| V220-R1-T01 身份+Pre-mortem        | Required Reading/假设台账   | §1-§3                                | §5                      | 完成                                 | 无        |
| T02 Task schema/migration/repo   | 状态/冻结/容量                | task\_repository                     | T2 41/0                 | 无                                  | <br />   |
| T03 API/保存/单活动/恢复                | REST                    | task api                             | T3 26/0                 | 无                                  | <br />   |
| T04 SSE seq/恢复/幂等                | 事件流                     | task\_sse                            | T4 27/0                 | 无                                  | <br />   |
| T05 实际取消/清理/fence                | cancel                  | task\_cancel                         | T5 39/0                 | 无                                  | <br />   |
| T06 紧凑JD/Fact+reason/并发2/门禁      | 编排                      | task\_generation/jd/llm/prompts      | T6 23/0                 | 无                                  | <br />   |
| T07 联系方式/技能/headline/教育          | 装配                      | document\_assembler                  | T7 57/0                 | 无                                  | <br />   |
| T08 短输入 TemplateError 修复         | 宽容渲染                    | template\_renderer                   | T8 14/0                 | 无                                  | <br />   |
| T09 容量/保留/cleanup                | cleanup                 | task\_cleanup                        | T9 19/0                 | 无                                  | <br />   |
| T10 真实纵切 Architecture Check      | 只读                      | §4                                   | 246/0 回归                | 无                                  | <br />   |
| T11 完整 Gate+Falsification+RESULT | 本批收口                    | §5-§8 + 新增验证脚本                       | Gate/打包/隔离启动            | 无（首Fact≤15s 偏差已在返工关闭）              | <br />   |

### 7.3 参数与运行证据

- **最终模型**：`deepseek-v4-pro-ga-260813`（ARK，base `https://ark.cn-beijing.volces.com/api/v3`）；
  **Embedding**：`doubao-embedding-vision-251215`；temperature=0.0

- **Token 区间**：JD 紧凑上限 `JD_COMPACT_MAX_TOKENS`；Fact/Reason `FACT_MAX_TOKENS`/`REASON_MAX_TOKENS`；
  单任务 completion ≤ 16k（`TASK_LLM_COMPLETION_LIMIT`）；在允许区间（T6 门禁断言，未越界）

- **调用摘要（真实纵切，typical 样例）**：逻辑调用公式 `1+2F`；真实样例 SUCCEEDED，DOCX 38,9xx B、PDF 4,225,x7x B

- **性能样本**：total 见 §6.2（**复用**，返工前 n=5 median 38.04 max 43.04；返工后典型 cold 实测
  total≈38.35/37.42/40.07s）；**首完整 Fact 全部为本轮新证据**（见 §7.6 矩阵 6 格 n=3：中位数
  8.68~~14.04、最大值 8.99~~14.27，均 ≤15s）。旧“首 Fact n=2 均为 17.4s”是返工前（事件挂到整段
  经历结束才发布）的历史测量，仅作根因对照，不再作为达标证据。

- **状态/事件真实序列**：`_e2e_v22_slice.py` 打印 jd.done→fact.done→reason→P4；取消/T09 归 T5/T9 隔离验证

- **Pre-mortem/Architecture Check/Falsification**：三处注册失败模式（§2）均配最小证伪探针；T10 当时未打开 Challenge，后续性能返工已按 §7.6 开启并关闭 `CHALLENGE_OPEN`；T11 Falsification 找到 2 个真实反例并修复。

### 7.4 实际变化与偏差

- **API**：新增 `POST /api/task`、`PUT /api/task/{id}/save`、`/freeze`、`/start`、`/cancel`、`/generate`、
  `GET /api/task/{id}`、SSE `GET /api/task/{id}/stream`（prefix `/api/task`）；gen 另出新 worker

- **数据库/schema**：新增 `tasks / input_revisions / task_subtasks / task_snapshots / task_events` 表 +
  迁移；`Experience/Fact` 既有事实表未改内容定义

- **领域模型**：新增 `ResumeDocument` 装配中间层、`EducationItem.description`；`TaskSnapshot.payload` 入参镜像（R1 受控镜像）

- **模块职责**：新增 `task_repository/task_service/task_generation/task_sse/task_cleanup/task_cancel/
  document_assembler`；`template_renderer` 加 `allow_empty_required`/`bold_headline`；P4 由桩升级为真实 DOCX/PDF 链

- **配置/依赖**：无新增运行时依赖（复用 langchain/openai/pywin32）；真实模型发布前仅存在于
  `backend/.env`（**T11 完成真实 timing 采集后已删除该文件**，本文件保留删除确认；用户要求
  "开发结束后不要保留这个信息"，不必保留 ark key /模型名于仓库内）。

- **打包**：spec 增加 `services` 子模块收集（排除 `services.pdf_renderer`）；excludes=\["reportlab"]

- **可见前端**：无（Revision 1 禁可见改动；仅修复冲突导致的构建）——**无**

- **假设台账最终状态**：A09/A10 已由 T07/T08 改为 EVIDENCED（含反例修复）；**A03 返工后恢复为
  EVIDENCED**（§7.6 矩阵 6 格 n≥3，首完整 Fact 中位数与最大值均 ≤15s）；A05/A06 维持如实（T6/T9
  门禁覆盖，Long/干预 16k 探针在 T6）

- **Challenge**：本批返工对首 Fact 性能偏差**开启** **`CHALLENGE_OPEN`**（§7.6）并已在现合同内达成
  ≤15s——未改硬目标/模型/调用公式/并发上限/技术路线，只修正编排器的事件发布粒度（渐进逐 Fact），
  因此**不需要新 PLAN Revision、也不把问题推迟给 Revision 2**。

### 7.6 CHALLENGE\_OPEN 处置（本轮返工，均为本轮新证据）

**问题**：从“点击生成”计时的首个完整 Fact 曾 ≈17.4s（旧测量为 P1 完成点起算 17.4s；若严格从点击
零点起算曾高达 \~23.9s），>15s 硬目标。

**完整延迟分解**（本轮新证据，真实复跑 `_e2e_v22_profile.py`，模型 deepseek-v4-pro-ga-260813，
typical，冷启动，点击零点同基单调时钟；进程 `perf_counter` 全程 **38.01s**，DOCX 38961 B / PDF 4,226,804 B）：

| 阶段             | 返工前                                 | 返工后（本轮实测）                 | 说明                   |
| -------------- | ----------------------------------- | ------------------------- | -------------------- |
| P1 紧凑 JD（LLM）  | 5.6–6.6s（旧）                         | 6.95s（jd.done 相对点击零点）     | 单次 LLM，无并发           |
| P2 选材（本地）      | \~0.5s（旧）                           | \~0.0s（selection，无 LLM）   | 本地排序                 |
| P3 首个完整 Fact   | 挂到整段经历（+18.3s，首 Fact \~23.9s）**根因** | **+6.51s（首 Fact 13.47s）** | 渐进逐 Fact 发布          |
| P4 装配/DOCX→PDF | —                                   | 落于 SUCCEEDED（38.01s）      | 非首 Fact 路径，不影响首 Fact |

**最弱假设与根因**：此前 P3 事件在“整段经历全部 6 次调用（3 Fact + 3 reason）结束后”才统一写
fact.done；首个完整 Fact 的**发布时刻**被后续调用的完成时刻人为拉长。技术路线与调用公式并无问题，
是**事件发布粒度**（编排器实现细节）导致的测量偏差。

**现合同内可达成性的验证**：改发布粒度（worker 每完成一个已绑定+校验的 Fact 即经线程安全队列交回
主线程单一 DB 写者，立即发 fact.done；reason 单独以 reason.delta 渐进发布）。不改变调用公式
（仍 1+2F）、并发上限（MAX\_WORKERS=2）、模型与 Token/质量约束。**真实矩阵结果**（每格 n≥3，首完整
Fact = 首个 fact.done；中位数 / 最大值均须 ≤15s）：

| 格            | n | 原始 first\_fact（逐步采样）  | 中位数   | 最大值   | 是否 ≤15s |
| ------------ | - | --------------------- | ----- | ----- | ------- |
| short-cold   | 3 | 12.15 / 11.75 / 11.84 | 11.84 | 12.15 | ✓       |
| typical-cold | 3 | 14.04 / 13.90 / 14.27 | 14.04 | 14.27 | ✓       |
| long-cold    | 3 | 13.64 / 13.73 / 13.19 | 13.64 | 13.73 | ✓       |
| short-warm   | 3 | 8.99 / 8.68 / 8.58    | 8.68  | 8.99  | ✓       |
| typical-warm | 3 | 10.79 / 10.61 / 10.00 | 10.61 | 10.79 | ✓       |
| long-warm    | 3 | 10.90 / 10.11 / 10.34 | 10.34 | 10.90 | ✓       |

（cold 每样本独立进程+全新 runtime；warm 同进程预热后连续 n 次。total 仍满足 ≥25% 相对 V2.1.0
典型的降幅，见 §6.2 复用证据。）

**本轮证据归集（尽可能可复核）**：真实矩阵原始 JSON 逐步采样已持久化于
`backend/validation-artifacts/v2.2-rework/matrix/cold_{short,typical,long}.jsonl` 与
`warm_{short,typical,long}.jsonl`（该目录按仓库约定整体 `.gitignore`，仅留本机审计，不入 checkpoint）；
复现入口脚本 `backend/_e2e_v22_profile.py`、`backend/_e2e_v22_matrix.py` **已随 checkpoint** **`d878645`** **提交**，
供 Documentation Agent / 独立验收在具备 ARK Key 时复跑。本表为这些原始采样的汇总指标。

**替代路线与最小证伪实验**：若渐进逐 Fact 仍不达标，备选路线＝把首个经历的首个 Fact 从并发池
单列、让 P1 完成即串行启动首 Fact（减少多 worker 共享限流的等待），其证伪实验＝单任务只含 1 段
经历时测首 Fact；本矩阵 short/1 经历即**直接验证**该场景（short-cold max 12.15s ≤15s），故无需
额外打开。任何路线均未移动计时零点、未降低内容质量、未删减合法事实。

**结论**：已开启又**在现合同内关闭**的 CHALLENGE\_OPEN；A03 恢复 EVIDENCED；无需 PLAN Revision。

### 7.5 待独立验收问题

1. 刷新/重连/乱序下是否真实不重复调用、不交叉覆盖（T3/T4 隔离验证 → 需包内候选复核）
2. 取消后 Provider/Word/artifact 是否真正停止、能否立即开始新任务（T5 验证）
3. 两阶段绑定、并发 2、调用/Token 在最终包成立（**首 Fact ≤15s 已由 §7.6 源层真实矩阵证实；
   包内最终复核仍属独立验收**）
4. task cleanup 是否可能误删活动状态或已发布 DOCX/PDF（T9 验证）
5. 联系方式/技能/headline/教育/short 是否在真实 DOCX/PDF 一致（T7/T8 + real docx hash 验证）
6. 最终 Revision 2 是否忠实实现其绑定的 `DS-xxx`，HTML 过程预览未成第二产物真源。

> 说明：以上 6 项属**独立验收**范畴（需在 Revision 2 最终候选包上、正式发布前复核），不影响本批开发 Gate 的 PASS；
> 首 Fact ≤15s 的开发侧证据已由 §7.6 源层真实矩阵证实。

### 7.7 开发候选 checkpoint（本批收口主体）

- **开发候选 H**：`09ee23651161afe7dc24f2e839618f49213e4217`；唯一父为返工 checkpoint
  `d8786457c0422dfbca1ad4f4e81b1c8096de3375`。

- **返工 checkpoint（继承基础）**：HEAD `d8786457c0422dfbca1ad4f4e81b1c8096de3375`，唯一父
  `085c8d84cb25456ffdabbeb0cbd06b66097e6962`

- **相对批准基线** **`d75b692`** **完整 diff（d75b692 → H）**：
  **35 files changed, 6619 insertions(+), 14 deletions(-)**（仍未新增文件、故保持 35 files；本轮仅对已
  入档的 RESULT.md 增行改档，插入数由返工 checkpoint 的 6573 增至 6619）

- **工作树**：`git status --porcelain` 为空（clean）；`backend/.env` 已删除；`validation-artifacts/`
  与 `.trae/` 按仓库约定整体 `.gitignore`，不入 checkpoint。

## 8. 第一批开发 Gate 收口与实际结果

- **状态已改为** **`BATCH1_DEV_VERIFIED`**：**开发侧 T01–T11 全部完成、开发 Gate 全 PASS（候选冻结）**；
  独立 Acceptance（§7.5 各项）由用户 / Doc Agent 在适当时机另启，本批不进入也不替代。T10 为开发侧
  Architecture Check，不存在“用户 / Doc Agent 手动 T10”。

- 性能偏差已按 `CHALLENGE_OPEN` 处置：§7.6 已给出完整延迟分解、根因、现合同内 ≤15s 的达成验证与
  替代路线/最小证伪实验；A03 恢复 EVIDENCED；**无需 PLAN Revision，问题不推迟给 Revision 2**。

- 保留已通过的功能/回归/构建/打包结果；本轮仅重跑受性能与身份修正影响的 Gate，并明确标注
  **复用证据**（T2–T9 回归、precheck、V2.1.0 基线表）与**本轮新证据**（§6.2 总耗时矩阵、
  §7.6 首 Fact 渐进发布矩阵、重打包身份/隔离启动）。

- **onedir 已从返工 checkpoint 源码重建并复核**：性能修正（渐进逐 Fact 事件发布）已入包；
  `h8_package_audit`=PASS（marker\_hits=0／forbidden=0）、`t11_isolated_start`=PASS（隔离启动
  /api/health 2.8s，无 Key/注入/开发路径）；包身份与 EXE SHA-256 见 §7.1/§6.4。**返工后工作树已清
  clean**（含托管 `.trae/`，`git status --porcelain` 为空），形成最终候选 checkpoint 提交（§7.7）。

- 未触 Design Gate 禁止范围（无可见布局/文案/动效改动）。

- Documentation Agent 的语义交接结论见 §9；未新增独立交接文件。

**下一门禁**：Product Owner 已批准本地 Design Snapshot `D-003`；Documentation Agent 据此形成 Revision 2、
映射并导入 canonical `DS-003`，取得 Product Owner 对 Revision 2 的批准后，才授权第二批可见实现与
最终集成。本批是 clean 开发候选 checkpoint（`BATCH1_DEV_VERIFIED`），**不构成发布候选或独立验收 PASS**。

## 9. RESULT 语义交付审查

- **结论**：`DOC_ALIGNED`。

- **审查对象**：开发候选 H `09ee23651161afe7dc24f2e839618f49213e4217`，批准 PLAN blob
  `324302a0ef6d81214c752d12281c221f2550f320`，分支 `version/v2.2.0`。

- **机械前置**：H 唯一父为 `d8786457c0422dfbca1ad4f4e81b1c8096de3375`；相对批准基线
  `d75b692` 为 35 files、+6619/-14；开发交接时工作区 clean。

- **语义结论**：RESULT 已完整声明 Revision 1 范围、开发理解、实际交付、Challenge 处置、开发 Gate、
  证据入口、包身份、偏差和待独立验收问题；声明与 PLAN Revision 1 一致，可以进入下一文档门禁。

- **边界**：本结论只依据 PLAN、RESULT、机械身份和证据入口，不证明源码或运行行为真实正确。
  Revision 1 明确不启动独立 Acceptance；最终候选包的真实纵切属于 Revision 2 完成后的独立验收，
  不是本批新增开发门禁。

***

## R2-1. Revision 2 · T01 身份与 Required Reading 核对

> Revision 1 完成（§1–§9 为其开发记录，`BATCH1_DEV_VERIFIED`）。以下起为 Revision 2 开发记录，
> 依 PLAN（Revision 2）实施矩阵与 RESULT Delivery Contract（§8）逐步收口至 `REV2_DEV_VERIFIED`。

| 阅读对象 / 基线字段                                                           | 结论                                                                                                                                                                      |
| --------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs/README.md` §0、§1–§5；`docs/CURRENT_STATE.md`；本 PLAN 全文           | 完成                                                                                                                                                                      |
| `HUMAN_AI_WORKFLOW.md` §3.1/3.2/3.3/3.4、§6、§11                        | 完成                                                                                                                                                                      |
| Revision 1 `RESULT.md` §6–§9                                          | 完成（本文件 §1–§9）                                                                                                                                                           |
| `DS-003`：SNAPSHOT.md、SPEC.md、prototype/README.md、prototype/index.html | 完成（见 §R2-2）                                                                                                                                                             |
| 角色 / 开发路径                                                             | Development Agent / `version/v2.2.0`，`git branch --show-current` 一致                                                                                                     |
| 当前 HEAD                                                               | `47ae33edcd20e160e64466ece0bf3bdda8cc74a9`（Revision 2 批准 identity 记录顶部）                                                                                                 |
| 批准收口 commit / 批准内容基线                                                  | 收口 `e3c68ac7405abe3a70e807b22d51a25ddb80731f`（VH-014）；内容基线 commit `af2f8f9bc193fbe78e77e5d6009b5ad7836d6f3e`                                                            |
| 当前批准 PLAN blob                                                        | `e134703ce6e37a2f4d5df389662119f38638fae8`（`git rev-parse HEAD:docs/versions/v2.2.0/PLAN.md`）                                                                           |
| 工作树                                                                   | clean（`git status --porcelain` 空）                                                                                                                                       |
| 产品基线                                                                  | `v2.1.0` → `5d72a2e08ebd4fa416b4b1dcdd79c1d08dfc7cfd`                                                                                                                   |
| DS-003 导入身份                                                           | 源 `D-003` → canonical `DS-003`；manifest SHA-256 实测 = `CC699466AF400EE603A7E9FE39EF22E75BC7DB37BD7150F41A0F0718AC9D0A61`（与 PLAN 一致）；**27 个登记文件全部 SHA-256 核对 mismatch=0** |

**身份边界确认（Development Agent，Revision 2）**：只读 PLAN/HISTORY/CURRENT\_STATE/DECISIONS/全局
文档、不修改；在 Revision 2 实施矩阵与冻结路线内修改源码/测试/依赖/构建配置；候选冻结前写本文档
实施/自测/偏差，不写"独立验收通过"或"可发布"；不操作 canonical `main`、GitHub remote 或正式 tag；
不读取/跟随 Design Agent 的 `current/` 与后续工作稿。严格复用 Revision 1 的单一 Task/SSE/生成/
artifact 链，不另建第二套。

## R2-2. Revision 2 · T01 前置核对与关键边界（Start-of-Implementation 反思）

进入 T02 前，依据 PLAN §5、§6 对本 Revision 特有的风险做一次先验核对，作为 Pre-mortem 的正式宿主
（PLAN §6 四项 + §5 五项已含 Revision 1 部分；此处只列 Revision 2 新增/最相关项）。

### 失败模式 R2-A：路由状态与后端 Task 形成双真源，刷新后 UI 看似恢复但重复生成或覆盖

- **最弱反证/最小证伪探针**：T03/T04——进入或重连任务必须先 `GET /api/task/{id}` 取权威快照，再以
  `after_seq` 订阅 SSE；前端不得在无快照时自行拼接生成状态，也不得在任何路径第二次调用生成端点。
  刷新前后对同一 `task_id + input_revision + seq` 断言：LLM/Embedding/operation=0 增量，UI 只呈现
  快照已确认输入（dirty 本地值保持"未保存"）。

- **最迟决策点**：T03 首条"保存→刷新→恢复"实测之后；T06 首条真实纵切之后复核。

- **替代路线**：若路由壳被迫持有生成状态，则把权威快照降为唯一真源、路由态只做选中/焦点语义，
  禁止任何未经快照确认的业务值写入结果展示。

### 失败模式 R2-B：HTML 过程预览与 ResumeDocument/DOCX/PDF 分叉，用户看到的 Fact 与最终 PDF 不一致

- **最弱反证**：T05/T06——每个进入 HTML 的完整 Fact（`fact_id/headline/body/fact_refs`）必须来自同一
  权威快照，且该快照正是装配 ResumeDocument→DOCX→PDF 的真源；reason 只作旁侧展示、绝不进入简历正文。
  PDF.js viewer 与下载读取同一不可变 PDF artifact（比对字节/hash）；anchor 绑定当前 artifact，
  空/错配诚实不可用。

- **最迟决策点**：T06 首条真实纵切后 Architecture Check（PLAN §5 强制暂停点）。

- **替代路线**：任一环节漂移即进入 `CHALLENGE_OPEN`，不得用 CSS/重试逼近或固定样张掩盖。

### 失败模式 R2-C：Design-only fixture / 固定样张 / 无效按钮被误接入正式产品

- **最弱反证**：T02/T07——工作台与"我的经历/我的简历/个人与隐私"只连接既有真实 API
  （`/api/task*`、`/api/experience*`、records 能力、privacy 文案），不存在的端点不得用 fixture/固定
  前端假数据冒充；DS-003 明确"不实施"的能力（主题切换、评审条、批注工具、自然语言修改）不在正式 UI
  出现下载/导出/假成功入口。

- **最迟决策点**：T02 Design Fidelity 对照、T07 真实能力映射完成后。

- **替代路线**：页面出现任何非真实可用动作时降级为诚实不可用/隐藏，而非远端演示。

> **Pre-mortem 结论**：已登记 3 个 Revision 2 可证伪失败模式，各配最小证伪探针、最迟决策点与替代
> 路线，非"未发现风险"式空答。T01 完成证据＝上述身份/清单核对 + 本节反思已建立；实现度自 T02 起
> 递增，最终 Gate 与 Falsification 见 T10/T11。

***

## R2-3. Revision 2 · T02–T06 实现与 T06 首条纵切后 Architecture Check

> 本批次实现均在 `version/v2.2.0` 工作树未提交状态推进（收口时统一成 checkpoint，身份见 T11）。
> 以下证据为本次核对时点可复现的构建 / 导入 / 代码事实：前端 `tsc -b` 与 `vite build` 均通过
> （`dist/index.html 0.40 kB`、`index-CQFjAinr.js 630.62 kB`，>500kB 仅为非致命 chunk 提示）、
> 后端 `services.document_assembler` 导入干净、`pdf_anchors.build_anchors_from_word_pdf` 签名与装配调用一致。

### R2-3.1 T02 DS-003 theme A 工作台壳（四步轨道与路由壳）

- 落地：`WorkbenchShell`（顶栏 / 头像菜单 / 四步工作台轨道）、`StepRail`、`WorkbenchPage`（四步主/辅卡
  与响应式断点）、`workbench.css`（theme A 令牌，`--primary/--focus/--error/--success/--warning` 等，
  系统字体、无新增 npm 依赖）。路由经 `App.tsx` 挂载到既有工作台路径。

- 关联失败模式 R2-C：外壳仅渲染真实工作台容器，未引入任何固定样张 / fixture / 假下载入口。

### R2-3.2 T03 身份 / JD 保存确认、dirty 边界与刷新恢复

- `WorkbenchTaskContext`：绑定真实 `/api/task`（`taskApi.create/save/freeze`）；姓名必填、JD ≥ 60 字符
  校验（V220-G02，本轮由 30 对齐为 60）；750ms debounce；dirty 状态管理；刷新按权威快照恢复（`applyView` 先 `GET /api/task/{id}`）。

- `StepIdentity`：身份与 JD 输入、保存反馈。

- 关联失败模式 R2-A：进入任务先取权威快照再订 SSE，不复用路由态重建生成状态。

### R2-3.3 T04 P1/P2 逐项输出、历史阶段回看与缺口重取

- `StepUnderstand`（P1 JD 分析）、`StepMatch`（P2 选材）逐项输出；回看按阶段快照渲染；缺口重取依赖
  权威快照而非自行拼接（`after_seq` SSE 订阅见 T06 前的 TaskContext）。

### R2-3.4 T05 P3 HTML 过程预览、完整 Fact、reason 旁侧与依据

- `StepCheckout`：P3 过程 HTML 预览 + 完整 `fact_id/headline/body/fact_refs`；reason 仅旁侧展示，绝不
  落入简历正文；`PdfPreview`（pdf.js）读取与下载同一 artifact，anchor 空/错配诚实不可用。

- 关联失败模式 R2-B：HTML 预览只作过程展示、不可导出/交换为第二真源。

### R2-3.5 T06 P4 真实 PDF 切换、anchor、双下载

- `WorkbenchTaskContext` 新增终态发布路径 `publishedDocxPath / publishedPdfPath`（仅 SUCCEEDED 非空），
  `applyView` 写入、`startNewTask` 清空。

- `StepDownload`：任务 `SUCCEEDED` 时替换 P3 过程预览；PDF.js 与「下载 PDF」读同一 `published_pdf_path`
  字节一致；Word / PDF 双下载独立可用；PDF 缺失时保留 Word 下载并诚实显示「PDF 不可用」，绝不伪造链接。

- 后端 `document_assembler`：从 Word 转换后的**确切** PDF 文本层重建 `pdf_anchors`（绑定 `pdf_artifact_id`
  \= `resume_revision_key`），失败项记 `unavailable` 诚实不高亮；锚点失败不影响 DOCX/PDF 可用。

- `WorkbenchPage.mainContent`: `activeIdx===3 && status==='SUCCEEDED'` → `StepDownload`，否则保留
  `StepCheckout`（运行/回看不抢先）。

### R2-3.6 T06 Architecture Check（首条 Revision 2 真实纵切后的只读暂停点）

- **双真源检查**：成品 PDF 为唯一排版真源（ResumeDocument → DOCX → 本机 Word→PDF 转换，`document_assembler`
  单一装配路径，与 Revision 1 同一链）；HTML 过程预览（P3 `StepCheckout`）与 pdf.js 成品视图（P4
  `StepDownload`）都**只读**该链产物——过程预览不可导出/交换，成品视图与下载是同一不可变 PDF 字节。
  未发现第二套可写真源。满足 R2-B 的"任一环节漂移→CHALLENGE\_OPEN"失败模式的反证：viewer 与下载共用
  `published_pdf_path`，anchor 绑定 `pdf_artifact_id` 且空/错配 fail closed，故无漂移成立点。

- **职责转移**：P4 由 Revision 1 的真实 `document_assembler` / `make_task_assembler` 承担，前端不另建
  装配；`pdf_anchors` 只补坐标层，不替代 DOCX/PDF 生成。职责无转移。

- **fixture 检查**：工作台全部动作绑定真实 `/api/task*`、`/api/template/download`；无固定样张 / theme 切换 /
  评审条 / 批注 / 自然语言修改等 DS-003「不实施」能力进入正式 UI。

- **结论**：T06 首条 Revision 2 纵切（真实 DOCX/PDF 装配 + P4 成品视图）未发现需开 `CHALLENGE_OPEN` 的双真源、
  漂移或职责转移问题。开发侧 Architecture Check **无开放 Challenge**；据此可铺开 T07～T11。

***

## R2-4. Revision 2 · T07 我的经历/我的简历/个人与隐私真实能力映射

> 完成证据（可复现构建事实）：T07 改动后前端 `tsc -b`、`eslint rules-of-hooks`、针对
> `App.tsx / RecordsPage / PrivacyPage / WorkbenchShell` 的 eslint 全部通过。改动均在未提交工作树。

### R2-4.1 我的经历（/experiences）

- 复用既有真实「Career Memory」`ProfilePage`：`experienceApi.exp/list/create/update/remove` 全部绑定真实
  后端；type tab 值域、`summary_status`、`fact_count` 均来自真实数据，无 fixture。

- 作用范围断言：本页修改只写经历库（影响未来任务），不写当前冻结 InputRevision、不触碰正在生成内容或
  已导出文件（后端既有边界，T07 不新增第二套写入）。

### R2-4.2 我的简历（/records）

- 从「诚实空说明」升级为绑定**当前任务真实 artifact**：读取 `WorkbenchTaskContext` 的终态发布路径
  `published_docx_path / published_pdf_path`，下载走同一 `/api/template/download` artifact，与工作台 P4
  逐字同源；SUCCEEDED + 无 artifact，以及 RUNNING/FAILED/CANCELLED/DRAFT 均如实呈现与下一步，不伪造列表
  或可用链接。后端无「已生成文件列表」端点，故不伪造历史列表（满足"无fixture"）。

- 作用范围断言：本页仅展示当前任务（`taskId + input`），不做跨任务/历史范围推断。

### R2-4.3 个人与隐私（/privacy）

- 真实边界文案沿用；新增一条真实能力「清空当前未运行草稿」：明确指向工作台顶栏「＋ 开始新任务」
  丢弃当前 DRAFT/已取消草稿，且不触碰经历库或历史成品（满足矩阵"可清当前未运行草稿"）。

### R2-4.4 当前任务返回（PLAN §7.2 Gate：返回后不丢失、不新增调用）

- `WorkbenchTaskProvider` 由仅 `"/"` 提升到路由最外层（`<App>` 内包裹 `<Routes>`），使「我的经历/我的
  简历/个人与隐私」与工作台共享同一当前任务真源；从这些页面返回 `/` 时 task/input/phase 在内存中保持，
  不触发额外 `GET /api/task/{id}` 或任何生成调用（刷新/整页重开仍走既有权威快照恢复）。关联失败模式
  R2-A/R2-C 的反证：路由不复制生成状态，各页只连接既有真实 API。

***

## R2-5. Revision 2 · T08 取消、新任务、insufficient/partial/failed、范围重试与 ErrorBoundary

> 完成证据：T08 改动后前端 `tsc -b`、`npm run lint:hooks`（项目 Hooks Gate）通过；`vite build` 产出含
> `.wb-failed` 的 CSS（`index-C-g9eyMe.css` 65.5 kB）。`WorkbenchTaskContext` 中两处
> `react-hooks/set-state-in-effect`（第 282 / 515 行 restore 与 taskId 重置 effect）为 T03/T05 既有代码，
> 非本次引入，项目 Gate 以 `lint:hooks` 为准（通过）。

### R2-5.1 取消 / 新任务（不重复 POST、不丢状态）

- `cancel()`（仅 `RUNNING/CANCELLING` 调一次 `POST /api/task/{id}/cancel`）与「开始新任务」
  `startNewTask()`（清空本地草稿与 artifact 路径）已在 T03 落地；顶栏按钮运行中显示「取消生成」、
  空闲显示「＋ 开始新任务」，`generate()` 由 `generatePending` 单飞守卫，点击生成只创建一个 task operation
  （满足"不重复 POST"）。

### R2-5.2 FAILED / CANCELLED 终态面板（不白屏、不丢状态）

- 工作台主面板新增 `.wb-failed` 诚实终态面板，替代"无提示跳回第 1 步"：

  - FAILED：展示失败原因（`generateError` 或后端稳定 `terminal_error` 错误码，如
    `GENERATION_FAILED`）；明确"输入保留、已完成经历/事实复用不重复计费、范围化重试"三要点，动作指向
    「去我的经历补充 ›」与顶栏「开始新任务」。

  - CANCELLED：说明输入保留、未发布成品，下一步指向「开始新任务」。

- `WorkbenchTaskContext` 新增 `terminalError`（`applyView` 写入、`startNewTask` 清空）支撑上面板。

### R2-5.3 insufficient / partial 诚实降级

- FAILED/取消面板声明已完成经历与事实保留在真实数据库（真实范围），不伪造补齐；补充纠正走「我的经历」
  真实能力，随后点击生成即按失败/缺口范围复用已完成事实（"范围重试"）。

- P3 逐 Fact 的 `insufficient` 标记沿用 T05 `StepCheckout` 诚实呈现，不输出通用空话补齐。

- **范围重试的操作证据（本批实测，非仅声明）**：重试边界由 `core/task.py LLM_MAX_ATTEMPTS=3` + `services/llm_service.invoke_observed_json` 限定为「**单次逻辑调用内最多 3 个 HTTP attempt**」，并区分可重试/不可重试（`_retryable`：timeout/connection/reset/rate-limit/429/json-decode/validation 才重试；其余立即失败）。直接构造 provider 注入实测（真实 `invoke_observed_json` 路径）：

  - CASE1 可重试前 2 次 `ConnectionError` → 第 3 次成功：`attempts=3`、`retry_reasons=['attempt1:ConnectionError','attempt2:ConnectionError']`、返回 `{ok:true}`；

  - CASE2 可重试 3 次全失败 → 抛 `LLMOutputInvalidError`（严格失败，绝不返回空成功），`attempts=3`；

  - CASE3 不可重试 `ValueError` → 直接失败不重试，`attempts=1`；

  - CASE4 失败后 token 预算正常回吐（`budget.used` 仅含实际成功 token）。

  上述 4 例与 `_v22_t6_generation.py [T6]`（`fail_first={"compact":1}` → compact 恰好 2 attempts 后成功并返回 typed 结果）互相印证：**重试范围是"单逻辑调用"而非"整任务"，任务级失败只复用已完成范围、不做全局重放**。

### R2-5.4 ErrorBoundary

- 复用 V2.1.0 R21 应用级 `AppErrorBoundary`（`main.tsx` 顶层挂载，生产 build/onedir 同样可见）：渲染期
  抛错显示固定可理解错误界面，提供「重试页面渲染 / 返回生成工作台」，两者都不重提生成 API、不创建
  operation、不计费、不覆盖已成功 artifact；诊断只记脱敏组件栈，不含正文/Key —— 满足"不白屏"。

***

## R2-6. Revision 2 · T09 全视口 / 键盘 / 焦点 / reduced-motion / 卡片与滚动收口

### R2-6.1 已核实不变量（构建 / 代码事实）

- **html/body 不产生整页滚动**：`global.css` `html,body{overflow:hidden}`、`html,body,#root{height:100%}`；
  工作台 `.wb-shell{height:100%;overflow:hidden}`（`workbench.css`）把滚动收口到指定内部容器
  （`.wb-panel__scroll{overflow:auto}`）；次级页走 `.page-scroll{height:100vh;overflow-y:auto}`。满足
  PLAN §4.3「只允许指定内部滚动容器」。

- **reduced-motion**：`@media (prefers-reduced-motion: reduce)` 已禁 `.wb-shell` 全子树
  transition/animation/scroll-behavior（既有，核实存在）。

- **focus-visible**：`.wb-shell :focus-visible` 与 `.wb-btn:focus-visible` 可见焦点环（既有）。

- **响应式断点**：1100px（三栏缩窄）/ 850px（切单主卡 + 步骤导轨横向化、隐藏说明栏）已覆盖
  1280×800 至 320×568 的小视口变换（PLAN §4.3/§7.1）。

### R2-6.2 本次收口（T09 改动）

- 头像菜单关闭后焦点归还触发按钮：点击外部 / `Escape` 关闭菜单时 `avatarBtnRef.current?.focus()`
  （`WorkbenchShell`），便于键盘继续操作；`aria-haspopup/aria-expanded/role=menu/menuitem` 既有。

- 完成证据：改动后 `tsc -b`、`npm run lint:hooks`、`WorkbenchShell` eslint 通过。

### R2-6.3 隔离 E2E 视口截图 / DOM 核对（H2 clean onedir + 真实模型）

- 已在 H2 clean onedir 隔离 runtime 真实 E2E（`scripts/h8_real_model_e2e.py`，有头浏览器 + 真实模型
  deepseek-v4-pro-ga-260813，P4 成品页）中对 7 个冻结 viewport 逐视口执行截图 + `_LAYOUT_PROBE` DOM 探针，
  证据落在 `validation-artifacts/h8/e2e/viewports/vp_{W}x{H}.png`（7 张均已落盘，28.9–205.7 KB）与
  `real_model_e2e.json.viewports`。实测投影如下：

| viewport  | docOv | bodyOv | htmlOvY | bodyOvY | 内部滚动容器               | pdfState | dlLinks | 截图 |
| --------- | ----- | ------ | ------- | ------- | -------------------- | -------- | ------- | -- |
| 1920×1080 | 0     | 0      | hidden  | hidden  | wb-panel\_\_scroll   | ready    | 2       | ✓  |
| 1440×900  | 0     | 0      | hidden  | hidden  | wb-panel\_\_scroll   | ready    | 2       | ✓  |
| 1280×800  | 0     | 0      | hidden  | hidden  | wb-panel\_\_scroll   | ready    | 2       | ✓  |
| 1024×768  | 0     | 0      | hidden  | hidden  | wb-panel\_\_scroll×2 | ready    | 2       | ✓  |
| 720×450   | 0     | 0      | hidden  | hidden  | wb-panel\_\_scroll   | ready    | 2       | ✓  |
| 390×844   | 0     | 0      | hidden  | hidden  | wb-panel\_\_scroll   | ready    | 2       | ✓  |
| 320×568   | 0     | 0      | hidden  | hidden  | wb-panel\_\_scroll   | ready    | 2       | ✓  |

- 结论：7 视口全部 `html/body` 整页滚动 `overflow=0`、`overflow-y=hidden`，滚动仅发生在指定内部容器
  `.wb-panel__scroll`（1024×768 因布局折行出现 2 个内部滚动面板，仍非整页滚动），PDF viewer `data-state=ready`
  且 ≥1 页、下载区 2 个链接均固位 —— 满足 PLAN §4.3/§7.1「只允许指定内部滚动容器」不变量。本节已由待执行改为
  实证记录。

## R2-7. Revision 2 · T10 收口：模型默认对齐、clean 重建、隔离真实模型 E2E（开发侧冻结证据）

> 本轮为 T10 重闸的收口补记，覆盖此前 PLAN §7 BLOCKED 的「隔离 onedir 真实模型不可用」阻断的解除。

### 7.1 模型默认对齐（唯一源码改动动因）

- **现象**：源码运行时在正常数据目录读到 `RESUME_DATA_DIR/config/connection.json`，命中已开通模型
  `deepseek-v4-pro-ga-260813`，故源码级矩阵/纵切通过；而 **H2 clean onedir 隔离临时目录无该 config**，
  落回 `core/config.py` / `core/config_resolver.py` 内置默认 `doubao-seed-evolving`，实测 Ark 返回
  `404 ModelNotOpen`（账号 2130562826 未开通该模型）→ T10 E2E 在 P1 被阻断。

- **处置（用户批准，非静默切换）**：按用户指令「deepseek-v4-pro-ga-260813 用这个，以后都默认这个」，
  将内置默认对齐到运行时已实际使用的真实模型。改动仅 3 处源码默认值 + 1 处前端占位符：

  - `backend/core/config.py`：`LLM_MODEL` 默认 → `deepseek-v4-pro-ga-260813`

  - `backend/core/config_resolver.py`：`_DEFAULTS["LLM_MODEL"]` → `deepseek-v4-pro-ga-260813`

  - `backend/.env.example`：`LLM_MODEL=deepseek-v4-pro-ga-260813`

  - `frontend/src/pages/SystemPage.tsx`：LLM model 输入占位符 → `deepseek-v4-pro-ga-260813`

- 真模型 `doubao-seed-evolving` 未开通属于外部账号开通项；本批改走已开通的真实模型，不启用任何 mock/
  代理直替（ARK 计数代理仅转发真实 `chat/completions` 并落计数，不伪造响应）。

- 不打开 `CHALLENGE_OPEN`：模型替换由 Product Owner 明确授权，且为真实推理模型、真实产出，不属于
  mock/固定样张/职责转移；与本文件 §4.1 / [v2.1.0 §7.6 参考](RESULT.md) 的既有处理一致。

### 7.2 H2 clean onedir 重建身份

- 命令：前端 `npm run build`（`tsc -b && vite build`，69 modules）+ `python -m PyInstaller --noconfirm --clean packaging/resume_assistant.spec`，exit=0。

- 产物：`dist/ResumeAssistant/ResumeAssistant.exe`

  - **JD-60 对齐后的 H2 clean 重建身份（本批）**：SHA-256 `B2AB8E182B11A7F78E2375AA1364E7CD2FC7796BE9BB327E623FE12C3444AE01`；前端 bundle `index-8bEMCLmP.js` 内含 JD≥60 文案（`JD_MSG=60`/`JD_HINT=60` 抽样确认）。此前默认模型对齐重建的 EXE（`f1c05a4dc9…`）已被本次 JD-60 onedir 覆盖。

### 7.3 隔离真实模型 E2E（`scripts/h8_real_model_e2e.py`，隔离 temp runtime + onedir + 有头浏览器）

- **证据文件**：`validation-artifacts/h8/e2e/real_model_e2e.json`（此文件即时覆盖为本次成功运行）

- 通过项（关键）：

  - 隔离启动 /api/status 200（带 `ra_session` cookie）；迁移、导入 4 段经历、embedding 重建 10/10 VALID；ready=true。

  - **UI 真实驱动**：React 兼容填入 姓名+JD（`nameOk:true, jdLen:122`）→ 点击「生成岗位简历」→ `ui_chat_fired:true`（此前 fill 不进 React state 导致生成空转，已改成原生 value setter + input/change 事件并回读验证）。

  - **真实模型**：生成窗内 **19 次** **`POST /chat/completions`** **全部** **`status 200`**，`model=deepseek-v4-pro-ga-260813`，`response_format` 存在（temperature=0.0）；另 1 次 embedding。

  - **P1–P4**：P4 成品视图出现（含下载区），端到端（点击→chat→P4）约 112s（21:32:43→21:34:35）。

  - **viewer 同源（本批已解除** **`pdfjs-absent`** **弱项）**：PDF.js UI viewer 探针现返回 `viewer_ready:true, viewer_pages:1`（`.pdf-preview[data-state=ready]` + ≥1 `.pdf-page__canvas`），不再 `pdfjs-absent`；同源闭环 `pdf_viewer_same_source` 与 `pdf_viewer_same_source_final` 均 `same_source=true`：viewer 顶部 hash 文本 `ui_hash16=cbb2e52159e13728` 与下载 PDF sha 前 16 位 `cbb2e52159e13728…` 一致，证明 viewer 内嵌渲染与「下载 PDF」读的是**同一不可变 PDF artifact**（满足 PLAN §4.2/G04，不再以"下载成功"替代 viewer Gate）。

- **双下载字节一致**：Word `/api/template/download` 200（38,897 B）、PDF 200（4,228,060 B）；`word_download_eq_disk_docx=true`、`pdf_download_eq_disk_pdf=true`、`no_4xx_5xx=true`。说明：agent-browser `download` 命令在本受控环境未落盘副本（`saved_by_agent_browser:false`，页面内 in-page 探针 HTTP 200 且字节一致已断言）；VIEWER 同源以「viewport 探针捕获的 UI hash16 ⊇ session-下载 sha256 前 16 位」收口，不依赖 agent-browser 文件落盘。

- **隔离/干净**：无 WINWORD 泄露（before/after 均空）；结束时 `/api/health` 200；runtime 目录已清理（`runtime_deleted:true`）。

- **本批 JD-60 复核**：填充 nameOk:true、`jdLen=122`（≥60），生成按钮解除禁用，成功产出 —— 前端/后端 JD≥60 门槛在真实 onedir 路径验证通过。

### 7.4 T10 H2 冻结与 T11 结论（本 Revision 专属，不引用 Revision 1 证据）

- 冻结检查：工作区已清残余临时文件（`_tmp_retry_scope_proof.py`、根级 `package-lock.json` 均为本次开发临时物，已删除）；无开放 `CHALLENGE_OPEN`（全部引用为历史已关闭或规则定义）。

- **T10 开发侧成品**（本 Revision：模型默认对齐 + JD-60 + H2 clean 重建 + 隔离 onedir 真实模型 E2E + save\_draft 并发原子 upsert）。本轮在 JD-60 收口后完成：

  - **H2 clean onedir 重建**：`python -m PyInstaller --noconfirm --clean packaging/resume_assistant.spec`（仓库根 cwd），exit=0；EXE SHA-256 `B2AB8E182B11A7F78E2375AA1364E7CD2FC7796BE9BB327E623FE12C3444AE01`，前端 bundle 含 JD-60 文案。

  - **隔离 onedir 真实模型 E2E**：exit code **0**（`H8_EXIT=0`）；端到端点击→chat→P4 全通；19 次真实 `POST /chat/completions` 全 200（deepseek-v4-pro-ga-260813）；7 视口截图+DOM 断言全过；viewer 同源 `same_source=true`（见 §R2-7.3）。

#### R2-T11 Falsification Check（主动伪造，未发现新反例）

- **候选 1「JD 短输入能绕过生成」** → **已证伪（真实反例，已修复）**：对齐前前端 gate 为 30 字、后端 `freeze_input` 无下限（PLAN 要求 ≥60）。修复：前端两处升 60 字（[WorkbenchTaskContext.tsx](frontend/src/pages/workbench/WorkbenchTaskContext.tsx) validate、[StepIdentity.tsx](frontend/src/pages/workbench/StepIdentity.tsx) gate+hint），后端 `TaskService._require_jd` 作为 `freeze_input` 权威下限；断言：10 字拒绝（"JD 至少 60 字，当前 10 字"）、60 字放行、72 字放行（`python -c` 实测）；short 夹具全部抬到 ≥60 后 `_v22_t4` 27/27、`_v22_t5` 39/39、`_v22_t6` 23/23、`_v22_t9` 19/19 全过。未发现「仍能绕过 ≥60」的剩余开口。

- **候选 2「viewer 内嵌渲染无取证（pdfjs-absent）」** → **已证伪（真实反例，已修复）**：此前探针 `pdfjs-absent`，viewer 独立于下载取证。修复：探针改为等 `.pdf-preview[data-state=ready]` + ≥1 `.pdf-page__canvas`，实测 `viewer_ready:true, pages:1`；再以同源闭环确认 viewer hash 与下载 PDF sha 一致（`ui_hash16=cbb2e521…` ⊇ 下载 sha 前 16 位）。未再发现 viewer 与下载分叉。

- **候选 3「整页滚动/overflow 泄露」** → 未证伪（保持）：7 视口实测 `html/body overflow=0`、`overflow-y=hidden`，滚动仅限内部容器。

- **候选 4「失败后全局重放/不真实复用范围」** → **已证伪（真实反例，详见 §R2-5.3 操作证据）**：重试范围被限定为单逻辑调用 ≤3 attempt；任务级失败只复用已完成范围，不做全局重放。

#### 必做开发 Gate：结果与退出码（T10 收口现场重跑，非沿用 Revision 1）

| 门禁                  | 命令                                                                | 结果                               | 退出码 |
| ------------------- | ----------------------------------------------------------------- | -------------------------------- | --- |
| 后端语法                | `python -m compileall backend`                                    | PASS                             | 0   |
| 前端类型                | `frontend: npx tsc --noEmit -p tsconfig.json`                     | PASS                             | 0   |
| 前端构建                | `frontend: npm run build`（`tsc -b && vite build`，69 modules）      | SUCCESS                          | 0   |
| T04 SSE/恢复          | `backend/_v22_t4_sse.py`                                          | PASS（27/27）                      | 0   |
| T05 取消/新任务          | `backend/_v22_t5_cancel.py`                                       | PASS（39/39）                      | 0   |
| T06 生成/编排/重试        | `backend/_v22_t6_generation.py`                                   | PASS（23/23）                      | 0   |
| 清理门禁                | `backend/_v22_t9_cleanup.py`                                      | PASS（19/19）                      | 0   |
| H8 隔离 onedir 真实 E2E | `scripts/h8_real_model_e2e.py --exe dist/.../ResumeAssistant.exe` | PASS（19 chat 200，同源/viewport 全过） | 0   |

- 附加实操证据：JD≥60 判定阈值 `python -c`（拒绝/放行 3 例）与重试范围 4 例注入测试均退出码 0（证据文本见 §R2-5.3）。

#### Revision 2 专属交付清单

- [x] DS-003 工作台四步轨道与路由壳（T02，§R2-3.1）

- [x] 身份/JD 保存确认、dirty 边界与刷新恢复（T03，§R2-3.2）

- [x] P1/P2 逐项输出、历史阶段回看与缺口重取（T04，§R2-3.3）

- [x] P3 HTML 过程预览、完整 Fact、reason 旁侧与依据（T05，§R2-3.4）

- [x] P4 真实 PDF 切换、anchor、双下载（T06，§R2-3.5）

- [x] T07 我的经历/我的简历/个人与隐私映射（§R2-4）

- [x] T08 取消/新任务/失败面板/范围重试/ErrorBoundary（§R2-5）

- [x] T09 全视口/键盘/焦点/reduced-motion/滑动收口 + 7 视口 E2E 实证（§R2-6.3）

- [x] T10 模型默认对齐 + JD-60 + H2 clean 重建 + 隔离 real-model E2E + 同源（§R2-7）

- [x] **JD 校验对齐 60 字**（前端 gate×2 + 后端 `_require_jd` 权威，§R2-7.3 复核 + T 门禁全绿）

- **开发侧结论**：本 Revision 达到 `REV2_DEV_VERIFIED`（候选冻结语义）。全局文档（CURRENT\_STATE / README / docs/README / versions README / DECISIONS）由用户 / Document Agent 在 T10 人工验收通过后更新，开发侧不越权修改。

***

## R2-8. Revision 2 收口缺口处理（集中补齐，本 Revision 专属证据，不引用 Revision 1）

> 本节对应用户在 Revision 2 收口提出的 5 项缺口的集中处理。每项「用户结果 → 开发理解 → 实际交付
> → 可复核证据 → 偏差」均在下方映射表或对应小节中如实给出；未实现/需决策处显式标注阻断，不缩小范围。

### R2-8.1 R2 专属映射表（V220-G01~G06、R2-T01~T11，本 Revision 专属，不充数 §7.2）

| PLAN ID | 用户结果 | 开发理解 | 实际交付 | 可复核证据 | 偏差 |
| --- | --- | --- | --- | --- | --- |
| V220-G01 任务连续性 | 跨路由/刷新/重开恢复 | Task/InputRevision/Snapshot/Event + SSE 恢复协议 | task_repository/task_sse | §R2-3.2/3.3；`_v22_t4_sse.py` 27/27 | 无 |
| V220-G02 可恢复草稿+实际取消 | 姓名必填/后端确认/可取消停产；JD≥60 | 状态机+单活动+cancel 协议 + `TaskService._require_jd` 权威下限 | task_api/task_cancel；StepIdentity gate | §R2-3.2；`_v22_t3_task_api.py` 26/26、`_v22_t5_cancel.py` 39/39；JD-60 阈值 3 例 | 无 |
| V220-G03 四阶段渐进 | P1–P4 真实状态 + P3 HTML 过程预览 | generate_task 编排 + 事件流 + incremental commit | task_generation | §R2-3.3/3.4/3.5；`_v22_t6_generation.py` 23/23 | 无 |
| V220-G04 性能 | total 降 + 首 Fact≤15s | 真实模型 timing + 增量提交 | 见 §R2-8.4、§R2-10 | **6 格真实模型矩阵已完成**（§R2-10：18/18，首 Fact 中位数+最大值全部 ≤12.88s < 15s，满足门禁） | 无 |
| V220-G05 内容正确性 | 联系方式/技能/headline/教育；短输入宽容 | document_assembler/渲染修复 | docx 装配 | §R2-3.5；T7/T8 回归 | 无 |
| V220-G06 最终产物不变量 | DOCX 唯一真源 / PDF 同源 / viewer 同源 | real DOCX→Word→PDF 链 + viewer 取证 | docx_writer/隔离验证 | §R2-7.3 `same_source=true`、`ui_hash16=cbb2e521…` ⊇ 下载 sha 前 16 位 | 无 |
| V220-R2-T01 身份+Required Reading 复核 | Required Reading/假设台账 | §R2-1/§R2-2 | §R2-1/§R2-2 | §R2-1/§R2-2 | 无 |
| V220-R2-T02 DS-003 工作台壳 | 四步轨道 + 路由壳 | 工作台壳实现 | §R2-3.1 | §R2-3.1 | 无 |
| V220-R2-T03 身份/JD 保存确认 | 后端确认/dirty/刷新恢复 | task api/R2 校验对齐 60 | §R2-3.2 | `_v22_t3_task_api.py` 26/26 | 无 |
| V220-R2-T04 P1/P2 逐项+历史回看 | 逐项输出/缺料重取 | P1/P2 编排 | §R2-3.3 | `_v22_t4_sse.py` 27/27 | 无 |
| V220-R2-T05 P3 HTML 预览+Fact+reason | 过程预览/完整 Fact/依据 | P3 HTML + reason 旁侧 | §R2-3.4 | `_v22_t6_generation.py` 23/23 | 无 |
| V220-R2-T06 P4 真实 PDF+anchor+双下载 | PDF 切换/锚点/双下载 | P4 + 发布产物 | §R2-3.5 | 真实双下载 38,897B / 4,228,060B 字节一致 | 无 |
| V220-R2-T07 我的经历/简历/隐私 | 真实记录 + artifact | 记录列表查询 | **本批新增 records 端点**（§R2-8.2） | `_v22_t8_records.py` 12/12 | 无 |
| V220-R2-T08 取消/新任务/失败面板/范围重试 | 失败保留已完成、只重试失败范围 | 任务级 partial 保留 + 调用增量 | **本批新增 `_v22_range_retry_proof.py`**（§R2-8.3） | 10/10 | **同一任务「只重试失败范围」因 `TRANSITIONS[FAILED]=∅` 阻断**（§R2-8.3 决策，不静默缩小） |
| V220-R2-T09 视口/键盘/焦点/滑动收口 | 全视口可访问 | 7 视口收口 | §R2-6 | §R2-6.3 7 视口 E2E | 无 |
| V220-R2-T10 模型对齐+clean 重建+真实 E2E | 默认模型真实可用 | 默认值对齐 + 重建 + 隔离 E2E | §R2-7 | h8 真实 19 chat exit 0 | 无 |
| V220-R2-T11 Falsification+Gate 收口 | 反例证伪 + 交付清单 | 主动伪造 | §R2-7.4 + §R2-8 | Gate 全绿（§R2-8.5） | 无 |

### R2-8.2 缺口 2：我的简历真实记录列表（不再只展示当前任务）

- **实现**：新增只读列表端点 `GET /api/task/records`（[task.py](backend/api/routes/task.py)，声明在
  `GET /{task_id}` 之前避免路径参数捕获），`TaskRepository.list_records()` + `TaskService.list_records()`
  只返回 `SUCCEEDED` 且已发布 DOCX 原件的任务；[RecordsPage.tsx](frontend/src/pages/RecordsPage.tsx)
  改为拉取列表并按每条记录的 `published_docx_path / published_pdf_path` 渲染真实
  `/api/template/download` 下载链接（与工作台 P4 逐字同源），不再只展示当前任务、也不再伪造历史。
- **验证**（`_v22_t8_records.py`，TestClient 真实 HTTP 层）：**12 通过 / 0 失败**，exit=0。断言：
  [B1] 仅 SUCCEEDED+已发布进列表，失败/无产物任务不进；[B2] docx/pdf 发布引用真实可构造下载链接；
  [B3] 每条 name/jd_len 真实回读；[B4] 按发布时间降序；[B5] `GET /records` 不被 `/{task_id}` 捕获、
  `GET /api/task/{task_id}` 单独读取仍正常。
- **前端构建与入包**：`npm run build` exit=0；产物 bundle `index-DCtj5n8O.js`；打包后 bundle 含 `task/records`
  （`CONTAINS_RECORDS=True`），即正式 onedir 已具备该能力。
- **偏差**：无（此前仅声明展示当前任务的缺口已在本批范围内补齐）。

### R2-8.3 缺口 3：失败范围重试操作证据（`_v22_range_retry_proof.py`，10/10，exit=0）

- **实现**：在 [task_generation.py](backend/services/task_generation.py) P3 每个完成经历的
  `update_subtask(SUCCEEDED)` 后新增 `db.commit()`（约 L362-365），使已完成经历的子任务与 Fact 事件
  在整次运行后续失败时不会被 worker 的 `local.rollback()` 回滚，从而被持久化保留。
- **操作证据**（注入确定性 provider，exp-a 先完整完成并提交、exp-b 首 Fact 延迟 0.25s 后抛
  `ContentGenerationError`）：
  - **用户可见动作**：点击生成 → 任务 RUNNING；exp-b 失败 → 编排向上抛异常（非截断成功）→ worker 收尾 FAILED；
  - **状态变化**：exp-a 子任务 `SUCCEEDED`+`fact_results` 持久化保留（rollback 不影响）；exp-b 为
    `PENDING`/非 SUCCEEDED（无成功 artifact）；`TaskEvent` 保留 `fact.done` + `reason.delta`；
  - **调用增量**：只覆盖失败范围——compact×1、exp-a：fact+reason；exp-b：fact 调用发生但失败被拒，
    无额外成功产出。实测 `fact_calls=[fact(exp-a), fact(exp-b)]`、`reason_calls=[reason(exp-a/fa1)]`、
    `compact_calls=1`。
- **现状边界（需决策，不静默缩小范围）**：同一任务「只重试失败范围、不全任务静默重跑」因
  [core/task.py](backend/core/task.py) `TRANSITIONS[FAILED] = ∅`（FAILED 为终态）而**无法在同一任务上触发**
  ——本证明覆盖「失败后已完成范围保留 + 调用仅限失败范围」。若要【同任务直接续跑失败范围】需 P.O. 决策：
  - 选项 A：允许 `RUNNING → FAILED → RUNNING` 复用，且 generate_task 跳过 SUCCEEDED 子任务、复用其
    `fact_results`，只重跑未完成经历（改动状态机 + 增量提交门禁）；
  - 选项 B：维持 FAILED 终态，失败范围只能以「新任务 + 复用已完成 Fact」承载。
- **偏差**：同任务直接重试失败范围本身仍未实现（阻断于状态机终态语义），需用户/所有者以上任一决策。

### R2-8.4 缺口 4：Revision 2 最终包清单、真实模型时序与调用摘要

- **最终 onedir 包身份**（`python -m PyInstaller --noconfirm --clean packaging/resume_assistant.spec`，
  仓库根 cwd，exit=0，**本批重建含 records + JD-60 + 模型对齐**）：
  - 包路径：`dist/ResumeAssistant/`；EXE：`dist/ResumeAssistant/ResumeAssistant.exe`
  - 文件数：**4045**；总字节：**170,353,066 B**
  - **EXE SHA-256**：`FF05ECB85B6D1B64BF009937BFA24C58AB780440F67221B83B1395B05F9B9E04`
  - 前端 bundle：`index-DCtj5n8O.js`（646,862 B；含 `task/records` + JD-60 文案）
  - manifest：PyInstaller onedir，spec `packaging/resume_assistant.spec`，`name=ResumeAssistant`，
    `console=False`，`upx=False`，`excludes=["reportlab"]`。
  - 说明：以上为本批从当前源码候选重建后的实测计数，**未沿用 Revision 1 的 `4B134…` EXE**。
- **真实模型时序/调用/Token 摘要**：现有真实模型证据仅为 **1 次典型 warm run**（§R2-7.3 隔离 E2E：
  19 次真实 `POST /chat/completions` 全 200、`deepseek-v4-pro-ga-260813`、温度 0.0、另 1 次 embedding；
  端到端约 **112s**，P4 出现；首 Fact 时刻未单独记录）。
- **6 格真实模型矩阵（short/typical/long × cold/warm × n≥3）**：**已完成**（见 §R2-10）。

### R2-8.5 修订后的必做开发 Gate（本批收口现场重跑）

| 门禁 | 命令 | 结果 | 退出码 |
| --- | --- | --- | --- |
| 后端语法 | `python -m compileall backend` | **PASS**（本批修复 3 个遗留 GUARD 脚本的 `__future__` 位置，见下） | **0** |
| 前端类型+构建 | `frontend: npm run build`（`tsc -b && vite build`） | **SUCCESS**（69 modules；bundle `index-DCtj5n8O.js`） | **0** |
| T04 SSE/恢复 | `backend/_v22_t4_sse.py` | PASS（27/27） | 0 |
| T05 取消/新任务 | `backend/_v22_t5_cancel.py` | PASS（39/39） | 0 |
| T06 生成/编排/重试 | `backend/_v22_t6_generation.py` | PASS（23/23） | 0 |
| T03 Task API | `backend/_v22_t3_task_api.py` | PASS（26/26，R2 JD-60 对齐后重跑） | 0 |
| 记录列表（新增） | `backend/_v22_t8_records.py` | PASS（12/12） | 0 |
| 范围重试（新增） | `backend/_v22_range_retry_proof.py` | PASS（10/10） | 0 |
| T09 清理 | `backend/_v22_t9_cleanup.py` | PASS（19/19） | 0 |
| 打包 | `PyInstaller --clean packaging/resume_assistant.spec` | SUCCESS | 0 |

- 关于 `compileall`：**此前 RESULT 记载编译 PASS，但现场实测 exit=1**，根因为 3 个遗留 GUARD 脚本
  （`_v13_validation.py` / `_e2e_v13_full.py` / `_v14_t3_migrate.py`）把 `from __future__ import annotations`
  放在 `sys.exit(0)` 之后，属死代码但触发 SyntaxError。本批已删除这 3 处死行（不改逻辑，脚本仍立即
  GUARD 退出），`compileall` 恢复 exit=0。此 3 文件不入打包图，不影响包身份。

### R2-8.6 缺口 5：提交身份澄清（H2 与 RESULT-only 提交）

- **源码候选 H2 = `106bd810c3c42cd51c6369aff02bb33e2d6d9450`**（feat），唯一父提交 `47ae33e`（批准基线
  H），相对 H diff：**31 files / 4282 insertions / 137 deletions**；该 tree 为冻结源码树（含模型对齐 +
  JD-60 + 真实模型 E2E 等 R2 全部源码/验证脚本/证据）。
- **`3d7eb22`（docs）仅为本文件顶部身份块内容更正**（把 H2 身份字段从旧的 `2af905b+4268` 修正为
  `106bd81+4282`），**不改变冻结源码树，故不是独立验收的源码候选**。
- **为何 `106bd81` 内仍含旧身份字段（2af905b/4268）**：H2 提交内的 RESULT 身份块是在 amend 之前的
  H2 原始哈希/尺寸下写就的；amend 改写了 hex1 与 diff 尺寸但**未同步改写嵌入的 RESULT 身份块**，因此
  该旧文本留存在 `106bd81` 的冻结文档里。`3d7eb22` 通过独立 docs 提交仅修正该身份块。
- **PLAN blob**：`docs/versions/v2.2.0/PLAN.md` = `e134703ce6e37a2f4d5df389662119f38638fae8`（PLAN
  Revision 2 未变更）。
- **新 clean 候选（本批）**：见下一节 R2-9。

### R2-8.7 剩余偏差与阻断（交付边界，如实上报）

- 范围内已补齐：records 列表（12/12）、任务级 partial 保留 + 失败范围（10/10）、compileall=0、
  包重建 manifest、映射表。
- 需决策/待独立验收（不静默缩小）：**同一任务直接重试失败范围**（状态机终态，§R2-8.3 选项 A/B —— 本批以
  **用户可操作的"只重试失败范围"续试任务**收口，见 §R2-10），**6 格真实模型矩阵**（§R2-8.4 —— 本批已完成，
  见 §R2-10）；最终顶部全局文档由用户/Doc Agent 在人工验收后更新。

## R2-9. 本批新 clean 候选（gap 处理后提交）

- **HEAD / 源码候选**：`58ab85dff987dfd52ae36361d67ac06f165c9215`（fix：close Revision 2 gaps）
- **唯一父提交**：`3d7eb22`（docs：RESULT 顶部身份更正，仅文档；其下源码基线即 H2 `106bd81`）
- **相对批准基线 H（`47ae33e`）的 diff**：**40 files, 4894 insertions(+), 148 deletions(-)**
- **PLAN blob**：`docs/versions/v2.2.0/PLAN.md` = `e134703ce6e37a2f4d5df389662119f38638fae8`（Revision 2 未变）
- **最终包身份**：onedir `dist/ResumeAssistant/`（4045 files / 170,353,066 B）；EXE SHA-256
  `FF05ECB85B6D1B64BF009937BFA24C58AB780440F67221B83B1395B05F9B9E04`；前端 bundle
  `index-DCtj5n8O.js`（含 `task/records` + JD-60 文案）。
- 顶部状态：`REV2_DEV_VERIFIED`（候选冻结语义，非独立验收）。提交说明见 §R2-8。

## R2-10. H3 开发侧收口（DOC_RETURNED 后，两项开发 Gate 完成）

> 背景：H3（`58ab85d`）被以 `DOC_RETURNED` 退回开发侧，要求补两项**开发 Gate**（不进入独立验收、不改全局
> 文档及 PLAN）。本节为两项收口的开发侧结果与证据。候选已更新，详见 R2-11。

### R2-10.1 收口一：用户可操作的"只重试失败范围"续试任务

- **需求**（源自 §R2-8.3 选项 A/B）：状态机保持 `FAILED` 为终态，不沿用源 task_id，新建承载续试的任务；
  **已完成子任务的 fact_results 被复用、不重复计费**；实际发起模型调用仅落在失败范围内。
- **实现**：
  - `backend/services/task_generation.py`：`generate_task(..., preload)`，P2 命中即复用经历 id 子任务置
    SUCCEEDED，P3 先并入 reused、其余进 todo worker；`_reuse_experience` 复原 `GeneratedFact`。
  - `backend/services/task_service.py`：`continue_failed_scope(source_task_id)` —— 校验源 FAILED → 读 SUCCEEDED
    子任务为 `succeeded` 复用 + `incomplete` 失败范围 → 从源 snapshot 恢复 selected_slots 与冻结 InputRevision →
    `create_task`+`save_draft`+`freeze_input`+`start_task` 新建续试任务 → `_scope_selector` 按源选材重建 →
    `run_generation(tid, select_scope, preload=succeeded)`。
  - `backend/api/routes/task.py`：新增 `POST /{task_id}/continue`。
  - 前端：`endpoints.ts` 的 `taskApi.continue`、`WorkbenchTaskContext.continueScope()`、`WorkbenchPage` FAILED
    面板「续试失败范围 ›」按钮（生成中 disabled）。
- **操作证据**：`backend/_v22_continue_scope_proof.py` → **11/11 PASS, exit 0**；关键断言：
  - 源任务 FAILED 终态；续试用**新 task_id**；
  - 续试 exp-a fact_results 与源任务**逐字一致**（已完成结果被复用）；
  - 续试实际调用增量仅 `['compact(jd)','fact(exp-b)','reason(exp-b/fb1)','fact(exp-b)','reason(exp-b/fb2)']`，
    **已完成 exp-a 零调用**（不重复计费）；
  - 源任务保持 FAILED（未改写）。

### R2-10.2 收口二：六格真实模型性能矩阵（short/typical/long × cold/warm × n≥3）

- **运行入口**：`backend/_v22_sixgrid_run.py`（从 credential manager 注入真实 ARK Key）；
  单格脚本 `backend/_e2e_v22_matrix.py`；cold 每样本独立子进程 `--n 1`、warm 单进程 `--n 3`（规避 engine
  单例引发的 cold 多样本 UNIQUE 冲突）。
- **模型**：`deepseek-v4-pro-ga-260813`（真实模型，credential-manager key）。
- **结果**：**18/18 SUCCEEDED**，证据 `docs/versions/v2.2.0/evidence/r2_real_model_matrix.json`
  （本轮含调用遥测重跑；elapsed **674.1s**；`backend/_v22_sixgrid_run.py` **实际退出码 = 0**，命令级
  `$LASTEXITCODE` 捕获 `SIXGRID_EXIT=0 failures=0`）。首完整 Fact 中位数+最大值（单调时钟，秒）：

  | cell | n | first_fact median | first_fact max | total median | total max |
  | --- | --- | --- | --- | --- | --- |
  | short/cold | 3 | 5.44 | 9.49 | 18.88 | 25.52 |
  | short/warm | 3 | 5.60 | 5.87 | 19.09 | 19.17 |
  | typical/cold | 3 | 6.50 | 7.00 | 30.15 | 31.14 |
  | typical/warm | 3 | 6.64 | 7.42 | 29.95 | 32.34 |
  | long/cold | 3 | 6.68 | 7.05 | 38.58 | 41.00 |
  | long/warm | 3 | 6.46 | 6.75 | 37.18 | 37.66 |

- **门禁判定**：全部 18 样本首 Fact **max ≤ 9.49s < 15s**，满足 **V220-G04** 首 Fact≤15s 门禁（不再以
  §7.6 旧矩阵或 §R2-7.3 单次典型 run 充数；§R2-8.4 标记已更新为完成）。

- **四格有基线格（typical/long × cold/warm）总耗时降幅与 ≥25% 判定**（降幅 = 1 − 本轮中位数/V2.1.0
  同格基线中位数；V2.1.0 基线取自 §6.2 表，V2.2 上限 75% = 基线×0.75）：

  | cell | 本轮 total 中位数（s） | V2.1.0 基线（s） | V2.2 上限 75%（s） | 降幅 | 判定 |
  | --- | --- | --- | --- | --- | --- |
  | typical/cold | 30.15 | 89.49 | 67.12 | 1 − 30.15/89.49 ≈ **66.3%** | **≥25% ✓**（≤上限 ✓） |
  | typical/warm | 29.95 | 84.48 | 63.36 | 1 − 29.95/84.48 ≈ **64.5%** | **≥25% ✓**（≤上限 ✓） |
  | long/cold | 38.58 | 94.32 | 70.74 | 1 − 38.58/94.32 ≈ **59.1%** | **≥25% ✓**（≤上限 ✓） |
  | long/warm | 37.18 | 97.92 | 73.44 | 1 − 37.18/97.92 ≈ **62.0%** | **≥25% ✓**（≤上限 ✓） |

  → **4/4 有基线格中位数均 ≤ 基线上限 75% 且 ≥25% 降低**，满足 PLAN §V220-G04 的 total 门禁。
  short 两格（无基线格）绝对总耗时 18.88/19.09s，全部 SUCCEEDED。

- **调用遥测摘要**（`_e2e_v22_matrix.py` 在验证脚本内包裹 `invoke_observed_json` / `build_task_llm` /
  `_embed_text` 采集；**全部为实测**，证据 JSON 每样本含 `telemetry` 块，**无"未采集"**）：
  - **逻辑调用数**：每样本 `logical_calls`（short=5、typical=15、long=21）均等于 **1 + 2F**
    （compact_jd×1 + fact×F + reason×F；F=short 2 / typical 7 / long 10），
    `logical_calls_eq_1_plus_2F=true` **18/18**。
  - **HTTP attempt**：每逻辑调用 `attempts` 均 **=1**（全部首试成功），`attempts_all_le_3=true` **18/18**；
    `attempts_done`（实际收到响应的 attempt）与 `attempts` 一致。
  - **重试**：`retry_reasons` **全部为空数组**（无重试）；`no_retry_after_success=true`（结构上
    `retry_reasons` 只在失败 attempt 追加、成功即返回，故终末成功 attempt 上不可能记录重试）**18/18**。
  - **Embedding**：每样本 `embedding_calls=1`（18/18，`embedding_in_0_or_1=true`），对应任务级在线
    JD 向量单次查询；种子/重建阶段 embedding 已复位不计入。
  - **Token（用法实测 + 请求侧上限证明）**：
    - **实测**：Ark 响应含 usage，`usage_available=true`（18/18 全部调用），每调用记录
      `prompt_tokens`/`completion_tokens`/`total_tokens`；单任务实测 completion 合计
      **short ≤421 / typical ≤1307 / long ≤1778 token**，均 **≤ 16k**（`completion_le_16k=true` 18/18）。
    - **配置上限证明（非 resp_bytes 推算）**：每逻辑调用请求侧 completion 上限固定为
      `compact_jd=1024 / fact=800 / reason=256`（`completion_token_cap_per_call` 逐调用记录），
      `completion_token_request_caps` 按上限值计数；单任务 completion ≤16k 亦由
      `TaskTokenBudget.reserve/refund`（`TASK_LLM_COMPLETION_LIMIT=16*1024`）+ 各调用上限之和证明，
      与实测一致。未用 resp_bytes 折算 Token。

### R2-10.3 收口二（续）：新候选 clean 源码重建 onedir + 真实模型 E2E

- **重建**：当前候选的源码父 `b70d6e6`（含续试收口，HEAD `0cc444e` 另含六格运行脚本+证据）clean 源码 →
  前端 `npm run build` → `python -m PyInstaller --noconfirm --clean packaging/resume_assistant.spec`，exit=0。
- **新包身份**：`dist/ResumeAssistant/`（**4045 files / 170,356,413 B**）；EXE SHA-256
  `9E6DF063E6056E78 47A6FF78F4207BD9 03CD4A23CA97ACB4 0EF0D56841FAF9C6`；前端 bundle `index-BrAu-oeZ.js`。
- **真实模型 E2E**（`scripts/h8_real_model_e2e.py --exe dist\ResumeAssistant\ResumeAssistant.exe`，隔离 runtime）：
  - **实际退出码 = 0（补采实测，命令级 `$LASTEXITCODE` 捕获；非脚本成功分支推断）**：本 RESULT 首版曾据
    `main()` 成功路径推断为 0，后按 DOC_RETURNED 要求补采，实际运行
    `python scripts\h8_real_model_e2e.py --exe dist\ResumeAssistant\ResumeAssistant.exe` 捕获
    `REAL_E2E_EXIT=0`，证据以 `validation-artifacts/h8/e2e/real_model_e2e.json` 为准。
  - 生成窗口 **19 次真实 `POST /chat/completions` + 1 次 embedding 均 200**（deepseek-v4-pro-ga-260813，温度 0.0）；
  - viewer 同源 **`pdf_viewer_same_source.same_source=true`**，`ui_hash16=`download_pdf 前16位
    =`f97054e95001ea84`（viewer 渲染 PDF 与下载 PDF 同源；取自本次补采后 `real_model_e2e.json` 实测）;
  - 双下载一致：`word_download_eq_disk_docx=true`、`pdf_download_eq_disk_pdf=true`、`no_4xx_5xx=true`;
  - **7 视口** DOM 断言 + 截图全过：`docOv=0, bodyOv=0, pdf=ready, dlLinks=2`；
  - `winword` 无泄漏；`http_health_final=200`。
  - 产物：`validation-artifacts/h8/e2e/real_model_e2e.json`。

#### R2-10.4 新候选必做开发 Gate 最终 PASS / 退出码（本轮收口后复跑）

| 门禁 | 命令 | 结果 | 退出码 |
| --- | --- | --- | --- |
| 后端语法 | `python -m compileall backend` | PASS | **0** |
| 续试（只重试失败范围） | `backend/_v22_continue_scope_proof.py` | PASS（**11/11**） | **0** |
| Task API | `backend/_v22_t3_task_api.py` | PASS（26/26） | 0 |
| 记录列表 | `backend/_v22_t8_records.py` | PASS（12/12） | 0 |
| 范围重试 | `backend/_v22_range_retry_proof.py` | PASS（10/10） | 0 |
| 六格真实模型矩阵 | `backend/_v22_sixgrid_run.py` | PASS（**18/18**） | **0** |
| onedir 重建 | `python -m PyInstaller --clean packaging/resume_assistant.spec` | SUCCESS | 0 |
| 真实模型 E2E | `scripts/h8_real_model_e2e.py --exe dist\ResumeAssistant\ResumeAssistant.exe` | PASS（viewer 同源 + 双下载 + 7 视口） | **0** |

以上为新候选 `0cc444e`（源码父 `b70d6e6`）clean 源码确定性复跑的最终结果，**非旧候选证据充数**。

## R2-11. 收口后唯一冻结候选（§R2-10 两项收口提交）

- **本轮唯一冻结候选 = HEAD `0cc444e`**：`docs(v2.2.0): record H3 dev-side closure - six-grid real-model matrix + rebuilt onedir E2E`
  （含全部源码收口 + 六格矩阵运行脚本 `_v22_sixgrid_run.py` + 证据 JSON + 本 RESULT）。
- **源码候选（其父）**：`b70d6e6 feat(v2.2.0): user-operable failed-scope continuation task (reuse done, retry only failed) + proof`
  （续试收口实现）。
- **唯一父提交**：`0cc444e` 的 parent = `b70d6e6`（`git cat-file` 仅 1 条 parent）。
- **相对批准基线 H（`47ae33e`）的完整 diff**：**43 files changed, 5785 insertions(+), 162 deletions(-)**
  （`47ae33e`→`0cc444e` 实测 `git diff --shortstat`）。
- **PLAN blob**：`docs/versions/v2.2.0/PLAN.md` = `e134703ce6e37a2f4d5df389662119f38638fae8`（Revision 2 未变）。
- **最终包身份**：onedir `dist/ResumeAssistant/`（**4045 files / 170,356,413 B**）；EXE SHA-256
  `9E6DF063E6056E78 47A6FF78F4207BD9 03CD4A23CA97ACB4 0EF0D56841FAF9C6`；前端 bundle `index-BrAu-oeZ.js`。
- 顶部状态：`REV2_DEV_VERIFIED`（候选冻结语义，非独立验收，不宣称 DOC_ALIGNED / 独立验收通过 / 可发布）。
  交付只报开发侧结果与证据。

