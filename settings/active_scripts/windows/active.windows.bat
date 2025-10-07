@echo off
set WORKSPACE_ROOT_PATH=%~dp0

:: python
call %WORKSPACE_ROOT_PATH%/python/active.bat

:: conan
set CONAN_HOME=%WORKSPACE_ROOT_PATH%/conan/.conan
set CONAN_USE_ALWAYS_SHORT_PATHS=1
call %WORKSPACE_ROOT_PATH%/conan/conanbuild.bat

:: android
call %WORKSPACE_ROOT_PATH%/android/active.bat

:: rust
call %WORKSPACE_ROOT_PATH%/rust/active.bat

:: summary
python %WORKSPACE_ROOT_PATH%/summary.py