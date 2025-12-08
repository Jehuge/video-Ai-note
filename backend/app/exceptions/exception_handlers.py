from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)


def register_exception_handlers(app: FastAPI):
    """注册全局异常处理器"""
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"未处理的异常: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "code": 500,
                "msg": str(exc),
                "data": None
            }
        )

