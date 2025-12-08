import subprocess
import os
import uuid
from pathlib import Path
from typing import Optional
from app.utils.logger import get_logger
from app.utils.ffmpeg_helper import get_ffmpeg_path

logger = get_logger(__name__)


def generate_screenshot(video_path: str, output_dir: str, timestamp: int, index: int) -> str:
    """
    使用 ffmpeg 生成截图，返回生成图片路径
    
    :param video_path: 视频文件路径
    :param output_dir: 输出目录
    :param timestamp: 时间戳（秒）
    :param index: 截图索引
    :return: 生成的截图文件路径
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"screenshot_{index:03d}_{uuid.uuid4().hex[:8]}.jpg"
    output_path = output_dir / filename

    ffmpeg_path = get_ffmpeg_path()
    command = [
        ffmpeg_path,
        "-ss", str(timestamp),
        "-i", str(video_path),
        "-frames:v", "1",
        "-q:v", "2",  # 高质量
        "-y",  # 覆盖已存在文件
        str(output_path)
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"截图生成成功: {output_path} (时间戳: {timestamp}秒)")
        return str(output_path)
    except subprocess.CalledProcessError as e:
        logger.error(f"生成截图失败: {e.stderr}")
        raise Exception(f"生成截图失败: {e.stderr}")



