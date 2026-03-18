@echo off
REM Setup script for Bumble BLE Testing Framework

echo.
echo ============================================================
echo   Bumble BLE Testing Framework - Setup
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo Please install Python 3.8+ from python.org
    pause
    exit /b 1
)

echo [1/3] Creating virtual environment...
if exist "venv" (
    echo Virtual environment already exists, skipping...
) else (
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo Virtual environment created successfully!
)

echo.
echo [2/3] Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo [3/3] Installing dependencies...
echo pip install --upgrade pip
echo pip install -r requirements.txt

rem if errorlevel 1 (
rem     echo [ERROR] Failed to install dependencies
rem     pause
rem     exit /b 1
rem )

echo.
echo ============================================================
echo   Setup Complete!
echo ============================================================
echo.
echo Next Steps:
echo.
echo 1. Start HCI Bridge (in Administrator terminal):
echo    bumble-hci-bridge usb:0 tcp-server:127.0.0.1:9001
echo.
echo 2. Start the application:
echo    run.bat
echo.
echo For detailed setup instructions, see SETUP.md
echo.

pause
