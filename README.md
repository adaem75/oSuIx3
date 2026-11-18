# PULSE — Desktop Rhythm Game

PULSE is a playable, osu!standard-inspired desktop rhythm game written in Python. Its built-in song, hit sounds, and sample chart are generated locally, so it starts without external assets. It can also read `.osu` beatmaps and `.osz` archives, using the audio file named by the beatmap when available.

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
- **Song select:** press `O` to open an `.osu` or `.osz`, or drag a beatmap onto the window. Toggle NF/EZ/HR/DT/HD/AT with `1`–`6` or click the mod buttons.
- **Audio offset:** Settings, left/right arrows in 5 ms increments.

PULSE uses a centered, responsive 4:3 playfield in osu!'s 512×384 coordinate space. Beatmap hit windows are derived from OD, and game time is driven by a monotonic clock with mixer playback-position correction where the backend provides it.

## Build a standalone executable

Install the requirements in the active virtual environment, then run:

```powershell
python build.py
```

The script runs the equivalent one-file, windowed PyInstaller build. To invoke PyInstaller directly:

```powershell
python -m PyInstaller --noconfirm --clean --onefile --windowed --name PulseRhythm --collect-all pygame --collect-all numpy main.py
```

The executable is written to `dist/PulseRhythm.exe` on Windows or `dist/PulseRhythm` on macOS/Linux. macOS users can build on macOS and rename/package the executable as desired; PyInstaller does not cross-compile between operating systems.
