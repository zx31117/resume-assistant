# 已导入设计基线

本目录只保存已由 Product Owner 批准、并由正式版本 PLAN 选择的不可变设计基线。Design Agent
持续修改的工作稿与本地源快照保存在 `<design-workspace>`，不直接作为开发指令，也不进入
CURRENT_STATE。

## 身份规则

- `DECISIONS.md` 的决策编号使用 `D-xxx`；
- 设计侧既有本地快照可以保留 `D-xxx`；
- 导入 canonical 后统一使用 `DS-xxx`，并在 PLAN 同时记录源 Snapshot ID、canonical Baseline
  ID、入口、manifest SHA-256、批准人和现实源码基线；
- 已导入基线不得原地修改。任何设计变化先回到 Design Agent 工作稿，经用户批准新快照后再
  由后续 PLAN 选择。

## 基线索引

| 版本 | Canonical Baseline | 源 Snapshot | 主题 | Manifest SHA-256 | 状态 |
|---|---|---|---|---|---|
| V2.1.0 | `DS-002` | `D-002`（Based On `D-001`） | A | `7ace7413a81d504a16cdfface2faff50b1623dab0f70ceac4edea1c9717c0cfc` | 已导入并校验；PLAN 已批准 |

设计获批只代表 UI/UX 基线获批，不表示其中的 Mock、Preview 或未来页面已经实现。具体实施范围
由对应版本 PLAN 的交付矩阵决定；只有完成真实实现和验收的 Active 能力才能进入
`CURRENT_STATE.md`。
