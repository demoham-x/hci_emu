@echo off
REM Run script for Bumble BLE Testing Framework

echo.
echo ============================================================
echo   Bumble BLE Testing Framework
echo ============================================================
echo.

REM Activate virtual environment if it exists (optional)
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [INFO] Virtual environment activated.
) else (
    echo [INFO] No virtual environment found - using system Python.
)

echo Starting application...
echo.

python src\main.py

REM Store exit code
set ERROR_CODE=%errorlevel%

REM Deactivate virtual environment if it was activated
if exist "venv\Scripts\deactivate.bat" (
    call venv\Scripts\deactivate.bat
)

if %ERROR_CODE% neq 0 (
    echo.
    echo [ERROR] Application exited with error
    pause
    exit /b %ERROR_CODE%
)

pause
