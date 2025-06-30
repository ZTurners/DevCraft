#!/bin/bash

DEV_ENV_ROOT_PATH=$(dirname "$(realpath "$0")")
DEV_ENV_WORKSPACE_PATH="$DEV_ENV_ROOT_PATH/workspace"

PYTHON_SETTING_FILE="$DEV_ENV_ROOT_PATH/settings/python/version.txt"
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
PYTHON_DOWNLOAD_DIR="$DEV_ENV_WORKSPACE_PATH/.download"
PYTHON_INSTALL_DIR="$DEV_ENV_WORKSPACE_PATH/python/python_$PYTHON_VERSION"
ADD_TO_SYSTEM_PATH=0

# Check if pyenv is installed
if ! command -v pyenv &> /dev/null; then
    echo "Error: pyenv is not installed. Please install pyenv first."
    echo "You can install it using: brew install pyenv"
    exit 1
fi

# Create directories
echo "Creating directories..."
mkdir -p "$PYTHON_DOWNLOAD_DIR"
mkdir -p "$PYTHON_INSTALL_DIR"

# Install the specified Python version using pyenv
echo "Installing Python $PYTHON_VERSION using pyenv..."
pyenv install "$PYTHON_VERSION" --skip-existing

# Check if installation was successful
if [ $? -ne 0 ]; then
    echo "Error: Failed to install Python $PYTHON_VERSION"
    exit 1
fi

# Get the path to the installed Python version
PYENV_PYTHON_PATH=$(pyenv prefix "$PYTHON_VERSION")

# Check if the path exists
if [ ! -d "$PYENV_PYTHON_PATH" ]; then
    echo "Error: Could not find installed Python version at $PYENV_PYTHON_PATH"
    exit 1
fi

# Copy the bin directory to the target location
echo "Copying binaries from $PYENV_PYTHON_PATH/bin to $PYTHON_INSTALL_DIR..."
rsync -a "$PYENV_PYTHON_PATH/" "$PYTHON_INSTALL_DIR/"

echo "Done! Python $PYTHON_VERSION binaries have been copied to $PYTHON_INSTALL_DIR"

# Temporarily add to PATH for the rest of the script
export PATH="$PYTHON_INSTALL_DIR/bin:$PATH"

# Verify installation
echo "Verifying Python installation..."
"$PYTHON_INSTALL_DIR/bin/python" --version || {
    echo "Python installation verification failed"
    exit 1
}

# Install pip if not present (should already be included in macOS package)
echo "Verifying pip..."
"$PYTHON_INSTALL_DIR/bin/python" -m ensurepip --upgrade || {
    echo "Failed to ensure pip is available"
    exit 1
}

# Verify pip installation
"$PYTHON_INSTALL_DIR/bin/python" -m pip --version || {
    echo "Pip verification failed"
    exit 1
}

# Verify build backend is available
echo "Verifying build backend..."
echo "Installing complete setuptools package..."

"$PYTHON_INSTALL_DIR/bin/python" -m pip install --force-reinstall setuptools    
if [ $? -ne 0 ]; then
    echo "setuptools install failed"
    exit 1
fi

# Install Conan
echo "Installing Conan..."
"$PYTHON_INSTALL_DIR/bin/python" -m pip install conan || {
    echo "Failed to install Conan"
    exit 1
}


# Verify Conan
echo "Verifying conan..."
"$PYTHON_INSTALL_DIR/bin/conan" --version || {
    echo "Conan verification failed"
    exit 1
}

# Installation summary
echo
echo "========================================"
echo "         INSTALLATION SUMMARY"
echo "========================================"
echo
echo "[PYTHON INSTALLATION]"
echo "Version:     $PYTHON_VERSION"
echo "Location:    $PYTHON_INSTALL_DIR"
echo "Executable:  $PYTHON_INSTALL_DIR/bin/python"
"$PYTHON_INSTALL_DIR/bin/python" -c "import sys; print(sys.executable)"
echo
echo "[PIP INSTALLATION]"
"$PYTHON_INSTALL_DIR/bin/python" -m pip show pip
echo
echo "[CONAN INSTALLATION]"
"$PYTHON_INSTALL_DIR/bin/python" -m pip show conan
echo