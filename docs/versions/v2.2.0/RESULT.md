# V2.2.0 RESULT：执行记录

> 文档角色：V2.2.0 Development Agent 执行记录（开发候选冻结前由开发维护实施、自测与偏差）
> 当前状态：**待验收** — `BATCH1_DEV_VERIFYING`
> 当前阶段：Revision 1 / 第一批（仅设计无关后端实现）
> 产品基线：annotated tag `v2.1.0` → `5d72a2e08ebd4fa416b4b1dcdd79c1d08dfc7cfd`
> 开发路径：`<current-workspace>` 分支 `version/v2.2.0`
> 批准 PLAN：Revision 1，blob `324302a0ef6d81214c752d12281c221f2550f320`（VH-010 记录）

> **本文件由 Development Agent 在候选冻结前写实施、自测与偏差。** Revision 1 不产生可发布
> 候选，也不启动独立 Acceptance；`BATCH1_DEV_VERIFYING` 表示开发 Gate 尚在收口，不代表
> 任何独立验收结论或可发布状态。

---

## 1. T01 身份与基线核对（Required Reading 确认）

本节确认 Development Agent 在开始实现前已完成本版本强制阅读，缺任一项不得进入源码实现。

| 阅读对象 | 结论 |
|---|---|
| `docs/README.md` §0（Agent 执行入口）、§1～§5（产品目标/版本边界/链路/事实所有权/架构不变量） | 完成 |
| `docs/CURRENT_STATE.md`（当前已验收实现事实） | 完成 |
| 本版本 `PLAN.md` 全文（Revision 1 唯一有效合同） | 完成 |
| `docs/HUMAN_AI_WORKFLOW.md` §3.1（权限）、§3.2（PLAN/候选身份）、§3.4（强制反思与 Challenge）、§6（开发职责）、§11（上下文控制） | 完成 |

| 基线字段 | 值 | 核对 |
|---|---|---|
| 角色 | Development Agent（第一批，仅设计无关实现） | 一致 |
| 开发路径 | `<current-workspace>`，分支 `version/v2.2.0` | `git branch --show-current` = `version/v2.2.0` |
| 当前 HEAD | `d75b692c73ebeea91435f1daae996dde974fbf31`（docs 收口链顶部） | 一致 |
| 工作树 | clean（`git status --porcelain` 为空） | 一致 |
| 产品基线 | `v2.1.0` → `5d72a2e08ebd4fa416b4b1dcdd79c1d08dfc7cfd` | `git rev-list -n1 v2.1.0` 一致 |
| 批准 PLAN blob | `324302a0ef6d81214c752d12281c221f2550f320` | HISTORY VH-010 记录一致 |
| 本 Revision 授权 | 第一批、仅设计无关实现；Design Gate 关闭 | 遵守（不读取 Design Agent 工作稿） |
| Required Reading 项 | 全部完成 | 见上表 |

**身份边界确认（Development Agent）：**
- 只读 PLAN / HISTORY / CURRENT_STATE / DECISIONS / 全局文档，不修改；在 PLAN 范围修改源码、测试、依赖与构建配置；
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

| ID | PLAN 状态 | 内容 | T01 执行确认 / 后续证据入口 |
|---|---|---|---|
| A01 | EVIDENCED | minimal 可稳定输出绑定 Fact | T06 最终实现 3+3+3 边界重跑；失败则 Challenge 模型/协议 |
| A02 | REJECTED | 单复杂流能同时稳定绑定 Fact/reason | 禁止采用；T06 必须实现两阶段，不得用局部 1/3 PASS 恢复 |
| A03 | EVIDENCED | 紧凑 JD＋两阶段可在 15s 内首 Fact | T06 最终集成固定样例 n≥3；max>15s 即不得声称达标 |
| A04 | EVIDENCED | Experience 并发 2 有收益且绑定稳定 | T06 限流/乱序/单经历失败；异常退回串行并 Challenge |
| A05 | ASSUMPTION | 16k 总预算覆盖合法长简历 | T06 最大 Fact 数/重试/超限探针；不足不得静默删内容 |
| A06 | ASSUMPTION | 快照限频可同时满足恢复与 512KiB/task | T04/T09 断线中 reason、缺口、容量压力；超限压缩完成事件而非删结果 |
| A07 | EVIDENCED | 长任务状态峰值约 26.9KiB | T02/T09 最终 schema 重新序列化，不复用实验值 |
| A08 | EVIDENCED | 联系方式链可完整保留 | T07 最终 Task→Document→DOCX→PDF/download 重跑 |
| A09 | REJECTED | 当前教育映射正确 | T07 必须修复真实 `本科（）` 反例 |
| A10 | REJECTED | 合法短输入当前可稳定渲染 | T08 必须关闭 short 7/7 TemplateError |

> T01 完成证据：本文件身份区（§1）、Pre-mortem（§2）、假设台账（§3）已建立；基线 commit/blob
> clean 状态见候选冻结与 T11 收口记录。三个失败模式、对应探针与停止点已在 §2 登记。