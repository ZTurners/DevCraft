@echo off
rem Keep the workspace root without a trailing separator; callers add their own.
set DEVCRAFT_WORKSPACE=%~dp0
set DEVCRAFT_WORKSPACE=%DEVCRAFT_WORKSPACE:\=/%
set DEVCRAFT_WORKSPACE=%DEVCRAFT_WORKSPACE:~0,-1%

call %DEVCRAFT_WORKSPACE%/active.windows.bat

if %errorlevel% neq 0 (
    echo Error occurred in otherscript.bat
    exit /b %errorlevel%
)

SET "PROMPT=(arieo_dev) %PROMPT%"
cmd /k
