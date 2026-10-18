@echo off
rem Keep the workspace root without a trailing separator; callers add their own.
set DEVCRAFT_WORKSPACE=%~dp0
set DEVCRAFT_WORKSPACE=%DEVCRAFT_WORKSPACE:\=/%
set DEVCRAFT_WORKSPACE=%DEVCRAFT_WORKSPACE:~0,-1%
set DSH_APP_EXE=

pushd "%~dp0"
call active.windows.bat

if %errorlevel% neq 0 (
    echo Error occurred in active.windows.bat
    popd
    exit /b %errorlevel%
)

:: start DeepSeek Harness desktop app as a child process so it inherits this environment
:: locate the desktop executable via the dsh:// protocol handler registration, which the app
:: itself writes at first launch: HKEY_CLASSES_ROOT\dsh\shell\open\command;
:: the exe path is the first token of the registered command
for /f "usebackq delims=" %%A in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = $null; $key = Get-Item -LiteralPath 'Registry::HKEY_CLASSES_ROOT\dsh\shell\open\command' -ErrorAction SilentlyContinue; if ($key) { $cmd = $key.GetValue(''); if ($cmd) { $p = $cmd.Trim(); if ($p.StartsWith([char]34)) { $j = $p.IndexOf([char]34, 1); if ($j -gt 0) { $p = $p.Substring(1, $j - 1) } } else { $i = $p.IndexOf(' '); if ($i -gt 0) { $p = $p.Substring(0, $i) } }; if (-not (Test-Path -LiteralPath $p)) { $p = $null } } }; if ($p) { Write-Output $p }"`) do set "DSH_APP_EXE=%%A"

if "%DSH_APP_EXE%"=="" (
    echo DeepSeek Harness desktop app is not installed or its dsh:// protocol handler is not registered.
    popd
    exit /b 1
)

start "" "%DSH_APP_EXE%" %*
set DSH_EXIT=%errorlevel%
popd
exit /b %DSH_EXIT%
