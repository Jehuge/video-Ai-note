# 项目结构说明

## 后端结构 (backend/)

```
backend/
├── app/
│   ├── __init__.py          # 应用工厂函数
│   ├── routers/              # API 路由
│   │   ├── __init__.py
│   │   └── note.py          # 笔记相关 API（上传、任务状态等）
│   ├── services/             # 业务逻辑层
│   │   ├── __init__.py
│   │   └── note.py          # 笔记生成核心服务
│   ├── db/                   # 数据库相关
│   │   ├── __init__.py
│   │   ├── engine.py        # 数据库引擎配置
│   │   ├── init_db.py       # 数据库初始化
│   │   ├── models/          # 数据模型
│   │   │   ├── __init__.py
│   │   │   └── video_task.py # 视频任务模型
│   │   └── video_task_dao.py # 数据访问对象
│   ├── models/               # 业务模型
│   │   ├── __init__.py
│   │   ├── notes_model.py   # 笔记结果模型
│   │   └── transcriber_model.py # 转录结果模型
│   ├── transcriber/          # 音频转文字
│   │   ├── __init__.py
│   │   ├── base.py          # 转录器基类
│   │   ├── fast_whisper.py  # FastWhisper 实现
│   │   └── transcriber_provider.py # 转录器工厂
│   ├── gpt/                  # GPT 集成
│   │   ├── __init__.py
│   │   ├── base.py          # GPT 基类
│   │   └── openai_gpt.py   # OpenAI 实现
│   ├── exceptions/           # 异常处理
│   │   ├── __init__.py
│   │   └── exception_handlers.py
│   └── utils/                # 工具函数
│       ├── logger.py        # 日志配置
│       └── response.py      # 响应包装器
├── main.py                   # 应用入口
├── requirements.txt          # Python 依赖
├── .env.example             # 环境变量示例
├── start.sh                 # Linux/Mac 启动脚本
└── start.bat                # Windows 启动脚本
```

## 前端结构 (frontend/)

```
frontend/
├── src/
│   ├── components/           # React 组件
│   │   ├── UploadForm.tsx   # 文件上传组件
│   │   ├── TaskList.tsx     # 任务列表组件
│   │   └── MarkdownViewer.tsx # Markdown 预览组件
│   ├── services/             # API 服务
│   │   └── api.ts           # API 调用封装
│   ├── store/                # 状态管理
│   │   └── taskStore.ts    # 任务状态管理（Zustand）
│   ├── App.tsx              # 主应用组件
│   ├── main.tsx            # 入口文件
│   ├── index.css           # 全局样式
│   └── vite-env.d.ts       # Vite 类型定义
├── index.html               # HTML 模板
├── package.json             # 依赖配置
├── vite.config.ts          # Vite 配置
├── tsconfig.json           # TypeScript 配置
└── tailwind.config.js      # Tailwind CSS 配置
```

## 核心流程

1. **文件上传** (`/api/upload`)
   - 用户上传视频/音频文件
   - 保存到 `uploads/` 目录
   - 创建任务记录
   - 启动后台任务

2. **音频提取** (`NoteGenerator._extract_audio`)
   - 使用 FFmpeg 从视频中提取音频
   - 转换为 WAV 格式（16kHz, 单声道）

3. **音频转写** (`NoteGenerator._transcribe_audio`)
   - 使用 FastWhisper 转录音频
   - 返回带时间戳的分段文本
   - 结果缓存到 `note_results/`

4. **笔记生成** (`NoteGenerator._summarize_text`)
   - 调用 OpenAI API
   - 根据转录内容生成 Markdown 笔记
   - 结果缓存到 `note_results/`

5. **状态查询** (`/api/task/{task_id}`)
   - 前端轮询任务状态
   - 返回任务信息和生成的笔记

## 数据流

```
用户上传文件
    ↓
保存文件 + 创建任务（status: pending）
    ↓
后台任务启动（status: processing）
    ↓
提取音频（status: processing）
    ↓
转写音频（status: transcribing）
    ↓
生成笔记（status: summarizing）
    ↓
保存结果（status: completed）
    ↓
前端获取并显示笔记
```

## 简化点

相比原 BiliNote 项目，本简化版：

1. ✅ **移除了下载器模块** - 改为直接文件上传
2. ✅ **简化了 GPT 集成** - 只支持 OpenAI（可扩展）
3. ✅ **简化了转录器** - 只支持 FastWhisper（可扩展）
4. ✅ **移除了复杂的配置系统** - 使用简单的环境变量
5. ✅ **移除了 Docker 支持** - 直接运行
6. ✅ **简化了前端 UI** - 只保留核心功能
7. ✅ **移除了截图功能** - 专注于笔记生成
8. ✅ **移除了链接跳转功能** - 简化处理流程

## 扩展建议

如果需要扩展功能，可以：

1. **添加更多 GPT 提供商** - 在 `app/gpt/` 下添加新的实现类
2. **添加更多转录器** - 在 `app/transcriber/` 下添加新的实现类
3. **添加截图功能** - 参考原项目的 `video_helper.py`
4. **添加任务重试** - 在路由中添加重试接口
5. **添加任务删除** - 完善删除功能，清理相关文件

