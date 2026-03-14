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
PYENV_ROOT_DIR="$DEV_ENV_WORKSPACE_PATH/python"
ADD_TO_SYSTEM_PATH=0

# Check if pyenv is installed
echo "Verifying Python installation..."
"$PYENV_ROOT_DIR/versions/$PYTHON_VERSION/bin/python" --version || {
    if ! command -v pyenv &> /dev/null; then
        echo "Error: pyenv is not installed. Please install pyenv first."
        echo "You can install it using: brew install pyenv"
        exit 1
    fi

    # Create directories
    echo "Creating directories..."
    mkdir -p "$PYTHON_DOWNLOAD_DIR"
    mkdir -p "$PYENV_ROOT_DIR"

    # Install the specified Python version using pyenv
    echo "Installing Python $PYTHON_VERSION using pyenv..."

    # Set PYENV_ROOT to python install dir
    export PYENV_ROOT="$PYENV_ROOT_DIR"
    pyenv install "$PYTHON_VERSION" --skip-existing

    # Check if installation was successful
    if [ $? -ne 0 ]; then
        echo "Error: Failed to install Python $PYTHON_VERSION"
        exit 1
    fi

    # Get the path to the installed Python version
    PYENV_PYTHON_PATH=$(pyenv prefix "$PYTHON_VERSION")

    echo "Done! Python $PYTHON_VERSION binaries have been copied to $PYENV_ROOT_DIR"
}

# Verify installation
echo "Verifying Python installation..."
$PYENV_ROOT_DIR/versions/$PYTHON_VERSION/bin/python --version || {
    echo "Python installation verification failed"
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

# Verify build backend is available
echo "Verifying build backend..."
echo "Installing complete setuptools package..."

python -m pip install setuptools    
if [ $? -ne 0 ]; then
    echo "setuptools install failed"
    exit 1
fi

# Install PyYAML for configuration file support
echo "Installing PyYAML..."
python -m pip install pyyaml
if [ $? -ne 0 ]; then
    echo "PyYAML install failed"
    exit 1
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