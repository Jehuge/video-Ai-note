# -*- coding: utf-8 -*-
"""
FunASR 本地转写引擎（Paraformer + fsmn-vad + ct-punc 三模型管线）

针对中文课程视频（数学、物理等）优化：
- 中文识别准确率高于 Whisper 同量级模型
- CPU 上速度明显更快（60s 音频转写约 3-5s，不含模型加载）
- VAD 切分提供句级时间戳
- 支持热词：把"导数、圆锥曲线、洛伦兹力"等课程术语加入热词可显著提升专有名词准确率
- 模型从 ModelScope（国内镜像）下载，不走 HuggingFace
"""

import os
import re
from typing import List

from app.transcriber.base import Transcriber
from app.models.transcriber_model import TranscriptResult, TranscriptSegment
from app.utils.logger import get_logger

logger = get_logger(__name__)

# 预置的理科课程热词，用户可在设置里自定义覆盖
DEFAULT_HOTWORDS = "导数 圆锥曲线 抛物线 双曲线 椭圆 函数 单调性 极值 点差法 韦达定理 阿基米德三角形 焦点弦 准线 离心率 洛伦兹力 安培力 电磁感应 加速度 动量 势能 傅里叶变换 楞次定律 牛顿第二定律"

_RICH_TAG = re.compile(r"<\|[^|]*\|>")

ASR_MODEL = os.getenv("FUNASR_MODEL", "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch")
VAD_MODEL = os.getenv("FUNASR_VAD_MODEL", "fsmn-vad")
PUNC_MODEL = os.getenv("FUNASR_PUNC_MODEL", "ct-punc")


class SenseVoiceTranscriber(Transcriber):
    """基于 FunASR 的本地转写：VAD 切分 + Paraformer 识别 + 标点恢复"""

    def __init__(self, model: str = None, device: str = "cpu", hotwords: str = None, **kwargs):
        self.model_name = model or ASR_MODEL
        self.device = device or "cpu"
        self.hotwords = (hotwords if hotwords is not None else os.getenv("FUNASR_HOTWORDS", "")) or DEFAULT_HOTWORDS
        self._asr = None
        self._vad = None
        self._punc = None
        logger.info(f"配置 FunASR 转录器: model={self.model_name}, device={self.device}")

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device in ("cuda", "auto"):
            try:
                import torch
                if not torch.cuda.is_available():
                    logger.warning("CUDA 不可用，FunASR 自动回退到 CPU")
                    return "cpu"
            except Exception:
                return "cpu"
        return device

    def _lazy_load(self):
        if self._asr is not None:
            return
        from funasr import AutoModel

        device = self._resolve_device(self.device)
        logger.info(f"正在加载 FunASR 模型 (device={device}, 首次使用需从 ModelScope 下载)...")
        self._asr = AutoModel(
            model=self.model_name,
            device=device,
            disable_update=True,
            disable_pbar=True,
        )
        self._vad = AutoModel(model=VAD_MODEL, device=device, disable_update=True, disable_pbar=True)
        self._punc = AutoModel(model=PUNC_MODEL, device=device, disable_update=True, disable_pbar=True)
        logger.info("FunASR 模型加载完成")

    def transcript(self, file_path: str) -> TranscriptResult:
        logger.info(f"开始转录 (FunASR): {file_path}")
        try:
            self._lazy_load()

            import librosa
            wave, _ = librosa.load(file_path, sr=16000, mono=True)
            duration = len(wave) / 16000.0
            logger.info(f"音频时长: {duration:.1f}s")

            # 1) VAD 切分语音段（毫秒）
            vad_res = self._vad.generate(input=wave, batch_size_s=300)
            spans = (vad_res[0].get("value") if vad_res and vad_res[0].get("value") else None) or [[0, int(duration * 1000)]]

            # 2) 逐段识别 + 3) 标点恢复
            segments: List[TranscriptSegment] = []
            hotword = self.hotwords.strip() or None
            for start_ms, end_ms in spans:
                # 16kHz 采样：每毫秒 16 个样本
                chunk = wave[int(start_ms) * 16: int(end_ms) * 16]
                if chunk.size == 0:
                    continue
                asr_res = self._asr.generate(input=chunk, hotword=hotword)
                text = _RICH_TAG.sub("", (asr_res[0].get("text", "") if asr_res else "")).strip()
                if not text:
                    continue
                try:
                    punc_res = self._punc.generate(input=text)
                    if punc_res and punc_res[0].get("text"):
                        text = _RICH_TAG.sub("", punc_res[0]["text"]).strip()
                except Exception as e:
                    logger.warning(f"标点恢复失败（跳过）: {e}")
                segments.append(
                    TranscriptSegment(
                        start=start_ms / 1000.0,
                        end=end_ms / 1000.0,
                        text=text,
                    )
                )

            full_text = "".join(s.text for s in segments)
            if not full_text:
                raise RuntimeError("未识别到有效语音")

            logger.info(f"转录完成: 分段数={len(segments)}, 总字数={len(full_text)}")
            return TranscriptResult(language="zh", full_text=full_text, segments=segments)
        except Exception as exc:
            logger.error(f"FunASR 转录失败: {file_path}, 错误: {exc}", exc_info=True)
            raise RuntimeError(self._friendly_error(exc)) from exc

    def _friendly_error(self, exc: Exception) -> str:
        message = str(exc)
        lower_message = message.lower()
        if any(keyword in lower_message for keyword in ["connection", "download", "modelscope", "timeout", "网络"]):
            return (
                "本地语音识别失败：首次使用 FunASR 模型需要从 ModelScope 下载（约 1GB），"
                "请检查网络后重试，或在设置里切换回 faster-whisper 引擎。"
            )
        if any(keyword in lower_message for keyword in ["out of memory", "memory"]):
            return "本地语音识别失败：内存不足。请关闭其他大内存程序后重试。"
        if any(keyword in lower_message for keyword in ["cuda", "cublas", "cudnn"]):
            return "本地语音识别失败：CUDA/GPU 不可用。请在设置里把运行设备改为 CPU。"
        if "未识别到有效语音" in message:
            return "本地语音识别没有识别到有效语音。请确认视频有清晰人声。"
        return f"本地语音识别失败：{message[:300]}"
