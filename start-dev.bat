@echo off
REM ============================================
REM  One-click development startup (Windows)
REM  app_entry starts Vite first, then the backend.
REM  Closing the development entry process stops both services.
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

if not exist "%ROOT%frontend\node_modules" (
    echo [ERROR] Frontend dependencies not found.
    echo Run: cd /d "%ROOT%frontend" ^&^& npm install
    pause
    exit /b 1
)

echo Starting Video Note AI development entrypoint...
cd /d "%ROOT%backend"
"%BACKEND_PYTHON%" app_entry.py --dev
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] Video Note AI exited with code %EXIT_CODE%.
    pause
)

endlocal & exit /b %EXIT_CODE%
