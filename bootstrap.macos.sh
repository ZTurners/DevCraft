#!/bin/bash

DEV_ENV_ROOT_PATH=$(dirname "$(realpath "$0")")
DEV_ENV_WORKSPACE_PATH="$DEV_ENV_ROOT_PATH/workspace"

PYTHON_SETTING_FILE="$DEV_ENV_ROOT_PATH/configs/boostrap_python_version.txt"
# Read the file, trim whitespace, and remove quotes
PYTHON_VERSION=$(cat "$PYTHON_SETTING_FILE" | xargs | tr -d '"')
# Check if version was obtained
if [ -z "$PYTHON_VERSION" ]; then
    echo "Cannot fetch python version"
    exit 1
fi
# Set the environment variable (for current session and export to child processes)
export PYTHON_VERSION="$PYTHON_VERSION"
# Verify
echo "Setting PYTHON_VERSION=$PYTHON_VERSION"

# Configuration
# PYTHON_VERSION=3.13.5
PYTHON_URL="https://www.python.org/ftp/python/$PYTHON_VERSION/python-$PYTHON_VERSION-macos11.pkg"
PYTHON_DOWNLOAD_DIR="$DEV_ENV_ROOT_PATH/.downloads"
# Bootstrap interpreter lives apart from the user-facing ${workspace}/python
# tree (duplicated by the python config) so an sdk_root wipe there can never
# touch the interpreter install.py itself runs on
PYENV_ROOT_DIR="$DEV_ENV_WORKSPACE_PATH/bootstrap/python"
ADD_TO_SYSTEM_PATH=0
PYTHON_BIN="$PYENV_ROOT_DIR/versions/$PYTHON_VERSION/bin/python"

# Check whether Python exists and includes the optional modules required by
# the installer. In particular, tar.xz extraction requires the _lzma module.
echo "Verifying Python installation..."
PYTHON_NEEDS_INSTALL=0
if ! "$PYTHON_BIN" --version; then
    PYTHON_NEEDS_INSTALL=1
elif ! "$PYTHON_BIN" -c "import lzma" >/dev/null 2>&1; then
    echo "Python $PYTHON_VERSION is missing lzma support and will be rebuilt."
    PYTHON_NEEDS_INSTALL=1
fi

if [ "$PYTHON_NEEDS_INSTALL" -eq 1 ]; then
    if ! command -v pyenv &> /dev/null; then
        echo "Error: pyenv is not installed. Please install pyenv first."
        echo "You can install it using: brew install pyenv"
        exit 1
    fi

    if ! command -v brew &> /dev/null; then
        echo "Error: Homebrew is required to provide xz when building Python."
        exit 1
    fi

    if ! brew list --versions xz >/dev/null 2>&1; then
        echo "Installing xz for Python lzma support..."
        brew install xz || {
            echo "Error: Failed to install xz"
            exit 1
        }
    fi

    # Create directories
    echo "Creating directories..."
    mkdir -p "$PYTHON_DOWNLOAD_DIR"
    mkdir -p "$PYENV_ROOT_DIR"

    # Install the specified Python version using pyenv
    echo "Installing Python $PYTHON_VERSION using pyenv..."

    # Set PYENV_ROOT to python install dir
    export PYENV_ROOT="$PYENV_ROOT_DIR"
    XZ_PREFIX=$(brew --prefix xz)
    export CPPFLAGS="-I$XZ_PREFIX/include${CPPFLAGS:+ $CPPFLAGS}"
    export LDFLAGS="-L$XZ_PREFIX/lib${LDFLAGS:+ $LDFLAGS}"
    export PKG_CONFIG_PATH="$XZ_PREFIX/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
    pyenv install --force "$PYTHON_VERSION"

    # Check if installation was successful
    if [ $? -ne 0 ]; then
        echo "Error: Failed to install Python $PYTHON_VERSION"
        exit 1
    fi

    # Get the path to the installed Python version
    PYENV_PYTHON_PATH=$(pyenv prefix "$PYTHON_VERSION")

    echo "Done! Python $PYTHON_VERSION binaries have been copied to $PYENV_ROOT_DIR"
fi

# Verify installation
echo "Verifying Python installation..."
"$PYTHON_BIN" --version || {
    echo "Python installation verification failed"
    exit 1
}
"$PYTHON_BIN" -c "import lzma" || {
    echo "Python lzma verification failed"
    exit 1
}

# Temporarily add to PATH for the rest of the script
export PATH="$PYENV_ROOT_DIR/versions/$PYTHON_VERSION/bin:$PATH"

# Install pip if not present (should already be included in macOS package)
echo "Verifying pip..."
python -m ensurepip --upgrade || {
    echo "Failed to ensure pip is available"
    exit 1
}

# Verify pip installation
python -m pip --version || {
    echo "Pip verification failed"
    exit 1
}

# Install PyYAML (YAML configs) + pypdl (multi-threaded downloads in configs/download.py);
# pip show is a local check, so an already-provisioned machine skips the pypi round-trip
if python -m pip show pyyaml >/dev/null 2>&1 && python -m pip show pypdl >/dev/null 2>&1; then
    echo "PyYAML and pypdl already installed, skipping pip install"
else
    echo "Installing PyYAML and pypdl..."
    python -m pip install pyyaml pypdl
    if [ $? -ne 0 ]; then
        echo "PyYAML/pypdl install failed"
        exit 1
    fi
fi

# Installation summary
echo
echo "========================================"
echo "         INSTALLATION SUMMARY"
echo "========================================"
echo
echo "[PYTHON INSTALLATION]"
echo "Version:     " $(python --version)
echo "Location:    " $(whereis python)
echo "Executable:  " $(python -c "import sys; print(sys.executable)")
echo
echo "[PIP INSTALLATION]"
python -m pip show pip
echo
