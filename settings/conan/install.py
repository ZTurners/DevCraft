import os
import shutil
from pathlib import Path
import subprocess

def main():
    # Get the directory where this script is located
    dev_env_conan_root_path = Path(__file__).parent.absolute()
    
    # Set environment variables
    os.environ["CONAN_HOME"] = str(dev_env_conan_root_path / ".conan")
    os.environ["CONAN_USE_ALWAYS_SHORT_PATHS"] = "1"
    
    # Create .conan directory and copy config files
    conan_home = Path(os.environ["CONAN_HOME"])
    conan_home.mkdir(exist_ok=True)
    
    config_files = ["global.conf", "settings.yml", "remotes.json"]
    for file in config_files:
        src = dev_env_conan_root_path / file
        dst = conan_home / file
        if src.exists():
            shutil.copy2(src, dst)
    
    # Run conan commands
    try:
        # Detect profile
        subprocess.run(["conan", "profile", "detect", "--force"], check=True)
        
        # Windows build
        windows_output = dev_env_conan_root_path / "_generated" / "builder" / "windows"
        windows_output.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "conan", "install", str(dev_env_conan_root_path / "conanfile.txt"),
            "--update",
            "--generator", "CMakeToolchain",
            "--generator", "VirtualBuildEnv",
            "--output-folder", str(windows_output),
            "--build", "never",
            "--profile", str(dev_env_conan_root_path / "profiles" / "builder" / "conan_builder_profile.windows.txt")
        ], check=True)
        
        # Ubuntu build
        ubuntu_output = dev_env_conan_root_path / "_generated" / "builder" / "ubuntu"
        ubuntu_output.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            "conan", "install", str(dev_env_conan_root_path / "conanfile.txt"),
            "--update",
            "--generator", "CMakeToolchain",
            "--generator", "VirtualBuildEnv",
            "--output-folder", str(ubuntu_output),
            "--build", "never",
            "--profile", str(dev_env_conan_root_path / "profiles" / "builder" / "conan_builder_profile.ubuntu.txt")
        ], check=True)
        
    except subprocess.CalledProcessError as e:
        print(f"Command failed with error: {e}")
        exit(1)

if __name__ == "__main__":
    main()