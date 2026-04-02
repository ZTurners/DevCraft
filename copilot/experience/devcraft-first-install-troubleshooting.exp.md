---
title: devcraft-first-install-troubleshooting
topics:
  - devcraft
  - install
  - troubleshooting
  - first-time-setup
scope: local
status: working-notes
---

# DevCraft First Install Troubleshooting

## Theme

Only keep problems and fixes that a user may hit during the **first-time DevCraft installation**.

## Problem 1: Ran the wrong install script for the current OS

### Symptom
- Install does not work as expected from the start.
- Workspace is left in a partial or inconsistent state.

### Cause
Used the wrong platform entry script.

### Fix
Run the installer that matches the current OS from the repository root:
- Windows: `install.windows.bat`
- macOS: `./install.macos.sh`

Do not mix platform scripts.

---

## Problem 2: Config was changed but the installed environment did not update

### Symptom
- A config under `configs/**/*.yaml` was edited.
- Installed tools or generated environment still look unchanged.

### Cause
DevCraft install was not rerun after config changes.

### Fix
Rerun the platform install script from the repo root:
- Windows: `install.windows.bat`
- macOS: `./install.macos.sh`

For first-install debugging, always check this before assuming a deeper issue.

---

## Problem 3: Install completed, but tools are still unavailable in terminal or VS Code

### Symptom
- `cmake`, `conan`, `ninja`, `clang`, or `python` cannot be found.
- VS Code does not see the DevCraft toolchain.

### Cause
DevCraft was installed, but the environment was not activated for the current session.

### Fix
Activate from `workspace/` after install:

Windows terminal session:
```bat
workspace\active_with_cmd.windows.bat
```

Windows VS Code workflow:
```bat
workspace\active_with_vscode.windows.bat
```

macOS:
```sh
source workspace/active.macos.sh
```

For daily Windows usage, prefer launching VS Code through `active_with_vscode.windows.bat`.

---

## Problem 4: Windows terminal in VS Code uses PowerShell, but DevCraft commands only support cmd syntax

### Symptom
- Commands that should work in DevCraft fail only inside the VS Code integrated terminal.
- Batch commands or command syntax behave incorrectly in PowerShell.

### Cause
The current terminal profile is PowerShell, while the related DevCraft command flow only supports `cmd`.

### Fix
Use **Command Prompt** in VS Code instead of PowerShell.

How to find it in VS Code:
- Open the integrated terminal.
- Click the terminal profile selector near the terminal tab.
- Choose `Command Prompt` / `cmd`.
- If needed, use Terminal -> Select Default Profile, then set it to `Command Prompt`.

When working with DevCraft on Windows inside VS Code, prefer `cmd` as the terminal shell.

---

## Problem 5: A tool is missing from `workspace/`

### Symptom
- Expected tool folder is not present under `workspace/`.
- Or the tool folder exists but its activation script is missing.

### Cause
The related config likely failed or is incorrect.

### Fix
Check the corresponding config file under `configs/<tool>/`:
- `*_config.windows.yaml`
- `*_config.macos.yaml`

Then rerun the install script.

Expected verification after a healthy install:
- `workspace/` contains expected tool directories
- each installed tool directory contains `active.bat` or `active.sh`

---

## Problem 6: SHA-512 mismatch during install

### Symptom
- Install fails with checksum mismatch while downloading a tool.

### Cause
Corrupted download artifact.

### Fix
Delete the broken file from `.downloads/` and rerun install.

Do not keep retrying with the same corrupted artifact still present.

---

## Problem 7: Download was partially completed or truncated in the middle

### Symptom
- A package downloads only partially.
- A path appears to be cut off in the middle.
- Extraction or follow-up steps fail because the downloaded artifact is incomplete.

### Cause
A path containing spaces was not wrapped in quotes, so the command line was truncated at the space.
This kind of issue had already shown up before during `rustup` download handling, where the path was cut around the `Visual Studio` segment.

### Fix
When a download path contains spaces, always quote the full path.
Examples:
- correct: `"C:\\Program Files\\...\\file.zip"`
- wrong: `C:\Program Files\...\file.zip`

If a package looks partially downloaded, do not only suspect the network. Also inspect whether the path was broken because of missing quotes.

Treat any path containing `Visual Studio`, `Program Files`, or similar space-containing segments as high risk.

---

## Problem 8: Bootstrap Python is not available after bootstrap stage

### Symptom
- Python is still unavailable during or right after bootstrap.

### Cause
Bootstrap Python state is incomplete or misconfigured.

### Fix
On Windows, rerun bootstrap manually if needed:
```bat
bootstrap.windows.bat
```

Then rerun:
```bat
install.windows.bat
```

---

## Problem 9: Install was done, but validation was skipped, so later errors are hard to classify

### Symptom
- User assumes DevCraft is ready.
- Later build failures happen in downstream repos.
- It is unclear whether the root cause is DevCraft or the downstream project.

### Cause
No immediate post-install validation was done.

### Fix
After activation, verify the main tools immediately:

```bash
cmake --version
conan --version
ninja --version
clang --version
python --version
```

If these fail right after activation, fix DevCraft first before debugging any dependent repo.

---

## Problem 10: VS Code workflow works inconsistently between sessions

### Symptom
- One terminal sees tools, another does not.
- VS Code integrated terminal behaves differently from a manually opened shell.

### Cause
The editor was not launched from the activated DevCraft environment.

### Fix
On Windows, standardize on:
```bat
workspace\active_with_vscode.windows.bat
```

Use that as the normal entry point for repo work that depends on DevCraft.

---

## Keep for Later

If new first-install issues appear, only append entries in this format:
- symptom
- likely cause
- exact fix
- quick verification


