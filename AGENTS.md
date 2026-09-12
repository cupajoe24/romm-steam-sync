# `romm-steam-sync` Workspace Rules & Guidelines

Welcome to **`romm-steam-sync`**. When working on this project, adhere strictly to the following instructions:

## Core Directives
1. **Multi-Platform Support**: Target Windows, macOS, and Linux. Refer to [`.agent/rules/romm_steam_sync_architecture.md`](.agent/rules/romm_steam_sync_architecture.md).
2. **User-Friendly GUI**: Prioritize a modern, approachable desktop GUI consistent across all platforms. Avoid CLI requirements for end users. Refer to [`.agent/rules/romm_steam_sync_architecture.md`](.agent/rules/romm_steam_sync_architecture.md).
3. **Steam Safety Guard**: Whenever modifying `shortcuts.vdf` or grid artwork files, check if Steam is running. Alert the user to close Steam before proceeding, and notify them when it is safe to reopen. Refer to [`.agent/rules/romm_steam_sync_architecture.md`](.agent/rules/romm_steam_sync_architecture.md).
4. **Unit Test Execution & Architecture**: When code changes occur, run unit tests using the project virtual environment Python interpreter:
   - **Windows**: `.\.venv\Scripts\python.exe -m pytest tests/unit`
   - **Linux / macOS**: `./.venv/bin/python -m pytest tests/unit`
   Do NOT invoke system `python` or `py` directly for testing, as system Python lacks virtual environment packages (`pytest`, `requests`, `customtkinter`). Follow 1:1 test mapping, AAA structure, and naming conventions. Refer to [`.agent/rules/unit_testing.md`](.agent/rules/unit_testing.md). If only documentation or untested configurations change, running tests is not required.
5. **Logging Standard**:
   - **Major Behaviors**: Log major app behaviors (app launch, library sync start/finish, game launch/exit, save sync evaluation, on-demand downloads, backup/cleanup operations) using `logger.info()`.
   - **Exceptions**: Log exceptions in ALL `try...except` blocks using `logger.error()`, `logger.warning()`, or `logger.debug()`. Never swallow exceptions silently with `pass`. Refer to [`.agent/rules/logging_and_git.md`](.agent/rules/logging_and_git.md).
6. **Git Commit Policy**:
   - **User Confirmation Required**: NEVER create a git commit autonomously. ONLY create a git commit when explicitly instructed or confirmed by the user.
   - **Pre-Commit Verification**: When asked by the user to commit, run unit tests (`.\.venv\Scripts\python.exe -m pytest tests/unit`) ONLY if code was changed. If only documentation or untested configuration changed, running tests is not required. Never commit failing tests or half-baked code. Refer to [`.agent/rules/logging_and_git.md`](.agent/rules/logging_and_git.md).
7. **Python Style & String Rules**: Follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) across all Python code (docstrings with `Args:`/`Returns:`/`Raises:`, sorted 3-tier imports, type annotations, and contextual exception logging). NEVER include emojis in UI strings (button labels, modal titles, status text, placeholders, logs, etc.). Refer to [`.agent/rules/python_style.md`](.agent/rules/python_style.md).
8. **Third-Party Dependencies**: All third-party packages or vendored modules must reside in `third_party/`, must not be edited directly, and are exempt from linting/formatting. Refer to [`.agent/rules/third_party.md`](.agent/rules/third_party.md).

## Agent Rules Directory (`.agent/rules/`)
All agent-specific rules are defined in `.agent/rules/`:
- [`.agent/rules/python_style.md`](.agent/rules/python_style.md) - Google Python Style Guide, docstrings, typing, import ordering, and no-emojis rule.
- [`.agent/rules/logging_and_git.md`](.agent/rules/logging_and_git.md) - Mandatory logging standards, log levels, and git commit guidelines.
- [`.agent/rules/unit_testing.md`](.agent/rules/unit_testing.md) - Pytest virtual environment execution, 1:1 test file mapping, naming conventions, and AAA pattern.
- [`.agent/rules/romm_steam_sync_architecture.md`](.agent/rules/romm_steam_sync_architecture.md) - Desktop GUI requirements, Tender alignment, and Steam safety guard.
- [`.agent/rules/third_party.md`](.agent/rules/third_party.md) - Third-party directory location, immutability, and linting exemption.

## Technical & Functional Documentation (`docs/`)
Technical and architectural specifications for human developers and agents are documented in `docs/`:
- [`docs/README.md`](docs/README.md) - Documentation Index
- [`docs/overview.md`](docs/overview.md) - Project Overview & Tender Comparison
- [`docs/compatibility.md`](docs/compatibility.md) - Console & Platform Compatibility Matrix
- [`docs/roadmap.md`](docs/roadmap.md) - Development Roadmap & Feature Priorities
- [`docs/architecture/backend-architecture.md`](docs/architecture/backend-architecture.md) - Domain Aggregates & SQLite UoW
- [`docs/architecture/steam-shortcuts-vdf.md`](docs/architecture/steam-shortcuts-vdf.md) - Steam VDF & Close Guard
- [`docs/architecture/launcher-and-on-demand-downloads.md`](docs/architecture/launcher-and-on-demand-downloads.md) - Launcher Execution & On-Demand Downloads
- [`docs/architecture/retroarch-flavors-and-paths.md`](docs/architecture/retroarch-flavors-and-paths.md) - RetroArch Multi-Flavor Architecture & Path Resolution
- [`docs/architecture/save-file-sync-architecture.md`](docs/architecture/save-file-sync-architecture.md) - Save File & Playtime Sync
- [`docs/architecture/logging-architecture.md`](docs/architecture/logging-architecture.md) - Logging Architecture & System Setup
