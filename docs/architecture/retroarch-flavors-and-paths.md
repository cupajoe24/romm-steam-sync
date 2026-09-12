# RetroArch Multi-Flavor Architecture & Path Resolution

## 1. Overview & Architectural Goals

**`romm-steam-sync`** relies on [RetroArch](https://github.com/libretro/RetroArch) to execute ROMs launched from Steam shortcuts or the desktop Library manager. Because RetroArch is distributed through multiple channels with radically different filesystem layouts, sandboxing boundaries, and execution models, `romm-steam-sync` implements a polymorphic adapter architecture located in `src/romm_steam_sync/adapters/retroarch/`.

### Supported Flavors
1. **Steam RetroArch (`steam`)**: The official Steam Store release (Steam AppID `1118310`), installed inside a Steam library folder (`steamapps/common/RetroArch`).
2. **Standalone RetroArch (`standalone`)**: The traditional standalone distribution installed via official installers (Windows `C:\RetroArch-Win64`), native package managers (`/usr/bin/retroarch` on Linux, Homebrew on macOS), or the official Libretro Flatpak (`org.libretro.RetroArch`).
3. **RetroDECK (`retrodeck`)**: The all-in-one emulation Flatpak ecosystem (`net.retrodeck.retrodeck`) designed for Linux desktops and the Steam Deck.

---

## 2. Adapter Class Hierarchy & Abstraction Layer

The adapter design decouples platform- and distribution-specific execution details from the rest of the application:

```
                      +-----------------------+
                      | BaseRetroArchAdapter  |  (Abstract Base Class)
                      +-----------------------+
                                  |
        +-------------------------+-------------------------+
        |                         |                         |
        v                         v                         v
+-----------------------+ +-----------------------+ +-----------------------+
| SteamRetroArchAdapter | |StandaloneRetroArchAd. | |   RetroDeckAdapter    |
+-----------------------+ +-----------------------+ +-----------------------+
```

### Core Responsibilities (`BaseRetroArchAdapter`)
Every flavor adapter implements the contract defined in [`BaseRetroArchAdapter`](../../src/romm_steam_sync/adapters/retroarch/base.py):
- **Binary Resolution (`resolve_binary()`)**: Locates the executable binary or verifies that the sandbox runner is callable.
- **Configuration Resolution (`resolve_cfg_path()`)**: Resolves the path to the primary `retroarch.cfg` file.
- **Core Search Directories (`get_core_search_dirs()`)**: Identifies directories containing dynamic libretro cores (`.dll` on Windows, `.so` on Linux, `.dylib` on macOS).
- **Core Path Resolution (`resolve_core_path(core_name)`)**: Finds the exact filesystem path to a specific libretro core library.
- **Save Directory Resolution (`resolve_save_directory(...)`)**: Determines where RetroArch reads and writes save RAM for a given ROM, respecting runtime config settings.
- **Launch Command Construction (`build_launch_command(...)`)**: Assembles command-line arguments to launch games cleanly.
- **Process Spawning & Window Management (`launch_game(...)`)**: Spawns the process, monitors its lifecycle, and brings the game window to the foreground on Windows.

---

## 3. Flavor Implementations

### A. Steam RetroArch Adapter (`SteamRetroArchAdapter`)
- **Distribution Model**: Installed through the Steam client as non-Steam shortcut runner or native Steam title.
- **Binary Locations**:
  - Windows: `<SteamLibrary>\steamapps\common\RetroArch\retroarch.exe`
  - Linux: `<SteamLibrary>/steamapps/common/RetroArch/retroarch`
  - macOS: `<SteamLibrary>/steamapps/common/RetroArch/RetroArch.app/Contents/MacOS/RetroArch`
- **Configuration**:
  - Windows: Reads `retroarch.cfg` in the installation folder or under user profile directories.
  - Linux/macOS: `<SteamLibrary>/steamapps/common/RetroArch/retroarch.cfg`.
- **Core Discovery**: Scans `steamapps/common/RetroArch/cores/` for downloaded DLC and manually installed cores.

### B. Standalone RetroArch Adapter (`StandaloneRetroArchAdapter`)
- **Distribution Model**: Native installations from libretro.com, OS repositories (APT, DNF, Pacman, Homebrew), or the standalone Flatpak (`org.libretro.RetroArch`).
- **Binary Locations**:
  - System PATH: Checks `shutil.which("retroarch")` and `shutil.which("org.libretro.RetroArch")`.
  - Windows: `C:\RetroArch-Win64\retroarch.exe`, `C:\Program Files\RetroArch-Win64\retroarch.exe`, `%APPDATA%\RetroArch\retroarch.exe`.
  - Linux Native: `/usr/bin/retroarch`, `/usr/local/bin/retroarch`.
  - Linux Flatpak: `flatpak run org.libretro.RetroArch`.
  - macOS: `/Applications/RetroArch.app/Contents/MacOS/RetroArch`, Homebrew binaries in `/opt/homebrew/bin/retroarch` or `/usr/local/bin/retroarch`.
- **Configuration**:
  - Windows: Directory of executable or `%APPDATA%\RetroArch\retroarch.cfg`.
  - Linux Native: `~/.config/retroarch/retroarch.cfg`.
  - Linux Flatpak: `~/.var/app/org.libretro.RetroArch/config/retroarch/retroarch.cfg`.
  - macOS: `~/Library/Application Support/RetroArch/retroarch.cfg`.

### C. RetroDECK Adapter (`RetroDeckAdapter`)
- **Distribution Model**: Sandboxed Flatpak container `net.retrodeck.retrodeck` primarily used on SteamOS and Linux desktop gaming setups.
- **Binary & Execution**:
  - RetroDECK wraps RetroArch inside its Flatpak container.
  - Execution invokes the Flatpak runner:
    ```bash
    flatpak run --command=retroarch net.retrodeck.retrodeck -L <core_path> "<rom_path>"
    ```
- **Configuration & State Paths**:
  - Manifest & Settings: `~/.var/app/net.retrodeck.retrodeck/config/retrodeck/retrodeck.json`.
  - RetroArch Config: `~/.var/app/net.retrodeck.retrodeck/config/retrodeck/retroarch/retroarch.cfg` (or legacy `~/.var/app/net.retrodeck.retrodeck/config/retroarch/retroarch.cfg`).
  - Cores: `~/.var/app/net.retrodeck.retrodeck/data/retrodeck/cores/` or `/app/lib/libretro/`.
  - Saves: Centralized under `~/.var/app/net.retrodeck.retrodeck/config/retrodeck/saves/`.
- **Health Diagnostics (`RetroDeckConfigHealth`)**:
  - Validates sandbox directory existence, Flatpak installation status, configuration readability, and core availability.
  - Reports diagnostic warnings to logs if RetroDECK paths are missing or misconfigured.

---

## 4. Dynamic Flavor Sniffing & Detection Pipeline

When `detect_retroarch_flavor()` is called without an explicit flavor, it evaluates candidate environments in strict priority order:

```
[Start Flavor Detection]
          |
          v
  Explicit Preference Set in Settings? (steam, standalone, retrodeck)
          |--- YES ---> Return Specific Flavor Adapter
          |
          NO
          v
  Configured Path Contains 'retrodeck'?
          |--- YES ---> Return RetroDeckAdapter
          |
          NO
          v
  Configured Path Contains 'steamapps' or '/steam/'?
          |--- YES ---> Return SteamRetroArchAdapter
          |
          NO
          v
  System PATH contains 'retroarch' or 'org.libretro.RetroArch'?
          |--- YES ---> Return StandaloneRetroArchAdapter
          |
          NO
          v
  Linux Host with '~/.var/app/net.retrodeck.retrodeck' Present?
          |--- YES ---> Return RetroDeckAdapter
          |
          NO
          v
  Standalone RetroArch found in Default OS Paths?
          |--- YES ---> Return StandaloneRetroArchAdapter
          |
          NO
          v
  Steam RetroArch found in Steam Library?
          |--- YES ---> Return SteamRetroArchAdapter
          |
          NO
          v
  Default Fallback: StandaloneRetroArchAdapter
```

Users can override detection at any time in **Settings** > **RetroArch Settings** > **Flavor** (`auto`, `steam`, `standalone`, `retrodeck`).

---

## 5. Centralized Path Resolver Facade (`RetroArchPathResolver`)

To avoid duplicating path resolution across views, launcher scripts, and save handlers, [`RetroArchPathResolver`](../../src/romm_steam_sync/adapters/retroarch_paths.py) provides a static facade wrapping the active flavor adapter:

```python
class RetroArchPathResolver:
    @classmethod
    def resolve_retroarch_binary(cls, configured_path: str = "") -> Optional[Path]: ...

    @classmethod
    def resolve_retroarch_cfg_path(cls, configured_path: str = "") -> Optional[Path]: ...

    @classmethod
    def get_core_search_dirs(cls, retroarch_path: str = "") -> List[Path]: ...

    @classmethod
    def resolve_core_path(cls, core_name: str, retroarch_path: str = "") -> Optional[Path]: ...
```

### Platform Normalization & Core Suffix Helpers
- `normalize_platform_slug(slug)`: Produces a 3-tuple `(raw_lowered, clean_hyphenated, clean_no_hyphen)` to match diverse platform identifiers across RomM and RetroArch (e.g. `playstation-2`, `ps2`, `playstation2`).
- `lookup_platform_mapping(mapping, slug)`: Resolves default cores or candidate lists using normalized slug variants.
- `get_core_suffix()`: Returns `.dll` (Windows), `.dylib` (macOS), or `.so` (Linux).
- `strip_core_suffix(name)` / `ensure_core_suffix(name)`: Strips or appends OS-specific dynamic library extensions safely.

---

## 6. Runtime Configuration & Save Directory Resolver (`RetroArchConfigAdapter`)

RetroArch provides multiple configuration settings that dictate where save RAM (`.srm`, `.sav`) is stored. Placing save files in the wrong folder leads to missing saves on launch.

[`RetroArchConfigAdapter`](../../src/romm_steam_sync/adapters/retroarch_config.py) parses `retroarch.cfg` and libretro `.info` files at runtime:

### Configuration Directives Handled
1. **`savefiles_in_content_dir` (`bool`)**:
   - When `true`, saves are stored directly in the folder alongside the ROM file.
2. **`savefile_directory` (`str`)**:
   - Custom base directory for save files (e.g. `C:\RetroArch-Win64\saves` or `default`).
   - If set to `"default"` or empty, defaults to the `saves/` folder inside RetroArch's base installation directory.
3. **`sort_savefiles_by_content_enable` (`bool`)**:
   - When `true`, creates a subfolder matching the ROM's parent folder name inside the base saves directory.
4. **`sort_savefiles_enable` (`bool`)**:
   - When `true`, organizes saves into subfolders named after the active libretro core (e.g. `saves/mGBA/`, `saves/Nestopia/`, `saves/Snes9x/`).

### Canonical Core Name Resolution via `.info` Metadata
When `sort_savefiles_enable` is enabled, RetroArch creates directory names matching the **canonical display name** of the core (e.g. `mGBA` rather than `mgba_libretro`).
- The adapter inspects the core's `.info` file in RetroArch's `info/` directory (`corename = "mGBA"`).
- If the `.info` file is missing or unreadable, the adapter falls back to `CORE_NAME_FALLBACKS` mapping known core stems to their exact folder names.

---

## 7. Process Execution, Timing & Window Management

When launching games:
1. **Monotonic Timing (`time.monotonic()`)**:
   - Session duration calculations use `time.monotonic()` instead of wall-clock time (`time.time()`), preventing skew from system clock adjustments, daylight savings transitions, or NTP syncs.
2. **Win32 Window Foregrounding (`bring_process_window_to_foreground`)**:
   - On Windows, launching an emulator from a background script wrapper can result in the game window remaining behind other open windows.
   - The launcher invokes `user32.EnumWindows` and `user32.SetForegroundWindow` targeting RetroArch's PID to restore and focus the window immediately.
3. **Clean Exit Codes & Process Monitoring**:
   - Spawns subprocess with `creationflags=subprocess.CREATE_NO_WINDOW` on Windows for silent background wrapper execution.
   - Monitors exit status to ensure post-launch save synchronization and playtime recording execute reliably upon process termination.
