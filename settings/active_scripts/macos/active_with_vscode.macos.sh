#!/bin/bash

# Set the workspace root path
WORKSPACE_ROOT_PATH=$(dirname "$0")

# Call the activation script
source "${WORKSPACE_ROOT_PATH}/active.macos.sh"

# Check the exit status
if [ $? -ne 0 ]; then
    echo "Error occurred in active.macos.sh"
    exit $?
fi

# Launch VS Code with the custom user data directory
code --user-data-dir="${WORKSPACE_ROOT_PATH}/vscode/.config"