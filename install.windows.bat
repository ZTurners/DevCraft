@echo off
set DEV_ENV_ROOT_PATH=%~dp0
SETLOCAL
    call %DEV_ENV_ROOT_PATH%/conan/install.windows.bat
ENDLOCAL

SETLOCAL
    call %DEV_ENV_ROOT_PATH%/android/install.windows.bat
ENDLOCAL

SETLOCAL
    call %DEV_ENV_ROOT_PATH%/conan/_generated/builder/windows/conanbuild.bat

    @echo off
    for /f "tokens=*" %%A in (%DEV_ENV_ROOT_PATH%/android_sdk/sdk_install_command.txt) do (
        echo Executing: %%A
        %%A
    )
ENDLOCAL



