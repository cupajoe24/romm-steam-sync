# `romm-steam-sync` Documentation

Welcome to the documentation for **`romm-steam-sync`**, a multi-platform (Windows, macOS, Linux) application designed to synchronize your self-hosted [RomM](https://github.com/rommapp/romm) game library with Steam as non-Steam shortcuts launched via [RetroArch](https://github.com/libretro/RetroArch), while providing a local **Library** manager to launch or uninstall local ROM files. The application includes a 6-step **First-Launch Onboarding Wizard** on initial setup, leading into 5 main navigation views: **Library**, **Platform Selection**, **Library Sync**, **Cleanup & Restore**, and **Settings**.

This project draws heavy architectural inspiration from [Tender](https://github.com/danielcopper/romm-tender) (`decky-romm-sync`), maintaining compatibility in domain structures, database schemas, and RomM API interactions while adapting for standalone desktop environments without Decky Loader.

---

## Documentation Index

### Core & High-Level Specs
- **[Project Overview](overview.md)**: High-level vision, target operating systems, user-friendly desktop GUI approach, key comparisons and divergences from Tender.
- **[Console & Platform Compatibility](compatibility.md)**: Comprehensive compatibility matrix for major Nintendo, Sega, Sony, and Microsoft consoles by generation, default RetroArch cores, game launch support, and save sync status.
- **[Project Roadmap](roadmap.md)**: Development roadmap tracking completed milestones and upcoming feature priorities.

### Architectural Documents (`docs/architecture/`)
- **[Backend Architecture & Data Model](architecture/backend-architecture.md)**: Cosmic Python aggregate roots, SQLite Unit of Work (`uow`), persistence boundaries, unified API key authentication, and RomM REST API client adapter.
- **[Steam Shortcuts & VDF Architecture](architecture/steam-shortcuts-vdf.md)**: Binary `shortcuts.vdf` parsing/writing, 32/64-bit AppID generation, grid artwork file management, and Steam process lock/close guard.
- **[RetroArch Multi-Flavor Architecture & Path Resolution](architecture/retroarch-flavors-and-paths.md)**: Polymorphic adapter hierarchy supporting Steam, Standalone, and RetroDECK flavors, dynamic flavor sniffing, centralized `RetroArchPathResolver`, and `retroarch.cfg` runtime save resolution (`RetroArchConfigAdapter`).
- **[Launcher Wrapper & On-Demand Downloads](architecture/launcher-and-on-demand-downloads.md)**: `romm-steam-sync-launcher` execution flow, standalone native binary packaging with ELF/PE magic-byte guards, on-demand ROM fetching and archive extraction, window foregrounding, and exit handling.
- **[Save File & Playtime Synchronization Architecture](architecture/save-file-sync-architecture.md)**: Gavel normative decision engine (`local_matches_server`, shrinkage guard, 409 conflict ladder, 2.0s timestamp tolerance), save strategy abstraction layer (`default_save_per_game`, `shared_memory_card`, `memory_card_per_game`), and specialized handlers for Dolphin GameCube, Dolphin Wii emulated NAND, and Citra 3DS emulated SDMC.
- **[Logging Architecture](architecture/logging-architecture.md)**: System logging setup, RotatingFileHandler parameters, logging level policies, and contextual exception handling strategy.


---

## Related Context & References
- Project Repository: [https://github.com/cupajoe24/romm-steam-sync](https://github.com/cupajoe24/romm-steam-sync)
- Upstream RomM project: [https://github.com/rommapp/romm](https://github.com/rommapp/romm)
- Upstream Tender project: [https://github.com/danielcopper/romm-tender](https://github.com/danielcopper/romm-tender)
- Libretro RetroArch: [https://github.com/libretro/RetroArch](https://github.com/libretro/RetroArch)