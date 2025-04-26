@echo off
set DEV_ENV_ROOT_PATH=%~dp0

set CONAN_HOME=%DEV_ENV_ROOT_PATH%\conan\.conan
set CONAN_USE_ALWAYS_SHORT_PATHS=1

call %DEV_ENV_ROOT_PATH%\conan\_generated\builder\windows\conanbuild.bat
SET "PROMPT=(arieo_dev) %PROMPT%"
cmd /k
