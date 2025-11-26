@echo off
set DEVCRAFT_WORKSPACE=%~dp0

call %DEVCRAFT_WORKSPACE%active.windows.bat

if %errorlevel% neq 0 (
    echo Error occurred in otherscript.bat
    exit /b %errorlevel%
)

:: start vscode
code --user-data-dir=%DEVCRAFT_WORKSPACE%\vscode\.config --new-window 
