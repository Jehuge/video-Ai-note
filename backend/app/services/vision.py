# -*- coding: utf-8 -*-
"""
视觉模型服务：读取视频帧里的板书/题目内容

网课里的题目大多写在屏幕/黑板上，纯语音转写拿不到。这里把截图帧发给
OpenAI 兼容的视觉模型（如 GLM-4V、Qwen-VL、GPT-4o 等），转录成文字，
让笔记真正包含题目内容。

注意：需要模型配置里填的是支持视觉（多模态）的模型；不支持时调用会失败，
调用方应静默跳过，不影响笔记生成。
"""

import base64
import os
import re
from pathlib import Path
from typing import Optional

from app.utils.logger import get_logger

logger = get_logger(__name__)

FRAME_PROMPT = (
    "这是网课视频的一帧画面（板书/课件/题目）。请只转录画面里实际写着的文字内容："
    "题目原文、公式、图形的文字说明。不要解释、不要总结、不要推断画面外的内容。\n"
    "输出格式要求：\n"
    "1. 公式一律用 Markdown 数学语法：独立公式用 $$公式$$，行内公式用 $公式$；"
    "禁止使用 \\( \\) \\[ \\] 定界符。\n"
    "2. 坐标轴的孤立字母（如 x、y、O）和箭头标记不要转录，只转录有实际含义的题目、公式和文字。\n"
    "3. 每个内容点单独一行。\n"
    "如果画面里没有可读的文字或公式，只输出：无"
)


def _client_from_config(model_config: Optional[dict]):
    """用与笔记生成一致的 provider 配置构造 OpenAI 客户端"""
    from openai import OpenAI
    from app.services.model_provider import (
        normalize_provider_type,
        normalize_api_key,
        normalize_base_url,
    )

    cfg = model_config or {}
    provider = cfg.get("provider", "openai")
    provider_type = normalize_provider_type(provider, cfg.get("provider_type", "openai"))
    api_key = normalize_api_key(provider_type, cfg.get("api_key", ""))
    base_url = normalize_base_url(provider_type, cfg.get("base_url", ""))
    model = os.getenv("AINOTE_VISION_MODEL") or cfg.get("vision_model") or cfg.get("model", "")

    if not model:
        return None, None
    client = OpenAI(api_key=api_key or "EMPTY", base_url=base_url or None, timeout=60)
    return client, model


def describe_frame(image_path: str, model_config: Optional[dict] = None, timeout: int = 60) -> Optional[str]:
    """
    转录一帧画面里的文字/公式。

    :param image_path: 截图文件路径
    :param model_config: 任务使用的模型配置（需要是视觉模型）
    :return: 画面文字描述；失败返回 None
    """
    try:
        client, model = _client_from_config(model_config)
        if client is None or not model:
            logger.info("未配置视觉模型，跳过板书识别")
            return None

        img_b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": FRAME_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                        },
                    ],
                }
            ],
            timeout=timeout,
        )
        text = (response.choices[0].message.content or "").strip() if response.choices else ""
        if not text or text == "无":
            return None
        # 兜底：把 \( \) 和 \[ \] 定界符统一转成 $ / $$（前端渲染器只认 $ 语法）
        text = re.sub(r"\\\((.+?)\\\)", r"$\1$", text, flags=re.DOTALL)
        text = re.sub(r"\\\[(.+?)\\\]", r"$$\1$$", text, flags=re.DOTALL)
        logger.info(f"板书识别成功 ({Path(image_path).name}): {text[:50]}...")
        return text
    except Exception as exc:
        logger.warning(f"板书识别失败（跳过）: {exc}")
        return None
