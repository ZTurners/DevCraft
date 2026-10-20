# Electron runtime

The platform configs install the official Electron 44.9.1 runtime locally:

- Windows: x64
- macOS: arm64 (Apple Silicon), matching the existing DevCraft macOS toolchain

Run the normal DevCraft installer (`install.windows.bat` or
`./install.macos.sh`). Config discovery and the workspace activation scripts
automatically pick up this module. Downloads are SHA-256 pinned to the official
GitHub release assets; update both version and platform checksum when upgrading.
macOS extraction uses `/usr/bin/ditto` to preserve framework symlinks and modes.

After activating the workspace, `ELECTRON_HOME` points to the unpacked runtime
and `ELECTRON_EXECUTABLE` points to its executable. Launch an application folder
whose package.json declares the main-process entry point:

```bat
rem Windows cmd
"%ELECTRON_EXECUTABLE%" --version
"%ELECTRON_EXECUTABLE%" "C:\path\to\desktop-app"
```

```sh
# macOS
"$ELECTRON_EXECUTABLE" --version
"$ELECTRON_EXECUTABLE" "/path/to/desktop-app"
```

This module installs the runtime, not application dependencies or packaging
tools. Use DevCraft's separate Node.js/npm environment to build Vite projects.
Projects may still pin the matching `electron` npm devDependency for TypeScript
definitions and tooling; it normally downloads its own runtime. Do not assume
that setting ELECTRON_HOME configures npm or application packaging tools.
Native Node addon headers and rebuild tools are only needed for `.node` addons,
not for the WASM/WebGPU integration.
