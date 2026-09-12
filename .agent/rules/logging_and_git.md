---
trigger: always_on
---

# Logging and Git Commit Guidelines for `romm-steam-sync`

This document defines mandatory development rules regarding **when to log** and **when to create git commits**.

---

## 1. Logging Guidelines

### A. Core Rule: Every Major Behavior & Every Exception
- **Major Behaviors**: Every significant lifecycle event, state transition, network operation, and external process invocation MUST be logged.
- **Exception Logging**: Every `try...except` block—especially broad `except Exception:` handlers—MUST log the caught exception with contextual information. Never silently swallow errors with `pass`.

### B. When to Log & Log Level Selection

| Scenario / Operation | Recommended Log Level | Example |
| :--- | :--- | :--- |
| **App Startup & Entry Point** | `logger.info()` | Initializing GUI app / launcher script |
| **Library Sync Milestones** | `logger.info()` | Sync start, platform loop progress, completion count |
| **Game Launch Lifecycle** | `logger.info()` | Process spawning with PID, exit code, post-launch sync |
| **Save Sync Matrix Outcome** | `logger.info()` | Sync evaluation (`DOWNLOAD`, `UPLOAD`, `NO_OP`, `CONFLICT`) |
| **On-Demand ROM Download** | `logger.info()` | Download start, completion target path, RomInstall DB record |
| **Backup / Cleanup Actions** | `logger.info()` | Pre-sync backup created, library collection removed, rollback restored |
| **Unexpected Failures & API Errors** | `logger.error()` | Subprocess launch error, network failure, write error |
| **Recoverable Fallbacks / Warnings** | `logger.warning()` | Server timeout, missing RetroArch path, Steam running guard blocked |
| **Debug / Expected Misses** | `logger.debug()` | Registry key not found, optional path search fallbacks |

### C. Logging Implementation Rules
- Acquire loggers per module using standard Python logging:
  ```python
  import logging
  logger = logging.getLogger(__name__)
  ```
- Pass format strings and arguments lazily (e.g., `logger.info("Fetched %d items from %s", count, source)`).
- All log messages are written to console stdout and persisted to `%APPDATA%\romm-steam-sync\romm-steam-sync.log` via central configuration in `romm_steam_sync.logging_config.setup_logging()`.

---

## 2. Git Commit Guidelines

### A. When to Create a Git Commit
- **User Confirmation Required**: NEVER create a git commit autonomously. ONLY execute `git commit` when the user explicitly instructs or confirms it is time to commit.
- **Logical Units of Work**: Keep commits atomic. Each commit should address a single logical concept or task (e.g., "implement save sync architecture", "add application-wide logging", "fix shortcuts.vdf parser edge case").
- **Clean State**: Commit when the codebase is in a stable, passing, and well-documented state.

### B. Pre-Commit Verification Prerequisites
Before executing `git commit`, if code changes were made, you MUST run the automated unit test suite using the project virtual environment interpreter:

- **Windows**:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/unit
  ```
- **Linux / macOS**:
  ```bash
  ./.venv/bin/python -m pytest tests/unit
  ```

If only documentation or untested configuration changed, running tests is not required.

> [!IMPORTANT]
> **NEVER commit broken code or failing tests.** Whenever code is modified, all tests must pass cleanly (`code 0`) before a commit is created.

### C. When NOT to Commit
- Do NOT commit mid-task while in an incomplete, unverified, or broken state.
- Do NOT commit before running unit tests.
- Do NOT commit generated log files (`romm-steam-sync.log`), temporary test folders, or virtual environments (`.venv`).

### D. Commit Message Standards
Use clear, concise imperative commit messages following conventional commit prefixes:
- `feat: <description>` for new capabilities (e.g., `feat: add save file sync engine and Tender matrix matching`)
- `fix: <description>` for bug fixes (e.g., `fix: prevent duplicate shortcut entries in VDF writer`)
- `refactor: <description>` for non-functional code restructures (e.g., `refactor: extract SteamPathResolver into dedicated adapter`)
- `docs: <description>` for documentation updates (e.g., `docs: update logging architecture documentation`)
