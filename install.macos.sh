#!/bin/bash
DEV_ENV_ROOT_PATH=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
source "$DEV_ENV_ROOT_PATH/conan/install.macos.sh"

{
    source "$DEV_ENV_ROOT_PATH/active_with_bash.macos.sh"
    source "$DEV_ENV_ROOT_PATH/android_sdk/sdk_install_command.txt"
}
