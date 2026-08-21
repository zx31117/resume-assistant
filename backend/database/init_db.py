"""建表脚本：python database/init_db.py"""
from database.session import engine
from database.models import Base


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("数据库表已创建")
