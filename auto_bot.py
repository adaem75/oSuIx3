"""Deterministic autoplay cursor for local practice."""
from __future__ import annotations

import math

from beatmap_parser import HitObject, slider_path_position


class AutoBot:
    def position(self, obj: HitObject, now_ms: float) -> tuple[float, float]:
        if obj.kind == "spinner":
            angle = max(0.0, now_ms - obj.time) / 1000 * (2 * math.pi * 477 / 60)
            return 256 + 105 * math.cos(angle), 192 + 105 * math.sin(angle)
        if obj.kind == "slider":
            position = slider_path_position(obj, now_ms)
            if position is not None:
                return position
        return obj.x, obj.y
