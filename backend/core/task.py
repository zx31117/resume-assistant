"""V2.2.0 任务领域常量与状态机（PLAN §2.3 / §2.4）。

后端是任务状态真源。本模块只保存稳定枚举、标签和容量边界常量，不承载业务逻辑。
业务状态由 repository / service 维护，本模块只保证身份与上限可被三方复用而不漂移。
"""
from __future__ import annotations

import enum


class TaskStatus(str, enum.Enum):
    """任务生命周期状态（PLAN §2.3）。非法跳转由 repository 拒绝（fail closed）。"""

    DRAFT = "DRAFT"            # 身份/JD 草稿已保存，尚未开始生成
    READY = "READY"            # 输入冻结完成（InputRevision 已落盘），可开始生成
    RUNNING = "RUNNING"        # 生成进行中（一个 profile 最多一个）
    CANCELLING = "CANCELLING"  # 取消已请求，正在停止可控资源
    SUCCEEDED = "SUCCEEDED"    # 终态：成功
    FAILED = "FAILED"          # 终态：失败
    CANCELLED = "CANCELLED"    # 终态：取消完成


# 终态集合（不可再变更业务结果，只允许清理生命周期）
TERMINAL_STATUSES = frozenset({
    TaskStatus.SUCCEEDED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
})

# 未提交可编辑态（可接受输入保存/刷新）
DRAFTABLE_STATUSES = frozenset({TaskStatus.DRAFT, TaskStatus.READY})

# 唯一前台活动任务状态（一个 profile 只允许其一）
ACTIVE_EXCLUSIVE_STATUSES = frozenset({TaskStatus.RUNNING, TaskStatus.CANCELLING})

# 合法状态跳转表（source -> 允许的 targets）。未列出即非法，repository fail closed。
TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.DRAFT: frozenset({TaskStatus.DRAFT, TaskStatus.READY, TaskStatus.CANCELLED}),
    TaskStatus.READY: frozenset({TaskStatus.READY, TaskStatus.RUNNING, TaskStatus.CANCELLED}),
    TaskStatus.RUNNING: frozenset({TaskStatus.RUNNING, TaskStatus.CANCELLING, TaskStatus.SUCCEEDED,
                                   TaskStatus.FAILED, TaskStatus.CANCELLED}),
    TaskStatus.CANCELLING: frozenset({TaskStatus.CANCELLING, TaskStatus.CANCELLED, TaskStatus.FAILED}),
    TaskStatus.SUCCEEDED: frozenset(),   # 终态
    TaskStatus.FAILED: frozenset(),      # 终态
    TaskStatus.CANCELLED: frozenset({TaskStatus.CANCELLED}),  # 终态：仅容忍重复确认同一态
}


class SubtaskStatus(str, enum.Enum):
    """Experience 子任务状态（PLAN §2.3）。每个 Experience 一个。"""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# ── 容量与保留常量（PLAN §2.4） ───────────────────────────────── #


# 单任务状态记录硬上限 256 KiB（Task + InputRevision + 子任务 + 权威快照之外的元数据）
TASK_STATE_HARD_LIMIT_BYTES = 256 * 1024

# 单任务事件与 display snapshot 合计硬上限 256 KiB
TASK_EVENT_SNAPSHOT_LIMIT_BYTES = 256 * 1024

# 最多保留 20 条终态或孤立临时记录
MAX_KEEP_TERMINAL = 20

# 任务临时状态（artifact 正文之外）总量最多 16 MiB
TASK_TEMPORARY_TOTAL_LIMIT_BYTES = 16 * 1024 * 1024

# 未提交孤立草稿及 FAILED/CANCELLED 保留 24 小时
DRAFT_EXPIRES_HOURS = 24
FAILED_OR_CANCELLED_EXPIRES_HOURS = 24

# 快速跳过：一次 profile 只允许一个前台活动任务
MAX_ACTIVE_EXCLUSIVE = 1

# 事件 seq 环形缓冲（SSE 重连断点上限；超过直接从权威快照恢复）
EVENT_RING_BUFFER_SIZE = 1024

# ── LLM 调用/Token 门禁（PLAN §2.2 / V220-G04） ───────────────── #
# 单任务全部 LLM completion tokens 合计上限；即将超限时不得启动新的 Fact/reason 调用
TASK_LLM_COMPLETION_LIMIT = 16 * 1024

# 各逻辑调用单次 HTTP attempt 的 completion token 上限
JD_COMPACT_MAX_TOKENS = 1024          # 允许 512–2048；超区间须 Challenge
FACT_MAX_TOKENS = 800                 # 单 Fact 一次 attempt 上限
REASON_MAX_TOKENS = 256               # reason 一次 attempt 上限

# 单个逻辑调用最多重试次数（最多 3 个 HTTP attempt）
LLM_MAX_ATTEMPTS = 3

# 每任务 Embedding：同一 input_revision 至多一次在线 JD 查询向量（Fact 向量复用）
TASK_MAX_ONLINE_JD_EMBEDDING = 1