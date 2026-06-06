from __future__ import annotations

from typing import Dict, List, Optional
from urllib.parse import urlsplit, urlunsplit


OPENAI_COMPATIBLE_PROVIDER_TYPES = {
    "openai",
    "deepseek",
    "qwen",
    "claude",
    "gemini",
    "groq",
    "ollama",
    "siliconflow",
    "moonshot",
    "openrouter",
    "zhipu",
    "volcengine",
    "custom",
}


BUILTIN_PROVIDER_TYPES: List[Dict[str, str]] = [
    {
        "id": "openai",
        "name": "OpenAI",
        "type": "built-in",
        "logo": "OpenAI",
        "default_base_url": "https://api.openai.com/v1",
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "type": "built-in",
        "logo": "DeepSeek",
        "default_base_url": "https://api.deepseek.com",
    },
    {
        "id": "qwen",
        "name": "Qwen",
        "type": "built-in",
        "logo": "Qwen",
        "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    {
        "id": "claude",
        "name": "Claude",
        "type": "built-in",
        "logo": "Claude",
        "default_base_url": "https://api.anthropic.com/v1",
    },
    {
        "id": "gemini",
        "name": "Gemini",
        "type": "built-in",
        "logo": "Gemini",
        "default_base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    },
    {
        "id": "groq",
        "name": "Groq",
        "type": "built-in",
        "logo": "Groq",
        "default_base_url": "https://api.groq.com/openai/v1",
    },
    {
        "id": "ollama",
        "name": "Ollama",
        "type": "built-in",
        "logo": "Ollama",
        "default_base_url": "http://127.0.0.1:11434/v1",
    },
    {
        "id": "siliconflow",
        "name": "SiliconFlow",
        "type": "built-in",
        "logo": "SiliconFlow",
        "default_base_url": "https://api.siliconflow.cn/v1",
    },
    {
        "id": "moonshot",
        "name": "Moonshot",
        "type": "built-in",
        "logo": "Moonshot",
        "default_base_url": "https://api.moonshot.cn/v1",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "type": "built-in",
        "logo": "OpenAI",
        "default_base_url": "https://openrouter.ai/api/v1",
    },
    {
        "id": "zhipu",
        "name": "Zhipu GLM",
        "type": "built-in",
        "logo": "OpenAI",
        "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
    },
    {
        "id": "volcengine",
        "name": "Volcengine Ark",
        "type": "built-in",
        "logo": "OpenAI",
        "default_base_url": "https://ark.cn-beijing.volces.com/api/v3",
    },
    {
        "id": "custom",
        "name": "Custom OpenAI",
        "type": "built-in",
        "logo": "OpenAI",
        "default_base_url": "",
    },
]


def provider_type_ids() -> set[str]:
    return {item["id"] for item in BUILTIN_PROVIDER_TYPES}


def normalize_provider_type(provider: str = "", provider_type: str = "openai") -> str:
    if provider_type and provider_type != "openai":
        return provider_type
    if provider in provider_type_ids():
        return provider
    return provider_type or "openai"


def default_base_url(provider_type: str) -> str:
    provider_config = next((item for item in BUILTIN_PROVIDER_TYPES if item["id"] == provider_type), None)
    if provider_config:
        return provider_config.get("default_base_url", "")
    return "https://api.openai.com/v1"


def normalize_base_url(provider_type: str, base_url: Optional[str]) -> str:
    final_base_url = (base_url or "").strip() or default_base_url(provider_type)
    if not final_base_url:
        return final_base_url

    parsed = urlsplit(final_base_url)
    has_scheme_and_host = bool(parsed.scheme and parsed.netloc)
    path = parsed.path.strip("/")
    if (
        provider_type in OPENAI_COMPATIBLE_PROVIDER_TYPES
        and has_scheme_and_host
        and not path
    ):
        final_base_url = urlunsplit((parsed.scheme, parsed.netloc, "/v1", "", ""))
    return final_base_url


def normalize_api_key(provider_type: str, api_key: Optional[str]) -> str:
    if provider_type == "ollama":
        return api_key or "ollama"
    return api_key or ""


def model_item(
    model_id: str,
    provider_type: str,
    provider_instance_id: str = "",
    name: Optional[str] = None,
) -> Dict[str, str]:
    return {
        "id": model_id,
        "name": name or model_id,
        "provider": provider_instance_id or provider_type,
        "provider_type": provider_type,
    }
