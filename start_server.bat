@echo off
title Smartlead Campaign Analytics Dashboard
echo ========================================================
echo  SMARTLEAD CAMPAIGN ANALYTICS DASHBOARD
echo ========================================================
echo.

:: Check if virtual environment exists
if not exist "venv\Scripts\python.exe" (
    echo [Step 1/2] Setting up Python virtual environment (First time only)...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Python is not installed or not added to PATH.
        echo Please ensure Python 3.10+ is installed.
        pause
        exit /b 1
    )
    echo [Step 2/2] Installing required dependencies...
    .\venv\Scripts\pip install -r requirements.txt
    echo Setup completed successfully!
    echo.
) else (
    echo Virtual environment detected.
)

echo Starting application server...
echo URL: http://localhost:8000
echo.

:: Open browser automatically after a short 2-second delay
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"

:: Start FastAPI server
.\venv\Scripts\python run.py --server

pause
