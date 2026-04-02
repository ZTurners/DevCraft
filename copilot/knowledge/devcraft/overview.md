---
title: devcraft-overview
topics:
  - devcraft
  - architecture
  - toolchain
  - bootstrap
  - workspace
scope: repo
status: working-notes
---

# DevCraft Overview

## Theme

This document is the high-level entry point for understanding what DevCraft is, how it is organized, how users are expected to work with it, and which companion AI knowledge files to read next.

---

## Core Definition and Positioning

DevCraft is a **repo-local developer environment bootstrap and toolchain workspace**. Its job is to define, install, and activate a consistent set of development tools inside the repository itself instead of relying on machine-global setup. In practice, DevCraft turns the repository into a reproducible environment layer: tool versions are declared in `configs/`, installed into `workspace/`, and activated on demand through generated activation scripts.

---

## Core Design Principles

### 1. Config-driven environment provisioning

DevCraft uses per-tool YAML files under `configs/` to describe how each toolchain should be downloaded, unpacked, initialized, and exposed to the user environment.

### 2. Repo-local installation

Installed artifacts live under `workspace/` rather than system directories. This keeps the environment portable, versioned, and easier to reproduce across machines.

### 3. Activation instead of permanent global mutation

DevCraft does not depend on permanently modifying the host system PATH for normal usage. Instead, it generates activation scripts that assemble the required environment for the current shell or IDE session.

### 4. Multi-toolchain and multi-target orientation

The repository is structured to support not just one compiler or SDK, but a broad environment surface including native Windows builds, Android, Vulkan, LLVM, WASM/WASI, Rust, .NET, and cross-compilation resources.

### 5. AI-readable repository knowledge

The `copilot/` directory complements the install system with AI-facing knowledge, skills, and troubleshooting documents so both humans and AI assistants can reason about the repository in a consistent way.

---

## Root Structure Overview

### Root entry scripts

- `install.windows.bat` — Windows installation entry point
- `install.macos.sh` — macOS installation entry point
- `bootstrap.windows.bat` — Windows bootstrap stage for Python and installer prerequisites
- `bootstrap.macos.sh` — macOS bootstrap stage

### `configs/`

This is the environment definition layer. Each subdirectory represents a tool or environment module, typically with platform-specific config files such as:

- `*_config.windows.yaml`
- `*_config.macos.yaml`

Current major modules include:

- `active/`
- `android_sdk/`
- `cmake/`
- `conan/`
- `dotnet/`
- `emscripten/`
- `gradle/`
- `jdk/`
- `llvm/`
- `mustache/`
- `ninja/`
- `python/`
- `rustup/`
- `sysroot/`
- `tools/`
- `visual_studio/`
- `vscode/`
- `vulkan/`
- `wasm/`
- `xcode/`

These configs define installation actions such as:

- `download`
- `unzip`
- `copy`
- `execute`
- `environments`
- `resolve_symlinks`
- `make_execute_permission`
- `generator_active_batch`

`configs/install.py` is the central installer/orchestrator that reads these configs and performs the installation workflow.

### `workspace/`

This is the repo-local output directory where installed tools and generated activation scripts live. Typical contents include:

- `workspace/python/`
- `workspace/cmake/`
- `workspace/conan/`
- `workspace/llvm/`
- `workspace/visual_studio/`
- `workspace/vulkan/`
- `workspace/wasm/`
- `workspace/android/`
- `workspace/dotnet/`
- `workspace/rust/`

Important activation entry points include:

- `workspace/active.windows.bat`
- `workspace/active_with_cmd.windows.bat`
- `workspace/active_with_vscode.windows.bat`

### `copilot/`

This is the AI knowledge layer for the repository.

- `copilot/knowledge/` — overview and long-lived repository understanding
- `copilot/skills/` — task-oriented operational guidance
- `copilot/experience/` — troubleshooting notes and working experience records

This document belongs to the **knowledge** layer and should stay high-level and navigational.

---

## Standard User Workflow

### 1. Clone the repository

The user starts from the repository root.

### 2. Run the platform install entry

Use the script that matches the host OS:

- Windows: `install.windows.bat`
- macOS: `./install.macos.sh`

### 3. Let bootstrap prepare the installer runtime

On Windows, `bootstrap.windows.bat` prepares the local Python runtime and installs prerequisites such as `pip`, `setuptools`, and `PyYAML`, which are needed by `configs/install.py`.

### 4. Let the installer materialize the environment

`configs/install.py` reads the YAML module configs, downloads tools, unpacks archives, runs setup commands, and generates activation scripts under `workspace/`.

### 5. Activate the environment before daily work

Typical activation flow:

- Terminal session: activate the generated workspace environment
- VS Code workflow on Windows: prefer `workspace/active_with_vscode.windows.bat`

### 6. Work inside the activated environment

After activation, commands such as `cmake`, `conan`, `clang`, `cargo`, `dotnet`, `sdkmanager`, and related tools are expected to resolve from the repo-local environment.

### 7. Re-run install after config changes

If a user edits files under `configs/**/*.yaml`, they should rerun the install entry script so the installed artifacts and generated activation scripts reflect the new configuration.

---

## AI Terminology Standardization

Use the following terms consistently when describing DevCraft.

### Preferred terms

- **DevCraft**: the repository as a whole
- **repo-local environment**: the environment installed under this repository
- **bootstrap**: the prerequisite setup stage before the main install orchestration
- **installer/orchestrator**: `configs/install.py`
- **module config**: a tool-specific YAML file under `configs/`
- **activation script**: generated script that applies environment variables for use
- **workspace**: the installation/output root under `workspace/`
- **toolchain module**: one installable module such as `llvm`, `cmake`, `rustup`, or `vulkan`
- **knowledge layer**: `copilot/knowledge/`
- **skill layer**: `copilot/skills/`
- **experience layer**: `copilot/experience/`

### Avoid inconsistent phrasing

Prefer these forms:

- Say **repo-local environment**, not “a random local tool folder”
- Say **activation**, not “just run some bat files”
- Say **module config**, not “that yaml thing”
- Say **installer/orchestrator**, not “the python script” when precision matters
- Say **knowledge / skills / experience**, not mixing them as one generic docs bucket

---

## Other Knowledge Base Quick Links

### Onboarding / first-time setup

- `copilot/skills/beginners/beginners_guide.skill.md`

Use this when the goal is step-by-step setup guidance for a new developer.

### First-install troubleshooting

- `copilot/experience/.local/devcraft-first-install-troubleshooting.exp.md`

Use this when installation was attempted but the environment is incomplete, not activated, or inconsistent.

### This document

- `copilot/knowledge/devcraft/overview.md`

Use this when the goal is to understand what DevCraft is, how it is structured, and how the repository is supposed to be reasoned about at a high level.

---

## Current Environment Surface at a Glance

From the current repository configuration, DevCraft covers a broad toolchain surface, including:

- Python
- CMake
- Ninja
- Conan
- Portable Visual Studio / MSVC + Windows SDK
- LLVM
- JDK
- Gradle
- Android SDK / NDK
- Emscripten
- .NET SDK
- Rust / rustup
- WASM tools (`wasmtime`, `wabt`, `wasi-sdk`)
- Vulkan SDK
- sysroot assets for cross-target scenarios
- local VS Code environment support

This makes DevCraft best understood as a **toolchain workspace repository**, not just a one-off installer.

---

## One-Sentence Summary

DevCraft is a config-driven, repo-local toolchain workspace that installs development dependencies into `workspace/`, activates them through generated scripts, and documents them through a structured AI knowledge layer.
