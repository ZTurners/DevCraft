#!/bin/bash

# Set the workspace root path
WORKSPACE_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd -P)

# Call the activation script
source "${WORKSPACE_ROOT}/active.macos.sh"

# Check the exit status
if [ $? -ne 0 ]; then
    echo "Error occurred in active.macos.sh"
    exit $?
fi

# Launch VS Code with the custom user data directory
code --user-data-dir="${WORKSPACE_ROOT}/vscode/.config"