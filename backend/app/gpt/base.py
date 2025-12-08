from abc import ABC, abstractmethod
from app.models.transcriber_model import TranscriptResult


class GPT(ABC):
    """GPT 基类"""
    
    @abstractmethod
    def summarize(self, transcript: TranscriptResult, filename: str = "") -> str:
        """
        根据转录内容生成笔记
        
        :param transcript: 转录结果
        :param filename: 文件名（可选）
        :return: Markdown 格式的笔记
        """
        pass

