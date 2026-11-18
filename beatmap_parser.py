"""Small osu!standard beatmap reader and curve helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
import zipfile


@dataclass
class HitObject:
    x: float
    y: float
    time: float
    kind: str
    combo: int = 1
    sound: int = 0
    end_time: float = 0.0
    curve: list[tuple[float, float]] = field(default_factory=list)
    repeats: int = 1


@dataclass
class Beatmap:
    title: str
    artist: str
    creator: str
    version: str
    audio_filename: str
    approach_rate: float
    overall_difficulty: float
    hp_drain: float
    circle_size: float
    slider_multiplier: float
    beat_length: float
    objects: list[HitObject]
    source: Path | None = None


def _bezier(points: list[tuple[float, float]], steps: int = 30) -> list[tuple[float, float]]:
    result = []
    degree = len(points) - 1
    for i in range(steps + 1):
        t = i / steps
        x = y = 0.0
        for j, (px, py) in enumerate(points):
            weight = math.comb(degree, j) * (1 - t) ** (degree - j) * t**j
            x += px * weight
            y += py * weight
        result.append((x, y))
    return result


def _curve_path(x: float, y: float, raw: str, pixel_length: float) -> list[tuple[float, float]]:
    fields = raw.split("|")
    kind = fields[0]
    points = [(x, y)]
    for part in fields[1:]:
        try:
            px, py = part.split(":")[:2]
            points.append((float(px), float(py)))
        except (ValueError, IndexError):
            continue
    if kind == "L" or len(points) < 2:
        path = points
    elif kind == "P" and len(points) == 3:
        a, b, c = points
        ax, ay = a
        bx, by = b
        cx, cy = c
        determinant = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
        if abs(determinant) < 1e-5:
            path = _bezier(points)
        else:
            ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / determinant
            uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / determinant
            angles = [math.atan2(py - uy, px - ux) for px, py in points]
            start, mid, end = angles
            direction = 1 if ((mid - start) % (2 * math.pi)) <= ((end - start) % (2 * math.pi)) else -1
            sweep = (end - start) % (2 * math.pi) if direction > 0 else -((start - end) % (2 * math.pi))
            path = [(ux + math.cos(start + sweep * i / 40) * math.hypot(ax - ux, ay - uy),
                     uy + math.sin(start + sweep * i / 40) * math.hypot(ax - ux, ay - uy)) for i in range(41)]
    else:
        # osu! Bezier segments break at repeated control points.
        path = []
        segment = []
        for point in points:
            if segment and point == segment[-1]:
                path.extend(_bezier(segment, max(8, len(segment) * 8))[:-1])
                segment = [point]
            else:
                segment.append(point)
        if segment:
            path.extend(_bezier(segment, max(8, len(segment) * 8)))
    if len(path) < 2:
        return path
    lengths = [math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]) for i in range(1, len(path))]
    total = sum(lengths)
    if total <= 0 or pixel_length <= 0:
        return path
    target = min(pixel_length, total)
    trimmed = [path[0]]
    travelled = 0.0
    for index, length in enumerate(lengths, 1):
        if travelled + length >= target:
            ratio = (target - travelled) / length if length else 0
            previous, current = path[index - 1], path[index]
            trimmed.append((previous[0] + (current[0] - previous[0]) * ratio,
                            previous[1] + (current[1] - previous[1]) * ratio))
            break
        trimmed.append(path[index])
        travelled += length
    return trimmed


def parse_osu(text: str, source: Path | None = None) -> Beatmap:
    sections: dict[str, list[str]] = {}
    section = ""
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            sections[section] = []
        elif section:
            sections[section].append(line)

    def values(name: str) -> dict[str, str]:
        result = {}
        for line in sections.get(name, []):
            if ":" in line:
                key, value = line.split(":", 1)
                result[key.strip()] = value.strip()
        return result

    general, metadata = values("General"), values("Metadata")
    difficulty = values("Difficulty")
    timing = [line.split(",") for line in sections.get("TimingPoints", [])]
    beat_length = 500.0
    for point in timing:
        try:
            if float(point[6]) == 1 and float(point[1]) > 0:
                beat_length = float(point[1])
                break
        except (IndexError, ValueError):
            continue
    slider_multiplier = float(difficulty.get("SliderMultiplier", 1.4))
    objects: list[HitObject] = []
    combo_index = 0
    combo_base = 0
    for line in sections.get("HitObjects", []):
        parts = line.split(",")
        try:
            x, y, time, type_bits = float(parts[0]), float(parts[1]), float(parts[2]), int(parts[3])
        except (IndexError, ValueError):
            continue
        if type_bits & 4:
            combo_index = 0
            combo_base += 1
        combo_index += 1
        combo = combo_base * 10 + combo_index
        sound = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0
        if type_bits & 8:
            end_time = float(parts[5].split(":")[0])
            objects.append(HitObject(x, y, time, "spinner", combo, sound, end_time))
        elif type_bits & 2 and len(parts) > 7:
            curve_type = parts[5]
            try:
                repeats = int(parts[6])
                pixel_length = float(parts[7])
            except ValueError:
                continue
            curve = _curve_path(x, y, curve_type, pixel_length)
            velocity = 100 * slider_multiplier * (beat_length / 1000)
            duration = pixel_length / max(velocity, 1) * beat_length * repeats
            objects.append(HitObject(x, y, time, "slider", combo, sound,
                                     time + duration, curve, repeats))
        else:
            objects.append(HitObject(x, y, time, "circle", combo, sound, time))
    objects.sort(key=lambda item: item.time)
    return Beatmap(metadata.get("TitleUnicode", metadata.get("Title", "Untitled")),
                   metadata.get("ArtistUnicode", metadata.get("Artist", "Unknown")),
                   metadata.get("Creator", "Unknown"), metadata.get("Version", "Normal"),
                   general.get("AudioFilename", ""), float(difficulty.get("ApproachRate", 5)),
                   float(difficulty.get("OverallDifficulty", 5)), float(difficulty.get("HPDrainRate", 5)),
                   float(difficulty.get("CircleSize", 5)), slider_multiplier, beat_length, objects, source)


def load_beatmap(path: str | Path) -> tuple[Beatmap, Path]:
    path = Path(path)
    if path.suffix.lower() == ".osz":
        import tempfile
        destination = Path(tempfile.mkdtemp(prefix="pyrhythm_"))
        with zipfile.ZipFile(path) as archive:
            osu_files = [name for name in archive.namelist() if name.lower().endswith(".osu")]
            if not osu_files:
                raise ValueError("This .osz archive does not contain an .osu beatmap.")
            for entry in archive.infolist():
                member = Path(entry.filename)
                if member.is_absolute() or ".." in member.parts:
                    continue
                target = destination.joinpath(*member.parts)
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(entry))
            safe_osu = next((name for name in osu_files
                             if (destination / Path(name)).is_file()), None)
            if safe_osu is None:
                raise ValueError("The .osz archive contains no readable .osu beatmap.")
        osu_path = destination / safe_osu
        return parse_osu(osu_path.read_text(encoding="utf-8-sig", errors="replace"), osu_path), destination
    if path.suffix.lower() != ".osu":
        raise ValueError("Choose an .osu beatmap or .osz archive.")
    return parse_osu(path.read_text(encoding="utf-8-sig", errors="replace"), path), path.parent


def builtin_map() -> Beatmap:
    objects = []
    positions = [(100, 100), (390, 95), (410, 285), (110, 285), (255, 190),
                 (150, 180), (360, 180), (255, 90), (255, 290), (110, 110)]
    for i in range(40):
        x, y = positions[i % len(positions)]
        at = 1800 + i * 500
        if i in (7, 19, 31):
            curve = [(x, y), (256, 192), (512 - x, 384 - y)]
            objects.append(HitObject(x, y, at, "slider", i + 1, 0, at + 700, curve, 1))
        elif i == 38:
            objects.append(HitObject(x, y, at, "spinner", i + 1, 0, at + 2500))
        else:
            objects.append(HitObject(x, y, at, "circle", i + 1))
    return Beatmap("Neon Pulse", "Copilot", "OpenAI", "Standard",
                   "builtin", 8, 6, 5, 4, 1.4, 500, objects)
