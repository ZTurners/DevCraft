#!/bin/bash

# Set base paths
DEVCRAFT_WORKSPACE=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd -P)

# python
source "${DEVCRAFT_WORKSPACE}/python/active.sh"

# conan settings
export CONAN_HOME="$DEVCRAFT_WORKSPACE/conan/.conan"
export CONAN_USE_ALWAYS_SHORT_PATHS=1
source "${DEVCRAFT_WORKSPACE}/conan/conanbuild.sh"

# android settings
source "${DEVCRAFT_WORKSPACE}/android/active.sh"

# rust settings
source "${DEVCRAFT_WORKSPACE}/rust/active.sh"

# SDK settings
source "${DEVCRAFT_WORKSPACE}/sdk/active.sh"

# JDK settings
source "${DEVCRAFT_WORKSPACE}/jdk/active.sh"

# Tools settings
source "${DEVCRAFT_WORKSPACE}/tools/active.sh"

# summary
python ${DEVCRAFT_WORKSPACE}/summary.py