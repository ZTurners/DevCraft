@echo off

set DEV_ENV_ROOT_PATH=%~dp0
set DEV_ENV_WORKSPACE_PATH=%DEV_ENV_ROOT_PATH%/workspace
set DEV_ENV_DOWNLOAD_PATH=%DEV_ENV_ROOT_PATH%/.downloads
set DEV_ENV_TOOLS_PATH=%DEV_ENV_WORKSPACE_PATH%/tools

if not exist "%DEV_ENV_DOWNLOAD_PATH%" mkdir "%DEV_ENV_DOWNLOAD_PATH%"
if not exist "%DEV_ENV_TOOLS_PATH%" mkdir "%DEV_ENV_TOOLS_PATH%"
echo Using Python tar extraction on Windows (no external tar bootstrap)

:: Enable long path support (total path length beyond 260 chars), system-wide
:: Direct write when already elevated; otherwise pops the native UAC dialog to elevate on the spot
reg query "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled 2>nul | find "0x1" >nul
if errorlevel 1 (
	reg add "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled /t REG_DWORD /d 1 /f >nul 2>&1
	if errorlevel 1 (
		rem Not elevated: pop the native UAC dialog and write from an elevated hidden reg.exe
		powershell -NoProfile -Command "Start-Process reg -Verb RunAs -WindowStyle Hidden -Wait -ArgumentList 'add HKLM\SYSTEM\CurrentControlSet\Control\FileSystem /v LongPathsEnabled /t REG_DWORD /d 1 /f'" >nul 2>&1
	)
)

:: Verify it is really set; deep workspace installs break without it, so abort instead of continuing
reg query "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled 2>nul | find "0x1" >nul
if errorlevel 1 (
	echo [ERROR] Long path support could not be enabled: UAC prompt declined or write failed.
	echo          Enable it from an elevated prompt, then rerun this script:
	echo          reg add "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled /t REG_DWORD /d 1 /f
	pause
	exit /b 1
)
echo [OK] Long path support enabled: total path length up to 32767 chars

:: Install Python
:: SETLOCAL ENABLEDELAYEDEXPANSION
    
    :: Python Installer Batch Script
    :: Usage: Just double-click this .bat file to run it (Admin rights required)
    :: The bootstrap interpreter version is pinned here; the user-facing
    :: ${workspace}/python tree is versioned separately by configs/python
    set "BOOTSTRAP_PYTHON_VERSION=3.13.5"

    echo Setting BOOTSTRAP_PYTHON_VERSION=%BOOTSTRAP_PYTHON_VERSION%
    set PYTHON_URL=https://www.python.org/ftp/python/%BOOTSTRAP_PYTHON_VERSION%/python-%BOOTSTRAP_PYTHON_VERSION%-embed-amd64.zip
    set PYTHON_DOWNLOAD_DIR=%DEV_ENV_DOWNLOAD_PATH%
    :: Bootstrap interpreter lives apart from the user-facing ${workspace}/python
    :: tree (duplicated by the python config) so an sdk_root wipe there can
    :: never touch the interpreter install.py itself runs on
    set PYTHON_INSTALL_DIR=%DEV_ENV_WORKSPACE_PATH%/bootstrap/python
    set PYTHON_SCRIPTS_DIR=%PYTHON_INSTALL_DIR%/Scripts
    set ADD_TO_SYSTEM_PATH=0

    set ZIP_FILE=%PYTHON_DOWNLOAD_DIR%\python-%BOOTSTRAP_PYTHON_VERSION%-embed-amd64.zip

    :: Create directories if they don't exist
    echo Creating directories if needed ...

    if not exist "%PYTHON_DOWNLOAD_DIR%" mkdir "%PYTHON_DOWNLOAD_DIR%"

    echo Verifying Python installation...
    "%PYTHON_INSTALL_DIR%\python.exe" --version
    if %ERRORLEVEL% neq 0 (
        
        echo Creating installation directory: %PYTHON_INSTALL_DIR%
        mkdir "%PYTHON_INSTALL_DIR%"

        :: Download Python ZIP
        echo Downloading Python %BOOTSTRAP_PYTHON_VERSION% ...
        if not exist "%ZIP_FILE%" (
            echo Downloading from %PYTHON_URL% ...
            where curl.exe >nul 2>&1
            if not errorlevel 1 (
                curl.exe -fL --progress-bar -o "%ZIP_FILE%.tmp" "%PYTHON_URL%"
            ) else (
                echo curl.exe not found, falling back to Invoke-WebRequest ...
                powershell -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%ZIP_FILE%.tmp'"
            )
            if errorlevel 1 (
                if exist "%ZIP_FILE%.tmp" del /f /q "%ZIP_FILE%.tmp"
                echo Error: Failed to download %PYTHON_URL%
                pause
                exit /b 1
            )
            move /y "%ZIP_FILE%.tmp" "%ZIP_FILE%" >nul
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
            exit /b 1
        )
    )

    :: Configure Python environment
    echo Configuring Python ...
    :: Dynamically find the ._pth file
    
    set "PTH_FILE="
    set "PYTHON_ZIP_FILE="
    for %%f in ("%PYTHON_INSTALL_DIR%\python*._pth") do if exist "%%~ff" set "PTH_FILE=%%~ff"
    for %%f in ("%PYTHON_INSTALL_DIR%\python*.zip") do if exist "%%~ff" set "PYTHON_ZIP_FILE=%%~nxf"

    if not defined PTH_FILE (
        echo ERROR: Could not find python*._pth file in %PYTHON_INSTALL_DIR%
        pause
        exit /b 1
    )
    if not defined PYTHON_ZIP_FILE (
        echo ERROR: Could not find python*.zip standard library in %PYTHON_INSTALL_DIR%
        pause
        exit /b 1
    )
    echo Found ._pth file: %PTH_FILE%

    :: Keep the original backup, but refresh configuration on every run.
    :: Relative paths are resolved beside ._pth and survive moving the project.
    if not exist "%PTH_FILE%.bak" copy "%PTH_FILE%" "%PTH_FILE%.bak" >nul
    (
        echo %PYTHON_ZIP_FILE%
        echo .
        echo Lib\site-packages
        echo import site
    ) > "%PTH_FILE%"
    if errorlevel 1 (
        echo ERROR: Failed to configure Python module paths.
        exit /b 1
    )

    :: --version skips runtime initialization; verify standard-library imports too.
    echo Verifying Python installation...
    "%PYTHON_INSTALL_DIR%\python.exe" -c "import encodings, site, sys; print(sys.version)"
    if %ERRORLEVEL% neq 0 (
        echo Python installation verification failed.
        exit /b 1
    ) else (
        echo Python %BOOTSTRAP_PYTHON_VERSION% successfully installed at %PYTHON_INSTALL_DIR%
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
            exit /b 1
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
        exit /b 1
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
    echo Executable:  %PYTHON_INSTALL_DIR%\python.exe
    python -c "import sys; print(sys.executable)"
    echo.
    echo [PIP INSTALLATION]
    "%PYTHON_INSTALL_DIR%\python.exe" -m pip show pip
    echo.

    python --version

    :: Install PyYAML + pypdl so configs/install.py can parse YAML configs and
    :: download tool archives multi-threaded (configs/download.py); pip show is
    :: a local check, so an already-provisioned machine skips the pypi round-trip
    "%PYTHON_INSTALL_DIR%\python.exe" -m pip show pyyaml >nul 2>&1 && "%PYTHON_INSTALL_DIR%\python.exe" -m pip show pypdl >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        echo PyYAML and pypdl already installed, skipping pip install.
    ) else (
        echo Installing PyYAML and pypdl...
        "%PYTHON_INSTALL_DIR%\python.exe" -m pip install --upgrade --disable-pip-version-check --no-cache-dir pyyaml pypdl
        if errorlevel 1 (
            echo Warning: Failed to install PyYAML/pypdl automatically.
            echo You can install them manually by running:
            echo    python -m pip install pyyaml pypdl
        ) else (
            echo PyYAML and pypdl installed successfully.
        )
    )