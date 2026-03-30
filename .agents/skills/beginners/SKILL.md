---
name: beginners
description: Step-by-step onboarding guide for new developers setting up DevCraft for the first time. Use this skill when someone says they are new, asks what to do first, or needs help setting up the development environment. Guides the user through cloning DevCraft, running the install script, activating the local toolchain, and verifying the setup is working.
---
# beginners-guide

Step-by-step instructions for a new developer to set up the DevCraft environment from scratch.

## When to use

Use this skill when the user needs help getting started with DevCraft or setting up the local development environment for the first time.

Common situations include:
- They are new to DevCraft or new to the project.
- They ask how to get started, what to do first, or what the setup steps are.
- They are using a new machine and need to install or bootstrap the environment.
- They need to activate the local toolchain or verify that the setup completed successfully.

## Memory Policy

- User Memory [NoAccess, NoStore]
- Session Memory [ReadWrite]
- Repo Memory [NoAccess, NoStore]

---

## Overview

DevCraft is a **self-contained developer environment bootstrap** repository. It downloads and installs all required toolchains (CMake, Conan, LLVM, Vulkan SDK, Android NDK, Emscripten, etc.) into the repository's own `workspace/` folder. This means:

- No global installs required.
- Every developer uses exactly the same tool versions.
- The environment is activated on-demand — it does not permanently modify your system PATH.

---

## Instructions

### Step 0 — Setup

Follow the "Memory Policy" specified above.

Before starting, ask the user:

> What operating system are you on?
>
> 1. **Windows** (x86_64)
> 2. **macOS** (ARM64 / Apple Silicon)

Store the answer as `HOST_OS` (`windows` or `macos`) and use it to select the correct commands in every step below.

---

### Step 1 — Prerequisites check

Before running the install script, verify the following tools are already available on the system. These are the only things DevCraft does **not** install automatically:

#### Windows

| Tool | Why needed | How to check |
|---|---|---|
| **Git** | Cloning repos and submodule management | `git --version` |
| **Python 3.8+** | The install script bootstraps via Python | `python --version` |
| **Visual Studio 2022** (with C++ workload) | MSVC compiler for Windows builds | Check Start Menu or `cl` in a VS Developer Prompt |
| **Windows SDK** | Comes with VS 2022 C++ workload | Bundled with Visual Studio |

#### macOS

| Tool | Why needed | How to check |
|---|---|---|
| **Git** | Cloning repos and submodule management | `git --version` |
| **Python 3.8+** | The install script bootstraps via Python | `python3 --version` |
| **Xcode Command Line Tools** | Clang compiler and SDK headers | `xcode-select --install` |
| **Homebrew** | Package manager used by the bootstrap script | `brew --version` |

If any prerequisite is missing, help the user install it before continuing.

---

### Step 2 — Clone the DevCraft repository

If the user has not already cloned DevCraft, run:

```bash
git clone https://github.com/ZTurners/DevCraft.git
cd DevCraft
```

If they already have it cloned, make sure they are in the `DevCraft` root directory before continuing.

---

### Step 3 — Run the install script

This script downloads and installs all toolchains into `DevCraft/workspace/`. It may take **10–30 minutes** depending on internet speed.

#### Windows

```bat
install.windows.bat
```

#### macOS

```sh
./install.macos.sh
```

What the install script does:

- Reads tool configurations from `configs/<tool>/<tool>_config.<os>.yaml`.
- Downloads each tool into `workspace/<tool>/`.
- Generates activation scripts under `workspace/`.

> **Note:** If the script fails partway through, it is safe to run again — it will skip tools that are already downloaded.

---

### Step 4 — Activate the environment

After installation, the toolchains are **not** active by default. You must activate the environment each time you start a new terminal or VS Code session.

#### Windows — Command Prompt session

```bat
workspace\active_with_cmd.windows.bat
```

#### Windows — Open VS Code with environment active

```bat
workspace\active_with_vscode.windows.bat
```

#### macOS — Terminal session

```sh
source workspace/active.macos.sh
```

> **Tip for Windows users:** Use `active_with_vscode.windows.bat` for your daily workflow. It launches VS Code with all tools on the PATH so CMake, Conan, Ninja, and the compilers are all available inside the integrated terminal.

---

### Step 5 — Verify the installation

After activating, run the following commands to confirm the key tools are available:

```bash
# CMake
cmake --version
# Expected: cmake version 4.x.x

# Conan
conan --version
# Expected: Conan version 2.x.x

# Ninja
ninja --version
# Expected: 1.x.x

# Clang (cross-compilation toolchain)
clang --version
# Expected: clang version 21.x.x

# Python
python --version
# Expected: Python 3.x.x
```

#### Windows-only checks

```bat
:: MSVC compiler (run from a VS Developer Command Prompt or after activating)
cl
:: Expected: Microsoft (R) C/C++ Optimizing Compiler ...

:: Vulkan SDK
vulkaninfo --summary
:: Expected: Vulkan Instance Version: 1.4.x
```

If any tool is missing or shows an unexpected version, check that:
1. The `install` script completed without errors.
2. The activation script was run in the **current** terminal session.

---

### Step 6 — What to do next

Once the environment is verified, the developer is ready to work with any repository that depends on DevCraft toolchains.

Typical next steps:

1. **Set up ArieoEngine** — Clone the `ArieoEngine` repo alongside `DevCraft`, then launch VS Code via `active_with_vscode.windows.bat` from the DevCraft workspace.
2. **Read the ArieoEngine beginner guide** — Open the `ArieoEngine` repo in VS Code, then ask: *"I am a beginner, what should I do first?"*
3. **Explore the configs** — Browse `DevCraft/configs/` to understand which tool versions are installed and how to customise them.

---

### Step 7 — Common problems

| Problem | Likely cause | Fix |
|---|---|---|
| `cmake: command not found` after activation | Activation script was not sourced in this session | Re-run the activation script in the current terminal |
| Install script fails downloading a tool | Network issue or proxy | Check internet connection; try again — the script is idempotent |
| `conan` version is 1.x instead of 2.x | Old global Conan install shadowing the local one | Make sure the activation script runs **before** any other PATH setup |
| VS Code IntelliSense not finding headers | CMake Tools not configured with a preset | See ArieoEngine beginner guide for VSCode settings |
| `python` not found on macOS | macOS ships `python3`, not `python` | Use `python3` or install the `python` alias via Homebrew |
| Permission denied on `install.macos.sh` | Script not marked executable | Run `chmod +x install.macos.sh` first |

---

### Step 8 — Summary

Present the user with a final checklist:

> **DevCraft setup checklist**
>
> - [ ] Prerequisites installed (Git, Python, Visual Studio / Xcode)
> - [ ] DevCraft cloned
> - [ ] `install.<os>.bat/sh` completed successfully
> - [ ] Activation script run in current session
> - [ ] `cmake --version`, `conan --version`, `ninja --version` all return expected versions
> - [ ] Ready to open ArieoEngine or another project

If all boxes are checked, the setup is complete.
