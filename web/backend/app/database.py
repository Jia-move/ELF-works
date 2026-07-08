"""数据库配置和会话管理"""
import os
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

# 基于本文件位置计算数据库绝对路径
_DB_DIR = Path(__file__).resolve().parent.parent / "data"
_DB_DIR.mkdir(parents=True, exist_ok=True)
_DEFAULT_DB_PATH = f"sqlite:///{_DB_DIR / 'smart_guide.db'}"

DATABASE_URL = os.getenv("DATABASE_URL", _DEFAULT_DB_PATH)

# SQLite 需要 check_same_thread=False
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)


# SQLite 外键约束
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI 依赖注入：获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """创建所有表"""
    import app.models  # noqa: F401 - 确保模型已导入
    Base.metadata.create_all(bind=engine)


def run_migrations():
    """为新模型字段在现有表中添加缺失的列（SQLite ALTER TABLE ADD COLUMN）"""
    import sqlite3
    from pathlib import Path

    # 从 DATABASE_URL 提取文件路径
    db_url = DATABASE_URL
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
        # 处理相对路径
        if not Path(db_path).is_absolute():
            db_path = str((Path(__file__).resolve().parent.parent / db_path).resolve())
    else:
        return  # 非 SQLite 跳过

    if not Path(db_path).exists():
        return  # 全新数据库，create_all 已处理

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 定义迁移：(表名, 列名, SQL 定义)
    migrations = [
        # Device 新增列
        ("devices", "sent_at", "sent_at TIMESTAMP"),
        ("devices", "mode", "mode VARCHAR(20) DEFAULT 'unknown'"),
        ("devices", "npu_status", "npu_status VARCHAR(20) DEFAULT 'unknown'"),
        ("devices", "qa_status", "qa_status VARCHAR(20) DEFAULT 'unknown'"),
        ("devices", "asr_status", "asr_status VARCHAR(20) DEFAULT 'unknown'"),
        ("devices", "is_demo", "is_demo BOOLEAN DEFAULT 0"),
        ("devices", "first_seen", "first_seen TIMESTAMP"),
        # ScenicSpot 新增列
        ("scenic_spots", "domain", "domain VARCHAR(20) DEFAULT 'scenic'"),
        # RecognitionEvent 新增列
        ("recognition_events", "event_id", "event_id VARCHAR(64)"),
        ("recognition_events", "received_at", "received_at TIMESTAMP"),
    ]

    for table, column, col_def in migrations:
        # 检查列是否存在
        cursor.execute(f"PRAGMA table_info({table})")
        existing = {row[1] for row in cursor.fetchall()}
        if column not in existing:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
                print(f"[Migration] Added {table}.{column}")
            except Exception as e:
                print(f"[Migration] SKIP {table}.{column}: {e}")

    conn.commit()
    conn.close()
