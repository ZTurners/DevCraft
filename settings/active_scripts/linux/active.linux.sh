#!/bin/bash

# Set base paths
WORKSPACE_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd -P)

# python
source "${WORKSPACE_ROOT}/python/active.sh"

# conan settings
export CONAN_HOME="$WORKSPACE_ROOT/conan/.conan"
export CONAN_USE_ALWAYS_SHORT_PATHS=1
source "${WORKSPACE_ROOT}/conan/conanbuild.sh"

# android settings
source "${WORKSPACE_ROOT}/android/active.sh"

# rust settings
source "${WORKSPACE_ROOT}/rust/active.sh"

# SDK settings
source "${WORKSPACE_ROOT}/sdk/active.sh"

# JDK settings
source "${WORKSPACE_ROOT}/jdk/active.sh"

# Tools settings
source "${WORKSPACE_ROOT}/tools/active.sh"

# summary
python ${WORKSPACE_ROOT}/summary.py