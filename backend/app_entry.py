import os
import sys
import multiprocessing

multiprocessing.freeze_support()

import uvicorn
import imageio_ffmpeg
import subprocess
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import Request
import socket
import threading
import webview
import time
import webbrowser

_instance_lock_socket = None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure user-writable data paths for packaged Windows/macOS apps.
try:
    from app.utils.app_paths import configure_app_environment
    app_data_dir = configure_app_environment()

    log_file = app_data_dir / "app_debug.log"
    sys.stdout = open(log_file, "a", encoding="utf-8", buffering=1)
    sys.stderr = open(log_file, "a", encoding="utf-8", buffering=1)
    
    print(f"\n{'='*50}")
    print(f"Application starting at {os.environ.get('Current_Time', '')}")
    print(f"Data directory: {app_data_dir}")
except Exception as e:
    pass

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


def ensure_playwright_chromium():
    """Install Playwright Chromium into the user data dir when it is missing."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser.close()
        print("Playwright Chromium is available")
    except Exception as first_error:
        first_line = str(first_error).strip().splitlines()[0] if str(first_error).strip() else repr(first_error)
        print(f"Playwright Chromium is missing, attempting install: {first_line}")
        try:
            from playwright._impl._driver import compute_driver_executable, get_driver_env

            driver_executable, driver_cli = compute_driver_executable()
            result = subprocess.run(
                [driver_executable, driver_cli, "install", "chromium"],
                capture_output=True,
                text=True,
                check=False,
                env=get_driver_env(),
                timeout=600,
            )
            if result.returncode == 0:
                print("Playwright Chromium install completed")
            else:
                stderr_tail = (result.stderr or result.stdout or "").strip().splitlines()[-3:]
                print(f"Playwright Chromium install returned {result.returncode}: {' | '.join(stderr_tail)}")
        except subprocess.TimeoutExpired:
            print("Playwright Chromium install timed out; app will continue without browser automation")
        except Exception as install_error:
            print(f"Failed to install Playwright Chromium: {install_error}")


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


def acquire_single_instance_lock(app_port):
    """Keep only one packaged desktop app process alive per user session."""
    global _instance_lock_socket
    lock_port = int(os.getenv("AINOTE_LOCK_PORT", str(app_port + 10000)))
    lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            lock_socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            lock_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        lock_socket.bind(("127.0.0.1", lock_port))
        lock_socket.listen(1)
        _instance_lock_socket = lock_socket
        return True
    except OSError:
        lock_socket.close()
        return False


def ensure_window_visible(window, url):
    """Bring the desktop UI forward or open a browser fallback if WebView is hidden."""
    try:
        if window.events.shown.wait(8):
            print("PyWebView window shown")
            try:
                window.restore()
                window.show()
                window.on_top = False
            except Exception as show_error:
                print(f"Window show/restore failed: {show_error}")
            return

        print("PyWebView window was not shown within 8 seconds; opening browser fallback")
        webbrowser.open(url)
    except Exception as error:
        print(f"Window visibility check failed: {error}")
        try:
            webbrowser.open(url)
        except Exception as browser_error:
            print(f"Browser fallback failed: {browser_error}")

def main():
    port = int(os.getenv("BACKEND_PORT", 8483))
    host = "127.0.0.1"
    server_thread = None
    
    url = f"http://localhost:{port}"
    print(f"Starting server at {url}")

    if not acquire_single_instance_lock(port):
        print("Another Video Note AI instance is already running; exiting.")
        sys.exit(0)
    
    # 启动服务器线程
    if check_port(host, port):
        print(f"Existing Video Note AI server detected at {url}")
    else:
        server_thread = ServerThread(app, host, port)
        server_thread.start()
        threading.Thread(target=ensure_playwright_chromium, daemon=True).start()
    
    # 等待服务器启动
    # 虽然 pywebview 会一直加载，但最好确保端口可达
    # 不过为了响应速度，我们可以直接打开窗口
    
    # 创建 PyWebView 窗口
    window = webview.create_window(
        title='Video Note AI', 
        url=url, 
        width=1280, 
        height=800,
        resizable=True,
        hidden=False,
        focus=True,
        on_top=True,
    )
    
    # 启动 GUI 循环
    # 这会阻塞主线程，直到窗口关闭
    webview.start(ensure_window_visible, args=(window, url), debug=False)
    
    # 窗口关闭后清理
    print("Stopping server...")
    if server_thread and server_thread.is_alive():
        server_thread.stop()
        server_thread.join(timeout=3)
    sys.exit(0)

if __name__ == "__main__":
    main()
