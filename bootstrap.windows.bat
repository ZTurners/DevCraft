@echo off

set DEV_ENV_ROOT_PATH=%~dp0
set DEV_ENV_WORKSPACE_PATH=%DEV_ENV_ROOT_PATH%/workspace

:: Install Python
SETLOCAL ENABLEDELAYEDEXPANSION
    
    :: Python Installer Batch Script
    :: Usage: Just double-click this .bat file to run it (Admin rights required)
    :: Check if jq is available (optional, for more complex JSON parsing)
    set "PYTHON_SETTING_FILE=%DEV_ENV_ROOT_PATH%/settings/python/version.txt"
    
    :: Read the file into a variable (strip whitespace)
    for /f "delims=" %%i in (%PYTHON_SETTING_FILE%) do (
        set PYTHON_VERSION=%%i
    )
    :: Remove any remaining whitespace
    set PYTHON_VERSION=%PYTHON_VERSION: =%
    :: Remove quotes
    set PYTHON_VERSION=%PYTHON_VERSION:"=%
    :: Set it in the environment (for current session)
    set PYTHON_VERSION=%PYTHON_VERSION%

    :: Check the Python version
    if not defined PYTHON_VERSION (
        echo Cannot fetch python version
        exit /b
    )

    :: Set the environment variable
    echo Setting PYTHON_VERSION=%PYTHON_VERSION%

    :: Configuration - Change these values if needed
    :: PYTHON_VERSION=3.13.5
    set PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/python-%PYTHON_VERSION%-embed-amd64.zip
    set PYTHON_DOWNLOAD_DIR=%DEV_ENV_WORKSPACE_PATH%/.download
    set PYTHON_INSTALL_DIR=%DEV_ENV_WORKSPACE_PATH%/python/python_%PYTHON_VERSION%
    set PYTHON_SCRIPTS_DIR=%PYTHON_INSTALL_DIR%/Scripts
    set ADD_TO_SYSTEM_PATH=0


    :: Check for administrator privileges
    :: NET SESSION >nul 2>&1
    ::if %ERRORLEVEL% neq 0 (
    ::    echo This script requires administrator privileges.
    ::    echo Please right-click the file and select "Run as administrator".
    ::    pause
    ::    exit /b
    ::)

    :: Create directories if they don't exist
    echo Creating directories if needed...
    if not exist "%PYTHON_DOWNLOAD_DIR%" mkdir "%PYTHON_DOWNLOAD_DIR%"
    if not exist "%PYTHON_INSTALL_DIR%" (
        echo Creating installation directory: %PYTHON_INSTALL_DIR%
        mkdir "%PYTHON_INSTALL_DIR%"
    )

    :: Download Python ZIP
    echo Downloading Python %PYTHON_VERSION% (ZIP version)...
    set ZIP_FILE=%PYTHON_DOWNLOAD_DIR%\python-%PYTHON_VERSION%-embed-amd64.zip
    if not exist "%ZIP_FILE%" (
        echo Downloading from %PYTHON_URL%...
        powershell -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%ZIP_FILE%'"
        if %ERRORLEVEL% neq 0 (
            echo Failed to download Python ZIP file!
            pause
            exit /b
        )
    ) else (
        echo ZIP file already exists at %ZIP_FILE%
    )

    :: Extract Python
    echo Extracting Python to %PYTHON_INSTALL_DIR%...
    if exist "%ZIP_FILE%" (
        powershell -Command "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%PYTHON_INSTALL_DIR%' -Force"
    ) else (
        echo Error: ZIP file not found!
        pause
        exit /b
    )
    
    :: Configure Python environment
    echo Configuring Python...
    :: Dynamically find the ._pth file
    set PTH_FILE=
    for %%f in ("%PYTHON_INSTALL_DIR%\python*._pth") do set PTH_FILE=%%f

    if not defined PTH_FILE (
        echo ERROR: Could not find python*._pth file in %PYTHON_INSTALL_DIR%
        pause
        exit /b
    )

    echo Found ._pth file: %PTH_FILE%

    :: Backup original ._pth file
    copy "%PTH_FILE%" "%PTH_FILE%.bak" >nul

    :: Modify ._pth file to enable site-packages
    for %%f in ("%PYTHON_INSTALL_DIR%\python*.zip") do set PYTHON_ZIP_FILE=%%f
    (
        echo %PYTHON_ZIP_FILE%
        echo .
        echo Lib\site-packages
        echo import site
    ) > "%PTH_FILE%"


    :: Add to Environment to PATH
    echo Adding Python to PATH...
    set "PATH=%PYTHON_INSTALL_DIR%;%PYTHON_SCRIPTS_DIR%;%PATH%"
    echo %PATH%
    
    if %ADD_TO_SYSTEM_PATH% equ 1 (
        echo Adding Python to system PATH...
        :: Add to system envrionment
        setx /M PATH "%PYTHON_INSTALL_DIR%;%PYTHON_SCRIPTS_DIR%;%PATH%"
    )

    :: Verify installation
    echo Verifying Python installation...
    "%PYTHON_INSTALL_DIR%\python.exe" --version
    if %ERRORLEVEL% neq 0 (
        echo Python installation verification failed.
    ) else (
        echo Python %PYTHON_VERSION% successfully installed at %PYTHON_INSTALL_DIR%
    )

    :: Download get-pip.py
    echo Downloading pip installer...
    powershell -Command "(New-Object System.Net.WebClient).DownloadFile('https://bootstrap.pypa.io/get-pip.py', '%PYTHON_DOWNLOAD_DIR%\get-pip.py')"
    if %ERRORLEVEL% neq 0 (
        echo Failed to download pip installer
        pause
        exit /b
    )

    :: Install pip properly for embedded Python
    echo Installing pip...
    "%PYTHON_INSTALL_DIR%\python.exe" "%PYTHON_DOWNLOAD_DIR%\get-pip.py" --no-warn-script-location --trusted-host pypi.org --trusted-host files.pythonhosted.org
    if %ERRORLEVEL% neq 0 (
        echo Failed to install pip
        echo Trying alternative installation method...
        "%PYTHON_INSTALL_DIR%\python.exe" -c "import urllib.request; urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py', '%PYTHON_DOWNLOAD_DIR%\get-pip.py')"
        "%PYTHON_INSTALL_DIR%\python.exe" "%PYTHON_DOWNLOAD_DIR%\get-pip.py" --no-warn-script-location
        if %ERRORLEVEL% neq 0 (
            echo Pip installation failed completely
            pause
            exit /b
        )
    )

    :: Verify pip installation
    echo Verifying pip...
    "%PYTHON_INSTALL_DIR%\python.exe" -m pip --version
    if %ERRORLEVEL% neq 0 (
        echo Pip verification failed
        pause
        exit /b
    )
    
    :: Verify build backend is available
    echo Verifying build backend...
    (    
        echo Installing complete setuptools package...
        "%PYTHON_INSTALL_DIR%\python.exe" -m pip install --force-reinstall setuptools --no-warn-script-location

        if %ERRORLEVEL% neq 0 (
            echo setuptools install failed
            pause
            exit /b
        )
    )

    :: Install Conan
    echo Installing Conan...
    "%PYTHON_INSTALL_DIR%\python.exe" -m pip install conan
    if %ERRORLEVEL% neq 0 (
        echo Failed to install Conan
        pause
        exit /b
    )

    echo Verifying conan...
    "%PYTHON_SCRIPTS_DIR%\conan.exe" --version
    if %ERRORLEVEL% neq 0 (
        echo Conan verification failed
        pause
        exit /b
    )

    :: Get installation details
    echo Collecting installation details...

    :: Display installation summary
    echo.
    echo ========================================
    echo          INSTALLATION SUMMARY
    echo ========================================
    echo.
    echo [PYTHON INSTALLATION]
    echo Version:     %PYTHON_VERSION%
    echo Location:    %PYTHON_INSTALL_DIR%
    echo Executable:  %PYTHON_EXE%
    python -c "import sys; print(sys.executable)"
    echo.
    echo [PIP INSTALLATION]
    "%PYTHON_INSTALL_DIR%\python.exe" -m pip show pip
    echo.
    echo [CONAN INSTALLATION]
    "%PYTHON_INSTALL_DIR%\python.exe" -m pip show conan