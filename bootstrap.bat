@echo off
set DEV_ENV_ROOT_PATH=%~dp0
set DEV_ENV_BIN_PATH=%DEV_ENV_ROOT_PATH%bin
set DEV_ENV_TMP_PATH=%DEV_ENV_ROOT_PATH%.temp
set DEV_ENV_BOOTSTRAP_PATH=%DEV_ENV_BIN_PATH%\bootstrap
set DEV_ENV_CONFIG_PATH=%DEV_ENV_ROOT_PATH%configs

:: Install dev_tools from manual
call %DEV_ENV_CONFIG_PATH%\dev_tools\win64\manual\active_env.bat

:: Install dev_tools from nuget
call %DEV_ENV_CONFIG_PATH%\dev_tools\win64\nuget\active_env.bat

:: Install dev_tools from conan
call %DEV_ENV_CONFIG_PATH%\dev_tools\win64\conan\active_env.bat

SET "PROMPT=(dev_env) %PROMPT%"
cmd /k
