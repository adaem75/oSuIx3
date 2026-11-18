"""Build the standalone desktop game with PyInstaller."""
from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.__main__ import run as pyinstaller_run


LOCAL_MODULES = (
    "audio_engine",
    "auto_bot",
    "beatmap_parser",
    "game_objects",
    "renderer",
)


def main() -> None:
    project_dir = Path(__file__).resolve().parent
    os.chdir(project_dir)

    options = [
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name=oSu!x3",
        "--paths=.",
        "--collect-all=pygame",
        "--collect-all=numpy",
        "--hidden-import=tkinter",
        "--hidden-import=tkinter.filedialog",
        *(f"--hidden-import={module}" for module in LOCAL_MODULES),
        "main.py",
    ]
    pyinstaller_run(options)


if __name__ == "__main__":
    main()
