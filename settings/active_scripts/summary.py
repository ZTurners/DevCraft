import os
import stat
import shutil
from pathlib import Path
import subprocess
import platform
import json
import sys

class WorkspaceSummary:
    def __init__(self):
        # Get the directory where this script is located
        self.m_workspace_root_path = Path(__file__).parent.absolute()
        return

    def run_command(self, command: str) -> str:
        """Run a Conan command and return its output."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"Error running Conan command: {e.stderr}")
            raise

    def get_python_info(self):
        print("Python info:")
        print(f"    Version: {sys.version}")
        print(f"    Path: {sys.version}")
        output_data = {
            "Version": sys.version,
            "Path" : sys.executable,
        }
        return output_data

    def get_conan_info(self):
        output = self.run_command(f'conan list "*:*" --format=json')
        try:
            data = json.loads(output)
            libs_with_first_package = []
            
            for lib_name, lib_data in data["Local Cache"].items():
                # Get the first revision (if multiple exist)
                revision_data = next(iter(lib_data["revisions"].values()))
                
                # Extract all package IDs for this library
                for package_id in revision_data["packages"].keys():
                    libs_with_first_package.append((lib_name, package_id))
                    break
            
            output_data = {
                "Version": self.run_command(f'conan --version'),
                "Home" : self.run_command(f'conan config home'),
                "LocalCaches": []
            }

            # Print the results
            print("Libraries with their first revisions:")
            for lib, package_id in libs_with_first_package:
                folder = self.run_command(f'conan cache path "{lib}:{package_id}"').strip()
                print(f"    fetched package info: {lib}:{package_id} {folder}")
                output_data["LocalCaches"].append(
                    {
                        f"{lib}":
                        {
                            "package_id": f"{package_id}",
                            "folder": f"{folder}",
                        }
                    }
                )

            return output_data
            
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON output: {e}")
            raise
        except Exception as e:
            print(f"Unexpected error processing JSON: {e}")
            raise

    def generator_summary_json(self):
        output_jason_data = {
            "Python": self.get_python_info(),
            "Conan": self.get_conan_info()
        }

        json_string = json.dumps(output_jason_data, indent=4)
        with open(os.path.join(self.m_workspace_root_path, 'summary.json'), 'w', encoding='utf-8') as f:
            f.write(json_string)

        return

def main():
    workspace_summary = WorkspaceSummary()
    workspace_summary.generator_summary_json()
    
if __name__ == "__main__":
    main()