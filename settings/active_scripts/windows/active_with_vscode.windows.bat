@echo off
set WORKSPACE_ROOT=%~dp0

call %WORKSPACE_ROOT%active.windows.bat

if %errorlevel% neq 0 (
    echo Error occurred in otherscript.bat
    exit /b %errorlevel%
)

:: start vscode
code --user-data-dir=%WORKSPACE_ROOT%\vscode\.config
