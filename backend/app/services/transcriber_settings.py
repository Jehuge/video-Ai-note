from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Optional

from app.utils.app_paths import get_app_data_dir
from app.utils.logger import get_logger

logger = get_logger(__name__)


LOCAL_TRANSCRIBER_ID = "fast-whisper"

TRANSCRIBER_TYPES = {
    LOCAL_TRANSCRIBER_ID: {
        "id": LOCAL_TRANSCRIBER_ID,
        "name": "本地语音识别",
        "description": "使用源码内置的 faster-whisper 在本机转写音频，不调用语音识别 API。",
    },
}


def _settings_path() -> Path:
    path = get_app_data_dir() / "transcriber_config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def default_transcriber_config() -> Dict[str, str]:
    device = os.getenv("WHISPER_DEVICE", "cpu").strip() or "cpu"
    return {
        "type": LOCAL_TRANSCRIBER_ID,
        "model_size": os.getenv("WHISPER_MODEL_SIZE", "base").strip() or "base",
        "device": device,
        "compute_type": os.getenv(
            "WHISPER_COMPUTE_TYPE",
            "int8" if device == "cpu" else "float16",
        ).strip(),
    }


def normalize_transcriber_config(config: Optional[dict]) -> Dict[str, str]:
    """Normalize config to the local faster-whisper path.

    Older builds briefly allowed OpenAI-compatible speech APIs. The product
    direction is local speech recognition plus LLM-only note generation, so
    saved remote-STT configs are intentionally folded back to fast-whisper.
    """
    defaults = default_transcriber_config()
    config = config or {}

    payload = {
        "type": LOCAL_TRANSCRIBER_ID,
        "model_size": config.get("model_size", config.get("modelSize", defaults["model_size"])),
        "device": config.get("device", defaults["device"]),
        "compute_type": config.get("compute_type", config.get("computeType", defaults["compute_type"])),
    }

    normalized = {key: str(value or "").strip() for key, value in payload.items()}
    if normalized["device"] not in {"cpu", "cuda", "auto"}:
        normalized["device"] = defaults["device"]
    if not normalized["model_size"]:
        normalized["model_size"] = defaults["model_size"]
    if not normalized["compute_type"]:
        normalized["compute_type"] = defaults["compute_type"]

    return normalized


def load_transcriber_config() -> Dict[str, str]:
    path = _settings_path()
    if not path.exists():
        return default_transcriber_config()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return normalize_transcriber_config(data)
    except Exception as exc:
        logger.warning(f"Failed to read local transcriber config: {exc}")
        return default_transcriber_config()


def save_transcriber_config(config: dict) -> Dict[str, str]:
    current = load_transcriber_config()
    payload = normalize_transcriber_config({**current, **(config or {})})
    _settings_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Saved local faster-whisper config")
    return payload


def validate_transcriber_config(config: Optional[dict] = None) -> Optional[str]:
    raw = config or {}
    raw_device = str(raw.get("device", "")).strip()
    raw_model_size = str(raw.get("model_size", raw.get("modelSize", ""))).strip()
    raw_compute_type = str(raw.get("compute_type", raw.get("computeType", ""))).strip()

    if not raw_model_size:
        return "请选择本地识别模型大小"
    if raw_device and raw_device not in {"cpu", "cuda", "auto"}:
        return "设备只能选择 cpu、cuda 或 auto"
    if not raw_compute_type:
        return "请选择计算精度"

    payload = normalize_transcriber_config(config)
    if not payload.get("model_size"):
        return "请选择本地识别模型大小"
    if payload.get("device") not in {"cpu", "cuda", "auto"}:
        return "设备只能选择 cpu、cuda 或 auto"
    if not payload.get("compute_type"):
        return "请选择计算精度"
    return None


def public_transcriber_config(config: Optional[dict] = None) -> Dict[str, object]:
    payload = dict(config or load_transcriber_config())
    payload["local_only"] = True
    payload["has_api_key"] = False
    payload["api_key"] = ""
    payload["base_url"] = ""
    payload["model"] = ""
    return payload
