# -*- coding: utf-8 -*-
"""
日志工具
"""

import logging


def init_logger():
    """初始化日志配置"""
    level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s - %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger("BiliCrawler")
    logger.setLevel(level)
    
    # 禁用 httpx INFO 级别日志
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    return logger


logger = init_logger()
