import os
import sys
import uvicorn
import multiprocessing
import imageio_ffmpeg
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import Request
import socket
import threading
import webview
import time

# --- 关键修复：设置用户可写的数据目录 ---
try:
    user_home = Path.home()
    app_data_dir = user_home / "Documents" / "VideoNoteAI_Data"
    app_data_dir.mkdir(parents=True, exist_ok=True)

    os.environ["UPLOAD_DIR"] = str(app_data_dir / "uploads")
    os.environ["NOTE_OUTPUT_DIR"] = str(app_data_dir / "note_results")
    os.environ["STATIC_DIR"] = str(app_data_dir / "static")
    os.environ["FFMPEG_BIN_DIR"] = str(app_data_dir / "ffmpeg_bin")
    os.environ["DATABASE_URL"] = f"sqlite:///{app_data_dir}/video_note.db"
    os.environ["HF_HOME"] = str(app_data_dir / "cache" / "huggingface")
    
    (app_data_dir / "uploads").mkdir(exist_ok=True)
    (app_data_dir / "ffmpeg_bin").mkdir(exist_ok=True)
    (app_data_dir / "note_results").mkdir(exist_ok=True)
    (app_data_dir / "static").mkdir(exist_ok=True)
    (app_data_dir / "cache").mkdir(exist_ok=True)

    log_file = app_data_dir / "app_debug.log"
    sys.stdout = open(log_file, "a", encoding="utf-8", buffering=1)
    sys.stderr = open(log_file, "a", encoding="utf-8", buffering=1)
    
    print(f"\n{'='*50}")
    print(f"Application starting at {os.environ.get('Current_Time', '')}")
    print(f"Data directory: {app_data_dir}")
except Exception as e:
    pass

# --- End of Fix ---

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from main import app, logger
except Exception as e:
    print(f"Critical error importing main: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

try:
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    print(f"Found ffmpeg at: {ffmpeg_exe}")
    ffmpeg_dir = os.path.dirname(ffmpeg_exe)
    os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ["PATH"]
except Exception as e:
    print(f"Failed to setup ffmpeg path: {e}")

frontend_dist = get_resource_path("dist")

if os.path.exists(frontend_dist):
    logger.info(f"Mounting frontend from {frontend_dist}")
    
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    
    @app.middleware("http")
    async def spa_fallback(request: Request, call_next):
        response = await call_next(request)
        if response.status_code == 404 and not request.url.path.startswith("/api"):
            file_path = os.path.join(frontend_dist, request.url.path.lstrip("/"))
            if os.path.exists(file_path) and os.path.isfile(file_path):
                 return FileResponse(file_path)
            index_path = os.path.join(frontend_dist, "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path)
        return response
else:
    logger.warning(f"Frontend dist directory not found at {frontend_dist}")

class ServerThread(threading.Thread):
    def __init__(self, app, host, port):
        super().__init__()
        self.server = uvicorn.Server(config=uvicorn.Config(
            app=app, 
            host=host, 
            port=port, 
            log_level="info",
            loop="asyncio"
        ))
    
    def run(self):
        self.server.run()
    
    def stop(self):
        self.server.should_exit = True

def check_port(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0

def main():
    multiprocessing.freeze_support()
    
    port = int(os.getenv("BACKEND_PORT", 8483))
    host = "127.0.0.1"
    
    url = f"http://localhost:{port}"
    print(f"Starting server at {url}")
    
    # 启动服务器线程
    server_thread = ServerThread(app, host, port)
    server_thread.start()
    
    # 等待服务器启动
    # 虽然 pywebview 会一直加载，但最好确保端口可达
    # 不过为了响应速度，我们可以直接打开窗口
    
    # 创建 PyWebView 窗口
    window = webview.create_window(
        title='Video Note AI', 
        url=url, 
        width=1280, 
        height=800,
        resizable=True
    )
    
    # 启动 GUI 循环
    # 这会阻塞主线程，直到窗口关闭
    webview.start(debug=False)
    
    # 窗口关闭后清理
    print("Stopping server...")
    if server_thread.is_alive():
        server_thread.stop()
        server_thread.join(timeout=3)
    sys.exit(0)

if __name__ == "__main__":
    main()
