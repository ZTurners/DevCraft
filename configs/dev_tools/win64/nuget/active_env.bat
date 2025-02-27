@echo off
set DEV_ENV_NUGET_USER_HOME=%DEV_ENV_BIN_PATH%\dev_tools\win64\.nuget
set DEV_ENV_NUGET_ENV_OUTPUT_DIR=%DEV_ENV_NUGET_USER_HOME%\.env_set

FOR /F "usebackq tokens=1,* delims==" %%i IN (%DEV_ENV_NUGET_ENV_OUTPUT_DIR%\environment.bat.env) DO (
    CALL SET "%%i=%%j"
)

::subst X: %DEV_ENV_NUGET_USER_HOME% -f 