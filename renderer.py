"""Responsive 4:3 playfield rendering and game screens."""
from __future__ import annotations

import math
import pygame
import pygame.gfxdraw

from beatmap_parser import Beatmap, HitObject, slider_path_position
from game_objects import GameState
from skin_manager import Skin

BG = (14, 17, 27)
PANEL = (25, 30, 45)
CYAN = (69, 220, 235)
PINK = (250, 88, 170)
WHITE = (238, 244, 255)


def approach_timing(approach_rate: float) -> tuple[float, float]:
    if approach_rate < 5:
        return (1200 + 600 * (5 - approach_rate) / 5,
                800 + 400 * (5 - approach_rate) / 5)
    if approach_rate > 5:
        return (1200 - 750 * (approach_rate - 5) / 5,
                800 - 500 * (approach_rate - 5) / 5)
    return 1200, 800


class Renderer:
    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.fonts: dict[int, pygame.font.Font] = {}
        for size in (14, 18, 24, 32, 46, 64):
            self.fonts[size] = pygame.font.Font(None, size)
        self.trail: list[tuple[float, float, float]] = []
        self.skin: Skin | None = None
        self._texture_cache: dict[tuple[str, int, int, float], pygame.Surface] = {}
        self._background_path: str | None = None
        self._background_image: pygame.Surface | None = None

    def set_skin(self, skin: Skin) -> None:
        self.skin = skin
        self._texture_cache.clear()

    def font(self, size: int) -> pygame.font.Font:
        size = max(1, int(size))
        if size not in self.fonts:
            try:
                self.fonts[size] = pygame.font.SysFont("Arial", size)
            except pygame.error:
                self.fonts[size] = pygame.font.Font(None, size)
        return self.fonts[size]

    def text(self, value: str, size: int, color: tuple[int, int, int], pos: tuple[int, int],
             center: bool = False) -> pygame.Rect:
        surface = self.font(size).render(value, True, color)
        rect = surface.get_rect()
        rect.center = pos if center else rect.center
        if not center:
            rect.topleft = pos
        self.screen.blit(surface, rect)
        return rect

    def button(self, label: str, rect: pygame.Rect, selected: bool = False) -> None:
        pygame.draw.rect(self.screen, (36, 54, 72) if selected else PANEL, rect, border_radius=8)
        pygame.draw.rect(self.screen, CYAN if selected else (57, 69, 89), rect, 2, border_radius=8)
        self.text(label, 24, WHITE, rect.center, True)

    def layout(self) -> tuple[pygame.Rect, float]:
        width, height = self.screen.get_size()
        scale = min(width / 512, height / 384)
        rect = pygame.Rect(0, 0, int(512 * scale), int(384 * scale))
        rect.center = (width // 2, height // 2)
        return rect, scale

    def field(self, pos: tuple[float, float], rect: pygame.Rect, scale: float) -> tuple[int, int]:
        return round(rect.x + pos[0] * scale), round(rect.y + pos[1] * scale)

    def draw_approach_circle(self, point: tuple[int, int], radius: float,
                             color: tuple[int, int, int], alpha: int, scale: float) -> None:
        if self.skin and "approachcircle" in self.skin.textures:
            diameter = max(1, round(radius * 2))
            image = pygame.transform.smoothscale(self.skin.textures["approachcircle"], (diameter, diameter))
            image.set_alpha(alpha)
            self.screen.blit(image, image.get_rect(center=point))
            return
        thickness = max(1, round(3.5 * scale))
        radius = max(1, round(radius))
        padding = thickness + 2
        diameter = (radius + padding) * 2 + 1
        ring = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        center = (diameter // 2, diameter // 2)
        pygame.draw.circle(ring, color, center, radius, thickness)
        pygame.gfxdraw.aacircle(ring, center[0], center[1], radius, color)
        inner_radius = max(1, radius - thickness)
        pygame.gfxdraw.aacircle(ring, center[0], center[1], inner_radius, color)
        ring.set_alpha(alpha)
        self.screen.blit(ring, (point[0] - center[0], point[1] - center[1]))

    def texture(self, name: str, size: tuple[int, int], alpha: int = 255,
                angle: float = 0.0) -> pygame.Surface | None:
        if not self.skin:
            return None
        original = self.skin.textures.get(name)
        if original is None:
            return None
        width, height = max(1, size[0]), max(1, size[1])
        key = (name, width, height, round(angle, 2))
        image = self._texture_cache.get(key)
        if image is None:
            if len(self._texture_cache) > 512:
                self._texture_cache.clear()
            image = pygame.transform.smoothscale(original, (width, height))
            if angle:
                image = pygame.transform.rotate(image, angle)
            self._texture_cache[key] = image
        if alpha < 255:
            image = image.copy()
            image.set_alpha(max(0, alpha))
        return image

    def _song_background(self, beatmap: Beatmap) -> None:
        if not beatmap.source or not beatmap.background_filename:
            return
        path = (beatmap.source.parent / beatmap.background_filename).resolve()
        if not path.is_file():
            return
        if str(path) != self._background_path:
            try:
                self._background_image = pygame.image.load(str(path)).convert()
                self._background_path = str(path)
            except pygame.error:
                self._background_image = None
        if self._background_image:
            image = pygame.transform.smoothscale(self._background_image, self.screen.get_size())
            image.set_alpha(105)
            self.screen.blit(image, (0, 0))

    def draw_playfield(self, rect: pygame.Rect) -> None:
        pygame.draw.rect(self.screen, (18, 23, 37), rect)
        pygame.draw.rect(self.screen, (55, 74, 99), rect, 2)
        for i in range(1, 4):
            y = rect.y + rect.height * i // 4
            pygame.draw.line(self.screen, (26, 34, 49), (rect.x, y), (rect.right, y))

    def draw_map(self, state: GameState, now_ms: float, cursor: tuple[float, float],
                 key_count: int, holding: bool = False, autoplay: bool = False) -> None:
        self.screen.fill(BG)
        rect, scale = self.layout()
        self.draw_playfield(rect)
        radius = (54.4 - 4.48 * state.beatmap.circle_size) * scale
        ar = state.beatmap.approach_rate
        if "EZ" in state.mods:
            ar *= .5
        if "HR" in state.mods:
            ar = min(10, ar * 1.4)
        preempt_ms, fade_in_ms = approach_timing(ar)

        for obj in state.objects[state.index:]:
            delta = obj.time - now_ms
            if delta > preempt_ms:
                continue
            progress = max(0.0, min(1.0, (now_ms - (obj.time - preempt_ms)) / preempt_ms))
            fade_alpha = round(255 * min(1.0, max(0.0, (preempt_ms - delta) / fade_in_ms)))
            alpha = fade_alpha
            if "HD" in state.mods and 0 < delta < 450:
                alpha = int(alpha * max(0, (delta - 70) / 380))
            if self.skin and self.skin.combo_colors:
                color = self.skin.combo_colors[(obj.combo - 1) % len(self.skin.combo_colors)]
            else:
                color = (int(70 + obj.combo * 19 % 150), int(170 + obj.combo * 11 % 80), 235)
            point = self.field((obj.x, obj.y), rect, scale)
            if obj.kind == "slider":
                curve = [self.field(point, rect, scale) for point in obj.curve]
                if len(curve) > 1:
                    border = self.skin.slider_border if self.skin and self.skin.slider_border else (3, 5, 12)
                    track = self.skin.slider_track_override if self.skin and self.skin.slider_track_override else (112, 149, 178)
                    pygame.draw.lines(self.screen, border, False, curve, max(8, round(radius * .95)))
                    pygame.draw.lines(self.screen, track, False, curve, max(4, round(radius * .72)))
                    for turn in range(1, max(1, obj.repeats)):
                        end = curve[-1] if turn % 2 else curve[0]
                        adjacent = curve[-2] if turn % 2 else curve[1]
                        direction = pygame.Vector2(end) - pygame.Vector2(adjacent)
                        if direction.length_squared():
                            direction = direction.normalize()
                            perpendicular = pygame.Vector2(-direction.y, direction.x)
                            tip = pygame.Vector2(end) + direction * radius * .4
                            base = pygame.Vector2(end) - direction * radius * .35
                            arrow = [tip, base + perpendicular * radius * .35,
                                     base - perpendicular * radius * .35]
                            pygame.draw.polygon(self.screen, WHITE, [(round(p.x), round(p.y)) for p in arrow])
                slider_position = slider_path_position(obj, now_ms)
                if slider_position is not None and now_ms <= obj.end_time:
                    ball = self.field(slider_position, rect, scale)
                    follow_radius = max(1, round(radius * 2.4))
                    if holding and math.dist(cursor, slider_position) <= max(.1, 54.4 - 4.48 * state.beatmap.circle_size) * 2.4:
                        follow = self.texture("sliderfollowcircle", (follow_radius * 2, follow_radius * 2))
                        if follow:
                            self.screen.blit(follow, follow.get_rect(center=ball))
                        else:
                            pygame.draw.circle(self.screen, (224, 242, 255), ball, follow_radius, max(1, round(3 * scale)))
                    ball_texture = self.texture("sliderb0", (round(radius * 2), round(radius * 2)))
                    if ball_texture:
                        self.screen.blit(ball_texture, ball_texture.get_rect(center=ball))
                    else:
                        pygame.draw.circle(self.screen, WHITE, ball, max(2, round(radius * .48)))
            if obj.kind == "spinner":
                if now_ms <= obj.end_time:
                    center = self.field((256, 192), rect, scale)
                    spinner_r = round(min(rect.width, rect.height) * .39)
                    duration = max(1, obj.end_time - obj.time)
                    spinner_progress = min(1.0, max(0.0, (now_ms - obj.time) / duration))
                    approach_radius = round(spinner_r * (1 - spinner_progress))
                    if approach_radius > 0:
                        spinner_approach = self.texture(
                            "spinner-approachcircle",
                            (approach_radius * 2, approach_radius * 2),
                        )
                        if spinner_approach:
                            self.screen.blit(spinner_approach, spinner_approach.get_rect(center=center))
                        else:
                            pygame.draw.circle(self.screen, (135, 190, 225), center, approach_radius,
                                               max(2, round(3 * scale)))
                    disc_size = round(spinner_r * 1.45)
                    spinner_angle = state.spinner_angle if state.active_spinner is obj else 0.0
                    disc = self.texture("spinner-circle", (disc_size, disc_size),
                                        angle=math.degrees(spinner_angle))
                    if disc:
                        self.screen.blit(disc, disc.get_rect(center=center))
                    else:
                        pygame.draw.circle(self.screen, (33, 48, 69), center, round(spinner_r * .66))
                        pygame.draw.circle(self.screen, (110, 165, 202), center, round(spinner_r * .66),
                                           max(2, round(scale * 4)))
                        for ray in range(12):
                            angle = math.tau * ray / 12 + spinner_angle
                            end = (round(center[0] + math.cos(angle) * spinner_r * .58),
                                   round(center[1] + math.sin(angle) * spinner_r * .58))
                            pygame.draw.line(self.screen, (85, 115, 150), center, end, max(1, round(scale * 2)))
                    meter_width = min(round(rect.width * .58), 460)
                    meter = pygame.Rect(center[0] - meter_width // 2, center[1] + round(spinner_r * .76),
                                        meter_width, max(8, round(12 * scale)))
                    pygame.draw.rect(self.screen, (37, 48, 65), meter, border_radius=6)
                    ratio = state.spinner_ratio(obj)
                    if ratio:
                        pygame.draw.rect(self.screen, CYAN,
                                         (meter.x, meter.y, round(meter.width * ratio), meter.height),
                                         border_radius=6)
                    self.text("SPINNER", 24, WHITE, (center[0], center[1] - 8), True)
                    elapsed = max(1, now_ms - obj.time)
                    rpm = (state.spinner_rotations() * 60000 / elapsed
                           if state.active_spinner is obj and state.spinner_last_angle is not None else 0)
                    self.text(f"{rpm:.0f} RPM", 24, CYAN, (center[0], meter.bottom + 27), True)
                    if ratio >= 1:
                        self.text("CLEAR!", 32, (255, 230, 120), (center[0], center[1] - round(spinner_r * .8)), True)
                continue
            fade = max(0, min(255, alpha))
            color_surface = pygame.Surface((round(radius * 3), round(radius * 3)), pygame.SRCALPHA)
            c = (*color, fade)
            center = (color_surface.get_width() // 2, color_surface.get_height() // 2)
            hit_texture = self.texture("hitcircle", (round(radius * 2), round(radius * 2)), fade)
            if hit_texture:
                self.screen.blit(hit_texture, hit_texture.get_rect(center=point))
                overlay = self.texture("hitcircleoverlay", (round(radius * 2), round(radius * 2)), fade)
                if overlay:
                    self.screen.blit(overlay, overlay.get_rect(center=point))
            else:
                pygame.draw.circle(color_surface, (6, 11, 24, fade), center, round(radius))
                pygame.draw.circle(color_surface, c, center, round(radius * .92))
                pygame.draw.circle(color_surface, (225, 247, 255, fade), center, round(radius * .78), max(1, round(2 * scale)))
                pygame.draw.circle(color_surface, (18, 30, 46, fade), center, round(radius * .66))
            local = (point[0] - center[0] + color_surface.get_width() // 2,
                     point[1] - center[1] + color_surface.get_height() // 2)
            if not hit_texture:
                self.screen.blit(color_surface, (point[0] - color_surface.get_width() // 2,
                                                 point[1] - color_surface.get_height() // 2))
            if (now_ms < obj.time and not state.has_judged(obj)
                    and state.active_slider is not obj and "HD" not in state.mods):
                approach_radius = radius * (3.5 - 2.5 * progress)
                self.draw_approach_circle(point, approach_radius, color, fade_alpha, scale)
            digit = self.texture(f"default-{obj.combo % 10}", (round(radius * .8), round(radius * .8)), fade)
            if digit:
                self.screen.blit(digit, digit.get_rect(center=point))
            else:
                number = self.font(max(14, round(24 * scale))).render(str(obj.combo), True, WHITE)
                number.set_alpha(fade)
                self.screen.blit(number, number.get_rect(center=point))

        for effect in list(state.effects):
            age = now_ms - effect.started
            if age > 700:
                state.effects.remove(effect)
                continue
            point = self.field((effect.x, effect.y), rect, scale)
            radius_burst = round(radius * (1 + age / 220))
            pygame.draw.circle(self.screen, effect.color, point, radius_burst, 2)
            label = self.font(24).render(effect.text, True, effect.color)
            label.set_alpha(round(255 * (1 - age / 700)))
            self.screen.blit(label, label.get_rect(center=(point[0], point[1] - round(30 * scale))))

        px, py = self.field(cursor, rect, scale)
        self.trail.append((px, py, time_now()))
        self.trail = [item for item in self.trail if time_now() - item[2] < .24][-16:]
        for i, (tx, ty, when) in enumerate(self.trail):
            age = time_now() - when
            trail_texture = self.texture("cursortrail", (max(2, round(12 * scale)), max(2, round(12 * scale))),
                                         round(255 * max(0, 1 - age / .24)))
            if trail_texture:
                self.screen.blit(trail_texture, trail_texture.get_rect(center=(tx, ty)))
            else:
                pygame.draw.circle(self.screen, (80, 222, 245), (tx, ty),
                                   max(1, round(scale * (2 + (1 - age / .24) * 5))), 1)
        cursor_texture = self.texture("cursor", (max(12, round(28 * scale)), max(12, round(28 * scale))))
        if cursor_texture and self.skin and self.skin.cursor_rotate and len(self.trail) > 1:
            previous = self.trail[-2]
            cursor_texture = self.texture(
                "cursor",
                (max(12, round(28 * scale)), max(12, round(28 * scale))),
                angle=-math.degrees(math.atan2(py - previous[1], px - previous[0])),
            )
        if cursor_texture:
            self.screen.blit(cursor_texture, cursor_texture.get_rect(center=(px, py)))
        else:
            pygame.draw.circle(self.screen, WHITE, (px, py), max(3, round(6 * scale)))
            pygame.draw.circle(self.screen, CYAN, (px, py), max(5, round(10 * scale)), 1)

        self.text(f"{state.score:08d}", 32, WHITE, (24, 18))
        self.text(f"{state.accuracy():.2f}%", 24, CYAN, (24, 54))
        self.text(f"{state.combo}x", 46, WHITE, (rect.right - 90, rect.bottom - 72))
        bar = pygame.Rect(rect.x, rect.y - 12, rect.width, 7)
        pygame.draw.rect(self.screen, (46, 54, 70), bar, border_radius=4)
        pygame.draw.rect(self.screen, (75, 235, 180), (bar.x, bar.y, int(bar.width * state.hp), bar.height), border_radius=4)
        key_rect = pygame.Rect(rect.right + 16, rect.y + 25, max(72, self.screen.get_width() - rect.right - 25), 80)
        pygame.draw.rect(self.screen, PANEL, key_rect, border_radius=8)
        self.text("INPUT", 18, (153, 170, 192), (key_rect.x + 12, key_rect.y + 9))
        self.text(f"Z  X   {key_count}", 24, CYAN, (key_rect.x + 12, key_rect.y + 38))
        if autoplay:
            self.text("AUTOPLAY", 18, PINK, (24, self.screen.get_height() - 34))
        pygame.display.flip()

    def menu_background(self) -> None:
        self.screen.fill(BG)
        width, height = self.screen.get_size()
        for i in range(8):
            x = (i * 193 + 70) % width
            pygame.draw.circle(self.screen, (20, 32, 52), (x, height // 2), 80 + i * 17, 1)
        pygame.draw.rect(self.screen, (36, 56, 76), (0, height - 90, width, 90))

    def menu(self, selected: int) -> None:
        self.menu_background()
        width, height = self.screen.get_size()
        self.text("PULSE", 64, WHITE, (width // 2, height // 2 - 150), True)
        self.text("A desktop rhythm game", 24, CYAN, (width // 2, height // 2 - 103), True)
        for i, item in enumerate(("PLAY", "SETTINGS", "QUIT")):
            self.button(item, pygame.Rect(width // 2 - 150, height // 2 - 40 + i * 68, 300, 52), i == selected)
        pygame.display.flip()

    def select(self, beatmaps: list[Beatmap], selected: int, mods: set[str],
               message: str = "") -> None:
        self.menu_background()
        width, height = self.screen.get_size()
        if beatmaps and 0 <= selected < len(beatmaps):
            self._song_background(beatmaps[selected])
        self.text("SONG SELECT", 46, WHITE, (width // 2, 60), True)
        self.button("Import .osz / .osk", pygame.Rect(width - 285, 66, 255, 44))
        first = max(0, min(selected - 2, max(0, len(beatmaps) - 6)))
        for row, index in enumerate(range(first, min(len(beatmaps), first + 6))):
            beatmap = beatmaps[index]
            label = f"{beatmap.artist} — {beatmap.title} [{beatmap.version}]  |  {beatmap.creator}"
            self.button(label, pygame.Rect(width // 2 - 360, 116 + row * 42, 720, 38), index == selected)
        if beatmaps:
            current = beatmaps[selected]
            self.text(f"{current.title}  ·  {current.version}", 24, WHITE,
                      (width // 2, 350), True)
        self.button("PLAY SELECTED", pygame.Rect(width // 2 - 115, 370, 230, 48), True)
        self.text("Up/Down: choose song    1-6: toggle mods    O/I: import    Drop .osz/.osk onto the window",
                  18, (175, 192, 211), (width // 2, 441), True)
        for i, mod in enumerate(("NF", "EZ", "HR", "DT", "HD", "AT")):
            self.button(f"{mod} {'ON' if mod in mods else 'OFF'}",
                        pygame.Rect(width // 2 - 280 + (i % 3) * 190,
                                    488 + (i // 3) * 58, 170, 46), mod in mods)
        self.text(message, 18, (255, 135, 125), (width // 2, height - 26), True)
        pygame.display.flip()

    def settings(self, offset: int, fullscreen: bool, skin_names: list[str],
                 skin_index: int, selected: int, message: str = "") -> None:
        self.menu_background()
        width, height = self.screen.get_size()
        self.text("SETTINGS", 46, WHITE, (width // 2, height // 2 - 130), True)
        options = [f"Audio offset: {offset:+d} ms   (Left / Right)",
                   f"Display: {'Fullscreen' if fullscreen else 'Windowed'}   (Enter)",
                   f"Skin: {skin_names[skin_index]}   (Left / Right)",
                   "Import .osz / .osk",
                   "Back"]
        for i, item in enumerate(options):
            self.button(item, pygame.Rect(width // 2 - 260, height // 2 - 150 + i * 62, 520, 48),
                        selected == i)
        if message:
            self.text(message, 18, (255, 135, 125), (width // 2, height - 30), True)
        pygame.display.flip()

    def overlay(self, title: str, lines: list[str], selected: int) -> None:
        shade = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 185))
        self.screen.blit(shade, (0, 0))
        w, h = self.screen.get_size()
        self.text(title, 46, WHITE, (w // 2, h // 2 - 100), True)
        for i, line in enumerate(lines):
            self.button(line, pygame.Rect(w // 2 - 150, h // 2 - 30 + i * 62, 300, 48), i == selected)
        pygame.display.flip()

    def results(self, state: GameState) -> None:
        self.menu_background()
        width, height = self.screen.get_size()
        self.text(state.grade(), 90, CYAN, (width // 2, height // 2 - 165), True)
        self.text(f"{state.score:,}", 46, WHITE, (width // 2, height // 2 - 88), True)
        self.text(f"Accuracy  {state.accuracy():.2f}%     Max combo  {state.max_combo}x", 26, WHITE,
                  (width // 2, height // 2 - 28), True)
        self.text(f"300: {state.counts[300]}    100: {state.counts[100]}    50: {state.counts[50]}    Miss: {state.counts[0]}",
                  24, (177, 194, 214), (width // 2, height // 2 + 20), True)
        self.button("Enter: song select", pygame.Rect(width // 2 - 150, height // 2 + 88, 300, 48), True)
        pygame.display.flip()


def time_now() -> float:
    import time
    return time.perf_counter()
