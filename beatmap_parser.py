"""Small osu!standard beatmap reader and curve helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path

from content_store import app_directory, extract_archive


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
    duration_ms: float = 0.0
    beat_length: float = 0.0


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
    background_filename: str = ""
    slider_tick_rate: float = 1.0


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
    target = pixel_length
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
    if target > total:
        previous, current = path[-2], path[-1]
        segment_length = math.hypot(current[0] - previous[0], current[1] - previous[1])
        if segment_length:
            extension = target - total
            trimmed.append((current[0] + (current[0] - previous[0]) / segment_length * extension,
                            current[1] + (current[1] - previous[1]) / segment_length * extension))
    return _resample_path(trimmed)


def _resample_path(path: list[tuple[float, float]], samples: int = 101) -> list[tuple[float, float]]:
    if len(path) < 2:
        return path
    distances = [0.0]
    for previous, current in zip(path, path[1:]):
        distances.append(distances[-1] + math.dist(previous, current))
    total = distances[-1]
    if total <= 0:
        return [path[0]] * samples
    result = []
    segment = 1
    for i in range(samples):
        target = total * i / (samples - 1)
        while segment < len(distances) - 1 and distances[segment] < target:
            segment += 1
        start_distance, end_distance = distances[segment - 1], distances[segment]
        ratio = (target - start_distance) / max(1e-9, end_distance - start_distance)
        start, end = path[segment - 1], path[segment]
        result.append((start[0] + (end[0] - start[0]) * ratio,
                       start[1] + (end[1] - start[1]) * ratio))
    return result


def slider_path_progress(obj: HitObject, current_time: float) -> float | None:
    if obj.kind != "slider" or current_time < obj.time or not obj.curve:
        return None
    duration = obj.duration_ms or (obj.end_time - obj.time) / max(1, obj.repeats)
    if duration <= 0:
        return 1.0
    total_progress = min(max(0.0, (current_time - obj.time) / duration), float(max(1, obj.repeats)))
    if total_progress >= max(1, obj.repeats):
        return 1.0 if (max(1, obj.repeats) - 1) % 2 == 0 else 0.0
    pass_index = int(total_progress)
    pass_progress = total_progress - pass_index
    return 1.0 - pass_progress if pass_index % 2 else pass_progress


def slider_path_position(obj: HitObject, current_time: float) -> tuple[float, float] | None:
    progress = slider_path_progress(obj, current_time)
    if progress is None:
        return None
    scaled = progress * (len(obj.curve) - 1)
    start_index = min(len(obj.curve) - 1, int(scaled))
    end_index = min(len(obj.curve) - 1, start_index + 1)
    ratio = scaled - start_index
    start, end = obj.curve[start_index], obj.curve[end_index]
    return (start[0] + (end[0] - start[0]) * ratio,
            start[1] + (end[1] - start[1]) * ratio)


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
    timing = []
    beat_length = 500.0
    for line in sections.get("TimingPoints", []):
        point = line.split(",")
        try:
            timing.append((float(point[0]), float(point[1]), int(point[6]) == 1))
        except (IndexError, ValueError):
            continue
    timing.sort(key=lambda point: point[0])
    for _, length, uninherited in timing:
        if uninherited and length > 0:
            beat_length = length
            break
    slider_multiplier = float(difficulty.get("SliderMultiplier", 1.4))
    slider_tick_rate = float(difficulty.get("SliderTickRate", 1))
    events = sections.get("Events", [])
    background_filename = ""
    for event in events:
        parts = event.split(",", 3)
        if parts and parts[0] == "0" and len(parts) >= 3:
            background_filename = parts[2].strip().strip('"')
            break
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
            objects.append(HitObject(256, 192, time, "spinner", combo, sound, end_time))
        elif type_bits & 2 and len(parts) > 7:
            curve_type = parts[5]
            try:
                repeats = max(1, int(parts[6]))
                pixel_length = float(parts[7])
            except ValueError:
                continue
            curve = _curve_path(x, y, curve_type, pixel_length)
            active_beat = 500.0
            sv_multiplier = 1.0
            for point_time, point_length, uninherited in timing:
                if point_time > time:
                    break
                if uninherited and point_length > 0:
                    active_beat = point_length
                    sv_multiplier = 1.0
                elif not uninherited and point_length < 0:
                    sv_multiplier = max(.1, min(10.0, -100.0 / point_length))
            duration = (pixel_length / max(slider_multiplier * 100.0 * sv_multiplier, 1e-9)) * active_beat
            objects.append(HitObject(x, y, time, "slider", combo, sound,
                                     time + duration * repeats, curve, repeats, duration, active_beat))
        else:
            objects.append(HitObject(x, y, time, "circle", combo, sound, time))
    objects.sort(key=lambda item: item.time)
    return Beatmap(metadata.get("TitleUnicode", metadata.get("Title", "Untitled")),
                   metadata.get("ArtistUnicode", metadata.get("Artist", "Unknown")),
                   metadata.get("Creator", "Unknown"), metadata.get("Version", "Normal"),
                   general.get("AudioFilename", ""), float(difficulty.get("ApproachRate", 5)),
                   float(difficulty.get("OverallDifficulty", 5)), float(difficulty.get("HPDrainRate", 5)),
                   float(difficulty.get("CircleSize", 5)), slider_multiplier, beat_length, objects, source,
                   background_filename, slider_tick_rate)


def scan_songs(songs_directory: str | Path) -> list[Beatmap]:
    maps = []
    root = Path(songs_directory)
    if not root.exists():
        return maps
    for path in sorted(path for path in root.rglob("*") if path.is_file() and path.suffix.lower() == ".osu"):
        try:
            maps.append(parse_osu(path.read_text(encoding="utf-8-sig", errors="replace"), path))
        except (OSError, ValueError):
            continue
    return maps


def import_osz(path: str | Path, songs_directory: str | Path) -> list[Beatmap]:
    destination = extract_archive(path, songs_directory)
    return scan_songs(destination)


def load_beatmap(path: str | Path) -> tuple[Beatmap, Path]:
    path = Path(path)
    if path.suffix.lower() == ".osz":
        maps = import_osz(path, app_directory() / "Songs")
        if not maps:
            raise ValueError("This .osz archive does not contain a readable .osu beatmap.")
        return maps[0], maps[0].source.parent if maps[0].source else app_directory()
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
