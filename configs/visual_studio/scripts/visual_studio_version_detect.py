#!/usr/bin/env python3
"""
Visual Studio version detection script.
Detects Visual Studio using vswhere and saves detailed info to JSON.

Usage:
    python detection_visual_studio_version.py
    python detection_visual_studio_version.py --version-check 18.3.x.x
    python detection_visual_studio_version.py --version-check 18.3.x.x --info-output-file <path/to/info.json>
    python detection_visual_studio_version.py --vswhere <path/to/vswhere.exe>
"""

import os
import sys
import json
import argparse
import subprocess
import datetime
import re
from pathlib import Path


def parse_version_pattern(raw_value):
    """Validate and normalize a dotted version pattern string."""
    if raw_value is None:
        return None

    pattern = str(raw_value).strip()
    if not pattern:
        raise ValueError(
            "Expected a non-empty Visual Studio version pattern, "
            f"got: {raw_value}"
        )

    valid_part = re.compile(r"^(\d+|[xX*])$")
    parts = pattern.split('.')
    if not all(valid_part.match(part) for part in parts):
        raise ValueError(
            "Expected a dotted Visual Studio version pattern using numeric "
            "parts or x/* wildcards, "
            f"got: {raw_value}"
        )

    return pattern


def version_matches_pattern(version_text, pattern_text):
    """Return True when version_text matches pattern_text with x/* wildcards."""
    if pattern_text is None:
        return True

    version_parts = str(version_text).split('.')
    pattern_parts = str(pattern_text).split('.')

    if len(version_parts) != len(pattern_parts):
        return False

    for version_part, pattern_part in zip(version_parts, pattern_parts):
        if pattern_part in ("x", "X", "*"):
            continue
        if version_part != pattern_part:
            return False

    return True


def parse_version_sort_key(version_text):
    """Convert a dotted version string into a sortable tuple of integers."""
    if not version_text:
        return tuple()

    parts = []
    for part in str(version_text).split('.'):
        if part.isdigit():
            parts.append(int(part))
        else:
            break
    return tuple(parts)


def detect_visual_studio(workspace_root_path, version_pattern=None, info_output_file=None, vswhere_path=None):
    """Detect Visual Studio installation using vswhere."""
    print("Info: Detecting Visual Studio installation...")
    
    if not vswhere_path:
        vswhere_path = os.path.join(workspace_root_path, "visual_studio", "vswhere.exe")
    
    if not os.path.exists(vswhere_path):
        print(f"Error: vswhere.exe not found at {vswhere_path}")
        print("Please ensure bootstrap.windows.bat was run successfully.")
        return None
    
    print(f"Using vswhere.exe from: {vswhere_path}")

    try:
        # First, check for any Visual Studio installation with all details
        print("Checking for Visual Studio installations...")
        basic_check = subprocess.run([
            vswhere_path,
            '-all', '-legacy', '-prerelease',
            '-format', 'json'
        ], capture_output=True, text=True)

        vs_info = json.loads(basic_check.stdout)
        # Now extract path and version from the found installations
        vs_path = None
        vs_version = None
        highest_version_key = tuple()
                    
        if len(vs_info) == 0:
            print("No Visual Studio installations found. Please install Visual Studio first.")
            print("You can download it from: https://visualstudio.microsoft.com/downloads/")
            return None

        # Search for installation for biggest version
        for install in vs_info:
            install_path = install.get('installationPath', '')
            install_version = install.get('installationVersion', '')
            install_version_key = parse_version_sort_key(install_version)

            if not version_matches_pattern(install_version, version_pattern):
                continue

            if not vs_path or install_version_key > highest_version_key:
                vs_path = install_path
                vs_version = install_version.split('.')[0] if install_version else None
                highest_version_key = install_version_key
        
        if vs_path and vs_version:
            print(f"Found Visual Studio {vs_version} at: {vs_path}")

            # Get detailed information about the selected VS instance
            print("Running vswhere to get detailed information...")
            detailed_info = subprocess.run([
                vswhere_path,
                '-all',
                '-legacy',
                '-prerelease',
                '-format', 'json'
            ], capture_output=True, text=True)

            if detailed_info.returncode != 0:
                print(f"Error running vswhere: {detailed_info.stderr}")
                print(f"Command output: {detailed_info.stdout}")
            else:
                try:
                    print("Parsing vswhere output...")
                    if not detailed_info.stdout.strip():
                        print("Warning: vswhere returned empty output")
                    else:
                        detailed_json = json.loads(detailed_info.stdout)
                        if not detailed_json:
                            print("Warning: No VS instances found in JSON output")
                        else:
                            # Find the matching VS instance
                            selected_vs = None
                            normalized_detected_path = os.path.normcase(os.path.normpath(vs_path))
                            for instance in detailed_json:
                                instance_path = instance.get('installationPath', '')
                                normalized_instance_path = os.path.normcase(os.path.normpath(instance_path))
                                if normalized_instance_path == normalized_detected_path:
                                    selected_vs = instance
                                    break

                            if selected_vs is None:
                                raise RuntimeError(
                                    "Could not find the selected Visual Studio instance "
                                    f"in detailed vswhere output for path: {vs_path}"
                                )

                            # Add additional information
                            selected_vs['selected_timestamp'] = datetime.datetime.now().isoformat()
                            selected_vs['is_primary_instance'] = True
                            selected_vs['detected_path'] = vs_path
                            selected_vs['detected_version'] = vs_version

                            if info_output_file:
                                info_output_path = Path(info_output_file)
                                info_output_path.parent.mkdir(parents=True, exist_ok=True)
                                print(f"Writing VS info to: {info_output_path}")
                                with open(info_output_path, 'w', encoding='utf-8') as f:
                                    json.dump(selected_vs, f, indent=2)
                                print(f"Successfully saved VS info to: {info_output_path}")
                except json.JSONDecodeError as je:
                    print(f"JSON parsing error: {je}")
                    print(f"Raw output: {detailed_info.stdout}")
                except Exception as e:
                    print(f"Unexpected error saving VS info: {e}")
            
            # Set environment variables for current process (for install.py to use)
            os.environ['env_vs_path'] = vs_path
            os.environ['env_vs_version'] = str(vs_version)
            print(f"env_vs_path: {vs_path}")
            print(f"env_vs_version: {vs_version}")
            
            return vs_path, vs_version

        print(
            "Error: No Visual Studio installation matches required version pattern "
            f"{version_pattern}."
        )
        return None
    except subprocess.CalledProcessError as e:
        print(f"Error detecting Visual Studio: {e}")
    except Exception as e:
        print(f"Unexpected error during Visual Studio detection: {e}")

    return None


def main():
    parser = argparse.ArgumentParser(description="Detect Visual Studio version")
    parser.add_argument(
        "--vswhere",
        help="Path to vswhere.exe",
    )
    parser.add_argument(
        "--version-check",
        help="Require the detected Visual Studio major version to match the major component of this value",
    )
    parser.add_argument(
        "--info-output-file",
        help="Path to write detected Visual Studio instance info JSON",
    )
    args = parser.parse_args()

    try:
        version_pattern = parse_version_pattern(
            args.version_check
        )
    except ValueError as exc:
        parser.error(str(exc))

    script_dir = Path(__file__).parent.parent.parent.parent.absolute()
    workspace_root = script_dir / "workspace"

    print("Visual Studio Detection Script")
    print("=" * 50)
    print(f"Workspace: {script_dir}")
    print()

    result = detect_visual_studio(
        str(workspace_root),
        version_pattern=version_pattern,
        info_output_file=args.info_output_file,
        vswhere_path=args.vswhere,
    )
    if not result:
        print("Failed to detect Visual Studio")
        return 1

    vs_path, vs_version = result
    print(f"Detected Visual Studio major version: {vs_version}")
    print(f"Detected Visual Studio path: {vs_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
