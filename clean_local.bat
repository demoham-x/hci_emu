@echo off
setlocal
pushd "%~dp0"
echo Cleaning local environment artifacts...

rem Remove top-level virtual environments and build artifacts
for %%d in (venv env .venv build dist .eggs) do (
    if exist "%%d" rmdir /s /q "%%d"
)

rem Remove egg-info folders at repo root
for /d %%d in (*.egg-info) do (
    rmdir /s /q "%%d"
)

rem Remove caches recursively
for /d /r %%d in (__pycache__) do (
    if exist "%%d" rmdir /s /q "%%d"
)
for /d /r %%d in (.pytest_cache) do (
    if exist "%%d" rmdir /s /q "%%d"
)
for /d /r %%d in (.mypy_cache) do (
    if exist "%%d" rmdir /s /q "%%d"
)
for /d /r %%d in (.ruff_cache) do (
    if exist "%%d" rmdir /s /q "%%d"
)

rem Remove coverage artifacts
if exist ".coverage" del /f /q ".coverage"
del /f /q ".coverage.*" >nul 2>&1
if exist "htmlcov" rmdir /s /q "htmlcov"

rem Remove captures and local CSV logs
if exist "captures" rmdir /s /q "captures"
del /f /q "notifications_*.csv" >nul 2>&1

rem Remove log files
if exist "logs" (
    del /f /q "logs\*.log" >nul 2>&1
    del /f /q "logs\*.btsnoop" >nul 2>&1
    del /f /q "logs\*.fsc" >nul 2>&1
    del /f /q "logs\*.pcap" >nul 2>&1
)

echo Done.
popd
endlocal
