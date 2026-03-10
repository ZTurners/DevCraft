#!/usr/bin/env python3
"""
Visual Studio version detection script.
Detects Visual Studio using vswhere, saves detailed info to JSON,
and writes a .bat file that sets VISUAL_STUDIO_MAJOR_VERSION.

Usage:
    python detection_visual_studio_version.py --output <path/to/output.bat>
"""

import os
import sys
import json
import argparse
import subprocess
import datetime
from pathlib import Path


def detect_visual_studio(workspace_root_path):
    """Detect Visual Studio installation using vswhere."""
    print("Info: Detecting Visual Studio installation...")
    
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
                    
        if len(vs_info) == 0:
            print("No Visual Studio installations found. Please install Visual Studio first.")
            print("You can download it from: https://visualstudio.microsoft.com/downloads/")
            return None

        # Search for installation for biggest version
        for install in vs_info:
            install_path = install.get('installationPath', '')
            install_version = install.get('installationVersion', '')

            if not vs_path or (install_version and install_version > vs_version):
                vs_path = install_path
                vs_version = install_version.split('.')[0] if install_version else None
        
        if vs_path and vs_version:
            print(f"Found Visual Studio {vs_version} at: {vs_path}")
            
            # Save detailed VS info to JSON file
            vs_info_dir = os.path.join(workspace_root_path, "visual_studio")
            print(f"Creating directory: {vs_info_dir}")
            os.makedirs(vs_info_dir, exist_ok=True)
            
            vs_info_path = os.path.join(vs_info_dir, "visual_studio_info.json")
            print(f"Will save VS info to: {vs_info_path}")
            
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
                            for instance in detailed_json:
                                if instance.get('installationPath') == vs_path:
                                    selected_vs = instance
                                    break
                            
                            if selected_vs:
                                # Add additional information
                                selected_vs['selected_timestamp'] = datetime.datetime.now().isoformat()
                                selected_vs['is_primary_instance'] = True
                                selected_vs['detected_path'] = vs_path
                                selected_vs['detected_version'] = vs_version
                                
                                print(f"Writing VS info to: {vs_info_path}")
                                with open(vs_info_path, 'w') as f:
                                    json.dump(selected_vs, f, indent=2)
                                print(f"Successfully saved VS info to: {vs_info_path}")
                            else:
                                print(f"Warning: Could not find VS instance with path {vs_path} in vswhere output")
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
    except subprocess.CalledProcessError as e:
        print(f"Error detecting Visual Studio: {e}")
    except Exception as e:
        print(f"Unexpected error during Visual Studio detection: {e}")

    return None




def main():
    parser = argparse.ArgumentParser(description="Detect Visual Studio version")
    parser.add_argument("--output", required=True, help="Path to write the output YAML file")
    args = parser.parse_args()

    script_dir = Path(__file__).parent.parent.parent.parent.absolute()
    workspace_root = script_dir / "workspace"

    print("Visual Studio Detection Script")
    print("=" * 50)
    print(f"Workspace: {script_dir}")
    print()

    result = detect_visual_studio(str(workspace_root))
    if not result:
        print("Failed to detect Visual Studio")
        return 1

    vs_path, vs_version = result

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        f"@echo off\nset VISUAL_STUDIO_MAJOR_VERSION={vs_version}\n",
        encoding="utf-8"
    )
    print(f"Written: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
