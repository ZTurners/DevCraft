# dev_env

## Overview
This repositry is used to download and install tools/SDKs for development automatically and isolately so that we can keep all develpers in the same environment to avoid conflicts and ambious

## Priciples
- The storage is a closure: All tools/SDKs are downloaded into a local bin folder under ROOT folder so that it won't effect anything else already on the local system.
    - By running "install.bat" and "install.sh"
- The usage is a closure: Just set the environment variables (no other ways) to make the downloaded tools/SDKs availiable and availiable only in the environment
    - By running "bootstrap.bat" and "bootstrap.sh"

## Architecture
- The repositry install tools in three ways: 
    - From Nuget (No support for linux now, windows only)
    - From Conan (Besides the default conan depots, we use a self-hosted conan artifactor: https://roundtables.kplanb.com:10030/artifactory/api/conan/kplanb_conan )
    - Manually download and setting the correspond environment variables 
- All the configurations of the download tools are located in the "configs" folder which specify the download tools source, version, etc

## Flow
- Download Python manually.
- Download Nuget manually.
- Install pip and conan.
- Install toolset/SDKs defined in Nuget
- Install toolset/SDKs defined in Conan
- Setting the environment variables to make toolset/SDKs availiable

## Usages
- run "install.bat"/"install.sh" first time or when check tools/SDK updated
- run "bootstrap.bat"/"bootstrap.sh" everytime before you start development work
- after bootstrap, start you develop work in the isolated environment

### With VSCode
- For windows, start VSCode with "code.exe" after bootstrap.
- For Linux, the vscode-server will started and load a script "~/.vscode-server/server-env-setup", so we just make this file and call bootstrap.