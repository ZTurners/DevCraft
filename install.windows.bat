@echo off
set DEV_ENV_ROOT_PATH=%~dp0

call %DEV_ENV_ROOT_PATH%/bootstrap.windows.bat
python %DEV_ENV_ROOT_PATH%/install.py




