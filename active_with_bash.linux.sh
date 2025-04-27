#!/bin/bash

# Get the directory where this script is located
DEV_ENV_ROOT_PATH=$(dirname "$(readlink -f "$0")")

export CONAN_HOME="${DEV_ENV_ROOT_PATH}/conan/.conan"
export CONAN_USE_ALWAYS_SHORT_PATHS=1

# Source the conanbuild script (assuming there's a Linux version)
source "${DEV_ENV_ROOT_PATH}/conan/_generated/builder/macos/conanbuild.sh"

# Modify the prompt to show (arieo_dev) and current path
export PS1='(arieo_dev) \[\033[01;34m\]\w\[\033[00m\] \$ '

# Start a new interactive shell with the modified environment
exec bash