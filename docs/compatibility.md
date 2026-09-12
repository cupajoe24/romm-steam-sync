# Console & Platform Compatibility

This document details the compatibility status of **`romm-steam-sync`** across major home and handheld video game consoles from **Nintendo**, **Sega**, and **Sony** that have a supported RetroArch libretro core.
---

## Compatibility Legend

| Symbol | Status | Definition |
| :---: | :--- | :--- |
| ✅ | **Tested** | Explicitly supported and verified. |
| ☑️ | **Supported** | Supported but not verified (default core mapping / save strategy configured). |
| ❔ | **Potential** | Not explicitly configured, but may work via RetroArch custom core mappings or user configuration. |
| ❌ | **Unsupported** | Not supported (no functional RetroArch core available, hardware lacks save capability, or emulator does not exist). |

---

## Master Compatibility Table

| Console / Platform | RetroArch Core | Launch Games | Sync Saves |
| :--- | :--- | :---: | :---: |
| **Nintendo** | | | |
| NES / Famicom | `nestopia_libretro` | ✅ | ✅ |
| Game Boy *(Handheld)* | `sameboy_libretro` | ✅ | ✅ |
| Super Nintendo (SNES) / Super Famicom | `snes9x_libretro` | ✅ | ✅ |
| Nintendo 64 (N64) | `mupen64plus_next_libretro` | ✅ | ✅ |
| Game Boy Color (GBC) | `sameboy_libretro` | ✅ | ✅ |
| Game Boy Advance (GBA) | `mgba_libretro` | ✅ | ✅ |
| Nintendo GameCube | `dolphin_libretro` | ✅ | ✅ |
| Nintendo DS (NDS) | `melonds_libretro` | ✅ | ✅ |
| Nintendo Wii | `dolphin_libretro` | ✅ | ✅ |
| Nintendo 3DS | `citra_libretro` | ✅ | ✅ |
| Wii U | `cemu_libretro` | ❔ | ❔ |
| **Sega** | | | |
| Sega Master System (SMS) | `genesis_plus_gx_libretro` | ☑️ | ☑️ |
| Sega Genesis / Mega Drive | `genesis_plus_gx_libretro` | ☑️ | ☑️ |
| Sega Game Gear | `genesis_plus_gx_libretro` | ☑️ | ☑️ |
| Sega CD / Mega-CD | `genesis_plus_gx_libretro` | ☑️ | ☑️ |
| Sega 32X | `picodrive_libretro` | ☑️ | ☑️ |
| Sega Saturn | `beetle_saturn_libretro` | ☑️ | ☑️ |
| Sega Nomad | `genesis_plus_gx_libretro` | ☑️ | ☑️ |
| Sega Dreamcast | `flycast_libretro` | ✅ | ✅ |
| **Sony** | | | |
| PlayStation (PS1 / PSX) | `pcsx_rearmed_libretro` | ✅ | ✅ |
| PlayStation 2 (PS2) | `pcsx2_libretro` | ✅ | ✅ |
| PlayStation Portable (PSP) | `ppsspp_libretro` | ❔ | ❔ |
| PlayStation 3 (PS3) | `rpcs3_libretro` | ❌ | ❔ |
| PlayStation Vita (PS Vita)| `vitaquake2_libretro` | ❌ | ❔ |

---

## Architectural Details & Save Sync Strategies

`romm-steam-sync` routes save synchronization through specialized strategy engines depending on the platform architecture:

### 1. `default_save_per_game` (Standard Cartridges & Disc Systems)
- **Platforms**: NES, SNES, N64, Game Boy, GBC, GBA, Nintendo DS, Sega Master System, Genesis, Sega CD, 32X, Game Gear, Saturn, PS1.
- **Mechanism**: RetroArch writes saves next to the ROM or inside RetroArch's `saves/` folder using standardized formats (`.srm`, `.sav`, `.eep`).
- **Sync Behavior**: The `SaveSyncEngine` calculates MD5 checksums, checks mtimes against RomM, handles pre-launch downloads, and uploads updated saves on process exit.

### 2. `shared_memory_card` (Virtual Memory Card Swapping)
- **Platforms**: PlayStation 2 (`pcsx2_libretro`), Sega Dreamcast (`flycast_libretro`).
- **Mechanism**: The emulator core expects fixed shared memory card files (e.g. `Mcd001.ps2` for PS2, `vmu_save_A1.bin` for Dreamcast) inside RetroArch's `system/` directory.
- **Sync Behavior**:
  1. Before launch, the game's individual memory card is fetched from RomM (or local app storage) and copied into RetroArch's system path as the active memory card.
  2. During launch, RetroArch reads and modifies the active card.
  3. Upon game exit, the updated card is moved back to the game's isolated storage, uploaded to RomM, and removed from the RetroArch system directory (leaving BIOS files like `dc_boot.bin` and `dc_flash.bin` intact).

### 3. `memory_card_per_game` (Per-Game Container & Title ID Inspection)
- **Platforms**: Nintendo GameCube (`dolphin_libretro`), Nintendo Wii (`dolphin_libretro`), Nintendo 3DS (`citra_libretro`).
- **Mechanism**:
  - **GameCube**: `DolphinGameCubeHandler` reads the 0x60-byte disc boot header (extracting game code, maker code, and region), locates `.gci` save files in Dolphin's `User/GC/<Region>/` directories, and synchronizes the discrete save file.
  - **Nintendo Wii**: `DolphinWiiHandler` inspects disc boot headers (ISO, WBFS, RVZ, WIA, CISO) to extract the 4-character Game ID, derives the emulated Wii NAND Title ID (`00010000<TitleIDHex>`), discovers title save directories (`User/Wii/title/00010000/<TitleIDHex>/data/`), and synchronizes the emulated NAND save files with RomM as zip archives.
  - **Nintendo 3DS**: `Citra3DSHandler` inspects NCSD / NCCH container headers to extract the 64-bit Title ID, consolidates Citra's folder-based save directories (`data/00000000000000000000000000000000/<ID1>/title/<high>/<low>/data/00000001/`), and synchronizes individual title saves with RomM as zip archives.

---

## Custom Core Overrides & Architecture References

Users can override any platform's default libretro core at any time in the GUI under **Settings** &gt; **RetroArch Settings** &gt; **Core Mappings**.

For comprehensive architectural specifications on how cores, flavors, and save files are discovered and managed, refer to:
- **[RetroArch Multi-Flavor Architecture & Path Resolution](architecture/retroarch-flavors-and-paths.md)**: Detailed flavor detection (Steam, Standalone, RetroDECK), candidate core fallback lists, and runtime config parsing.
- **[Save File & Playtime Synchronization Architecture](architecture/save-file-sync-architecture.md)**: Gavel normative engine, strategy selection, and discrete container handling.
