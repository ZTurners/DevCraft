import os
import shutil
from pathlib import Path
import subprocess
import platform

class DevEnvInstaller:
    def __init__(self):
        # Get the directory where this script is located
        self.m_dev_env_root_path = Path(__file__).parent.absolute()
        self.m_settins_root_path = os.path.join(self.m_dev_env_root_path, "settings")
        self.m_workspace_root_path = os.path.join(self.m_dev_env_root_path, "workspace")
        self.system_name = platform.system()

        return

    def install_all(self):
        self.install_conan()

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


def main():
    dev_env_installer = DevEnvInstaller()
    dev_env_installer.install_all()
    
if __name__ == "__main__":
    main()