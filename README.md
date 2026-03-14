# DevCraft

## Overview
DevCraft is a cross-platform developer environment bootstrap repository. It downloads, installs, and activates local toolchains inside the repository so developers can work with a consistent setup without depending on machine-global installs.

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

## Documentation
Detailed documentation is maintained in the Obsidian Git repository.

Update the link below to your current Obsidian docs repository if needed:

- `Index.md`: `<OBSIDIAN_GIT_REPO_URL>/DevCraft/Index.md`