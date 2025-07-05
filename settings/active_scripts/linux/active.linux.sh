#!/bin/bash

# Set base paths
WORKSPACE_ROOT_PATH=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd -P)

# python
source "${WORKSPACE_ROOT_PATH}/python/active.sh"

# conan settings
export CONAN_HOME="$WORKSPACE_ROOT_PATH/conan/.conan"
export CONAN_USE_ALWAYS_SHORT_PATHS=1
source "${WORKSPACE_ROOT_PATH}/conan/conanbuild.sh"

# android settings
source "${WORKSPACE_ROOT_PATH}/android/active.sh"

# summary
python ${WORKSPACE_ROOT_PATH}/summary.py