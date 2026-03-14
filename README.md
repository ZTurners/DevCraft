# DevCraft

## Overview
DevCraft is a cross-platform developer environment bootstrap repository. It downloads, installs, and activates local toolchains inside the repository so developers can work with a consistent setup without depending on machine-global installs.

The repository is organized around three main parts:
- `configs/`: configuration and platform-specific install definitions
- `configs/install.py`: installation and orchestration logic
- `workspace/`: local tool installs, activation scripts, and runtime state

## Primary Workflow
1. Run the platform bootstrap script.
2. Bootstrap verifies or installs Python using `configs/boostrap_python_version.txt`.
3. Run the platform install script.
4. `configs/install.py` reads the tool configs under `configs/` and installs artifacts into `workspace/`.
5. Use the activation scripts under `workspace/` for daily development work.

## Entry Points

### Windows
- `bootstrap.windows.bat`
- `install.windows.bat`
- `workspace/active.windows.bat`
- `workspace/active_with_cmd.windows.bat`
- `workspace/active_with_vscode.windows.bat`

### macOS
- `bootstrap.macos.sh`
- `install.macos.sh`

## Quick Start

### Windows
Run:

```bat
install.windows.bat
```

For daily work after installation:

```bat
workspace\active_with_cmd.windows.bat
```

Or launch VS Code with the local environment:

```bat
workspace\active_with_vscode.windows.bat
```

### macOS
Run:

```sh
./install.macos.sh
```

## Current Tool Areas
DevCraft currently contains configuration or workspace support for:
- Python
- JDK
- .NET
- Gradle
- Conan
- CMake
- LLVM
- Emscripten
- Android SDK
- Rustup
- Vulkan SDK
- Visual Studio / Windows SDK
- VS Code

## Example Workspace State
The current repository snapshot already contains local installs or activation state for several tools, including:
- Python bootstrap target `3.13.5`
- CMake `4.2.3`
- .NET SDK `10.0.101-win-x64`
- JDK `25`
- Emscripten `3.1.73`
- Gradle `9.1.0`

## Validation After Install
After activating the environment, verify the major tools are visible:

```bat
python --version
cmake --version
dotnet --info
java -version
conan --version
```

## Notes
- `workspace/` behaves as managed local tool state, not a normal source-only directory.
- `.downloads/` is used as a download cache during installation.
- `configs/install.py` can generate YAML equivalents for JSON configuration files under `configs/`.