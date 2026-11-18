"""Responsive 4:3 playfield rendering and game screens."""
from __future__ import annotations

import math
import pygame

from beatmap_parser import HitObject
from game_objects import GameState

BG = (14, 17, 27)
PANEL = (25, 30, 45)
CYAN = (69, 220, 235)
PINK = (250, 88, 170)
WHITE = (238, 244, 255)


class Renderer:
    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.fonts = {}
        for size in (14, 18, 24, 32, 46, 64):
            self.fonts[size] = pygame.font.Font(None, size)
        self.trail: list[tuple[float, float, float]] = []

    def text(self, value: str, size: int, color: tuple[int, int, int], pos: tuple[int, int],
             center: bool = False) -> pygame.Rect:
        surface = self.fonts[size].render(value, True, color)
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

    def draw_playfield(self, rect: pygame.Rect) -> None:
        pygame.draw.rect(self.screen, (18, 23, 37), rect)
        pygame.draw.rect(self.screen, (55, 74, 99), rect, 2)
        for i in range(1, 4):
            y = rect.y + rect.height * i // 4
            pygame.draw.line(self.screen, (26, 34, 49), (rect.x, y), (rect.right, y))

    def draw_map(self, state: GameState, now_ms: float, cursor: tuple[float, float],
                 key_count: int, autoplay: bool = False) -> None:
        self.screen.fill(BG)
        rect, scale = self.layout()
        self.draw_playfield(rect)
        radius = (54.4 - 4.48 * state.beatmap.circle_size) * scale
        ar = state.beatmap.approach_rate
        if "EZ" in state.mods:
            ar *= .5
        if "HR" in state.mods:
            ar = min(10, ar * 1.4)
        approach = (1800 - 120 * ar) if ar < 5 else (1200 - 150 * (ar - 5))
        if "DT" in state.mods:
            approach /= 1.5

        for obj in state.objects[state.index:]:
            delta = obj.time - now_ms
            if delta < -1100:
                continue
            if delta > approach + 1000:
                continue
            alpha = max(0, min(255, int(255 * min(1, (delta + 1000) / 180))))
            if "HD" in state.mods and 0 < delta < 450:
                alpha = int(alpha * max(0, (delta - 70) / 380))
            color = (int(70 + obj.combo * 19 % 150), int(170 + obj.combo * 11 % 80), 235)
            point = self.field((obj.x, obj.y), rect, scale)
            if obj.kind == "slider":
                curve = [self.field(point, rect, scale) for point in obj.curve]
                if len(curve) > 1:
                    pygame.draw.lines(self.screen, (3, 5, 12), False, curve, max(8, round(radius * .95)))
                    pygame.draw.lines(self.screen, (112, 149, 178), False, curve, max(4, round(radius * .72)))
                if delta < 0 and now_ms < obj.end_time and curve:
                    progress = min(1, (now_ms - obj.time) / max(1, obj.end_time - obj.time))
                    ball = curve[min(len(curve) - 1, int(progress * (len(curve) - 1)))]
                    pygame.draw.circle(self.screen, (255, 255, 255), ball, round(radius * .52), 2)
            if obj.kind == "spinner":
                if now_ms <= obj.end_time:
                    center = self.field((256, 192), rect, scale)
                    spinner_r = round(min(rect.width, rect.height) * .38)
                    pygame.draw.circle(self.screen, (110, 165, 202), center, spinner_r, max(2, round(scale * 4)))
                    pygame.draw.circle(self.screen, CYAN, center, round(radius * .65), 2)
                    self.text("SPINNER", 24, WHITE, (center[0], center[1] - 8), True)
                continue
            fade = max(0, min(255, alpha))
            color_surface = pygame.Surface((round(radius * 3), round(radius * 3)), pygame.SRCALPHA)
            c = (*color, fade)
            center = (color_surface.get_width() // 2, color_surface.get_height() // 2)
            pygame.draw.circle(color_surface, (6, 11, 24, fade), center, round(radius * 1.06))
            pygame.draw.circle(color_surface, c, center, round(radius * .92))
            pygame.draw.circle(color_surface, (225, 247, 255, fade), center, round(radius * .78), max(1, round(2 * scale)))
            pygame.draw.circle(color_surface, (18, 30, 46, fade), center, round(radius * .66))
            local = (point[0] - center[0] + color_surface.get_width() // 2,
                     point[1] - center[1] + color_surface.get_height() // 2)
            if delta > 0:
                progress = max(0, min(1.0, 1 - delta / max(1, approach)))
                pygame.draw.circle(color_surface, (255, 255, 255, fade), local,
                                   round(radius * (1.7 - .7 * progress)), max(1, round(2 * scale)))
            self.screen.blit(color_surface, (point[0] - color_surface.get_width() // 2,
                                             point[1] - color_surface.get_height() // 2))
            number = self.fonts[max(14, round(24 * scale))].render(str(obj.combo), True, WHITE)
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
            label = self.fonts[24].render(effect.text, True, effect.color)
            label.set_alpha(round(255 * (1 - age / 700)))
            self.screen.blit(label, label.get_rect(center=(point[0], point[1] - round(30 * scale))))

        px, py = self.field(cursor, rect, scale)
        self.trail.append((px, py, time_now()))
        self.trail = [item for item in self.trail if time_now() - item[2] < .24][-16:]
        for i, (tx, ty, when) in enumerate(self.trail):
            age = time_now() - when
            pygame.draw.circle(self.screen, (80, 222, 245), (tx, ty),
                               max(1, round(scale * (2 + (1 - age / .24) * 5))), 1)
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

    def select(self, selected: int, mods: set[str], title: str, message: str = "") -> None:
        self.menu_background()
        width, height = self.screen.get_size()
        self.text("SONG SELECT", 46, WHITE, (width // 2, 60), True)
        self.button(title, pygame.Rect(width // 2 - 330, 130, 660, 90), True)
        self.text("Enter: play   O: open .osu/.osz   Drop a beatmap onto this window", 20, (175, 192, 211), (width // 2, 245), True)
        mods_list = ["NF", "EZ", "HR", "DT", "HD", "AT"]
        for i, mod in enumerate(mods_list):
            self.button(f"{mod} {'ON' if mod in mods else 'OFF'}",
                        pygame.Rect(width // 2 - 280 + (i % 3) * 190, 305 + (i // 3) * 62, 170, 48),
                        mod in mods or selected == i + 1)
        self.text(message, 18, (255, 135, 125), (width // 2, height - 48), True)
        pygame.display.flip()

    def settings(self, offset: int, fullscreen: bool, selected: int) -> None:
        self.menu_background()
        width, height = self.screen.get_size()
        self.text("SETTINGS", 46, WHITE, (width // 2, height // 2 - 130), True)
        options = [f"Audio offset: {offset:+d} ms   (Left / Right)",
                   f"Display: {'Fullscreen' if fullscreen else 'Windowed'}   (Enter)",
                   "Escape: back"]
        for i, item in enumerate(options):
            self.button(item, pygame.Rect(width // 2 - 240, height // 2 - 55 + i * 70, 480, 52), selected == i)
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
