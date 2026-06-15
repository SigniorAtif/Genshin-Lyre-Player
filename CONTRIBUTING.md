# Contributing to Genshin Lyre Player

Thanks for taking the time to contribute! This project welcomes bug reports, feature suggestions, and pull requests.

## Before You Start

Open an issue to discuss any significant change before writing code. This avoids duplicate work and ensures the change aligns with the project's direction. For small bug fixes or typos, a PR without a prior issue is fine.

## Reporting Bugs

Include:
- What you did
- What you expected to happen
- What actually happened
- Your OS version and the app version (shown in Settings → Version)
- Any error messages or screenshots

## Development Setup

### Requirements
- [Git](https://git-scm.com)
- [.NET 6.0 SDK](https://dotnet.microsoft.com/download)
- [Python 3.10+](https://www.python.org/downloads/)

### Clone and install

```bat
git clone https://github.com/SigniorAtif/GenshinLyrePlayer.git
cd GenshinLyrePlayer
pip install -e ".[dev]"
```

### Running tests

```bat
pytest tests/ -v
```

### Running the WPF app during development

```bat
dotnet run --project GenshinLyrePlayer/GenshinLyrePlayer.WPF/GenshinLyrePlayer.WPF.csproj
```

Or open `GenshinLyrePlayer/GenshinLyrePlayer.sln` in Visual Studio and press **F5**.

### Building the WPF app (compile only, no run)

```bat
dotnet build GenshinLyrePlayer/GenshinLyrePlayer.sln -c Release
```

### Building the full release package (ship only)

```bat
build_release.bat
```

This produces `GenshinLyrePlayer-v1.0.0-win-x64.zip` — a self-contained single exe for distribution. Only needed when preparing a release, not during regular development.

## Pull Request Process

1. Fork the repo and create a branch from `main` with a descriptive name (e.g. `fix/update-check-url`, `feat/drag-drop-support`).
2. Make your changes. Add or update tests for any new Python logic.
3. Run `pytest tests/` and `dotnet build GenshinLyrePlayer/GenshinLyrePlayer.sln` — both must pass cleanly before submitting.
4. Keep the PR focused — one feature or fix per PR.
5. Write a clear PR description: what changed and why.

## Code Style

- **C#**: follow the existing naming and formatting conventions in the project (Allman braces, `var` where obvious, expression-bodied members for single-line getters).
- **Python**: PEP 8. Run `pytest` to catch regressions.
- Do not include build output (`release/`, `*.spec`, `publish/`) in the PR.

## Contact

Post an issue, or email signioratif@gmail.com for anything that doesn't fit an issue.
