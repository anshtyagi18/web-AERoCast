@echo off
setlocal enabledelayedexpansion
title AeroCast - Air Grab ^& Drop System

cd /d "%~dp0"

echo ================================================================
echo       AEROCAST: AIR TELEPORT SYSTEM (ONE-CLICK LAUNCHER)
echo ================================================================

:: 1. Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not found in system PATH.
    echo Please install Python 3.10+ from python.org and check "Add to PATH".
    goto error_pause
)

:: 2. Check virtual environment
if not exist "venv\Scripts\activate.bat" (
    echo [SETUP] Virtual environment not found. Creating venv...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        goto error_pause
    )
    echo [SETUP] venv created successfully.
)

:: 3. Activate venv
echo [ENV] Activating virtual environment...
call venv\Scripts\activate.bat

:: 4. Install / Verify dependencies
echo [DEPS] Checking dependencies from requirements.txt...
pip install -r requirements.txt
if errorlevel 1 (
    echo [WARNING] Some dependencies failed to install. Attempting to proceed...
)

:: 5. Launch unified orchestrator
echo.
echo [LAUNCH] Starting AeroCast Unified System (FastAPI HTTPS + OpenCV Vision)...
echo ================================================================
python main.py
if errorlevel 1 (
    echo [ERROR] AeroCast stopped with an error code: %errorlevel%
    goto error_pause
)

echo [AEROCAST] Session terminated cleanly.
pause
exit /b 0

:error_pause
echo.
echo ================================================================
echo Execution failed. Please review the errors above.
echo ================================================================
pause
exit /b 1
