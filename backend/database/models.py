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

