@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found: .venv\Scripts\python.exe
    echo Please create it first, e.g.: python -m venv .venv
    pause
    exit /b 1
)

if not exist "app\main.py" (
    echo [ERROR] app\main.py not found. Run this script from the project root.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m uvicorn app.main:app --reload
pause
