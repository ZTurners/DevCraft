@echo off
set WORKSPACE_ROOT_PATH=%~dp0

:: python
call %WORKSPACE_ROOT_PATH%/python/active_python.windows.bat

:: conan
set CONAN_HOME=%WORKSPACE_ROOT_PATH%/conan/.conan
set CONAN_USE_ALWAYS_SHORT_PATHS=1
call %WORKSPACE_ROOT_PATH%/conan/conanbuild.bat

:: android
set "ANDROID_SDK_ROOT=%WORKSPACE_ROOT_PATH%/android/AndroidSDK"

:: summary
python %WORKSPACE_ROOT_PATH%/summary.py