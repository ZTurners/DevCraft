@echo off
set WORKSPACE_ROOT=%~dp0

:: python
call %WORKSPACE_ROOT%/python/active.bat

:: conan
set CONAN_HOME=%WORKSPACE_ROOT%/conan/.conan
set CONAN_USE_ALWAYS_SHORT_PATHS=1
call %WORKSPACE_ROOT%/conan/conanbuild.bat

:: android
call %WORKSPACE_ROOT%/android/active.bat

:: jdk
call %WORKSPACE_ROOT%/jdk/active.bat

:: rust
call %WORKSPACE_ROOT%/rust/active.bat

:: SDK
call %WORKSPACE_ROOT%/sdk/active.bat

:: Tools
call %WORKSPACE_ROOT%/tools/active.bat

:: summary
python %WORKSPACE_ROOT%/summary.py