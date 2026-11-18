oSuIx3 an osu recreation that SUCKS (my first project)

oSuIx3 is a playable, osu!standard-inspired desktop rhythm game written in Python. Its built-in song, hit sounds, and sample chart are generated locally, so it starts without external assets. It supports `.osu` maps, imported `.osz` song archives, and `.osk` custom skins.

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

oSuIx3 uses a centered, responsive 4:3 playfield in osu!'s 512×384 coordinate space. Slider timing honors uninherited beat length and inherited slider velocity; beatmap hit windows are derived from OD.

##HOW TO INSTALL

so when u download the zip ( u download it by pressing the green code button then download zip) u double click it then double click the main folder then double click dist and inside will be the game, you will have to extract all into a folder
so that u can repeat the same steps but instead of extracting you just double click the game, windows smartscreen might call it malicious but its not because its malicious you will have to click on more info
then run anyway. if you still think its malicious i copied this from gemini and a bunch of ais had very similar answers.
Microsoft Defender SmartScreen flags apps from small developers as "unrecognized" or potentially malicious primarily because they lack download reputation and an expensive digital code-signing certificate. SmartScreen does not actually scan the code inside your file for viruses—instead, it relies on a trust-based reputation system.

Why Small Developers Get Flagged

• Zero Download Reputation: SmartScreen tracks how many Windows users around the world have downloaded and safely run a specific file (identified by its cryptographic hash). Whenever you compile a brand-new .exe—even if you only change one line of code—its file hash changes, resetting its reputation to zero.
• No Code-Signing Certificate: Established companies buy digital Code Signing Certificates (often costing hundreds of dollars per year) to prove their identity to Windows. Without one, Windows marks the publisher as "Unknown Publisher" and displays the warning screen by default.
• PyInstaller & Packer Heuristics: Tools like PyInstaller bundle a Python interpreter and compressed scripts inside a single .exe wrapper. Because malware authors sometimes use similar executable packers to hide their code, Windows security tools treat newly compiled single-file executables with extra suspicion until enough users run them safely.

