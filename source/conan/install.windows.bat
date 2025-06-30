@echo off
set DEV_ENV_CONAN_ROOT_PATH=%~dp0

set CONAN_HOME=%DEV_ENV_CONAN_ROOT_PATH%\.conan
set CONAN_USE_ALWAYS_SHORT_PATHS=1

:: Install dev_tools from conan
mkdir %CONAN_HOME%
copy %DEV_ENV_CONAN_ROOT_PATH%\global.conf %CONAN_HOME%
copy %DEV_ENV_CONAN_ROOT_PATH%\settings.yml %CONAN_HOME%
copy %DEV_ENV_CONAN_ROOT_PATH%\remotes.json %CONAN_HOME%

:: https://stackoverflow.com/questions/69719363/httpsconnectionpool-error-when-trying-to-install-gtest-with-conan
:: https://github.com/conan-io/conan/issues/9695
:: conan config install https://github.com/conan-io/conanclientcert.git
conan profile detect --force
conan install %DEV_ENV_CONAN_ROOT_PATH%\conanfile.txt --update --generator CMakeToolchain --generator VirtualBuildEnv --output-folder %DEV_ENV_CONAN_ROOT_PATH%\_generated\builder\windows --build never --profile=%DEV_ENV_CONAN_ROOT_PATH%\profiles\builder\conan_builder_profile.windows.txt
conan install %DEV_ENV_CONAN_ROOT_PATH%\conanfile.txt --update --generator CMakeToolchain --generator VirtualBuildEnv --output-folder %DEV_ENV_CONAN_ROOT_PATH%\_generated\builder\ubuntu --build never --profile=%DEV_ENV_CONAN_ROOT_PATH%\profiles\builder\conan_builder_profile.ubuntu.txt