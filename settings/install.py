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

    def _formalize_path(self, path):
        """Formalize a path by replacing workspace and settings variables."""
        if not isinstance(path, str):
            return path
        path = path.replace("${workspace}", self.m_workspace_root_path)
        path = path.replace("${settings}", self.m_settings_root_path)
        return path

    def _handle_download(self, download_config, context):
        """Handle download node."""
        # download_config is the child node data: { src: {url, auth_required} or src_url, dest }
        
        # Handle src as either nested object or flat src_url
        if "src" in download_config and isinstance(download_config["src"], dict):
            src_url = download_config["src"]["url"]
            need_auth = download_config["src"].get("auth_required", False)
        else:
            src_url = download_config.get("src_url", download_config.get("url", ""))
            need_auth = download_config.get("auth_required", False)
        
        downloaded_file = self._formalize_path(download_config["dest"])

        # Check if file already exists
        if os.path.exists(downloaded_file):
            file_size = os.path.getsize(downloaded_file)
            if file_size > 0:
                print(f"File already exists, skipping download: {downloaded_file}")
                return downloaded_file
            else:
                print(f"File exists but is empty, will re-download: {downloaded_file}")
                os.remove(downloaded_file)

        # Create directory for downloaded file
        os.makedirs(os.path.dirname(downloaded_file), exist_ok=True)

        # Download using curl with authentication
        print(f"Downloading... {src_url}")

        # Prepare curl command
        curl_cmd = [
            "curl",
            "--progress-bar",  # Show download progress
            "-L",  # Follow redirects
        ]

        # Add authentication if needed
        if need_auth:                    
            from urllib.parse import urlparse
            domain = urlparse(src_url).netloc
            print(f"\nDownloading from {domain}")
            
            username = input("Username: ")
            curl_cmd.extend(["--user", f"{username}"])  # Curl will prompt for password

        # Add output file specification
        curl_cmd.extend([
            "-o", downloaded_file,  # Output file
            "-f",  # Fail on HTTP errors
            "-S",  # Show error
            "--retry", "3",  # Retry up to 3 times
            "--retry-delay", "5",  # Wait 5 seconds between retries
            src_url
        ])
        subprocess.run(curl_cmd, check=True)
        
        # Verify the downloaded file
        if not os.path.exists(downloaded_file):
            raise Exception("Downloaded file does not exist")
        
        file_size = os.path.getsize(downloaded_file)
        if file_size == 0:
            raise Exception("Downloaded file is empty")
        print("\nDownload completed and verified.")
        
        return downloaded_file

    def _handle_unzip_source(self, unzip_config, context):
        """Handle unzip node."""
        # unzip_config is the child node data: { src, src_sub_folder, dest }
        
        downloaded_file = self._formalize_path(unzip_config["src"])
        target_folder = self._formalize_path(unzip_config["dest"])
        unzip_source = unzip_config.get("src_sub_folder", "")
        
        if not downloaded_file or not target_folder:
            return
        
        # Check if target folder already exists
        if os.path.exists(target_folder) and os.path.isdir(target_folder):
            # Check if folder has content
            if os.listdir(target_folder):
                print(f"Target folder already exists and has content, skipping extraction: {target_folder}")
                return
            else:
                print(f"Target folder exists but is empty, will extract: {target_folder}")
        
        # Check file extension to determine archive type
        is_zip = downloaded_file.lower().endswith('.zip')
        is_tar_gz = downloaded_file.lower().endswith('.tar.gz')
        is_tar_xz = downloaded_file.lower().endswith('.tar.xz')

        if not (is_zip or is_tar_gz or is_tar_xz):
            raise Exception("Unsupported archive format. Only .zip, .tar.gz, and .tar.xz are supported")

        # Verify archive integrity
        try:
            if is_zip:
                with zipfile.ZipFile(downloaded_file, 'r') as test_zip:
                    if test_zip.testzip() is not None:
                        raise Exception("ZIP file is corrupted")
            else:  # tar.gz or tar.xz
                mode = "r:gz" if is_tar_gz else "r:xz"
                with tarfile.open(downloaded_file, mode) as test_tar:
                    test_tar.getmembers()
        except (zipfile.BadZipFile, tarfile.TarError) as e:
            raise Exception(f"Invalid archive file: {str(e)}")

        print(f"\nExtracting files to {target_folder}...")
        
        if is_zip:
            with zipfile.ZipFile(downloaded_file, 'r') as zip_ref:
                # Get all members and filter by unzip_source if specified
                all_members = zip_ref.namelist()
                
                if unzip_source:
                    # Use unzip_source as the base directory
                    base_dir = unzip_source
                    # Ensure base_dir ends with / for proper prefix matching
                    if base_dir and not base_dir.endswith('/'):
                        base_dir_with_slash = base_dir + '/'
                    else:
                        base_dir_with_slash = base_dir
                    # Only extract files from the specified source folder
                    members = [m for m in all_members if m.startswith(base_dir_with_slash) or m == base_dir]
                    # Get the base directory to remove
                    base_dir_len = len(base_dir_with_slash)
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
                            # Read the file content
                            file_data = zip_ref.read(member)
                            final_path = os.path.join(target_folder, target_path)
                            
                            # Create parent directory if needed
                            os.makedirs(os.path.dirname(final_path), exist_ok=True)
                            
                            # Write the file directly to the target location
                            if not member.endswith('/'):
                                with open(final_path, 'wb') as f:
                                    f.write(file_data)
                    else:
                        zip_ref.extract(member, target_folder)
                    percent = (index * 100) // total
                    print(f"\rProgress: {percent}% [{index}/{total} files]", end="", flush=True)
        else:  # tar.gz or tar.xz
            mode = "r:gz" if is_tar_gz else "r:xz"
            with tarfile.open(downloaded_file, mode) as tar:
                # Get all members and filter by unzip_source if specified
                all_members = tar.getmembers()
                
                if unzip_source:
                    # Use unzip_source as the path filter
                    path_filter = unzip_source
                    # Only extract files from the specified path
                    members = [m for m in all_members if m.name.startswith(path_filter)]
                    # Remove the entire prefix
                    base_dir_len = len(unzip_source) + 1  # +1 for the slash
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

    def _handle_copy(self, copy_config, context):
        """Handle copy node."""
        # copy_config is the child node data: { src, dest }
        if not isinstance(copy_config, dict) or "src" not in copy_config or "dest" not in copy_config:
            return
        
        src_path = self._formalize_path(copy_config["src"])
        dest_path = self._formalize_path(copy_config["dest"])
        
        print(f"\nCopying files from {src_path} to {dest_path}...")
        
        if os.path.exists(src_path):
            # Create destination directory if it doesn't exist
            os.makedirs(dest_path, exist_ok=True)
            
            if os.path.isdir(src_path):
                # Copy directory contents
                try:
                    # Use copytree with dirs_exist_ok to allow overwriting
                    shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
                    print(f"Successfully copied directory contents")
                except Exception as e:
                    print(f"Error copying directory: {e}")
                    raise
            else:
                # Copy single file
                try:
                    dest_file = os.path.join(dest_path, os.path.basename(src_path))
                    shutil.copy2(src_path, dest_file)
                    print(f"Successfully copied file")
                except Exception as e:
                    print(f"Error copying file: {e}")
                    raise
        else:
            print(f"Warning: Source path not found: {src_path}")

    def _handle_make_execute_permission(self, permission_paths, context):
        """Handle make_execute_permission node."""
        # permission_paths is the child node data: array of paths
        if not isinstance(permission_paths, list):
            return
        
        print("\nSetting execute permissions...")
        for path_pattern in permission_paths:
            # Replace workspace variable
            path_pattern = self._formalize_path(path_pattern)
            
            if os.path.exists(path_pattern):
                # Check if it's a directory or file
                if os.path.isdir(path_pattern):
                    # Recursively set execute permissions for all files in the directory
                    for root, dirs, files in os.walk(path_pattern):
                        for filename in files:
                            file_path = os.path.join(root, filename)
                            try:
                                self.make_executable(file_path)
                            except Exception as e:
                                print(f"Warning: Could not set execute permission for {file_path}: {e}")
                    print(f"Set execute permissions for all files in: {path_pattern}")
                else:
                    # It's a single file
                    try:
                        self.make_executable(path_pattern)
                        print(f"Set execute permission for: {path_pattern}")
                    except Exception as e:
                        print(f"Warning: Could not set execute permission for {path_pattern}: {e}")
            else:
                print(f"Warning: Path not found for execute permissions: {path_pattern}")

    def _handle_environments(self, env_config, context):
        """Handle environments node."""
        
        print("\nSetting environment variables...")
        
        # Handle "set" environment variables
        if "set" in env_config and isinstance(env_config["set"], dict):
            for var_name, var_value in env_config["set"].items():
                # Replace variables in value
                var_value = self._formalize_path(var_value)
                # Set environment variable
                os.environ[var_name] = var_value
                print(f"  Set {var_name}={var_value}")
        
        # Handle "prepend" environment variables
        if "prepend" in env_config and isinstance(env_config["prepend"], list):
            for item_env in env_config["prepend"]:
                if isinstance(item_env, dict):
                    for var_name, var_value in item_env.items():
                        # Replace variables in value
                        var_value = self._formalize_path(var_value)
                        # Prepend to existing value
                        existing_value = os.environ.get(var_name, "")
                        if existing_value:
                            separator = ";" if self.m_system_name == "Windows" else ":"
                            os.environ[var_name] = f"{var_value}{separator}{existing_value}"
                        else:
                            os.environ[var_name] = var_value
                        print(f"  Prepended {var_name}={var_value}")

    def _handle_execute(self, command_config, context):
        """Handle execute node."""
        print("\nExecuting installation command...")
        
        # Handle new object format: { command: [...], target_folder: "..." }
        if isinstance(command_config, dict):
            cmd_list = command_config.get("command", [])
            cmd_target_folder = self._formalize_path(command_config.get("target_folder", ""))
            
            # Build command string from list, replacing variables
            command_parts = []
            for part in cmd_list:
                part = self._formalize_path(part)
                command_parts.append(part)
            
            command = " ".join(command_parts)
        # Handle old format: string or array
        elif isinstance(command_config, list):
            # If it's an array, join the parts with spaces
            command = " ".join(command_config)
            # Replace variables in the command
            command = self._formalize_path(command)
        elif isinstance(command_config, str):
            command = command_config
            # Replace variables in the command
            command = self._formalize_path(command)
        else:
            print("Warning: execute must be an object, string, or array")
            command = ""
        
        if command:
            # Execute the command
            try:
                print(f"Running command: {command}")
                subprocess.run(command, shell=True, check=True)
                print("Command executed successfully.")
            except subprocess.CalledProcessError as e:
                print(f"Error executing command: {e}")
                raise

    def _handle_generator_active_batch(self, generator_active_batch, context):
        """Handle generator_active_batch node."""
        # generator_active_batch is the child node data: { file_path, environments }
        if "file_path" not in generator_active_batch or "environments" not in generator_active_batch:
            return
        
        # Process file path, replacing {workspace} with actual path
        file_path = self._formalize_path(generator_active_batch["file_path"])
        
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        # Prepare environment lists
        set_env_list = []
        prepend_env_list = []
        
        # Process set
        if "set" in generator_active_batch["environments"]:
            for var, value in generator_active_batch["environments"]["set"].items():
                # Replace workspace variable
                value = self._formalize_path(value)
                set_env_list.append((var, value))
        
        # Process prepend
        if "prepend" in generator_active_batch["environments"]:
            for item in generator_active_batch["environments"]["prepend"]:
                # Each item is a dictionary with a single key-value pair
                for var, value in item.items():
                    # Replace workspace variable
                    value = self._formalize_path(value)
                    prepend_env_list.append((var, value))
        
        # Generate the batch file
        self.generate_enviroment_set_batch_file(file_path, set_env_list, prepend_env_list)

    def _handle_install(self, install_node, context):
        
        # Define node handlers mapping (with context requirements)
        node_handlers = {
            'download': self._handle_download,
            'unzip': self._handle_unzip_source,
            'copy': self._handle_copy,
            'make_execute_permission': self._handle_make_execute_permission,
            'environments': self._handle_environments,
            'execute': self._handle_execute,
        }
        
        # install_node is now a dictionary where keys are install item names
        # Iterate over each install item
        for install_item_name, install_item in install_node.items():
            print(f"\n{'='*60}")
            print(f"Processing install item: '{install_item_name}'")
            print(f"{'='*60}")
            
            # Process nodes in order for this install item
            for node_name, handler in node_handlers.items():
                if node_name in install_item:
                    try:
                        print(f"\nProcessing '{node_name}' node for '{install_item_name}'...")
                        handler(install_item[node_name], context)
                    except Exception as e:
                        # Re-raise with context
                        raise Exception(f"Error processing '{node_name}' node for '{install_item_name}': {e}") from e

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

        context = {
            'config': config
        }

        # Define config-level node handlers mapping
        config_handlers = {
            'install': self._handle_install,
            'generator_active_batch': self._handle_generator_active_batch,
        }
        
        # Process config nodes in order
        for node_name, handler in config_handlers.items():
            if node_name in config:
                try:
                    print(f"\nProcessing '{node_name}' configuration...")
                    handler(config[node_name], context)
                except Exception as e:
                    print(f"Error processing '{node_name}' configuration: {e}")
                    exit(1)

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

    def install_android_sdk(self):
        """Install Android by downloading and extracting from configured URLs."""
        if self.m_system_name == "Windows":
            android_config_path = os.path.join(self.m_settings_root_path, "android", "android_sdk_config.windows.json")
        elif self.m_system_name == "Linux":
            android_config_path = os.path.join(self.m_settings_root_path, "android", "android_sdk_config.linux.json")
        elif self.m_system_name == "Darwin":
            android_config_path = os.path.join(self.m_settings_root_path, "android", "android_sdk_config.macos.json")
        self.install_from_config(android_config_path)

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

        # Map system names to settings subdirectory paths
        system_name_map = {
            "Windows": os.path.join(self.m_settings_root_path, "windows"),
            "Linux": os.path.join(self.m_settings_root_path, "linux"),
            "Darwin": os.path.join(self.m_settings_root_path, "macos")
        }
        
        # Get the path for current system
        system_settings_path = system_name_map.get(self.m_system_name)
        if not system_settings_path:
            print(f"Error: Unsupported system: {self.m_system_name}")
            return
        
        # Check if the system settings path exists
        if not os.path.exists(system_settings_path):
            print(f"Warning: Settings path not found: {system_settings_path}")
            return
        
        # Get all JSON files in the system-specific settings folder
        config_files = [f for f in os.listdir(system_settings_path) 
                       if f.endswith('.json') and os.path.isfile(os.path.join(system_settings_path, f))]
        
        # Process each config file
        for config_file in sorted(config_files):
            config_path = os.path.join(system_settings_path, config_file)
            print(f"\n{'='*70}")
            print(f"Processing config: {config_file}")
            print(f"{'='*70}")
            self.install_from_config(config_path)


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
        """Install Python by downloading and extracting from configured URLs."""
        if self.m_system_name == "Windows":
            python_config_path = os.path.join(self.m_settings_root_path, "python", "python_config.windows.json")
        elif self.m_system_name == "Linux":
            python_config_path = os.path.join(self.m_settings_root_path, "python", "python_config.linux.json")
        elif self.m_system_name == "Darwin":
            python_config_path = os.path.join(self.m_settings_root_path, "python", "python_config.macos.json")
        self.install_from_config(python_config_path)       

    def install_conan(self):
        """Install Conan by downloading and extracting from configured URLs."""
        if self.m_system_name == "Windows":
            conan_config_path = os.path.join(self.m_settings_root_path, "conan", "conan_config.windows.json")
        elif self.m_system_name == "Linux":
            conan_config_path = os.path.join(self.m_settings_root_path, "conan", "conan_config.linux.json")
        elif self.m_system_name == "Darwin":
            conan_config_path = os.path.join(self.m_settings_root_path, "conan", "conan_config.macos.json")
        self.install_from_config(conan_config_path)

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