@echo off
set "DEV_ENV_ROOT_PATH=%~dp0"

call "%DEV_ENV_ROOT_PATH%bootstrap.windows.bat"
if %errorlevel% neq 0 (
    echo Bootstrap failed, aborting install.
    exit /b %errorlevel%
)
"%DEV_ENV_ROOT_PATH%workspace\bootstrap\python\python.exe" "%DEV_ENV_ROOT_PATH%configs\install.py"