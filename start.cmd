@echo off
cd /d "%~dp0"

echo Starting API Regression Quality Gate and bundled demo service...
echo Platform: http://127.0.0.1:8000/workbench
echo Demo API: http://127.0.0.1:8010/docs
echo Keep this window open. Press Ctrl+C to stop.
echo.

if not exist ".venv-codex\Scripts\python.exe" (
    echo ERROR: Python environment was not found.
    pause
    exit /b 1
)

start "" /b powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 4; Start-Process 'http://127.0.0.1:8000/workbench'"
".venv-codex\Scripts\python.exe" scripts\run_demo.py

echo.
echo The server stopped or failed to start.
pause
