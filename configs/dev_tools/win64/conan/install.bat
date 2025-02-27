@echo off
set DEV_ENV_CONAN_USER_HOME=%DEV_ENV_BIN_PATH%\dev_tools\win64
set DEV_ENV_CONAN_ENV_OUTPUT_DIR=%DEV_ENV_CONAN_USER_HOME%\.conan\.env_set

:: Install dev_tools from conan
mkdir %DEV_ENV_CONAN_USER_HOME%
mkdir %DEV_ENV_CONAN_USER_HOME%\.conan
copy %DEV_ENV_CONAN_CONFIG_HOME%\*.* %DEV_ENV_CONAN_USER_HOME%\.conan

set CONAN_USER_HOME=%DEV_ENV_CONAN_USER_HOME%
set CONAN_USE_ALWAYS_SHORT_PATHS=1
set CONAN_USER_HOME_SHORT=%CONAN_USER_HOME%\.conan_s

:: https://stackoverflow.com/questions/69719363/httpsconnectionpool-error-when-trying-to-install-gtest-with-conan
:: https://github.com/conan-io/conan/issues/9695
:: conan config install https://github.com/conan-io/conanclientcert.git
conan install %DEV_ENV_CONAN_CONFIG_HOME%\conanfile.txt --update --install-folder %DEV_ENV_CONAN_ENV_OUTPUT_DIR% --build never --profile %DEV_ENV_CONAN_CONFIG_HOME%\conan_profile.txt