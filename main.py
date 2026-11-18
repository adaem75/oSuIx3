"""PULSE — a standalone osu!standard-inspired desktop rhythm game."""
from __future__ import annotations

import math
import sys
import time
import zipfile
from pathlib import Path

import pygame

from audio_engine import AudioEngine
from auto_bot import AutoBot
from beatmap_parser import Beatmap, builtin_map, import_osz, load_beatmap, scan_songs
from content_store import persistent_directories
from game_objects import GameState
from renderer import Renderer
from skin_manager import SkinManager

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


def pick_imports() -> tuple[str, ...]:
    try:
        import tkinter
        from tkinter import filedialog

        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        paths = filedialog.askopenfilenames(
            filetypes=[
                ("osu! maps and skins", "*.osz *.osk *.osu"),
                ("Beatmap archives", "*.osz"),
                ("Skin archives", "*.osk"),
                ("Beatmap files", "*.osu"),
                ("All files", "*.*"),
            ]
        )
        root.destroy()
        return tuple(paths)
    except Exception as error:
        print(f"Could not open import dialog: {error}", file=sys.stderr)
        return ()


def main() -> None:
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    try:
        pygame.mixer.init()
    except pygame.error as error:
        print(f"Audio device unavailable: {error}", file=sys.stderr)
    pygame.display.set_caption("oSu!x3 — Desktop Rhythm Game")
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    renderer = Renderer(screen)
    audio = AudioEngine()
    bot = AutoBot()
    songs_dir, skins_dir = persistent_directories()
    skin_manager = SkinManager(skins_dir)
    skin_names = skin_manager.available()
    skin_index = 0
    skin = skin_manager.load(skin_names[skin_index])
    renderer.set_skin(skin)
    audio.apply_skin(skin)
    beatmaps = [builtin_map(), *scan_songs(songs_dir)]
    selected_map = 0
    clock = pygame.time.Clock()
    mode = "menu"
    menu_selection = 0
    settings_selection = 0
    pause_selection = 0
    offset_ms = 0
    fullscreen = False
    mods: set[str] = set()
    selection_message = ""
    settings_message = ""
    state: GameState | None = None
    cursor = (256.0, 192.0)
    key_count = 0
    running = True

    def apply_skin(index: int) -> None:
        nonlocal skin_index, skin
        skin_index = index % len(skin_names)
        skin = skin_manager.load(skin_names[skin_index])
        renderer.set_skin(skin)
        audio.apply_skin(skin)

    def import_files(paths: tuple[str, ...] | list[str]) -> None:
        nonlocal beatmaps, selected_map, selection_message, settings_message
        nonlocal skin_names
        for raw_path in paths:
            path = Path(raw_path)
            suffix = path.suffix.lower()
            try:
                if suffix == ".osz":
                    imported = import_osz(path, songs_dir)
                    beatmaps = [builtin_map(), *scan_songs(songs_dir)]
                    if not imported:
                        raise ValueError(f"No .osu maps found inside {path.name}.")
                    imported_sources = {item.source for item in imported}
                    selected_map = next(
                        (index for index, item in enumerate(beatmaps)
                         if item.source in imported_sources),
                        0,
                    )
                    message = f"Imported {len(imported)} difficulty/difficulties from {path.name}."
                elif suffix == ".osu":
                    beatmap, _ = load_beatmap(path)
                    existing = next((i for i, item in enumerate(beatmaps)
                                     if item.source == beatmap.source), None)
                    if existing is None:
                        beatmaps.append(beatmap)
                        selected_map = len(beatmaps) - 1
                    else:
                        selected_map = existing
                    message = f"Loaded {beatmap.title} — {beatmap.version}."
                elif suffix == ".osk":
                    name = skin_manager.import_skin(path)
                    skin_names = skin_manager.available()
                    apply_skin(skin_names.index(name))
                    message = f"Imported skin: {name}."
                else:
                    message = f"Unsupported file: {path.name}"
                selection_message = settings_message = message
            except (OSError, ValueError, zipfile.BadZipFile, pygame.error) as error:
                selection_message = settings_message = str(error)

    def toggle_fullscreen() -> None:
        nonlocal screen, renderer, fullscreen
        fullscreen = not fullscreen
        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN) if fullscreen else pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        renderer = Renderer(screen)
        renderer.set_skin(skin)

    def start_game() -> None:
        nonlocal state, mode
        beatmap = beatmaps[selected_map]
        state = GameState(beatmap, mods)
        audio.offset_ms = offset_ms
        audio_path = beatmap.source.parent / beatmap.audio_filename if beatmap.source and beatmap.audio_filename else None
        audio.play(audio_path, 1.5 if "DT" in mods else 1.0)
        mode = "game"

    def field_cursor(position: tuple[int, int]) -> tuple[float, float, float]:
        field_rect, scale = renderer.layout()
        return ((position[0] - field_rect.x) / scale,
                (position[1] - field_rect.y) / scale, scale)

    def click_current_object(now_ms: float, position: tuple[int, int]) -> None:
        if state is None or state.index >= len(state.objects) or state.active_slider is not None:
            return
        x, y, scale = field_cursor(position)
        obj = state.objects[state.index]
        if obj.kind == "circle":
            if state.judge(obj, now_ms, x, y, scale):
                audio.hit(hit_sound_name(obj.sound))
        elif obj.kind == "slider":
            if state.begin_slider(obj, now_ms, x, y, scale):
                audio.hit(hit_sound_name(obj.sound))

    while running:
        dt = min(clock.tick(120) / 1000, .05)
        events = pygame.event.get()
        for event in events:
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE and not fullscreen:
                screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                renderer = Renderer(screen)
                renderer.set_skin(skin)
            elif event.type == pygame.DROPFILE:
                import_files([event.file])
                if Path(event.file).suffix.lower() in (".osz", ".osu"):
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
                        settings_selection = (settings_selection + (1 if event.key == pygame.K_DOWN else -1)) % 5
                    elif event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                        if settings_selection == 0:
                            offset_ms = max(-500, min(500, offset_ms + (-5 if event.key == pygame.K_LEFT else 5)))
                        elif settings_selection == 2:
                            apply_skin(skin_index + (-1 if event.key == pygame.K_LEFT else 1))
                    elif event.key == pygame.K_RETURN:
                        if settings_selection == 1:
                            toggle_fullscreen()
                        elif settings_selection == 2:
                            apply_skin(skin_index + 1)
                        elif settings_selection == 3:
                            import_files(pick_imports())
                        elif settings_selection == 4:
                            mode = "menu"
                    elif event.key == pygame.K_ESCAPE:
                        mode = "menu"
                elif mode == "select":
                    if event.key == pygame.K_ESCAPE:
                        mode = "menu"
                    elif event.key == pygame.K_UP:
                        selected_map = max(0, selected_map - 1)
                    elif event.key == pygame.K_DOWN:
                        selected_map = min(len(beatmaps) - 1, selected_map + 1)
                    elif event.key == pygame.K_RETURN:
                        start_game()
                    elif event.key in (pygame.K_o, pygame.K_i):
                        import_files(pick_imports())
                    elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5, pygame.K_6):
                        mods.symmetric_difference_update({MODS[event.key - pygame.K_1]})
                elif mode == "game":
                    if event.key == pygame.K_ESCAPE and state:
                        audio.pause()
                        mode = "pause"
                    elif event.key in (pygame.K_z, pygame.K_x):
                        key_count += 1
                        click_current_object(audio.position() * 1000, pygame.mouse.get_pos())
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
                elif mode in ("results", "dead") and event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                    mode = "select" if mode == "results" else "results"
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if mode == "menu":
                    width, height = screen.get_size()
                    for index in range(3):
                        rect = pygame.Rect(width // 2 - 150, height // 2 - 40 + index * 68, 300, 52)
                        if rect.collidepoint(event.pos):
                            menu_selection = index
                            if index == 0:
                                mode = "select"
                            elif index == 1:
                                mode = "settings"
                            else:
                                running = False
                elif mode == "select":
                    width = screen.get_width()
                    list_start = max(0, min(selected_map - 2, max(0, len(beatmaps) - 6)))
                    for row in range(min(6, len(beatmaps) - list_start)):
                        rect = pygame.Rect(width // 2 - 360, 116 + row * 42, 720, 38)
                        if rect.collidepoint(event.pos):
                            selected_map = list_start + row
                    import_rect = pygame.Rect(width - 285, 66, 255, 44)
                    play_rect = pygame.Rect(width // 2 - 115, 370, 230, 48)
                    if import_rect.collidepoint(event.pos):
                        import_files(pick_imports())
                    elif play_rect.collidepoint(event.pos):
                        start_game()
                    else:
                        for index, mod in enumerate(MODS):
                            rect = pygame.Rect(width // 2 - 280 + (index % 3) * 190,
                                               488 + (index // 3) * 58, 170, 46)
                            if rect.collidepoint(event.pos):
                                mods.symmetric_difference_update({mod})
                elif mode == "settings":
                    width, height = screen.get_size()
                    for index in range(5):
                        rect = pygame.Rect(width // 2 - 260, height // 2 - 150 + index * 62, 520, 48)
                        if rect.collidepoint(event.pos):
                            settings_selection = index
                            if index == 1:
                                toggle_fullscreen()
                            elif index == 2:
                                apply_skin(skin_index + 1)
                            elif index == 3:
                                import_files(pick_imports())
                            elif index == 4:
                                mode = "menu"
                elif mode == "game" and state and event.button in (1, 3):
                    click_current_object(audio.position() * 1000, event.pos)

        if mode == "game" and state:
            now_ms = audio.position() * 1000
            buttons = pygame.mouse.get_pressed()
            keys = pygame.key.get_pressed()
            holding = bool(buttons[0] or buttons[2] or keys[pygame.K_z] or keys[pygame.K_x])
            mouse = pygame.mouse.get_pos()
            x, y, scale = field_cursor(mouse)
            cursor = (x, y)

            if "AT" in mods and state.index < len(state.objects):
                obj = state.objects[state.index]
                cursor = bot.position(obj, now_ms)
                holding = True
                if obj.kind == "circle" and now_ms >= obj.time:
                    state.register(obj, 300, now_ms)
                    audio.hit(hit_sound_name(obj.sound))
                elif obj.kind == "slider" and state.active_slider is None and now_ms >= obj.time:
                    state.begin_slider(obj, obj.time, obj.x, obj.y, scale)

            if state.index < len(state.objects):
                obj = state.objects[state.index]
                if obj.kind == "spinner":
                    was_spinning = state.spinner_last_angle is not None
                    bonuses = state.update_spinner(obj, now_ms, cursor, holding)
                    if not was_spinning and state.spinner_last_angle is not None:
                        audio.hit("spinnerspin")
                    for _ in range(bonuses):
                        audio.hit("spinnerbonus")
                    if now_ms >= obj.end_time:
                        if state.finish_spinner(obj, now_ms) == 0:
                            audio.hit("combobreak")
                elif obj.kind == "slider" and state.active_slider is not None:
                    misses_before = state.slider_ticks_missed
                    ticks, _ = state.update_slider(now_ms, cursor, holding, scale)
                    for _ in range(ticks):
                        audio.hit("sliderslide")
                    if state.slider_ticks_missed > misses_before:
                        audio.hit("combobreak")
            while state.index < len(state.objects) and state.active_slider is None:
                obj = state.objects[state.index]
                if obj.kind == "spinner":
                    if now_ms >= obj.end_time:
                        if state.finish_spinner(obj, now_ms) == 0:
                            audio.hit("combobreak")
                    else:
                        break
                elif obj.kind in ("circle", "slider") and now_ms > obj.time + state.hit_window(50):
                    state.register(obj, 0, now_ms)
                    audio.hit("combobreak")
                else:
                    break
            state.drain(dt, True)
            if state.hp <= 0 and "NF" not in mods:
                audio.stop()
                mode = "dead"
            elif state.index >= len(state.objects):
                audio.stop()
                mode = "results"
            renderer.draw_map(state, now_ms, cursor, key_count, holding, "AT" in mods)
        elif mode == "menu":
            renderer.menu(menu_selection)
        elif mode == "select":
            renderer.select(beatmaps, selected_map, mods, selection_message)
        elif mode == "settings":
            renderer.settings(offset_ms, fullscreen, skin_names, skin_index, settings_selection, settings_message)
        elif mode == "pause":
            renderer.overlay("PAUSED", ["Resume", "Song Select", "Main Menu"], pause_selection)
        elif mode in ("results", "dead") and state:
            renderer.overlay("FAILED", ["Enter: results"], 0) if mode == "dead" else renderer.results(state)
    audio.stop()
    pygame.quit()


if __name__ == "__main__":
    main()
