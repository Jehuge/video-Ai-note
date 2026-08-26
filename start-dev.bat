@echo off
REM ============================================
REM  One-click dev startup (Windows)
REM  - Backend FastAPI : http://localhost:8483
REM  - Frontend Vite   : http://localhost:5173
REM ============================================
setlocal

set "ROOT=%~dp0"
set "BACKEND_PYTHON=%ROOT%backend\.venv\Scripts\python.exe"

if not exist "%BACKEND_PYTHON%" (
    echo [ERROR] Backend virtual environment not found: "%BACKEND_PYTHON%"
    echo Create it with: python -m venv "%ROOT%backend\.venv"
    pause
    exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
    echo [ERROR] npm not found in PATH.
    pause
    exit /b 1
)

echo [1/2] Starting backend (port 8483)...
start "video-ai-note-backend" /D "%ROOT%backend" cmd /k ""%BACKEND_PYTHON%" main.py"

echo Waiting for backend to become ready...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$deadline = (Get-Date).AddSeconds(60); do { try { $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8483/api/tasks?limit=1' -TimeoutSec 2; if ($response.StatusCode -eq 200) { exit 0 } } catch {}; Start-Sleep -Milliseconds 500 } while ((Get-Date) -lt $deadline); exit 1"
if errorlevel 1 (
    echo [ERROR] Backend did not become ready within 60 seconds.
    pause
    exit /b 1
)

echo [2/2] Starting frontend (port 5173)...
start "video-ai-note-frontend" /D "%ROOT%frontend" cmd /k "npm run dev"

echo.
echo Both services started in separate windows:
echo    Frontend: http://localhost:5173
echo    Backend : http://localhost:8483/docs
echo.
echo Close the corresponding window to stop a service.
endlocal
pause
