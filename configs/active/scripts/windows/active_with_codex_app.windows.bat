@echo off
rem Keep the workspace root without a trailing separator; callers add their own.
set DEVCRAFT_WORKSPACE=%~dp0
set DEVCRAFT_WORKSPACE=%DEVCRAFT_WORKSPACE:\=/%
set DEVCRAFT_WORKSPACE=%DEVCRAFT_WORKSPACE:~0,-1%
set CODEX_APP_EXE=

pushd "%~dp0"
call active.windows.bat

if %errorlevel% neq 0 (
    echo Error occurred in active.windows.bat
    popd
    exit /b %errorlevel%
)

:: start Codex desktop app as a child process so it inherits this environment
for /f "usebackq delims=" %%A in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$install = $null; $pkg = @(Get-AppxPackage -Name OpenAI.Codex -ErrorAction SilentlyContinue)[0]; if ($pkg) { $install = $pkg.InstallLocation } else { foreach ($candidatePath in @(where.exe codex.exe 2>$null)) { $marker = '\WindowsApps\'; $index = $candidatePath.IndexOf($marker, [System.StringComparison]::OrdinalIgnoreCase); if ($index -ge 0) { $base = $candidatePath.Substring(0, $index + $marker.Length); $folder = $candidatePath.Substring($index + $marker.Length).Split([char]92)[0]; if ($folder -like 'OpenAI.Codex_*') { $install = Join-Path $base $folder; break } } } }; if (-not $install) { foreach ($file in Get-ChildItem -Path (Join-Path $env:ProgramFiles 'WindowsApps\OpenAI.Codex_*\AppxManifest.xml') -ErrorAction SilentlyContinue) { $install = $file.DirectoryName; break } }; if ($install) { $manifestPath = Join-Path $install 'AppxManifest.xml'; if (Test-Path -LiteralPath $manifestPath) { [xml]$manifest = Get-Content -LiteralPath $manifestPath; $app = @($manifest.Package.Applications.Application)[0]; if ($app -and $app.Executable) { $exePath = Join-Path $install $app.Executable; if (Test-Path -LiteralPath $exePath) { Write-Output $exePath } } } }"`) do set "CODEX_APP_EXE=%%A"

if "%CODEX_APP_EXE%"=="" (
    echo Codex desktop app is not installed.
    popd
    exit /b 1
)

start "" "%CODEX_APP_EXE%"
set CODEX_EXIT=%errorlevel%
popd
exit /b %CODEX_EXIT%
