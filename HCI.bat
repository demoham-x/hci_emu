@echo off
REM Run script for Bumble BLE Testing Framework

echo.
echo ============================================================
echo   Bumble BLE HCI Testing Framework
echo ============================================================
echo.


echo Starting application...
echo.

python C:\workspace\misc\bumble_hci\src\main.py

REM Store exit code
set ERROR_CODE=%errorlevel%

if %ERROR_CODE% neq 0 (
    echo.
    echo [ERROR] Application exited with error
    pause
    exit /b %ERROR_CODE%
)

pause
