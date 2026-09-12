# Steam Shortcuts & VDF Architecture

## 1. Overview

Because `romm-steam-sync` runs outside Decky Loader as a standalone application on Windows, macOS, and Linux, it manages Steam non-Steam shortcuts by directly parsing, mutating, and serializing Steam's binary `shortcuts.vdf` file and placing grid artwork in Steam's user configuration folder.

---

## 2. Cross-Platform Steam User Directories

The app detects Steam user profile directories across platforms:

| Operating System | Steam User Directory Path |
| :--- | :--- |
| **Windows** | `C:\Program Files (x86)\Steam\userdata\<user_id>\config\` |
| **macOS** | `~/Library/Application Support/Steam/userdata/<user_id>/config/` |
| **Linux (Native)** | `~/.local/share/Steam/userdata/<user_id>/config/` |
| **Linux (Flatpak)** | `~/.var/app/com.valvesoftware.Steam/data/Steam/userdata/<user_id>/config/` |

If multiple `<user_id>` folders exist, `romm-steam-sync` allows the user to select their active Steam profile in the GUI.

---

## 3. Binary `shortcuts.vdf` Format & AppID Derivation

### VDF Binary Structure
Steam stores non-Steam shortcuts as binary KeyValues in `shortcuts.vdf`:
- `AppName` (string): Display name of the game (e.g. `Super Mario World`).
- `Exe` (string): Path to `romm-steam-sync-launcher` executable (unquoted).
- `StartDir` (string): Working directory for the launcher.
- `LaunchOptions` (string): Command line flags passed to the launcher (e.g., `--rom-id 123 --platform snes`).
- `icon` (string): Path to icon PNG in `grid/`.
- `appid` (int32): Signed 32-bit integer assigned by Steam or computed deterministically.

### Non-Steam AppID Generation & Normalization
For grid artwork association and collection mapping, Steam calculates non-Steam AppIDs using a deterministic algorithm based on the executable path and display name:
1. `clean_exe = Exe.strip('"')` (surrounding quotes must be stripped before CRC calculation to prevent mismatch between unquoted launcher calls and quoted VDF `Exe` strings).
2. `crc = CRC32(clean_exe + AppName)`
3. `appid_32 = crc | 0x80000000` (signed 32-bit int for VDF, unsigned uint32 `appid_32 & 0xFFFFFFFF` for CloudStorage collections).
4. `appid_64 = (appid_32_unsigned << 32) | 0x02000000` (64-bit uint for legacy `localconfig.vdf`).

The 32-bit/64-bit integer representation is converted to unsigned hex/decimal string format for grid filenames.

### Multi-Version Sibling Group Shortcuts
When a game has multiple versions, revisions, or discs in RomM:
- **Single Shortcut**: Only **one** shortcut is created in `shortcuts.vdf` per game group.
- **Canonical Title**: The shortcut's `AppName` is stripped of disc/revision noise using `canonical_group_name()` (e.g. `Dark Cloud 2`).
- **Representative Binding**: The shortcut's `LaunchOptions` (`--rom-id <id> --platform <slug>`) targets the active representative ROM resolved via 1G1R (or user preference), while all sibling variants are stored in the local SQLite database.
- **Shared Artwork**: Grid artwork in `grid/` is downloaded once for the canonical game shortcut AppID.

---


## 4. Steam Library Collections (Modern CloudStorage vs. Legacy `localconfig.vdf`)

### Modern Steam Collection Storage Engine
Recent versions of the Steam Desktop client and Steam Deck interface **no longer use `localconfig.vdf`** for library collections. Instead, Steam persists custom collections in its local CloudStorage engine:

- **Storage File**: `<Steam>/userdata/<user_id>/config/cloudstorage/cloud-storage-namespace-1.json`
- **Version Manifest**: `<Steam>/userdata/<user_id>/config/cloudstorage/cloud-storage-namespaces.json`

Each collection entry in `cloud-storage-namespace-1.json` is stored as a 2-element tuple `[key_string, info_dict]`:

```json
[
  "user-collections.user-collection-playstation-2",
  {
    "key": "user-collections.user-collection-playstation-2",
    "timestamp": 1787078148,
    "value": "{\"id\":\"user-collection-playstation-2\",\"name\":\"PlayStation 2\",\"added\":[2149452156,2157069074],\"removed\":[]}",
    "version": "2763",
    "conflictResolutionMethod": "custom",
    "strMethodId": "union-collections"
  }
]
```

- **AppID Array**: The `added` field inside `value` contains a JSON array of unsigned 32-bit AppID integers (`appid_32 & 0xFFFFFFFF`).
- **Version Increment**: When updating `cloudstorage` files externally, the namespace version header in `cloud-storage-namespaces.json` is incremented (e.g. `[[1, "2763"], [3, "0"]]`) so Steam detects external changes immediately.

### Dual-Sync Compatibility & Backup Strategy
To ensure maximum compatibility across legacy Steam clients, modern Steam Desktop, and Steam Deck:
1. **Dual-Sync Writing**: `romm-steam-sync` updates both modern `cloudstorage` JSON manifests and legacy `localconfig.vdf` KeyValues during synchronization.
2. **Backup & Rollback Scope**: `SteamBackupManager` backs up and restores `shortcuts.vdf`, `localconfig.vdf`, and the `cloudstorage/` directory tree together.

---

## 5. Grid Artwork Management

Artwork files fetched from SteamGridDB (or RomM cover art fallback) are stored in `<Steam>/userdata/<user_id>/config/grid/`:

| Asset Type | Filename Pattern | Target Resolution | Source Priority |
| :--- | :--- | :--- | :--- |
| **Portrait Grid (Cover)** | `<appId>p.png` | 600x900 (2:3) | SteamGridDB (top-rated) -> RomM Cover Fallback |
| **Hero Banner** | `<appId>_hero.png` | 1920x620 | SteamGridDB (top-rated) |
| **Logo Overlay** | `<appId>_logo.png` | 800x450 (Transparent PNG) | SteamGridDB (top-rated) |
| **Wide Grid (Horizontal)** | `<appId>.png` | 920x430 | SteamGridDB (top-rated) -> RomM Cover Fallback |
| **Icon** | `<appId>_icon.png` | 256x256 | SteamGridDB (top-rated) |

When a SteamGridDB API Key is configured in settings, `romm-steam-sync` queries SGDB by IGDB ID or display name to download all 5 custom artwork types. If no key is set or SGDB is unavailable, it gracefully falls back to RomM cover art.

---

## 6. Steam Process Lock & Safe Re-open Guard

> [!CAUTION]
> **Steam Memory Overwrite Hazard**: When Steam is running, it holds `shortcuts.vdf` in memory. Any external file write to `shortcuts.vdf` while Steam is active will be silently overwritten when Steam exits.

To ensure safety and reliability, `romm-steam-sync` implements an explicit **Steam Close Guard**:

```
[GUI Sync Initiated]
        |
        v
 Is Steam Running? --- YES ---> [Display Alert Modal]
        |                       "Please close Steam to continue sync"
        |                                |
        NO                               v
        |                     [User Closes Steam]
        +--------------------------------+
        |
        v
[1. Mutate & Write shortcuts.vdf]
[2. Write Grid Artwork Files]
[3. Commit SQLite Aggregate Updates]
        |
        v
[Display Success Notification Modal]
"Sync completed! It is now safe to re-open Steam."
```

### Safety Rules
1. Before any VDF write or delete operation, inspect running processes for `steam` / `steam.exe`.
2. If Steam is detected, display a clear prompt asking the user to close Steam.
3. Wait for process exit confirmation before writing or removing changes.
4. Notify the user as soon as write operations finish, informing them that Steam can be launched safely.

---

## 7. Library Cleanup & Reverse Sync Protocol

In addition to forward library synchronization down to Steam, `romm-steam-sync` provides reverse-sync capabilities in the **Cleanup & Restore** view (`sync_service.remove_synced_library` and `remove_all_synced_libraries`):

```
[Cleanup Initiated (Selected Library or All)]
                   |
                   v
         Is Steam Running? --- YES ---> [Display Alert Modal]
                   |                    "Please close Steam before proceeding"
                   |                                |
                   NO                               v
                   |                     [User Closes Steam]
                   +--------------------------------+
                   |
                   v
   [1. Create Automatic Steam VDF Backup]
   [2. Filter & Update shortcuts.vdf]
   [3. Delete Matching Grid Artwork Files]
   [4. Remove Collections from localconfig.vdf & cloudstorage/]
   [5. Delete ROM Records from SQLite DB]
                   |
                   v
   [Display Cleanup Success Notification]
```

### Deletion Procedure Details
1. **Shortcut Removal**: Parses `shortcuts.vdf` and filters out entries where tags contain `"RomM"` and match the target collection/platform (or all RomM shortcuts when removing all libraries).
2. **Artwork Purge**: Computes AppIDs for deleted shortcuts and unlinks `<appId>.png`, `<appId>p.png`, and `<appId>_icon.png` from `<Steam>/userdata/<user_id>/config/grid/`.
3. **Steam Collection Pruning**: Updates `localconfig.vdf` `CloudCollections` and `cloudstorage/cloud-storage-namespace-1.json` to remove `user-collection-<slug>` and update/prune `user-collection-romm`. Increments `cloud-storage-namespaces.json` version.
4. **SQLite State Cleanup**: Invokes `RomRepository.delete_by_platform(platform_slug)` or `delete_all()`.
5. **Safety Backups**: Creates a pre-cleanup rolling backup in `SteamBackupManager` before mutating any files, ensuring cleanups can be reversed using the Rollback section.