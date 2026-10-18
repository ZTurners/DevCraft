#!/bin/bash

# Set the workspace root path
# BASH_SOURCE is bash-only; zsh sets $0 to the sourced file instead
DEV_ACTIVE_SCRIPT="${BASH_SOURCE[0]}"
[ -n "${DEV_ACTIVE_SCRIPT}" ] || DEV_ACTIVE_SCRIPT="$0"
export DEVCRAFT_WORKSPACE=$(cd "$(dirname "${DEV_ACTIVE_SCRIPT}")" &>/dev/null && pwd -P)

# Call the activation script, checking the exit status; return (not
# exit) so sourcing shells survive
if ! source "${DEVCRAFT_WORKSPACE}/active.macos.sh"; then
    echo "Error occurred in active.macos.sh"
    return 1 2>/dev/null || exit 1
fi

# Locate the DeepSeek Harness desktop app binary; launching it directly makes it inherit this environment
DSH_APP_BIN=""
for candidate in \
    "/Applications/DeepSeek Harness.app/Contents/MacOS/DeepSeek Harness" \
    "${HOME}/Applications/DeepSeek Harness.app/Contents/MacOS/DeepSeek Harness"; do
    if [ -x "${candidate}" ]; then
        DSH_APP_BIN="${candidate}"
        break
    fi
done

if [ -z "${DSH_APP_BIN}" ]; then
    echo "DeepSeek Harness desktop app is not installed."
    return 1 2>/dev/null || exit 1
fi

# Start DeepSeek Harness as a background process so it inherits this environment and outlives this script
"${DSH_APP_BIN}" "$@" >/dev/null 2>&1 &
disown
