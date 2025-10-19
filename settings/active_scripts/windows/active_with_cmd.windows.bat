@echo off
set WORKSPACE_ROOT=%~dp0

call %WORKSPACE_ROOT%active.windows.bat

if %errorlevel% neq 0 (
    echo Error occurred in otherscript.bat
    exit /b %errorlevel%
)

SET "PROMPT=(arieo_dev) %PROMPT%"
cmd /k
