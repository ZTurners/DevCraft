@echo off
set DEVCRAFT_WORKSPACE=%~dp0
set DEVCRAFT_WORKSPACE=%DEVCRAFT_WORKSPACE:\=/%
set CODEX_CLI_EXE=

pushd "%~dp0"
call active.windows.bat

if %errorlevel% neq 0 (
    echo Error occurred in active.windows.bat
    popd
    exit /b %errorlevel%
)

for /f "usebackq delims=" %%A in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$exe = $null; $root = Join-Path $env:LOCALAPPDATA 'OpenAI\Codex\bin'; if (Test-Path -LiteralPath $root) { foreach ($candidate in Get-ChildItem -LiteralPath $root -Recurse -Filter codex.exe -File -ErrorAction SilentlyContinue) { $exe = $candidate.FullName; break } }; if (-not $exe) { foreach ($candidate in @(where.exe codex.exe 2>$null)) { if ($candidate -notmatch '\\app\\Codex\.exe$') { $exe = $candidate; break } } }; if ($exe) { Write-Output $exe }"`) do set "CODEX_CLI_EXE=%%A"

if "%CODEX_CLI_EXE%"=="" (
    echo Codex CLI is not installed.
    popd
    exit /b 1
)

"%CODEX_CLI_EXE%" %*
set CODEX_EXIT=%errorlevel%
popd
exit /b %CODEX_EXIT%
