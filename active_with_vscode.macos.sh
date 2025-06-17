#!/bin/sh

# Get the directory where the script is located
DEV_ENV_ROOT_PATH=$(dirname "$0")

# Set environment variables
export CONAN_HOME="$DEV_ENV_ROOT_PATH/conan/.conan"
export CONAN_USE_ALWAYS_SHORT_PATHS=1

VS_CODE_INIT_USER_SETTING="$DEV_ENV_ROOT_PATH/vscode/init_user_settings.json"
VS_CODE_USER_SETTING="$DEV_ENV_ROOT_PATH/vscode/.config/User/settings.json"

# Execute the conan build script
. "$DEV_ENV_ROOT_PATH/conan/_generated/builder/macos/conanbuild.sh"

# Check if VS Code user settings exist, if not create them
if [ ! -f "$VS_CODE_USER_SETTING" ]; then
    mkdir -p "$DEV_ENV_ROOT_PATH/vscode/.config/User"
    cp "$VS_CODE_INIT_USER_SETTING" "$VS_CODE_USER_SETTING"
fi

# Launch VS Code with the custom user data directory
code --user-data-dir="$DEV_ENV_ROOT_PATH/vscode/.config"