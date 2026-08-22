# AI Career Resume Assistant 开发文档

> 文档角色：开发者与 Agent 的总入口；保存稳定产品目标、版本边界与架构约束
> GitHub 用户入口：[根 README](../README.md)；普通使用者不需要先阅读本开发档案
> 当前已验收版本：V1.4.1；公开 `main` 与 annotated tag `v1.4.1` 的基线 commit 为 `cbccdc8f40c9d4c2952c08504c14aa248fbfa29a`
> 当前开发版本：[V1.4.2 PLAN](./versions/v1.4.2/PLAN.md)；未验收内容不得写成当前能力
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
PDF → 文本解析 → 经历提取 → 经历确认并写入 SQL → 向量索引
JD → JD 分析 → RAG 匹配 → 受事实约束的内容生成
→ ResumeBuilder → ResumeDocument → TemplateRenderer → DOCX
~~~

V1.3.0 已完成并验收该核心链路；当前具体实现能力以 `CURRENT_STATE.md` 为准。

## 4. 事实所有权

| 数据 | 事实源 | 说明 |
|---|---|---|
| 用户经历 | SQL Experience | 公司、岗位、学校、项目、时间及原始事实 |
| 检索数据 | Chroma；故障时可回退 numpy | 可从 SQL 重建，不是事实源 |
| 姓名与联系方式 | 用户请求中的显式输入 | 缺失就留空；禁止从数据库、AI、模板或职业经历推测/回填 |
| 求职意向 | V1 只使用当前 JD 的 `JDAnalysis.position` | 未来可接受用户明确指定；永远不写入职业经历库 |
| 个人总结/自我评价 | V1 不生成、不渲染 | V2/V3 仅在履历单薄等场景按需评估 |
| JD | 用户请求原文 | JDAnalysis 是派生理解 |
| 定制表达 | AI 结构化结果 | V1 只改写已有经历的 bullets，不生成身份信息或个人总结 |
| 最终内容集合 | ResumeBuilder | 唯一负责选择、排序和数量限制 |
| 输出样式 | 系统 DOCX + TemplateSpec | Renderer 只负责展示 |

## 5. 架构不变量

1. API Route 只负责请求校验、调用应用服务和 HTTP 错误映射。
2. 业务模块不得直接处理 Word XML 或依赖具体 LLM 框架。
3. LangChain 只能存在于明确的 AI 适配层。
4. RAG 命中的 ID 必须回 SQL 读取完整经历事实。
5. 核心流程中的 ResumeDocument 必须由 ResumeBuilder 构建。
6. TemplateRenderer 和 LayoutOptimizer 不得选择或删除业务内容。
7. 模板样例文字不得进入用户简历。
8. SQL 是事实源，向量库是可重建索引；已知索引失败不得被隐藏。
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
| `versions/<version>/PLAN.md` | 该版本准备改变什么 |
| `versions/<version>/RESULT.md` | 该版本实际完成什么、偏差、证据和验收结论 |

规则：PLAN 规定要做什么，RESULT 记录实际做了什么，CURRENT_STATE 只记录已经验收的事实。

版本目录同时遵守以下结构约束：

1. 版本号和目录统一采用三段式：文档显示为 `V<major>.<minor>.<patch>`，目录为 `v<major>.<minor>.<patch>`；已经发布的历史 Git tag 保留原名，不因文档规范化而移动或重建。
2. 正式版本目录长期只保留 `PLAN.md` 与 `RESULT.md`；尚未立项的版本目录只保留 `DRAFT.md`。
3. 审计、迁移、验证、交付、评审和 manifest 等分项文件属于阶段产物：独有结论必须合并进同版本 `RESULT.md`，机读运行产物写入临时目录或 runtime data root，不在版本档案中形成第三个真源。
4. 文档路径、版本目录或交付规则的变化如果影响 `.gitignore`、源码脚本、测试或构建配置，文档 Agent 必须在当前版本 PLAN / RESULT 中建立源码同步任务；由开发 Agent 实施，并在必要时由源码验收 Agent复核。文档 Agent 不直接以改源码代替任务交接。

## 7. RESULT 最低交付契约

每个版本的开发 Agent 必须在 `RESULT.md` 中提供：

1. **实现标识**：对应分支、Git commit；尚未提交时明确记录工作区状态，最终验收必须绑定具体 commit；
2. **实际全局变化**：分别说明 API、数据表/模型、模块职责、配置/依赖是否变化；没有变化也要明确写“无”；
3. **验证表**：每项验证标记为“通过”“失败”“未执行”或“待独立验收”，并记录简短证据或未执行原因。
4. **两类验收结论**：分别记录“功能验收”和“结构变更验收”；后者没有适用变化时写“不适用”。

替换、废弃、统一、迁移或事实来源变更必须同时证明：新状态生效、旧状态退出、其他链路无回归。动态测试不能单独证明死代码或旧实现已经消失。RESULT 不粘贴源码或长日志；未经验证的内容不能写入 `CURRENT_STATE.md`，PLAN 要求的高风险或阶段性源码验收必须单独标明结论和对应 commit。详细操作规则见 [HUMAN_AI_WORKFLOW.md](./HUMAN_AI_WORKFLOW.md)。

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
| V1.4.2 | 发布基线与开发档案收口 | [PLAN](./versions/v1.4.2/PLAN.md) | [RESULT](./versions/v1.4.2/RESULT.md) | 第三轮修正完成、待 T9；当前事实仍以 V1.4.1 为准 |

历史经验的推荐阅读顺序见 [versions/README.md](./versions/README.md)。
