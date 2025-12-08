import os
from faster_whisper import WhisperModel
from app.transcriber.base import Transcriber
from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.utils.logger import get_logger

logger = get_logger(__name__)


class FastWhisperTranscriber(Transcriber):
    """使用 faster-whisper 进行音频转录"""
    
    def __init__(self, model_size: str = "base", device: str = "cpu"):
        """
        初始化转录器
        
        :param model_size: 模型大小 (tiny, base, small, medium, large)
        :param device: 设备 (cpu, cuda)
        """
        self.model_size = model_size
        self.device = device
        logger.info(f"初始化 FastWhisper 转录器: model_size={model_size}, device={device}")
        self.model = WhisperModel(model_size, device=device)
    
    def transcript(self, file_path: str) -> TranscriptResult:
        """转录音频文件"""
        logger.info(f"开始转录: {file_path}")
        
        segments, info = self.model.transcribe(
            file_path,
            beam_size=5,
            language=None,  # 自动检测语言
            vad_filter=True  # 启用语音活动检测
        )
        
        # 提取语言
        language = info.language
        
        # 处理分段
        transcript_segments = []
        full_text_parts = []
        
        for segment in segments:
            transcript_segments.append(
                TranscriptSegment(
                    start=segment.start,
                    end=segment.end,
                    text=segment.text.strip()
                )
            )
            full_text_parts.append(segment.text.strip())
        
        full_text = " ".join(full_text_parts)
        
        logger.info(f"转录完成: 语言={language}, 分段数={len(transcript_segments)}")
        
        return TranscriptResult(
            language=language,
            full_text=full_text,
            segments=transcript_segments
        )

