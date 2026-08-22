# V1.4.2 RESULT：发布基线与开发档案收口

> 状态：待验收
> 分支：`version/v1.4.2`
> 基线 commit：`cbccdc8f40c9d4c2952c08504c14aa248fbfa29a`（`main` / `v1.4.1`）
> 候选 commit：尚未形成；当前仅形成文档阶段提交，最终以 T8 候选为准
> 功能验收：待开发与测试完成
> 结构变更验收：待高性能源码验收 Agent复核

## 1. 当前进度

| PLAN Task | 状态 | 当前结果 |
|---|---|---|
| T0 固定基线与工作路径 | 完成 | canonical 与 current 已从 `cbccdc8...` 建立；current 分支为 `version/v1.4.2`，建立时两处均 clean；review 待候选 commit 形成后创建 |
| T1 一次性首发工具退出 | 待开发 Agent | PLAN 已明确删除 `_v14_t8_delivery.py`，改为只读发布前检查 |
| T2 README、隐私和工作流 | 文档侧完成，源码/最终复核待办 | 根 README 已使用可复制的公开仓库 URL；工作流已写入路径角色、commit 交接、发布责任和正常 fast-forward 规则 |
| T3 当前事实与历史归档 | 文档侧完成 | CURRENT_STATE 已移除候选流水账；V1.4.1 RESULT 已追加带性质说明的发布后远端纠正记录 |
| T4 Markdown LF 规范 | 待开发 Agent | 需要新增 `.gitattributes` 并机械规范化、复核 diff |
| T5 Stub E2E runtime 隔离 | 待开发 Agent | 需要修改 `_v13_stub_e2e.py`，连续运行两次并证明不接触真实 runtime |
| T6 V1.5.0 草稿同步 | 完成 | 已补齐 SQLite 单一持久化、退出 Chroma/numpy+JSON、内部 Provider 边界及高风险迁移验收要求 |
| T7 版本元数据 | 文档侧部分完成，源码待办 | 根 README 已写 V1.4.2；`APP_VERSION`、OpenAPI/Stub 需开发 Agent同步并验证 |
| T8 候选与开发验证 | 未开始 | 等待 T1/T4/T5/T7 完成 |
| T9 独立源码验收 | 未开始 | 候选 commit 形成后，在 clean review 工作树执行 |
| T10 文档收口与发布 | 未开始 | 需 T9、人工确认和用户最终发布授权 |

## 2. 已完成的文档变化

### 2.1 正常 Git 生命周期

- 新增决策 D-023：公开 main 是后续版本唯一长期基线；
- 明确 V1.4.0 单 commit 首发是切断旧敏感历史的一次性动作；
- 后续版本保留正常父子提交关系，不重建 orphan/single-commit 仓库；
- 开发 Agent不发布公开 main/tag；文档 Agent在用户确认后执行远端 preflight、fast-forward 和 annotated tag；
- 非 fast-forward、未知远端提交或已存在 tag 时停止，不把 force push 当作常规发布方式。

### 2.2 固定工作角色

- `<canonical-repo>`：最新正式版本；
- `<current-worktree>`：最新开发候选；
- `<review-worktree>`：指定候选 commit 的干净验收副本；
- 四方交接必须同时给出版本、基线 commit、候选 commit、分支和 clean 状态；
- 公开文档只保存语义别名，不保存本机绝对路径。

### 2.3 文档真源收口

- CURRENT_STATE 只保留当前已验收事实和当前公开基线；
- 候选、失败冻结和发布过程继续保存在版本 RESULT；
- 历史 PLAN/RESULT 不改写原结论，但允许隐私、路径、换行、明显笔误等机械修正和有标记的发布后补录；
- 公开仓库 URL、项目名和 release/tag 明确属于用户入口，不再被隐私规则误删；
- 修正 V1.4.1 PLAN 的过期角色和 V1.2.1 两处版本边界笔误。

### 2.4 V1.5.0 规划同步

V1.5.0 仍以事实级内容决策为核心，同时补齐已经确认的数据架构：SQLite 保存 Experience、Fact、向量和索引状态；Chroma 与 numpy + JSON 两套活动后端退出；内部建立 LLM/Embedding Provider 契约，任意供应商用户配置留到 V3。V1.4.2 没有提前实施这些产品架构变化。

## 3. 实际全局变化

| 类别 | 当前实际变化 |
|---|---|
| API | 无 |
| 数据表/模型 | 无 |
| 产品业务链路 | 无 |
| 模块职责 | 尚无源码变化；计划退出一次性首发脚本并修复测试隔离 |
| 配置/依赖 | 尚无；`.gitattributes` 待开发 Agent新增 |
| 根 README | 当前开发版本和 clone URL 已更新 |
| 开发文档 | 工作流、决策、当前状态、历史补录、索引和 V1.5.0 草稿已同步 |

## 4. 当前验证

| 验证 | 状态 | 证据 |
|---|---|---|
| 基线 commit | 通过 | canonical main、`v1.4.1^{commit}` 和 current 起点均为 `cbccdc8...` |
| current 分支与初始状态 | 通过 | `version/v1.4.2`；建立时 `git status --short` 为空 |
| 文档相对链接 | 通过 | 当前仓库全部 Markdown 相对链接扫描无缺失 |
| 本机绝对路径 | 通过（文档侧） | 当前改动未写入真实用户目录；工作路径使用语义别名 |
| 公开仓库地址 | 通过 | 根 README 保留真实、可复制的公开 URL；这是允许项 |
| 源码实现与回归 | 未执行 | T1/T4/T5/T7 尚未由开发 Agent完成 |
| 高性能源码验收 | 未执行 | 待候选 commit |
| 人工验收 | 未执行 | 本版本无新产品功能，最终由用户审核文档和发布结果 |

## 5. 当前遗留与交接

开发 Agent 下一步只读取 `docs/README.md`、`CURRENT_STATE.md`、本 PLAN 和本 RESULT，然后完成 T1、T4、T5、T7、T8。不得读取旧 worktree 作为实现真源，不得操作公开 main/tag。完成后必须把候选 commit、实际 diff、两次 Stub E2E、版本一致性、换行检查和旧首发工具退出证据写回本 RESULT。

当前不能标记 V1.4.2 完成，也不能把 V1.4.2 写入 CURRENT_STATE 的已验收版本。
