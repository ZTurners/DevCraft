#!/bin/bash

# Set the workspace root path
DEVCRAFT_WORKSPACE=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd -P)

# Call the activation script
source "${DEVCRAFT_WORKSPACE}/active.macos.sh"

# Check the exit status
if [ $? -ne 0 ]; then
    echo "Error occurred in active.macos.sh"
    exit $?
fi

# Locate the ZCode desktop app binary; launching it directly makes it inherit this environment
ZCODE_APP_BIN=""
for candidate in \
    "/Applications/ZCode.app/Contents/MacOS/ZCode" \
    "${HOME}/Applications/ZCode.app/Contents/MacOS/ZCode"; do
    if [ -x "${candidate}" ]; then
        ZCODE_APP_BIN="${candidate}"
        break
    fi
done

if [ -z "${ZCODE_APP_BIN}" ]; then
    echo "ZCode desktop app is not installed."
    exit 1
fi

# Start ZCode as a background process so it inherits this environment and outlives this script
"${ZCODE_APP_BIN}" >/dev/null 2>&1 &
disown
