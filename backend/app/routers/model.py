from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import google.generativeai as genai
from google.api_core.exceptions import FailedPrecondition
from app.utils.response import ResponseWrapper as R
from app.utils.logger import get_logger
from app.services.model_settings import load_active_model_config, save_active_model_config
from app.services.openai_client import create_openai_client
from app.services.model_provider import (
    BUILTIN_PROVIDER_TYPES as SERVICE_BUILTIN_PROVIDER_TYPES,
    model_item,
    normalize_api_key,
    normalize_base_url,
    normalize_provider_type,
)

logger = get_logger(__name__)
router = APIRouter()

BUILTIN_PROVIDER_TYPES = SERVICE_BUILTIN_PROVIDER_TYPES

class ModelConfigRequest(BaseModel):
    provider: str  # 实例 ID 或名称
    provider_type: str = "openai" # 提供商类型 (openai, deepseek, gemini, ollama, etc.)
    api_key: str
    base_url: str = None
    model: str = ""
    note_style: str = "simple"

class ModelItem(BaseModel):
    id: str
    name: str
    provider: str # 实例 ID
    provider_type: str # 提供商类型

@router.get("/providers")
def get_providers():
    """获取所有可用的提供商类型列表"""
    # 为了兼容前端，我们将 default_base_url 映射为 base_url
    # 前端应该更新为使用 provider_type 和 default_base_url
    result = []
    for p in BUILTIN_PROVIDER_TYPES:
        item = p.copy()
        item["base_url"] = item.get("default_base_url", "")
        result.append(item)
    return R.success(result, msg="获取提供商列表成功")

@router.post("/models/list")
def get_model_list(config: ModelConfigRequest):
    """获取指定提供商的模型列表"""
    try:
        provider_type = normalize_provider_type(config.provider, config.provider_type)

        if provider_type == 'gemini' and not config.base_url:
            return get_gemini_models(config.api_key)
        else:
            return get_openai_compatible_models(provider_type, config.api_key, config.base_url, config.provider)
    except HTTPException as e:
        logger.warning(f"获取模型列表警告: {e.detail}")
        return R.error(e.detail)
    except Exception as e:
        import os
        logger.error(f"获取模型列表失败: {e} [Proxy Config: HTTP_PROXY={os.environ.get('HTTP_PROXY')}, HTTPS_PROXY={os.environ.get('HTTPS_PROXY')}]", exc_info=True)
        return R.error(f"获取模型列表失败: {str(e)}")

def get_openai_compatible_models(provider_type: str, api_key: str = "", base_url: str = "", provider_instance_id: str = ""):
    """获取 OpenAI 兼容 API 的模型列表"""
    try:
        final_api_key = normalize_api_key(provider_type, api_key)
        if not final_api_key:
            raise HTTPException(status_code=400, detail=f"{provider_type} 需要配置 API 密钥")

        final_base_url = normalize_base_url(provider_type, base_url)

        # 创建 OpenAI 兼容客户端；trust_env=False 禁用系统代理并兼容不同 httpx 版本。
        client = create_openai_client(api_key=final_api_key, base_url=final_base_url)

        # 获取模型列表
        models_response = client.models.list()

        chat_models = []
        for model in models_response.data:
            model_id = model.id
            if model_id:
                chat_models.append(model_item(model_id, provider_type, provider_instance_id))

        if not chat_models:
            raise HTTPException(status_code=400, detail="接口已连接，但没有返回任何模型")

        return R.success(chat_models, msg="获取模型列表成功")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 {provider_type} 模型列表失败: {e}")
        error_msg = str(e)
        if "Connection error" in error_msg:
            error_msg = "网络连接失败，请检查网络连接"
        elif "timeout" in error_msg.lower():
            error_msg = "连接超时，请检查网络连接"
        elif "unauthorized" in error_msg.lower() or "invalid" in error_msg.lower():
            error_msg = f"API密钥无效或已过期"
        elif "not found" in error_msg.lower():
            error_msg = f"API端点不存在"
        raise HTTPException(status_code=400, detail=f"获取模型列表失败: {error_msg}")

def get_gemini_models(api_key: str):
    """获取 Gemini 模型列表"""
    try:
        genai.configure(api_key=api_key)
        
        # 获取可用模型列表
        models = genai.list_models()
        
        # 过滤出生成模型
        chat_models = []
        for model in models:
            # 只包含生成模型
            if 'generateContent' in model.supported_generation_methods:
                model_id = model.name.split('/')[-1]
                chat_models.append(model_item(model_id, "gemini", "gemini", model.display_name or model_id))
        
        # 如果没有获取到模型，抛出异常
        if not chat_models:
            raise Exception("未找到任何可用的 Gemini 模型")

        return R.success(chat_models, msg="获取 Gemini 模型列表成功")
    except FailedPrecondition as e:
        # 处理 Gemini API 地域限制错误
        if "User location is not supported" in str(e):
            logger.warning(f"Gemini API 地域限制错误: {e}")
            raise HTTPException(status_code=400, detail="Gemini API 在您所在的地区不可用，请尝试使用其他 LLM 提供商")
        else:
            logger.error(f"Gemini API 错误: {e}")
            raise HTTPException(status_code=400, detail=f"Gemini API 错误: {str(e)}")
    except Exception as e:
        logger.error(f"获取 Gemini 模型列表失败: {e}")
        raise HTTPException(status_code=400, detail=f"获取 Gemini 模型列表失败: {str(e)}")

@router.post("/models/test")
def test_model_connection(config: ModelConfigRequest):
    """测试模型连接"""
    try:
        provider_type = normalize_provider_type(config.provider, config.provider_type)

        if provider_type == 'gemini' and not config.base_url:
            if not config.api_key:
                return R.error("Gemini 提供商需要配置 API 密钥")

            genai.configure(api_key=config.api_key)
            # 尝试列出模型来测试连接
            list(genai.list_models())
            return R.success(None, msg="Gemini 连接成功")
        else:
            final_api_key = normalize_api_key(provider_type, config.api_key)
            if not final_api_key:
                return R.error(f"需要配置 API 密钥")

            final_base_url = normalize_base_url(provider_type, config.base_url)

            # 创建 OpenAI 兼容客户端；trust_env=False 禁用系统代理并兼容不同 httpx 版本。
            client = create_openai_client(api_key=final_api_key, base_url=final_base_url)
            # 尝试获取模型列表来测试连接
            client.models.list()
            return R.success(None, msg=f"连接成功")

    except FailedPrecondition as e:
        # 处理 Gemini API 地域限制错误
        if "User location is not supported" in str(e):
            logger.warning(f"Gemini API 地域限制错误: {e}")
            return R.error("Gemini API 在您所在的地区不可用，请尝试使用其他 LLM 提供商")
        else:
            logger.error(f"Gemini API 错误: {e}")
            return R.error(f"Gemini API 错误: {str(e)}")
    except Exception as e:
        logger.error(f"测试连接失败: {e}", exc_info=True)
        # 提供更用户友好的错误信息
        error_msg = str(e)
        if "Connection error" in error_msg:
            error_msg = "网络连接失败，请检查网络连接或API密钥"
        elif "timeout" in error_msg.lower():
            error_msg = "连接超时，请检查网络连接"
        elif "unauthorized" in error_msg.lower() or "invalid" in error_msg.lower():
            error_msg = "API密钥无效或已过期"
        return R.error(f"连接失败: {error_msg}")


@router.get("/models/active")
def get_active_model_config():
    """Return the app-level model config used by extension-created tasks."""
    config = load_active_model_config()
    if not config:
        return R.success(None, msg="no active model config")
    safe_config = dict(config)
    if safe_config.get("api_key"):
        safe_config["api_key"] = "***"
    return R.success(safe_config)


@router.post("/models/active")
def set_active_model_config(config: ModelConfigRequest):
    """Persist the current app model config for background extension imports."""
    saved = save_active_model_config(config.model_dump())
    safe_config = dict(saved)
    if safe_config.get("api_key"):
        safe_config["api_key"] = "***"
    return R.success(safe_config, msg="active model config saved")
