from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from openai import OpenAI
import google.generativeai as genai
from google.api_core.exceptions import FailedPrecondition
from app.utils.response import ResponseWrapper as R
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# 内置提供商配置模版
# 这些是提供商类型定义，不再是单一的实例配置
BUILTIN_PROVIDER_TYPES = [
    {
        "id": "openai",
        "name": "OpenAI",
        "type": "built-in",
        "logo": "OpenAI",
        "default_base_url": "https://api.openai.com/v1"
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "type": "built-in",
        "logo": "DeepSeek",
        "default_base_url": "https://api.deepseek.com"
    },
    {
        "id": "qwen",
        "name": "Qwen",
        "type": "built-in",
        "logo": "Qwen",
        "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"
    },
    {
        "id": "claude",
        "name": "Claude",
        "type": "built-in",
        "logo": "Claude",
        "default_base_url": "https://api.anthropic.com/v1"
    },
    {
        "id": "gemini",
        "name": "Gemini",
        "type": "built-in",
        "logo": "Gemini",
        "default_base_url": "https://generativelanguage.googleapis.com/v1beta/openai/"
    },
    {
        "id": "groq",
        "name": "Groq",
        "type": "built-in",
        "logo": "Groq",
        "default_base_url": "https://api.groq.com/openai/v1"
    },
    {
        "id": "ollama",
        "name": "Ollama",
        "type": "built-in",
        "logo": "Ollama",
        "default_base_url": "http://127.0.0.1:11434/v1"
    },
    {
        "id": "siliconflow",
        "name": "SiliconFlow",
        "type": "built-in",
        "logo": "SiliconFlow", # Will map to siliconcloud-color.svg via alias if needed or direct match
        "default_base_url": "https://api.siliconflow.cn/v1"
    },
    # 添加一个通用的 OpenAI 兼容类型，供用户自定义其他厂商
    {
        "id": "custom",
        "name": "Custom OpenAI",
        "type": "built-in",
        "logo": "OpenAI", # 复用 OpenAI logo
        "default_base_url": ""
    }
]

class ModelConfigRequest(BaseModel):
    provider: str  # 实例 ID 或名称
    provider_type: str = "openai" # 提供商类型 (openai, deepseek, gemini, ollama, etc.)
    api_key: str
    base_url: str = None

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
        provider_type = config.provider_type
        # 兼容旧代码：如果 provider_type 未传且 provider 是已知类型之一，则推断 provider_type
        if provider_type == "openai" and config.provider in [p["id"] for p in BUILTIN_PROVIDER_TYPES if p["id"] != "custom"]:
             # 这里假设如果只传了 provider 且是 'gemini' 等，则它是旧逻辑
             # 但为了安全，我们应当优先信任 provider_type。
             # 只有当 provider_type 是默认值 'openai' 且 provider 是特殊类型（如 gemini）时才修正
             if config.provider == 'gemini':
                 provider_type = 'gemini'
             elif config.provider == 'ollama':
                 provider_type = 'ollama'
             # 其他如 deepseek 等其实都是 openai 兼容，所以 provider_type='openai' 或者 具体类型名 都可以
             # 为了逻辑统一，我们尽量通过 provider_type 判断
             # 如果前端更新了，会传正确的 provider_type
             pass

        if provider_type == 'gemini':
            return get_gemini_models(config.api_key)
        else:
            # 其他厂商都使用 OpenAI 兼容 API
            # 注意：provider 参数这里主要用于日志或特定类型的过滤 logic
            # 我们传递 provider_type 给 get_openai_compatible_models 以便它知道如何过滤
            effective_type = provider_type
            if effective_type == 'openai' and config.provider in ['deepseek', 'qwen', 'claude', 'groq', 'ollama']:
                 # 如果 provider_type 是默认的 openai，但 provider 是具体厂商名（旧逻辑兼容），则使用 provider 作为类型
                 effective_type = config.provider

            return get_openai_compatible_models(effective_type, config.api_key, config.base_url, config.provider)
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
        # 处理 API 密钥
        final_api_key = api_key
        if provider_type == 'ollama':
            # Ollama 本地服务，可以使用任意密钥
            final_api_key = api_key or 'ollama'
        elif not api_key:
            # 其他提供商必须有 API 密钥
            raise HTTPException(status_code=400, detail=f"{provider_type} 需要配置 API 密钥")

        # 处理 base_url
        final_base_url = base_url
        if not final_base_url:
            provider_config = next((p for p in BUILTIN_PROVIDER_TYPES if p["id"] == provider_type), None)
            if provider_config:
                final_base_url = provider_config.get("default_base_url", "")
            else:
                final_base_url = "https://api.openai.com/v1"

        # 创建客户端，显式禁用代理，避免 macOS 系统级代理设置干扰
        import httpx
        http_client = httpx.Client(proxy=None)  # 显式禁用代理
        client = OpenAI(api_key=final_api_key, base_url=final_base_url, http_client=http_client)

        # 获取模型列表
        models_response = client.models.list()

        # 处理模型列表
        chat_models = []
        for model in models_response.data:
            model_id = model.id

            # 根据提供商类型过滤和处理模型
            should_include = False

            if provider_type == 'openai':
                # 标准 OpenAI，过滤 gpt 模型
                # 但如果是自定义的 provider_type='openai'，可能用户希望看到所有模型?
                # 暂时保持过滤逻辑，但放宽一点
                should_include = any(keyword in model_id.lower() for keyword in ['gpt-4', 'gpt-3.5', 'gpt-4o', 'o1', 'o3'])
            elif provider_type == 'deepseek':
                should_include = 'deepseek' in model_id.lower()
            elif provider_type == 'qwen':
                should_include = 'qwen' in model_id.lower()
            elif provider_type == 'claude':
                should_include = 'claude' in model_id.lower()
            elif provider_type == 'groq':
                should_include = any(keyword in model_id.lower() for keyword in ['llama', 'mixtral', 'gemma'])
            elif provider_type == 'ollama':
                # Ollama 返回所有模型
                should_include = True
            elif provider_type == 'custom':
                 # 自定义类型，返回所有模型
                 should_include = True
            else:
                # 其他情况，默认返回所有模型，或者尝试兼容旧逻辑
                if provider_type == 'custom' or not provider_type:
                    should_include = True
                else:
                    # 尝试宽松匹配
                     should_include = True

            if should_include:
                chat_models.append({
                    "id": model_id,
                    "name": model_id,
                    "provider": provider_instance_id or provider_type, # 使用实例 ID
                    "provider_type": provider_type
                })

        if not chat_models:
            # 如果没有找到匹配的模型，返回所有可用模型
            for model in models_response.data:
                chat_models.append({
                    "id": model.id,
                    "name": model.id,
                    "provider": provider_instance_id or provider_type,
                    "provider_type": provider_type
                })

        return R.success(chat_models, msg=f"获取模型列表成功")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 {provider_type} 模型列表失败: {e}")
        # 提供更用户友好的错误信息
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
                chat_models.append({
                    "id": model_id,  # 提取模型名称
                    "name": model.display_name or model_id,
                    "provider": "gemini", # Gemini 目前可能还是像单例一样处理，或者前端传实例ID过来
                    "provider_type": "gemini"
                })
        
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
        provider_type = config.provider_type
        # 兼容逻辑
        if provider_type == "openai" and config.provider == 'gemini':
            provider_type = 'gemini'
        elif provider_type == "openai" and config.provider == 'ollama':
            provider_type = 'ollama'
        # 还有其他厂商的兼容..

        if provider_type == 'gemini':
            if not config.api_key:
                return R.error("Gemini 提供商需要配置 API 密钥")

            genai.configure(api_key=config.api_key)
            # 尝试列出模型来测试连接
            list(genai.list_models())
            return R.success(None, msg="Gemini 连接成功")
        else:
            # OpenAI 兼容 API
            final_api_key = config.api_key
            if provider_type == 'ollama':
                final_api_key = config.api_key or 'ollama'

            if not final_api_key and provider_type != 'ollama':
                return R.error(f"需要配置 API 密钥")

            final_base_url = config.base_url
            if not final_base_url:
                provider_config = next((p for p in BUILTIN_PROVIDER_TYPES if p["id"] == provider_type), None)
                if provider_config:
                    final_base_url = provider_config.get("default_base_url")
                else:
                    final_base_url = "https://api.openai.com/v1"

            # 创建客户端，显式禁用代理
            import httpx
            http_client = httpx.Client(proxy=None)
            client = OpenAI(api_key=final_api_key, base_url=final_base_url, http_client=http_client)
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
