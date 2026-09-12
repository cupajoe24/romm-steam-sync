# Project Overview: `romm-steam-sync`

## 1. Executive Summary

**`romm-steam-sync`** is an open-source, multi-platform desktop application for **Windows, macOS, and Linux**. Its core purpose is to connect to a self-hosted [RomM](https://github.com/rommapp/romm) instance, synchronize the user's retro gaming library into Steam as non-Steam shortcuts, and launch those games seamlessly using [RetroArch](https://github.com/libretro/RetroArch) libretro cores across multiple distribution flavors (Steam, Standalone, and RetroDECK) while managing on-demand downloads and bidirectional save file synchronization.

The application is heavily modeled after [Tender](https://github.com/danielcopper/romm-tender) (`decky-romm-sync`), maintaining structural, architectural, and data compatibility with Tender wherever possible, while adapting to operate standalone on desktop platforms without Decky Loader.

---

## 2. Key Objectives & Features

1. **Library Synchronization to Steam**:
   - Query RomM v4.9+ REST API for platforms, ROMs, metadata, cover art, and custom collections.
   - Group multi-version and multi-disc ROMs into unified game sibling groups, creating exactly **one** Steam shortcut per game.
   - Apply deterministic 1G1R (1 Game 1 ROM) resolution and canonical title derivation.
   - Map RomM platforms to RetroArch libretro cores across Steam, Standalone, and RetroDECK distributions.
   - Generate binary `shortcuts.vdf` entries and place full grid artwork (`cover`, `hero`, `logo`, `icon`) in Steam's user directory.
   - Animate created ROM poster cover images live across a horizontal conveyor track (`RomCoverConveyor`) during synchronization.
   - Provide mid-sync cancellation with options to either **Cancel & Keep** progress so far or **Cancel & Rollback** (restoring pre-sync Steam VDF backup).
   - Enforce safety guards by alerting the user to close Steam prior to file modifications and notifying them when Steam can be safely reopened.

2. **Library Cleanup & Reverse Sync**:
   - Perform reverse sync to remove shortcuts, grid artwork, and Steam collection categories for a specific platform/collection or all synced libraries.
   - Automatically generate a pre-cleanup backup of Steam files to allow easy rollbacks.
   - Update SQLite database state and prune modern `cloudstorage` and legacy `localconfig.vdf` collection structures.

3. **On-Demand ROM Downloading & Multi-Version Launcher**:
   - Shortcuts in Steam execute a lightweight wrapper binary (`romm-steam-sync-launcher.exe` on Windows, native ELF binary on Linux) auto-installed to the user's config bin directory.
   - For multi-version/multi-disc games, presents an interactive version selection dialog with rich metadata badges (Region, Version/Revision, Languages, File Size) and an **"Always run this version for this game"** preference checkbox.
   - If a ROM has not yet been downloaded locally, clicking "Play" in Steam triggers an on-demand download from RomM before RetroArch is launched.
   - On-demand archive extraction (`archive_extractor.py`) decompresses `.zip`, `.7z`, or `.tar` ROMs when cores require uncompressed files.
   - Full or selective library pre-downloads are also supported via the desktop application GUI.

4. **Bidirectional Save File & Playtime Sync**:
   - **Gavel Normative Engine**: Embeds the normative save synchronization specification ported from `romm-gavel` (MIT licensed), featuring identity check disjunction (`local_matches_server`), 50% size reduction anti-corruption guard (`is_implausibly_shrunken`), HTTP 409 conflict resolution ladder (`resolve_upload_conflict`), and 2.0s timestamp tolerance for cross-filesystem accuracy.
   - **Save Strategy Abstraction Layer**: Pluggable strategies (`DefaultSavePerGameStrategy`, `SharedMemoryCardStrategy`, `MemoryCardPerGameStrategy`) handle diverse emulation save architectures:
     - Standard per-game SRAM/battery saves (`.srm`, `.sav`, `.rtc`, `.eep`, `.dsv`) routed via `RetroArchConfigAdapter` to match `retroarch.cfg` runtime directories.
     - Shared virtual memory cards with pre/post-launch swapping and canonical naming (`Mcd001.ps2` for PS2, `vmu_save_A1.bin` for Dreamcast).
     - Discrete memory card containers: GameCube `.gci` memory cards in `User/GC/<Region>/Card A/`, Nintendo Wii emulated NAND saves in `User/Wii/title/00010000/<TitleIDHex>/data/`, and Nintendo 3DS emulated SDMC title saves in Citra's folder hierarchies.
   - Pre-launch hook downloads the latest save slot from RomM for the game into the core's designated save path.
   - Post-launch hook detects process exit, uploads updated save files to RomM, and ingests play sessions to `/api/play-sessions` using monotonic session timing.

5. **Installed ROM Library & Local ROM Uninstallation**:
   - Dedicated `Library` view displaying locally installed games organized by platform with cover card art and search filtering.
   - Clickable game tiles open detailed action modals providing **Launch Game** (runs launcher wrapper in background subprocess) and **Uninstall ROM** (deletes local file and updates SQLite tracking).

6. **First-Launch Onboarding Wizard**:
   - Automatic first-launch detection controlled by `onboarding_complete` flag in `settings.json`.
   - Guides new users through a 6-step setup workflow:
     1. **Welcome Screen**: Visual introduction to RomM Steam Sync capabilities.
     2. **RomM Server Configuration**: Server URL (defaulting to `http://`) and unified API key input with live connection testing.
     3. **RetroArch Auto-Detection**: Sniffs system PATH, standard install directories, Steam libraries (`steamapps/common/RetroArch`), and RetroDECK Flatpak sandbox; provides direct Steam Store launcher (`steam://store/1118310`) and manual file picker if missing.
     4. **SteamGridDB API Key**: Setup instructions, direct link to SteamGridDB settings page, API key testing, and optional skip option.
     5. **Platform Selection**: Interactive checklist fetching available platforms from RomM server with Select All / Deselect All convenience buttons.
     6. **Initial Library Sync**: Runs initial sync pass with live `RomCoverConveyor`, toggleable log drawer, cancellation/rollback support, and completion transition to the main app Library view.

7. **User-Friendly Cross-Platform Desktop GUI**:
   - Built with CustomTkinter structured into 5 primary navigation views (`Library`, `Platform Selection`, `Library Sync`, `Cleanup & Restore`, and `Settings`) plus the first-launch setup wizard.
   - Hardened against Linux GUI edge cases (debounced resize events, modal reference tracking, Pillow Tk backend fallbacks).
   - Simplifies server setup, platform-to-core mapping, local library management, sync preferences, cleanups, VDF backup rollbacks, and status monitoring.

---

## 3. Comparison & Architectural Alignment with Tender

| Architectural Area | Tender (`decky-romm-sync`) | `romm-steam-sync` | Rationale & Alignment |
| :--- | :--- | :--- | :--- |
| **Execution Environment** | Steam Deck (SteamOS) plugin running inside Decky Loader | Standalone application on Windows, macOS, and Linux | Expands support to all desktop operating systems without requiring Decky Loader |
| **User Interface** | SteamOS Game Mode webview (TypeScript / React injected into Steam UI) | Modern Desktop GUI (6-step Onboarding Wizard + 5 view tabs: `Library`, `Platform Selection`, `Library Sync`, `Cleanup & Restore`, `Settings`) | Provides a user-friendly interface with local library cover grids, ROM uninstallation, animated cover conveyor, mid-sync rollback, and backup management |
| **Domain Model & DB** | Cosmic Python aggregate roots + SQLite (`uow`, `roms`, `rom_installs`, `rom_save_sync_states`, `rom_playtime`) | Shared Cosmic Python aggregate roots + SQLite schema | Ensures 1:1 data model and persistence compatibility with Tender |
| **RomM API Integration** | REST endpoints (`/api/roms`, `/api/saves`, `/api/devices`, `/api/sync/negotiate`) | Identical REST client adapter with unified API key Bearer authentication | Seamless integration with RomM v4.9+ servers |
| **Steam Shortcut & Collections** | Decky `SteamClient.Apps.AddShortcut` JS webview bridge | Direct `shortcuts.vdf` VDF serializer & `cloudstorage/cloud-storage-namespace-1.json` dual-sync manager | Manages non-Steam games, grid artwork, library collections, and reverse-sync cleanups for modern Steam clients |
| **Grid Artwork Staging** | Written via `SteamClient.Apps.SetCustomArtworkForApp` | Direct file writes/deletions in `<Steam>/userdata/<user_id>/config/grid/` | Places/removes images directly in Steam's local grid cache directory using standard AppID hash filenames |
| **Steam Safety Guard** | SteamOS webview memory update | Process check + User Close & Reopen Notification | Prevents file corruption or Steam overwriting `shortcuts.vdf` during sync or cleanup passes |
| **Launch & Save Hook** | `bin/rom-launcher` shell wrapper | `romm-steam-sync-launcher` standalone native binary / script wrapper | Intercepts Steam launch commands, handles RetroArch flavor resolution, performs pre/post-launch save sync, and manages on-demand ROM downloads |

---

## 4. Platform Specifications & System Requirements

- **Runtime**: Packaged standalone binaries (zero Python requirement for end users) or Python 3.11/3.12+ for development.
- **Operating Systems**:
  - **Windows**: Windows 10/11 (x64)
  - **macOS**: macOS 12+ (Apple Silicon & Intel)
  - **Linux**: Ubuntu 22.04+, Fedora 38+, SteamOS Desktop Mode
- **Dependencies**:
  - **RomM**: Self-hosted RomM instance version 4.9.0 or higher.
  - **RetroArch**: Installed via Steam (Steam AppID 1118310), Standalone package/installer/Flatpak (`org.libretro.RetroArch`), or RetroDECK Flatpak (`net.retrodeck.retrodeck`).
  - **Steam**: Steam client installed with at least one logged-in user profile.
