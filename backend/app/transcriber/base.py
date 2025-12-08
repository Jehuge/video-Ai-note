from abc import ABC, abstractmethod
from app.models.transcriber_model import TranscriptResult


class Transcriber(ABC):
    """转录器基类"""
    
    @abstractmethod
    def transcript(self, file_path: str) -> TranscriptResult:
        """
        转录音频文件
        
        :param file_path: 音频文件路径
        :return: TranscriptResult 对象
        """
        pass

