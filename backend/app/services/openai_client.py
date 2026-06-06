from __future__ import annotations

from typing import Optional

import httpx
from openai import OpenAI


def create_openai_http_client(timeout: float = 60.0) -> httpx.Client:
    """Create a version-stable httpx client for OpenAI-compatible providers."""
    return httpx.Client(
        timeout=httpx.Timeout(timeout),
        trust_env=False,
    )


def create_openai_client(
    api_key: str,
    base_url: Optional[str] = None,
    timeout: float = 60.0,
) -> OpenAI:
    kwargs = {
        "api_key": api_key,
        "http_client": create_openai_http_client(timeout=timeout),
    }
    if base_url:
        kwargs["base_url"] = base_url.strip()
    return OpenAI(**kwargs)
