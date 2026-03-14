#!/bin/bash
DEV_ENV_ROOT_PATH=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
source "$DEV_ENV_ROOT_PATH/bootstrap.macos.sh"
python $DEV_ENV_ROOT_PATH/configs/install.py
