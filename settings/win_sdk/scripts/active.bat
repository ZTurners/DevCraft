@echo off

call "%~dp0win_sdk_version.bat"

if not defined DEVCRAFT_WINDOWS_SDK_VERSION if defined WINDOWS_SDK_VERSION set DEVCRAFT_WINDOWS_SDK_VERSION=%WINDOWS_SDK_VERSION%

echo Environment variables set successfully
echo DEVCRAFT_WINDOWS_SDK_VERSION=%DEVCRAFT_WINDOWS_SDK_VERSION%
