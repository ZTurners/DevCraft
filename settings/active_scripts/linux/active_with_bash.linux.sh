#!/bin/bash

# Set the workspace root path
WORKSPACE_ROOT_PATH=$(dirname "$(readlink -f "$0")")

# Call the activation script
source "${WORKSPACE_ROOT_PATH}/active.linux.sh"

# Check the exit status
if [ $? -ne 0 ]; then
    echo "Error occurred in active.linux.sh"
    exit $?
fi

# Set custom prompt and start interactive shell
export PS1="(arieo_dev) $PS1"
exec bash