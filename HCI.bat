@echo off
REM Run script for Bumble BLE Testing Framework

echo.
echo ============================================================
echo   Bumble BLE HCI Testing Framework
echo ============================================================
echo.


echo Starting application...
echo.
set "BASE=%~dp0"

REM Build path to main.py
set "TARGET=%BASE%src\main.py"

REM Check if the file exists
if not exist "%TARGET%" (
    echo [ERROR] Cannot find: "%TARGET%"
    exit /b 1
)

REM Run Python
python "%TARGET%

REM Store exit code
set ERROR_CODE=%errorlevel%

if %ERROR_CODE% neq 0 (
    echo.
    echo [ERROR] Application exited with error
    pause
    exit /b %ERROR_CODE%
)

pause
