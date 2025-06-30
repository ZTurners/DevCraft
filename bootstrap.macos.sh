#!/bin/bash

DEV_ENV_ROOT_PATH=$(dirname "$(realpath "$0")")
DEV_ENV_WORKSPACE_PATH="$DEV_ENV_ROOT_PATH/workspace"

# Configuration
PYTHON_VERSION=3.13.5
PYTHON_URL="https://www.python.org/ftp/python/$PYTHON_VERSION/python-$PYTHON_VERSION-macos11.pkg"
PYTHON_DOWNLOAD_DIR="$DEV_ENV_WORKSPACE_PATH/.download"
PYTHON_INSTALL_DIR="$DEV_ENV_WORKSPACE_PATH/python/python_$PYTHON_VERSION"
TMP_MOUNT_DIR="/tmp/python_installer"
ADD_TO_SYSTEM_PATH=0

# Check if pyenv is installed
if ! command -v pyenv &> /dev/null; then
    echo "Error: pyenv is not installed. Please install pyenv first."
    echo "You can install it using: brew install pyenv"
    exit 1
fi

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
cp -r "$PYENV_PYTHON_PATH/bin" "$PYTHON_INSTALL_DIR"

echo "Done! Python $PYTHON_VERSION binaries have been copied to $TARGET_DIR"
exit 1

# Create directories
echo "Creating directories..."
mkdir -p "$PYTHON_DOWNLOAD_DIR"
mkdir -p "$PYTHON_INSTALL_DIR"
mkdir -p "$TMP_MOUNT_DIR"

# Download Python package
echo "Downloading Python $PYTHON_VERSION..."
if [ ! -f "$PYTHON_DOWNLOAD_DIR/python-$PYTHON_VERSION.pkg" ]; then
    curl -L -o "$PYTHON_DOWNLOAD_DIR/python-$PYTHON_VERSION.pkg" "$PYTHON_URL" || {
        echo "Failed to download Python package"
        exit 1
    }
else
    echo "Package already downloaded"
fi

# Mount the package
echo "Mounting installer package..."
sudo hdiutil attach "$PYTHON_DOWNLOAD_DIR/python-$PYTHON_VERSION.pkg" -mountpoint "$TMP_MOUNT_DIR" -nobrowse || {
    echo "Failed to mount package"
    exit 1
}

# Extract Python framework
echo "Extracting Python framework..."
pkgutil --expand-full "$TMP_MOUNT_DIR/Python_Framework.pkg" "$PYTHON_DOWNLOAD_DIR/python-extracted" || {
    echo "Failed to extract package"
    sudo hdiutil detach "$TMP_MOUNT_DIR"
    exit 1
}

# Copy Python framework to our installation directory
echo "Installing Python to $PYTHON_INSTALL_DIR..."
if [ -d "$PYTHON_DOWNLOAD_DIR/python-extracted/Payload/Library/Frameworks/Python.framework" ]; then
    cp -R "$PYTHON_DOWNLOAD_DIR/python-extracted/Payload/Library/Frameworks/Python.framework" "$PYTHON_INSTALL_DIR/" || {
        echo "Failed to copy Python framework"
        sudo hdiutil detach "$TMP_MOUNT_DIR"
        exit 1
    }
else
    echo "Error: Python framework not found in package"
    sudo hdiutil detach "$TMP_MOUNT_DIR"
    exit 1
fi

# Unmount the package
sudo hdiutil detach "$TMP_MOUNT_DIR"

# Create symlinks for easier access
echo "Creating symlinks..."
ln -sf "$PYTHON_INSTALL_DIR/Python.framework/Versions/Current/bin/python3" "$PYTHON_INSTALL_DIR/python"
ln -sf "$PYTHON_INSTALL_DIR/Python.framework/Versions/Current/bin/pip3" "$PYTHON_INSTALL_DIR/pip"

# Set up environment variables
echo "Creating activation script..."
cat > "$PYTHON_INSTALL_DIR/activate" << 'EOF'
#!/bin/bash
export PYTHONHOME="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="$PYTHONHOME/Python.framework/Versions/Current/bin:$PATH"
EOF

chmod +x "$PYTHON_INSTALL_DIR/activate"

# Temporarily add to PATH for the rest of the script
export PATH="$PYTHON_INSTALL_DIR/Python.framework/Versions/Current/bin:$PATH"

# Verify installation
echo "Verifying Python installation..."
"$PYTHON_INSTALL_DIR/python" --version || {
    echo "Python installation verification failed"
    exit 1
}

# Install pip if not present (should already be included in macOS package)
echo "Verifying pip..."
"$PYTHON_INSTALL_DIR/python" -m ensurepip --upgrade || {
    echo "Failed to ensure pip is available"
    exit 1
}

# Verify pip installation
"$PYTHON_INSTALL_DIR/python" -m pip --version || {
    echo "Pip verification failed"
    exit 1
}

# Verify build backend is available
echo "Verifying build backend..."
"$PYTHON_INSTALL_DIR/python" -c "import setuptools.build_meta" || {
    echo "WARNING: Build backend not available"
    echo "Installing complete setuptools package..."
    "$PYTHON_INSTALL_DIR/python" -m pip install --force-reinstall setuptools
    
    if [ $? -ne 0 ]; then
        echo "setuptools install failed"
        exit 1
    fi
}

# Install Conan
echo "Installing Conan..."
"$PYTHON_INSTALL_DIR/python" -m pip install conan || {
    echo "Failed to install Conan"
    exit 1
}

# Verify Conan
echo "Verifying conan..."
"$PYTHON_INSTALL_DIR/Python.framework/Versions/Current/bin/conan" --version || {
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
echo "Executable:  $PYTHON_INSTALL_DIR/python"
"$PYTHON_INSTALL_DIR/python" -c "import sys; print(sys.executable)"
echo
echo "[PIP INSTALLATION]"
"$PYTHON_INSTALL_DIR/python" -m pip show pip
echo
echo "[CONAN INSTALLATION]"
"$PYTHON_INSTALL_DIR/python" -m pip show conan
echo
echo "To use this Python environment, run:"
echo "source $PYTHON_INSTALL_DIR/activate"
echo