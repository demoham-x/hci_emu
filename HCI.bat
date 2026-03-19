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
set "BASE=%~dp0"
set "MAIN=%BASE%src\hciemu\main.py"
set "BASEDIR=%BASE%src"

REM Prefer installed package command when available.
where hciemu >nul 2>nul
if %errorlevel%==0 (
    hciemu %*
) else (
    REM Fallback for plain git clone usage.
    if not exist "%MAIN%" (
        echo [ERROR] Cannot find: "%MAIN%"
        exit /b 1
    )
    pushd "%BASEDIR%"
    python -m hciemu.main %*
    popd
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
