@echo off

call ./active_windows.bat
:: start vscode
code --user-data-dir=%WORKSPACE_ROOT_PATH%\vscode\.config
