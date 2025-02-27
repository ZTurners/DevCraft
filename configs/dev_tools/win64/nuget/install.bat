@echo off
set DEV_ENV_NUGET_CONFIG_HOME=%DEV_ENV_CONFIG_PATH%\dev_tools\win64\nuget
set DEV_ENV_NUGET_USER_HOME=%DEV_ENV_BIN_PATH%\dev_tools\win64\.nuget
set DEV_ENV_NUGET_ENV_OUTPUT_DIR=%DEV_ENV_NUGET_USER_HOME%\.env_set

:: Install tools from nuget.
nuget install %DEV_ENV_NUGET_CONFIG_HOME%\packages.config -OutputDirectory %DEV_ENV_NUGET_USER_HOME%

:: subst X: %NUGET_USER_HOME%
set DEV_ENV_WIN_SDK_CPP_PATH=%DEV_ENV_NUGET_USER_HOME%\Microsoft.Windows.SDK.CPP.10.0.22000.196
set DEV_ENV_WIN_SDK_CPP_X64_PATH=%DEV_ENV_NUGET_USER_HOME%\Microsoft.Windows.SDK.CPP.x64.10.0.22000.196

:: For clang to found lib
set LD_LIBRARY_PATH=%DEV_ENV_WIN_SDK_CPP_X64_PATH%\c\um\x64
set LIBRARY_PATH=%DEV_ENV_WIN_SDK_CPP_X64_PATH%\c\um\x64
set LIB=%DEV_ENV_WIN_SDK_CPP_X64_PATH%\c\um\x64
set LIB=%DEV_ENV_WIN_SDK_CPP_X64_PATH%\c\ucrt\x64;%LIB%

:: For clang to found includes
set INCLUDE=%DEV_ENV_WIN_SDK_CPP_PATH%\c\Include\10.0.22000.0\ucrt
set INCLUDE=%DEV_ENV_WIN_SDK_CPP_PATH%\c\Include\10.0.22000.0\um;%INCLUDE%
set INCLUDE=%DEV_ENV_WIN_SDK_CPP_PATH%\c\Include\10.0.22000.0\shared;%INCLUDE%
set INCLUDE=%DEV_ENV_WIN_SDK_CPP_PATH%\c\Include\10.0.22000.0\winrt;%INCLUDE%

:: set env for cmake
set CMAKE_WINDOWS_KITS_10_DIR=%WIN_SDK_CPP_PATH%\c

:: set windows runtime dll pathes
set DEV_EVN_PATH=%DEV_ENV_NUGET_USER_HOME%\VCRuntime.140.1.0.3\runtimes\win-x64
set DEV_EVN_PATH=%DEV_ENV_WIN_SDK_CPP_PATH%\c\Redist\10.0.22000.0\ucrt\DLLs\x64;%DEV_EVN_PATH%
set DEV_EVN_PATH=%DEV_ENV_NUGET_USER_HOME%\runtime.win10-x64.Microsoft.Net.Native.Compiler.2.2.11-rel-30601-02\tools\x64\ilc\tools64\;%DEV_EVN_PATH%

:: Write DEV_EVN_PATH to the env file to be used from active.bat
mkdir %DEV_ENV_NUGET_ENV_OUTPUT_DIR%
echo PATH=%DEV_EVN_PATH%;%%PATH%% > %DEV_ENV_NUGET_ENV_OUTPUT_DIR%/environment.bat.env
echo INCLUDE=%INCLUDE%;%%INCLUDE%% >> %DEV_ENV_NUGET_ENV_OUTPUT_DIR%/environment.bat.env
echo LIB=%LIB%;%%LIB%% >> %DEV_ENV_NUGET_ENV_OUTPUT_DIR%/environment.bat.env
echo LD_LIBRARY_PATH=%LD_LIBRARY_PATH%;%%LD_LIBRARY_PATH%% >> %DEV_ENV_NUGET_ENV_OUTPUT_DIR%/environment.bat.env
echo LIBRARY_PATH=%LIBRARY_PATH%;%%LIBRARY_PATH%% >> %DEV_ENV_NUGET_ENV_OUTPUT_DIR%/environment.bat.env
echo CMAKE_WINDOWS_KITS_10_DIR=%CMAKE_WINDOWS_KITS_10_DIR% >> %DEV_ENV_NUGET_ENV_OUTPUT_DIR%/environment.bat.env

:: Add DEV_ENV_NUGET_USER_HOME to set X: in bootstrap
echo DEV_ENV_NUGET_USER_HOME=%DEV_ENV_NUGET_USER_HOME% >> %DEV_ENV_NUGET_ENV_OUTPUT_DIR%/environment.bat.env
