import json
from pathlib import Path
from typing import Optional

from app.utils.app_paths import get_app_data_dir
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _settings_path() -> Path:
    path = get_app_data_dir() / "active_model_config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def save_active_model_config(config: dict) -> dict:
    payload = {
        "provider": config.get("provider", ""),
        "provider_type": config.get("provider_type", config.get("providerType", "openai")),
        "api_key": config.get("api_key", config.get("apiKey", "")),
        "base_url": config.get("base_url", config.get("baseUrl", "")),
        "model": config.get("model", ""),
        "note_style": config.get("note_style", config.get("noteStyle", "simple")),
    }
    _settings_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Saved active model config for local app bridge")
    return payload


def load_active_model_config() -> Optional[dict]:
    path = _settings_path()
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not data.get("model"):
            return None
        return data
    except Exception as exc:
        logger.warning(f"Failed to read active model config: {exc}")
        return None
