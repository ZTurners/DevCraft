@echo off
set DEVCRAFT_WORKSPACE=%~dp0
set DEVCRAFT_WORKSPACE=%DEVCRAFT_WORKSPACE:\=/%
set ZCODE_APP_EXE=

pushd "%~dp0"
call active.windows.bat

if %errorlevel% neq 0 (
    echo Error occurred in active.windows.bat
    popd
    exit /b %errorlevel%
)

:: start ZCode desktop app as a child process so it inherits this environment
for /f "usebackq delims=" %%A in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$exe = $null; $default = Join-Path $env:LOCALAPPDATA 'Programs\ZCode\ZCode.exe'; if (Test-Path -LiteralPath $default) { $exe = $default }; if (-not $exe) { foreach ($hive in 'Registry::HKEY_CURRENT_USER', 'Registry::HKEY_LOCAL_MACHINE') { $key = Get-Item -LiteralPath ($hive + '\Software\Microsoft\Windows\CurrentVersion\App Paths\ZCode.exe') -ErrorAction SilentlyContinue; if ($key) { $p = $key.GetValue(''); if ($p) { $p = $p.Trim([char]34); if (Test-Path -LiteralPath $p) { $exe = $p; break } } } } }; if (-not $exe) { foreach ($candidate in @(where.exe ZCode.exe 2>$null)) { $exe = $candidate; break } }; if ($exe) { Write-Output $exe }"`) do set "ZCODE_APP_EXE=%%A"

if "%ZCODE_APP_EXE%"=="" (
    echo ZCode desktop app is not installed.
    popd
    exit /b 1
)

:: TODO: remove later
:: --enable-unsafe-webgpu: force-enable WebGPU for GPUs not on Chrome's hardware whitelist
:: (e.g. Moore Threads). Newer Chrome versions already include them in the
:: whitelist, but the Chromium version bundled with ZCode is too old. Remove this flag
:: once ZCode ships a Chromium version that natively supports these GPUs.
start "" "%ZCODE_APP_EXE%" --enable-unsafe-webgpu
set ZCODE_EXIT=%errorlevel%
popd
exit /b %ZCODE_EXIT%
