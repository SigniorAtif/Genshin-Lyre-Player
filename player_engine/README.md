# Player Engine (Part 2 — Not Yet Implemented)

The Player Engine consumes `.txt` token files produced by the Vision Parser and
replays them in-game by injecting DirectX hardware-level scancodes on Windows 11.

## Planned Architecture

- `token_reader.py` — parse the `.txt` format into structured events
- `key_mapper.py` — load `config/key_mappings/` to map token keys → scancodes
- `input_injector.py` — send DirectInput scancodes via `ctypes` / `SendInput`
- `timing_scheduler.py` — schedule key events relative to BPM with precise timing
- `player_pipeline.py` — top-level orchestrator (mirror of vision_parser/parser_pipeline.py)

## Key Mapping Config

Scancode maps live in `config/key_mappings/`. Format TBD (JSON).
Each entry maps a token key (e.g. "A") to a DirectX scancode integer.
