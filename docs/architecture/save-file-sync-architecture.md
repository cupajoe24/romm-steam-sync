# Save File & Playtime Synchronization Architecture

## 1. Overview

`romm-steam-sync` provides bidirectional save file synchronization between RetroArch and RomM server instances, aligned with Tender (`decky-romm-sync`) specifications. Saves are pulled before game execution (pre-launch) and pushed after game exit (post-launch), ensuring cross-device save continuity across Windows, macOS, Linux, and Steam Deck.

---

## 2. RetroArch Save File Extensions Matrix

RetroArch cores store save RAM, Flash RAM, Controller Pak, and RTC clock states alongside ROM files or in RetroArch's centralized `saves/` directory (or core-specific subfolders such as `saves/Mupen64Plus-Next/`). The save discovery module scans candidate directories recursively and monitors the following extensions:

| System / Category | Extension | Description |
| :--- | :--- | :--- |
| **Standard Core SRAM** | `.srm` | Default libretro Battery RAM save file |
| **Standard Battery Save** | `.sav` | Standard raw battery save file |
| **Real-Time Clock** | `.rtc` | Real-time clock state file |
| **Nintendo 64** | `.eep`, `.fla`, `.sra`, `.mpk` | EEPROM, Flash RAM, SRAM, and Controller Pak saves |
| **Nintendo DS** | `.dsv` | DeSmuME / melonDS save file |
| **Sega Saturn** | `.bkr`, `.bcr`, `.smpc` | Internal memory backup & expansion card saves |
| **Sega CD / Mega CD** | `.brm` | Internal CD backup RAM save file |
| **PlayStation (PSX)** | `.mcd`, `.gme` | Memory card images |
| **Neo Geo Pocket Color** | `.flash`, `.ngf` | Internal flash RAM saves |
| **Commodore Amiga** | `.nvr` | Non-volatile RAM save files |

---

## 3. Save File Content Hashing Algorithm

To determine byte identity between local save files and RomM server save entries without downloading unneeded files, `romm-steam-sync` replicates RomM's internal MD5 content hashing scheme:

1. **Single-File Save**:
   - `content_hash = md5(file_bytes)`
2. **Zip Container Save** (multi-file save set):
   - For each entry inside the zip archive, calculate `md5(entry_bytes)`.
   - Sort entries alphabetically by filename (`name`).
   - Format lines as `name:md5_hash\n`.
   - `content_hash = md5(joined_lines)`

---

## 4. Bidirectional Save Negotiation Lifecycle & Slot Alignment

### Default Save Slot (`autosave`)
To maintain 100% cross-device compatibility with Tender (`decky-romm-sync`) on Steam Deck and official RomM web/mobile clients, saves are tagged in the canonical **`autosave`** slot (`slot="autosave"`). The default slot name can also be configured via `AppSettings.default_slot` in the desktop GUI Settings view.

### RomM Save API Wire Contract
- `GET /api/saves?rom_id={id}&slot={slot}`: Returns existing save entries for the ROM in the active slot (prioritizing `slot="autosave"`).
- `POST /api/saves?rom_id={id}&emulator={emulator}&slot={slot}`: Creates a new save entry in RomM. The multipart form field name MUST be set to **`saveFile`** (`files={"saveFile": (filename, f, "application/octet-stream")}`).
- `PUT /api/saves/{id}?rom_id={id}&emulator={emulator}&slot={slot}`: Updates save content for an existing save entry in RomM.
- `GET /api/saves/{id}/content`: Downloads binary save content.
- `POST /api/sync/negotiate`: Opens device sync session.
- `POST /api/play-sessions`: Ingests play session duration data.


### Gavel Decision Engine & Normative Spec Alignment (`romm-gavel`)

`romm-steam-sync` embeds Gavel (`romm-gavel`), the normative save-sync specification engine created for RomM/Tender clients (`gavel/ladder.py`, `gavel/decision_table.py`).

#### 1. Identity Check Disjunction (`local_matches_server`)
- **Provenance (Primary)**: `(local_hash == last_sync_hash) AND (last_sync_server_hash == remote_content_hash)`. Compares two server-produced digests to verify identity even if client and server MD5 schemes drift over time.
- **Parity (Fallback)**: `local_hash == remote_content_hash`. Used when no baseline record exists.

#### 2. Corrupt / Truncated Local Save Guard (`is_implausibly_shrunken`)
- Prevents uploading 0-byte saves or saves whose size has dropped below 50% of the recorded baseline size (`SHRINK_RATIO = 0.5`). If a remote save exists, automatically falls back to **DOWNLOAD** to protect against save loss.

#### 3. HTTP 409 Upload Conflict Resolution Ladder (`resolve_upload_conflict`)
- When an automatic upload POST returns HTTP 409 (server head moved):
  - **L1**: If local file is unchanged since baseline (`local_hash == last_sync_hash`), downgrades to **DOWNLOAD**.
  - **L2**: If identity check passes against new server head, downgrades to **DOWNLOAD**.
  - Otherwise flags **CONFLICT** for user resolution.

#### 4. Timestamp Precision Tolerance (2.0s Delta)
- Filesystems differ significantly in timestamp resolution (FAT32 stores mtime with 2-second precision, while ext4 and NTFS store sub-second timestamps).
- `compute_sync_action` applies a 2.0-second tolerance window:
  - If `local_mtime > remote_epoch + 2.0`: resolves to **UPLOAD**.
  - If `remote_epoch > local_mtime + 2.0`: resolves to **DOWNLOAD**.
  - Within 2.0 seconds: treats minor timestamp drift as non-conflicting.

#### 5. Baseline Bookkeeping & Persistence (`RomSaveSyncState` / `FileSyncState`)
- At every successful sync boundary (upload acknowledged, download completed, or baseline adopted), records baseline metadata in SQLite table `rom_save_sync_states`:
  - `last_sync_hash`: Client's local file hash at sync time.
  - `last_sync_server_hash`: RomM server's `content_hash` recorded verbatim.
  - `last_sync_local_size`: Local save file size in bytes.
  - `last_sync_local_mtime`: Local modification timestamp.
  - `tracked_save_id`: Server save ID.

#### 6. Baseline Migration Utility (`scripts/migrate_gavel_baselines.py`)
- Provides a standalone migration script to scan local installed game save files, query RomM for remote save records, and seed initial Gavel baselines into `%APPDATA%\romm-steam-sync\romm_steam_sync.db`.

---

## 5. Playtime Tracking & Session Ingestion

Whenever `romm-steam-sync-launcher` exits after running RetroArch:
1. Calculates session duration using monotonic timing: `duration_ms = (exit_monotonic - start_monotonic) * 1000`.
2. Emits session payload with persistent client `device_id` (`settings.json`):
   ```json
   {
     "device_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
     "sessions": [
       {
         "rom_id": 123,
         "start_time": "2026-08-29T21:45:08Z",
         "end_time": "2026-08-29T21:46:03Z",
         "duration_ms": 55000
       }
     ]
   }
   ```
3. POSTs payload to RomM `POST /api/play-sessions` to update RomM playtime aggregation and "Recently Played" activity.

---

## 6. Save Strategy Abstraction Layer

To accommodate platform-specific save behaviors (cartridge SRAM, virtual memory cards, and complex emulated NAND/SDMC folder hierarchies), save sync behavior is abstracted into pluggable strategies organized inside `src/romm_steam_sync/service_layer/save_strategies/`.

### Package Layout
- `save_strategies/base.py`: Defines `BaseSaveStrategy` abstract base class.
- `save_strategies/default_save_per_game.py`: Implements `DefaultSavePerGameStrategy` (`name = "default_save_per_game"`).
- `save_strategies/shared_memory_card.py`: Implements `SharedMemoryCardStrategy` (`name = "shared_memory_card"`).
- `save_strategies/memory_card_per_game.py`: Implements `MemoryCardPerGameStrategy` (`name = "memory_card_per_game"`).
- `save_strategies/handlers/base.py`: Defines `BaseMemoryCardHandler` abstract base class.
- `save_strategies/handlers/citra.py`: Implements `Citra3DSHandler` for Nintendo 3DS emulated SDMC title saves.
- `save_strategies/handlers/dolphin.py`: Implements `BaseDolphinHandler` defining shared disc container extraction (ISO, WBFS, RVZ, WIA, CISO, GCZ) and region resolution.
- `save_strategies/handlers/dolphin_gamecube.py`: Implements `DolphinGameCubeHandler` for GameCube `.gci` memory cards in `User/GC/<Region>/Card A/`.
- `save_strategies/handlers/dolphin_wii.py`: Implements `DolphinWiiHandler` for Nintendo Wii emulated NAND title saves in `User/Wii/title/00010000/<TitleIDHex>/data/`.
- `save_strategies/registry.py`: Holds `CORE_SAVE_STRATEGY_MAP`, `SAVE_STRATEGY_REGISTRY`, and strategy resolver functions.
- `save_strategies/__init__.py`: Package entry point re-exporting strategy abstractions.

### Core Strategy Mapping & Resolution

| Platform / System | Matched Core Identifiers & Slugs | Assigned Save Strategy |
| :--- | :--- | :--- |
| **NES** | `nestopia_libretro`, `fceumm_libretro`, `mesen_libretro` | `default_save_per_game` |
| **SNES** | `snes9x_libretro`, `bsnes_libretro`, `snes9x2010_libretro` | `default_save_per_game` |
| **Nintendo 64 (N64)** | `mupen64plus_next_libretro`, `parallel_n64_libretro` | `default_save_per_game` |
| **Game Boy / GBC** | `sameboy_libretro`, `gambatte_libretro` | `default_save_per_game` |
| **Game Boy Advance (GBA)** | `mgba_libretro`, `vba_next_libretro`, `gpsp_libretro` | `default_save_per_game` |
| **Nintendo DS (NDS)** | `melonds_libretro`, `desmume_libretro` | `default_save_per_game` |
| **PlayStation 2 (PS2)** | `pcsx2_libretro`, `pcsx2`, `lrps2_libretro`, `lrps2`, `playstation2`, `ps2` | `shared_memory_card` |
| **Dreamcast / Arcade** | `flycast_libretro`, `flycast`, `flycast_gles2_libretro`, `reicast_libretro`, `reicast`, `dc`, `dreamcast`, `sega-dreamcast`, `naomi`, `naomi2`, `naomigd`, `atomiswave` | `shared_memory_card` |
| **Nintendo GameCube** | `dolphin_libretro`, `dolphin`, `dolphin_launcher`, `gc`, `ngc`, `gamecube` | `memory_card_per_game` |
| **Nintendo Wii** | `dolphin_libretro`, `dolphin`, `wii` | `memory_card_per_game` |
| **Nintendo 3DS** | `citra_libretro`, `citra`, `3ds` | `memory_card_per_game` |

- **Default Strategy**: Any unmapped core automatically defaults to `"default_save_per_game"`.

---

## 6.1 Strategy Implementations & Handlers

### 1. Default Save Per Game Strategy (`default_save_per_game`)
- **Applies to**: NES, SNES, N64, GB, GBC, GBA, NDS, Genesis, SMS, PS1.
- **Runtime Save Resolution (`RetroArchConfigAdapter`)**:
  - Instead of guessing where RetroArch places saves, the strategy delegates to `RetroArchConfigAdapter` (`adapters/retroarch_config.py`).
  - Reads `retroarch.cfg` runtime flags (`savefiles_in_content_dir`, `sort_savefiles_by_content_enable`, `sort_savefiles_enable`, `savefile_directory`) and libretro core `.info` files.
  - Automatically resolves subfolders like `saves/mGBA/` or `saves/Nestopia/` before evaluating sync actions.

### 2. Shared Memory Card Strategy (`shared_memory_card`)
- **Applies to**: PlayStation 2 (`pcsx2_libretro`, `lrps2_libretro`), Sega Dreamcast (`flycast_libretro`).
- **Local App Card Storage**: Stored per game in AppData storage: `<AppData>/romm-steam-sync/memcards/<system_folder>/<game_name>/<card_filename>` (e.g. `%APPDATA%\romm-steam-sync\memcards\pcsx2\Final Fantasy X\Mcd001.ps2`).
- **Canonical Filename Standardization (`Mcd001.ps2`)**:
  - The target memory card file inside RetroArch's `system/pcsx2/memcards/` and in app local storage is strictly standardized to the core's default card filename (`Mcd001.ps2` for PS2). Remote save display names are normalized to `Mcd001.ps2`.
- **Pre-Launch Swapping**:
  - Freshness comparison (`compute_sync_action`) is calculated strictly between RomM server saves and app local storage. The existing file in RetroArch is excluded from freshness calculation.
  - Copies active card into RetroArch `system/pcsx2/memcards/Mcd001.ps2`.
- **Post-Launch Cleanup**:
  - Copies modified card back to app local storage, uploads to RomM, and unlinks cards from `system/pcsx2/memcards/` with a process lock retry loop.

### 3. Memory Card Per Game Strategy (`memory_card_per_game`)
Coordinates discrete save containers with registered `BaseMemoryCardHandler` implementations:

#### A. Dolphin GameCube Handler (`DolphinGameCubeHandler`)
- **Storage Location**: `RetroArch/saves/dolphin-emu/User/GC/<Region>/Card A/`. Supported regions: `USA`, `EUR`, `JAP`, `KOR`.
- **Header Parsing**: Reads raw 0x60 boot header at `0x00` (ISO/GCM), RVZ/WIA embedded uncompressed disc header at `0x48`, CISO/CSO block 0, or decompressed GCZ block tables.
- **Region Detection**: Inspects GameCode 4th character (`'E'/'U'/'A'` -> `USA`, `'P'/'D'/'F'` -> `EUR`, `'J'` -> `JAP`, `'K'/'W'` -> `KOR`).
- **GCI Binary Inspection**: Correlates `.gci` files via 4-byte GameCode at `0x00`, 2-byte MakerCode at `0x04`, and 32-byte internal name at `0x08`.
- **Multi-Disc Linking**: Strips `(Disc 1)`, `(Disc 2)` tags from filenames so all discs of a multi-disc title (e.g. *Resident Evil 4*) link to the same shared `.gci` memory card save in `Card A`.
- **Auto-Migration**: Automatically migrates legacy saves located next to the ROM into `User/GC/<Region>/Card A/`.

#### B. Dolphin Nintendo Wii Handler (`DolphinWiiHandler`)
- **Storage Location**: Dolphin emulated NAND title directory: `User/Wii/title/00010000/<TitleIDHex>/data/` (containing files such as `banner.bin` and `save.dat`).
- **Disc Header Parsing**: Inspects Wii disc magic `\x5d\x1c\x9e\xa3` at offset `0x18` across ISO, WBFS, RVZ, WIA, CISO, and GCZ container formats.
- **Title ID Derivation**:
  - Extracts 4-to-6 character Game ID (e.g. `RMCE01` for *Mario Kart Wii*).
  - Encodes the 4-byte Game ID to hex to form the lower 32-bit Title ID (`524D4345`), yielding full Wii Title ID `00010000524D4345`.
- **Zip Archive Consolidation & Unpacking**:
  - Pre-launch: Unpacks downloaded RomM `.zip` save archive safely into `User/Wii/title/00010000/<TitleIDHex>/data/`.
  - Post-launch: Discovers modified save files in the title directory, bundles them into a deterministic `.zip` archive, and uploads to RomM.

#### C. Citra Nintendo 3DS Handler (`Citra3DSHandler`)
- **Storage Location**: Citra emulated SDMC NAND directory: `sdmc/Nintendo 3DS/00000000000000000000000000000000/<ID1>/title/00040000/<TitleIDLow>/data/00000001/` (containing save data files like `main`).
- **Container Parsing**: Inspects NCSD cartridge images (`.3ds`, `.cci`) and NCCH partitions (`.cxi`, `.app`) at magic offset `0x100` or `0x00` to extract the 64-bit Title ID, Product Code, Maker Code, and Region.
- **Save Consolidation & Unpacking**:
  - Pre-launch: Unpacks RomM save archive into `data/00000001/`.
  - Post-launch: Bundles modified save files from `data/00000001/` into a deterministic `.zip` archive and uploads to RomM.