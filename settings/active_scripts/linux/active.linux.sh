#!/bin/bash

# Set base paths
WORKSPACE_ROOT_PATH=$(dirname "$(readlink -f "$0")")

# python
source "${WORKSPACE_ROOT_PATH}/python/active_python.linux.sh"

# conan settings
export CONAN_HOME="$WORKSPACE_ROOT_PATH/conan/.conan"
export CONAN_USE_ALWAYS_SHORT_PATHS=1
source "${WORKSPACE_ROOT_PATH}/conan/conanbuild.sh"

# android settings
export ANDROID_SDK_ROOT="$WORKSPACE_ROOT_PATH/android/AndroidSDK"

# summary
python %WORKSPACE_ROOT_PATH%/summary.py