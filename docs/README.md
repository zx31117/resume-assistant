# AI Career Resume Assistant 开发文档

> 文档角色：开发者与 Agent 的总入口；保存稳定产品目标、版本边界与架构约束
> GitHub 用户入口：[根 README](../README.md)；普通使用者不需要先阅读本开发档案
> 当前已验收版本：V2.0.1；源码验收对象为 `9319782d5f1a8d5f543e6795f2f024143fa9dbc7`，发布标识为 annotated tag `v2.0.1`
> 当前已发布版本档案：[V2.0.1 PLAN](./versions/v2.0.1/PLAN.md) / [RESULT](./versions/v2.0.1/RESULT.md)；开发、独立源码验收、人工确认、文档收口与版本发布均已完成
> 当前活动版本：V2.0.2；首次候选 `a40c14d` 在文档 Agent 发布前复核中因测试访问真实 runtime 被打回，[PLAN](./versions/v2.0.2/PLAN.md) / [RESULT](./versions/v2.0.2/RESULT.md) 等待开发集中返工
> 后续方向：V2.1.0 预计重新设计整体界面，具体范围仍需另立版本文档；其他 V2 需求继续从 [V2 需求池](./versions/V2_REQUIREMENTS_POOL.md) 选择
> 当前实现事实：[CURRENT_STATE.md](./CURRENT_STATE.md)

本文只保存跨版本稳定的开发信息。当前实现、历史过程和活动版本目标分别由 `CURRENT_STATE.md`、版本 `RESULT.md` 和版本 `PLAN.md` 负责。根 `README.md` 面向 GitHub 普通用户，必须独立说明项目用途、安装、运行、数据边界和已公开能力，不承担内部状态管理职责。

文档的核心目的是留存开发经验：记录问题、方案、决策依据、实际结果和计划偏差，供后续回忆与他人学习。能依据记录复刻当时的开发路径，是检验记录完整度的标准，不是项目目的。

## 1. 产品目标

产品基于用户已有职业经历，根据目标岗位 JD 生成针对性简历。

核心原则：

- 真正的长期资产是用户职业经历知识库，简历只是一次输出；
- 生成内容必须以用户已有事实为边界，不得虚构经历；
- 同一条 Experience 可以服务多个 JD 和输出格式；
- 求职意向随目标 JD 变化，不属于职业经历资产，不能写入职业经历库；
- 模板只提供结构和样式，不提供用户事实；
- 更换模板或输出格式不能推翻经历库和匹配逻辑。

## 2. 版本边界

| 阶段 | 目标 | 明确不做 |
|---|---|---|
| V1 | 核心流程完整运行、内容正确、关键失败可见 | 精细体验、生产部署 |
| V2 | 匹配、生成、交互、性能、模板和排版体验完善 | 多用户服务器化 |
| V3 | 登录、多用户、持久化 Profile、服务器与生产体验 | 重做已经稳定的核心事实链路 |

V1 不要求严格一页纸、像素级排版、高性能体验、多用户或公网部署，也不生成个人总结/自我评价。个人总结只在后续版本针对履历单薄等场景评估；一页纸和视觉精修属于 V2；用户系统、PostgreSQL、对象存储、异步任务、限流和监控属于 V3。

## 3. 全局业务链路

~~~text
PDF → 文本解析 → 经历提取 → Experience / Fact 写入 SQL → SQLite 向量派生
JD → JD 分析 → 固定经历槽位 → 入选经历内事实选择 → 受事实约束的内容生成
→ ResumeBuilder 确定性装配 → ResumeDocument → TemplateRenderer → DOCX
~~~

V1.5.0 已完成并验收该核心链路的事实级、两层选材和单一向量持久化收口；V2.0.0 在不建立第二业务真源的前提下，为配置、维护、履历和生成增加三页图形交互及 Windows 便携启动器；V2.0.1 为生成、提取、Experience CRUD、迁移和索引维护增加统一的本地阶段、耗时与脱敏诊断能力。当前具体实现能力以 `CURRENT_STATE.md` 为准。

## 4. 事实所有权

| 数据 | 事实源 | 说明 |
|---|---|---|
| 用户经历 | SQL Experience / Fact | 公司、岗位、学校、项目、时间、可表达事实及其来源/revision/hash |
| 检索数据 | SQLite `fact_embeddings` | 可从 Fact 重建，不是事实源；numpy 只用于内存计算，不承担持久化或 fallback |
| 姓名与联系方式 | 用户请求中的显式输入 | 缺失就留空；禁止从数据库、AI、模板或职业经历推测/回填 |
| 求职意向 | V1 只使用当前 JD 的 `JDAnalysis.position` | 未来可接受用户明确指定；永远不写入职业经历库 |
| 个人总结/自我评价 | V1 不生成、不渲染 | V2/V3 仅在履历单薄等场景按需评估 |
| JD | 用户请求原文 | JDAnalysis 是派生理解 |
| 定制表达 | AI 结构化结果 | V1 只改写已有经历的 bullets，不生成身份信息或个人总结 |
| 最终内容集合 | CandidateExperienceSet / SelectedEvidenceSet | 第一层冻结经历名单，第二层只选择入选经历内的事实与表达侧重 |
| 输出样式 | 系统 DOCX + TemplateSpec | Renderer 只负责展示 |

## 5. 架构不变量

1. API Route 只负责请求校验、调用应用服务和 HTTP 错误映射。
2. 业务模块不得直接处理 Word XML 或依赖具体 LLM 框架。
3. LangChain 只能存在于明确的 AI 适配层。
4. RAG 命中的 ID 必须回 SQL 读取完整经历事实。
5. 核心流程中的 ResumeDocument 必须由 ResumeBuilder 按已经冻结的两层选材结果构建；Builder 不得重新进行 JD 相关性选择。
6. TemplateRenderer 和 LayoutOptimizer 不得选择或删除业务内容。
7. 模板样例文字不得进入用户简历。
8. SQL Experience / Fact 是事实源，SQLite `fact_embeddings` 是可重建派生索引；已知索引失败不得被隐藏。
9. 关键 AI 失败不能伪装成空成功。
10. 姓名和联系方式要么来自用户显式输入，要么留空；不得使用其他来源补齐。
11. 求职意向只能来自当前 JD；未来只有用户明确指定才能覆盖，职业经历库不得保存求职意向。
12. 未经用户确认，不得把 V2/V3 能力提前加入 V1。

## 6. 文档真源

| 文档 | 唯一职责 |
|---|---|
| [根 README](../README.md) | 面向 GitHub 普通用户的自包含项目介绍与使用入口；不是开发事实真源 |
| [README.md](./README.md) | 稳定产品目标、版本边界和架构不变量 |
| [CURRENT_STATE.md](./CURRENT_STATE.md) | 当前已经验收的实现事实和已知缺口 |
| [DECISIONS.md](./DECISIONS.md) | 影响后续版本的重要产品与技术决策 |
| [V2_REQUIREMENTS_POOL.md](./versions/V2_REQUIREMENTS_POOL.md) | V2 阶段尚未排入具体版本的候选需求；不是实施范围真源 |
| `versions/<version>/PLAN.md` | 该版本准备改变什么 |
| `versions/<version>/RESULT.md` | 该版本实际完成什么、偏差、证据和验收结论 |

规则：PLAN 规定要做什么，RESULT 记录实际做了什么，CURRENT_STATE 只记录已经验收的事实。

版本目录同时遵守以下结构约束：

1. 版本号和目录统一采用三段式：文档显示为 `V<major>.<minor>.<patch>`，目录为 `v<major>.<minor>.<patch>`；已经发布的历史 Git tag 保留原名，不因文档规范化而移动或重建。
2. 正式版本目录长期只保留 `PLAN.md` 与 `RESULT.md`；尚未立项的版本目录只保留 `DRAFT.md`。
3. 审计、迁移、验证、交付、评审和 manifest 等分项文件属于阶段产物：独有结论必须合并进同版本 `RESULT.md`，机读运行产物写入临时目录或 runtime data root，不在版本档案中形成第三个真源。
4. 文档路径、版本目录或交付规则的变化如果影响 `.gitignore`、源码脚本、测试或构建配置，文档 Agent 必须在当前版本 PLAN / RESULT 中建立源码同步任务；由开发 Agent 实施，并在必要时由验收 Agent 复核。文档 Agent 不直接以改源码代替任务交接。
5. 大版本需求池只保存尚未排期的候选想法，不使用完成状态，也不构成开发指令；具体版本只从中选择必要范围写入本版本 DRAFT / PLAN，版本范围冲突时以本版本 DRAFT / PLAN 为准。

协作路径采用固定独立仓库：`<canonical-repo>`、`<current-workspace>`、`<review-workspace>` 各自拥有独立 `.git`，不使用共享 Git 控制面的 linked worktree。开发 Agent 长期复用 current 的活动版本分支；验收 Agent 长期复用 detached、clean 的 review，并只对冻结候选 commit 返回只读报告；文档 Agent 在 canonical 中冻结 PLAN、接收候选、归并验收结论并在用户批准后发布。真实绝对路径只保存在本机项目配置和任务交接中，不进入公开文档；详细权限与版本流转见 [HUMAN_AI_WORKFLOW.md](./HUMAN_AI_WORKFLOW.md)。

## 7. RESULT 最低交付契约

每个版本的开发 Agent 必须在 `RESULT.md` 中提供：

1. **实现标识**：对应分支、Git commit；尚未提交时明确记录工作区状态，最终验收必须绑定具体 commit；
2. **实际全局变化**：分别说明 API、数据表/模型、模块职责、配置/依赖是否变化；没有变化也要明确写“无”；
3. **验证表**：每项验证标记为“通过”“失败”“未执行”或“待独立验收”，并记录简短证据或未执行原因。
4. **两类验收结论**：分别记录“功能验收”和“结构变更验收”；后者没有适用变化时写“不适用”。

用户批准 PLAN 后，文档 Agent 记录批准 commit、PLAN 路径和 blob；开发 Agent 与验收 Agent 对该 PLAN 只读。开发 Agent 只在候选冻结前更新 RESULT 的实施、自测和偏差，冻结后由文档 Agent 记录源码验收、人工验收、文档收口与发布状态。PLAN 需要返工补充时，由文档 Agent 追加契约并形成新的批准 commit/blob，开发 Agent 不得自行改写。

替换、废弃、统一、迁移或事实来源变更必须同时证明：新状态生效、旧状态退出、其他链路无回归。动态测试不能单独证明死代码或旧实现已经消失。测试、迁移、发布、临时目录或资源清理工具即使不改变产品功能，也必须按完整生命周期验收；业务断言通过、打印 warning 或正常路径无残留，都不能替代失败路径和清理失败的可执行断言。首次打回后，文档 Agent 必须把已见症状上升为对应问题类别的完整返工契约，避免只修当前样例。RESULT 不粘贴源码或长日志；未经验证的内容不能写入 `CURRENT_STATE.md`，PLAN 要求的高风险或阶段性源码验收必须单独标明结论和对应 commit。详细操作规则见 [HUMAN_AI_WORKFLOW.md](./HUMAN_AI_WORKFLOW.md)。

PLAN 要求独立源码验收时，参与该候选实现、自测或源码修复的开发 Agent 不得兼任验收 Agent。更换工作目录、会话、模型或职责名称都不能建立独立性；开发侧复核只能记为开发验证，T9 等独立验收任务仍须标记“待独立验收”。验收 Agent 若直接修改源码，该补丁转为新的开发候选，必须由未参与该补丁实现的另一验收 Agent 复验。没有独立验收者时版本保持“待验收”，用户的产品体验反馈也不能替代 PLAN 规定的源码验收，相关能力不得进入 `CURRENT_STATE.md` 或发布。

## 8. 文档同步规则

文档 Agent 在版本验收或需求变更后按影响更新，不新增重复真源：

| 变化 | 更新位置 |
|---|---|
| 公开用途、安装、运行、配置、隐私边界或用户可见能力 | 根 `../README.md` |
| 版本实际实现、测试和偏差 | 当前版本 `RESULT.md` |
| 已验收能力、API、数据模型、模块、运行基线和缺口 | `CURRENT_STATE.md` |
| 稳定产品目标、版本边界或架构不变量 | `README.md` |
| 影响后续版本的重要选择或既有决策状态变化 | `DECISIONS.md` |
| 版本状态和入口 | `README.md` 与 `versions/README.md` |

每次文档更新完成前必须检查：

1. RESULT 满足最低交付契约，人工验收和 PLAN 要求的源码验收已有结论；
2. PLAN、RESULT、CURRENT_STATE 中的“计划 / 实际 / 已验收”没有混写；
3. README、CURRENT_STATE、DECISIONS 和两个版本索引的版本号、状态与链接一致；
4. 只写入已验证事实；未完成项保留在 PLAN 或 RESULT，不进入 CURRENT_STATE；
5. 历史 PLAN / RESULT 不改写当时的目标、结论和决策；允许隐私脱敏、路径/链接迁移、编码/换行、明显笔误等机械修正，也允许用注明日期和性质的附录补记发布后才能确认的事实；
6. 相对链接、决策锚点和已删除路径检查通过。
7. 根 README 对 GitHub 用户自包含，且不要求读者理解 PLAN、RESULT、T 编号、Agent 分工或内部验收状态。
8. 功能验收与结构变更验收分别有结论；替换型变更具有正向、反向和回归证据。
9. 开发验证、源码验收、最终实现和发布标识指向同一条可追溯的 commit 链；验收后的相关修改已经重验。
10. 拟公开文档已扫描本机绝对路径、用户名、真实凭据和不安全的 Token URL；公开项目名、公开仓库 URL 和 release/tag 属于正常用户入口，不应误删；需要保留的内部执行路径使用语义别名，commit、branch 和验收数据不得以脱敏为由删除。
11. RESULT 记录被验收源码 commit 和冻结核对结果；最终发布 commit 不回写自身 SHA，发布后由 annotated tag 的目标 commit 作为唯一发布标识，避免“写入 SHA 导致 commit 再变化”的循环。

## 9. 版本索引

| 版本 | 定位 | 计划 | 结果 | 状态 |
|---|---|---|---|---|
| V1.0.0 | 核心技术链路可行性 | [PLAN](./versions/v1.0.0/PLAN.md) | [RESULT](./versions/v1.0.0/RESULT.md) | 已验收 |
| V1.1.0 | AI 质量与稳定性 | [PLAN](./versions/v1.1.0/PLAN.md) | [RESULT](./versions/v1.1.0/RESULT.md) | 已验收 |
| V1.2.0 | 标准模板与 DOCX 输出 | [PLAN](./versions/v1.2.0/PLAN.md) | [RESULT](./versions/v1.2.0/RESULT.md) | 路径 A 已验收；JD 路径未闭环 |
| V1.2.1 | 工程清理与基线稳定 | [PLAN](./versions/v1.2.1/PLAN.md) | [RESULT](./versions/v1.2.1/RESULT.md) | 已验收 |
| V1.3.0 | V1 核心链路收口 | [PLAN](./versions/v1.3.0/PLAN.md) | [RESULT](./versions/v1.3.0/RESULT.md) | 已验收；第三轮修正、源码复核和人工 E2E 通过 |
| V1.4.0 | 源码—数据解耦与 GitHub 首发 | [PLAN](./versions/v1.4.0/PLAN.md) | [RESULT](./versions/v1.4.0/RESULT.md) | 已验收；Public 首发、`v1.4` tag 与匿名 clone 复核通过 |
| V1.4.1 | 版本元数据与身份事实边界补丁 | [PLAN](./versions/v1.4.1/PLAN.md) | [RESULT](./versions/v1.4.1/RESULT.md) | 已验收；N4、源码与发布档案复核通过 |
| V1.4.2 | 发布基线与开发档案收口 | [PLAN](./versions/v1.4.2/PLAN.md) | [RESULT](./versions/v1.4.2/RESULT.md) | 已验收；第三轮 T9 9/9 通过，正常增量发布 |
| V1.5.0 | 事实级内容决策、两层选材与 SQLite 持久化收束 | [PLAN](./versions/v1.5.0/PLAN.md) | [RESULT](./versions/v1.5.0/RESULT.md) | 已发布；annotated tag `v1.5.0` 指向 `8d3aac6369146052f819c414cc18f53b11a778fc` |
| V2.0.0 | 本地全流程图形交互首版 | [PLAN](./versions/v2.0.0/PLAN.md) | [RESULT](./versions/v2.0.0/RESULT.md) | 已发布；annotated tag `v2.0.0` |
| V2.0.1 | 本地流程可观测性与问题定位 | [PLAN](./versions/v2.0.1/PLAN.md) | [RESULT](./versions/v2.0.1/RESULT.md) | 已发布；annotated tag `v2.0.1` |
| V2.0.2 | 工程基线与旧迁移契约退出 | [PLAN](./versions/v2.0.2/PLAN.md) | [RESULT](./versions/v2.0.2/RESULT.md) | 前置审核打回；待开发返工 |

历史经验的推荐阅读顺序见 [versions/README.md](./versions/README.md)。
