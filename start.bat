@echo off
title WHai Image Station

cd /d "%~dp0"

echo.
echo   WHai Image Station - AI Image Generator
echo   -------------------------------
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create venv
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat

if not exist ".venv\.deps_installed" (
    echo [INFO] Installing dependencies...
    pip install -r requirements.txt -q
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
    echo [INFO] Installing project in editable mode...
    pip install -e . -q
    if errorlevel 1 (
        echo [ERROR] Failed to install project
        pause
        exit /b 1
    )
    type nul > ".venv\.deps_installed"
)

echo [INFO] Starting WHai Image Station...
echo.
python src\main.py

if errorlevel 1 (
    echo.
    echo [ERROR] App exited with code: %errorlevel%
    pause
)
