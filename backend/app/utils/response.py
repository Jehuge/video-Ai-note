from typing import Any, Optional
from pydantic import BaseModel


class ResponseWrapper:
    """统一响应包装器"""
    
    @staticmethod
    def success(data: Any = None, msg: str = "success", code: int = 200):
        return {
            "code": code,
            "msg": msg,
            "data": data
        }
    
    @staticmethod
    def error(msg: str = "error", code: int = 500, data: Any = None):
        return {
            "code": code,
            "msg": msg,
            "data": data
        }

