#!/bin/bash

export DEVCRAFT_HOST_TRIPLE=arm64-apple-darwin

# Determine the directory where this script resides and use it as the base
# BASH_SOURCE is bash-only; zsh sets $0 to the sourced file instead
DEV_ACTIVE_SCRIPT="${BASH_SOURCE[0]}"
[ -n "${DEV_ACTIVE_SCRIPT}" ] || DEV_ACTIVE_SCRIPT="$0"
export DEVCRAFT_WORKSPACE=$(cd "$(dirname "${DEV_ACTIVE_SCRIPT}")" &>/dev/null && pwd -P)

# Iterate immediate subdirectories and source any active.sh found
for sub in "${DEVCRAFT_WORKSPACE}"/*/; do
	# Ensure it's a directory (glob can return literal pattern if no match)
	[ -d "${sub}" ] || continue

	ACTIVE_SH="${sub}active.sh"
	if [ -f "${ACTIVE_SH}" ]; then
		echo "Sourcing ${ACTIVE_SH}"
		# shellcheck disable=SC1090
		source "${ACTIVE_SH}"
	fi
done

# Run summary if present
if [ -f "${DEVCRAFT_WORKSPACE}/summary.py" ]; then
	python "${DEVCRAFT_WORKSPACE}/summary.py"
fi

# source "${DEVCRAFT_WORKSPACE}/conan/conanbuild.sh"
