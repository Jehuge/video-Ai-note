from dataclasses import dataclass
from typing import List, Optional


@dataclass
class TranscriptSegment:
    """转录片段"""
    start: float  # 开始时间（秒）
    end: float    # 结束时间（秒）
    text: str     # 该段文字


@dataclass
class TranscriptResult:
    """转录结果"""
    language: Optional[str]  # 检测语言（如 "zh"、"en"）
    full_text: str           # 完整合并后的文本
    segments: List[TranscriptSegment]  # 分段结构

