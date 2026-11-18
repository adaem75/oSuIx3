"""Deterministic autoplay cursor for local practice."""
from __future__ import annotations

from beatmap_parser import HitObject


class AutoBot:
    def position(self, obj: HitObject, now_ms: float) -> tuple[float, float]:
        if obj.kind == "spinner":
            return 256 + 100, 192
        if obj.kind == "slider" and obj.curve:
            progress = min(1.0, max(0.0, (now_ms - obj.time) / max(1, obj.end_time - obj.time)))
            index = round(progress * (len(obj.curve) - 1))
            return obj.curve[index]
        return obj.x, obj.y
