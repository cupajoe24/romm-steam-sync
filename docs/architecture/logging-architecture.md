# Logging Architecture

This document details the logging architecture, log formatting standards, and exception logging policies for **`romm-steam-sync`**.

---

## 1. System Overview & Central Configuration

All logging in `romm-steam-sync` is centralized and initialized via `setup_logging()` from `romm_steam_sync.logging_config`.

```python
from romm_steam_sync.logging_config import setup_logging

# Called once at application entry point (ui/app.py or launcher/__main__.py)
setup_logging(log_level=logging.INFO)
```

### Log Handlers
- **Console Handler (`StreamHandler`)**: Outputs formatted log records directly to `sys.stdout` for interactive development and CLI visibility.
- **Rotating File Handler (`RotatingFileHandler`)**: Persists logs to disk in the platform-appropriate application directory:
  - **Windows**: `%APPDATA%\romm-steam-sync\romm-steam-sync.log`
  - **macOS**: `~/Library/Application Support/romm-steam-sync/romm-steam-sync.log`
  - **Linux**: `~/.config/romm-steam-sync/romm-steam-sync.log`

### Rotation Strategy
- **Max File Size**: 5 MB (`5 * 1024 * 1024` bytes)
- **Backup Count**: 3 rolling backup files (`romm-steam-sync.log.1`, etc.)
- **Encoding**: UTF-8

---

## 2. Standard Log Format

All log handlers apply a unified format string:

```text
%(asctime)s [%(levelname)s] %(name)s: %(message)s
```

Example output:
```text
2026-08-19 16:45:01,123 [INFO] romm_steam_sync.service_layer.sync_service: ================ Starting Library Synchronization Pass ================
2026-08-19 16:45:02,456 [INFO] romm_steam_sync.launcher.app: Successfully launched RetroArch process PID 14208: Launched Game.sfc with RetroArch
```

---

## 3. Log Level Policies & Strategy

Log levels are partitioned according to the operational significance of the event:

| Log Level | Purpose & Criteria | Typical Scenarios |
| :--- | :--- | :--- |
| **`logger.info()`** | Major application milestones, user actions, and state transitions | App launch, library sync milestones, game spawn/exit, save sync evaluations, on-demand downloads, backup/cleanup operations |
| **`logger.warning()`** | Non-fatal anomalies or recoverable fallback events | Server timeouts triggering retry modals, Steam running guard activation, missing optional config |
| **`logger.error()`** | Operation failures or exceptions that disrupt intended functionality | Subprocess failure, network connection drops, database write errors, ROM extraction failures |
| **`logger.debug()`** | Fine-grained diagnostic traces and expected search misses | Registry key lookups, file pattern matches, ISO timestamp fallback parses |

### Major Behavior Events
The application emits `logger.info()` for significant lifecycle transitions to ensure deterministic troubleshooting from log files:
1. **Application Lifecycle**: Startup, main navigation tab switching, settings updates.
2. **Library Synchronization**:
   - Starting synchronization pass
   - Resolving target Steam user profile
   - Creating pre-sync Steam VDF backups
   - Authenticating with RomM API and fetching platform libraries
   - Writing `shortcuts.vdf` and updating `cloudstorage` / `localconfig.vdf` collections
   - Sync completion metrics (total ROMs processed, shortcuts created)
3. **On-Demand ROM Downloads & Extraction**:
   - Initiating content downloads for missing ROM files
   - Archive extraction progress and destination file resolution
   - Writing `RomInstall` records to the SQLite database
4. **Game Execution & Launcher Lifecycle**:
   - Inspecting ROM state and evaluating default sibling version preferences
   - Resolving RetroArch distribution flavors and libretro cores
   - Spawning the emulator subprocess with PID tracking
   - Process exit monitoring and elapsed session duration calculation
5. **Save Synchronization**:
   - Evaluating pre-launch Gavel matrix outcomes (`DOWNLOAD`, `UPLOAD`, `NO_OP`, `CONFLICT`)
   - Creating local `.romm-backup` quarantine files
   - Executing post-launch save upload to RomM
   - Ingesting playtime sessions via `/api/play-sessions`
6. **Maintenance & Cleanups**:
   - Removing individual platform collections or all RomM shortcuts
   - Purging associated grid artwork
   - Restoring Steam configuration from backup archives

---

## 4. Contextual Exception Handling

`romm-steam-sync` enforces strict exception handling across all components:

- **No Silent Exception Swallowing**: `try...except` blocks must never swallow exceptions with `pass`. Every caught exception must be recorded at an appropriate log level (`logger.error()`, `logger.warning()`, or `logger.debug()`).
- **Contextual Information**: Log entries must include contextual identifiers (such as ROM ID, file path, platform slug, or HTTP status) to facilitate root-cause analysis.
- **Lazy Formatting**: Pass format arguments lazily to logging methods (e.g., `logger.error("Failed to parse %s: %s", path, exc)`) rather than using eager f-strings or string concatenation.
