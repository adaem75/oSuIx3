"""Persistent content folders and safe extraction for user-imported archives."""
from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
import re
import sys
import zipfile


def app_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(os.path.dirname(sys.executable)).resolve()
    return Path(".").resolve()


def persistent_directories() -> tuple[Path, Path]:
    songs = app_directory() / "Songs"
    skins = app_directory() / "Skins"
    songs.mkdir(parents=True, exist_ok=True)
    skins.mkdir(parents=True, exist_ok=True)
    return songs, skins


def _safe_folder_name(name: str) -> str:
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", Path(name).stem).strip(" .")
    return clean or "Imported"


def extract_archive(archive_path: str | Path, destination_root: str | Path) -> Path:
    archive_path = Path(archive_path)
    root = Path(destination_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    destination = (root / _safe_folder_name(archive_path.name)).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        for entry in archive.infolist():
            relative = PurePosixPath(entry.filename.replace("\\", "/"))
            if relative.is_absolute() or not relative.parts or any(part in ("..", "") for part in relative.parts):
                continue
            if ":" in relative.parts[0]:
                continue
            target = destination.joinpath(*relative.parts).resolve()
            if target != destination and destination not in target.parents:
                continue
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(entry))
    return destination
