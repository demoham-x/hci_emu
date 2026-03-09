@echo off
REM Run script for Bumble BLE Testing Framework

echo.
echo ============================================================
echo   Bridging Windows BT USB
echo ============================================================
echo.

bumble-hci-bridge usb:0 tcp-server:127.0.0.1:9001

REM Store exit code
set ERROR_CODE=%errorlevel%

if %ERROR_CODE% neq 0 (
    echo.
    echo [ERROR] Bridge exited with error
    pause
    exit /b %ERROR_CODE%
)
