@echo off
rem Recursively find and run every active.bat under this workspace
rem Usage:
rem   active.windows.bat            -> runs each found active.bat
rem   active.windows.bat /list      -> lists all active.bat that would be run (safe preview)

set DEVCRAFT_HOST_TRIPLE=x86_64-windows-msvc
rem Keep the workspace root without a trailing separator; callers add their own.
set DEVCRAFT_WORKSPACE=%~dp0
set DEVCRAFT_WORKSPACE=%DEVCRAFT_WORKSPACE:\=/%
set DEVCRAFT_WORKSPACE=%DEVCRAFT_WORKSPACE:~0,-1%



if not "%LIST_ONLY%"=="1" (
	rem Enable long path support (total path length beyond 260 chars), system-wide
	rem Direct write when already elevated; otherwise pops the native UAC dialog to elevate on the spot
	reg query "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled 2>nul | find "0x1" >nul
	if errorlevel 1 (
		reg add "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled /t REG_DWORD /d 1 /f >nul 2>&1
		if errorlevel 1 (
			powershell -NoProfile -Command "Start-Process reg -Verb RunAs -WindowStyle Hidden -Wait -ArgumentList 'add HKLM\SYSTEM\CurrentControlSet\Control\FileSystem /v LongPathsEnabled /t REG_DWORD /d 1 /f'" >nul 2>&1
			reg query "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled 2>nul | find "0x1" >nul
			if errorlevel 1 (
				echo [WARN] Long path support NOT enabled: UAC prompt declined or write failed. Rerun this script to retry, or from an elevated prompt run:
				echo        reg add "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled /t REG_DWORD /d 1 /f
			) else (
				echo [OK] Long path support enabled via UAC elevation: total path length up to 32767 chars
			)
		) else (
			echo [OK] Long path support enabled: total path length up to 32767 chars
		)
	)
)

rem Iterate through immediate subdirectories and run active.bat if it exists
for /d %%D in (*) do (
	if exist "%%D\active.bat" (
		if "%LIST_ONLY%"=="1" (
			echo [LIST] %%~fD\active.bat
		) else (
			echo ------------------------------------------------------------------------
			echo Running: %%~fD\active.bat
			pushd "%%D"
			call active.bat
			popd
		)
	)
)
@REM call %DEVCRAFT_WORKSPACE%\conan\conanbuild.bat
@REM call %DEVCRAFT_WORKSPACE%\conan\conanvcvars.bat