@echo off
set DEV_ENV_ROOT_PATH=%~dp0
SETLOCAL
call %DEV_ENV_ROOT_PATH%\conan\install.windows.bat
ENDLOCAL

