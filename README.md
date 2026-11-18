# PULSE — Desktop Rhythm Game

PULSE is a playable, osu!standard-inspired desktop rhythm game written in Python. Its built-in song, hit sounds, and sample chart are generated locally, so it starts without external assets. It supports `.osu` maps, imported `.osz` song archives, and `.osk` custom skins.

## Run from source

Requires Python 3.10 or later. On Windows:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

On macOS/Linux, activate with `source .venv/bin/activate` instead.

## Controls

- **Menu/song select:** arrows and Enter; click works on menu items and the selected beatmap.
- **Hit objects:** left/right mouse button or `Z` / `X`.
- **Pause:** `Esc`; resume with `Esc` or Enter.
- **Fullscreen:** `Alt+Enter`; also available in Settings.
- **Song select:** use Up/Down to choose a difficulty; click **Import .osz / .osk** or press `O`/`I`. Drag `.osz`, `.osk`, or `.osu` files onto the window to import them. Toggle NF/EZ/HR/DT/HD/AT with `1`–`6`.
- **Audio offset:** Settings, left/right arrows in 5 ms increments.
- **Slider tracking / spinners:** hold either mouse button or `Z`/`X`; follow the slider ball or spin the cursor around the playfield center.
- **Skins:** import `.osk` files from Song Select or Settings, then choose the skin in Settings.

Imported songs and skins are stored in `Songs/` and `Skins/` beside the executable (or in the current folder when running from source). Every `.osu` difficulty in imported archives is scanned into Song Select. Missing skin assets fall back to the built-in artwork and sounds.

PULSE uses a centered, responsive 4:3 playfield in osu!'s 512×384 coordinate space. Slider timing honors uninherited beat length and inherited slider velocity; beatmap hit windows are derived from OD.

## Build a standalone executable

Install the requirements in the active virtual environment, then run:

```powershell
python build.py
```

The script runs the equivalent one-file, windowed PyInstaller build. To invoke PyInstaller directly:

```powershell
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "oSu!x3" --paths . --collect-all pygame --collect-all numpy --hidden-import audio_engine --hidden-import auto_bot --hidden-import beatmap_parser --hidden-import content_store --hidden-import game_objects --hidden-import renderer --hidden-import skin_manager --hidden-import tkinter --hidden-import tkinter.filedialog main.py
```

The executable is written to `dist/oSu!x3.exe` on Windows or `dist/oSu!x3` on macOS/Linux. The sample chart and audio are generated in Python; imported maps, skins, audio, and images are read from the persistent content folders. macOS users must build on macOS; PyInstaller does not cross-compile between operating systems.
