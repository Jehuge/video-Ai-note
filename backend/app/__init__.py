from fastapi import FastAPI


def create_app(lifespan=None) -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="Video AI Note",
        description="简化版视频笔记生成工具",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # 注册路由
    from app.routers import note, model, bili_download
    
    app.include_router(note.router, prefix="/api", tags=["note"])
    app.include_router(model.router, prefix="/api", tags=["model"])
    app.include_router(bili_download.router, prefix="/api", tags=["bili"])
    
    return app
