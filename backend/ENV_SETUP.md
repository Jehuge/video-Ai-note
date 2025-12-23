# 环境变量配置说明

## 必需配置

### OPENAI_API_KEY

这是**必需**的环境变量，用于调用 OpenAI API 生成笔记。

**获取方式：**

1. 访问 https://platform.openai.com/api-keys
2. 登录你的 OpenAI 账号
3. 创建新的 API Key
4. 复制 API Key

**配置方法：**

1. 在 `backend` 目录下创建 `.env` 文件（如果不存在）
2. 添加以下内容：

```env
OPENAI_API_KEY=sk-your-actual-api-key-here
```

**注意：**

- 不要将 `.env` 文件提交到 Git（已在 .gitignore 中）
- API Key 以 `sk-` 开头
- 确保 API Key 有效且有足够的余额

## 完整配置示例

创建 `backend/.env` 文件，内容如下：

```env
# GPT 配置（必需）
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
GPT_MODEL=gpt-4o-mini

# 转录器配置（可选）
TRANSCRIBER_TYPE=fast-whisper
WHISPER_MODEL_SIZE=base
WHISPER_DEVICE=cpu

# 服务器配置（可选）
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8483

# 文件存储（可选）
UPLOAD_DIR=uploads
NOTE_OUTPUT_DIR=note_results
STATIC_DIR=static
```

## 配置说明

### GPT 配置

- `OPENAI_API_KEY`: OpenAI API 密钥（**必需**）
- `OPENAI_BASE_URL`: API 基础 URL，默认 `https://api.openai.com/v1`
  - 如果使用代理或兼容 API，可以修改此值
  - 例如：`https://api.deepseek.com/v1`（DeepSeek）
- `GPT_MODEL`: 使用的模型，默认 `gpt-4o-mini`
  - 可选：`gpt-4o`, `gpt-4o-mini`, `gpt-3.5-turbo` 等

### 转录器配置

- `TRANSCRIBER_TYPE`: 转录器类型，默认 `fast-whisper`
- `WHISPER_MODEL_SIZE`: Whisper 模型大小，默认 `base`
  - 可选：`tiny`, `base`, `small`, `medium`, `large`
  - 模型越大，准确度越高，但速度越慢
- `WHISPER_DEVICE`: 运行设备，默认 `cpu`
  - 如果有 NVIDIA GPU，可以设置为 `cuda`

### 服务器配置

- `BACKEND_HOST`: 服务器监听地址，默认 `0.0.0.0`（所有接口）
- `BACKEND_PORT`: 服务器端口，默认 `8483`

### 文件存储

- `UPLOAD_DIR`: 上传文件存储目录，默认 `uploads`
- `NOTE_OUTPUT_DIR`: 笔记结果存储目录，默认 `note_results`
- `STATIC_DIR`: 静态文件目录，默认 `static`

## 验证配置

启动后端服务后，检查日志中是否有错误：

```bash
cd backend
./start.sh
```

如果看到 "OPENAI_API_KEY 未设置" 错误，说明 `.env` 文件配置不正确。

## 常见问题

### Q: 如何检查 API Key 是否有效？

A: 可以在命令行测试：

```bash
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer sk-your-api-key"
```

### Q: 可以使用其他 GPT 服务吗？

A: 目前只支持 OpenAI 兼容的 API。如果需要支持其他服务（如 DeepSeek、Qwen），需要修改 `app/gpt/openai_gpt.py` 或添加新的实现。

### Q: 如何提高转录准确度？

A: 可以：

1. 使用更大的 Whisper 模型（如 `medium` 或 `large`）
2. 使用 GPU 加速（设置 `WHISPER_DEVICE=cuda`）

### Q: 配置修改后需要重启吗？

A: 是的，修改 `.env` 文件后需要重启后端服务。
