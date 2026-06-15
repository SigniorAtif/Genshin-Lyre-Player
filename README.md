# Genshin Lyre Player

An automated lyre player for Genshin Impact — load a MIDI file or a token sheet and let it play directly into the game. Includes a video-to-sheet converter powered by computer vision.

**[Download v1.0.0 →][latest]** &nbsp; [![GitHub release](https://img.shields.io/github/v/release/SigniorAtif/GenshinLyrePlayer)][latest] [![GitHub all releases](https://img.shields.io/github/downloads/SigniorAtif/GenshinLyrePlayer/total?style=social)][latest]

<!-- Add a screenshot here: open any Issue on your repo, drag an image into the comment box,
     copy the https://user-images.githubusercontent.com/... URL it generates, paste it below.
     You can delete the comment once you have a real screenshot. -->
<!-- ![App screenshot](https://user-images.githubusercontent.com/YOUR_ID/YOUR_HASH.png) -->

---

## Quick Start

1. Download `GenshinLyrePlayer-v1.0.0-win-x64.zip` from the [Releases page][latest] and extract it anywhere — no installation required.
2. Run `GenshinLyrePlayer.exe`.
3. Add a `.mid` or `.txt` token sheet via the **Playlist** tab.
4. Press **Play** — the app switches focus to Genshin Impact and starts playing.

> **SmartScreen warning?** Click **More info → Run anyway**. The app is not code-signed (signing certificates are expensive). The source is fully open.

---

## Features

### MIDI & Token Sheet Playback
- Load **MIDI files** (`.mid`) or **token sheets** (`.txt`) into the playlist.
- Multi-track MIDI support — enable only the tracks you want.
- **Key transposition** — shift up or down to match your lyre's tuning.
- **Merge nearby notes** — clean up songs that sound too choppy.
- **Playback speed** control.
- **Test mode** — hear the song through your speakers without opening Genshin.

### Token Sheet View
- Converts the loaded song into a shareable **token sheet** — a plain-text format anyone can read and play manually.
- Copy to clipboard in one click.
- Customize delimiter, bars per row, and beat spacing.

### Vision Parser — Video to Sheet
Record yourself (or anyone) playing the lyre in Genshin, feed the video to the parser, and get a `.txt` token sheet back automatically.

```
python -m vision_parser --input my_recording.mp4 --output my_song.txt
```

The parser uses OpenCV to detect key presses from each video frame and reconstructs the timing into a playable token sheet.

### Keyboard Layouts
Switch between **QWERTY, QWERTZ, AZERTY, DVORAK**, and more — the key mappings update everywhere automatically.

### Playlist & Controls
- Queue multiple files and play continuously.
- Shuffle and loop modes.
- Full **media key** support (play/pause/skip via keyboard media buttons).
- **Scheduled play** — set a timer to start playing at a specific time.

### Appearance
- Windows 11 Mica / Fluent design.
- **Light and dark mode** — follows your system theme or set manually.
- **Mini mode** — shrink the window down to just the controls.

---

## Can I get banned?

The short answer is: **use at your own risk.** Automated key input is technically a third-party tool. Playing one instrument at a reasonable tempo is far less detectable than spamming. [Here is miHoYo's general stance on third-party tools.](https://genshin.mihoyo.com/en/news/detail/5763) Listen to the song through Test Mode first and avoid anything that hammers keys faster than a human could.

---

## Build from Source

### Requirements
- [Git](https://git-scm.com)
- [.NET 6.0 SDK](https://dotnet.microsoft.com/download)
- [Python 3.10+](https://www.python.org/downloads/)

```bat
git clone https://github.com/SigniorAtif/GenshinLyrePlayer.git
cd GenshinLyrePlayer
pip install -e ".[dev]"
```

#### Build the full release package (exe + zip)
```bat
build_release.bat
```
This produces `GenshinLyrePlayer-v1.0.0-win-x64.zip` in the project root — the same artifact uploaded to GitHub Releases.

#### Build the WPF app only
```bat
dotnet build GenshinLyrePlayer/GenshinLyrePlayer.sln -c Release
```

---

## Project Structure

```
GenshinLyrePlayer/
├── GenshinLyrePlayer/          # C# WPF application
│   ├── GenshinLyrePlayer.WPF/  # UI, ViewModels, Views
│   └── GenshinLyrePlayer.Data/ # MIDI parsing, token format
├── vision_parser/              # Python: video -> token sheet
├── player_engine/              # Python: token sheet player engine
├── shared/                     # Shared Python utilities
├── tests/                      # Python test suite
├── config/                     # ROI profiles and settings
├── build_release.bat           # One-click release builder
└── build_release.ps1           # Release build script
```

---

## Contributing

Open an issue to discuss any change before sending a PR. Keep PRs focused — one feature or fix per PR.

1. Fork the repo and create a branch from `main`.
2. Make your changes and add tests where applicable.
3. Run `pytest tests/` and `dotnet build` — both must pass.
4. Submit the PR with a clear description of what changed and why.

---

## License

- Source code: [MIT License](LICENSE.md)
- All Genshin Impact assets and trademarks are © miHoYo / HoYoverse. This project is not affiliated with or endorsed by miHoYo.
- Third-party libraries: see [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)

---

## Credits

Built on top of the original [GenshinLyreMidiPlayer](https://github.com/sabihoshi/GenshinLyreMidiPlayer) by [sabihoshi](https://github.com/sabihoshi). Extended with a Python vision parser, token sheet pipeline, and redesigned UI.

[latest]: https://github.com/SigniorAtif/GenshinLyrePlayer/releases/latest
