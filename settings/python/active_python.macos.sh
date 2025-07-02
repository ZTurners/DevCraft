#!/bin/bash

# Python Installer Bash Script
# Usage: Run this script with sudo or as root (admin rights required)

PYTHON_WORKSPACE_PATH=$(dirname "$0")

# Check if jq is available (optional, for more complex JSON parsing)
PYTHON_SETTING_FILE="${PYTHON_WORKSPACE_PATH}/version.txt"

# Read the file into a variable (strip whitespace)
PYTHON_VERSION=$(cat "$PYTHON_SETTING_FILE" | xargs)

PYTHON_INSTALL_PATH="${PYTHON_WORKSPACE_PATH}/python_${PYTHON_VERSION}"
PYTHON_SCRIPTS_PATH="${PYTHON_INSTALL_PATH}/Scripts"

# Add to Environment to PATH
echo "Adding Python to PATH..."
export PATH="${PYTHON_INSTALL_PATH}:${PYTHON_SCRIPTS_PATH}:${PATH}"
echo "$PATH"