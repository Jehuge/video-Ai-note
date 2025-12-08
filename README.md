# Video AI Note - 简化版

基于 BiliNote 的简化版本，专注于视频笔记生成功能。

## 功能特性

- 📤 直接上传视频文件（支持常见视频格式）
- 🎙️ 自动音频转文字（使用 fast-whisper）
- 🤖 AI 生成结构化笔记（支持 OpenAI/DeepSeek/Qwen 等）
- 📝 Markdown 格式输出
- 💾 任务历史记录

## 技术栈

### 后端
- FastAPI
- SQLite
- fast-whisper (音频转文字)
- OpenAI API (笔记生成)

### 前端
- React + TypeScript
- Vite
- Tailwind CSS
- Zustand (状态管理)

## 快速开始

### 前置要求

- Python 3.8+
- Node.js 18+
- FFmpeg（用于视频处理）

安装 FFmpeg：
```bash
# Mac
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows
# 从 https://ffmpeg.org/download.html 下载安装
```

### 1. 配置后端

**方式一：使用启动脚本（推荐）**

启动脚本会自动创建和激活虚拟环境：

```bash
cd backend

# Linux/Mac
chmod +x start.sh
./start.sh

# Windows
start.bat
```

**方式二：手动配置**

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

# 创建 .env 文件（复制 .env.example 并修改）
cp .env.example .env
# 编辑 .env 文件，填入你的 OPENAI_API_KEY
```

### 2. 启动后端

如果使用启动脚本，直接运行即可。如果手动配置，需要先激活虚拟环境：

```bash
# 确保虚拟环境已激活（命令行前会显示 (venv)）
# 然后运行
python main.py
```

**注意：每次启动前都需要激活虚拟环境！**

后端将在 `http://localhost:8483` 启动

### 3. 配置并启动前端

```bash
cd frontend

# 安装依赖
npm install
# 或
pnpm install
# 或
yarn install

# 启动开发服务器
npm run dev
# 或
pnpm dev
```

前端将在 `http://localhost:5173` 启动

### 4. 使用

1. 打开浏览器访问 `http://localhost:5173`
2. 点击上传区域选择视频或音频文件
3. 等待处理完成（转写 → 生成笔记）
4. 查看生成的 Markdown 笔记

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
│   └── main.py
└── frontend/         # React 前端
    └── src/
```

## 注意事项

- ⚠️ **必须使用 Python 虚拟环境**（推荐使用启动脚本自动管理）
- 需要安装 FFmpeg 用于视频处理
- 首次运行会自动创建数据库
- 上传的视频文件会保存在 `uploads` 目录
- 详细虚拟环境使用指南请查看 [VENV_GUIDE.md](backend/VENV_GUIDE.md)

