#!/bin/bash
# get the directory of bootstrap.sh as the root dir.
if [ -z "$DEV_ENV_ROOT_PATH" ]
then
    DEV_ENV_ROOT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

echo "The dev environment root path is $DEV_ENV_ROOT_PATH"
DEV_ENV_BIN_PATH=$DEV_ENV_ROOT_PATH/bin
DEV_ENV_TMP_PATH=$DEV_ENV_ROOT_PATH/.temp
DEV_ENV_BOOTSTRAP_PATH=$DEV_ENV_ROOT_PATH/bootstrap
DEV_ENV_CONFIG_PATH=$DEV_ENV_ROOT_PATH/configs

# Install tools from manual
DEV_ENV_MANUAL_CONFIG_HOME=$DEV_ENV_CONFIG_PATH/dev_tools/linux/manual
chmod +x $DEV_ENV_MANUAL_CONFIG_HOME/active_env.sh
. $DEV_ENV_MANUAL_CONFIG_HOME/active_env.sh

# Install dev_tools from conan
DEV_ENV_CONAN_CONFIG_HOME=$DEV_ENV_CONFIG_PATH/dev_tools/linux/conan
chmod +x $DEV_ENV_CONAN_CONFIG_HOME/active_env.sh
. $DEV_ENV_CONAN_CONFIG_HOME/active_env.sh

# Set the PS1
export CONAN_OLD_PS1="$PS1"
export PS1="(devenv) $PS1"