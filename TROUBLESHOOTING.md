# 故障排查指南

## 前端连接超时问题

### 问题现象
```
Failed to load resource: net::ERR_CONNECTION_TIMED_OUT
```

### 解决方案

#### 1. 检查后端服务是否运行

```bash
# 检查端口是否被占用
lsof -ti:8483

# 或者访问后端文档
curl http://localhost:8483/docs
```

#### 2. 启动后端服务

```bash
cd backend
./start.sh  # Linux/Mac
# 或
start.bat   # Windows
```

确保看到类似输出：
```
🚀 启动后端服务...
   访问地址: http://localhost:8483
   API 文档: http://localhost:8483/docs
INFO:     Uvicorn running on http://0.0.0.0:8483
```

#### 3. 检查前端配置

前端使用 Vite 代理，配置在 `frontend/vite.config.ts`：

```typescript
proxy: {
  '/api': {
    target: 'http://localhost:8483',
    changeOrigin: true,
  },
}
```

前端 API 调用使用相对路径 `/api`，会自动代理到后端。

#### 4. 重启前端开发服务器

修改配置后需要重启：

```bash
cd frontend
# 停止当前服务 (Ctrl+C)
npm run dev  # 或 pnpm dev
```

#### 5. 检查 CORS 配置

后端 CORS 配置在 `backend/main.py`，确保包含前端地址：

```python
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
]
```

#### 6. 直接测试后端 API

```bash
# 测试任务列表接口
curl http://localhost:8483/api/tasks

# 测试上传接口（需要文件）
curl -X POST http://localhost:8483/api/upload \
  -F "file=@test.mp4"
```

### 常见错误

#### 错误：`ModuleNotFoundError: No module named 'requests'`

**解决：** 安装缺失的依赖
```bash
cd backend
source venv/bin/activate
pip install requests
```

#### 错误：`WARNING: You must pass the application as an import string`

**解决：** 已在 `main.py` 中修复，使用 `"main:app"` 而不是 `app` 对象

#### 错误：端口已被占用

**解决：** 
```bash
# 查找占用端口的进程
lsof -ti:8483

# 杀死进程（替换 PID）
kill -9 <PID>
```

#### 错误：虚拟环境未激活

**解决：**
```bash
cd backend
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows
```

## 前端问题

### 问题：页面空白或无法加载

1. 检查 Node.js 版本（需要 18+）
2. 清除缓存并重新安装依赖：
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### 问题：API 请求失败

1. 确保后端服务正在运行
2. 检查浏览器控制台的错误信息
3. 检查网络标签页中的请求详情

## 后端问题

### 问题：数据库初始化失败

**解决：** 确保有写入权限，删除旧的数据库文件重新创建：
```bash
cd backend
rm video_note.db  # 如果存在
python main.py    # 会自动创建新数据库
```

### 问题：FFmpeg 未找到

**解决：** 安装 FFmpeg
```bash
# Mac
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows
# 从 https://ffmpeg.org/download.html 下载安装
```

### 问题：OpenAI API 调用失败

**解决：** 
1. 检查 `.env` 文件中的 `OPENAI_API_KEY` 是否正确
2. 检查 API 密钥是否有效
3. 检查网络连接

## 调试技巧

### 查看后端日志

后端日志会显示在控制台，包括：
- 请求日志
- 错误信息
- 任务状态更新

### 查看前端日志

打开浏览器开发者工具（F12）：
- Console 标签：查看 JavaScript 错误
- Network 标签：查看 API 请求详情

### 测试 API

使用 curl 或 Postman 直接测试后端 API：
```bash
# 获取任务列表
curl http://localhost:8483/api/tasks

# 获取任务状态
curl http://localhost:8483/api/task/{task_id}
```

## 获取帮助

如果问题仍然存在：
1. 检查所有日志输出
2. 确认所有依赖已正确安装
3. 确认环境变量配置正确
4. 查看 GitHub Issues（如果有）

