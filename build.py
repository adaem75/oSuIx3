"""Build a one-file desktop executable with PyInstaller."""
from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onefile", "--windowed", "--name", "PulseRhythm",
        "--collect-all", "pygame", "--collect-all", "numpy",
        "main.py",
    ]
    return subprocess.call(command, cwd=os.path.dirname(os.path.abspath(__file__)))


if __name__ == "__main__":
    raise SystemExit(main())
