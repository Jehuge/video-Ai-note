"""
数据库迁移脚本
用于添加新字段到现有数据库
"""
import sqlite3
from pathlib import Path
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from app.utils.logger import get_logger
    logger = get_logger(__name__)
except:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./video_note.db")
# 处理相对路径和绝对路径
if DATABASE_URL.startswith("sqlite:///"):
    DB_PATH = DATABASE_URL.replace("sqlite:///", "")
    # 如果是相对路径，转换为绝对路径
    if not os.path.isabs(DB_PATH):
        DB_PATH = os.path.join(os.getcwd(), DB_PATH)
else:
    DB_PATH = DATABASE_URL


def migrate_add_screenshot_column():
    """Add missing columns to the video_tasks table."""
    if not Path(DB_PATH).exists():
        logger.info("Database does not exist yet; tables will be created on first run")
        return

    migrations = [
        ("screenshot", "ALTER TABLE video_tasks ADD COLUMN screenshot INTEGER DEFAULT 0"),
        ("error_message", "ALTER TABLE video_tasks ADD COLUMN error_message TEXT"),
        ("source", "ALTER TABLE video_tasks ADD COLUMN source TEXT NOT NULL DEFAULT 'upload'"),
        ("source_url", "ALTER TABLE video_tasks ADD COLUMN source_url TEXT"),
    ]

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(video_tasks)")
        columns = {column[1] for column in cursor.fetchall()}

        for column, statement in migrations:
            if column not in columns:
                logger.info(f"Adding {column} column to video_tasks...")
                cursor.execute(statement)
                conn.commit()
                logger.info(f"{column} column added")
            else:
                logger.info(f"{column} column already exists, skipping")

        conn.close()
    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        raise


if __name__ == "__main__":
    migrate_add_screenshot_column()

