@echo off
set DEV_ENV_ROOT_PATH=%~dp0
set DEV_ENV_CONFIG_PATH=%DEV_ENV_ROOT_PATH%configs

set DEV_ENV_BIN_PATH=%DEV_ENV_ROOT_PATH%bin
set DEV_ENV_TMP_PATH=%DEV_ENV_ROOT_PATH%.temp
set DEV_ENV_WORKSPACE_PATH=%DEV_ENV_ROOT_PATH%workspaces

mkdir %DEV_ENV_TMP_PATH%
mkdir %DEV_ENV_BIN_PATH%
mkdir %DEV_ENV_WORKSPACE_PATH%


:: Install dev_tools from manual
set DEV_ENV_MANUAL_CONFIG_HOME=%DEV_ENV_CONFIG_PATH%\dev_tools\win64\manual
call %DEV_ENV_MANUAL_CONFIG_HOME%\install.bat

:: Install dev_tools from nuget
SETLOCAL
set DEV_ENV_NUGET_CONFIG_HOME=%DEV_ENV_CONFIG_PATH%\dev_tools\win64\nuget
call %DEV_ENV_NUGET_CONFIG_HOME%\install.bat
ENDLOCAL

:: Install dev_tools from conan
SETLOCAL
set DEV_ENV_CONAN_CONFIG_HOME=%DEV_ENV_CONFIG_PATH%\dev_tools\win64\conan
call %DEV_ENV_CONAN_CONFIG_HOME%\install.bat
ENDLOCAL