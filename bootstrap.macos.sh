#!/bin/bash

DEV_ENV_ROOT_PATH=$(dirname "$(realpath "$0")")
DEV_ENV_WORKSPACE_PATH="$DEV_ENV_ROOT_PATH/workspace"

# Bootstrap interpreter version, pinned here (the user-facing ${workspace}/python
# tree is versioned separately by configs/python). Distributed as a
# python-build-standalone "install_only" archive: a prebuilt, relocatable
# CPython with lzma/ssl/pip included, so no pyenv/brew/compile is involved.
# PBS_TAG must be a release tag whose assets still carry BOOTSTRAP_PYTHON_VERSION.
BOOTSTRAP_PYTHON_VERSION=3.13.5
PBS_TAG=20250702

# Configuration
PYTHON_DOWNLOAD_DIR="$DEV_ENV_ROOT_PATH/.downloads"
# Bootstrap interpreter lives apart from the user-facing ${workspace}/python
# tree (duplicated by the python config) so an sdk_root wipe there can never
# touch the interpreter install.py itself runs on
PYTHON_ROOT_DIR="$DEV_ENV_WORKSPACE_PATH/bootstrap/python"
ADD_TO_SYSTEM_PATH=0
PYTHON_BIN="$PYTHON_ROOT_DIR/versions/$BOOTSTRAP_PYTHON_VERSION/bin/python"

# Apple Silicon only; the tarball triple is pinned below
PBS_ARCH=aarch64

PYTHON_TARBALL="$PYTHON_DOWNLOAD_DIR/cpython-$BOOTSTRAP_PYTHON_VERSION+$PBS_TAG-$PBS_ARCH-apple-darwin-install_only.tar.gz"
PYTHON_URL="https://github.com/astral-sh/python-build-standalone/releases/download/$PBS_TAG/cpython-$BOOTSTRAP_PYTHON_VERSION+$PBS_TAG-$PBS_ARCH-apple-darwin-install_only.tar.gz"
# Pinned SHA-256 of the tarball above
PYTHON_SHA256=66577414e9f4b0caa116a8e15fa50306db91bce13d49278079bb22adaeefb1fa

# Check whether Python exists and includes the optional modules required by
# the installer. In particular, tar.xz extraction requires the _lzma module.
echo "Verifying Python installation..."
PYTHON_NEEDS_INSTALL=0
if ! "$PYTHON_BIN" --version; then
    PYTHON_NEEDS_INSTALL=1
elif ! "$PYTHON_BIN" -c "import lzma" >/dev/null 2>&1; then
    echo "Python $BOOTSTRAP_PYTHON_VERSION is missing lzma support and will be reinstalled."
    PYTHON_NEEDS_INSTALL=1
fi

if [ "$PYTHON_NEEDS_INSTALL" -eq 1 ]; then
    # Create directories
    echo "Creating directories..."
    mkdir -p "$PYTHON_DOWNLOAD_DIR"
    mkdir -p "$PYTHON_ROOT_DIR/versions/$BOOTSTRAP_PYTHON_VERSION"

    # Download the prebuilt archive unless it is already staged
    if [ -f "$PYTHON_TARBALL" ]; then
        echo "Tarball already exists at $PYTHON_TARBALL"
    else
        echo "Downloading Python $BOOTSTRAP_PYTHON_VERSION ($PBS_ARCH)..."
        curl -fL --progress-bar -o "$PYTHON_TARBALL.tmp" "$PYTHON_URL" || {
            echo "Error: Failed to download $PYTHON_URL"
            rm -f "$PYTHON_TARBALL.tmp"
            exit 1
        }
        mv "$PYTHON_TARBALL.tmp" "$PYTHON_TARBALL"
    fi

    # Verify checksum before extracting
    echo "$PYTHON_SHA256  $PYTHON_TARBALL" | shasum -a 256 -c - || {
        echo "Error: SHA-256 mismatch for $PYTHON_TARBALL"
        exit 1
    }

    # The archive has a single 'python/' prefix; strip it into the version dir
    echo "Extracting Python $BOOTSTRAP_PYTHON_VERSION ..."
    tar -xzf "$PYTHON_TARBALL" -C "$PYTHON_ROOT_DIR/versions/$BOOTSTRAP_PYTHON_VERSION" --strip-components=1 || {
        echo "Error: Failed to extract $PYTHON_TARBALL"
        exit 1
    }

    echo "Done! Python $BOOTSTRAP_PYTHON_VERSION installed to $PYTHON_ROOT_DIR/versions/$BOOTSTRAP_PYTHON_VERSION"
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
export PATH="$PYTHON_ROOT_DIR/versions/$BOOTSTRAP_PYTHON_VERSION/bin:$PATH"

# pip ships inside the standalone archive; make sure it is importable
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
