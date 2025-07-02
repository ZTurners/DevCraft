@echo off
set WORKSPACE_ROOT_PATH=%~dp0

call %WORKSPACE_ROOT_PATH%active.windows.bat

if %errorlevel% neq 0 (
    echo Error occurred in otherscript.bat
    exit /b %errorlevel%
)

:: start vscode
code --user-data-dir=%WORKSPACE_ROOT_PATH%\vscode\.config
