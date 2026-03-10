#!/usr/bin/env python3
"""
Windows SDK version detection script.
Detects the latest installed Windows SDK version and writes a .bat file.

Usage:
    python detection_win_sdk_version.py --output <path/to/output.bat>
"""

import sys
import argparse
from pathlib import Path


def detect_windows_sdk_version():
    """Detect the latest installed Windows SDK version."""
    sdk_base_path = Path("C:/Program Files (x86)/Windows Kits/10/Include")
    
    if not sdk_base_path.exists():
        print("Warning: Windows SDK base path not found")
        return None
    
    try:
        # Get all SDK version directories, sorted in descending order
        sdk_versions = sorted(
            [d.name for d in sdk_base_path.iterdir() if d.is_dir()],
            reverse=True
        )
        
        if sdk_versions:
            latest_sdk = sdk_versions[0]
            print(f"Detected Windows SDK version: {latest_sdk}")
            return latest_sdk
        else:
            print("Warning: No Windows SDK versions found")
            return None
    except Exception as e:
        print(f"Error detecting Windows SDK: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Detect Windows SDK version")
    parser.add_argument("--output", required=True, help="Path to write the output YAML file")
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
        f"@echo off\nset WINDOWS_SDK_VERSION={sdk_version}\n",
        encoding="utf-8"
    )
    print(f"Written: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

