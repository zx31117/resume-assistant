# V2.2.0 RESULT：执行记录

> 文档角色：V2.2.0 Development Agent 执行记录（开发候选冻结前由开发维护实施、自测与偏差）
> 当前状态：**待验收** — `BATCH1_DEV_VERIFIED`
> 当前阶段：Revision 1 / 第一批（仅设计无关后端实现）
> 产品基线：annotated tag `v2.1.0` → `5d72a2e08ebd4fa416b4b1dcdd79c1d08dfc7cfd`
> 开发路径：`<current-workspace>` 分支 `version/v2.2.0`
> 批准 PLAN：Revision 1，blob `324302a0ef6d81214c752d12281c221f2550f320`（VH-010 记录）
> 语义交接：**DOC\_RETURNED**（开发侧 RESULT 被退回返工；本版为返工处置结果）

> **本文件由 Development Agent 在候选冻结前写实施、自测与偏差。** Revision 1 全部开发 Gate 已
> 收口为 PASS，`BATCH1_DEV_VERIFIED` = **开发侧 T01–T11 全部完成（候选冻结）**，不代表独立
> 验收/可发布：独立 Acceptance 由用户 / Doc Agent 在适当时机另启，本批不进入也不替代。T10 是
> 开发侧 Architecture Check（只读核对产品
> 不变量是否在真实路径成立），**不存在“用户 / Doc Agent 手动 T10”**；Revision 1 完成或本批
> 返工完成后也不进入独立验收。全局文档（CURRENT\_STATE / docs/README / README / DECISIONS）
> 由用户 / Doc Agent 在适当时机更新，本批不触碰，也不把任何返工过程文档升级为事实真源。

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

