---
trigger: always_on
---

# Project Architecture & Design Guidelines for `romm-steam-sync`

This rule set defines the mandatory architectural decisions, user interface requirements, and safety guards for the `romm-steam-sync` project.

---

## 1. Project Goal & Target Platforms
- **Scope**: Multi-platform Python application targeting **Windows, macOS, and Linux**.
- **Core Functionality**:
  - Connect to a self-hosted [RomM](https://github.com/rommapp/romm) instance (v4.9+).
  - Sync RomM library to Steam as non-Steam shortcuts launched via [RetroArch](https://github.com/libretro/RetroArch).
  - Provide on-demand ROM downloading when launching games from Steam.
  - Provide pre/post-launch save file synchronization and playtime tracking.

---

## 2. User Interface & Approachability Requirement
- **User-Friendly Desktop GUI**: The application must prioritize an approachable, user-friendly, and modern graphical interface consistent across Windows, macOS, and Linux.
- **Minimize CLI**: Avoid CLI-only workflows for end users whenever possible.

---

## 3. Architectural Alignment with Tender (`decky-romm-sync`)
- **Reference Spec**: Reference `context/romm-tender-main/romm-tender-main/docs/architecture/` for domain and API decisions.
- **Domain Aggregates & SQLite**: Follow Cosmic Python aggregate patterns (`Rom`, `RomInstall`, `RomSaveSyncState`, `RomPlaytime`, `SyncRun`, `KvConfig`) backed by an SQLite Unit of Work (`uow`).
- **RomM API Integration**: Match RomM REST API models (`/api/roms`, `/api/saves`, `/api/devices`, `/api/sync/negotiate`, `/api/play-sessions`).

---

## 4. Steam Shortcut & File Modification Safety Guards
- **Steam Process Close Guard**:
  - Whenever an operation modifies Steam shortcut configuration files (`shortcuts.vdf`) or grid artwork files, **check if Steam is currently running**.
  - If Steam is running, **alert the user to close Steam** before writing files.
  - Once file writing completes, **notify the user that it is safe to re-open Steam**.
- **Binary VDF Parsing**: Perform direct binary VDF serialization for `shortcuts.vdf` (`<Steam>/userdata/<user_id>/config/shortcuts.vdf`).
- **Launcher Seam**: Use `romm-steam-sync-launcher` executable/script as the shortcut `Exe` target to intercept launch events for on-demand downloads and save sync hooks.
