from dataclasses import dataclass
from app.models.transcriber_model import TranscriptResult


@dataclass
class NoteResult:
    """笔记结果"""
    markdown: str                    # GPT 总结的 Markdown 内容
    transcript: TranscriptResult     # 转录结果
    filename: str                   # 原始文件名

