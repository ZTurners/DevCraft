#!/bin/bash
# Source the conanbuild script (assuming there's a Linux version)
source "./active_macos.sh"

# Modify the prompt to show (arieo_dev) and current path
export PS1='(arieo_dev) \[\033[01;34m\]\w\[\033[00m\] \$ '

# Start a new interactive shell with the modified environment
exec bash