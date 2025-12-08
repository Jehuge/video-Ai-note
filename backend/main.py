import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from app.db.init_db import init_db
from app.exceptions.exception_handlers import register_exception_handlers
from app.utils.logger import get_logger
from app import create_app
from app.transcriber.transcriber_provider import get_transcriber

logger = get_logger(__name__)
load_dotenv()

# 创建必要的目录
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
NOTE_OUTPUT_DIR = os.getenv("NOTE_OUTPUT_DIR", "note_results")
STATIC_DIR = os.getenv("STATIC_DIR", "static")

for dir_path in [UPLOAD_DIR, NOTE_OUTPUT_DIR, STATIC_DIR]:
    Path(dir_path).mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 初始化数据库
    init_db()
    
    # 初始化转录器
    transcriber_type = os.getenv("TRANSCRIBER_TYPE", "fast-whisper")
    get_transcriber(transcriber_type=transcriber_type)
    
    logger.info("应用启动完成")
    yield
    logger.info("应用关闭")


app = create_app(lifespan=lifespan)

# CORS 配置
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册异常处理器
register_exception_handlers(app)

# 静态文件服务
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# note_results 目录服务（包含截图）
NOTE_OUTPUT_DIR = os.getenv("NOTE_OUTPUT_DIR", "note_results")
Path(NOTE_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
app.mount("/api/note_results", StaticFiles(directory=NOTE_OUTPUT_DIR), name="note_results")


if __name__ == "__main__":
    port = int(os.getenv("BACKEND_PORT", 8483))
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    logger.info(f"启动服务器 {host}:{port}")
    # 使用导入字符串以支持 reload
    uvicorn.run("main:app", host=host, port=port, reload=True)

