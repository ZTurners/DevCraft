#!/usr/bin/env python3
"""
Windows SDK version detection script.
Detects the latest installed Windows SDK version.

Usage:
    python detection_win_sdk_version.py
    python detection_win_sdk_version.py --version-check 10.0.26100.0
    python detection_win_sdk_version.py --version-check 10.0.26100.0 --info-output-file <path/to/info.json>
"""

import sys
import os
import json
import re
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
    """Detect the latest installed Windows SDK version and install folder."""
    sdk_base_path = find_windows_sdk_include_base_path()

    if not sdk_base_path:
        print("Warning: Windows SDK base path not found")
        return None, None

    try:
        sdk_versions = sorted(
            [d.name for d in sdk_base_path.iterdir() if d.is_dir()],
            reverse=True
        )

        if sdk_versions:
            latest_sdk = sdk_versions[0]
            print(f"Detected Windows SDK version: {latest_sdk}")
            install_folder = sdk_base_path.parent
            return latest_sdk, install_folder

        print("Warning: No Windows SDK versions found")
        return None, None
    except Exception as e:
        print(f"Error detecting Windows SDK: {e}")
        return None, None


def parse_version_pattern(raw_value):
    """Validate and normalize a dotted Windows SDK version pattern string."""
    if raw_value is None:
        return None

    pattern = str(raw_value).strip()
    if not pattern:
        raise ValueError(
            "Expected a non-empty Windows SDK version pattern, "
            f"got: {raw_value}"
        )

    valid_part = re.compile(r"^(\d+|[xX*])$")
    parts = pattern.split('.')
    if not all(valid_part.match(part) for part in parts):
        raise ValueError(
            "Expected a dotted Windows SDK version pattern using numeric "
            "parts or x/* wildcards, "
            f"got: {raw_value}"
        )

    return pattern


def check_version_matches(detected_version, required_pattern):
    """Return True when detected version matches required pattern with x/* wildcards."""
    if not required_pattern:
        return True

    detected_parts = str(detected_version).split('.')
    required_parts = str(required_pattern).split('.')

    if len(detected_parts) != len(required_parts):
        return False

    for detected_part, required_part in zip(detected_parts, required_parts):
        if required_part in ("x", "X", "*"):
            continue

        if detected_part != required_part:
            return False

    return True


def main():
    parser = argparse.ArgumentParser(description="Detect Windows SDK version")
    parser.add_argument(
        "--version-check",
        "--version_check",
        dest="version_check",
        help="Require the detected Windows SDK version to match this value (supports x/* wildcard parts)",
    )
    parser.add_argument(
        "--info-output-file",
        dest="info_output_file",
        help="Path to write detected Windows SDK info JSON",
    )
    args = parser.parse_args()

    try:
        version_pattern = parse_version_pattern(args.version_check)
    except ValueError as exc:
        parser.error(str(exc))

    print("Windows SDK Detection Script")
    print("=" * 50)
    print()

    sdk_version, install_folder = detect_windows_sdk_version()
    if not sdk_version:
        print("Failed to detect Windows SDK")
        return 1

    if not check_version_matches(sdk_version, version_pattern):
        print(
            "Error: Detected Windows SDK version "
            f"{sdk_version} does not match required version pattern {version_pattern}."
        )
        return 1

    os.environ['DEVCRAFT_WINDOWS_SDK_VERSION'] = sdk_version

    if args.info_output_file:
        info_path = Path(args.info_output_file)
        info_path.parent.mkdir(parents=True, exist_ok=True)
        info_payload = {
            "version": sdk_version,
            "install_folder": str(install_folder) if install_folder else "",
        }
        info_path.write_text(json.dumps(info_payload, indent=2), encoding="utf-8")
        print(f"Written: {info_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
