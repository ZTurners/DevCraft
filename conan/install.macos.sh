#!/bin/bash

# Set root path and Conan home
DEV_ENV_CONAN_ROOT_PATH=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
export CONAN_HOME="$DEV_ENV_CONAN_ROOT_PATH/.conan"
export CONAN_USE_ALWAYS_SHORT_PATHS=1

# Create Conan home directory and copy configuration files
mkdir -p "$CONAN_HOME"
cp "$DEV_ENV_CONAN_ROOT_PATH/global.conf" "$CONAN_HOME/"
cp "$DEV_ENV_CONAN_ROOT_PATH/settings.yml" "$CONAN_HOME/"
cp "$DEV_ENV_CONAN_ROOT_PATH/remotes.json" "$CONAN_HOME/"

# Configure Conan
conan profile detect --force

# Run Conan installations
conan install $DEV_ENV_CONAN_ROOT_PATH/conanfile.txt --update --generator CMakeToolchain --generator VirtualBuildEnv --output-folder $DEV_ENV_CONAN_ROOT_PATH/_generated/builder/macos --build never --profile=$DEV_ENV_CONAN_ROOT_PATH/profiles/builder/conan_builder_profile.macos.txt