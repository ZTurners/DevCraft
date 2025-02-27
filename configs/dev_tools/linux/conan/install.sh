DEV_ENV_CONAN_USER_HOME=$DEV_ENV_BIN_PATH/dev_tools/linux
DEV_ENV_CONAN_ENV_OUTPUT_DIR=$DEV_ENV_BIN_PATH/dev_tools/linux/.conan/.env_set

# Install dev_tools from conan
export CONAN_USER_HOME=$DEV_ENV_CONAN_USER_HOME
mkdir -p $DEV_ENV_CONAN_USER_HOME
mkdir -p $DEV_ENV_CONAN_USER_HOME/.conan
cp $DEV_ENV_CONAN_CONFIG_HOME/*.* $DEV_ENV_CONAN_USER_HOME/.conan/

# https://stackoverflow.com/questions/69719363/httpsconnectionpool-error-when-trying-to-install-gtest-with-conan
# https://github.com/conan-io/conan/issues/9695
# conan config install https://github.com/conan-io/conanclientcert.git
conan install $DEV_ENV_CONAN_CONFIG_HOME/conanfile.txt --update --install-folder $DEV_ENV_CONAN_ENV_OUTPUT_DIR --build never --profile $DEV_ENV_CONAN_CONFIG_HOME/conan_profile.txt

# Call this by "source activate.sh" to setup the environment.
chmod +x $DEV_ENV_CONAN_ENV_OUTPUT_DIR/activate.sh