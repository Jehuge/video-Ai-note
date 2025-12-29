from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import google.generativeai as genai
from google.api_core.exceptions import FailedPrecondition
from app.utils.response import ResponseWrapper as R
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# 内置提供商配置
BUILTIN_PROVIDERS = [
    {
        "id": "openai",
        "name": "OpenAI",
        "type": "built-in",
        "logo": "OpenAI",
        "base_url": "https://api.openai.com/v1"
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "type": "built-in",
        "logo": "DeepSeek",
        "base_url": "https://api.deepseek.com"
    },
    {
        "id": "qwen",
        "name": "Qwen",
        "type": "built-in",
        "logo": "Qwen",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"
    },
    {
        "id": "claude",
        "name": "Claude",
        "type": "built-in",
        "logo": "Claude",
        "base_url": "https://api.anthropic.com/v1"
    },
    {
        "id": "gemini",
        "name": "Gemini",
        "type": "built-in",
        "logo": "Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/"
    },
    {
        "id": "groq",
        "name": "Groq",
        "type": "built-in",
        "logo": "Groq",
        "base_url": "https://api.groq.com/openai/v1"
    },
    {
        "id": "ollama",
        "name": "Ollama",
        "type": "built-in",
        "logo": "Ollama",
        "base_url": "http://127.0.0.1:11434/v1"
    }
]

class ModelConfigRequest(BaseModel):
    provider: str
    api_key: str
    base_url: str = None

class ModelItem(BaseModel):
    id: str
    name: str
    provider: str

@router.get("/providers")
def get_providers():
    """获取所有可用的提供商列表"""
    return R.success(BUILTIN_PROVIDERS, msg="获取提供商列表成功")

@router.post("/models/list")
def get_model_list(config: ModelConfigRequest):
    """获取指定提供商的模型列表"""
    try:
        if config.provider == 'gemini':
            return get_gemini_models(config.api_key)
        else:
            # 其他厂商都使用 OpenAI 兼容 API
            return get_openai_compatible_models(config.provider, config.api_key, config.base_url)
    except Exception as e:
        logger.error(f"获取模型列表失败: {e}", exc_info=True)
        return R.error(f"获取模型列表失败: {str(e)}")

def get_openai_compatible_models(provider: str, api_key: str = "", base_url: str = ""):
    """获取 OpenAI 兼容 API 的模型列表"""
    try:
        # 处理 API 密钥
        final_api_key = api_key
        if provider == 'ollama':
            # Ollama 本地服务，可以使用任意密钥
            final_api_key = api_key or 'ollama'
        elif not api_key:
            # 其他提供商必须有 API 密钥
            raise HTTPException(status_code=400, detail=f"{provider} 提供商需要配置 API 密钥")

        # 处理 base_url
        final_base_url = base_url
        if not final_base_url:
            provider_config = next((p for p in BUILTIN_PROVIDERS if p["id"] == provider), None)
            if provider_config:
                final_base_url = provider_config.get("base_url", "")
            else:
                final_base_url = "https://api.openai.com/v1"

        # 创建客户端
        client = OpenAI(api_key=final_api_key, base_url=final_base_url)

        # 获取模型列表
        models_response = client.models.list()

        # 处理模型列表
        chat_models = []
        for model in models_response.data:
            model_id = model.id

            # 根据提供商过滤和处理模型
            should_include = False

            if provider == 'openai':
                should_include = any(keyword in model_id.lower() for keyword in ['gpt-4', 'gpt-3.5', 'gpt-4o'])
            elif provider == 'deepseek':
                should_include = 'deepseek' in model_id.lower()
            elif provider == 'qwen':
                should_include = 'qwen' in model_id.lower()
            elif provider == 'claude':
                should_include = 'claude' in model_id.lower()
            elif provider == 'groq':
                should_include = any(keyword in model_id.lower() for keyword in ['llama', 'mixtral', 'gemma'])
            elif provider == 'ollama':
                # Ollama 返回所有模型
                should_include = True
            else:
                # 其他提供商，返回所有模型
                should_include = True

            if should_include:
                chat_models.append({
                    "id": model_id,
                    "name": model_id,
                    "provider": provider
                })

        if not chat_models:
            # 如果没有找到匹配的模型，返回所有可用模型
            for model in models_response.data:
                chat_models.append({
                    "id": model.id,
                    "name": model.id,
                    "provider": provider
                })

        return R.success(chat_models, msg=f"获取 {provider} 模型列表成功")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 {provider} 模型列表失败: {e}")
        # 提供更用户友好的错误信息
        error_msg = str(e)
        if "Connection error" in error_msg:
            error_msg = "网络连接失败，请检查网络连接"
        elif "timeout" in error_msg.lower():
            error_msg = "连接超时，请检查网络连接"
        elif "unauthorized" in error_msg.lower() or "invalid" in error_msg.lower():
            error_msg = f"{provider} API密钥无效或已过期"
        elif "not found" in error_msg.lower():
            error_msg = f"{provider} API端点不存在"
        raise HTTPException(status_code=400, detail=f"获取 {provider} 模型列表失败: {error_msg}")

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
                chat_models.append({
                    "id": model.name.split('/')[-1],  # 提取模型名称
                    "name": model.display_name or model.name.split('/')[-1],
                    "provider": "gemini"
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
        if config.provider == 'gemini':
            if not config.api_key:
                return R.error("Gemini 提供商需要配置 API 密钥")

            genai.configure(api_key=config.api_key)
            # 尝试列出模型来测试连接
            list(genai.list_models())
            return R.success(None, msg="Gemini 连接成功")
        else:
            # OpenAI 兼容 API
            final_api_key = config.api_key
            if config.provider == 'ollama':
                final_api_key = config.api_key or 'ollama'

            if not final_api_key and config.provider != 'ollama':
                return R.error(f"{config.provider} 提供商需要配置 API 密钥")

            final_base_url = config.base_url
            if not final_base_url:
                provider_config = next((p for p in BUILTIN_PROVIDERS if p["id"] == config.provider), None)
                if provider_config:
                    final_base_url = provider_config.get("base_url")
                else:
                    final_base_url = "https://api.openai.com/v1"

            client = OpenAI(api_key=final_api_key, base_url=final_base_url)
            # 尝试获取模型列表来测试连接
            client.models.list()
            return R.success(None, msg=f"{config.provider} 连接成功")

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
