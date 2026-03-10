@echo off

call "%~dp0vs_version.bat"
call "%~dp0win_sdk_version.bat"

echo Environment variables set successfully
echo VISUAL_STUDIO_MAJOR_VERSION=%VISUAL_STUDIO_MAJOR_VERSION%
echo WINDOWS_SDK_VERSION=%WINDOWS_SDK_VERSION%
