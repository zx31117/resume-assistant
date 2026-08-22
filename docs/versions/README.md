# 版本开发经验档案

本目录保存项目从 V1.0.0 开始的开发经验，供项目维护者回忆上下文，也供其他人学习问题、方案、决策、实际结果和计划偏差。

“可以依据记录复刻当时的开发路径”是检验档案完整度的标准，不是文档建设的核心目的。

阅读某一版本时，先读 `PLAN.md` 理解当时准备做什么，再读 `RESULT.md` 理解实际做了什么。历史文档中的接口、依赖和后续设想属于当时语境，不代表当前状态；当前事实以根目录 `CURRENT_STATE.md` 为准。

## 版本索引

| 版本 | 定位 | 计划 | 结果 | 阶段结果 |
|---|---|---|---|---|
| V1.0.0 | 验证核心技术链路 | [PLAN](./v1.0.0/PLAN.md) | [RESULT](./v1.0.0/RESULT.md) | PDF → 经历库 → JD → RAG → Markdown 通过 |
| V1.1.0 | 提升抽取速度与 RAG 质量 | [PLAN](./v1.1.0/PLAN.md) | [RESULT](./v1.1.0/RESULT.md) | 并行抽取、7 维 JD、加权检索和结构化输出通过 |
| V1.2.0 | 建立标准 DOCX 能力 | [PLAN](./v1.2.0/PLAN.md) | [RESULT](./v1.2.0/RESULT.md) | 直接 ResumeDocument 路径通过；JD 路径未闭环 |
| V1.2.1 | 清理工程问题并恢复向量存储 | [PLAN](./v1.2.1/PLAN.md) | [RESULT](./v1.2.1/RESULT.md) | PII、依赖、下载、死代码和 Chroma 专项通过 |
| V1.3.0 | 闭合 V1 的 JD → DOCX 主链 | [PLAN](./v1.3.0/PLAN.md) | [RESULT](./v1.3.0/RESULT.md) | 第三轮修正、源码复核和人工 E2E 通过；V1 核心链路收口完成 |
| V1.4.0 | 源码—数据解耦与 GitHub 首发 | [PLAN](./v1.4.0/PLAN.md) | [RESULT](./v1.4.0/RESULT.md) | 已验收；Public 首发、`v1.4` tag 与匿名 clone 复核通过 |
| V1.4.1 | 对外版本一致性与身份边界清理 | [PLAN](./v1.4.1/PLAN.md) | [RESULT](./v1.4.1/RESULT.md) | 已验收；N4、源码与发布档案复核通过 |
| V1.4.2 | 发布基线与开发档案收口 | [PLAN](./v1.4.2/PLAN.md) | [RESULT](./v1.4.2/RESULT.md) | 需修正；Stub 异常退出仍泄漏临时目录 |

## 远期草稿（非开发指令）

| 版本 | 定位 | 草稿 | 状态 |
|---|---|---|---|
| V1.5.0 | 履历事实级内容决策与持久化收束 | [DRAFT](./v1.5.0/DRAFT.md) | 后续草稿；待 V1.4.2 收口后再复核 |
| V3.0.0 | 网页本地优先与模型服务平台 | [DRAFT](./v3.0.0/DRAFT.md) | 远期草稿；待 V1.5.0、V2 完成后重新评估 |

## 推荐历史阅读顺序

~~~text
V1.0.0 PLAN → V1.0.0 RESULT
→ V1.1.0 PLAN → V1.1.0 RESULT
→ V1.2.0 PLAN → V1.2.0 RESULT
→ V1.2.1 PLAN → V1.2.1 RESULT
→ V1.3.0 PLAN → V1.3.0 RESULT
→ V1.4.0 PLAN → V1.4.0 RESULT
→ V1.4.1 PLAN → V1.4.1 RESULT
→ V1.4.2 PLAN → V1.4.2 RESULT（完成后）
~~~
