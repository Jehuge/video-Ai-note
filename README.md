# Video AI Note

一个智能视频笔记生成工具，支持自动提取视频音频、转写文字，并使用 AI 生成结构化笔记。

**完全本地化处理，保护数据隐私** - 所有数据处理均在本地完成，支持 Ollama 等本地大模型，无需联网即可使用。

## 功能特性

- **完全本地化处理** - 所有数据在本地处理，不上传到云端，保护隐私安全
- **支持本地大模型** - 支持 Ollama 4B 等本地模型，完全离线运行，无需 API 密钥
- 直接上传视频文件（支持常见视频格式）
- 自动音频转文字（使用 fast-whisper，本地运行）
- AI 生成结构化笔记（支持 OpenAI/DeepSeek/Qwen/Ollama 等）
- Markdown 格式输出（图片自动嵌入为 base64）
- PDF 导出（支持可复制文本格式）
- 视频预览功能
- 任务历史记录
- 多模型配置支持
- 截图自动插入（可选）

### FFmpeg 说明

项目会自动处理 FFmpeg 的安装和使用：

- 如果系统已安装 FFmpeg，会优先使用系统版本
- 如果没有安装，首次运行时会自动下载 FFmpeg 到项目目录（`backend/ffmpeg_bin/`）
- 使用 `imageio-ffmpeg` 包自动管理 FFmpeg 二进制文件

如果你想使用系统级别的 FFmpeg，可以手动安装：

```bash
# Mac
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows
# 从 https://ffmpeg.org/download.html 下载安装
```

## 安装

### 后端配置

#### 方式一：使用启动脚本（推荐）

启动脚本会自动创建和激活虚拟环境：

```bash
cd backend

# Linux/Mac
chmod +x start.sh
./start.sh

# Windows
start.bat
```

#### 方式二：手动配置

```bash
cd backend

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
# Linux/Mac:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# 升级 pip
pip install --upgrade pip

# 安装依赖
pip install -r requirements.txt
```

### 前端配置

```bash
cd frontend

# 安装依赖
npm install
# 或
pnpm install
# 或
yarn install
```

## 使用

### 启动后端

如果使用启动脚本，直接运行即可。如果手动配置，需要先激活虚拟环境：

```bash
# 确保虚拟环境已激活（命令行前会显示 (venv)）
# 然后运行
python main.py
```

**注意：每次启动前都需要激活虚拟环境！**

后端将在 `http://localhost:8483` 启动

### 启动前端

```bash
cd frontend

# 启动开发服务器
npm run dev
# 或
pnpm dev
```

前端将在 `http://localhost:5173` 启动

### 使用流程

1. 打开浏览器访问 `http://localhost:5173`
2. 在"模型配置"页面配置你的 AI 模型：
   - **本地运行（推荐）**：选择 Ollama，配置本地模型（如 `llama3.2:3b`、`qwen2.5:4b` 等），无需 API 密钥
   - **云端 API**：也可选择 OpenAI/DeepSeek/Qwen 等云端 API
3. 在"上传"页面选择视频或音频文件
4. 在任务列表中选择任务，按步骤执行：
   - 文件上传（可查看视频）
   - 提取音频
   - 音频转写（可查看转写结果）
   - 生成笔记（可查看 Markdown 笔记）
5. 下载生成的 Markdown 或 PDF 文件

### 本地运行配置（Ollama）

如需完全离线运行，推荐使用 Ollama 本地模型：

1. **安装 Ollama**（如果尚未安装）：

   ```bash
   # Mac/Linux
   curl -fsSL https://ollama.com/install.sh | sh

   # Windows
   # 从 https://ollama.com/download 下载安装
   ```
2. **下载模型**（推荐 4B 参数模型，性能与速度平衡）：

   ```bash
   # 下载 4B 模型示例
   ollama pull llama3.2:3b
   # 或
   ollama pull qwen2.5:4b
   # 或
   ollama pull phi3:mini
   ```
3. **在模型配置中选择 Ollama**：

   - 模型类型选择 "Ollama"
   - 模型名称填写你下载的模型（如 `llama3.2:3b`）
   - API 地址默认为 `http://localhost:11434`（Ollama 默认端口）

**优势**：

- 完全离线运行，无需网络连接
- 数据不上传，保护隐私
- 无需 API 密钥，无使用费用
- 4B 模型在普通硬件上即可流畅运行

## 项目结构

```
video-Ai-note/
├── backend/          # FastAPI 后端
│   ├── app/
│   │   ├── routers/  # API 路由
│   │   ├── services/ # 业务逻辑
│   │   ├── transcriber/ # 音频转文字
│   │   ├── gpt/      # GPT 集成
│   │   └── db/       # 数据库
│   ├── uploads/      # 上传文件存储
│   ├── note_results/ # 笔记结果存储
│   └── main.py
└── frontend/         # React 前端
    └── src/
        ├── components/ # 组件
        ├── services/   # API 服务
        └── store/     # 状态管理
```

## 注意事项

- **数据隐私**：所有视频、音频、转写文本和生成的笔记均存储在本地，不会上传到任何服务器
- **本地运行**：使用 Ollama 等本地模型时，完全离线运行，无需网络连接和 API 密钥
- 必须使用 Python 虚拟环境（推荐使用启动脚本自动管理）
- FFmpeg 会自动下载到项目目录，无需手动安装
- 首次运行会自动创建数据库
- 上传的视频文件会保存在 `backend/uploads` 目录
- 生成的笔记和截图会保存在 `backend/note_results` 目录
- FFmpeg 二进制文件会保存在 `backend/ffmpeg_bin/` 目录（自动创建）
- 详细虚拟环境使用指南请查看 [VENV_GUIDE.md](backend/VENV_GUIDE.md)
