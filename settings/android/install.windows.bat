@echo off

:: Copy bootsrap folder to AndroidSDK
SETLOCAL
    call %DEV_ENV_ROOT_PATH%/conan/_generated/builder/windows/conanbuild.bat

    :: Check if source environment variable exists
    if "%ANDROID_SDK_BOOTSTRAP_ROOT%"=="" (
        echo Error: ANDROID_SDK_BOOTSTRAP_ROOT environment variable is not set
        exit /b 1
    )

    :: Set destination path (relative to current directory)
    set "DEST_PATH=./android/AndroidSDK/"

    :: Convert relative path to absolute path
    for %%I in ("%DEST_PATH%") do set "DEST_ABS_PATH=%%~fI"

    :: Create destination directory if it doesn't exist
    if not exist "%DEST_ABS_PATH%" (
        mkdir "%DEST_ABS_PATH%"
    )

    :: Copy files from source to destination
    echo Copying Android SDK files...
    xcopy "%ANDROID_SDK_BOOTSTRAP_ROOT%" "%DEST_ABS_PATH%" /E /I /Q /Y
    if errorlevel 1 (
        echo Error: Failed to copy files
        exit /b 1
    )

    :: Set the new environment variable
    set "ANDROID_SDK_ROOT=%DEST_ABS_PATH%"
    echo ANDROID_SDK_ROOT set to: %ANDROID_SDK_ROOT%

    :: Optionally: Set it permanently for future sessions
    :: setx ANDROID_SDK_ROOT "%DEST_ABS_PATH%"

    echo Operation completed successfully
ENDLOCAL

@echo off
SETLOCAL enabledelayedexpansion

    :: Check if sdkmanager is available
    where sdkmanager >nul 2>&1
    if %errorlevel% neq 0 (
        echo Error: sdkmanager not found in PATH
        echo Make sure ANDROID_SDK_ROOT is set correctly
        exit /b 1
    )

    :: Set your packages file path
    set "PACKAGES_FILE=packages.txt"

    :: Check if packages file exists
    if not exist "%PACKAGES_FILE%" (
        echo Error: Packages file not found: %PACKAGES_FILE%
        exit /b 1
    )

    :: Read packages and build install command
    set "INSTALL_CMD=sdkmanager --install "
    set "first=1"

    for /f "usebackq tokens=*" %%A in ("%PACKAGES_FILE%") do (
        set "package=%%A"
        :: Remove any trailing whitespace
        set "package=!package: =!"
        if not "!package!"=="" (
            if !first! equ 1 (
                set "INSTALL_CMD=!INSTALL_CMD!"!package!""
                set "first=0"
            ) else (
                set "INSTALL_CMD=!INSTALL_CMD! "!package!""
            )
        )
    )

    :: Check if we found any packages
    if "%first%"=="1" (
        echo No valid packages found in %PACKAGES_FILE%
        exit /b 1
    )

    :: Run the install command
    echo Installing packages...
    echo Command: %INSTALL_CMD%
    call %INSTALL_CMD%

    if %errorlevel% equ 0 (
        echo Packages installed successfully
    ) else (
        echo Error: Failed to install packages
        exit /b 1
    )

ENDLOCAL