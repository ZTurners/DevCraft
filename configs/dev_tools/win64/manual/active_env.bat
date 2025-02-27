@echo off
set DEV_ENV_MANUAL_USER_HOME=%DEV_ENV_BIN_PATH%\dev_tools\win64\.manual
set DEV_ENV_MANUAL_ENV_OUTPUT_DIR=%DEV_ENV_MANUAL_USER_HOME%\.env_set

FOR /F "usebackq tokens=1,* delims==" %%i IN (%DEV_ENV_MANUAL_ENV_OUTPUT_DIR%\environment.bat.env) DO (
    CALL SET "%%i=%%j"
)