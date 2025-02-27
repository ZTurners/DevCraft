#!/bin/bash
# Load envrionment setting from conan
DEV_ENV_CONAN_ENV_OUTPUT_DIR=$DEV_ENV_BIN_PATH/dev_tools/linux/.conan/.env_set

while read -r line; do
    LINE="$(eval echo $line)";
    export "$LINE";
done < "$DEV_ENV_CONAN_ENV_OUTPUT_DIR/environment.sh.env"