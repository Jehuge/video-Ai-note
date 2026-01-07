# -*- coding: utf-8 -*-
"""
时间工具函数
"""

import time


def get_unix_timestamp() -> int:
    """
    获取当前Unix时间戳（秒）
    """
    return int(time.time())


def get_current_timestamp() -> int:
    """
    获取当前时间戳（13位毫秒）
    """
    return int(time.time() * 1000)
