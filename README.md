# 🎬 Video Note AI

一款强大的AI视频笔记应用，支持视频转录、智能笔记生成和B站视频批量下载。

## ✨ 主要功能

### 📝 智能视频笔记
- **视频上传与转录**：支持上传本地视频，自动提取音频并转录为文字
- **AI笔记生成**：基于转录内容，使用AI模型生成结构化笔记
- **多模型支持**：集成OpenAI、本地LM Studio、Ollama等多种AI模型
- **截图功能**：为视频生成代表性截图，增强笔记可视化

### 🎞️ B站视频下载
- **批量下载管理**：添加多个B站视频链接，统一管理下载队列
- **自定义配置**：
  - 视频清晰度选择（360P - 1080P）
  - 自定义下载路径
  - 下载间隔设置
  - 无头模式（后台运行）
- **实时状态跟踪**：下载进度实时显示，支持手动刷新
- **下载历史记录**：完整记录所有下载历史，包括文件路径、大小等信息

## 🚀 技术栈

### 后端
- **框架**：FastAPI
- **数据库**：SQLite + SQLAlchemy ORM
- **转录**：faster-whisper
- **视频处理**：opencv-python, ffmpeg-python
- **B站下载**：playwright, yt-dlp, httpx

### 前端
- **框架**：React + TypeScript
- **构建工具**：Vite
- **UI组件**：Lucide React Icons
- **通知**：react-hot-toast
- **状态管理**：React Hooks

## 📦 安装指南

### 环境要求
- Python 3.8+
- Node.js 16+
- FFmpeg（视频处理）

### 后端安装

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 首次运行需要安装 Playwright 浏览器
playwright install chromium
```

### 前端安装

```bash
cd frontend

# 安装依赖（使用 pnpm）
pnpm install

# 或使用 npm
npm install
```

## 🎯 运行项目

### 启动后端

```bash
cd backend
source venv/bin/activate
python main.py
```

后端服务将运行在 `http://localhost:8483`

### 启动前端

```bash
cd frontend
pnpm dev
# 或 npm run dev
```

前端将运行在 `http://localhost:5173`

## 📖 使用说明

### 视频笔记生成

1. **配置AI模型**：
   - 进入"模型配置"页面
   - 添加并配置你的AI模型（OpenAI API Key、本地模型等）

2. **上传视频**：
   - 进入"任务"页面
   - 上传视频文件或从B站下载目录选择
   - 等待自动转录完成

3. **生成笔记**：
   - 转录完成后，点击"生成笔记"
   - AI将基于转录内容生成结构化笔记
   - 支持查看、编辑和导出笔记

### B站视频下载

1. **配置下载参数**：
   - 进入"B站下载"页面
   - 设置视频清晰度、保存路径、下载间隔等

2. **添加视频**：
   - 在视频列表区域输入B站视频URL或BV号
   - 点击"添加"将视频加入下载队列

3. **开始下载**：
   - 点击"开始下载"按钮
   - 首次下载需要扫码登录B站账号（登录状态会保存）
   - 下载状态会实时更新

4. **查看历史**：
   - 下载历史面板显示所有已完成的下载
   - 包含文件路径、大小、下载时间等信息

## 📁 项目结构

```
video-Ai-note/
├── backend/                 # 后端服务
│   ├── app/
│   │   ├── db/             # 数据库模型和DAO
│   │   ├── routers/        # API路由
│   │   ├── services/       # 业务逻辑
│   │   │   ├── bilibili/   # B站下载核心模块
│   │   │   └── ...
│   │   ├── transcriber/    # 转录服务
│   │   └── utils/          # 工具函数
│   ├── uploads/            # 上传和下载目录
│   └── main.py             # 入口文件
│
├── frontend/               # 前端应用
│   ├── src/
│   │   ├── components/     # React组件
│   │   ├── pages/          # 页面组件
│   │   ├── services/       # API服务层
│   │   └── App.tsx         # 应用入口
│   └── vite.config.ts      # Vite配置
│
└── README.md
```

## 🔧 配置说明

### 环境变量

后端支持以下环境变量配置：

```bash
# API服务端口
PORT=8483

# 数据库路径（可选，默认使用SQLite）
DATABASE_URL=sqlite:///./video_note.db
```

### 代理配置

如果您在使用外部AI模型API时需要代理，后端会自动清除代理环境变量以确保本地模型正常访问。

## ⚠️ 注意事项

1. **B站下载功能**：
   - 首次使用需要登录B站账号
   - 下载高清视频可能需要大会员权限
   - 请遵守B站服务条款，合理使用

2. **模型配置**：
   - OpenAI等外部模型需要有效的API Key
   - 本地模型（LM Studio/Ollama）需要单独安装和运行

3. **性能优化**：
   - 大文件转录可能需要较长时间
   - 建议根据硬件配置调整whisper模型大小

## 📝 更新日志

### v2.0.0 (2026-01-07)
- ✨ 新增B站视频批量下载功能
- ✨ 完整的下载配置和历史管理
- 🐛 修复前端状态同步问题
- 🎨 优化UI，添加刷新按钮和运行中状态显示

### v1.0.0
- 🎉 初始版本发布
- 📝 视频转录和AI笔记生成功能
- 🤖 多模型支持

## 📄 许可证

本项目采用 MIT 许可证。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

如有问题或建议，请随时联系。
