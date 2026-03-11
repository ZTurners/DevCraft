#!/usr/bin/env python3
"""
Windows SDK version detection script.
Detects the latest installed Windows SDK version and writes a .bat file.

Usage:
    python detection_win_sdk_version.py --output <path/to/output.bat>
"""

import sys
import os
import argparse
from pathlib import Path

try:
    import winreg
except Exception:
    winreg = None


def find_windows_sdk_include_base_path():
    """Resolve Windows SDK Include base path without hard-coded Program Files path."""
    candidates = []

    # 1) Preferred: Windows registry (official source for KitsRoot10)
    if winreg is not None:
        reg_keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows Kits\Installed Roots", "KitsRoot10"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows Kits\Installed Roots", "KitsRoot10"),
        ]
        for hive, key_path, value_name in reg_keys:
            try:
                with winreg.OpenKey(hive, key_path) as key:
                    kits_root, _ = winreg.QueryValueEx(key, value_name)
                    if kits_root:
                        candidates.append(Path(kits_root) / "Include")
            except Exception:
                pass

    # 2) Fallback: SDK-related environment variables
    for env_name in ("WindowsSdkDir", "WindowsSDKDir", "WindowsSdkDir_10"):
        env_value = os.environ.get(env_name)
        if env_value:
            candidates.append(Path(env_value) / "Include")

    # 3) Last fallback: derive from ProgramFiles env vars (still dynamic, not hard-coded full path)
    for pf_env in ("ProgramFiles(x86)", "ProgramFiles"):
        pf_value = os.environ.get(pf_env)
        if pf_value:
            candidates.append(Path(pf_value) / "Windows Kits" / "10" / "Include")

    # Return the first existing Include base directory.
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate

    return None


def detect_windows_sdk_version():
    """Detect the latest installed Windows SDK version."""
    sdk_base_path = find_windows_sdk_include_base_path()

    if not sdk_base_path:
        print("Warning: Windows SDK base path not found")
        return None

    try:
        sdk_versions = sorted(
            [d.name for d in sdk_base_path.iterdir() if d.is_dir()],
            reverse=True
        )

        if sdk_versions:
            latest_sdk = sdk_versions[0]
            print(f"Detected Windows SDK version: {latest_sdk}")
            return latest_sdk

        print("Warning: No Windows SDK versions found")
        return None
    except Exception as e:
        print(f"Error detecting Windows SDK: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Detect Windows SDK version")
    parser.add_argument("--output", required=True, help="Path to write the output bat file")
    args = parser.parse_args()

    print("Windows SDK Detection Script")
    print("=" * 50)
    print()

    sdk_version = detect_windows_sdk_version()
    if not sdk_version:
        print("Failed to detect Windows SDK")
        return 1

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        f"@echo off\nset DEVCRAFT_WINDOWS_SDK_VERSION={sdk_version}\n",
        encoding="utf-8"
    )
    print(f"Written: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
