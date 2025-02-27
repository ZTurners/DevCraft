#!/bin/bash
# get the directory of bootstrap.sh as the root dir.
DEV_ENV_ROOT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "The dev environment root path is $DEV_ENV_ROOT_PATH"

DEV_ENV_BIN_PATH=$DEV_ENV_ROOT_PATH/bin
DEV_ENV_TMP_PATH=$DEV_ENV_ROOT_PATH/.temp
DEV_ENV_BOOTSTRAP_PATH=$DEV_ENV_ROOT_PATH/bootstrap
DEV_ENV_CONFIG_PATH=$DEV_ENV_ROOT_PATH/configs
DEV_ENV_WORKSPACE_PATH=$DEV_ENV_ROOT_PATH/workspaces

# Install tools from manual
DEV_ENV_MANUAL_CONFIG_HOME=$DEV_ENV_CONFIG_PATH/dev_tools/linux/manual
chmod +x $DEV_ENV_MANUAL_CONFIG_HOME/install.sh
source $DEV_ENV_MANUAL_CONFIG_HOME/install.sh

# Install dev_tools from conan
DEV_ENV_CONAN_CONFIG_HOME=$DEV_ENV_CONFIG_PATH/dev_tools/linux/conan
chmod +x $DEV_ENV_CONAN_CONFIG_HOME/install.sh
source $DEV_ENV_CONAN_CONFIG_HOME/install.sh