@echo off
rem Recursively find and run every active.bat under this workspace
rem Usage:
rem   active.windows.bat            -> runs each found active.bat
rem   active.windows.bat /list      -> lists all active.bat that would be run (safe preview)

set DEVCRAFT_HOST_TRIPLE=x86_64-windows-msvc
set DEVCRAFT_WORKSPACE=%~dp0
set DEVCRAFT_WORKSPACE=%DEVCRAFT_WORKSPACE:\=/%



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