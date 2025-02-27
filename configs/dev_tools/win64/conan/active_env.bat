@echo off
set DEV_ENV_CONAN_USER_HOME=%DEV_ENV_BIN_PATH%\dev_tools\win64
set DEV_ENV_CONAN_ENV_OUTPUT_DIR=%DEV_ENV_CONAN_USER_HOME%\.conan\.env_set
FOR /F "usebackq tokens=1,* delims==" %%i IN (%DEV_ENV_CONAN_ENV_OUTPUT_DIR%\environment.bat.env) DO (
    CALL SET "%%i=%%j"
)