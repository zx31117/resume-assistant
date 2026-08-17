"""数据库会话与引擎。SQLite，V2 换 PostgreSQL 只改连接串。"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)


_ensure_parent(settings.SQLITE_PATH)

engine = create_engine(
    f"sqlite:///{settings.SQLITE_PATH}",
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """FastAPI 依赖：提供数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
