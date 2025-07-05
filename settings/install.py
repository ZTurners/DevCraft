import os
import stat
import shutil
from pathlib import Path
import subprocess
import platform
import json
import configparser

class WorkspaceInstaller:
    def __init__(self):
        # Get the directory where this script is located
        self.m_dev_env_root_path = Path(__file__).parent.parent.absolute()
        self.m_settings_root_path = os.path.join(self.m_dev_env_root_path, "settings")
        self.m_workspace_root_path = os.path.join(self.m_dev_env_root_path, "workspace")
        self.m_system_name = platform.system()

        self.m_summary_data = []

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
                    f.write(f'set {var_name}={value}\n')
                
                if set_env_list and prepend_env_list:
                    f.write('\n')
                
                # Append commands
                for var_name, value in prepend_env_list:
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
        self.install_active_script()
        self.install_conan()
        self.install_android_dev()
        self.install_vs_code_setting()
        self.install_python()

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
            subprocess.run([
                "conan", "install", os.path.join(self.m_conan_setting_path, "conanfile.txt"),
                "--update",
                "--generator", "CMakeToolchain",
                "--generator", "VirtualBuildEnv",
                "--output-folder", str(conan_output_path),
                "--build", "never",
                "--profile", conan_profile_file
            ], check=True)
            
        except subprocess.CalledProcessError as e:
            print(f"Command failed with error: {e}")
            exit(1)

    def install_android_dev(self):
        # Set destination path (relative to current directory)
        self.m_android_dev_setting_path = os.path.join(self.m_settings_root_path, "android")
        self.m_android_dev_root_path = os.path.join(self.m_workspace_root_path, "android")

        if not os.path.exists(self.m_android_dev_root_path):
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
            os.makedirs(self.m_android_dev_root_path, exist_ok=True)

            # Copy files from source to destination
            print(f"Copying Android SDK files to {self.m_android_dev_root_path}")
            try:
                shutil.copytree(self.m_android_sdk_bootstrap_root_path, self.m_android_dev_root_path, dirs_exist_ok=True)
            except Exception as e:
                print(f"Error: Failed to copy files: {str(e)}")
                exit(1)

        # Install packages
        try:
            android_settings_file = os.path.join(self.m_android_dev_setting_path, "settings.json")
            if self.m_system_name == "Windows":
                sdkmanager_exe_path = os.path.join(self.m_android_dev_root_path, "AndroidSDK", "cmdline-tools", "bootstrap", "bin", "sdkmanager.bat")
            else:
                sdkmanager_exe_path = os.path.join(self.m_android_dev_root_path, "AndroidSDK", "cmdline-tools", "bootstrap", "bin", "sdkmanager")

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
            os.path.join(self.m_android_dev_root_path, "active"),
            set_env_list = [
                ('ANDROID_SDK_ROOT', self.m_android_dev_root_path)
            ],
            prepend_env_list = [
                ('PATH', os.path.join(self.m_android_dev_root_path, "AndroidSDK", "cmdline-tools", "bootstrap", "bin")),
                ('PATH', os.path.join(self.m_android_dev_root_path, "AndroidSDK", "platform-tools"))
            ]
        )

    def install_vs_code_setting(self):
        self.vs_code_init_user_setting_file_path = os.path.join(self.m_settings_root_path, "vscode", "init_user_settings.json")
        self.vs_code_workspace_setting_folder = os.path.join(self.m_workspace_root_path, "vscode", ".config", "User")

        # Create destination directory if it doesn't exist
        os.makedirs(self.vs_code_workspace_setting_folder, exist_ok=True)
        shutil.copyfile(self.vs_code_init_user_setting_file_path, os.path.join(self.vs_code_workspace_setting_folder, "settings.json"))

def main():
    dev_env_installer = WorkspaceInstaller()
    dev_env_installer.install_all()
    
if __name__ == "__main__":
    main()