"""Build DeadlockRPC into exe."""

import subprocess
import sys

def main():
    sep = ";" if sys.platform == "win32" else ":"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        "--name", "DeadlockRPC",
        f"--add-data=src/config.json{sep}.",
        f"--add-data=src/favicon.ico{sep}.",
        "--icon=src/favicon.ico",
        "src/main.py",
    ]

    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print("\nDone! → dist/DeadlockRPC.exe")

if __name__ == "__main__":
    main()
