import os

from app.services.transcriber_settings import load_transcriber_config, normalize_transcriber_config
from app.transcriber.base import Transcriber
from app.transcriber.fast_whisper import FastWhisperTranscriber
from app.utils.logger import get_logger

logger = get_logger(__name__)


def get_transcriber(transcriber_type: str = None, config: dict = None) -> Transcriber:
    """Build the local speech recognizer.

    Speech recognition is intentionally local. LLM provider APIs are used only
    later, when the transcript is summarized into notes.
    """
    loaded_config = normalize_transcriber_config(config) if config else load_transcriber_config()

    requested_type = transcriber_type or loaded_config.get("type") or os.getenv("TRANSCRIBER_TYPE", "fast-whisper")
    if requested_type != "fast-whisper":
        logger.warning("Ignoring remote transcriber type %s; using local faster-whisper", requested_type)

    return FastWhisperTranscriber(
        model_size=loaded_config.get("model_size") or os.getenv("WHISPER_MODEL_SIZE", "base"),
        device=loaded_config.get("device") or os.getenv("WHISPER_DEVICE", "cpu"),
        compute_type=loaded_config.get("compute_type") or None,
    )
