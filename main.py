"""PULSE — a standalone osu!standard-inspired desktop rhythm game."""
from __future__ import annotations

import sys
import time
import math
from pathlib import Path

import pygame

from audio_engine import AudioEngine
from auto_bot import AutoBot
from beatmap_parser import Beatmap, builtin_map, load_beatmap
from game_objects import GameState
from renderer import Renderer

WIDTH, HEIGHT = 1280, 720
MODS = ("NF", "EZ", "HR", "DT", "HD", "AT")


def hit_sound_name(sound_flags: int) -> str:
    if sound_flags & 4:
        return "finish"
    if sound_flags & 8:
        return "clap"
    if sound_flags & 2:
        return "whistle"
    return "normal"


def pick_map() -> str | None:
    try:
        import tkinter
        from tkinter import filedialog
        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        name = filedialog.askopenfilename(filetypes=[("osu! beatmaps", "*.osu *.osz"), ("All files", "*.*")])
        root.destroy()
        return name or None
    except Exception as error:
        print(f"Could not open file picker: {error}", file=sys.stderr)
        return None


def main() -> None:
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    try:
        pygame.mixer.init()
    except pygame.error as error:
        print(f"Audio device unavailable: {error}", file=sys.stderr)
    pygame.display.set_caption("PULSE — Desktop Rhythm Game")
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    renderer = Renderer(screen)
    audio = AudioEngine()
    bot = AutoBot()
    clock = pygame.time.Clock()
    mode = "menu"
    menu_selection = 0
    settings_selection = 0
    select_selection = 0
    pause_selection = 0
    offset_ms = 0
    fullscreen = False
    mods: set[str] = set()
    beatmap = builtin_map()
    map_dir: Path | None = None
    selection_message = ""
    state: GameState | None = None
    cursor = (256.0, 192.0)
    key_count = 0
    running = True

    def toggle_fullscreen() -> None:
        nonlocal screen, renderer, fullscreen
        fullscreen = not fullscreen
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN) if fullscreen else pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        renderer = Renderer(screen)

    def start_game() -> None:
        nonlocal state, mode
        state = GameState(beatmap, mods)
        audio.offset_ms = offset_ms
        audio.play((map_dir / beatmap.audio_filename) if map_dir and beatmap.audio_filename else None,
                   1.5 if "DT" in mods else 1.0)
        mode = "game"

    while running:
        dt = min(clock.tick(120) / 1000, .05)
        now = time.perf_counter()
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE and not fullscreen:
                screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                renderer = Renderer(screen)
            elif event.type == pygame.DROPFILE:
                try:
                    beatmap, map_dir = load_beatmap(event.file)
                    selection_message = f"Loaded: {beatmap.title}"
                    mode = "select"
                except (OSError, ValueError, pygame.error) as error:
                    selection_message = str(error)
                    mode = "select"
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN and event.mod & pygame.KMOD_ALT:
                    toggle_fullscreen()
                    continue
                if mode == "menu":
                    if event.key in (pygame.K_UP, pygame.K_DOWN):
                        menu_selection = (menu_selection + (1 if event.key == pygame.K_DOWN else -1)) % 3
                    elif event.key == pygame.K_RETURN:
                        if menu_selection == 0:
                            mode = "select"
                        elif menu_selection == 1:
                            mode = "settings"
                        else:
                            running = False
                elif mode == "settings":
                    if event.key in (pygame.K_UP, pygame.K_DOWN):
                        settings_selection = (settings_selection + (1 if event.key == pygame.K_DOWN else -1)) % 3
                    elif event.key in (pygame.K_LEFT, pygame.K_RIGHT) and settings_selection == 0:
                        offset_ms += -5 if event.key == pygame.K_LEFT else 5
                        offset_ms = max(-500, min(500, offset_ms))
                    elif event.key == pygame.K_RETURN and settings_selection == 1:
                        toggle_fullscreen()
                    elif event.key == pygame.K_ESCAPE:
                        mode = "menu"
                elif mode == "select":
                    if event.key == pygame.K_ESCAPE:
                        mode = "menu"
                    elif event.key == pygame.K_UP:
                        select_selection = (select_selection - 1) % 7
                    elif event.key == pygame.K_DOWN:
                        select_selection = (select_selection + 1) % 7
                    elif event.key == pygame.K_RETURN:
                        start_game()
                    elif event.key == pygame.K_o:
                        chosen = pick_map()
                        if chosen:
                            try:
                                beatmap, map_dir = load_beatmap(chosen)
                                selection_message = f"Loaded: {beatmap.title}"
                            except (OSError, ValueError) as error:
                                selection_message = str(error)
                    elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6):
                        index = event.key - pygame.K_1
                        mod = MODS[index]
                        mods.symmetric_difference_update({mod})
                    elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                        mod = MODS[max(0, min(5, select_selection - 1))]
                        mods.symmetric_difference_update({mod})
                elif mode == "game":
                    if event.key == pygame.K_ESCAPE and state:
                        audio.pause()
                        mode = "pause"
                    elif event.key in (pygame.K_z, pygame.K_x):
                        key_count += 1
                        if state and state.index < len(state.objects):
                            field_rect, scale = renderer.layout()
                            mouse = pygame.mouse.get_pos()
                            x = (mouse[0] - field_rect.x) / scale
                            y = (mouse[1] - field_rect.y) / scale
                            obj = state.objects[state.index]
                            if state.judge(obj, audio.position() * 1000, x, y, scale):
                                audio.hit(hit_sound_name(obj.sound))
                elif mode == "pause":
                    if event.key in (pygame.K_UP, pygame.K_DOWN):
                        pause_selection = (pause_selection + (1 if event.key == pygame.K_DOWN else -1)) % 3
                    elif event.key == pygame.K_ESCAPE:
                        audio.resume()
                        mode = "game"
                    elif event.key == pygame.K_RETURN:
                        if pause_selection == 0:
                            audio.resume()
                            mode = "game"
                        elif pause_selection == 1:
                            audio.stop()
                            mode = "select"
                        else:
                            audio.stop()
                            mode = "menu"
                elif mode == "results":
                    if event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                        mode = "select"
                elif mode == "dead":
                    if event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                        mode = "results"
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if mode == "menu":
                    width, height = screen.get_size()
                    for i in range(3):
                        rect = pygame.Rect(width // 2 - 150, height // 2 - 40 + i * 68, 300, 52)
                        if rect.collidepoint(event.pos):
                            menu_selection = i
                            if i == 0:
                                mode = "select"
                            elif i == 1:
                                mode = "settings"
                            else:
                                running = False
                elif mode == "select":
                    width = screen.get_width()
                    for i, mod in enumerate(MODS):
                        rect = pygame.Rect(width // 2 - 280 + (i % 3) * 190, 305 + (i // 3) * 62, 170, 48)
                        if rect.collidepoint(event.pos):
                            mods.symmetric_difference_update({mod})
                    if event.button == 1 and event.pos[1] < 235:
                        start_game()
                elif mode == "settings" and event.button == 1:
                    width, height = screen.get_size()
                    for i in range(3):
                        if pygame.Rect(width // 2 - 240, height // 2 - 55 + i * 70, 480, 52).collidepoint(event.pos):
                            settings_selection = i
                            if i == 1:
                                toggle_fullscreen()
                elif mode == "game" and state and event.button in (1, 3):
                    field_rect, scale = renderer.layout()
                    x = (event.pos[0] - field_rect.x) / scale
                    y = (event.pos[1] - field_rect.y) / scale
                    cursor = (x, y)
                    now_ms = audio.position() * 1000
                    if state.index < len(state.objects):
                        obj = state.objects[state.index]
                        if state.judge(obj, now_ms, x, y, scale):
                            audio.hit(hit_sound_name(obj.sound))

        if mode == "game" and state:
            width, height = screen.get_size()
            field_rect, scale = renderer.layout()
            mouse = pygame.mouse.get_pos()
            cursor = ((mouse[0] - field_rect.x) / scale, (mouse[1] - field_rect.y) / scale)
            now_ms = audio.position() * 1000
            if "AT" in mods and state.index < len(state.objects):
                obj = state.objects[state.index]
                cursor = bot.position(obj, now_ms)
                if obj.kind == "spinner" and now_ms <= obj.end_time:
                    state.spinner_angle += dt * 13
                    cursor = (256 + 105 * math.cos(state.spinner_angle),
                              192 + 105 * math.sin(state.spinner_angle))
                    state.spinner_bonus += int(dt * 40)
                elif obj.kind != "spinner" and now_ms >= obj.time:
                    state.register(obj, 300, now_ms)
                    audio.hit("normal")
            if state.index < len(state.objects):
                obj = state.objects[state.index]
                if obj.kind == "spinner" and obj.time <= now_ms <= obj.end_time:
                    angle = math.atan2(cursor[1] - 192, cursor[0] - 256)
                    if state.spinner_last_angle is not None:
                        difference = (angle - state.spinner_last_angle + math.pi) % (2 * math.pi) - math.pi
                        state.spinner_rotation += abs(difference)
                        state.spinner_bonus += int(abs(difference) * 8)
                    state.spinner_last_angle = angle
            while state.index < len(state.objects):
                obj = state.objects[state.index]
                if obj.kind == "spinner" and now_ms >= obj.end_time:
                    rotations = state.spinner_rotation / (2 * math.pi)
                    result = 300 if rotations >= 2.5 else 100 if rotations >= 1.5 else 50 if rotations >= .5 else 0
                    state.score += state.spinner_bonus
                    state.register(obj, result, now_ms)
                    state.spinner_rotation = 0
                    state.spinner_last_angle = None
                    state.spinner_bonus = 0
                elif obj.kind == "slider" and now_ms >= obj.end_time:
                    state.register(obj, 0, now_ms)
                elif now_ms > obj.time + state.hit_window(50) and obj.kind == "circle":
                    state.register(obj, 0, now_ms)
                else:
                    break
            state.drain(dt, True)
            if state.hp <= 0 and "NF" not in mods:
                audio.stop()
                mode = "dead"
            elif state.index >= len(state.objects):
                audio.stop()
                mode = "results"
            renderer.draw_map(state, now_ms, cursor, key_count, "AT" in mods)
        elif mode == "menu":
            renderer.menu(menu_selection)
        elif mode == "select":
            renderer.select(select_selection, mods, f"{beatmap.artist} — {beatmap.title}", selection_message)
        elif mode == "settings":
            renderer.settings(offset_ms, fullscreen, settings_selection)
        elif mode == "pause":
            renderer.overlay("PAUSED", ["Resume", "Song Select", "Main Menu"], pause_selection)
        elif mode in ("results", "dead") and state:
            if mode == "dead":
                renderer.overlay("FAILED", ["Enter: results"], 0)
            else:
                renderer.results(state)
    audio.stop()
    pygame.quit()


if __name__ == "__main__":
    main()
