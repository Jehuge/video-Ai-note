from fastapi import FastAPI

from .routers import note


def create_app(lifespan) -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="Video AI Note",
        description="简化版视频笔记生成工具",
        version="1.0.0",
        lifespan=lifespan
    )
    
    app.include_router(note.router, prefix="/api")
    
    return app

