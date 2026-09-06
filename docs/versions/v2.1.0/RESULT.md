# V2.1.0 RESULT：执行记录（初始化）

> 当前状态：待验收（T0 已完成；开发待启动）
> 当前产品基线：已发布 V2.0.2
> 计划 Design Baseline：`DS-002`（源本地 Snapshot `D-002`，主题 A）
> PLAN 批准 commit：`4755ebe5a6a37ef40fc3179c1740eb8b5d22ae27`
> PLAN blob：`45fe3a2c3c6d99098ad2ba7fcb4996f7f7ca7e36`
> 发布结论：不适用

## 1. 本文件用途

本文件从 V2.1.0 立项阶段开始持续记录实际执行、验证证据、计划偏差和验收结论。它不以
PLAN 中的目标代替实现事实；尚未完成的工作必须保持“未开始”或“未通过”，不得提前写入
`CURRENT_STATE.md` 或对外 README。

## 2. 初始化结果

本轮只完成文档准备：

- 根据已发布 V2.0.2、全局决策、V2 需求池和用户已批准的本地设计快照形成正式 PLAN；
- 将本地 `D-002` 原样导入 canonical `DS-002`，完成文件清单和逐文件 hash 验证；
- 明确 V2.1.0 是一次完成核心用户界面整体重构的版本，开发可分 Task，但候选不得新旧混杂；
- 明确用户界面与开发者后台分离、真实链路优先、Mock/Adapter 隔离和三层功能状态；
- 将“生成历史”保留在 V2 需求池，不纳入本版本实施；
- 把 Windows GitHub CI 编码问题列为 T1，要求在候选提交上恢复统一预检绿灯；
- 建立 Design Fidelity、Integration、Regression、Accessibility 与人工场景验收门禁。

本轮未修改产品源码、测试、依赖、配置、构建、数据库、API 或公开产品事实。

## 3. 冻结身份状态

| 项目 | 计划值 | 当前结果 |
|---|---|---|
| 源 Design Snapshot | 本地 `D-002`，Based On `D-001`，主题 A | 已由 Product Owner 批准 |
| Canonical Design Baseline | `docs/design/baselines/V2.1.0/DS-002/` | 已导入；15 个文件 |
| manifest SHA-256 | `7ace7413a81d504a16cdfface2faff50b1623dab0f70ceac4edea1c9717c0cfc` | 源与目标一致 |
| `prototype/index.html` SHA-256 | `548c0ac44a989a550b5f0494f17df15bae9ac27bb524110aaa57ab126cfdd65d` | 源与目标一致 |
| PLAN 批准 commit/blob | Product Owner 批准后记录 | `4755ebe5a6a37ef40fc3179c1740eb8b5d22ae27` / `45fe3a2c3c6d99098ad2ba7fcb4996f7f7ca7e36` |
| 开发候选 commit | 开发结束后冻结 | 尚未产生 |
| 独立验收对象 | 与开发候选完全一致 | 尚未产生 |

导入结果：原清单覆盖的 14 个文件全部匹配；源和目标文件清单一致，15 个文件逐文件 SHA-256
一致；源快照没有被改写。Product Owner 已于 2026-09-06 批准 PLAN，批准 commit/blob 已记录。
设计基线由局部 `.gitattributes` 按 binary 保存，确保跨工作区检出时不发生换行归一化。

## 4. Task 状态

| Task | 状态 | 当前证据或下一门禁 |
|---|---|---|
| T0 设计基线与 PLAN 身份冻结 | 已完成 | `DS-002` 导入、逐文件 hash、批准 commit/blob 均已冻结 |
| T1 Windows CI 编码闭环 | 未开始 | 必须绑定后续源码提交和 GitHub run |
| T2 tokens、adapter、路由与状态骨架 | 未开始 | 等待 T0 |
| T3 用户界面与开发者后台分离 | 未开始 | 等待 T2 |
| T4 上传、D-038 确认边界与经历管理 | 未开始 | 等待 T2/T3 |
| T5 一键生成与真实进度 | 未开始 | 等待 T2/T3 |
| T6 内容预览、事实依据与 DOCX 下载 | 未开始 | 等待 T4/T5 |
| T7 隐私、Coming Soon 与缺席能力边界 | 未开始 | 等待 T3 |
| T8 Design Fidelity 与可访问性 | 未开始 | 等待 T3–T7 |
| T9 回归、统一预检与便携包 | 未开始 | 等待 T1–T8 |
| T10 RESULT 与冻结候选 | 未开始 | 等待 T9 |
| T11 独立验收 | 未开始 | 等待 T10 |
| T12 Product Owner 人工验收与发布 | 未开始 | 等待 T11 |

## 5. 开发交接

T0 已完成。Development Agent 启动前必须：

1. 在固定 `<current-workspace>` 同步包含本 RESULT 记录的 canonical 最新基线；
2. 核对批准 commit `4755ebe5a6a37ef40fc3179c1740eb8b5d22ae27` 与 PLAN blob
   `45fe3a2c3c6d99098ad2ba7fcb4996f7f7ca7e36`；
3. 重新验证 `DS-002` 的 14 项 manifest 和两个固定 hash；
4. 按 PLAN 从 T1 开始执行，候选冻结前持续更新本 RESULT 的实施、自测与偏差。

开发、自测或页面存在都不自动等于独立验收通过或发布；状态迁移继续遵守 PLAN 门禁。
