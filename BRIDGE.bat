@echo off
REM Run script for Bumble BLE Testing Framework
setlocal

echo.
echo ============================================================
echo   Bridging Windows BT USB
echo ============================================================
echo.

where bumble-hci-bridge >nul 2>nul
if not %errorlevel%==0 (
    echo [ERROR] 'bumble-hci-bridge' not found in PATH.
    echo Install dependencies first: pip install -r requirements.txt
    pause
    exit /b 1
)

if "%~1"=="" (
    bumble-hci-bridge usb:0 tcp-server:127.0.0.1:9001
) else (
    bumble-hci-bridge %*
)

REM Store exit code
set ERROR_CODE=%errorlevel%

if %ERROR_CODE% neq 0 (
    echo.
    echo [ERROR] Bridge exited with error
    pause
    exit /b %ERROR_CODE%
)

endlocal
