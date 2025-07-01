#!/bin/bash
# Source the conanbuild script (assuming there's a Linux version)
source "./active_macos.sh"

# Launch VS Code with the custom user data directory
code --user-data-dir="${DEV_ENV_ROOT_PATH}/vscode/.config"