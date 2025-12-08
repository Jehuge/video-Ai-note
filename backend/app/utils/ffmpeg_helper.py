"""
FFmpeg 工具模块
自动检测系统 ffmpeg，如果没有则使用 imageio-ffmpeg 提供的 ffmpeg
"""
import os
import shutil
import platform
from pathlib import Path
from typing import Optional
from app.utils.logger import get_logger

logger = get_logger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 优先使用环境变量中的 FFMPEG_BIN_DIR (由 app_entry.py 设置的用户可写目录)
ffmpeg_bin_env = os.getenv("FFMPEG_BIN_DIR")
if ffmpeg_bin_env:
    FFMPEG_DIR = Path(ffmpeg_bin_env)
else:
    FFMPEG_DIR = PROJECT_ROOT / "ffmpeg_bin"

try:
    FFMPEG_DIR.mkdir(parents=True, exist_ok=True)
except Exception as e:
    # 即使创建失败也继续，因为可能不需要下载 ffmpeg
    logger.warning(f"无法创建 ffmpeg 目录 {FFMPEG_DIR}: {e}")


def get_ffmpeg_path() -> str:
    """
    获取 ffmpeg 可执行文件路径
    优先级：
    1. 系统已安装的 ffmpeg
    2. 项目目录中的 ffmpeg（如果已下载）
    3. imageio-ffmpeg 提供的 ffmpeg（会自动下载）
    
    :return: ffmpeg 可执行文件路径
    """
    # 1. 首先检查系统是否已安装 ffmpeg
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        logger.info(f"使用系统 ffmpeg: {system_ffmpeg}")
        return system_ffmpeg
    
    # 2. 检查项目目录中是否有 ffmpeg
    system = platform.system().lower()
    if system == "windows":
        ffmpeg_exe = FFMPEG_DIR / "ffmpeg.exe"
    else:
        ffmpeg_exe = FFMPEG_DIR / "ffmpeg"
    
    if ffmpeg_exe.exists() and os.access(ffmpeg_exe, os.X_OK):
        logger.info(f"使用项目目录中的 ffmpeg: {ffmpeg_exe}")
        return str(ffmpeg_exe)
    
    # 3. 使用 imageio-ffmpeg 提供的 ffmpeg
    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        logger.info(f"使用 imageio-ffmpeg 提供的 ffmpeg: {ffmpeg_path}")
        
        # 可选：将 ffmpeg 复制到项目目录以便后续使用
        try:
            if system == "windows":
                target_path = FFMPEG_DIR / "ffmpeg.exe"
            else:
                target_path = FFMPEG_DIR / "ffmpeg"
            
            if not target_path.exists():
                shutil.copy2(ffmpeg_path, target_path)
                # 在 Unix 系统上确保可执行权限
                if system != "windows":
                    os.chmod(target_path, 0o755)
                logger.info(f"已将 ffmpeg 复制到项目目录: {target_path}")
        except Exception as e:
            logger.warning(f"复制 ffmpeg 到项目目录失败，但不影响使用: {e}")
        
        return ffmpeg_path
    except ImportError:
        logger.error("imageio-ffmpeg 未安装，请运行: pip install imageio-ffmpeg")
        raise ImportError(
            "未找到 ffmpeg。请安装 imageio-ffmpeg: pip install imageio-ffmpeg\n"
            "或者手动安装 ffmpeg: https://ffmpeg.org/download.html"
        )
    except Exception as e:
        logger.error(f"获取 ffmpeg 失败: {e}")
        raise Exception(f"无法获取 ffmpeg: {e}")


def check_ffmpeg_available() -> bool:
    """
    检查 ffmpeg 是否可用
    
    :return: True 如果可用，False 否则
    """
    try:
        ffmpeg_path = get_ffmpeg_path()
        # 验证 ffmpeg 是否真的可用
        import subprocess
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception as e:
        logger.warning(f"ffmpeg 不可用: {e}")
        return False
