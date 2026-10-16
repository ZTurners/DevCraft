#!/bin/bash

# Set the workspace root path
# BASH_SOURCE is bash-only; zsh sets $0 to the sourced file instead
DEV_ACTIVE_SCRIPT="${BASH_SOURCE[0]}"
[ -n "${DEV_ACTIVE_SCRIPT}" ] || DEV_ACTIVE_SCRIPT="$0"
DEVCRAFT_WORKSPACE=$(cd "$(dirname "${DEV_ACTIVE_SCRIPT}")" &>/dev/null && pwd -P)

# Call the activation script
source "${DEVCRAFT_WORKSPACE}/active.macos.sh"

# Check the exit status; return (not exit) so sourcing shells survive
if ! source "${DEVCRAFT_WORKSPACE}/active.macos.sh"; then
    echo "Error occurred in active.macos.sh"
    return 1 2>/dev/null || exit 1
fi

# Set custom prompt and start interactive shell
export PS1="(arieo_dev) $PS1"
exec bash