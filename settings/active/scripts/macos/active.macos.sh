#!/bin/bash

# Determine the directory where this script resides and use it as the base
WORKSPACE_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd -P)

# Iterate immediate subdirectories and source any active.sh found
for sub in "${WORKSPACE_ROOT}"/*/; do
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
if [ -f "${WORKSPACE_ROOT}/summary.py" ]; then
	python "${WORKSPACE_ROOT}/summary.py"
fi

# source "${WORKSPACE_ROOT}/conan/conanbuild.sh"
