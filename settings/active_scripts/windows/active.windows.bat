@echo off
set WORKSPACE_ROOT_PATH=%~dp0

:: python
call %WORKSPACE_ROOT_PATH%/python/active_python.windows.bat

:: conan
set CONAN_HOME=%WORKSPACE_ROOT_PATH%/.conan
set CONAN_USE_ALWAYS_SHORT_PATHS=1
call %WORKSPACE_ROOT_PATH%/_generated/conan/builder/windows/conanbuild.bat

:: android
set "ANDROID_SDK_ROOT=%WORKSPACE_ROOT_PATH%/android/AndroidSDK"