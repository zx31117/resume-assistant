# ResumeAssistant V2.2.0 PLAN

> Plan Revision：1  
> Supersedes：无；由 V2.2.0 DRAFT 范围基线转入  
> 状态：已批准
> 日期：2026-09-13  
> 产品源码基线：annotated tag `v2.1.0` → `5d72a2e08ebd4fa416b4b1dcdd79c1d08dfc7cfd`  
> 开发路径：`<current-workspace>` 的 `version/v2.2.0`  
> 本 Revision 授权：第一批、仅设计无关实现  
> Design Baseline：无；Design Gate 关闭  
> 批准 commit / PLAN blob：见同目录 `HISTORY.md` 的 VH-010；本次状态变更不改变已批准的产品合同

## Required Reading（Development Agent 必读）

按以下顺序读取，读完后在 RESULT 的身份区逐项确认；缺一项不得开始实现：

1. `docs/README.md` §0、§1～§5；
2. `docs/CURRENT_STATE.md`；
3. 本 PLAN 全文；
4. `docs/HUMAN_AI_WORKFLOW.md` §3.1（权限）、§3.2（PLAN/候选）、§3.4（强制反思与
   Architecture Challenge）、§6（开发职责）、§11（上下文控制）。

本 Revision 没有 Design Baseline，不读取 Design Agent 的工作稿。无需默认读取 DRAFT、HISTORY、
完整 DECISIONS 或历史 RESULT；只有本 PLAN 明确点名时才定向读取。

## 0. 合同性质

本文件是 V2.2.0 当前唯一可执行开发合同。Revision 1 只授权不依赖最终 Design Snapshot 的数据、
后端、协议、生成、性能、内容模型、DOCX/PDF 和测试工作；不得读取或猜测 Design Agent 的
`current/` 或未批准快照，不得实现新的可见布局、文案、动效和响应式。

Design Snapshot 获批后，Documentation Agent 将形成完整 Revision 2，`Supersedes` 本 Revision，
导入并绑定 `DS-xxx`，再授权前端可见交互、生成中 HTML 预览和最终集成。两批由同一 Development
Integrator 连续负责，不记为返工；Revision 1 不产生可发布 V2.2.0 候选，也不启动独立 Acceptance。

如果真实实现证据否定本文件的技术路线，必须按
`docs/HUMAN_AI_WORKFLOW.md` §3.4 发起 Architecture Challenge。目标导向冻结允许在本文件明确
授权的参数区间内调整实现，但不允许静默降低用户结果、扩大调用/成本或改变 Design Gate。

## 1. 用户结果

### V220-G01 任务连续性

一次工作台任务使用稳定 `task_id + input_revision`。在后端仍运行的前提下，应用内路由切换、
浏览器刷新和页面重开后，能够恢复已保存身份/JD、当前真实阶段、已完成业务结果、历史阶段、
失败/取消状态和最终结果。SSE 重连不得重复模型调用。

关闭整个应用/后端、应用崩溃、系统重启或关机后的未完成任务续跑不属于 V2.2.0。

### V220-G02 可恢复草稿与实际取消

- 姓名必填；电话、邮箱、所在地选填；JD 与身份摘要保存到后端临时任务；
- 每个新任务重新填写，不从上一任务、Career Memory、模板、JD 或 AI 自动回填；
- 保存状态必须来自后端确认，不能只显示前端假状态；
- 取消必须停止本产品可控的排队、Provider 流读取、事件发布、Word worker 和 artifact 发布；
- revision fence 拒绝旧任务迟到结果；释放本地活动槽后允许立即开始新任务；
- 第三方 Provider 已接收请求后的内部计算或计费不承诺能够撤销。

### V220-G03 四阶段渐进结果

- P1：逐项提供已完整解析、校验的 JD 业务条目；
- P2：逐项提供入选 Experience/Fact 以及面向用户的匹配依据；
- P3：每条 `headline + body + fact_refs` 完整校验后整条进入结果快照；随后在旁侧对同一
  `fact_id` 流式输出选择理由；
- P4：提供 DOCX 装配、Word→PDF、锚点和 artifact 发布的真实状态；
- 历史阶段可以回看最终业务结果，但不回放字符动画，不保存或展示模型私有思维链。

### V220-G04 性能

- 用户提交后真实状态反馈不晚于 1 秒；
- 固定代表性样例从“点击生成”计时，首个完整 Fact 的 `n >= 3` 中位数和最大值均不晚于 15 秒；
- 同一短/典型/长及 cold/warm 样例的成功总耗时中位数相对 V2.1.0 至少降低 25%；
- V2.1.0 的短样例 `TemplateRenderer.render` 错误必须修复；短样例无成功基线，因此只要求最终
  正确性与绝对耗时记录，不伪造降低比例；
- 不得通过减少事实校验、删除合法内容、更换低质量模型或移动计时起点达标。

V2.1.0 对照基线：

| 样例 | n | 中位数 | 最大值 | V2.2 中位数上限 |
|---|---:|---:|---:|---:|
| typical cold | 5 | 89.49s | 111.21s | 67.12s |
| typical warm | 4 | 84.48s | 105.78s | 63.36s |
| long cold | 4 | 94.32s | 122.82s | 70.74s |
| long warm | 3 | 97.92s | 125.24s | 73.44s |
| short cold/warm | 4/3 | 全部 TemplateError | 不适用 | 先达到成功 |

统计只报告样本数、中位数和最大值；小样本不报告 P95。

### V220-G05 内容正确性

- 已填写的姓名、电话、邮箱和所在地必须确定性进入 ResumeDocument、DOCX、同源 PDF、viewer 与下载；
- 技能区生成 2～4 个与 JD 相关、有 Fact 依据、可扫读的能力类别；事实不足时宁可减少类别，不得
  用内部实现词或关键词堆砌补数；
- 每条润色 Fact 使用结构化 `headline + body`；只加粗简短标题及冒号，正文保持普通字重；
- `headline / body / skills / reason` 均保留可核验的 `fact_refs`，且不回写 Career Memory；
- 教育的学校、专业、学历与时间保持独立语义；专业在外、学历在括号内，缺任一字段时不输出空括号，
  禁止字段倒置、重复括号和 `本科（）`；
- 短、长、中文/英文/数字混排和临界换行不能造成字段丢失或合法短输入渲染失败。

### V220-G06 最终产物不变量

DOCX 继续是唯一排版真源；PDF 只由同一 DOCX 经 Microsoft Word COM 转换；PDF.js viewer 与 PDF
下载读取同一不可变 artifact。不得恢复 ReportLab/手绘 PDF 或把过程 HTML 预览升级为第二产物真源。
Word/PDF 任一失败必须 fail closed，保留仍有效的独立下载，不得把残缺 artifact 标为成功。

## 2. 冻结技术路线

### 2.1 流程与并发

```text
冻结 InputRevision
├─ P1 紧凑 JD 结构化
└─ P2 可提前执行的本地索引/候选准备
   ↓ P1 结果与 P2 候选汇合
按 Experience 分组，最多 2 个经历并发
└─ 同一经历内按 Fact 串行
   ├─ Fact 结构化流：experience_id + fact_id + headline + body + fact_refs
   └─ Reason 文本流：协议层绑定同一 fact_id
全部经历按冻结顺序合并
→ ResumeDocument → DOCX → Word COM PDF → anchors/artifact
```

“单次复杂结构化流同时输出 Fact 与 reason”标记为 `REJECTED`：开发前真实证据只有 1/3 稳定
绑定，且 reason 不满足旁侧逐字语义，不得重新作为默认路线。

并发边界是 Experience，不是单 Fact。同一 Experience 内的 Fact 串行，共享上下文；跨 Experience
最大并发固定为 2。完成顺序不得改变最终模板顺序或把 reason 绑定到其他 Fact。

### 2.2 模型、调用与 Token

- 默认模型：`deepseek-v4-pro-ga-260813`；
- Endpoint：Ark 北京；
- `temperature=0`、`response_format=json_object`、`reasoning_effort=minimal`；
- JD 结构化输出默认 1024 completion tokens；开发可在 512～2048 内依据边界测试调整；
- Fact 每次 HTTP attempt 最多 800 completion tokens；
- reason 每次 HTTP attempt 最多 256 completion tokens；
- 每任务所有 LLM completion tokens 合计最多 16k；即将超限时不得启动新的 Fact/reason 调用，
  以明确失败或容量不足状态结束，不返回截断成功；
- 原始 JD 不受“1024 输出上限”限制，按冻结 InputRevision 原文保存；若整个输入记录超过状态硬
  上限，返回明确 413/领域错误和实际限制，不得静默截断；
- 令 `F` 为最终准备生成的 Fact 数量，正常 LLM 逻辑调用为 `1 + 2F`：一次 JD、每 Fact 一次
  Fact 调用和一次 reason 调用。Experience 数量记为 `E`，并发上限为 `min(E, 2)`；
- Embedding 单独计数；同一 `input_revision` 最多一次在线 JD 查询向量调用，已有 Fact embedding
  必须复用，不得因 SSE 重连或 Fact/reason 阶段重复计算；
- 单个逻辑调用最多重试 2 次，即最多 3 个 HTTP attempt。逻辑调用、HTTP attempt、重试原因、
  prompt/completion/reasoning tokens 分开记录；
- 人民币成本不可得时记录为 unavailable，以调用与 Token 作为本版本成本门禁，不伪造金额。

JD 默认值在 512～2048 内调整不产生 PLAN Revision，但 RESULT 必须记录最终值与边界证据。超出
区间、增加正常逻辑调用公式、提高 16k 总预算、改变模型或降低性能/正确性目标必须进入 Challenge。

### 2.3 Task、快照与事件

后端是任务状态真源。实现可以在不改变语义的前提下调整表拆分，但至少保存：

- `Task(task_id, status, current_input_revision, active_operation_id, created_at, updated_at, expires_at)`；
- 不可变 `InputRevision`：姓名、电话、邮箱、所在地、完整 JD、输入 hash；
- Experience 子任务状态、冻结顺序、Fact 结果和失败；
- 覆盖式 `display_snapshot`：当前可恢复的 P1～P4 业务结果、reason 当前完整文本、当前阶段；
- 单调 `seq`、终态、错误和已发布 ResumeRevision/artifact 引用。

状态至少为 `DRAFT / READY / RUNNING / CANCELLING / SUCCEEDED / FAILED / CANCELLED`。一次本地
profile 只允许一个前台活动任务；开始新任务不允许旧 task/revision 再写入当前结果。

SSE 事件必须包含 `task_id / input_revision / seq / type / phase / payload`。业务完成事件与权威
快照持久化；字符/token delta 不逐条写数据库。客户端首次进入或重连先读取权威快照，再订阅后续
序号；重复 seq 幂等忽略，出现缺口、服务端环形缓冲过期或 artifact 身份变化时重取快照，禁止自行
拼接猜测。快照刷新须限频并受容量约束，但刷新间隔属于实现细节。

### 2.4 容量、保留与清理

- 单任务状态记录硬上限 256 KiB；
- 单任务事件与 display snapshot 合计硬上限 256 KiB；
- 一次 profile 只允许一个 `RUNNING/CANCELLING` 前台任务；
- 最多保留 20 条终态或孤立临时记录，artifact 正文之外的临时状态总量最多 16 MiB；
- 当前 `DRAFT/READY/RUNNING/CANCELLING`、当前页面引用、当前 ResumeRevision 及其 DOCX/PDF
  不得清理；
- 未提交孤立草稿及 `FAILED/CANCELLED` 保留 24 小时；
- `SUCCEEDED` 工作台状态保留到用户开始新任务；已发布简历及 DOCX/PDF 保留到用户主动删除；
- 页面离开只保存状态并断开 SSE，不触发删除；
- 清理只在应用启动、任务进入终态和超过记录/字节阈值时扫描；cleanup 必须幂等、限定 runtime
  data root，失败可见，不得误删活动任务、已发布 artifact 或相邻文件。

## 3. Revision 1 允许与禁止范围

### 3.1 允许

- SQLite schema/migration、task repository、application service、API 与领域错误；
- Provider 流适配、结构化增量解析、reason 文本流、调用/Token/时间观测；
- Experience 级调度、取消、revision fence、资源清理；
- 权威快照、SSE 序号与恢复协议；
- ResumeDocument/Builder/模板字段映射、技能与 Fact 输出结构、短输入 Renderer 修复；
- DOCX→Word COM→PDF→viewer/download 既有链的后端回归；
- 不产生新可见结果的 TypeScript API 类型和 client 适配；
- fixture、测试 runner、precheck、打包依赖与文档 RESULT。

### 3.2 禁止

- 修改导航、页面布局、卡片、可见文案、颜色、字号、间距、动画和响应式；
- 实现生成中 HTML 简历预览、理由旁栏的具体视觉或最终 PDF 切换布局；
- 读取或实现 Design Agent 的 `current/`、`D-003` 或其他未批准快照；
- 多 Development Agent 并行修改产品源码；
- 登录、多用户、PostgreSQL、对象存储、分布式队列、跨设备/后端重启恢复；
- 同时运行多个前台任务、并发 3、单 Fact 并发或全简历额外统一润色；
- Profile 持久化、身份自动回填、简历上传查重/OCR、Fact 锁定或单 Fact 重新生成；
- 新模板、任意 Word 模板解析、ReportLab PDF 回退、自动全局字体/行距/字距排版。

触碰禁止范围时停止并报告，不以“便于联调”扩大 Revision 1。

## 4. 开发任务与依赖

| ID | 开发结果 | 关键依赖 | 完成证据 |
|---|---|---|---|
| V220-R1-T01 | 身份/基线核对；完成版本 Pre-mortem 和假设台账 | 无 | commit/blob/clean；三个失败模式、探针、停止点 |
| V220-R1-T02 | Task/InputRevision/子任务/快照 schema、migration 与 repository | T01 | 迁移正反向、幂等、旧库升级、容量边界 |
| V220-R1-T03 | Task API、保存确认、单活动任务和恢复快照 | T02 | 创建/保存/刷新/重连/终态矩阵 |
| V220-R1-T04 | SSE seq、去重、缺口重取、断线恢复与 artifact 身份 | T02-T03 | 重复/乱序/缺口/缓冲过期/重连不增调用 |
| V220-R1-T05 | 实际取消、Provider/worker 清理和 revision fence | T03-T04 | P1-P4 取消、迟到结果、立即新任务、无泄漏 |
| V220-R1-T06 | 紧凑 JD、Fact＋reason 两阶段、经历并发 2、调用/Token 门禁 | T03-T05 | typed/binding/顺序/并发/重试/超限/真实模型 |
| V220-R1-T07 | 联系方式、技能、headline/body/fact_refs、教育字段修正 | T06 | 数据链与 DOCX/PDF 三端内容对照 |
| V220-R1-T08 | 修复合法短输入 TemplateError，不改变事实/模板真源 | T07 | short cold/warm 成功；原失败可复现对照 |
| V220-R1-T09 | 容量/保留/cleanup 与并发故障恢复 | T02-T08 | 20条/16MiB、保护对象、失败/幂等/越界 |
| V220-R1-T10 | 首条真实纵切后的 Architecture Check | T02-T09 的最小纵切 | 只读 Challenge 记录；双真源/代理指标检查 |
| V220-R1-T11 | 完整开发 Gate、冻结前 Falsification Check、RESULT | T01-T10 | 全部门禁 PASS、clean 第一批 checkpoint |

T10 未完成前不得继续铺开所有路径；发现 `CHALLENGE_OPEN` 时暂停受影响任务。T11 只形成可供
Revision 2 继续的 clean 开发 checkpoint，不构成 V2.2.0 发布候选或独立验收 PASS。

## 5. 风险预案与假设台账

| ID | 状态 | 风险/判断 | 最小反证与处置 |
|---|---|---|---|
| A01 | EVIDENCED | minimal 可稳定输出绑定 Fact | 最终实现 3+3+3 边界重跑；失败则 Challenge 模型/协议 |
| A02 | REJECTED | 单复杂流能同时稳定绑定 Fact/reason | 禁止采用；不得用局部 1/3 PASS 恢复 |
| A03 | EVIDENCED | 紧凑 JD＋两阶段可在 15s 内首 Fact | 最终集成固定样例 n≥3；max>15s 即不得声称达标 |
| A04 | EVIDENCED | Experience 并发 2 有收益且绑定稳定 | 限流/乱序/单经历失败；异常则退回串行并 Challenge 性能目标 |
| A05 | ASSUMPTION | 16k 总预算覆盖合法长简历 | 最大 Fact 数、重试与超限探针；不足不得静默删内容 |
| A06 | ASSUMPTION | 快照限频可同时满足恢复与 512KiB/task | 断线中 reason、缺口和容量压力；超限时压缩完成事件而非删结果 |
| A07 | EVIDENCED | 长任务状态峰值约 26.9KiB | 最终 schema 重新序列化；不得直接沿用实验对象大小 |
| A08 | EVIDENCED | 联系方式链可完整保留 | 最终 Task→Document→DOCX→PDF/download 重跑 |
| A09 | REJECTED | 当前教育映射正确 | 真实 `本科（）` 反例；T07 必须修复 |
| A10 | REJECTED | 合法短输入当前可稳定渲染 | short 7/7 TemplateError；T08 必须关闭 |

Pre-mortem 至少重点尝试证明：

1. SSE 和快照在断线/并发下会重复调用、交叉绑定或让旧 revision 覆盖新任务；
2. 两阶段调用与经历并发会使 Token、限流或顺序失控，15 秒只在简化探针成立；
3. 清理或取消会误删活动/已发布对象，或遗留 Provider、Word、文件与迟到 artifact。

## 6. 开发 Gate

### 6.1 状态、协议与取消

- schema migration：新库、V2.1.0 旧库、重复执行、失败回滚、备份/cleanup；
- Task：DRAFT→RUNNING→SUCCEEDED/FAILED/CANCELLED 全矩阵，非法跳转 fail closed；
- 草稿：保存确认、刷新/页面重开恢复、输入 revision 冻结、未保存与已保存边界；
- SSE：重复 seq、乱序、缺口、重连、缓冲过期、快照替换、reason 断流；
- 幂等：刷新和重连不增加 LLM/Embedding/Word 调用；
- 取消：P1、P2、每个并发 P3、P4/Word worker；迟到结果不发布；随后新任务能开始；
- 资源：Provider client、后台 task、数据库、文件、Word/worker 无泄漏。

### 6.2 生成、性能与成本

- Fact schema、`experience_id/fact_id/fact_refs`、reason 绑定、无外来 ID；
- P1/P2 完成业务项、P3 整条 Fact、reason 真增量；断流使用明确 fallback；
- Experience 串行对照并发 2，顺序稳定、单经历失败隔离；
- 正常逻辑调用 `1 + 2F`，Embedding 0/1，SSE 重连增量 0；
- 成功不重试；可重试失败不超过 3 attempts；不可重试错误立即失败；
- JD/Fact/reason 单 attempt 和任务 16k Token 上限；超限不产生截断成功；
- 固定短/典型/长、cold/warm 真实模型样本每格 `n >= 3`；记录中位数、最大值和完整调用数据；
- 点击零点首状态、首 JD 项、首召回 Fact、首完成 Fact、P1-P4 和总耗时全部使用同一单调时钟。

### 6.3 内容与 artifact

- 联系方式全组合：仅姓名、每个选填字段、全部字段、Unicode/空白归一；
- 技能 2～4 类或事实不足时诚实减少，类别/条目均有事实依据，无内部术语堆砌；
- headline/body 标题加粗边界、冒号、fact_refs、事实不扩张、Career Memory 字节不变；
- 教育 major/degree 缺失组合、已有括号、中文/英文混排，无空括号/倒置/重复；
- short/typical/long 均生成 DOCX；同一 DOCX→Word PDF→viewer/download hash；
- Word 缺失、COM 失败、超时、并发 busy、PDF/anchor/下载失败均 fail closed；
- P4 全程无控制台或可见 Word 闪窗，WINWORD/worker 泄漏 0。

### 6.4 容量、回归与构建

- 256KiB/256KiB、20 条、16MiB 边界及恰好等于/超出 1 byte；
- 活动、取消中、当前页面、ResumeRevision、DOCX/PDF 保护对象 0 误删；
- 启动/终态/阈值 cleanup，重复调用、句柄占用、cleanup 失败、相邻哨兵；
- V2.1.0 核心事实、单次 JD、DOCX/PDF 同源、三视口零整页滚动与 ErrorBoundary 回归；
- Python compile、类型检查、前端正式 build、统一 precheck；
- Windows onedir 从 clean baseline 重建并隔离启动；包内无 Key、真实数据、测试注入、开发机路径和
  ReportLab 产品链；前端可见行为未在 Revision 1 被修改。

所有必做项必须给出 PASS/FAIL 与非零失败退出；“未执行”“待验收代跑”“环境限制但未定位”均不能
形成 T11 checkpoint。真实外部模型暂不可用时进入 `BLOCKED`，不得用 mock 替代真实性能结论。

## 7. RESULT Delivery Contract

Development Agent 在候选冻结前创建/更新 `RESULT.md`，顶部状态只能为“待验收”，并首先标明
`BATCH1_DEV_VERIFYING` 或 `BATCH1_DEV_VERIFIED`；不得写“独立验收通过”或“可发布”。

### 7.1 必填身份

- 版本、Plan Revision、批准 PLAN commit/blob；
- 实际 `<current-workspace>`、branch、开发基线、checkpoint commit、唯一父和 clean；
- 相对基线的完整文件清单与 diff 统计；
- 若有第一批内部包：路径、文件数/总字节、EXE/hash、manifest；不得称为发布包。

### 7.2 逐项交付映射

必须逐行填写：

| PLAN ID | 用户结果 | 开发理解 | 实际交付 | 可复核证据 | 已知偏差 |
|---|---|---|---|---|---|
| V220-G01～G06、V220-R1-T01～T11 | 不得缺项 | 说明结果而非只列模块 | 文件/API/schema/行为 | 命令、退出码、计数、artifact | 无也写“无” |

### 7.3 参数与运行证据

- 最终模型、Endpoint、reasoning、temperature、response format；
- JD 最终 token 值及为何在允许区间，Fact/reason/任务总上限；
- `E/F`、逻辑调用、HTTP attempt、Embedding、重试与 Token 的逐样例摘要；
- 短/典型/长及 cold/warm 的 n、中位数、最大值、首 Fact 和总时长；
- 状态/事件真实序列、取消与迟到 fence、容量/cleanup、DOCX/PDF hash；
- Pre-mortem、Architecture Check、Falsification Check 的结论；没有可信失败模式不能标记完成。

### 7.4 实际变化与偏差

分别说明 API、数据库/schema、领域模型、模块职责、配置/依赖、打包和可见前端是否变化；无变化也
写“无”。所有 `ASSUMPTION` 的最终状态必须更新。出现 Challenge 时记录触发证据、关闭方式和是否
需要 Revision 2 之外的新 PLAN Revision。

### 7.5 待独立验收问题

Revision 1 不启动 Acceptance，但 RESULT 必须预先列出最终候选需要独立核实的问题：

1. 刷新/重连/乱序下是否真实不重复调用、不交叉覆盖；
2. 取消后 Provider/Word/artifact 是否真正停止或被 fence，能否立即开始新任务；
3. 两阶段绑定、并发 2、调用/Token 与 15 秒是否在真实模型和最终包成立；
4. task cleanup 是否可能误删活动状态或已发布 DOCX/PDF；
5. 联系方式、技能、headline、教育和 short 输入是否在真实 DOCX/PDF 一致；
6. 最终 Revision 2 是否忠实实现批准 `DS-xxx`，且 HTML 过程预览没有成为第二产物真源。

## 8. 第一批完成条件与下一门禁

Revision 1 完成必须同时满足：

1. T01～T11 全部完成，开发 Gate 无 FAIL/NOT_RUN；
2. RESULT 合同一次填写完整，工作区 clean；
3. 没有开放 `CHALLENGE_OPEN`；
4. 没有修改 Design Gate 禁止范围；
5. Documentation Agent 仅依据 PLAN、RESULT、机械身份和证据入口完成一次语义交接审查。

随后仍不进入独立验收或发布。下一门禁是 Product Owner 批准 Design Snapshot；Documentation Agent
据此形成 Revision 2、导入 `DS-xxx` 并授权第二批可见实现与最终集成。只有 Revision 2 完成并形成
冻结候选，才进入 Acceptance、Product Owner 人工验收和发布流程。
