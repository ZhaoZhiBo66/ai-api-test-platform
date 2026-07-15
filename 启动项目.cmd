@echo off
cd /d "%~dp0"

set "DATABASE_URL=sqlite:///./ai_test_platform.db"
set "OPENAI_API_KEY="

echo Starting AI API Test Platform...
echo Open this page after startup:
echo http://127.0.0.1:8000/docs
echo.
echo Keep this window open. Press Ctrl+C to stop the server.
echo.

if not exist ".venv-codex\Scripts\python.exe" (
    echo ERROR: Python environment was not found.
    pause
    exit /b 1
)

start "" /b powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 4; Start-Process 'http://127.0.0.1:8000/docs'"

".venv-codex\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000

echo.
echo The server stopped or failed to start.
pause
