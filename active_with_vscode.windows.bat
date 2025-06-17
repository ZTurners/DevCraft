@echo off
set DEV_ENV_ROOT_PATH=%~dp0

set CONAN_HOME=%DEV_ENV_ROOT_PATH%/conan/.conan
set CONAN_USE_ALWAYS_SHORT_PATHS=1

set VS_CODE_INIT_USER_SETTING=%DEV_ENV_ROOT_PATH%/vscode/init_user_settings.json
set VS_CODE_USER_SETTING=%DEV_ENV_ROOT_PATH%/vscode/.config/User/settings.json

call %DEV_ENV_ROOT_PATH%/conan/_generated/builder/windows/conanbuild.bat

if not exist %VS_CODE_USER_SETTING% (
    mkdir %DEV_ENV_ROOT_PATH%/vscode/.config/User
    copy %VS_CODE_INIT_USER_SETTING% %VS_CODE_USER_SETTING%
)

code --user-data-dir=%DEV_ENV_ROOT_PATH%/vscode/.config
