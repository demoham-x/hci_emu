@echo off
REM Run script for Bumble BLE Testing Framework

echo.
echo ============================================================
echo   Bumble BLE Testing Framework
echo ============================================================
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo [ERROR] Virtual environment not found!
    echo Please run setup.bat first to install dependencies.
    pause
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

echo Starting application...
echo.

python src\main.py

REM Store exit code
set ERROR_CODE=%errorlevel%

REM Deactivate virtual environment
call venv\Scripts\deactivate.bat

if %ERROR_CODE% neq 0 (
    echo.
    echo [ERROR] Application exited with error
    pause
    exit /b %ERROR_CODE%
)

pause
