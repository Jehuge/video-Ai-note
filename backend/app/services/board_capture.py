# -*- coding: utf-8 -*-
"""
板书分页采集：把网课视频里的每一"页"板书完整截下来。

原理：按固定间隔抽帧，用缩略图差异判断画面是否翻页/清屏；
画面稳定后保留一帧代表图，并记录该页出现的时间段。
这样课件每一页（清屏前的完整板书）都能按时间线保留下来。
"""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List

from app.utils.ffmpeg_helper import get_ffmpeg_path
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BoardPage:
    """一页板书"""
    index: int            # 页序（从 0 开始）
    start: float          # 出现时间（秒）
    end: float            # 被下一页替换的时间（秒）
    image_path: str       # 代表帧图片路径


def _thumb_signature(image_path: str, size: tuple = (64, 36)) -> List[int]:
    """生成小尺寸灰度签名，用于快速比较两帧是否相似"""
    from PIL import Image

    with Image.open(image_path) as im:
        gray = im.convert("L").resize(size)
        return list(gray.getdata())


def _diff_ratio(a: List[int], b: List[int]) -> float:
    """平均绝对差异（0-255）"""
    total = sum(abs(x - y) for x, y in zip(a, b))
    return total / len(a)


def capture_board_pages(
    video_path: str,
    sample_interval: float = 20.0,
    diff_threshold: float = 8.0,
    max_pages: int = 60,
    out_dir: str = None,
) -> List[BoardPage]:
    """
    抽帧并按画面变化切分板书页。

    :param video_path: 视频文件
    :param sample_interval: 抽帧间隔（秒）
    :param diff_threshold: 画面差异阈值（0-255 平均绝对差），超过视为翻页
    :param max_pages: 最多保留页数（防止超长视频生成过多图片）
    :param out_dir: 截图输出目录
    :return: 按时间排序的 BoardPage 列表
    """
    out_dir = out_dir or str(Path(tempfile.gettempdir()) / "board_pages")
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    # 1) 定长抽帧
    sample_dir = Path(tempfile.mkdtemp(prefix="board_samples_"))
    cmd = [
        get_ffmpeg_path(), "-y",
        "-i", str(video_path),
        "-vf", f"fps=1/{sample_interval},scale=640:-1",
        "-q:v", "4",
        str(sample_dir / "f_%05d.jpg"),
    ]
    creation = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
    subprocess_run(cmd, creation)

    frames = sorted(sample_dir.glob("f_*.jpg"))
    if not frames:
        logger.warning("板书抽帧失败：未得到任何帧")
        return []
    logger.info(f"板书采样帧数: {len(frames)}（间隔 {sample_interval}s）")

    # 2) 逐帧比较，划分"页"：差异超阈值即新页；页内保留最中间的一帧为代表
    pages: List[BoardPage] = []
    current_group: List[Path] = [frames[0]]
    prev_sig = _thumb_signature(frames[0])

    def flush_group(group: List[Path], start_s: float, end_s: float):
        if not group:
            return
        rep = group[len(group) // 2]  # 页中间帧更稳定
        dest = Path(out_dir) / f"board_{start_s:.0f}s_{rep.name}"
        if not dest.exists():
            dest.write_bytes(rep.read_bytes())
        pages.append(BoardPage(index=len(pages), start=start_s, end=end_s, image_path=str(dest)))

    group_start = 0.0
    for i in range(1, len(frames)):
        frame_time = i * sample_interval
        sig = _thumb_signature(frames[i])
        diff = _diff_ratio(prev_sig, sig)
        prev_sig = sig
        if diff > diff_threshold and len(pages) + 1 < max_pages:
            flush_group(current_group, group_start, frame_time)
            current_group = [frames[i]]
            group_start = frame_time
        else:
            current_group.append(frames[i])
    flush_group(current_group, group_start, len(frames) * sample_interval)

    # 清理采样临时目录
    try:
        for f in sample_dir.iterdir():
            f.unlink()
        sample_dir.rmdir()
    except OSError:
        pass

    logger.info(f"板书分页完成: {len(pages)} 页（阈值 {diff_threshold}，间隔 {sample_interval}s）")
    return pages


def subprocess_run(cmd, creation: int):
    import subprocess
    kwargs = {"creationflags": creation} if creation else {}
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600, **kwargs)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 抽帧失败: {(result.stderr or '')[-300:]}")
