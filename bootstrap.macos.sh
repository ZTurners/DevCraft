#!/bin/bash

DEV_ENV_ROOT_PATH=$(dirname "$(realpath "$0")")
DEV_ENV_WORKSPACE_PATH="$DEV_ENV_ROOT_PATH/workspace"

# Install Python
# Python Installer Bash Script
# Usage: Run this script with sudo or as root

# Configuration - Change these values if needed
PYTHON_VERSION=3.12.4
PYTHON_URL="https://www.python.org/ftp/python/$PYTHON_VERSION/python-$PYTHON_VERSION-embed-amd64.zip"
PYTHON_DOWNLOAD_DIR="$DEV_ENV_WORKSPACE_PATH/.download"
PYTHON_INSTALL_DIR="$DEV_ENV_WORKSPACE_PATH/python/python_$PYTHON_VERSION"
PYTHON_SCRIPTS_DIR="$PYTHON_INSTALL_DIR/Scripts"
ADD_TO_SYSTEM_PATH=0

# Check for root privileges
#if [ "$(id -u)" -ne 0 ]; then
#    echo "This script requires administrator privileges."
#    echo "Please run with sudo or as root."
#    exit 1
#fi

# Create directories if they don't exist
echo "Creating directories if needed..."
mkdir -p "$PYTHON_DOWNLOAD_DIR"
if [ ! -d "$PYTHON_INSTALL_DIR" ]; then
    echo "Creating installation directory: $PYTHON_INSTALL_DIR"
    mkdir -p "$PYTHON_INSTALL_DIR"
fi

# Download Python ZIP
echo "Downloading Python $PYTHON_VERSION (ZIP version)..."
ZIP_FILE="$PYTHON_DOWNLOAD_DIR/python-$PYTHON_VERSION-embed-amd64.zip"
if [ ! -f "$ZIP_FILE" ]; then
    echo "Downloading from $PYTHON_URL..."
    wget -O "$ZIP_FILE" "$PYTHON_URL"
    if [ $? -ne 0 ]; then
        echo "Failed to download Python ZIP file!"
        exit 1
    fi
else
    echo "ZIP file already exists at $ZIP_FILE"
fi

# Extract Python
echo "Extracting Python to $PYTHON_INSTALL_DIR..."
if [ -f "$ZIP_FILE" ]; then
    unzip -o "$ZIP_FILE" -d "$PYTHON_INSTALL_DIR"
else
    echo "Error: ZIP file not found!"
    exit 1
fi

# Configure Python environment
echo "Configuring Python..."
# Dynamically find the ._pth file
PTH_FILE=$(find "$PYTHON_INSTALL_DIR" -name "python*._pth" | head -n 1)

if [ -z "$PTH_FILE" ]; then
    echo "ERROR: Could not find python*._pth file in $PYTHON_INSTALL_DIR"
    exit 1
fi

echo "Found ._pth file: $PTH_FILE"

# Backup original ._pth file
cp "$PTH_FILE" "$PTH_FILE.bak"

# Modify ._pth file to enable site-packages
cat > "$PTH_FILE" << EOF
python312.zip
.
Lib/site-packages
import site
EOF

# Add to Environment PATH
echo "Adding Python to PATH..."
export PATH="$PYTHON_INSTALL_DIR:$PYTHON_SCRIPTS_DIR:$PATH"
echo "$PATH"

if [ "$ADD_TO_SYSTEM_PATH" -eq 1 ]; then
    echo "Adding Python to system PATH..."
    # Add to system environment
    echo "export PATH=\"$PYTHON_INSTALL_DIR:$PYTHON_SCRIPTS_DIR:\$PATH\"" >> /etc/profile
fi

# Verify installation
echo "Verifying Python installation..."
"$PYTHON_INSTALL_DIR/python" --version
if [ $? -ne 0 ]; then
    echo "Python installation verification failed."
else
    echo "Python $PYTHON_VERSION successfully installed at $PYTHON_INSTALL_DIR"
fi

# Download get-pip.py
echo "Downloading pip installer..."
wget -O "$PYTHON_DOWNLOAD_DIR/get-pip.py" https://bootstrap.pypa.io/get-pip.py
if [ $? -ne 0 ]; then
    echo "Failed to download pip installer"
    exit 1
fi

# Install pip properly for embedded Python
echo "Installing pip..."
"$PYTHON_INSTALL_DIR/python" "$PYTHON_DOWNLOAD_DIR/get-pip.py" --no-warn-script-location --trusted-host pypi.org --trusted-host files.pythonhosted.org
if [ $? -ne 0 ]; then
    echo "Failed to install pip"
    echo "Trying alternative installation method..."
    "$PYTHON_INSTALL_DIR/python" -c "import urllib.request; urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py', '$PYTHON_DOWNLOAD_DIR/get-pip.py')"
    "$PYTHON_INSTALL_DIR/python" "$PYTHON_DOWNLOAD_DIR/get-pip.py" --no-warn-script-location
    if [ $? -ne 0 ]; then
        echo "Pip installation failed completely"
        exit 1
    fi
fi

# Verify pip installation
echo "Verifying pip..."
"$PYTHON_INSTALL_DIR/python" -m pip --version
if [ $? -ne 0 ]; then
    echo "Pip verification failed"
    exit 1
fi

# Verify build backend is available
echo "Verifying build backend..."
"$PYTHON_INSTALL_DIR/python" -c "import setuptools.build_meta" || {
    echo "WARNING: Build backend still not available"
    echo "Installing complete setuptools package..."
    "$PYTHON_INSTALL_DIR/python" -m pip install --force-reinstall setuptools --no-warn-script-location

    if [ $? -ne 0 ]; then
        echo "setuptools install failed"
        exit 1
    fi
}

# Install Conan
echo "Installing Conan..."
"$PYTHON_INSTALL_DIR/python" -m pip install conan
if [ $? -ne 0 ]; then
    echo "Failed to install Conan"
    exit 1
fi

echo "Verifying conan..."
"$PYTHON_SCRIPTS_DIR/conan" --version
if [ $? -ne 0 ]; then
    echo "Conan verification failed"
    exit 1
fi

# Get installation details
echo "Collecting installation details..."

# Display installation summary
echo
echo "========================================"
echo "         INSTALLATION SUMMARY"
echo "========================================"
echo
echo "[PYTHON INSTALLATION]"
echo "Version:     $PYTHON_VERSION"
echo "Location:    $PYTHON_INSTALL_DIR"
echo "Executable:  $PYTHON_EXE"
"$PYTHON_INSTALL_DIR/python" -c "import sys; print(sys.executable)"
echo
echo "[PIP INSTALLATION]"
"$PYTHON_INSTALL_DIR/python" -m pip show pip
echo
echo "[CONAN INSTALLATION]"
"$PYTHON_INSTALL_DIR/python" -m pip show conan
read -p "Press enter to continue"