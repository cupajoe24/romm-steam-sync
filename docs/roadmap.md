# Project Roadmap

This document outlines the development roadmap for **`romm-steam-sync`**, tracking completed milestones and upcoming architectural priorities.

---

## Completed Milestones

- **RetroDECK & Standalone RetroArch Support (v0.2.0)**:
  - Polymorphic adapter hierarchy supporting Steam RetroArch, Standalone RetroArch (system PATH, standard installer paths, Flatpak), and RetroDECK Flatpak (`net.retrodeck.retrodeck`).
  - Dynamic flavor detection, centralized `RetroArchPathResolver`, and config health validation (`RetroDeckConfigHealth`).
  - Runtime save directory resolution via `RetroArchConfigAdapter` parsing `retroarch.cfg` and libretro `.info` metadata.
---

## Upcoming Priorities (In Progress / Backlog)

1. **Save State Synchronization**:
   - Synchronization of emulator quicksave/state slots (`.state`, `.state1`, etc.) independently of cartridge/memory card battery RAM.
2. **Collection & Favorites Synchronization**:
   - Sync RomM favorites and custom user collections down into Steam library category tags.
3. **Deeper Steam Integration**:
   - Steam rich presence integration for active RomM games.
   - Recommended Steam Controller configurations / input templates per platform.
   - Enhanced launch flow prompts optimized for Steam Deck Game Mode and Steam Big Picture mode.
4. **Automated Core Management for Steam RetroArch**:
   - Automatic detection of missing libretro cores with prompts to install via Steam Store DLC or download into core search directories.
5. **Standalone Emulator Support**:
   - Direct integration with standalone emulators (RPCS3 for PS3, Cemu for Wii U, PCSX2 standalone, DuckStation standalone, and Xemu for original Xbox).
6. **BIOS & System Configuration Synchronization**:
   - Verifying and synchronizing required BIOS firmware images from RomM to the emulator's `system/` directory.
7. **Expanded Later-Generation Systems**:
   - DLC and title update management for disc/filesystem consoles (PlayStation 3, Wii U).