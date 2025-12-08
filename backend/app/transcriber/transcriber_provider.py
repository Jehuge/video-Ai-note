import os
from app.transcriber.base import Transcriber
from app.transcriber.fast_whisper import FastWhisperTranscriber
from app.utils.logger import get_logger

logger = get_logger(__name__)

# 支持的转录器类型
_transcribers = {
    "fast-whisper": FastWhisperTranscriber,
}


def get_transcriber(transcriber_type: str = "fast-whisper") -> Transcriber:
    """
    获取转录器实例
    
    :param transcriber_type: 转录器类型
    :return: Transcriber 实例
    """
    if transcriber_type not in _transcribers:
        raise ValueError(f"不支持的转录器类型: {transcriber_type}")
    
    transcriber_cls = _transcribers[transcriber_type]
    
    # 根据类型初始化
    if transcriber_type == "fast-whisper":
        model_size = os.getenv("WHISPER_MODEL_SIZE", "base")
        device = os.getenv("WHISPER_DEVICE", "cpu")
        return transcriber_cls(model_size=model_size, device=device)
    
    return transcriber_cls()

