"""SQLAlchemy ORM 模型。

数据模型按"经历是资产"设计：
- Experience 是用户长期职业资产，独立于任何一份简历。
- 简历只是该资产的一个输出渠道（V1 为 Markdown 文本）。
- skills / achievements 用 JSON 字段存数组，SQLite 原生支持。
- V1.5.0：VectorIndexJob 已退出（向量持久化统一走 FactEmbedding）；
  Experience 不再持有 vector_id；新增 Fact / SchemaVersion / FactEmbedding。
- V2.2.0：新增临时任务（Task / InputRevision / TaskSubtask / TaskSnapshot）持久化，
  作为任务状态真源（PLAN §2.3）；不替代 Experience / Fact 事实源。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    Integer,
    Enum as SAEnum,
    LargeBinary,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


def _gen_uuid() -> str:
    return str(uuid.uuid4())


# ── V1.5.0：IndexOperation / IndexJobStatus 已退出（向量持久化走 FactEmbedding） ── #


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_gen_uuid)
    name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    experiences = relationship("Experience", back_populates="user", cascade="all, delete-orphan")


class Experience(Base):
    __tablename__ = "experiences"

    id = Column(String, primary_key=True, default=_gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)

    # project | work | education
    type = Column(String, default="")
    title = Column(String, default="")
    company = Column(String, default="")
    time = Column(String, default="")
    role = Column(String, default="")
    description = Column(Text, default="")
    skills = Column(JSON, default=list)
    achievements = Column(JSON, default=list)
    raw_text = Column(Text, default="")

    # V1.5.0：vector_id 已移除（向量持久化统一走 FactEmbedding，不再关联 Chroma 文档 id）

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="experiences")
    # V1.5.0：index_jobs 已移除；facts 是经历内部的 Fact 反向关系
    facts = relationship("Fact", back_populates="experience", cascade="all, delete-orphan")


# ── V1.5.0：VectorIndexJob 已删除（向量同步走 embedding_service.rebuild_embeddings） ── #


# ── V1.5.0 Fact 与 Schema Version ─────────────────────────────── #

class FactType(str, enum.Enum):
    """Fact 类型（首批范围，PLAN §4.1）。

    迁移阶段确定性粗粒度赋值，不调用 LLM 做细分类：
    - description 字段 → RESPONSIBILITY（职责块，未安全拆细为较粗 Fact）
    - achievements 列表项 → RESULT（成果/指标）
    后续服务层修改不改 fact_type（类型不是 V1.5 选材 PASS 条件）。
    """
    RESPONSIBILITY = "responsibility"
    ACTION = "action"
    METHOD = "method"
    RESULT = "result"
    METRIC = "metric"
    DELIVERABLE = "deliverable"
    WORK_CONTENT = "work_content"


class Fact(Base):
    """V1.5.0：经历内部可表达的已知素材（PLAN §4.1）。

    - fact_id 由 experience_id + source locator 确定性派生（uuid5），保证重复迁移同身份
      且不重复创建（PLAN §6.1.5）
    - text 是当前规范化事实文本；修改走 fact_service.modify_fact，更新 revision/content_hash
    - source_text/source_field/source_index 保留原始输入回查，不允许只保留 AI 摘要
    - content_hash 判断同一 ID 内容是否变化；source_hash 核对迁移来源是否变化
    - 修改后 revision/content_hash 变化 → 旧向量(T3)与旧 SelectedEvidenceSet(T4) 失效
    """
    __tablename__ = "facts"

    fact_id = Column(String, primary_key=True)
    experience_id = Column(String, ForeignKey("experiences.id"), nullable=False, index=True)

    fact_type = Column(SAEnum(FactType), nullable=False, default=FactType.RESPONSIBILITY)

    text = Column(Text, default="")
    source_text = Column(Text, default="")
    source_field = Column(String, default="")        # "description" | "achievements"
    source_index = Column(Integer, nullable=True)    # achievements[i]；description 为 None

    content_hash = Column(String, default="")          # SHA256(normalize(text))
    source_hash = Column(String, default="")           # SHA256(source_text)
    revision = Column(Integer, default=1, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    experience = relationship("Experience", back_populates="facts")


class SchemaVersion(Base):
    """V1.5.0：正式 schema version 与顺序迁移记录（PLAN §6.3）。

    迁移成功后写入对应 version；中途失败不写入，可安全重试。
    """
    __tablename__ = "schema_versions"

    version = Column(String, primary_key=True)
    applied_at = Column(DateTime, default=datetime.utcnow)
    description = Column(Text, default="")



# ── V2.2.0 临时任务持久化（PLAN §2.3，状态真源） ──────────────── #
# 这些表承载"工作台任务"的真实状态：草稿身份/JD、入参冻结、经历子任务、权威快照。
# 它们不是职业经历的事实源（事实源仍是 Experience / Fact），仅服务当前应用运行期的
# 任务恢复、渐进结果与产物发布。对象容量/保留/清理遵守 PLAN §2.4。

class Task(Base):
    """V2.2.0：一次工作台任务（PLAN §2.3）。

    - task_id：稳定任务标识；一次 profile 的前台活动任务唯一。
    - status：DRAFT/READY/RUNNING/CANCELLING/SUCCEEDED/FAILED/CANCELLED（core.task.TaskStatus）。
    - current_input_revision：当前冻结的 InputRevision 序号（未冻结为 0）。
    - active_operation_id：关联生成 operation 的可观察 id。
    - seq：本任务事件/快照单调序号（SSE 断点与去重基准）。
    - expires_at：临时记录过期时刻（清理扫描依据）。
    - terminal_error：终态错误码（SUCCEEDED 为空）；只存稳定码，不存正文/堆栈。
    """
    __tablename__ = "tasks"

    task_id = Column(String, primary_key=True)
    # V2.2.0 P0（owner 契约）：任务归属当前本地用户。NULL 表示历史遗留无主任务
    # （LEGACY_UNOWNED 隔离态），不参与并 scope 的列选/列表/清理。
    user_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="DRAFT", index=True)
    current_input_revision = Column(Integer, nullable=False, default=0)
    active_operation_id = Column(String, nullable=True)
    seq = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True, index=True)
    terminal_error = Column(String, nullable=True)

    # 最终产物（ResumeRevision / artifact 引用），SUCCEEDED 后发布，受 T09 清理保护
    published_resume_revision = Column(Integer, nullable=True)
    published_docx_path = Column(Text, nullable=True)
    published_pdf_path = Column(Text, nullable=True)


class InputRevision(Base):
    """V2.2.0：不可变入参快照（PLAN §2.3）。

    姓名、电话、邮箱、所在地、完整 JD 与输入 hash。冻结后不可原地修改；新一次冻结生成新 revision。
    InputStream 原文超过状态硬上限时由 API/service 返回明确 413/领域错误，不静默截断。
    """
    __tablename__ = "input_revisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("tasks.task_id"), nullable=False, index=True)
    revision = Column(Integer, nullable=False, default=1)
    name = Column(Text, default="")
    phone = Column(Text, default="")
    email = Column(Text, default="")
    location = Column(Text, default="")
    jd = Column(Text, default="")
    input_hash = Column(String, nullable=False, default="")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("task_id", "revision", name="uq_input_revision_task_rev"),
    )


class TaskSubtask(Base):
    """V2.2.0：经历子任务状态（PLAN §2.3）。

    - sort_order：本任务内冻结顺序（不影响最终模板顺序）。
    - status：PENDING/RUNNING/SUCCEEDED/FAILED/CANCELLED（core.task.SubtaskStatus）。
    - fact_results：本经历内已完成的 Fact 结果 JSON：最长 2 个经历并发，同一经历内 Fact 串行。
    - failure_code：稳定失败码；context 只存脱敏摘要。
    """
    __tablename__ = "task_subtasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("tasks.task_id"), nullable=False, index=True)
    experience_id = Column(String, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="PENDING")
    fact_results = Column(JSON, default=list)
    failure_code = Column(String, nullable=True)
    started_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("task_id", "experience_id", name="uq_task_subtask_exp"),
    )


class TaskSnapshot(Base):
    """V2.2.0：覆盖式权威快照（PLAN §2.3）。

    - seq：本快照对应的事件序号（SSE 断线重连：先读权威快照，再从后续 seq 订阅）。
    - phase：当前阶段（P1–P4）。
    - payload：当前可恢复的 P1–P4 业务结果 + reason 当前完整文本 + 当前阶段（JSON）。
    快照为覆盖式（每个任务一条），容量受 PLAN §2.4 硬上限约束；超限时压缩完成事件而非删结果。
    """
    __tablename__ = "task_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("tasks.task_id"), nullable=False, unique=True, index=True)
    seq = Column(Integer, nullable=False, default=0)
    phase = Column(String, nullable=False, default="")
    payload = Column(JSON, default=dict)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class TaskEvent(Base):
    """V2.2.0：SSE 业务完成事件（PLAN §2.3）。

    只持久化业务完成事件与权威快照；字符/token delta 不逐条写数据库。
    事件有单调 seq、可幂等去重；出现缺口或环形缓冲过期时客户端重取权威快照。
    事件+快照合计受 PLAN §2.4 硬上限约束，超限时压缩完成事件。
    """
    __tablename__ = "task_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String, ForeignKey("tasks.task_id"), nullable=False, index=True)
    seq = Column(Integer, nullable=False)
    input_revision = Column(Integer, nullable=False, default=1)
    event_type = Column(String, nullable=False)
    phase = Column(String, nullable=False, default="")
    payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("task_id", "seq", name="uq_task_event_seq"),
    )


class Artifact(Base):
    """V2.2.0 Revision 3 返工：不可变 artifact 引用（PLAN G04/G05、§3.1、§3.3）。

    这是用户简历 DOCX/PDF 的**唯一授权真源**：下载路由只能通过 (task_id, kind,
    resume_revision) 解析到这里登记的行，再据此取文件；客户端传入的 filename、
    basename、相对路径或磁盘路径一律不作为授权依据。

    - `artifact_id`：不可变引用 id（登记时生成，之后不得改写）。
    - `task_id` / `user_id`：归属（Task 与 owner 双绑）；解析时必须同时匹配当前 owner。
    - `kind`："docx" | "pdf"。
    - `resume_revision`：本条 artifact 对应的冻结 InputRevision（同一任务不同轮次互不覆盖）。
    - `file_name`：最终发布目录下的文件名（不含任何目录分隔）；`rel_dir` 为发布目录语义标签。
    - `sha256` / `size_bytes`：登记时校验通过的实际文件身份，供发布后复核与同源判定。

    只有全部 staging 校验通过、文件提升成功、且与 `SUCCEEDED` 在同一数据库事务边界提交时，
    才允许写入本表；未登记的磁盘文件永远不会被下载路由暴露。
    """
    __tablename__ = "artifacts"

    artifact_id = Column(String, primary_key=True, default=_gen_uuid)
    task_id = Column(String, ForeignKey("tasks.task_id"), nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    kind = Column(String, nullable=False)
    resume_revision = Column(Integer, nullable=False, default=0)
    file_name = Column(String, nullable=False)
    rel_dir = Column(String, nullable=False, default="output")
    sha256 = Column(String, nullable=False, default="")
    size_bytes = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("task_id", "kind", "resume_revision", name="uq_artifact_task_kind_rev"),
    )


# ── V1.5.0 Fact Embedding（BLOB 向量派生表，PLAN §6.2） ────────── #

class EmbeddingStatus(str, enum.Enum):
    """Fact 向量状态。无 Key 时停在 PENDING；不匹配时 INVALID；失败可重试。"""
    PENDING = "PENDING"    # 待计算（无 Key 或未重建）
    VALID = "VALID"        # 可用：fingerprint/维度/Fact revision-hash 均匹配
    INVALID = "INVALID"    # Fact 修改或 fingerprint/维度变化，需重建
    FAILED = "FAILED"      # 计算失败（可重试）


class FactEmbedding(Base):
    """V1.5.0：Fact 向量派生表（PLAN §6.2）。

    - 以 (fact_id, embedding_fingerprint) 唯一定位
    - vector_blob 存明确 dtype 的向量字节；查询时读入内存做精确相似度
    - fingerprint/维度/Fact revision-hash 不匹配 → INVALID，重建前不得使用
    - numpy 只作计算库（cosine），不承担 JSON 持久化或 fallback 后端
    """
    __tablename__ = "fact_embeddings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fact_id = Column(String, ForeignKey("facts.fact_id"), nullable=False, index=True)
    embedding_fingerprint = Column(String, nullable=False)
    dimension = Column(Integer, nullable=False, default=0)
    vector_blob = Column(LargeBinary, nullable=True)
    vector_dtype = Column(String, default="float32")
    fact_revision = Column(Integer, nullable=False, default=1)
    fact_content_hash = Column(String, default="")
    status = Column(SAEnum(EmbeddingStatus), nullable=False, default=EmbeddingStatus.PENDING, index=True)
    error = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("fact_id", "embedding_fingerprint", name="uq_fact_embedding"),
    )
