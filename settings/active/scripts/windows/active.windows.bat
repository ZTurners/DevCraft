@echo off
rem Recursively find and run every active.bat under this workspace
rem Usage:
rem   active.windows.bat            -> runs each found active.bat
rem   active.windows.bat /list      -> lists all active.bat that would be run (safe preview)

set DEVCRAFT_WORKSPACE=%~dp0
rem Use DIR to find all files named active.bat and iterate over them
for /f "delims=" %%F in ('dir /b /s /a-d "active.bat" ^| sort') do (
	rem Skip this runner file if it happens to be named active.bat in the root
	if /I NOT "%%~fF"=="%~f0" (
		if "%LIST_ONLY%"=="1" (
			echo [LIST] %%~fF
		) else (
			echo ------------------------------------------------------------------------
			echo Running: %%~fF
			pushd "%%~dpF"
			call "%%~nxF"
			popd
		)
	)
)
@REM call %DEVCRAFT_WORKSPACE%\conan\conanbuild.bat
@REM call %DEVCRAFT_WORKSPACE%\conan\conanvcvars.bat