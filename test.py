import os
import subprocess
import platform

def main():
    os.environ["NEW_VAR"] = "test123"

    # Windows build
    if platform.system() == "Windows":
        subprocess.Popen(
            ["powershell.exe", "-NoExit", "-Command", " $env:NEW_VAR"],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
    # Ubuntu build
    elif platform.system() == "Linux":
        subprocess.Popen(
            ["bash", "--norc", "-i", "-c", "echo $NEW_VAR"],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )
    # Macos build
    elif platform.system() == "Darwin":
        subprocess.Popen(
            ["bash", "--norc", "-i", "-c", "echo $NEW_VAR"],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )

if __name__ == "__main__":
    main()

