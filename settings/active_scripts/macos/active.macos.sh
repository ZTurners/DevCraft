#!/bin/bash

# Set base paths
WORKSPACE_ROOT_PATH=$(dirname "$0")

# conan settings
export CONAN_HOME="$WORKSPACE_ROOT_PATH/.conan"
export CONAN_USE_ALWAYS_SHORT_PATHS=1
source "$WORKSPACE_ROOT_PATH/_generated/conan/builder/windows/conanbuild.sh" 2>/dev/null || \
    source "$WORKSPACE_ROOT_PATH/_generated/conan/builder/windows/conanbuild.bat" 2>/dev/null

# android settings
export ANDROID_SDK_ROOT="$WORKSPACE_ROOT_PATH/android/AndroidSDK"