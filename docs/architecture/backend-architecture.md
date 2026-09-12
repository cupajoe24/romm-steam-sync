# Backend Architecture & Data Model

## 1. Overview & Architectural Principles

`romm-steam-sync` follows the **Cosmic Python Architecture** (Domain-Driven Design with Clean Architecture principles), matching the architectural standards established in Tender (`decky-romm-sync`).

### Core Design Rules
1. **Domain Isolation**: Pure Python domain entities and value objects containing business rules and invariants without external dependencies (no direct HTTP, database, or UI imports in `domain/`).
2. **Aggregate Boundaries**: Data consistency is enforced at aggregate boundaries. Each aggregate root owns its invariants and is mutated solely via domain methods.
3. **Unit of Work (UoW)**: Database transactions are scoped using Python context managers (`with uow:`). Repositories are accessed exclusively via the Unit of Work.
4. **Explicit Persistence Seams**:
   - **User Settings**: `settings.json` (server URL, auth credentials, platform/collection sync toggles, RetroArch path, `onboarding_complete` state flag).
   - **Relational Domain State**: SQLite database (`romm_steam_sync.db`) backing domain aggregate roots.

---

## 2. Aggregate Domain Model

The system maintains 6 primary aggregate roots:

```
                  +-----------------------+
                  |         Rom           |  <-- Aggregate Root
                  |  (rom_id, platform,   |
                  |   shortcut_app_id)    |
                  +-----------------------+
                      |               |
         1:0..1       |               | 1:0..1
         +------------+               +------------+
         v                                         v
+------------------+                     +-------------------+
|    RomInstall    |                     | RomSaveSyncState  |
| (file_path,      |                     | (active_slot,     |
|  rom_dir, status)|                     |  file_sync_states)|
+------------------+                     +-------------------+
```

### 1. `Rom` Aggregate (`domain/rom.py`)
- **Role**: Synced-ROM registry anchoring local identity.
- **Fields**: `rom_id` (int, PK), `platform_slug` (str), `name` (str), `shortcut_app_id` (int | None), `sibling_group_key` (str | None), `summary` (str | None), `cover_url` (str | None), `fs_name` (str | None), `sgdb_id` (int | None), `igdb_id` (int | None).
- **Invariants**: `shortcut_app_id` is unique across all bound ROMs.
- **Methods**: `bind_shortcut(app_id)`, `unbind_shortcut()`.


### 2. `RomInstall` Aggregate (`domain/rom_install.py`)
- **Role**: Tracks on-disk ROM file presence and local installation state.
- **Fields**: `rom_id` (int, PK), `file_path` (str), `rom_dir` (str | None), `launchable` (bool), `installed_at` (datetime).
- **Invariants**: `rom_dir` is present for folder-backed ROMs and `None` for single-file ROMs.
- **Repository Methods**: `get(rom_id)`, `add(install)`, `delete(rom_id)`, `list_all()` (queries all local ROM installs for the desktop Library view).

### 3. `RomSaveSyncState` Aggregate (`domain/save_sync_state.py`)
- **Role**: Tracks save file sync baselines, active slot, and per-file sync metadata aligned with the Gavel specification.
- **Fields**: `rom_id` (int, PK), `slot_confirmed` (bool), `active_slot` (str), `file_states` (dict[str, FileSyncState]).
- **Value Object**: `FileSyncState` (`file_name`, `last_sync_hash`, `last_sync_server_hash`, `last_sync_local_size`, `last_sync_local_mtime`, `tracked_save_id`, `last_synced_at`).

### 4. `RomPlaytime` Aggregate (`domain/playtime.py`)
- **Role**: Tracks cumulative play duration and pending session outbox.
- **Fields**: `rom_id` (int, PK), `total_seconds` (int), `last_played_at` (datetime | None), `pending_sessions` (list[PlaySession]).

### 5. `SyncRun` Aggregate (`domain/sync_run.py`)
- **Role**: Transaction lifecycle for library synchronization passes.
- **Fields**: `run_id` (str), `started_at` (datetime), `status` (str: `RUNNING`, `COMPLETED`, `CANCELLED`, `FAILED`).

### 6. `KvConfig` Aggregate (`domain/kv_config.py`)
- **Role**: Key-value store for singleton runtime markers (e.g. `device_id`, platform slug-to-name cache, `default_version:<sibling_group_key>` pinned version preferences).

---

## 2.1 Sibling Group Architecture & 1G1R Resolution

In RomM, a single game may contain multiple regional versions (e.g. USA, Europe, Japan), revision dumps (e.g. v1.00, v2.00), or multiple discs (e.g. Disc 1, Disc 2). To prevent creating cluttered or duplicate shortcuts in Steam, `romm-steam-sync` groups these variants into unified game sibling groups.

### Sibling Group Key Derivation (`domain/sibling_group.py`)
- Sibling groups are scoped by platform and derived by coalescing metadata IDs across 8 supported sources:
  1. `igdb` (`igdb:<id>:<platform_slug>`)
  2. `ss` (ScreenScraper)
  3. `moby` (MobyGames)
  4. `ra` (RetroAchievements)
  5. `hasheous`
  6. `launchbox`
  7. `tgdb` (TheGamesDB)
  8. `flashpoint`
- **Connected Components**: Computes connected components using a Union-Find algorithm over RomM `sibling_roms` API graph edges to resolve groups even when individual sibling dumps lack complete metadata tags.
- **Fallback**: Unmatched solo ROMs fallback to `romm:<rom_id>:<platform_slug>`.

### Deterministic 1G1R Resolution (`domain/sibling_resolution.py`)
When generating Steam shortcuts during library synchronization, exactly **one** representative ROM is bound to the Steam shortcut (`shortcut_app_id`), while all other siblings remain unbound (`shortcut_app_id = None`) in SQLite:

1. **User Pinned Preference**: Checked in `kv_config` under `default_version:<sibling_group_key>`.
2. **Installed Status**: Local installed ROMs take priority over cloud-only siblings.
3. **Existing Binding**: Existing bound ROMs are preserved.
4. **Main Sibling**: RomM's `is_main_sibling` flag.
5. **1G1R Region & Revision Ranking**:
   - **Region Priority**: `World` > `USA` > `Europe` > `Japan` > others.
   - **Prerelease Demotion**: Retail releases are prioritized over Beta, Prototype, or Demo dumps across all regions.
   - **Revision Priority**: Higher revision numbers (e.g., `Rev 2` > `Rev 1` > base) win.

### Canonical Game Title Derivation
- `canonical_group_name(members)` strips parenthetical revision and disc suffixes (`(Disc 1)`, `(v1.00)`, `(USA)`) to produce a clean Steam shortcut display title (e.g. `Dark Cloud 2` or `Final Fantasy VII`).


## 3. Persistence & Unit of Work (`service_layer/unit_of_work.py`)

Access to SQLite repositories is gated by the `SqliteUnitOfWork`:

```python
class SqliteUnitOfWork(Protocol):
    roms: RomRepository
    installs: RomInstallRepository
    save_states: SaveSyncStateRepository
    playtime: PlaytimeRepository
    sync_runs: SyncRunRepository
    kv_config: KvConfigRepository

    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type, exc_val, exc_tb) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
```

---

## 4. RomM API Adapter (`adapters/romm_api.py`)

The backend connects to RomM v4.9+ REST endpoints:

- `GET /api/roms`: Query ROM library with pagination and filters.
- `GET /api/platforms`: Fetch platform metadata and tags.
- `GET /api/roms/{id}/content/{file_name}`: Download binary ROM content.
- `GET /api/saves?rom_id={id}`: List save files for a given ROM.
- `POST /api/saves`: Upload new save slot entry.
- `PUT /api/saves/{id}`: Update existing save entry content.
- `GET /api/saves/{id}/content`: Download binary save content.
- `POST /api/sync/negotiate`: Open sync negotiation session for device.
- `POST /api/play-sessions`: Ingest play session records.
- `POST /api/devices`: Register local client device.

### Authentication Unification & URL Scheme
- **Unified API Key Authentication**: In alignment with modern RomM v4.9+ releases, authentication is standardized on persistent API keys / personal access tokens rather than transient username/password session tokens. Requests set the `Authorization: Bearer <api_key>` header across all API calls.
- **Default Server URL Scheme (`http://`)**: Self-hosted RomM installations are frequently deployed on home LANs without public SSL/TLS certificates (e.g. `http://192.168.1.100:8080` or `http://romm.local:8080`). The app defaults new connections to `http://` to minimize connection failures during onboarding. Trailing slashes are automatically normalized.

### Network Retries, Timeout & Cancellation Recovery
- **Automatic 3-Attempt Retries**: Requests in `RomMApiClient` use `_request_with_retry` to automatically retry up to 3 times on `requests.exceptions.Timeout` or `ConnectionError`.
- **Timeout Callback Seam**: If retries fail during library sync, `SyncService` invokes `on_timeout_callback` displaying `RomMTimeoutModal` with three options: **Retry Fetch**, **Cancel Sync**, or **Revert to Backup** (restores pre-sync Steam VDF backup).
- **Cancellation Callback Seam**: `SyncService.sync_library` evaluates `is_cancelled_callback` at each ROM iteration. If **Cancel & Keep** (`"cancel"`) is selected, sync halts while saving shortcuts created so far; if **Cancel & Rollback** (`"rollback"`) is selected, `SteamBackupManager.restore_backup` immediately reverts Steam configuration (`shortcuts.vdf`, `localconfig.vdf`, `grid/`) to pre-sync state.

### Canonical Platform Normalization
- **Platform Alias Mapping**: `PLATFORM_ALIASES` normalizes platform slugs (e.g. `ps2`, `dc`) and display names (e.g. `Playstation 2`, `Dreamcast`) into canonical keys (`ps2`, `dreamcast`).
- **Deduplicated Collections**: `get_synced_libraries()` and `remove_synced_library()` merge metrics and cleanup shortcuts/DB records across all aliases of a platform.

---

## 5. SteamGridDB API Adapter (`adapters/steamgriddb.py`)

The backend connects to SteamGridDB API v2 (`https://www.steamgriddb.com/api/v2`) to fetch custom Steam non-Steam shortcut artwork:

- **Authentication**: `Authorization: Bearer <steamgriddb_api_key>` header.
- **Custom User-Agent**: Outgoing HTTP requests set `User-Agent: romm-steam-sync/1.0` to bypass SteamGridDB default User-Agent filtering.
- **Endpoints**:
  - `GET /search/autocomplete/test`: Verifies API key validity.
  - `GET /games/igdb/{igdb_id}`: Resolves SteamGridDB Game ID from RomM IGDB cross-reference.
  - `GET /search/autocomplete/{name}`: Free-text search fallback.
  - `GET /heroes/game/{id}`: Fetches top-rated Hero banner (1920x620).
  - `GET /logos/game/{id}`: Fetches top-rated Logo overlay (transparent PNG).
  - `GET /grids/game/{id}`: Fetches top-rated Wide Grid (920x430) and Portrait Cover (600x900).
  - `GET /icons/game/{id}`: Fetches top-rated Icon (256x256).
- **Fallback Strategy**: If SteamGridDB API key is unconfigured or a request fails, `SyncService` falls back to downloading RomM cover art (`/api/roms/{id}/cover`) for `<appId>p.png` and `<appId>.png`.