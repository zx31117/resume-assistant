"""SQLAlchemy ORM 模型。

数据模型按"经历是资产"设计：
- Experience 是用户长期职业资产，独立于任何一份简历。
- 简历只是该资产的一个输出渠道（V1 为 Markdown 文本）。
- skills / achievements 用 JSON 字段存数组，SQLite 原生支持。
- V1.3：新增 VectorIndexJob 表，用于保证 SQL ↔ 向量的同步一致性（T7）。
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
)
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()


def _gen_uuid() -> str:
    return str(uuid.uuid4())


# ── VectorIndexJob 枚举（V1.3 T7） ─────────────────────────────── #

class IndexOperation(str, enum.Enum):
    UPSERT = "UPSERT"
    DELETE = "DELETE"


class IndexJobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


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

    # 关联 Chroma 中的文档 id（V1 与 experience.id 一致）
    vector_id = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="experiences")
    index_jobs = relationship("VectorIndexJob", back_populates="experience", cascade="all, delete-orphan")
    facts = relationship("Fact", back_populates="experience", cascade="all, delete-orphan")


class VectorIndexJob(Base):
    """V1.3 T7：SQL 与向量索引一致性任务。

    - Experience 变更和本 Job 的创建在同一 SQL 事务提交；
    - 请求内同步执行 Job（不引入 Worker）；
    - 重试必须幂等：DONE 直接跳过，FAILED/PENDING 可重新执行。
    """

    __tablename__ = "vector_index_jobs"

    id = Column(String, primary_key=True, default=_gen_uuid)
    experience_id = Column(String, ForeignKey("experiences.id"), nullable=False, index=True)
    user_id = Column(String, nullable=True, index=True)

    operation = Column(SAEnum(IndexOperation), nullable=False)
    status = Column(SAEnum(IndexJobStatus), nullable=False, default=IndexJobStatus.PENDING, index=True)

    retry_count = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, default="")

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    experience = relationship("Experience", back_populates="index_jobs")




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
