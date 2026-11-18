"""Gameplay scoring state and timing judgements."""
from __future__ import annotations

from dataclasses import dataclass
import math

from beatmap_parser import Beatmap, HitObject


@dataclass
class HitEffect:
    x: float
    y: float
    text: str
    color: tuple[int, int, int]
    started: float
    combo: int


class GameState:
    def __init__(self, beatmap: Beatmap, mods: set[str]) -> None:
        self.beatmap = beatmap
        self.mods = set(mods)
        self.objects = beatmap.objects
        self.index = 0
        self.score = 0
        self.combo = 0
        self.max_combo = 0
        self.counts = {300: 0, 100: 0, 50: 0, 0: 0}
        self.hp = 1.0
        self.effects: list[HitEffect] = []
        self.spinner_angle = 0.0
        self.spinner_rotation = 0.0
        self.spinner_last_angle: float | None = None
        self.spinner_bonus = 0

    def hit_window(self, judgment: int) -> float:
        od = self.beatmap.overall_difficulty
        if "EZ" in self.mods:
            od *= .5
        if "HR" in self.mods:
            od = min(10, od * 1.4)
        if judgment == 300:
            return max(16, 79.5 - 6 * od)
        if judgment == 100:
            return max(30, 139.5 - 8 * od)
        return max(45, 199.5 - 10 * od)

    def judge(self, obj: HitObject, now_ms: float, x: float, y: float, scale: float) -> bool:
        if obj.kind == "spinner":
            return False
        radius = max(24, 54.4 - 4.48 * self.beatmap.circle_size) * scale
        if math.hypot(obj.x - x, obj.y - y) > radius * 1.35:
            return False
        delta = abs(now_ms - obj.time)
        result = 300 if delta <= self.hit_window(300) else 100 if delta <= self.hit_window(100) else 50 if delta <= self.hit_window(50) else 0
        if result == 0:
            return False
        if obj.kind == "slider" and now_ms < obj.end_time - self.hit_window(50):
            # A slider's head can be hit, but scoring completes at its tail.
            pass
        self.register(obj, result, now_ms)
        return True

    def register(self, obj: HitObject, result: int, now_ms: float) -> None:
        self.counts[result] += 1
        if result == 0:
            self.combo = 0
            self.hp -= .12
            label, color = "MISS", (255, 82, 100)
        else:
            self.combo += 1
            self.max_combo = max(self.max_combo, self.combo)
            self.score += result + (self.combo * 10 if result == 300 else self.combo * 5)
            self.hp += {300: .035, 100: .018, 50: .006}[result]
            label, color = str(result), {300: (99, 245, 196), 100: (91, 190, 255), 50: (255, 192, 84)}[result]
        self.hp = min(1.0, max(0.0, self.hp))
        self.effects.append(HitEffect(obj.x, obj.y, label, color, now_ms, self.combo))
        self.index += 1

    def drain(self, dt: float, playing: bool) -> None:
        if playing:
            amount = .012 if "HR" not in self.mods else .022
            self.hp -= dt * amount
            if "NF" in self.mods:
                self.hp = max(.1, self.hp)

    def accuracy(self) -> float:
        total = sum(self.counts.values())
        if not total:
            return 100.0
        return (self.counts[300] * 300 + self.counts[100] * 100 + self.counts[50] * 50) / (total * 300) * 100

    def grade(self) -> str:
        acc = self.accuracy()
        if acc >= 100 and self.counts[0] == 0:
            return "SS"
        if acc >= 95:
            return "S"
        if acc >= 90:
            return "A"
        if acc >= 80:
            return "B"
        if acc >= 65:
            return "C"
        return "D"
