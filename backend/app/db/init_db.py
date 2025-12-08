from app.db.engine import Base, engine
from app.db.migrate import migrate_add_screenshot_column
from app.utils.logger import get_logger

logger = get_logger(__name__)


def init_db():
    """初始化数据库，创建所有表"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("数据库表创建完成")
        
        # 执行迁移
        migrate_add_screenshot_column()
        
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise

