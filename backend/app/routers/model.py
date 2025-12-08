from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import google.generativeai as genai
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

def get_openai_compatible_models(provider: str, api_key: str, base_url: str = None):
    """获取 OpenAI 兼容 API 的模型列表（OpenAI, DeepSeek, Qwen, Claude, Groq, Ollama 等）"""
    try:
        # Ollama 不需要 API Key
        if provider == 'ollama':
            api_key = api_key or 'ollama'  # Ollama 可以使用任意值或空值
        
        # 如果没有提供 base_url，从内置配置中查找
        if not base_url:
            provider_config = next((p for p in BUILTIN_PROVIDERS if p["id"] == provider), None)
            if provider_config:
                base_url = provider_config.get("base_url")
            else:
                # 默认使用 OpenAI
                base_url = "https://api.openai.com/v1"
        
        client = OpenAI(api_key=api_key, base_url=base_url)
        
        # 获取模型列表
        models_response = client.models.list()
        
        # 过滤出可用的聊天模型
        chat_models = []
        for model in models_response.data:
            model_id = model.id
            
            # 根据提供商过滤模型
            if provider == 'openai':
                if any(x in model_id.lower() for x in ['gpt-4', 'gpt-3.5', 'gpt-4o']):
                    chat_models.append({
                        "id": model_id,
                        "name": model_id,
                        "provider": provider
                    })
            elif provider == 'deepseek':
                if 'deepseek' in model_id.lower():
                    chat_models.append({
                        "id": model_id,
                        "name": model_id,
                        "provider": provider
                    })
            elif provider == 'qwen':
                if 'qwen' in model_id.lower():
                    chat_models.append({
                        "id": model_id,
                        "name": model_id,
                        "provider": provider
                    })
            elif provider == 'claude':
                if 'claude' in model_id.lower():
                    chat_models.append({
                        "id": model_id,
                        "name": model_id,
                        "provider": provider
                    })
            elif provider == 'groq':
                if any(x in model_id.lower() for x in ['llama', 'mixtral', 'gemma']):
                    chat_models.append({
                        "id": model_id,
                        "name": model_id,
                        "provider": provider
                    })
            elif provider == 'ollama':
                # Ollama 返回所有模型
                chat_models.append({
                    "id": model_id,
                    "name": model_id,
                    "provider": provider
                })
            else:
                # 其他提供商，返回所有模型
                chat_models.append({
                    "id": model_id,
                    "name": model_id,
                    "provider": provider
                })
        
        # 如果没有获取到，返回常用模型列表
        if not chat_models:
            chat_models = get_default_models(provider)
        
        return R.success(chat_models, msg=f"获取 {provider} 模型列表成功")
    except Exception as e:
        logger.error(f"获取 {provider} 模型列表失败: {e}")
        # 返回默认模型列表
        return R.success(get_default_models(provider), msg=f"获取 {provider} 模型列表成功（使用默认列表）")

def get_default_models(provider: str):
    """获取默认模型列表"""
    defaults = {
        "openai": [
            {"id": "gpt-4o", "name": "GPT-4o", "provider": "openai"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "openai"},
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "provider": "openai"},
            {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "provider": "openai"},
        ],
        "deepseek": [
            {"id": "deepseek-chat", "name": "DeepSeek Chat", "provider": "deepseek"},
            {"id": "deepseek-coder", "name": "DeepSeek Coder", "provider": "deepseek"},
        ],
        "qwen": [
            {"id": "qwen-turbo", "name": "Qwen Turbo", "provider": "qwen"},
            {"id": "qwen-plus", "name": "Qwen Plus", "provider": "qwen"},
            {"id": "qwen-max", "name": "Qwen Max", "provider": "qwen"},
        ],
        "claude": [
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "provider": "claude"},
            {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus", "provider": "claude"},
            {"id": "claude-3-sonnet-20240229", "name": "Claude 3 Sonnet", "provider": "claude"},
        ],
        "groq": [
            {"id": "llama-3.1-70b-versatile", "name": "Llama 3.1 70B", "provider": "groq"},
            {"id": "mixtral-8x7b-32768", "name": "Mixtral 8x7B", "provider": "groq"},
            {"id": "gemma-7b-it", "name": "Gemma 7B", "provider": "groq"},
        ],
        "ollama": [
            {"id": "llama2", "name": "Llama 2", "provider": "ollama"},
            {"id": "mistral", "name": "Mistral", "provider": "ollama"},
            {"id": "codellama", "name": "CodeLlama", "provider": "ollama"},
        ],
    }
    return defaults.get(provider, [])

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
        
        # 如果没有获取到，返回常用模型列表
        if not chat_models:
            chat_models = [
                {"id": "gemini-2.0-flash-exp", "name": "Gemini 2.0 Flash (Experimental)", "provider": "gemini"},
                {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "provider": "gemini"},
                {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "provider": "gemini"},
                {"id": "gemini-pro", "name": "Gemini Pro", "provider": "gemini"},
            ]
        
        return R.success(chat_models, msg="获取 Gemini 模型列表成功")
    except Exception as e:
        logger.error(f"获取 Gemini 模型列表失败: {e}")
        raise

@router.post("/models/test")
def test_model_connection(config: ModelConfigRequest):
    """测试模型连接"""
    try:
        if config.provider == 'gemini':
            genai.configure(api_key=config.api_key)
            # 尝试列出模型来测试连接
            list(genai.list_models())
            return R.success(None, msg="Gemini 连接成功")
        else:
            # OpenAI 兼容 API
            # Ollama 不需要 API Key
            api_key = config.api_key
            if config.provider == 'ollama':
                api_key = api_key or 'ollama'  # Ollama 可以使用任意值或空值
            
            if not config.base_url:
                provider_config = next((p for p in BUILTIN_PROVIDERS if p["id"] == config.provider), None)
                if provider_config:
                    base_url = provider_config.get("base_url")
                else:
                    base_url = "https://api.openai.com/v1"
            else:
                base_url = config.base_url
            
            client = OpenAI(api_key=api_key, base_url=base_url)
            # 尝试获取模型列表来测试连接
            client.models.list()
            return R.success(None, msg=f"{config.provider} 连接成功")
    except Exception as e:
        logger.error(f"测试连接失败: {e}", exc_info=True)
        return R.error(f"连接失败: {str(e)}")
