@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_desktop_shortcuts.ps1" -Workspace "%~dp0."
exit /b %errorlevel%
