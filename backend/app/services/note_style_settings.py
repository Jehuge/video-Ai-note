import copy
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.utils.app_paths import get_app_data_dir
from app.utils.logger import get_logger

logger = get_logger(__name__)

STYLE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

DEFAULT_NOTE_STYLES: List[Dict[str, Any]] = [
    {
        "id": "simple",
        "name": "简洁模式",
        "prompt": (
            "聚焦关键观点，删除重复和无关内容；使用短段落和列表，"
            "保留核心概念、结论与必要步骤。"
        ),
        "built_in": True,
        "enabled": True,
    },
    {
        "id": "detailed",
        "name": "详细模式",
        "prompt": (
            "尽可能保留视频中的例子、数据、参数和具体步骤；深入解释关键概念，"
            "使笔记在信息完整度上能够替代重新观看，并使用清晰的标题和列表。"
        ),
        "built_in": True,
        "enabled": True,
    },
    {
        "id": "academic",
        "name": "学术模式",
        "prompt": (
            "使用正式、客观的语言，强调因果关系、论证、证据和专业术语；"
            "按照背景、核心观点、证据与结论组织内容。"
        ),
        "built_in": True,
        "enabled": True,
    },
    {
        "id": "creative",
        "name": "创意模式",
        "prompt": (
            "在忠于事实的前提下提高可读性和表达力，突出关键时刻、洞察与启发，"
            "并使用生动但结构清晰的标题。"
        ),
        "built_in": True,
        "enabled": True,
    },
]


def _settings_path() -> Path:
    path = get_app_data_dir() / "note_style_settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def default_note_style_settings() -> Dict[str, Any]:
    return {
        "version": 1,
        "default_style_id": "simple",
        "styles": copy.deepcopy(DEFAULT_NOTE_STYLES),
    }


def validate_note_style_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(settings, dict):
        raise ValueError("笔记模式配置格式无效")

    styles = settings.get("styles")
    if not isinstance(styles, list) or not styles:
        raise ValueError("至少需要保留一个笔记模式")

    built_in_ids = {item["id"] for item in DEFAULT_NOTE_STYLES}
    normalized_styles: List[Dict[str, Any]] = []
    seen_ids = set()
    for item in styles:
        if not isinstance(item, dict):
            raise ValueError("笔记模式条目格式无效")

        style_id = str(item.get("id", "")).strip()
        name = str(item.get("name", "")).strip()
        prompt = str(item.get("prompt", "")).strip()
        if not STYLE_ID_PATTERN.fullmatch(style_id):
            raise ValueError(f"模式 ID 无效: {style_id or '空值'}")
        if style_id in seen_ids:
            raise ValueError(f"模式 ID 重复: {style_id}")
        if not name:
            raise ValueError(f"模式 {style_id} 的名称不能为空")
        if len(name) > 60:
            raise ValueError(f"模式 {style_id} 的名称不能超过 60 个字符")
        if not prompt:
            raise ValueError(f"模式 {name} 的提示词不能为空")
        if len(prompt) > 12000:
            raise ValueError(f"模式 {name} 的提示词不能超过 12000 个字符")

        is_built_in = bool(item.get("built_in", False))
        if style_id in built_in_ids and not is_built_in:
            raise ValueError(f"内置模式 {style_id} 不能改为自定义模式")
        if style_id not in built_in_ids and is_built_in:
            raise ValueError(f"自定义模式 {style_id} 不能标记为内置模式")

        seen_ids.add(style_id)
        normalized_styles.append({
            "id": style_id,
            "name": name,
            "prompt": prompt,
            "built_in": is_built_in,
            "enabled": bool(item.get("enabled", True)),
        })

    missing_built_ins = built_in_ids - seen_ids
    if missing_built_ins:
        raise ValueError(f"内置模式不能删除: {', '.join(sorted(missing_built_ins))}")

    enabled_ids = {item["id"] for item in normalized_styles if item["enabled"]}
    if not enabled_ids:
        raise ValueError("至少需要启用一个笔记模式")

    default_style_id = str(settings.get("default_style_id", "")).strip()
    if default_style_id not in enabled_ids:
        raise ValueError("默认模式必须存在且处于启用状态")

    return {
        "version": 1,
        "default_style_id": default_style_id,
        "styles": normalized_styles,
    }


def load_note_style_settings() -> Dict[str, Any]:
    path = _settings_path()
    if not path.exists():
        return default_note_style_settings()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return validate_note_style_settings(data)
    except Exception as exc:
        logger.warning("Failed to read note style settings: %s", exc)
        return default_note_style_settings()


def save_note_style_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    normalized = validate_note_style_settings(settings)
    _settings_path().write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("Saved %s note styles", len(normalized["styles"]))
    return normalized


def reset_builtin_note_styles() -> Dict[str, Any]:
    current = load_note_style_settings()
    custom_styles = [item for item in current["styles"] if not item["built_in"]]
    default_style_id = current["default_style_id"]
    enabled_style_ids = {
        item["id"]
        for item in current["styles"]
        if item["enabled"]
    }
    if default_style_id not in enabled_style_ids:
        default_style_id = "simple"
    return save_note_style_settings({
        "version": 1,
        "default_style_id": default_style_id,
        "styles": copy.deepcopy(DEFAULT_NOTE_STYLES) + custom_styles,
    })


def resolve_note_style(style_id: Optional[str] = None) -> Dict[str, Any]:
    settings = load_note_style_settings()
    selected_id = str(style_id or "").strip() or settings["default_style_id"]
    style = next(
        (item for item in settings["styles"] if item["id"] == selected_id and item["enabled"]),
        None,
    )
    if not style:
        raise ValueError(f"笔记模式不存在或已停用: {selected_id}")
    return copy.deepcopy(style)


def apply_note_style_snapshot(
    model_config: Optional[Dict[str, Any]] = None,
    style_id: Optional[str] = None,
    preserve_existing: bool = True,
) -> Dict[str, Any]:
    config = dict(model_config or {})
    requested_id = str(style_id or "").strip()
    selected_id = requested_id or str(config.get("note_style") or "").strip()

    if (
        preserve_existing
        and not requested_id
        and selected_id
        and selected_id == config.get("note_style")
        and str(config.get("note_style_prompt", "")).strip()
    ):
        config["note_style_name"] = str(config.get("note_style_name") or selected_id).strip()
        return config

    style = resolve_note_style(selected_id or None)
    config.update({
        "note_style": style["id"],
        "note_style_name": style["name"],
        "note_style_prompt": style["prompt"],
    })
    return config
