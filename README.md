<h1 align="center">romm-steam-sync</h1>
<h3 align="center">A desktop RomM client for syncing your library to Steam</h3>

romm-steam-sync is a desktop application that seamlessly connects your self-hosted [RomM](https://github.com/rommapp/romm) retro gaming library directly to Steam on Windows, macOS (coming soon), and Linux. It automatically organizes your games into Steam collections, downloads high-resolution artwork, and launches titles through RetroArch or RetroDECK with a single click. With on-demand downloading and save file synchronization, you can play your classic collection anywhere while keeping your saves and playtime in sync.

> [!WARNING]
> This software is still a work in progress and is in a very alpha state. I strongly recommend following the backup steps listed below before running it. Please file any issues you encounter in the issue tracker. Also check the [compatibility matrix](docs/compatibility.md) to see if the cores you are using are supported.

---

## Features

- **Automated Steam Library Sync**: Synchronizes RomM platforms into Steam as non-Steam shortcuts with native collection categories.
- **High-Resolution Artwork**: Automatically fetches portrait posters, hero banners, logos, and icons using SteamGridDB.
- **On-Demand ROM Downloads**: Conserves local disk space by downloading games from your RomM server only when you click "Play" in Steam, complete with automatic archive extraction for compressed files (.zip, .7z, .tar) for platforms that cannot play archives.
- **Bidirectional Save & Playtime Sync**: Syncs save states (coming soon), cartridge saves/memory cards, and play sessions back and forth with RomM using [Gavel's](https://github.com/danielcopper/romm-gavel) normative decision engine and specialized memory card strategy handlers. Ideally save strategies are aligned with other major RomM clients so that you can play your games on any platform.
- **Multi-Version Game Groups**: Combines regional variants, revisions, and multi-disc releases into a single Steam shortcut with an interactive version selection launcher.
- **Broad RetroArch Compatibility**: Supports RetroArch across all major distribution flavors (Steam release, standalone installer, Flatpak) as well as RetroDECK on Linux and Steam Deck.
- **Steam Safety & Rollback Guards**: Monitors running processes to alert you before modifying Steam configuration files, with automated pre-sync backups and one-click rollback support.

---

## Installation & Setup

### Requirements

Before using romm-steam-sync, ensure you have the following prerequisites configured:

1. **Active RomM Instance**: A running [RomM](https://github.com/rommapp/romm) server (version 4.9.0 or newer recommended) with API access enabled and an API key generated from your user profile.
2. **Steam Client**: An installed Steam desktop client with at least one existing logged-in user profile.
3. **Emulator Setup**: Either [RetroArch](https://github.com/libretro/RetroArch) (installed via Steam, standalone installer, or Flatpak) or [RetroDECK](https://retrodeck.net/) (Flatpak) configured with the necessary libretro cores for your platforms.
4. **Python**: Python 3.9 or higher (if running from source).

### Manual Steam Configuration Backup

Before running any synchronization tool that modifies Steam library shortcuts, it is strongly recommended to create a manual backup of your Steam user configuration directory.

While romm-steam-sync creates automated timestamped backups before applying changes, making your own manual copy provides an extra layer of protection.

#### 1. Close Steam
Ensure the Steam desktop client is completely shut down before copying or modifying configuration files.
- On Windows: Right-click the Steam system tray icon and select **Exit Steam**, or end the process via Task Manager.
- On macOS: Quit Steam from the menu bar or dock.
- On Linux: Exit Steam via system tray or run `killall steam`.

#### 2. Locate Your Steam User Directory
Locate your Steam profile directory based on your operating system:

| Platform | Path |
| :--- | :--- |
| **Windows** | `C:\Program Files (x86)\Steam\userdata\<your_user_id>\config\` |
| **macOS** | `~/Library/Application Support/Steam/userdata/<your_user_id>/config/` |
| **Linux (Native)** | `~/.local/share/Steam/userdata/<your_user_id>/config/` |
| **Linux (Flatpak)** | `~/.var/app/com.valvesoftware.Steam/data/Steam/userdata/<your_user_id>/config/` |

> Note: If multiple numerical folders exist under `userdata`, locate the directory corresponding to your active Steam Account ID.

#### 3. Copy Important Configuration Files
Copy the following files and folders from your Steam `config/` folder into a safe backup directory (e.g., on your Desktop or in an external backup folder):
- `shortcuts.vdf` (Stores all non-Steam shortcuts)
- `cloudstorage/` (Directory storing modern Steam collection definitions)
- `grid/` (Directory containing custom artwork banners, posters, and logos)
- `localconfig.vdf` (Legacy Steam desktop collection configuration)

If you ever wish to restore your original Steam configuration, exit Steam and copy these backed-up items back into your Steam `config/` directory.

### First Launch

Run the executable to start the Onboarding Wizard, which will guide you through connecting to your RomM instance, detecting RetroArch or RetroDECK, setting up optional SteamGridDB artwork keys, choosing platforms, and running your initial sync. For best results make sure Steam is closed until the initial sync has completed. 

Subsequent launches will open directly to the main application window where you can access advanced settings and run manual syncs. You can also manage installed games from this app. When new updates are available you can download them from the [GitHub Releases](https://github.com/cupajoe24/romm-steam-sync/releases) page. Opening the main app once will also update the launcher.

### (Alternative) Running from Source

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/cupajoe24/romm-steam-sync.git
   cd romm-steam-sync
   ```

2. **Create and Activate a Virtual Environment**:
   - **Windows**:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - **macOS / Linux**:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Install Dependencies**:
   ```bash
   pip install -e .
   ```

4. **Launch the Application**:
   ```bash
   romm-steam-sync
   ```
   Or execute directly with Python:
   ```bash
   python -m romm_steam_sync
   ```

---

## Documentation

For in-depth architectural details, compatibility lists, and component guides, explore the `docs/` directory:
- [Documentation Index](docs/README.md)
- [Project Overview](docs/overview.md)
- [Console & Core Compatibility Matrix](docs/compatibility.md)
- [Steam Shortcuts & VDF Architecture](docs/architecture/steam-shortcuts-vdf.md)
- [RetroArch Multi-Flavor Architecture](docs/architecture/retroarch-flavors-and-paths.md)
- [Save File & Playtime Sync Architecture](docs/architecture/save-file-sync-architecture.md)
- [Launcher & On-Demand Downloads](docs/architecture/launcher-and-on-demand-downloads.md)
- [Development Roadmap](docs/roadmap.md)

---

## Acknowledgements

romm-steam-sync builds upon and takes inspiration from outstanding open-source projects in the retro gaming ecosystem:

- **[RomM (Rom Manager)](https://github.com/rommapp/romm)**: The self-hosted retro games library manager that makes centralized ROM, save, and metadata organization possible.
- **[Tender (formerly `decky-romm-sync`)](https://github.com/danielcopper/romm-tender)**: Steam Deck Decky Loader plugin for RomM. romm-steam-sync adapts Tender's domain concepts, database design, and RomM API interactions for standalone desktop environments across Windows, macOS, and Linux.
- **[Gavel (`romm-gavel`)](https://github.com/rommapp/romm)**: The save synchronization engine and specification that provides conflict-safe bidirectional save syncing between local emulators and the RomM server.

---

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

