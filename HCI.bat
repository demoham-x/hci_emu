@echo off
REM Run script for Bumble BLE Testing Framework
setlocal

echo.
echo ============================================================
echo   Bumble BLE HCI Testing Framework
echo ============================================================
echo.


echo Starting application...
echo.

REM Prefer installed package command when available.
where hciemu >nul 2>nul
if %errorlevel%==0 (
    hciemu %*
) else (
    REM Fallback for plain git clone usage.
    set "BASE=%~dp0"
    set "TARGET=%BASE%src\main.py"
    if not exist "%TARGET%" (
        echo [ERROR] Cannot find: "%TARGET%"
        exit /b 1
    )
    python "%TARGET%" %*
)

REM Store exit code
set ERROR_CODE=%errorlevel%

if %ERROR_CODE% neq 0 (
    echo.
    echo [ERROR] Application exited with error
    pause
    exit /b %ERROR_CODE%
)

pause
endlocal
