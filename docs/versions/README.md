# 版本开发经验档案

本目录保存项目从 V1.0 开始的开发经验，供项目维护者回忆上下文，也供其他人学习问题、方案、决策、实际结果和计划偏差。

“可以依据记录复刻当时的开发路径”是检验档案完整度的标准，不是文档建设的核心目的。

阅读某一版本时，先读 `PLAN.md` 理解当时准备做什么，再读 `RESULT.md` 理解实际做了什么。历史文档中的接口、依赖和后续设想属于当时语境，不代表当前状态；当前事实以根目录 `CURRENT_STATE.md` 为准。

## 版本索引

| 版本 | 定位 | 计划 | 结果 | 阶段结果 |
|---|---|---|---|---|
| V1.0 | 验证核心技术链路 | [PLAN](./v1.0/PLAN.md) | [RESULT](./v1.0/RESULT.md) | PDF → 经历库 → JD → RAG → Markdown 通过 |
| V1.1 | 提升抽取速度与 RAG 质量 | [PLAN](./v1.1/PLAN.md) | [RESULT](./v1.1/RESULT.md) | 并行抽取、7 维 JD、加权检索和结构化输出通过 |
| V1.2 | 建立标准 DOCX 能力 | [PLAN](./v1.2/PLAN.md) | [RESULT](./v1.2/RESULT.md) | 直接 ResumeDocument 路径通过；JD 路径未闭环 |
| V1.2.1 | 清理工程问题并恢复向量存储 | [PLAN](./v1.2.1/PLAN.md) | [RESULT](./v1.2.1/RESULT.md) | PII、依赖、下载、死代码和 Chroma 专项通过 |
| V1.3 | 闭合 V1 的 JD → DOCX 主链 | [PLAN](./v1.3/PLAN.md) | [RESULT](./v1.3/RESULT.md) | 第三轮修正、源码复核和人工 E2E 通过；V1 核心链路收口完成 |
| V1.4 | 源码—数据解耦与 GitHub 首发 | [PLAN](./v1.4/PLAN.md) | [RESULT](./v1.4/RESULT.md) | 待验收；第三轮本地 T9 通过，下一门为 MIG-3，之后执行 T10/T11 与用户验收 |

## 推荐历史阅读顺序

~~~text
V1.0 PLAN → V1.0 RESULT
→ V1.1 PLAN → V1.1 RESULT
→ V1.2 PLAN → V1.2 RESULT
→ V1.2.1 PLAN → V1.2.1 RESULT
→ V1.3 PLAN → V1.3 RESULT
→ V1.4 PLAN → V1.4 RESULT
~~~
