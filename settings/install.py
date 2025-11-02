import os
import stat
import shutil
from pathlib import Path
import subprocess
import platform
import json
import hashlib
try:
    import yaml
except Exception:
    yaml = None
import configparser
import urllib.request
import datetime
import time
import zipfile
import tarfile
import copy

class WorkspaceInstaller:
    def __init__(self):
        # Get the directory where this script is located
        self.m_dev_env_root_path = Path(__file__).parent.parent.absolute()
        self.m_settings_root_path = os.path.join(self.m_dev_env_root_path, "settings")
        self.m_workspace_root_path = os.path.join(self.m_dev_env_root_path, "workspace")
        self.m_download_root_path = os.path.join(self.m_dev_env_root_path, ".downloads")
        self.m_system_name = platform.system()
        self.m_env_vs_path = None
        self.m_summary_data = []
        # Ensure YAML config equivalents exist for JSON configs under settings/
        try:
            self._ensure_yaml_configs()
        except Exception as e:
            # Do not fail initialization if conversion fails; warn instead
            print(f"Warning: failed to ensure YAML configs: {e}")

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
        if not isinstance(path, str) or path == "":
            return path
        path = path.replace("${workspace}", self.m_workspace_root_path)
        path = path.replace("${settings}", self.m_settings_root_path)
        path = path.replace("${download}", self.m_download_root_path)
        path = os.path.normpath(path)
        
        return path

    def _dump_to_yaml_str(self, data, indent=0):
        """Lightweight YAML dumper for basic Python structures (dict, list, primitives).
        Used as a fallback when PyYAML is not available.
        This produces human-readable YAML (no anchors, tags).
        """
        sp = '  ' * indent
        if data is None:
            return 'null\n'
        if isinstance(data, bool):
            return ("true\n" if data else "false\n")
        if isinstance(data, (int, float)):
            return f"{data}\n"
        if isinstance(data, str):
            # Quote strings that start with special characters or contain newlines
            if '\n' in data or data.strip() == '' or data[0] in ('@', '&', '*', '>', '|', '%', ':', '-', '?', '{', '}', '[', ']', ','):
                return '"' + data.replace('"', '\\"') + '"\n'
            return f"{data}\n"
        if isinstance(data, list):
            if not data:
                return '[]\n'
            out = ''
            for item in data:
                if isinstance(item, (dict, list)):
                    out += f"{sp}- {self._dump_to_yaml_str(item, indent+1).lstrip()}"
                else:
                    out += f"{sp}- {self._dump_to_yaml_str(item, 0)}"
            return out
        if isinstance(data, dict):
            if not data:
                return '{}\n'
            out = ''
            for k, v in data.items():
                # ensure key is plain string
                out += f"{sp}{k}: "
                if isinstance(v, (dict, list)):
                    out += '\n' + self._dump_to_yaml_str(v, indent+1)
                else:
                    out += self._dump_to_yaml_str(v, 0)
            return out
        # Fallback to JSON representation
        return json.dumps(data) + '\n'

    def _ensure_yaml_configs(self):
        """Walk the settings folder and create .yaml equivalents for any .json config files.
        Keeps the original .json files as backups.
        If PyYAML is available, it will be used for dumping; otherwise uses a lightweight dumper.
        """
        settings_root = self.m_settings_root_path
        if not os.path.isdir(settings_root):
            return

        for root, dirs, files in os.walk(settings_root):
            for fname in files:
                if not fname.lower().endswith('.json'):
                    continue

                json_path = os.path.join(root, fname)
                yaml_fname = fname[:-5] + '.yaml'
                yaml_path = os.path.join(root, yaml_fname)

                # Skip if YAML already exists
                if os.path.exists(yaml_path):
                    continue

                try:
                    with open(json_path, 'r', encoding='utf-8') as jf:
                        data = json.load(jf)
                except Exception as e:
                    print(f"Warning: failed to parse JSON {json_path}: {e}")
                    continue

                try:
                    if yaml is not None:
                        # Use PyYAML if available
                        yaml_text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
                    else:
                        yaml_text = self._dump_to_yaml_str(data)

                    # Create YAML file
                    with open(yaml_path, 'w', encoding='utf-8') as yf:
                        yf.write(yaml_text)
                    print(f"Created YAML config: {yaml_path}")
                except Exception as e:
                    print(f"Warning: failed to write YAML for {json_path}: {e}")

    def _process_download(self, download_config, context):
        """Handle download node."""
        # download_config is the child node data: { src: {url, auth_required} or src_url, dest }
        
        # Handle src as either nested object or flat src_url
        if "src" in download_config and isinstance(download_config["src"], dict):
            src_url = download_config["src"]["url"]
            need_auth = download_config["src"].get("auth_required", False)
            expected_hash = download_config["src"].get("SHA-256", None)
        
        downloading_file = self._formalize_path(download_config["dest"]) + ".downloading"
        downloaded_file = self._formalize_path(download_config["dest"])

        # Check if file already exists
        if os.path.exists(downloaded_file):
            file_size = os.path.getsize(downloaded_file)
            if file_size > 0:
                print(f"File already exists, skipping download: {downloaded_file}")
                return
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
            "-o", downloading_file,  # Output file
            "-C", "-",  # Resume download
            "-S",  # Show error
            "--retry", "3",  # Retry up to 3 times
            "--retry-delay", "5",  # Wait 5 seconds between retries
            src_url
        ])

        # Check size of the file when no SHA-256 provided.
        # Attempt to determine expected size via HTTP HEAD Content-Length header.
        expected_size = None
        try:
            req = urllib.request.Request(src_url, method='HEAD')
            with urllib.request.urlopen(req, timeout=10) as resp:
                cl = resp.getheader('Content-Length') or resp.getheader('content-length')
                if cl:
                    expected_size = int(cl)
        except Exception as e:
            print(f"Warning: could not determine remote Content-Length: {e}")

        # Execute curl and check result. Retry up to 3 times on failure.
        max_attempts = 10
        attempt = 1
        last_err = None
        while attempt < max_attempts:
            result = subprocess.run(curl_cmd, text=True, check=True)
            if result.returncode == 0:
                # success
                print("Download command succeeded")

                # get file_size from downloading file
                file_size = os.path.getsize(downloading_file)
                if file_size == expected_size:
                    last_err = None
                    break
                else:
                    last_err = f"Downloaded file size {file_size} does not match expected size {expected_size}"
            else:
                # failed attempt: do not remove partial file; allow curl -C - to resume
                last_err = result.stderr.strip() or result.stdout.strip()
            
            print(f"Download attempt {attempt} failed: {last_err}")

            if attempt < max_attempts:
                print("Retrying download...")
                time.sleep(2)
            attempt += 1
            print(f"Running download attempt {attempt}/{max_attempts}...")

        if last_err:
            raise Exception(f"Download command failed after {max_attempts} attempts: {last_err}")

        
        # Verify the downloaded file
        if not os.path.exists(downloading_file):
            raise Exception("Downloaded file does not exist")
        
        file_size = os.path.getsize(downloading_file)
        if file_size == 0:
            raise Exception("Downloaded file is empty")

        if not expected_hash:
            print("No SHA-256 checksum provided, skipping verification.")

        # If a SHA-256 checksum is provided in the config, verify it now.
        if expected_hash:
            expected_hash = expected_hash.strip().lower()
            print(f"Verifying SHA-256 checksum for {downloading_file}...")
            sha256 = hashlib.sha256()
            with open(downloading_file, 'rb') as fh:
                for chunk in iter(lambda: fh.read(8192), b''):
                    sha256.update(chunk)
            actual_hash = sha256.hexdigest().lower()
            if actual_hash != expected_hash:
                # remove the corrupt download
                try:
                    os.remove(downloading_file)
                except Exception:
                    pass
                raise Exception(f"SHA-256 mismatch: expected {expected_hash}, got {actual_hash}")
            else:
                print("SHA-256 verification passed")

        
        # Rename the downloading file to final name
        os.rename(downloading_file, downloaded_file)

        print("\nDownload completed and verified.")

    def _process_unzip_source(self, unzip_config, context):
        """Handle unzip node."""
        # unzip_config is the child node data: { src, src_sub_folder, dest }
        
        src_zip_file = self._formalize_path(unzip_config["src"])
        dest_folder = self._formalize_path(unzip_config["dest"])
        unzip_source = unzip_config.get("src_sub_folder", "")

        if not src_zip_file:
            raise Exception("No source file specified for unzip")
        
        # Check if target folder already exists
        if os.path.exists(dest_folder) and os.path.isdir(dest_folder):
            # Check if folder has content
            if os.listdir(dest_folder):
                print(f"Target folder already exists and has content, skipping extraction: {dest_folder}")
                return
            else:
                print(f"Target folder exists but is empty, will extract: {dest_folder}")
        
        # Check file extension to determine archive type
        is_zip = src_zip_file.lower().endswith('.zip')
        is_tar_gz = src_zip_file.lower().endswith('.tar.gz')
        is_tar_xz = src_zip_file.lower().endswith('.tar.xz')

        if not (is_zip or is_tar_gz or is_tar_xz):
            raise Exception("Unsupported archive format. Only .zip, .tar.gz, and .tar.xz are supported")

        # Verify archive integrity
        try:
            if is_zip:
                with zipfile.ZipFile(src_zip_file, 'r') as test_zip:
                    if test_zip.testzip() is not None:
                        raise Exception("ZIP file is corrupted")
            else:  # tar.gz or tar.xz
                mode = "r:gz" if is_tar_gz else "r:xz"
                with tarfile.open(src_zip_file, mode) as test_tar:
                    test_tar.getmembers()
        except (zipfile.BadZipFile, tarfile.TarError) as e:
            raise Exception(f"Invalid archive file: {str(e)}")

        print(f"\nExtracting files to {dest_folder}...")
        
        if is_zip:
            with zipfile.ZipFile(src_zip_file, 'r') as zip_ref:
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
                            final_path = os.path.join(dest_folder, target_path)
                            
                            # Create parent directory if needed
                            os.makedirs(os.path.dirname(final_path), exist_ok=True)
                            
                            # Write the file directly to the target location
                            if not member.endswith('/'):
                                with open(final_path, 'wb') as f:
                                    f.write(file_data)
                    else:
                        zip_ref.extract(member, dest_folder)
                    percent = (index * 100) // total
                    print(f"\rProgress: {percent}% [{index}/{total} files]", end="", flush=True)
        else:  # tar.gz or tar.xz
            mode = "r:gz" if is_tar_gz else "r:xz"
            with tarfile.open(src_zip_file, mode) as tar:
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
                                tar.extract(new_member, dest_folder)
                    else:
                        tar.extract(member, dest_folder)
                    percent = (index * 100) // total
                    print(f"\rProgress: {percent}% [{index}/{total} files]", end="", flush=True)
        print("\nExtraction completed.")

    def _process_copy(self, copy_config, context):
        """Handle copy node."""
        # copy_config is the child node data: { src, dest }
        if not isinstance(copy_config, dict) or "src" not in copy_config or "dest" not in copy_config:
            return
        
        src_path = self._formalize_path(copy_config["src"])
        dest_path = self._formalize_path(copy_config["dest"])
        
        print(f"\nCopying files from {src_path} to {dest_path}...")
        
        if os.path.exists(src_path):
            
            if os.path.isdir(src_path):
                # Copy directory contents
                try:
                    # Create destination directory if it doesn't exist
                    os.makedirs(dest_path, exist_ok=True)
                    # Use copytree with dirs_exist_ok to allow overwriting
                    shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
                    print(f"Successfully copied directory contents")
                except Exception as e:
                    print(f"Error copying directory: {e}")
                    raise
            else:
                # Copy single file
                try:
                    dest_file = dest_path
                    # create parent folder if not exists
                    os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                    shutil.copy2(src_path, dest_file)
                    print(f"Successfully copied file")
                except Exception as e:
                    print(f"Error copying file: {e}")
                    raise
        else:
            print(f"Warning: Source path not found: {src_path}")

    def _process_make_execute_permission(self, permission_config, context):
        """Handle make_execute_permission node."""
        # New expected form in YAML:
        # make_execute_permission:
        #   files:
        #     - ${workspace}/path/to/file_or_dir
        # The code keeps backward compatibility with the old form which was a simple
        # list of paths. Supports a single string, a list of strings, or a dict with
        # a 'files' key containing the list.

        # Normalize input into a list of path strings
        paths = []
        if isinstance(permission_config, dict):
            # look for 'files' key
            files_val = permission_config.get('files')
            if isinstance(files_val, list):
                paths = files_val
            else:
                # Nothing sensible to do
                raise TypeError("make_execute_permission 'files' key must be a list")
        else:
            raise TypeError("make_execute_permission must be a dict with 'files' key")

        print("\nSetting execute permissions...")
        for path_pattern in paths:
            # Replace workspace/settings/download variables
            path_pattern = self._formalize_path(path_pattern)

            if not path_pattern:
                continue

            if os.path.exists(path_pattern):
                # If it's a directory, walk it and set execute on files
                if os.path.isdir(path_pattern):
                    for root, dirs, files in os.walk(path_pattern):
                        # Ensure directories themselves are executable (useful for searching)
                        try:
                            self.make_executable(root)
                        except Exception:
                            pass
                        for filename in files:
                            file_path = os.path.join(root, filename)
                            try:
                                self.make_executable(file_path)
                            except Exception as e:
                                print(f"Warning: Could not set execute permission for {file_path}: {e}")
                    print(f"Set execute permissions for all files in: {path_pattern}")
                else:
                    # Single file: make it executable
                    try:
                        self.make_executable(path_pattern)
                        print(f"Set execute permission for: {path_pattern}")
                    except Exception as e:
                        print(f"Warning: Could not set execute permission for {path_pattern}: {e}")
            else:
                print(f"Warning: Path not found for execute permissions: {path_pattern}")

    def _process_environments(self, env_config, context):
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

    def _process_execute(self, command_config, context):
        """Handle execute node."""
        print("\nExecuting installation command...")
        
        # Handle new object format: { command: [...], dest: "..." }
        if isinstance(command_config, dict):
            cmd_list = command_config.get("command", [])
            
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

    def _process_generator_active_batch(self, generator_active_batch, context):
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

    def _process_change_file_content(self, change_config, context):
        """Handle change_file_content node.

        Supported formats:
        - insert: insert a new line at 1-based line number
        - change: replace an existing line at 1-based line number (extend file if needed)

        Example:
        {
          "file_path": "${workspace}/path/to/file",
          "change": [ { "line": 55, "content": "..." } ],
          "insert": [ { "line": 60, "content": "..." } ]
        }

        Behavior:
        - Creates parent directory if missing.
        - If file doesn't exist, creates an empty file.
        - Applies 'change' operations first (replace), then 'insert' operations.
        - Line numbers are 1-based.
        """
        if not isinstance(change_config, dict):
            return

        file_path = change_config.get("file_path")
        inserts = change_config.get("insert", [])
        changes = change_config.get("change", [])

        if not file_path:
            print("Warning: change_file_content missing 'file_path'")
            return

        file_path = self._formalize_path(file_path)

        # Ensure parent directories exist
        parent = os.path.dirname(file_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        # Read existing lines (or start empty)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        else:
            lines = []

        def _ensure_nl(s: str) -> str:
            return s if s.endswith('\n') else s + '\n'

        # Normalize and apply changes (replace specific lines)
        normalized_changes = []
        for item in changes:
            if not isinstance(item, dict):
                continue
            line_no = item.get('line')
            content = item.get('content', '')
            try:
                line_no = int(line_no)
            except Exception:
                continue
            # Expand variables in content
            content = self._formalize_path(content).replace('\\', '/')
            normalized_changes.append((line_no, content))

        normalized_changes.sort(key=lambda x: x[0])

        for line_no, content in normalized_changes:
            idx = max(0, line_no - 1)
            # If index beyond current length, extend with blank lines up to idx
            if idx >= len(lines):
                lines.extend(['\n'] * (idx - len(lines) + 1))

            # Replace the line at idx
            lines[idx] = _ensure_nl(self._formalize_path(content).replace('\\', '/'))

        # Normalize inserts: ensure list of dicts with line(int) and content(str)
        normalized_inserts = []
        for item in inserts:
            if not isinstance(item, dict):
                continue
            line_no = item.get('line')
            content = item.get('content', '')
            try:
                line_no = int(line_no)
            except Exception:
                continue
            # store as 1-based line numbers
            normalized_inserts.append((line_no, content))

        # Sort by line number ascending so earlier inserts don't offset later ones unexpectedly
        normalized_inserts.sort(key=lambda x: x[0])

        # Apply inserts with offset tracking
        offset = 0
        for line_no, content in normalized_inserts:
            idx = max(0, line_no - 1) + offset
            # If index beyond current length, extend with empty lines
            if idx > len(lines):
                lines.extend(['\n'] * (idx - len(lines)))

            lines.insert(idx, _ensure_nl(self._formalize_path(content).replace('\\', '/')))
            offset += 1

        # Write back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)

        print(f"Modified file: {file_path}")

    def _process_install(self, install_node, context):
        # Define node handlers mapping (with context requirements)
        node_handlers = {
            'download': self._process_download,
            'unzip': self._process_unzip_source,
            'copy': self._process_copy,
            'make_execute_permission': self._process_make_execute_permission,
            'change_file_content': self._process_change_file_content,
            'environments': self._process_environments,
            'execute': self._process_execute,
        }

        # Normalize install_node to an iterable list of (name, item) pairs.
        install_steps = []
        if isinstance(install_node, list):
            # new format: list of single-key mappings or multi-key mappings
            for entry in install_node:
                if not isinstance(entry, dict):
                    raise TypeError("each install entry must be an object")
                # multiple keys: treat each as its own install item
                for k, v in entry.items():
                    install_steps.append((k, v))
        else:
            raise TypeError("install node must be an object or an array")

        # Iterate over each install item
        for install_step_name, install_step in install_steps:
            # print(f"\n{'='*60}")
            print(f"Processing install item: '{install_step_name}'")
            # print(f"{'='*60}")

            # Ensure install_item is a mapping
            if not isinstance(install_step, dict):
                raise TypeError(f"install item '{install_step_name}' must be an object")

            # Process nodes in order for this install item
            if node_handlers[install_step_name]:
                # Special case: if the install_item_name matches a handler, process it directly
                try:
                    print(f"\nProcessing '{install_step_name}'...")
                    force_update = install_step.get("force_update", False)
                    dest_path = install_step.get("dest", None)
                    if dest_path:
                        dest_path = self._formalize_path(dest_path)
                        if os.path.exists(dest_path) and not force_update:
                            print(f"Destination already exists: {dest_path}")
                            print(f"Skipping install step: '{install_step_name}'")
                            continue
                    node_handlers[install_step_name](install_step, context)
                except Exception as e:
                    raise Exception(f"Error processing '{install_step_name}': {e}") from e
                continue
            else:
                raise Exception(f"Unknown install item name: '{install_step_name}'")

    def install_from_config(self, config_file_path):
        """Generic installation function that handles downloading and extracting from configured URLs.
        Args:
            config_file_path (str): Path to the configuration JSON file
        """
        if not os.path.exists(config_file_path):
            print(f"Error: Configuration not found at {config_file_path}")
            exit(1)

        # Attempt to load YAML if file is YAML (and PyYAML is available),
        # otherwise fall back to JSON. If YAML file exists but PyYAML is not
        # available, fall back to the original .json file with same basename.
        config = None
        lower = config_file_path.lower()
        try:
            if lower.endswith('.yaml') or lower.endswith('.yml'):
                if yaml is not None:
                    with open(config_file_path, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                else:
                    # PyYAML not available: try to read original JSON backup in same folder
                    json_candidate = config_file_path[:-5] + '.json' if lower.endswith('.yaml') else config_file_path[:-4] + '.json'
                    if os.path.exists(json_candidate):
                        with open(json_candidate, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                    else:
                        # If not found, check the archived json_backup folder under settings/
                        try:
                            rel = os.path.relpath(config_file_path, self.m_settings_root_path)
                        except Exception:
                            rel = os.path.basename(config_file_path)
                        # replace extension with .json
                        if rel.lower().endswith('.yaml'):
                            rel_json = rel[:-5] + '.json'
                        elif rel.lower().endswith('.yml'):
                            rel_json = rel[:-4] + '.json'
                        else:
                            rel_json = rel + '.json'

                        backup_candidate = os.path.join(self.m_settings_root_path, 'json_backup', rel_json)
                        if os.path.exists(backup_candidate):
                            with open(backup_candidate, 'r', encoding='utf-8') as f:
                                config = json.load(f)
                        else:
                            print(f"Error: YAML config provided but PyYAML is not installed and no JSON backup found: {config_file_path}")
                            print(f"Searched for: {json_candidate} and archive: {backup_candidate}")
                            print("Install PyYAML (python -m pip install pyyaml) or restore JSON backups to the original location.")
                            exit(1)
            else:
                # Default: JSON
                with open(config_file_path, 'r', encoding='utf-8') as f:
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
            'install': self._process_install,
            'generator_active_batch': self._process_generator_active_batch,
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
                    value = self._formalize_path(value)
                    f.write(f'set {var_name}={value}\n')
                
                if set_env_list and prepend_env_list:
                    f.write('\n')
                
                # Append commands
                for var_name, value in prepend_env_list:
                    value = self._formalize_path(value)
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
                    value = self._formalize_path(value)
                    f.write(f'export {var_name}="{value}"\n')
                
                if set_env_list and prepend_env_list:
                    f.write('\n')
                
                # Write append commands
                for var_name, value in prepend_env_list:
                    value = self._formalize_path(value)
                    f.write(f'export {var_name}="{value}:${var_name}"\n')
                
                f.write('\necho "Environment variables set successfully"\n')
        
        # Make the script executable
        import os
        os.chmod(output_file, 0o755)
        print(f"Bash script generated at: {output_file}")


    def install_all(self):
        # On Windows, detect VS first so environment can be used by installs
        if self.m_system_name == "Windows":
            vs_info = self.detect_visual_studio()
            if vs_info:
                self.m_env_vs_path, self.m_env_vs_version = vs_info

        # Determine the filename suffix for this platform's config files.
        suffix_map = {
            "Windows": ".windows.yaml",
            "Linux": ".linux.yaml",
            "Darwin": ".macos.yaml",
        }

        suffix = suffix_map.get(self.m_system_name)
        if not suffix:
            print(f"Error: Unsupported system: {self.m_system_name}")
            return

        # Search only second-level folders under settings/ (e.g. settings/jdk/, settings/rustup/)
        config_files = []
        try:
            for entry in sorted(os.listdir(self.m_settings_root_path)):
                entry_path = os.path.join(self.m_settings_root_path, entry)
                if not os.path.isdir(entry_path):
                    # Only consider directories directly under settings/
                    continue

                # List files in this subdirectory (do NOT recurse deeper)
                for fname in sorted(os.listdir(entry_path)):
                    if fname.endswith(suffix):
                        config_files.append(os.path.join(entry_path, fname))
        except FileNotFoundError:
            print(f"Warning: Settings directory not found: {self.m_settings_root_path}")
            return

        if not config_files:
            print(f"Warning: No configuration files found for system '{self.m_system_name}' in {self.m_settings_root_path}")
            return

        # Process each config file found (sorted for deterministic order)
        for config_path in sorted(config_files):
            # Friendly display: show path relative to settings folder
            try:
                display_name = os.path.relpath(config_path, self.m_settings_root_path)
            except Exception:
                display_name = os.path.basename(config_path)

            print(f"\n{'='*70}")
            print(f"Processing config: {display_name}")
            print(f"{'='*70}")
            self.install_from_config(config_path)

def main():
    dev_env_installer = WorkspaceInstaller()
    dev_env_installer.install_all()
    
if __name__ == "__main__":
    main()