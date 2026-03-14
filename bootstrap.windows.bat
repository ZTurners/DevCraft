@echo off

set DEV_ENV_ROOT_PATH=%~dp0
set DEV_ENV_WORKSPACE_PATH=%DEV_ENV_ROOT_PATH%/workspace
set DEV_ENV_DOWNLOAD_PATH=%DEV_ENV_ROOT_PATH%/.downloads
set DEV_ENV_TOOLS_PATH=%DEV_ENV_WORKSPACE_PATH%/tools

if not exist "%DEV_ENV_DOWNLOAD_PATH%" mkdir "%DEV_ENV_DOWNLOAD_PATH%"
if not exist "%DEV_ENV_TOOLS_PATH%" mkdir "%DEV_ENV_TOOLS_PATH%"
echo Using Python tar extraction on Windows (no external tar bootstrap)

:: Install Python
:: SETLOCAL ENABLEDELAYEDEXPANSION
    
    :: Python Installer Batch Script
    :: Usage: Just double-click this .bat file to run it (Admin rights required)
    :: Check if jq is available (optional, for more complex JSON parsing)
    set "PYTHON_SETTING_FILE=%DEV_ENV_ROOT_PATH%/configs/boostrap_python_version.txt"
    
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
    set PYTHON_DOWNLOAD_DIR=%DEV_ENV_DOWNLOAD_PATH%
    set PYTHON_INSTALL_DIR=%DEV_ENV_WORKSPACE_PATH%/python/versions/%PYTHON_VERSION%
    set PYTHON_SCRIPTS_DIR=%PYTHON_INSTALL_DIR%/Scripts
    set ADD_TO_SYSTEM_PATH=0

    set ZIP_FILE=%PYTHON_DOWNLOAD_DIR%\python-%PYTHON_VERSION%-embed-amd64.zip

    :: Create directories if they don't exist
    echo Creating directories if needed ...

    if not exist "%PYTHON_DOWNLOAD_DIR%" mkdir "%PYTHON_DOWNLOAD_DIR%"

    echo Verifying Python installation...
    "%PYTHON_INSTALL_DIR%\python.exe" --version
    if %ERRORLEVEL% neq 0 (
        
        echo Creating installation directory: %PYTHON_INSTALL_DIR%
        mkdir "%PYTHON_INSTALL_DIR%"

        :: Download Python ZIP
        echo Downloading Python %PYTHON_VERSION% ...
        if not exist "%ZIP_FILE%" (
            echo Downloading from %PYTHON_URL% ...
            powershell -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%ZIP_FILE%'" 

        ) else (
            echo ZIP file already exists at %ZIP_FILE%
        )

        :: Extract Python
        echo Extracting Python to %PYTHON_INSTALL_DIR% ...
        if exist "%ZIP_FILE%" (
            powershell -Command "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%PYTHON_INSTALL_DIR%' -Force"
        ) else (
            echo Error: ZIP file not found!
            pause
            exit /b
        )
    )

    :: Configure Python environment
    echo Configuring Python ...
    :: Dynamically find the ._pth file
    
    for %%f in ("%PYTHON_INSTALL_DIR%\python*._pth") do set PTH_FILE=%%f
    for %%f in ("%PYTHON_INSTALL_DIR%\python*.zip") do set PYTHON_ZIP_FILE=%%f
    
    if not defined PTH_FILE (
        echo ERROR: Could not find python*._pth file in %PYTHON_INSTALL_DIR%
        pause
        exit /b
    )
    echo Found ._pth file: %PTH_FILE%
    
    if not exist "%PTH_FILE%.bak" (
        :: Backup original ._pth file
        copy "%PTH_FILE%" "%PTH_FILE%.bak" >nul

        :: Modify ._pth file to enable site-packages
        (
            echo %PYTHON_ZIP_FILE%
            echo .
            echo Lib\site-packages
            echo import site
        ) > "%PTH_FILE%"
    )

    :: Verify Python installation
    echo Verifying Python installation...
    "%PYTHON_INSTALL_DIR%\python.exe" --version
    if %ERRORLEVEL% neq 0 (
        echo Python installation verification failed.
        exit /b
    ) else (
        echo Python %PYTHON_VERSION% successfully installed at %PYTHON_INSTALL_DIR%
    )

    :: Add to Environment to PATH
    echo Adding Python to PATH...
    set "PATH=%PYTHON_INSTALL_DIR%;%PYTHON_SCRIPTS_DIR%;%PATH%"
    echo %PATH%

    :: Verify pip installation
    echo Verifying pip...
    "%PYTHON_INSTALL_DIR%\python.exe" -m pip --version
    if %ERRORLEVEL% neq 0 (
        :: Download get-pip.py
        echo Downloading pip installer...
        powershell -Command "(New-Object System.Net.WebClient).DownloadFile('https://bootstrap.pypa.io/get-pip.py', '%PYTHON_DOWNLOAD_DIR%\get-pip.py')"
        if not exist "%PYTHON_DOWNLOAD_DIR%\get-pip.py" (
            echo Failed to download pip installer
            pause
            exit /b
        )

        :: Install pip properly for embedded Python
        echo Installing pip...
        "%PYTHON_INSTALL_DIR%\python.exe" "%PYTHON_DOWNLOAD_DIR%\get-pip.py" --no-warn-script-location --trusted-host pypi.org --trusted-host files.pythonhosted.org
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
    "%PYTHON_INSTALL_DIR%\python.exe" -m pip show setuptools >nul 2>&1
    if %errorlevel% neq 0 (
        echo Installing complete setuptools package...
        "%PYTHON_INSTALL_DIR%\python.exe" -m pip install --force-reinstall setuptools --no-warn-script-location --no-cache-dir
    )

    echo Verifying build backend...
    "%PYTHON_INSTALL_DIR%\python.exe" -m pip show setuptools >nul 2>&1
    if %errorlevel% neq 0 (    
        echo setuptools verification failed
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
    echo Version:     
    python --version
    echo Location:    
    where python
    echo Executable:  %PYTHON_EXE%
    python -c "import sys; print(sys.executable)"
    echo.
    echo [PIP INSTALLATION]
    "%PYTHON_INSTALL_DIR%\python.exe" -m pip show pip
    echo.

    python --version

    :: Install PyYAML so configs/install.py can parse YAML configs
    echo Installing PyYAML (PyYAML is required for parsing YAML configs)...
    "%PYTHON_INSTALL_DIR%\python.exe" -m pip install --upgrade --disable-pip-version-check --no-cache-dir pyyaml
    if %ERRORLEVEL% neq 0 (
        echo Warning: Failed to install PyYAML automatically.
        echo You can install it manually by running:
        echo    python -m pip install pyyaml
    ) else (
        echo PyYAML installed successfully.
    )