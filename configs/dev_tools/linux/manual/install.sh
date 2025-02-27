#!/bin/bash
DEV_ENV_MANUAL_USER_HOME=$DEV_ENV_BIN_PATH/dev_tools/linux/.manual
DEV_ENV_MANUAL_ENV_SETTING_DIR=$DEV_ENV_MANUAL_USER_HOME/.env_set

# Install Python3
DEV_ENV_PYTHON_INSTALL_FILE_NAME=Python-3.10.2.tgz
DEV_ENV_PYTHON_VERSION=3.10.2
DEV_ENV_PYTHON_INSTALL_PATH=$DEV_ENV_MANUAL_USER_HOME/python-3.10.2

if [[ ! -f "$DEV_ENV_TMP_PATH/$DEV_ENV_PYTHON_INSTALL_FILE_NAME" ]] 
then
    echo "Downloading python to $DEV_ENV_TMP_PATH/$DEV_ENV_PYTHON_INSTALL_FILE_NAME"
    curl https://www.python.org/ftp/python/$DEV_ENV_PYTHON_VERSION/$DEV_ENV_PYTHON_INSTALL_FILE_NAME --create-dirs -o $DEV_ENV_TMP_PATH/$DEV_ENV_PYTHON_INSTALL_FILE_NAME 
fi

if [[ ! -d "$DEV_ENV_PYTHON_INSTALL_PATH" ]] 
then
    # install prerequired packages.
    sudo apt install build-essential zlib1g-dev \
    libncurses5-dev libgdbm-dev libnss3-dev \
    libssl-dev libreadline-dev libffi-dev curl

    echo "Extra python to $DEV_ENV_TMP_PATH"
    tar -xzvf $DEV_ENV_TMP_PATH/$DEV_ENV_PYTHON_INSTALL_FILE_NAME -C $TMP_PATH

    # complie python.
    echo "Installing python to $DEV_ENV_PYTHON_INSTALL_PATH"
    cd $DEV_ENV_TMP_PATH/Python-$DEV_ENV_PYTHON_VERSION
    ./configure --enable-optimizations --prefix=$DEV_ENV_PYTHON_INSTALL_PATH
    make install CFLAGS=-fPIC
    cd $DEV_ENV_ROOT_PATH

    # create soft link for python3
    ln -s $DEV_ENV_PYTHON_INSTALL_PATH/bin/python3 $DEV_ENV_PYTHON_INSTALL_PATH/bin/python3.10
fi

# Add path for installed python
export PATH=$DEV_ENV_PYTHON_INSTALL_PATH/bin:$PATH
DEV_EVN_PATH=$DEV_ENV_PYTHON_INSTALL_PATH/bin:$DEV_EVN_PATH

# update pip
python -m ensurepip --upgrade
# install virtualenv
python3 -m pip install --upgrade virtualenv

# setup virtualenv
DEV_ENV_PYTHON_HOME=$DEV_ENV_WORKSPACE_PATH/python-$DEV_ENV_PYTHON_VERSION
mkdir -p $DEV_ENV_PYTHON_HOME
virtualenv -p $DEV_ENV_PYTHON_INSTALL_PATH/bin/python3 $DEV_ENV_PYTHON_HOME

# Copy Python include/lib manully.
mkdir -p $DEV_ENV_PYTHON_HOME/include
mkdir -p $DEV_ENV_PYTHON_HOME/libs
cp -r $DEV_ENV_PYTHON_INSTALL_PATH/include/* $DEV_ENV_PYTHON_HOME/include
cp -r $DEV_ENV_PYTHON_INSTALL_PATH/lib/*.a $DEV_ENV_PYTHON_HOME/libs

export PATH=$DEV_ENV_PYTHON_HOME/bin:$PATH
DEV_EVN_PATH=$DEV_ENV_PYTHON_HOME/bin:$DEV_EVN_PATH

# install conan
python3 -m pip install --upgrade conan

# Write to the env file to be used from bootstrap.sh
mkdir -p $DEV_ENV_MANUAL_ENV_SETTING_DIR
echo "PATH=\"$DEV_EVN_PATH\""'${PATH:+:$PATH}' > "$DEV_ENV_MANUAL_ENV_SETTING_DIR/environment.sh.env"