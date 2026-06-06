import os
from faster_whisper import WhisperModel
from app.transcriber.base import Transcriber
from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.utils.logger import get_logger

logger = get_logger(__name__)


class FastWhisperTranscriber(Transcriber):
    """使用 faster-whisper 进行音频转录"""
    
    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = None):
        """
        初始化转录器
        
        :param model_size: 模型大小 (tiny, base, small, medium, large)
        :param device: 设备 (cpu, cuda)
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type or os.getenv(
            "WHISPER_COMPUTE_TYPE",
            "int8" if device == "cpu" else "float16",
        )
        self._model = None
        logger.info(
            f"配置 FastWhisper 转录器: model_size={model_size}, device={device}, compute_type={self.compute_type}"
        )
    
    @property
    def model(self):
        if self._model is None:
            logger.info(
                f"正在加载 FastWhisper 模型: {self.model_size} (device={self.device}, compute_type={self.compute_type})..."
            )
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info("FastWhisper 模型加载完成")
        return self._model

    def transcript(self, file_path: str) -> TranscriptResult:
        """转录音频文件"""
        logger.info(f"开始转录: {file_path}")

        try:
            segments, info = self.model.transcribe(
                file_path,
                beam_size=5,
                language=None,  # 自动检测语言
                vad_filter=True,  # 启用语音活动检测
            )

            # 提取语言
            language = info.language
            logger.info(
                f"FastWhisper 已识别语言: {language}, 音频时长={getattr(info, 'duration', 0):.2f}s"
            )

            # 处理分段
            transcript_segments = []
            full_text_parts = []

            for segment in segments:
                text = segment.text.strip()
                if not text:
                    continue
                transcript_segments.append(
                    TranscriptSegment(
                        start=segment.start,
                        end=segment.end,
                        text=text,
                    )
                )
                full_text_parts.append(text)

            full_text = " ".join(full_text_parts)

            logger.info(f"转录完成: 语言={language}, 分段数={len(transcript_segments)}")

            return TranscriptResult(
                language=language,
                full_text=full_text,
                segments=transcript_segments,
            )
        except Exception as exc:
            logger.error(f"FastWhisper 转录失败: {file_path}, 错误: {exc}", exc_info=True)
            raise RuntimeError(self._friendly_error(exc)) from exc

    def _friendly_error(self, exc: Exception) -> str:
        message = str(exc)
        lower_message = message.lower()
        if any(keyword in lower_message for keyword in ["cuda", "cublas", "cudnn"]):
            return "本地语音识别失败：CUDA/GPU 不可用或驱动不匹配。请在设置里把运行设备改为 CPU，并使用 int8。"
        if any(keyword in lower_message for keyword in ["out of memory", "memory", "bad allocation"]):
            return "本地语音识别失败：内存不足。请在设置里调小模型，例如 tiny/base，并使用 int8。"
        if any(keyword in lower_message for keyword in ["connection", "download", "huggingface", "resolve"]):
            return "本地语音识别模型加载失败：首次使用需要下载 faster-whisper 模型，请检查网络，或改用已缓存的模型大小。"
        if "no such file" in lower_message or "not found" in lower_message:
            return f"本地语音识别失败：找不到音频文件或模型文件。原始错误：{message}"
        return f"本地语音识别失败：{message}"
