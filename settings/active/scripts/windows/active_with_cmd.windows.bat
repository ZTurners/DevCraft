@echo off
set DEVCRAFT_WORKSPACE=%~dp0

call %DEVCRAFT_WORKSPACE%active.windows.bat

if %errorlevel% neq 0 (
    echo Error occurred in otherscript.bat
    exit /b %errorlevel%
)

SET "PROMPT=(arieo_dev) %PROMPT%"
cmd /k
