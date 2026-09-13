# Project Roadmap

This document outlines the development roadmap for **`romm-steam-sync`**, tracking completed milestones and upcoming architectural priorities.

---

## Completed Milestones

- **RetroDECK & Standalone RetroArch Support (v0.1.5)**:
  - Polymorphic adapter hierarchy supporting Steam RetroArch, Standalone RetroArch (system PATH, standard installer paths, Flatpak), and RetroDECK Flatpak (`net.retrodeck.retrodeck`).
  - Dynamic flavor detection, centralized `RetroArchPathResolver`, and config health validation (`RetroDeckConfigHealth`).
  - Runtime save directory resolution via `RetroArchConfigAdapter` parsing `retroarch.cfg` and libretro `.info` metadata.
---

## In Development

- **Collection & Favorites Synchronization**:
   - Sync RomM favorites and custom user collections down into Steam library category tags.

## Upcoming Features (Backlog)
In no particular order:

- **Save State Synchronization**:
   - Synchronization of emulator quicksave/state slots (`.state`, `.state1`, etc.) independently of cartridge/memory card battery RAM.
- **Deeper Steam Integration**:
   - Steam rich presence integration for active RomM games.
   - Recommended Steam Controller configurations / input templates per platform.
   - (maybe) Enhanced launch flow prompts optimized for Steam Deck Game Mode and Steam Big Picture mode.
- **Automated Core Management and configuration validation for RetroArch**:
   - Automatic detection of missing libretro cores with prompts to install via Steam Store DLC or download into core search directories.
- **Standalone Emulator Support**:
   - Direct integration with standalone emulators (RPCS3 for PS3, Cemu for Wii U, PCSX2 standalone, Xemu for original Xbox, etc).
- **BIOS & System Configuration Synchronization**:
   - Verifying and synchronizing required BIOS firmware images from RomM to the emulator's `system/` directory.
- **Expanded support for Later-Generation Systems**:
   - DLC and title update management for disc/filesystem consoles (PlayStation 3, Wii U, etc).