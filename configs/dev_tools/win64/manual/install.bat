@echo off
set DEV_ENV_MANUAL_USER_HOME=%DEV_ENV_BIN_PATH%\dev_tools\win64\.manual
set DEV_ENV_MANUAL_ENV_OUTPUT_DIR=%DEV_ENV_MANUAL_USER_HOME%\.env_set

:: Install nuget
mkdir %DEV_ENV_MANUAL_USER_HOME%

:: Install Nuget
mkdir %DEV_ENV_MANUAL_USER_HOME%\nuget
if not exist %DEV_ENV_MANUAL_USER_HOME%\nuget\nuget.exe (
    powershell $ProgressPreference = 'SilentlyContinue'; wget -O %DEV_ENV_MANUAL_USER_HOME%\nuget\nuget.exe https://roundtables.kplanb.com:10030/artifactory/kplanb_general/bootstrap/nuget.exe
)
:: set PATH to use exe in bootstrap folder
set PATH=%DEV_ENV_MANUAL_USER_HOME%\nuget;%PATH%
set DEV_EVN_PATH=%DEV_ENV_MANUAL_USER_HOME%\nuget;%DEV_EVN_PATH%

:: Install Python  (Put Python3 into .nuget pretending install from nuget)
:: https://juejin.cn/post/7001041440159563807
:: https://silentinstallhq.com/python-3-9-silent-install-how-to-guide/
:: https://segmentfault.com/q/1010000016236939
set DEV_ENV_PYTHON_INSTALL_FILE_NAME=python-3.10.3-windows-amd64.zip
set DEV_ENV_PYTHON_VERSION=3.10.3
set DEV_ENV_PYTHON_INSTALL_PATH=%DEV_ENV_MANUAL_USER_HOME%\python-%DEV_ENV_PYTHON_VERSION%

if not exist %DEV_ENV_PYTHON_INSTALL_PATH% (
    powershell $ProgressPreference = 'SilentlyContinue'; wget -O %DEV_ENV_TMP_PATH%\%DEV_ENV_PYTHON_INSTALL_FILE_NAME% https://roundtables.kplanb.com:10030/artifactory/kplanb_general/python/%DEV_ENV_PYTHON_INSTALL_FILE_NAME%
    powershell Expand-Archive -LiteralPath %DEV_ENV_TMP_PATH%\%DEV_ENV_PYTHON_INSTALL_FILE_NAME% -DestinationPath %DEV_ENV_PYTHON_INSTALL_PATH% -Force
)

set PATH=%DEV_ENV_PYTHON_INSTALL_PATH%\Scripts;%PATH%
set PATH=%DEV_ENV_PYTHON_INSTALL_PATH%;%PATH%

set DEV_EVN_PATH=%DEV_ENV_PYTHON_INSTALL_PATH%;%DEV_EVN_PATH%
set DEV_EVN_PATH=%DEV_ENV_PYTHON_INSTALL_PATH%\Scripts;%DEV_EVN_PATH%

:: Install PIP & Conan
::if not exist %DEV_ENV_PYTHON_INSTALL_PATH%\get-pip.py (
::    powershell $ProgressPreference = 'SilentlyContinue'; wget -O %DEV_ENV_PYTHON_INSTALL_PATH%\get-pip.py https://bootstrap.pypa.io/get-pip.py
::    ::python %DEV_ENV_PYTHON_INSTALL_PATH%\get-pip.py
::    echo Lib\site-packages>> %DEV_ENV_PYTHON_INSTALL_PATH%\python310._pth
::)
python -m ensurepip --upgrade
python -m pip install virtualenv
virtualenv --version

:: Setup env for python
set DEV_ENV_PYTHON_HOME=%DEV_ENV_WORKSPACE_PATH%\python-%DEV_ENV_PYTHON_VERSION%
mkdir %DEV_ENV_PYTHON_HOME%
virtualenv -p %DEV_ENV_PYTHON_INSTALL_PATH%\python.exe %DEV_ENV_PYTHON_HOME%
:: Copy python include/libs into workspace
mkdir %DEV_ENV_PYTHON_HOME%\include
mkdir %DEV_ENV_PYTHON_HOME%\libs
xcopy /s %DEV_ENV_PYTHON_INSTALL_PATH%\include\*.* %DEV_ENV_PYTHON_HOME%\include /Y
xcopy /s %DEV_ENV_PYTHON_INSTALL_PATH%\libs\*.lib %DEV_ENV_PYTHON_HOME%\libs /Y

set PATH=%DEV_ENV_PYTHON_HOME%\Scripts;%PATH%
set PATH=%DEV_ENV_PYTHON_HOME%;%PATH%

set DEV_EVN_PATH=%DEV_ENV_PYTHON_HOME%;%DEV_EVN_PATH%
set DEV_EVN_PATH=%DEV_ENV_PYTHON_HOME%\Scripts;%DEV_EVN_PATH%

:: install conan
pip install conan

:: Install MSVC
set DEV_ENV_MSVC_PATH=%DEV_ENV_MANUAL_USER_HOME%\Microsoft.VC.14.29.30133
if not exist %DEV_ENV_MSVC_PATH% (
     powershell $ProgressPreference = 'SilentlyContinue'; wget -O %DEV_ENV_TMP_PATH%\msvc.zip https://roundtables.kplanb.com:10030/artifactory/kplanb_general/msvc/msvc_14.29.30133.zip
     powershell Expand-Archive -LiteralPath %DEV_ENV_TMP_PATH%\msvc.zip -DestinationPath %DEV_ENV_MSVC_PATH% -Force
 )

:: For clang to found libs of MSVC
set LIB=%DEV_ENV_MSVC_PATH%\lib\x64

:: For clang to found includes of MSVC
set INCLUDE=%DEV_ENV_MSVC_PATH%\include

:: Set vc redist dll pathes
set DEV_EVN_PATH=%DEV_ENV_MSVC_PATH%\redist\x64\Microsoft.VC142.OpenMP;%DEV_EVN_PATH%
set DEV_EVN_PATH=%DEV_ENV_MSVC_PATH%\redist\x64\Microsoft.VC142.CRT;%DEV_EVN_PATH%
set DEV_EVN_PATH=%DEV_ENV_MSVC_PATH%\redist\x64\Microsoft.VC142.CXXAMP;%DEV_EVN_PATH%

:: Write DEV_EVN_PATH to the env file to be used from active.bat
mkdir %DEV_ENV_MANUAL_ENV_OUTPUT_DIR%
echo PATH=%DEV_EVN_PATH%;%%PATH%% > %DEV_ENV_MANUAL_ENV_OUTPUT_DIR%/environment.bat.env
echo LIB=%LIB%;%%LIB%% >> %DEV_ENV_MANUAL_ENV_OUTPUT_DIR%/environment.bat.env
echo INCLUDE=%INCLUDE%;%%INCLUDE%% >> %DEV_ENV_MANUAL_ENV_OUTPUT_DIR%/environment.bat.env