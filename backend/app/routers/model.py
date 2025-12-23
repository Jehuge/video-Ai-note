from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import requests
from urllib.parse import urlparse
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
        
        base_url = base_url.strip()

        # 如果 base_url 指向本地/私有网络且没有提供 api_key，尝试直接请求 /models 接口而非使用 OpenAI SDK
        def is_local_base_url(url: str) -> bool:
            try:
                parsed = urlparse(url)
                host = parsed.hostname or ''
                if host in ('localhost', '127.0.0.1'):
                    return True
                if host.startswith('10.') or host.startswith('192.168.'):
                    return True
                # 172.16.0.0 — 172.31.255.255
                if host.startswith('172.'):
                    parts = host.split('.')
                    if len(parts) >= 2:
                        try:
                            second = int(parts[1])
                            if 16 <= second <= 31:
                                return True
                        except:
                            pass
                return False
            except:
                return False

        models_response = None
        
        # 优先尝试手动 HTTP 请求的情况：
        # 1. 本地/私有地址 (防止 SSL/代理问题)
        # 2. 自定义 OpenAI BaseURL (防止 SDK 对第三方服务器返回的不规范 JSON 进行严格校验导致奔溃)
        # 3. Ollama (通常返回格式较简单)
        is_custom_endpoint = False
        if is_local_base_url(base_url):
            is_custom_endpoint = True
        elif provider == 'openai' and base_url and "api.openai.com" not in base_url:
            is_custom_endpoint = True
        elif provider == 'ollama':
            is_custom_endpoint = True

        if is_custom_endpoint:
             # 尝试直接请求常见的 models 路径
            candidates = [base_url.rstrip('/') + '/models', base_url.rstrip('/') + '/v1/models']
            for url in candidates:
                try:
                    # 如果有 API Key，带上
                    headers = {}
                    if api_key and api_key != 'ollama':
                        headers['Authorization'] = f'Bearer {api_key}'
                    
                    logger.info(f"Trying manual fetch from: {url}")
                    # 显式禁用代理，防止本地 IP 被排错路由
                    resp = requests.get(url, timeout=10, headers=headers, proxies={"http": None, "https": None})
                    logger.info(f"Manual fetch response status: {resp.status_code}")
                    
                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                            logger.info(f"Manual fetch response data length: {len(str(data))}")
                            # 构造一个兼容的对象
                            if isinstance(data, list):
                                models_response = type('R', (), {'data': data})
                            elif isinstance(data, dict) and 'data' in data:
                                models_response = type('R', (), {'data': data['data']})
                            else:
                                models_response = type('R', (), {'data': data.get('models', []) if isinstance(data, dict) else []})
                            break
                        except Exception as e:
                            logger.warning(f"Manual fetch parse failed: {e}")
                            continue
                    else:
                        logger.warning(f"Manual fetch failed with status {resp.status_code}: {resp.text[:200]}")
                except Exception as e:
                    logger.warning(f"Manual fetch exception for {url}: {e}")
                    continue

        # 如果手动请求未执行或失败，且不是只能手动的情况，则使用 SDK
        if models_response is None:
            logger.info("Falling back to OpenAI SDK")
            client = OpenAI(api_key=api_key, base_url=base_url)
            models_response = client.models.list()

        # 过滤出可用的聊天模型
        chat_models = []
        for model in models_response.data:
            # model 可能是 SDK 对象也可能是 dict
            if hasattr(model, "id"):
                model_id = getattr(model, "id")
                model_name = getattr(model, "name", model_id)
            elif isinstance(model, dict):
                model_id = model.get("id") or model.get("model") or model.get("name")
                model_name = model.get("name") or model_id
            else:
                # 无法识别的格式，跳过
                continue

            if not model_id:
                continue

            lid = str(model_id).lower()

            # 根据提供商过滤模型
            if provider == 'openai':
                # 检查是否使用官方 API
                is_official = not base_url or "api.openai.com" in base_url
                
                if is_official:
                    if any(x in lid for x in ['gpt-4', 'gpt-3.5', 'gpt-4o']):
                        chat_models.append({"id": model_id, "name": model_name, "provider": provider})
                else:
                    # 自定义 endpoint (如 LM Studio)，显示所有模型
                    chat_models.append({"id": model_id, "name": model_name, "provider": provider})
            elif provider == 'deepseek':
                if 'deepseek' in lid:
                    chat_models.append({"id": model_id, "name": model_name, "provider": provider})
            elif provider == 'qwen':
                if 'qwen' in lid:
                    chat_models.append({"id": model_id, "name": model_name, "provider": provider})
            elif provider == 'claude':
                if 'claude' in lid:
                    chat_models.append({"id": model_id, "name": model_name, "provider": provider})
            elif provider == 'groq':
                if any(x in lid for x in ['llama', 'mixtral', 'gemma']):
                    chat_models.append({"id": model_id, "name": model_name, "provider": provider})
            elif provider == 'ollama':
                # Ollama 返回所有模型
                chat_models.append({"id": model_id, "name": model_name, "provider": provider})
            else:
                # 其他提供商，返回所有模型
                chat_models.append({"id": model_id, "name": model_name, "provider": provider})

        # 不再返回默认模型列表；只返回实际获取到的模型（可能为空）
        return R.success(chat_models, msg=f"获取 {provider} 模型列表成功")
    except Exception as e:
        logger.error(f"获取 {provider} 模型列表失败: {e}")
        # 不再返回误导性的默认列表
        return R.error(f"获取 {provider} 模型列表失败: {str(e)}")

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
            
            # 如果 base_url 指向本地/私有网络且没有提供 api_key，尝试用简单 HTTP 请求检测 /models 是否可用
            def is_local_base_url(url: str) -> bool:
                try:
                    parsed = urlparse(url)
                    host = parsed.hostname or ''
                    if host in ('localhost', '127.0.0.1'):
                        return True
                    if host.startswith('10.') or host.startswith('192.168.'):
                        return True
                    if host.startswith('172.'):
                        parts = host.split('.')
                        if len(parts) >= 2:
                            try:
                                second = int(parts[1])
                                if 16 <= second <= 31:
                                    return True
                            except:
                                pass
                    return False
                except:
                    return False

            if is_local_base_url(base_url):
                # 尝试直接请求常见的 models 路径
                candidates = [base_url.rstrip('/') + '/models', base_url.rstrip('/') + '/v1/models']
                ok = False
                for url in candidates:
                    try:
                        headers = {}
                        if api_key and api_key != 'ollama':
                            headers['Authorization'] = f'Bearer {api_key}'

                        # 显式禁用代理
                        resp = requests.get(url, timeout=6, headers=headers, proxies={"http": None, "https": None})
                        if resp.status_code == 200:
                            ok = True
                            break
                    except Exception:
                        continue
                if ok:
                    return R.success(None, msg=f"{config.provider} 连接成功（本地/私有地址）")
                # 否则继续尝试 SDK 方式以获取更具体错误
            client = OpenAI(api_key=api_key, base_url=base_url)
            # 尝试获取模型列表来测试连接
            client.models.list()
            return R.success(None, msg=f"{config.provider} 连接成功")
    except Exception as e:
        logger.error(f"测试连接失败: {e}", exc_info=True)
        return R.error(f"连接失败: {str(e)}")
