"""Gameplay scoring state and timing judgements."""
from __future__ import annotations

from dataclasses import dataclass
import math

from beatmap_parser import Beatmap, HitObject, slider_path_position


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
        self.spinner_scored_rotations = 0
        self.spinner_bonus_rotations = 0
        self.spinner_started_at = 0.0
        self.active_slider: HitObject | None = None
        self.slider_head_result = 0
        self.slider_tick_times: list[float] = []
        self.slider_tick_index = 0
        self.slider_ticks_hit = 0
        self.slider_ticks_total = 0
        self.slider_ticks_missed = 0

    @staticmethod
    def _timing_result(delta: float, hit_window) -> int:
        if delta <= hit_window(300):
            return 300
        if delta <= hit_window(100):
            return 100
        if delta <= hit_window(50):
            return 50
        return 0

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
        if obj.kind != "circle":
            return False
        radius = max(.1, 54.4 - 4.48 * self.beatmap.circle_size) * scale
        if math.hypot(obj.x - x, obj.y - y) > radius * 1.35:
            return False
        result = self._timing_result(abs(now_ms - obj.time), self.hit_window)
        if result == 0:
            return False
        self.register(obj, result, now_ms)
        return True

    def begin_slider(self, obj: HitObject, now_ms: float, x: float, y: float, scale: float) -> bool:
        if obj.kind != "slider" or self.active_slider is not None:
            return False
        radius = max(.1, 54.4 - 4.48 * self.beatmap.circle_size) * scale
        if math.hypot(obj.x - x, obj.y - y) > radius * 1.35:
            return False
        result = self._timing_result(abs(now_ms - obj.time), self.hit_window)
        if result == 0:
            return False
        self.active_slider = obj
        self.slider_head_result = result
        self.slider_tick_times = []
        self.slider_tick_index = 0
        self.slider_ticks_hit = 0
        self.slider_ticks_missed = 0
        duration = obj.duration_ms or (obj.end_time - obj.time) / max(1, obj.repeats)
        tick_interval = (obj.beat_length or self.beatmap.beat_length) / max(.1, self.beatmap.slider_tick_rate)
        if tick_interval > 0:
            for span in range(max(1, obj.repeats)):
                tick_time = obj.time + span * duration + tick_interval
                span_end = obj.time + (span + 1) * duration
                while tick_time < span_end - self.hit_window(50):
                    self.slider_tick_times.append(tick_time)
                    tick_time += tick_interval
        self.slider_ticks_total = len(self.slider_tick_times)
        self.register(obj, result, now_ms, advance=False, show_effect=False)
        return True

    def update_slider(self, now_ms: float, cursor: tuple[float, float],
                      holding: bool, scale: float) -> tuple[int, bool]:
        obj = self.active_slider
        if obj is None:
            return 0, False
        follow_radius = max(.1, 54.4 - 4.48 * self.beatmap.circle_size) * 2.4
        hit_ticks = 0
        while (self.slider_tick_index < len(self.slider_tick_times)
               and self.slider_tick_times[self.slider_tick_index] <= now_ms):
            tick_time = self.slider_tick_times[self.slider_tick_index]
            point = slider_path_position(obj, tick_time) or (obj.x, obj.y)
            success = holding and math.dist(cursor, point) <= follow_radius
            self.register(obj, 300 if success else 0, tick_time, advance=False, show_effect=False)
            self.slider_ticks_hit += int(success)
            self.slider_ticks_missed += int(not success)
            hit_ticks += int(success)
            self.slider_tick_index += 1
        if now_ms < obj.end_time:
            return hit_ticks, False
        tail = slider_path_position(obj, obj.end_time) or (obj.x, obj.y)
        tail_hit = holding and math.dist(cursor, tail) <= follow_radius
        ratio = (self.slider_ticks_hit + int(tail_hit)) / max(1, self.slider_ticks_total + 1)
        result = 300 if ratio >= .9 else 100 if ratio >= .65 else 50 if ratio >= .35 else 0
        result = min(result, self.slider_head_result)
        self.register(obj, result, now_ms)
        self.active_slider = None
        return hit_ticks, True

    def spinner_required_rotations(self, obj: HitObject) -> float:
        duration_seconds = max(0.0, (obj.end_time - obj.time) / 1000)
        od = self.beatmap.overall_difficulty
        scale = 1.0
        if "EZ" in self.mods:
            od *= .5
            scale *= .5
        if "HR" in self.mods:
            od = min(10, od * 1.4)
            scale *= 1.4
        return duration_seconds * (3.0 + .4 * od) * scale

    def spinner_rotations(self) -> float:
        return self.spinner_rotation / (2 * math.pi)

    def spinner_ratio(self, obj: HitObject) -> float:
        return min(1.0, self.spinner_rotations() / max(.001, self.spinner_required_rotations(obj)))

    def update_spinner(self, obj: HitObject, now_ms: float,
                       cursor: tuple[float, float], holding: bool) -> int:
        if not (obj.time <= now_ms <= obj.end_time):
            self.spinner_last_angle = None
            return 0
        dx, dy = cursor[0] - 256, cursor[1] - 192
        if not holding or math.hypot(dx, dy) < 8:
            self.spinner_last_angle = None
            return 0
        angle = math.atan2(dy, dx)
        self.spinner_angle = angle
        if self.spinner_started_at <= 0:
            self.spinner_started_at = obj.time
        if self.spinner_last_angle is not None:
            delta = (angle - self.spinner_last_angle + math.pi) % (2 * math.pi) - math.pi
            self.spinner_rotation += abs(delta)
        self.spinner_last_angle = angle

        completed = int(self.spinner_rotations())
        score_turns = max(0, completed - self.spinner_scored_rotations)
        if score_turns:
            self.score += score_turns * 100
            self.spinner_scored_rotations = completed
        bonus_target = max(0, int(self.spinner_rotations() - self.spinner_required_rotations(obj)))
        bonuses = max(0, bonus_target - self.spinner_bonus_rotations)
        if bonuses:
            self.score += bonuses * 1000
            self.spinner_bonus_rotations += bonuses
        elapsed = max(1.0, now_ms - obj.time)
        self.spinner_bonus = round(self.spinner_rotations() * 60000 / elapsed)
        return bonuses

    def finish_spinner(self, obj: HitObject, now_ms: float) -> int:
        ratio = self.spinner_rotations() / max(.001, self.spinner_required_rotations(obj))
        result = 300 if ratio >= 1.0 else 100 if ratio >= .75 else 50 if ratio >= .25 else 0
        self.register(obj, result, now_ms)
        self.spinner_last_angle = None
        self.spinner_started_at = 0.0
        return result

    def register(self, obj: HitObject, result: int, now_ms: float,
                 advance: bool = True, show_effect: bool = True) -> None:
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
        if show_effect:
            self.effects.append(HitEffect(obj.x, obj.y, label, color, now_ms, self.combo))
        if advance:
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
