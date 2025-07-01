import os
import shutil
from pathlib import Path
import subprocess
import platform
import json

class DevEnvInstaller:
    def __init__(self):
        # Get the directory where this script is located
        self.m_dev_env_root_path = Path(__file__).parent.absolute()
        self.m_settins_root_path = os.path.join(self.m_dev_env_root_path, "settings")
        self.m_workspace_root_path = os.path.join(self.m_dev_env_root_path, "workspace")
        self.system_name = platform.system()

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

    def install_all(self):
        self.install_conan()
        self.install_android_dev()

    def install_conan(self):
        # Create .conan directory 
        self.m_conan_setting_path = os.path.join(self.m_settins_root_path, "conan")
        self.m_conan_home_path = os.path.join(self.m_workspace_root_path, ".conan")
        self.m_generated_path = os.path.join(self.m_workspace_root_path, "_generated")

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
            
            # Windows build
            if self.system_name == "Windows":
                windows_output_path = os.path.join(self.m_generated_path, "conan", "builder", "windows")
                os.makedirs(windows_output_path, exist_ok=True)

                subprocess.run([
                    "conan", "install", os.path.join(self.m_conan_setting_path, "conanfile.txt"),
                    "--update",
                    "--generator", "CMakeToolchain",
                    "--generator", "VirtualBuildEnv",
                    "--output-folder", str(windows_output_path),
                    "--build", "never",
                    "--profile", os.path.join(self.m_conan_setting_path, "profiles", "builder", "conan_builder_profile.windows.txt")
                ], check=True)
            
            # Ubuntu build
            if self.system_name == "Linux":
                ubuntu_output_path = os.path.join(self.m_generated_path, "conan", "builder", "ubuntu")
                os.makedirs(ubuntu_output_path, exist_ok=True)
                subprocess.run([
                    "conan", "install", os.path.join(self.m_conan_setting_path, "conanfile.txt"),
                    "--update",
                    "--generator", "CMakeToolchain",
                    "--generator", "VirtualBuildEnv",
                    "--output-folder", str(ubuntu_output_path),
                    "--build", "never",
                    "--profile", os.path.join(self.m_conan_setting_path, "profiles", "builder", "conan_builder_profile.ubuntu.txt")
                ], check=True)

            # Macos build
            if self.system_name == "Darwin":
                macos_output_path = os.path.join(self.m_generated_path, "conan", "builder", "macos")
                os.makedirs(macos_output_path, exist_ok=True)
                subprocess.run([
                    "conan", "install", os.path.join(self.m_conan_setting_path, "conanfile.txt"),
                    "--update",
                    "--generator", "CMakeToolchain",
                    "--generator", "VirtualBuildEnv",
                    "--output-folder", str(macos_output_path),
                    "--build", "never",
                    "--profile", os.path.join(self.m_conan_setting_path, "profiles", "builder", "conan_builder_profile.macos.txt")
                ], check=True)
            
        except subprocess.CalledProcessError as e:
            print(f"Command failed with error: {e}")
            exit(1)

    def install_android_dev(self):
        # Set destination path (relative to current directory)
        self.m_android_dev_setting_path = os.path.join(self.m_settins_root_path, "android")
        self.m_android_dev_root_path = os.path.join(self.m_workspace_root_path, "android")

        if not os.path.exists(self.m_android_dev_root_path):
            # dig the android bootstrap package path
            self.m_android_sdk_bootstrap_root_path = self.get_conan_package_folder("android_sdk/bootstrap@arieo/dev:*")
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
            if self.system_name == "Windows":
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

    def get_conan_package_folder(self, conan_package):
        output = self.run_command(f'conan list "{conan_package}" --format=json')
        try:
            data = json.loads(output)
            packages = []
            
            # Navigate through the JSON structure based on the example
            local_cache = data.get("Local Cache", {})
            package_ref = local_cache.get("android_sdk/bootstrap@arieo/dev", {})
            revisions = package_ref.get("revisions", {})
            
            for revision_id, revision_data in revisions.items():
                for package_id, package_info in revision_data.get("packages", {}).items():
                    packages.append({
                        "id": package_id,
                        "revision": revision_id,
                        "settings": package_info.get("info", {}).get("settings", {})
                    })
            

            return self.run_command(f'conan cache path "android_sdk/bootstrap@arieo/dev:{packages[0]["id"]}"').strip()
            
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON output: {e}")
            raise
        except Exception as e:
            print(f"Unexpected error processing JSON: {e}")
            raise

def main():
    dev_env_installer = DevEnvInstaller()
    dev_env_installer.install_all()
    
if __name__ == "__main__":
    main()