import os
import stat
import shutil
from pathlib import Path
import subprocess
import platform
import json
import configparser
import urllib.request
import datetime
import zipfile
import tarfile
import copy

class WorkspaceInstaller:
    def __init__(self):
        # Get the directory where this script is located
        self.m_dev_env_root_path = Path(__file__).parent.parent.absolute()
        self.m_settings_root_path = os.path.join(self.m_dev_env_root_path, "settings")
        self.m_workspace_root_path = os.path.join(self.m_dev_env_root_path, "workspace")
        self.m_system_name = platform.system()
        self.m_env_vs_path = None

        self.m_summary_data = []

    def detect_visual_studio(self):
        """Detect Visual Studio installation using vswhere."""
        if self.m_system_name != "Windows":
            return None

        print("Info: Detecting Visual Studio installation...")
        # Use our local vswhere from the workspace
        vswhere_path = os.path.join(self.m_workspace_root_path, "visual_studio", "vswhere.exe")
        
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
                exit(1)

            # Search for installation for biggest version
            for install in vs_info:
                install_path = install.get('installationPath', '')
                install_version = install.get('installationVersion', '')

                if not vs_path or (install_version and install_version > vs_version):
                    vs_path = install_path
                    vs_version = install_version.split('.')[0] if install_version else None
            
            if vs_path and vs_version:
                print(f"Found Visual Studio {vs_version} at: {vs_path}")
                # Set environment variables for the current process
                os.environ['env_vs_path'] = vs_path
                os.environ['env_vs_version'] = vs_version
                print(f"env_vs_path: {os.environ['env_vs_path']}")
                print(f"env_vs_version: {os.environ['env_vs_version']}")
                
                # Save detailed VS info to JSON file
                vs_info_dir = os.path.join(self.m_workspace_root_path, "visual_studio")
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
                
                # Store them for later use
                self.m_env_vs_path = vs_path
                self.m_env_vs_version = vs_version
                return vs_path, vs_version
        except subprocess.CalledProcessError as e:
            print(f"Error detecting Visual Studio: {e}")
        except Exception as e:
            print(f"Unexpected error during Visual Studio detection: {e}")

        return None

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
    
    def make_executable(self, path):
        mode = os.stat(path).st_mode
        mode |= (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.chmod(path, mode)

    def get_conan_lib_folder(self, lib_name):
        output = self.run_command(f'conan list "{lib_name}:*" --format=json')
        try:
            data = json.loads(output)
            packages = []
            
            # Navigate through the JSON structure based on the example
            local_cache = data.get("Local Cache", {})
            package_ref = local_cache.get(f"{lib_name}", {})
            revisions = package_ref.get("revisions", {})
            
            for revision_id, revision_data in revisions.items():
                for package_id, package_info in revision_data.get("packages", {}).items():
                    packages.append({
                        "id": package_id,
                        "revision": revision_id,
                        "settings": package_info.get("info", {}).get("settings", {})
                    })
            
            return self.run_command(f'conan cache path "{lib_name}:{packages[0]["id"]}"').strip()
            
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON output: {e}")
            raise
        except Exception as e:
            print(f"Unexpected error processing JSON: {e}")
            raise

    def install_from_config(self, config_file_path):
        """Generic installation function that handles downloading and extracting from configured URLs.
        Args:
            config_file_path (str): Path to the configuration JSON file
        """
        if not os.path.exists(config_file_path):
            print(f"Error: Configuration not found at {config_file_path}")
            exit(1)

        try:
            with open(config_file_path, 'r') as f:
                config = json.load(f)
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in configuration file: {config_file_path}")
            exit(1)
        except Exception as e:
            print(f"Unexpected error reading configuration: {e}")
            exit(1)
        
        # Handle active_batch configuration if present
        if "active_batch" in config:
            active_batch = config["active_batch"]
            if "file_path" in active_batch and "environments" in active_batch:
                # Process file path, replacing {workspace} with actual path
                file_path = active_batch["file_path"].replace("${workspace}", self.m_workspace_root_path)
                
                # Create the directory if it doesn't exist
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                # Prepare environment lists
                set_env_list = []
                prepend_env_list = []
                
                # Process set_list
                if "set_list" in active_batch["environments"]:
                    for var, value in active_batch["environments"]["set_list"].items():
                        # Replace workspace variable
                        value = value.replace("${workspace}", self.m_workspace_root_path)
                        set_env_list.append((var, value))
                
                # Process prepend_list
                if "prepend_list" in active_batch["environments"]:
                    for item in active_batch["environments"]["prepend_list"]:
                        # Each item is a dictionary with a single key-value pair
                        for var, value in item.items():
                            # Replace workspace variable
                            value = value.replace("${workspace}", self.m_workspace_root_path)
                            prepend_env_list.append((var, value))
                
                # Generate the batch file
                self.generate_enviroment_set_batch_file(file_path, set_env_list, prepend_env_list)

        # Process install items
        if "install" in config:
            for item in config["install"]:
                if "download_url" not in item:
                    print(f"Warning: Skipping {node_name} entry - no download URL provided")
                    continue

                temp_file = None
                try:
                    # Check if we have target_folder
                    target_folder = None
                    if "target_folder" in item:
                        target_folder = item["target_folder"].replace("${workspace}", self.m_workspace_root_path)
                        # Check if already installed
                        if os.path.exists(target_folder):
                            print(f"\nFiles already extracted to {target_folder}")
                            continue
                    
                    try:
                        if "download_url" in item:
                            download_filename = os.path.basename(item["download_url"])
                            # Create download directory in workspace
                            download_dir = os.path.join(self.m_workspace_root_path, ".download")
                            os.makedirs(download_dir, exist_ok=True)
                            temp_file = os.path.join(download_dir, download_filename)

                            # Download using curl with authentication
                            print(f"Downloading... {item["download_url"]}")

                            # Prepare curl command
                            curl_cmd = [
                                "curl",
                                "--progress-bar",  # Show download progress
                                "-L",  # Follow redirects
                            ]

                            # Add authentication if needed
                            need_auth = item.get("download_auth", False)
                            if need_auth:                    
                                from urllib.parse import urlparse
                                domain = urlparse(item["download_url"]).netloc
                                print(f"\nDownloading from {domain}")
                                
                                username = input("Username: ")
                                curl_cmd.extend(["--user", f"{username}"])  # Curl will prompt for password

                            # Add output file specification
                            curl_cmd.extend([
                                "-o", temp_file,  # Output file
                                "-f",  # Fail on HTTP errors
                                "-S",  # Show error
                                "--retry", "3",  # Retry up to 3 times
                                "--retry-delay", "5",  # Wait 5 seconds between retries
                                item["download_url"]
                            ])
                            subprocess.run(curl_cmd, check=True)
                            
                            # Verify the downloaded file
                            if not os.path.exists(temp_file):
                                raise Exception("Downloaded file does not exist")
                            
                            file_size = os.path.getsize(temp_file)
                            if file_size == 0:
                                raise Exception("Downloaded file is empty")
                            print("\nDownload completed and verified.")    

                        # Check if we need to unzip the archive
                        if "unzip_source" in item:
                            # Check file extension to determine archive type
                            is_zip = temp_file.lower().endswith('.zip')
                            is_tar_gz = temp_file.lower().endswith('.tar.gz')
                            is_tar_xz = temp_file.lower().endswith('.tar.xz')

                            if not (is_zip or is_tar_gz or is_tar_xz):
                                raise Exception("Unsupported archive format. Only .zip, .tar.gz, and .tar.xz are supported")

                            # Verify archive integrity
                            try:
                                if is_zip:
                                    with zipfile.ZipFile(temp_file, 'r') as test_zip:
                                        if test_zip.testzip() is not None:
                                            raise Exception("ZIP file is corrupted")
                                else:  # tar.gz or tar.xz
                                    mode = "r:gz" if is_tar_gz else "r:xz"
                                    with tarfile.open(temp_file, mode) as test_tar:
                                        test_tar.getmembers()
                            except (zipfile.BadZipFile, tarfile.TarError) as e:
                                raise Exception(f"Invalid archive file: {str(e)}")

                            
                            print(f"\nExtracting files to {target_folder}...")
                            
                            # Get source folder if specified
                            src_folder = item.get("src_folder", "")
                            
                            if is_zip:
                                with zipfile.ZipFile(temp_file, 'r') as zip_ref:
                                    # Get all members and filter by src_folder or unzip_source if specified
                                    all_members = zip_ref.namelist()
                                    unzip_source = item.get("unzip_source", "")
                                    
                                    if src_folder or unzip_source:
                                        # Use either src_folder or unzip_source as the base directory
                                        base_dir = src_folder if src_folder else unzip_source
                                        # Only extract files from the specified source folder
                                        members = [m for m in all_members if m.startswith(base_dir)]
                                        # Get the base directory to remove
                                        base_dir_len = len(base_dir) + 1  # +1 for the slash
                                    else:
                                        members = all_members
                                        base_dir_len = 0

                                    total = len(members)
                                    
                                    # Extract with progress
                                    for index, member in enumerate(members, 1):
                                        if base_dir_len > 0:
                                            # Remove the base directory prefix from the path
                                            target_path = member[base_dir_len:]
                                            if target_path:  # Skip if empty (was the base dir itself)
                                                zip_ref.extract(member, target_folder)
                                                extracted_path = os.path.join(target_folder, member)
                                                final_path = os.path.join(target_folder, target_path)
                                                # Create the parent directory if it doesn't exist
                                                os.makedirs(os.path.dirname(final_path), exist_ok=True)
                                                # Move file to remove base directory prefix
                                                if os.path.exists(extracted_path):
                                                    shutil.move(extracted_path, final_path)
                                        else:
                                            zip_ref.extract(member, target_folder)
                                        percent = (index * 100) // total
                                        print(f"\rProgress: {percent}% [{index}/{total} files]", end="", flush=True)
                            else:  # tar.gz or tar.xz
                                mode = "r:gz" if is_tar_gz else "r:xz"
                                with tarfile.open(temp_file, mode) as tar:
                                    # Get all members and filter by src_folder or unzip_source if specified
                                    all_members = tar.getmembers()
                                    unzip_source = item.get("unzip_source", "")
                                    
                                    if unzip_source or src_folder:
                                        # Use either src_folder or unzip_source as the path filter
                                        path_filter = unzip_source if unzip_source else src_folder
                                        # Only extract files from the specified path
                                        members = [m for m in all_members if m.name.startswith(path_filter)]
                                        # For unzip_source, we want to remove the entire prefix
                                        if unzip_source:
                                            base_dir_len = len(unzip_source) + 1  # +1 for the slash
                                        else:
                                            base_dir = src_folder.split('/')[0]
                                            base_dir_len = len(base_dir) + 1
                                    else:
                                        members = all_members
                                        base_dir_len = 0

                                    total = len(members)
                                    
                                    # Extract with progress
                                    for index, member in enumerate(members, 1):
                                        if base_dir_len > 0:
                                            # Create a copy of the member to modify
                                            new_member = copy.copy(member)
                                            # Remove the prefix from the path
                                            new_member.name = member.name[base_dir_len:]
                                            if new_member.name:  # Skip if empty
                                                # Check if this is a directory
                                                if not new_member.name.endswith('/'):
                                                    tar.extract(new_member, target_folder)
                                        else:
                                            tar.extract(member, target_folder)
                                        percent = (index * 100) // total
                                        print(f"\rProgress: {percent}% [{index}/{total} files]", end="", flush=True)
                            print("\nExtraction completed.")

                        # Check if we have an execute command
                        if "execute_command" in item:
                            print("\nExecuting installation command...")
                            
                            # Replace variables in the command
                            command = item["execute_command"]
                            command = command.replace("${target_folder}", target_folder)
                            command = command.replace("${download_file}", temp_file)
                            
                            # Create output directory if it doesn't exist
                            os.makedirs(os.path.dirname(target_folder), exist_ok=True)
                            
                            # Execute the command
                            try:
                                need_admin = item.get("execute_command_as_admin", False)
                                if need_admin:
                                    print(f"Running command with administrative privileges: {command}")
                                    if self.m_system_name == "Windows":
                                        # Create a PowerShell command to run the process as admin
                                        ps_command = f'Start-Process -FilePath "{temp_file}" -ArgumentList "install --root={target_folder}" -Verb RunAs -Wait'
                                        subprocess.run(["powershell", "-Command", ps_command], check=True)
                                    else:
                                        # For Linux/macOS, use sudo
                                        sudo_command = f"sudo {command}"
                                        subprocess.run(sudo_command, shell=True, check=True)
                                else:
                                    print(f"Running command: {command}")
                                    subprocess.run(command, shell=True, check=True)
                                print("Command executed successfully.")
                            except subprocess.CalledProcessError as e:
                                print(f"Error executing command: {e}")
                                if need_admin:
                                    print("Note: This error might be due to insufficient privileges.")
                                    print("Please ensure you have administrative rights.")
                                raise
                        
                        # Clean up the downloaded archive
                        os.remove(temp_file)
                        print("Installation completed successfully.\n")

                    except subprocess.CalledProcessError as e:
                        print(f"\nError downloading file: {e}")
                        if e.returncode == 22:  # HTTP error code
                            print("Authentication failed or access denied. Please check your credentials.")
                        elif e.returncode == 6:  # Could not resolve host
                            print("Could not resolve host. Please check your internet connection.")
                        elif e.returncode == 28:  # Operation timeout
                            print("Download timed out. Please try again or check your connection.")
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                        exit(1)
                    except Exception as e:
                        print(f"\nError verifying downloaded file: {e}")
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                        exit(1)

                except subprocess.CalledProcessError as e:
                    print(f"Error running curl command: {e}")
                    exit(1)
                except tarfile.TarError as e:
                    print(f"Error extracting archive: {e}")
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                    exit(1)
                except Exception as e:
                    print(f"Unexpected error during installation: {e}")
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                    exit(1)
                finally:
                    if temp_file and os.path.exists(temp_file):
                        os.remove(temp_file)

    def install_sysroot(self):
        """Install sysroot by downloading and extracting from configured URLs."""
        if self.m_system_name == "Windows":
            sysroot_config_path = os.path.join(self.m_settings_root_path, "sysroot", "sysroot_config.windows.json")
        elif self.m_system_name == "Linux":
            sysroot_config_path = os.path.join(self.m_settings_root_path, "sysroot", "sysroot_config.linux.json")
        elif self.m_system_name == "Darwin":
            sysroot_config_path = os.path.join(self.m_settings_root_path, "sysroot", "sysroot_config.macos.json")
        self.install_from_config(sysroot_config_path)

    def install_sdk(self):
        """Install SDK by downloading and extracting from configured URLs."""
        if self.m_system_name == "Windows":
            sdk_config_path = os.path.join(self.m_settings_root_path, "sdk", "sdk_config.windows.json")
        elif self.m_system_name == "Linux":
            sdk_config_path = os.path.join(self.m_settings_root_path, "sdk", "sdk_config.linux.json")
        elif self.m_system_name == "Darwin":
            sdk_config_path = os.path.join(self.m_settings_root_path, "sdk", "sdk_config.macos.json")
        self.install_from_config(sdk_config_path)

    def install_tools(self):
        """Install tools by downloading and extracting from configured URLs."""
        if self.m_system_name == "Windows":
            tools_config_path = os.path.join(self.m_settings_root_path, "tools", "tools_config.windows.json")
        elif self.m_system_name == "Linux":
            tools_config_path = os.path.join(self.m_settings_root_path, "tools", "tools_config.linux.json")
        elif self.m_system_name == "Darwin":
            tools_config_path = os.path.join(self.m_settings_root_path, "tools", "tools_config.macos.json")
        self.install_from_config(tools_config_path)

    def install_jdk(self):
        """Install JDK by downloading and extracting from configured URLs."""
        if self.m_system_name == "Windows":
            jdk_config_path = os.path.join(self.m_settings_root_path, "jdk", "jdk_config.windows.json")
        elif self.m_system_name == "Linux":
            jdk_config_path = os.path.join(self.m_settings_root_path, "jdk", "jdk_config.linux.json")
        elif self.m_system_name == "Darwin":
            jdk_config_path = os.path.join(self.m_settings_root_path, "jdk", "jdk_config.macos.json")
        self.install_from_config(jdk_config_path)

    def generate_enviroment_set_batch_file(self, output_file, set_env_list, prepend_env_list):
        # Basic check
        if self.m_system_name == "Windows":
            output_file = output_file + ".bat"
            with open(output_file, 'w') as f:
                f.write("@echo off\n\n")
                f.write(":: Auto-generated environment setup script (Windows)\n")
                f.write(":: This script sets and appends environment variables\n\n")
                
                # Set commands (overwrite existing values)
                for var_name, value in set_env_list:
                    value = value.replace("\\", "/")
                    f.write(f'set {var_name}={value}\n')
                
                if set_env_list and prepend_env_list:
                    f.write('\n')
                
                # Append commands
                for var_name, value in prepend_env_list:
                    value = value.replace("\\", "/")
                    f.write(f'set {var_name}={value};%{var_name}%\n')
                
                f.write('\necho Environment variables set successfully\n')
        else:
            output_file = output_file + ".sh"
            with open(output_file, 'w') as f:
                f.write("#!/bin/bash\n\n")
                f.write("# Auto-generated environment setup script\n")
                f.write("# This script sets and appends environment variables\n\n")
                
                # Write set commands (overwrite existing values)
                for var_name, value in set_env_list:
                    f.write(f'export {var_name}="{value}"\n')
                
                if set_env_list and prepend_env_list:
                    f.write('\n')
                
                # Write append commands
                for var_name, value in prepend_env_list:
                    f.write(f'export {var_name}="{value}:${var_name}"\n')
                
                f.write('\necho "Environment variables set successfully"\n')
        
        # Make the script executable
        import os
        os.chmod(output_file, 0o755)
        print(f"Bash script generated at: {output_file}")


    def install_all(self):
        if self.m_system_name == "Windows":
            vs_info = self.detect_visual_studio()
            if vs_info:
                self.m_env_vs_path, self.m_env_vs_version = vs_info

        self.install_active_script()
        self.install_sysroot()
        self.install_sdk()
        self.install_jdk()
        self.install_tools()
        self.install_conan()
        self.install_android_dev()
        self.install_vs_code_setting()
        self.install_python()
        self.install_rust()
        

    def install_active_script(self):
        self.active_scripts_src_folder = os.path.join(self.m_settings_root_path, "active_scripts")
        self.active_scripts_dest_folder = os.path.join(self.m_workspace_root_path)

        # Create destination directory if it doesn't exist
        os.makedirs(self.active_scripts_dest_folder, exist_ok=True)

        if self.m_system_name == "Windows":
            # Find all .bat files in source folder
            batch_files = [f for f in os.listdir(os.path.join(self.active_scripts_src_folder, "windows")) if f.endswith('.bat')]
            for batch_file in batch_files:
                shutil.copyfile(os.path.join(self.active_scripts_src_folder, "windows", batch_file), os.path.join(self.active_scripts_dest_folder, batch_file))
                self.make_executable(os.path.join(self.active_scripts_dest_folder, batch_file))
        elif self.m_system_name == "Linux":
            # Find all .bat files in source folder
            batch_files = [f for f in os.listdir(os.path.join(self.active_scripts_src_folder, "linux")) if f.endswith('.sh')]
            for batch_file in batch_files:
                shutil.copyfile(os.path.join(self.active_scripts_src_folder, "linux", batch_file), os.path.join(self.active_scripts_dest_folder, batch_file))
                self.make_executable(os.path.join(self.active_scripts_dest_folder, batch_file))
        elif self.m_system_name == "Darwin":
            # Find all .bat files in source folder
            batch_files = [f for f in os.listdir(os.path.join(self.active_scripts_src_folder, "macos")) if f.endswith('.sh')]
            for batch_file in batch_files:
                shutil.copyfile(os.path.join(self.active_scripts_src_folder, "macos", batch_file), os.path.join(self.active_scripts_dest_folder, batch_file))
                self.make_executable(os.path.join(self.active_scripts_dest_folder, batch_file))
        
        # copy summary.py
        shutil.copyfile(os.path.join(self.active_scripts_src_folder, "summary.py"), os.path.join(self.active_scripts_dest_folder, "summary.py"))

    def install_python(self):
        self.python_setting_folder_path = os.path.join(self.m_settings_root_path, "python")
        self.python_workspace_folder_path = os.path.join(self.m_workspace_root_path, "python")

        # read version.txt
        with open(os.path.join(self.python_setting_folder_path, "version.txt"), 'r') as file:
            python_version = file.read()
        # shutil.copyfile(os.path.join(self.python_setting_folder_path, "version.txt"), os.path.join(self.python_workspace_folder_path, "version.txt"))

        python_root_path = os.path.join(self.python_workspace_folder_path, f"python_{python_version}")
        python_bin_path = os.path.join(python_root_path, "bin")
        python_script_path = os.path.join(python_root_path, "scripts")

        # copy active python script
        self.generate_enviroment_set_batch_file(
            os.path.join(self.python_workspace_folder_path, "active"),
            set_env_list = [
                ('PYTHON_VERSION', python_version)
            ],
            prepend_env_list = [
                ('PATH', python_root_path),
                ('PATH', python_bin_path),
                ('PATH', python_script_path)
            ]
        )           

    def install_conan(self):
        # Create .conan directory 
        self.m_conan_setting_path = os.path.join(self.m_settings_root_path, "conan")
        self.m_conan_workspace_path = os.path.join(self.m_workspace_root_path, "conan")
        self.m_conan_home_path = os.path.join(self.m_conan_workspace_path, ".conan")

        os.makedirs(self.m_conan_workspace_path, exist_ok=True)
        os.makedirs(self.m_conan_home_path, exist_ok=True)

        # Set environment variables
        os.environ["CONAN_HOME"] = self.m_conan_home_path
        os.environ["CONAN_USE_ALWAYS_SHORT_PATHS"] = "1"

        # copy config files
        config_files = ["global.conf", "settings.yml", "remotes.json"]
        for file in config_files:
            src = Path(self.m_conan_setting_path) / file
            dst = Path(self.m_conan_home_path) / file
            if src.exists():
                shutil.copy2(src, dst)
        
        # Run conan commands
        try:
            # Detect profile
            subprocess.run(["conan", "profile", "detect", "--force"], check=True)
            
            conan_profile_file = ""
            conan_output_path = ""

            # Windows build
            if self.m_system_name == "Windows":
                conan_profile_file = os.path.join(self.m_conan_setting_path, "profiles", "builder", "conan_builder_profile.windows.txt")
                conan_output_path = os.path.join(self.m_conan_workspace_path)
            # Ubuntu build
            elif self.m_system_name == "Linux":
                conan_profile_file = os.path.join(self.m_conan_setting_path, "profiles", "builder", "conan_builder_profile.ubuntu.txt")
                conan_output_path = os.path.join(self.m_conan_workspace_path)
            # Macos build
            elif self.m_system_name == "Darwin":
                conan_profile_file = os.path.join(self.m_conan_setting_path, "profiles", "builder", "conan_builder_profile.macos.txt")
                conan_output_path = os.path.join(self.m_conan_workspace_path)

            os.makedirs(conan_output_path, exist_ok=True)
            conan_cmd = [
                "conan", "install", os.path.join(self.m_conan_setting_path, "conanfile.txt"),
                "--update",
                "--generator", "CMakeToolchain",
                "--generator", "VirtualBuildEnv",
                "--output-folder", str(conan_output_path),
                "--build", "never",
                "--profile", conan_profile_file
            ]

            # Add Visual Studio path if available
            if hasattr(self, 'm_env_vs_path') and self.m_env_vs_path:
                conan_cmd.extend([
                    "-c", f"tools.microsoft.msbuild:installation_path={self.m_env_vs_path}",
                    "-c", f"tools.microsoft.msbuild:vs_version={self.m_env_vs_version}"
                ])
                print(f"Using Visual Studio at: {self.m_env_vs_path}")

            subprocess.run(conan_cmd, check=True)
            
        except subprocess.CalledProcessError as e:
            print(f"Command failed with error: {e}")
            exit(1)

    def install_android_dev(self):
        # Set destination path (relative to current directory)
        self.m_android_dev_setting_path = os.path.join(self.m_settings_root_path, "android")
        self.m_android_dev_workspace_path = os.path.join(self.m_workspace_root_path, "android")
        self.m_android_sdk_root_path = os.path.join(self.m_android_dev_workspace_path, "AndroidSDK")

        if not os.path.exists(self.m_android_dev_workspace_path):
            # dig the android bootstrap package path
            self.m_android_sdk_bootstrap_root_path = self.get_conan_lib_folder("android_sdk/bootstrap@arieo/dev")
            print(f"Info: Got android sdk bootstrap root: {self.m_android_sdk_bootstrap_root_path}")

            if not self.m_android_sdk_bootstrap_root_path:
                print("Error: ANDROID_SDK_BOOTSTRAP_ROOT environment variable is not set")
                exit(1)
            if not os.path.exists(self.m_android_sdk_bootstrap_root_path):
                print(f"Error: Source directory does not exist: {self.m_android_sdk_bootstrap_root_path}")
                exit(1)
            
            # Create destination directory if it doesn't exist
            os.makedirs(self.m_android_dev_workspace_path, exist_ok=True)

            # Copy files from source to destination
            print(f"Copying Android SDK files to {self.m_android_dev_workspace_path}")
            try:
                shutil.copytree(self.m_android_sdk_bootstrap_root_path, self.m_android_dev_workspace_path, dirs_exist_ok=True)
            except Exception as e:
                print(f"Error: Failed to copy files: {str(e)}")
                exit(1)

        # Install packages
        try:
            android_settings_file = os.path.join(self.m_android_dev_setting_path, "settings.json")
            if self.m_system_name == "Windows":
                sdkmanager_exe_path = os.path.join(self.m_android_sdk_root_path, "cmdline-tools", "bootstrap", "bin", "sdkmanager.bat")
            else:
                sdkmanager_exe_path = os.path.join(self.m_android_sdk_root_path, "cmdline-tools", "bootstrap", "bin", "sdkmanager")

            with open(android_settings_file, 'r') as f:
                android_settings_json = json.load(f)
            
            # Get the list of packages to install (now nested under android_sdk)
            android_install_packages = android_settings_json['android_sdk']['install_packages']

            # Construct the sdkmanager command
            print(f"Installing Android SDK packages ... {str(android_install_packages)}")
            command = [sdkmanager_exe_path, '--install'] + android_install_packages
            
            result = subprocess.run(command, check=True)
            print("Command executed successfully:")
            print(result.stdout)
        except Exception as e:
            print(f"Error: Failed to install android sdk packages: {str(e)}")
            exit(1)

        # copy active python script
        self.generate_enviroment_set_batch_file(
            os.path.join(self.m_android_dev_workspace_path, "active"),
            set_env_list = [
                ('ANDROID_SDK_ROOT', self.m_android_sdk_root_path),
                ('GRADLE_USER_HOME', os.path.join(self.m_android_dev_workspace_path, ".gradle")),
                ('ANDROID_HOME', self.m_android_sdk_root_path),
                ('ANDROID_USER_HOME', os.path.join(self.m_android_dev_workspace_path, ".android"))
            ],
            prepend_env_list = [
                ('PATH', os.path.join(self.m_android_sdk_root_path, "cmdline-tools", "bootstrap", "bin")),
                ('PATH', os.path.join(self.m_android_sdk_root_path, "platform-tools")),
            ]
        )

    def install_vs_code_setting(self):
        self.vs_code_init_user_setting_file_path = os.path.join(self.m_settings_root_path, "vscode", "init_user_settings.json")
        self.vs_code_workspace_setting_folder = os.path.join(self.m_workspace_root_path, "vscode", ".config", "User")

        # Create destination directory if it doesn't exist
        os.makedirs(self.vs_code_workspace_setting_folder, exist_ok=True)
        shutil.copyfile(self.vs_code_init_user_setting_file_path, os.path.join(self.vs_code_workspace_setting_folder, "settings.json"))

    def install_rust(self):
        """Install Rust using rustup"""
        self.rust_workspace_path = os.path.join(self.m_workspace_root_path, "rust")
        os.makedirs(self.rust_workspace_path, exist_ok=True)

        # Read rustup settings
        rustup_settings_path = os.path.join(self.m_settings_root_path, "rust", "rustup.download.json")
        with open(rustup_settings_path, 'r') as f:
            rustup_settings = json.load(f)
        
        # Create rustup home and cargo home in work space
        os.makedirs(os.path.join(self.rust_workspace_path, ".rustup"), exist_ok=True)
        os.makedirs(os.path.join(self.rust_workspace_path, ".cargo"), exist_ok=True)

        # Copy settings.toml into it
        settings_toml_path = os.path.join(self.m_settings_root_path, "rust", "settings.toml")
        shutil.copyfile(settings_toml_path, os.path.join(self.rust_workspace_path, ".rustup", "settings.toml"))

        # Find platform settings for current system
        platform_settings = next((p for p in rustup_settings['platforms'] if p['name'].lower() == self.m_system_name.lower()), None)
        if not platform_settings:
            supported_platforms = [p['name'] for p in rustup_settings['platforms']]
            raise Exception(f"Platform settings for {self.m_system_name} not found in rustup.download.json. Supported platforms are: {', '.join(supported_platforms)}")
            
        # Setup common paths and environment
        rust_home = os.path.join(self.rust_workspace_path, ".rustup")
        cargo_home = os.path.join(self.rust_workspace_path, ".cargo")
        
        # Save original environment variables
        orig_rustup_home = os.environ.get("RUSTUP_HOME")
        orig_cargo_home = os.environ.get("CARGO_HOME")
        
        try:
            # Set environment for rustup installation
            os.environ["RUSTUP_HOME"] = rust_home
            os.environ["CARGO_HOME"] = cargo_home
            
            if self.m_system_name == "Windows":
                rustup_url = platform_settings['url']
                rustup_path = os.path.join(self.rust_workspace_path, "rustup-init.exe")
                
                def show_progress(count, block_size, total_size):
                    if total_size > 0:
                        percent = (count * block_size * 100) // total_size
                        print(f"\rDownloading rustup-init... {percent}% [{count * block_size}/{total_size} bytes]", end="", flush=True)
                    else:
                        print(f"\rDownloading rustup-init... {count * block_size} bytes", end="", flush=True)

                # Download rustup-init if needed
                if not os.path.exists(rustup_path):
                    print("Starting download of rustup-init...")
                    urllib.request.urlretrieve(rustup_url, rustup_path, show_progress)
                    print("\nDownload completed.")
                else:
                    print("rustup-init.exe already exists, skipping download.")
                
                # Make the file executable and run it
                self.make_executable(rustup_path)
                subprocess.run([rustup_path, "-y"], check=True)
            else:
                # Get and run the curl command for Unix systems
                curl_cmd = platform_settings.get('curl_cmd')
                if not curl_cmd:
                    raise Exception(f"curl_cmd not found in settings for {self.m_system_name}")
                subprocess.run(f'{curl_cmd} -y', shell=True, check=True)
        finally:
            # Restore original environment variables
            if orig_rustup_home:
                os.environ["RUSTUP_HOME"] = orig_rustup_home
            else:
                os.environ.pop("RUSTUP_HOME", None)
            
            if orig_cargo_home:
                os.environ["CARGO_HOME"] = orig_cargo_home
            else:
                os.environ.pop("CARGO_HOME", None)
        
        # Generate environment activation script
        self.generate_enviroment_set_batch_file(
            os.path.join(self.rust_workspace_path, "active"),
            set_env_list=[
                ("RUSTUP_HOME", rust_home),
                ("CARGO_HOME", cargo_home)
            ],
            prepend_env_list=[
                ("PATH", os.path.join(cargo_home, "bin"))
            ]
        )
        
        print("Rust installation completed successfully")

def main():
    dev_env_installer = WorkspaceInstaller()
    dev_env_installer.install_all()
    
if __name__ == "__main__":
    main()