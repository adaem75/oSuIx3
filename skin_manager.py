"""Import and load standard osu! skin assets."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pygame

from content_store import extract_archive


TEXTURE_NAMES = (
    "hitcircle", "hitcircleoverlay", "approachcircle", "sliderb0",
    "sliderfollowcircle", "spinner-circle", "spinner-approachcircle",
    "cursor", "cursortrail", *(f"default-{digit}" for digit in range(10)),
)

SOUND_PREFIXES = {
    "normal": ("normal-hitnormal", "soft-hitnormal", "drum-hitnormal"),
    "whistle": ("normal-hitwhistle", "soft-hitwhistle", "drum-hitwhistle"),
    "finish": ("normal-hitfinish", "soft-hitfinish", "drum-hitfinish"),
    "clap": ("normal-hitclap", "soft-hitclap", "drum-hitclap"),
    "combobreak": ("combobreak",),
    "sliderslide": ("sliderslide",),
    "spinnerspin": ("spinnerspin",),
    "spinnerbonus": ("spinnerbonus",),
}
AUDIO_EXTENSIONS = (".wav", ".ogg", ".mp3")


@dataclass
class Skin:
    name: str
    directory: Path | None = None
    combo_colors: list[tuple[int, int, int]] = field(default_factory=list)
    slider_border: tuple[int, int, int] | None = None
    slider_track_override: tuple[int, int, int] | None = None
    cursor_rotate: bool = True
    textures: dict[str, pygame.Surface] = field(default_factory=dict)
    sounds: dict[str, Path] = field(default_factory=dict)


def _color(value: str) -> tuple[int, int, int] | None:
    try:
        parts = [int(component.strip()) for component in value.split(",")[:3]]
        if len(parts) == 3:
            return tuple(max(0, min(255, component)) for component in parts)
    except ValueError:
        pass
    return None


class SkinManager:
    def __init__(self, skins_directory: str | Path) -> None:
        self.directory = Path(skins_directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def available(self) -> list[str]:
        return ["Default"] + sorted(path.name for path in self.directory.iterdir() if path.is_dir())

    def import_skin(self, archive_path: str | Path) -> str:
        destination = extract_archive(archive_path, self.directory)
        return destination.name

    def load(self, name: str) -> Skin:
        if name == "Default":
            return Skin("Default")
        directory = self.directory / name
        if not directory.is_dir():
            return Skin("Default")

        candidates = [directory, *(path for path in sorted(directory.rglob("*")) if path.is_dir())]
        asset_directory = next(
            (path for path in candidates
             if (path / "skin.ini").is_file()
             or any((path / f"{texture}.png").is_file()
                    or (path / f"{texture}@2x.png").is_file()
                    for texture in TEXTURE_NAMES)
             or any(any(path.glob(f"{prefix}*{extension}"))
                    for prefixes in SOUND_PREFIXES.values()
                    for prefix in prefixes
                    for extension in AUDIO_EXTENSIONS)),
            directory,
        )
        skin = Skin(name, asset_directory)
        config: dict[str, dict[str, str]] = {}
        section = ""
        ini = asset_directory / "skin.ini"
        if ini.is_file():
            for line in ini.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("//") or line.startswith(";"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    section = line[1:-1].lower()
                    config.setdefault(section, {})
                elif section and ":" in line:
                    key, value = line.split(":", 1)
                    config[section][key.strip().lower()] = value.strip()

        colors = config.get("colours", {})
        for index in range(1, 9):
            parsed = _color(colors.get(f"combo{index}", ""))
            if parsed:
                skin.combo_colors.append(parsed)
        skin.slider_border = _color(colors.get("sliderborder", ""))
        skin.slider_track_override = _color(colors.get("slidertrackoverride", ""))
        general = config.get("general", {})
        skin.cursor_rotate = general.get("cursorrotate", "1").lower() not in ("0", "false")

        for texture_name in TEXTURE_NAMES:
            hd_path = asset_directory / f"{texture_name}@2x.png"
            path = hd_path if hd_path.is_file() else asset_directory / f"{texture_name}.png"
            if not path.is_file():
                continue
            try:
                image = pygame.image.load(str(path)).convert_alpha()
                if path == hd_path:
                    width, height = image.get_size()
                    image = pygame.transform.smoothscale(image, (max(1, width // 2), max(1, height // 2)))
                skin.textures[texture_name] = image
            except pygame.error:
                continue

        for sound_name, prefixes in SOUND_PREFIXES.items():
            for prefix in prefixes:
                match = next((path for extension in AUDIO_EXTENSIONS
                              for path in sorted(asset_directory.glob(f"{prefix}*{extension}"))), None)
                if match:
                    skin.sounds[sound_name] = match
                    break
        return skin
