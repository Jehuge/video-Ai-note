@echo off
chcp 65001 >nul

REM 检查 Python 环境
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未找到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

python --version
echo ✓ Python 环境检查通过
echo.

REM 检查虚拟环境
if not exist "venv" (
    echo 📦 创建虚拟环境...
    python -m venv venv
    if errorlevel 1 (
        echo ❌ 虚拟环境创建失败
        pause
        exit /b 1
    )
    echo ✓ 虚拟环境创建成功
) else (
    echo ✓ 虚拟环境已存在
)

REM 激活虚拟环境
echo 🔧 激活虚拟环境...
call venv\Scripts\activate.bat

REM 升级 pip
echo ⬆️  升级 pip...
python -m pip install --upgrade pip -q

REM 安装依赖
echo 📥 安装依赖包...
pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ 依赖安装失败
    pause
    exit /b 1
)
echo ✓ 依赖安装完成
echo.

REM 检查 .env 文件
if not exist ".env" (
    echo ⚠️  警告: 未找到 .env 文件
    echo    请复制 .env.example 为 .env 并配置环境变量:
    echo    copy .env.example .env
    echo    然后编辑 .env 文件，填入你的 OPENAI_API_KEY
    echo.
    set /p continue="是否继续启动? (y/n): "
    if /i not "%continue%"=="y" (
        exit /b 1
    )
) else (
    echo ✓ 环境变量文件已配置
)

REM 启动服务
echo.
echo 🚀 启动后端服务...
echo    访问地址: http://localhost:8483
echo    API 文档: http://localhost:8483/docs
echo.
python main.py

pause

