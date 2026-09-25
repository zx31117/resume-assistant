"""建表脚本：python database/init_db.py"""
from datetime import datetime

from database.session import engine, SessionLocal
from database.models import Base, User
from core.config import settings


def init_db() -> None:
    """建表并确保默认本地身份（DEFAULT_USER_ID）的最小行存在（PLAN Revision 3 owner）。"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.get(User, settings.DEFAULT_USER_ID) is None:
            db.add(User(id=settings.DEFAULT_USER_ID, name="demo-user",
                        email="", created_at=datetime.utcnow()))
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print("数据库表已创建")