echo off

set PYTHON_WORKSPACE_PATH=%~dp0

:: Python Installer Batch Script
:: Usage: Just double-click this .bat file to run it (Admin rights required)
:: Check if jq is available (optional, for more complex JSON parsing)
set "PYTHON_SETTING_FILE=%PYTHON_WORKSPACE_PATH%/version.txt"

:: Read the file into a variable (strip whitespace)
for /f "delims=" %%i in (%PYTHON_SETTING_FILE%) do (
    set PYTHON_VERSION=%%i
)
 
set PYTHON_INSTALL_PATH=%PYTHON_WORKSPACE_PATH%python_%PYTHON_VERSION%
set PYTHON_SCRIPTS_PATH=%PYTHON_INSTALL_PATH%Scripts

:: Add to Environment to PATH
echo Adding Python to PATH...
set "PATH=%PYTHON_INSTALL_PATH%;%PYTHON_SCRIPTS_PATH%;%PATH%"

