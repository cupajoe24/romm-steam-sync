"""Library Synchronization Service Orchestrator."""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from romm_steam_sync.adapters.romm_api import RomMApiClient, RomMTimeoutError
from romm_steam_sync.adapters.steam_backup import SteamBackupManager
from romm_steam_sync.adapters.steam_guard import SteamGuard
from romm_steam_sync.adapters.steam_localconfig import SteamLocalConfigManager
from romm_steam_sync.adapters.steam_path import SteamPathResolver
from romm_steam_sync.adapters.steam_vdf import SteamVdfManager, generate_app_id
from romm_steam_sync.adapters.steamgriddb import SteamGridDbClient
from romm_steam_sync.adapters.wrapper_installer import (
    get_installed_wrapper_path,
    install_wrapper,
)
from romm_steam_sync.config import AppSettings
from romm_steam_sync.domain import (
    PlatformSyncDiff,
    Rom,
    SyncDiff,
    SyncRun,
    canonical_group_name,
    compute_component_group_keys,
    compute_sibling_group_key,
    resolve_group_representative,
)
from romm_steam_sync.domain.platform import (
    PLATFORM_ALIASES,
    get_platform_aliases,
    normalize_platform_identifier,
)
from romm_steam_sync.service_layer.db_session import DatabaseSession

logger = logging.getLogger(__name__)


class SteamRunningException(Exception):
    """Raised when Steam process is detected running during sync operation."""


class RomMTimeoutException(Exception):
    """Raised when RomM API times out during sync operation."""

    def __init__(
        self, platform_name: str, backup_id: Optional[str] = None
    ) -> None:
        super().__init__(f"RomM server timed out for platform {platform_name}")
        self.platform_name = platform_name
        self.backup_id = backup_id


class SyncService:
    """Orchestrates fetching library metadata, backing up Steam VDF, writing shortcuts, and persisting state."""

    def __init__(
        self,
        settings: Optional[AppSettings] = None,
        db_session: Optional[DatabaseSession] = None,
    ) -> None:
        """Initialize SyncService.

        Args:
            settings: Optional AppSettings instance.
            db_session: Optional DatabaseSession instance.
        """
        self.settings = settings or AppSettings.load()
        self.db_session = db_session or DatabaseSession()
        self.backup_manager = SteamBackupManager()

    def calculate_sync_diff(
        self,
        enabled_platforms: Optional[List[str]] = None,
        all_roms: Optional[List[dict]] = None,
        id_to_name: Optional[Dict[str, str]] = None,
        shortcuts: Optional[List[dict]] = None,
    ) -> SyncDiff:
        """Calculate sync diff (additions, removals, unchanged) per enabled platform.

        Compares remote RomM ROMs against SQLite local database and Steam shortcuts.vdf.

        Args:
            enabled_platforms: Optional list of enabled platform slugs.
            all_roms: Optional pre-fetched list of all remote RomM ROM dictionaries.
            id_to_name: Optional mapping of platform slugs to display names.
            shortcuts: Optional pre-loaded list of Steam shortcut dictionaries.

        Returns:
            SyncDiff container holding diff calculations per platform.
        """
        enabled = enabled_platforms or self.settings.enabled_platforms
        if not enabled:
            return SyncDiff()

        enabled_canonical = {}
        for p in enabled:
            ckey, dname = normalize_platform_identifier(p)
            enabled_canonical[ckey] = dname

        # Load local state from SQLite DB
        with self.db_session as db:
            local_db_roms = db.roms.list_all()

        local_roms_by_platform: Dict[str, List[Rom]] = {}
        for rom in local_db_roms:
            ckey, _ = normalize_platform_identifier(rom.platform_slug)
            if ckey not in local_roms_by_platform:
                local_roms_by_platform[ckey] = []
            local_roms_by_platform[ckey].append(rom)

        shortcut_map_by_name: Dict[str, dict] = {}
        shortcut_map_by_rom_id: Dict[int, dict] = {}
        if shortcuts:
            for s in shortcuts:
                app_name = s.get("AppName")
                if app_name:
                    shortcut_map_by_name[app_name] = s
                lopt = s.get("LaunchOptions", "")
                if "--rom-id" in lopt:
                    parts = lopt.split()
                    for idx, pt in enumerate(parts):
                        if pt == "--rom-id" and idx + 1 < len(parts) and parts[idx + 1].isdigit():
                            r_id = int(parts[idx + 1])
                            shortcut_map_by_rom_id[r_id] = s

        remote_roms_by_platform: Dict[str, List[dict]] = {}
        if all_roms:
            for r_data in all_roms:
                p_slug_item = (
                    r_data.get("platform_slug")
                    or (r_data.get("platform", {}).get("slug") if isinstance(r_data.get("platform"), dict) else None)
                    or "unknown"
                )
                ckey, dname = normalize_platform_identifier(p_slug_item)
                if ckey not in remote_roms_by_platform:
                    remote_roms_by_platform[ckey] = []
                remote_roms_by_platform[ckey].append(r_data)

        platform_diffs: Dict[str, PlatformSyncDiff] = {}

        for ckey, dname in enabled_canonical.items():
            remote_list = remote_roms_by_platform.get(ckey, [])
            local_list = local_roms_by_platform.get(ckey, [])

            # Compute sibling group keys for remote ROMs
            resident_keys = {r.rom_id: r.sibling_group_key for r in local_list if r.sibling_group_key}
            computed_keys = compute_component_group_keys(remote_list, resident_keys)
            for r in remote_list:
                r_id = r.get("id") or r.get("rom_id")
                if r_id and r_id in computed_keys:
                    r["sibling_group_key"] = computed_keys[r_id]
                elif "sibling_group_key" not in r:
                    r["sibling_group_key"] = compute_sibling_group_key(r)

            remote_ids = {r["id"]: r for r in remote_list if "id" in r}
            local_db_map = {r.rom_id: r for r in local_list}

            # Group remote ROMs by sibling_group_key
            remote_groups: Dict[str, List[dict]] = {}
            for r_data in remote_list:
                g_key = r_data.get("sibling_group_key") or f"romm:{r_data.get('id')}:{ckey}"
                remote_groups.setdefault(g_key, []).append(r_data)

            # Group local ROMs by sibling_group_key
            local_groups: Dict[str, List[Rom]] = {}
            for rom in local_list:
                g_key = rom.sibling_group_key or f"romm:{rom.rom_id}:{ckey}"
                local_groups.setdefault(g_key, []).append(rom)

            additions: List[dict] = []
            unchanged: List[dict] = []
            removals_roms: List[Rom] = []
            removals_shortcuts: List[dict] = []

            for g_key, members in remote_groups.items():
                group_has_db = any(m.get("id") in local_db_map for m in members)
                group_has_shortcut = any(
                    (m.get("id") in shortcut_map_by_rom_id) or (m.get("name") in shortcut_map_by_name)
                    for m in members
                )
                if group_has_db and group_has_shortcut:
                    unchanged.extend(members)
                else:
                    additions.extend(members)

            for g_key, l_members in local_groups.items():
                if not any(lr.rom_id in remote_ids for lr in l_members):
                    removals_roms.extend(l_members)

            target_aliases = [a.lower() for a in get_platform_aliases(ckey)]
            if shortcuts:
                for s in shortcuts:
                    tags = s.get("tags", {})
                    tag_vals = [str(v).lower() for v in tags.values()] if isinstance(tags, dict) else []
                    if "romm" in tag_vals:
                        matches = any(
                            str(v).lower() in target_aliases
                            or str(v).lower().replace(" ", "-") in target_aliases
                            or normalize_platform_identifier(str(v))[0] == ckey
                            for v in tag_vals
                        )
                        if matches:
                            lopt = s.get("LaunchOptions", "")
                            s_rom_id = None
                            if "--rom-id" in lopt:
                                parts = lopt.split()
                                for idx, pt in enumerate(parts):
                                    if pt == "--rom-id" and idx + 1 < len(parts) and parts[idx + 1].isdigit():
                                        s_rom_id = int(parts[idx + 1])

                            app_name = s.get("AppName")
                            if s_rom_id is not None and s_rom_id not in remote_ids:
                                if s not in removals_shortcuts and s_rom_id not in local_db_map:
                                    removals_shortcuts.append(s)
                            elif s_rom_id is None and app_name and app_name not in {r.get("name") for r in remote_list}:
                                if s not in removals_shortcuts:
                                    removals_shortcuts.append(s)

            disp_name = (id_to_name.get(ckey) if id_to_name else None) or dname
            platform_diffs[ckey] = PlatformSyncDiff(
                platform_slug=ckey,
                platform_name=disp_name,
                additions=additions,
                removals_roms=removals_roms,
                removals_shortcuts=removals_shortcuts,
                unchanged_roms=unchanged,
            )


        sync_diff = SyncDiff(platform_diffs=platform_diffs)
        logger.info(
            "Sync Diff Calculated: %d total additions, %d total removals, %d total unchanged across %d platforms",
            sync_diff.total_additions,
            sync_diff.total_removals,
            sync_diff.total_unchanged,
            len(platform_diffs),
        )
        return sync_diff

    def sync_library(
        self,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        skip_steam_guard: bool = False,
        on_timeout_callback: Optional[Callable[[str, Optional[str]], str]] = None,
        is_cancelled_callback: Optional[Callable[[], Optional[str]]] = None,
        on_diff_callback: Optional[Callable[[SyncDiff], str]] = None,
    ) -> Tuple[bool, str, int]:
        """Perform library synchronization with diff calculation and optional two-stage confirmation.
        
        Returns:
            Tuple[success: bool, message: str, synced_count: int]
        """
        def log_progress(
            pct: float,
            msg: str,
            cover_path: Optional[str] = None,
            rom_name: Optional[str] = None,
        ) -> None:
            """Emit progress to logger and optional GUI callback.

            Args:
                pct: Progress fraction from 0.0 to 1.0.
                msg: Status message to display.
                cover_path: Optional path to artwork image.
                rom_name: Optional game title.
            """
            logger.info("[%d%%] %s", int(pct * 100), msg)
            if progress_callback:
                try:
                    progress_callback(pct, msg, cover_path, rom_name)
                except TypeError:
                    progress_callback(pct, msg)

        logger.info("================ Starting Library Synchronization Pass ================")

        # 1. Steam Safety Guard Check
        if not skip_steam_guard and SteamGuard.is_steam_running():
            logger.warning("Library sync blocked: Steam is currently running.")
            raise SteamRunningException("Steam is currently running. Please close Steam before proceeding with sync.")

        # 2. Resolve Steam config directory
        config_dir, selected_user_id = SteamPathResolver.get_user_config_dir(
            user_id=self.settings.steam_user_id,
            custom_steam_path=self.settings.steam_custom_path,
        )
        if not config_dir:
            logger.error("Failed to locate Steam userdata config directory.")
            return False, "Could not locate Steam userdata config directory. Check Steam installation.", 0

        grid_dir = config_dir / "grid"
        grid_dir.mkdir(parents=True, exist_ok=True)
        vdf_path = config_dir / "shortcuts.vdf"

        log_progress(0.05, f"Targeting Steam profile {selected_user_id} ({config_dir})")

        # 3. Create Steam Config Backup (shortcuts.vdf & localconfig.vdf, rolling max 5)
        backup_id = self.backup_manager.create_backup(str(config_dir))
        if backup_id:
            log_progress(0.10, f"Created pre-sync backup: {backup_id} (max 5 retained)")

        # 4. Authenticate with RomM API
        log_progress(0.15, "Connecting to RomM server...")
        client = RomMApiClient(
            base_url=self.settings.romm_url,
            api_key=self.settings.api_key,
        )
        ok, auth_msg = client.authenticate()
        if not ok:
            logger.error("RomM API authentication failed: %s", auth_msg)
            return False, f"RomM connection failed: {auth_msg}", 0

        # Initialize SteamGridDB client if API key is provided
        sgdb_client: Optional[SteamGridDbClient] = None
        if self.settings.steamgriddb_api_key:
            sgdb_client = SteamGridDbClient(api_key=self.settings.steamgriddb_api_key)

        # 5. Fetch Enabled Platforms and ROMs
        enabled = self.settings.enabled_platforms
        
        # Build platform slug <-> ID <-> Name mapping
        slug_to_id = {}
        id_to_name = {}
        try:
            platforms = client.get_platforms()
            for p in platforms:
                p_id = p.get("id")
                p_slug = p.get("slug") or p.get("name", "").lower()
                p_name = p.get("display_name") or p.get("name") or p_slug
                if p_id is not None:
                    id_to_name[str(p_id)] = p_name
                if p_slug:
                    slug_to_id[str(p_slug).lower()] = p_id
                    id_to_name[str(p_slug).lower()] = p_name
            
            if not enabled:
                enabled = list(slug_to_id.keys())
        except Exception as e:
            logger.warning("Failed to fetch platform list from RomM: %s", e)

        if not enabled:
            logger.warning("No platforms selected for library sync.")
            return False, "No platforms selected for sync", 0

        logger.info("Fetching ROMs for platforms: %s", ", ".join(enabled))
        log_progress(0.25, "Checking RomM library and calculating library changes...")
        all_roms = []
        for p_slug in enabled:
            p_id = slug_to_id.get(p_slug.lower())
            if p_id is None and p_slug.isdigit():
                p_id = int(p_slug)

            p_display_name = id_to_name.get(p_slug.lower()) or id_to_name.get(str(p_id)) or p_slug.upper()

            while True:
                try:
                    roms = client.get_roms(platform_id=p_id, platform_slug=p_slug)
                    all_roms.extend(roms)
                    break
                except Exception as e:
                    logger.warning("RomM API error while fetching platform %s (%s): %s", p_display_name, p_slug, e)
                    if on_timeout_callback:
                        choice = on_timeout_callback(p_display_name, backup_id)
                        if choice == "retry":
                            log_progress(0.28, f"Retrying fetch for platform {p_display_name}...")
                            continue
                        elif choice == "revert":
                            if backup_id and config_dir:
                                self.backup_manager.restore_backup(backup_id, str(config_dir))
                            return False, "Sync cancelled: Reverted Steam configuration to pre-sync backup.", 0
                        else:
                            return False, f"Sync cancelled due to RomM server timeout on platform {p_display_name}.", 0
                    else:
                        return False, f"RomM server timed out fetching platform {p_display_name}: {e}", 0

        if not all_roms and not self.db_session:
            logger.warning("No ROMs retrieved for selected platforms.")
            return False, "No ROMs found for selected platforms", 0

        logger.info("Fetched %d remote ROMs from RomM.", len(all_roms))

        # 6. Load shortcuts.vdf and calculate diff
        vdf_mgr = SteamVdfManager(str(vdf_path))
        shortcuts = vdf_mgr.load_shortcuts()

        sync_diff = self.calculate_sync_diff(
            enabled_platforms=enabled,
            all_roms=all_roms,
            id_to_name=id_to_name,
            shortcuts=shortcuts,
        )

        user_mode = "full"
        if on_diff_callback:
            log_progress(0.38, f"Displaying sync diff summary (+{sync_diff.total_additions}, -{sync_diff.total_removals}, {sync_diff.total_unchanged} unchanged)...")
            user_mode = on_diff_callback(sync_diff)
            logger.info("User selected diff action mode: '%s'", user_mode)
            if user_mode == "cancel":
                log_progress(0.40, "Sync cancelled by user at diff stage.")
                return False, "Sync cancelled by user.", 0

        shortcut_map = {s.get("AppName"): s for s in shortcuts if "AppName" in s}

        sync_run = SyncRun.start_new()
        synced_count = 0

        # Launcher executable path setup
        try:
            launcher_exe = str(install_wrapper())
        except Exception as e:
            logger.warning("Failed to install launcher wrapper script, falling back to installed path: %s", e)
            launcher_exe = str(get_installed_wrapper_path())

        platform_app_ids_64: dict[str, set[int]] = {}
        master_app_ids_64: set[int] = set()

        all_additions = [r for pd in sync_diff.platform_diffs.values() for r in pd.additions]
        all_removals_roms = [rom for pd in sync_diff.platform_diffs.values() for rom in pd.removals_roms]
        all_removals_shortcuts = [s for pd in sync_diff.platform_diffs.values() for s in pd.removals_shortcuts]
        all_unchanged = [r for pd in sync_diff.platform_diffs.values() for r in pd.unchanged_roms]

        # Group additions and unchanged by sibling_group_key
        grouped_additions: Dict[str, List[dict]] = {}
        for r_data in all_additions:
            p_slug_item = r_data.get("platform_slug") or (r_data.get("platform", {}).get("slug") if isinstance(r_data.get("platform"), dict) else None) or "unknown"
            g_key = r_data.get("sibling_group_key") or compute_sibling_group_key(r_data) or f"romm:{r_data.get('id')}:{p_slug_item}"
            grouped_additions.setdefault(g_key, []).append(r_data)

        grouped_unchanged: Dict[str, List[dict]] = {}
        for r_data in all_unchanged:
            p_slug_item = r_data.get("platform_slug") or (r_data.get("platform", {}).get("slug") if isinstance(r_data.get("platform"), dict) else None) or "unknown"
            g_key = r_data.get("sibling_group_key") or compute_sibling_group_key(r_data) or f"romm:{r_data.get('id')}:{p_slug_item}"
            grouped_unchanged.setdefault(g_key, []).append(r_data)

        total_work_items = len(grouped_additions) + (len(all_removals_roms) if user_mode == "full" else 0)
        work_idx = 0

        with self.db_session as db:
            installed_ids = {inst.rom_id for inst in db.installs.list_all()}
            bound_ids = {r.rom_id for r in db.roms.list_all() if r.shortcut_app_id is not None}

            # Stage 2A: Process Unchanged ROMs (Fast path: register AppIDs for CloudCollections)
            for g_key, members in grouped_unchanged.items():
                canonical_name = canonical_group_name(members) if members else "Unknown Game"
                rep_data = members[0]
                p_slug_item = rep_data.get("platform_slug") or (rep_data.get("platform", {}).get("slug") if isinstance(rep_data.get("platform"), dict) else None) or "unknown"
                p_display_name = (
                    rep_data.get("platform_name")
                    or (rep_data.get("platform", {}).get("name") if isinstance(rep_data.get("platform"), dict) else None)
                    or id_to_name.get(p_slug_item.lower())
                    or id_to_name.get(str(rep_data.get("platform_id")))
                    or p_slug_item.upper()
                )
                _, app_id_64, _ = generate_app_id(launcher_exe, canonical_name)
                master_app_ids_64.add(app_id_64)
                if p_display_name not in platform_app_ids_64:
                    platform_app_ids_64[p_display_name] = set()
                platform_app_ids_64[p_display_name].add(app_id_64)

            # Stage 2B: Process Additions (One Steam shortcut per game/sibling group)
            for g_key, members in grouped_additions.items():
                if is_cancelled_callback:
                    cancel_choice = is_cancelled_callback()
                    if cancel_choice == "rollback":
                        logger.warning("User requested sync cancellation with rollback to pre-sync backup %s", backup_id)
                        if backup_id and config_dir:
                            self.backup_manager.restore_backup(backup_id, str(config_dir))
                        return False, "Sync cancelled: Reverted Steam configuration to pre-sync backup.", synced_count
                    elif cancel_choice == "cancel":
                        logger.info("User requested sync cancellation. Stopping sync pass.")
                        if shortcut_map:
                            updated_shortcuts_list = list(shortcut_map.values())
                            vdf_mgr.save_shortcuts(updated_shortcuts_list)
                        return False, f"Sync cancelled by user ({synced_count} games synced).", synced_count

                # Determine active representative ROM
                saved_default = db.kv_config.get(f"default_version:{g_key}")
                rep_id = None
                if saved_default and saved_default.value and saved_default.value.isdigit():
                    cand_id = int(saved_default.value)
                    if any(int(m.get("id") or m.get("rom_id") or 0) == cand_id for m in members):
                        rep_id = cand_id

                if rep_id is None:
                    rep_id = resolve_group_representative(members, installed_ids, bound_ids)

                rep_data = next((m for m in members if int(m.get("id") or m.get("rom_id") or 0) == rep_id), members[0])
                canonical_name = canonical_group_name(members) or rep_data.get("name") or f"ROM {rep_id}"

                p_slug_item = rep_data.get("platform_slug") or (rep_data.get("platform", {}).get("slug") if isinstance(rep_data.get("platform"), dict) else None) or "unknown"
                summary = rep_data.get("summary")
                cover_url = (
                    rep_data.get("path_cover_large")
                    or rep_data.get("path_cover_small")
                    or rep_data.get("cover_url")
                    or rep_data.get("cover_path")
                    or rep_data.get("url_cover")
                )

                p_display_name = (
                    rep_data.get("platform_name")
                    or (rep_data.get("platform", {}).get("name") if isinstance(rep_data.get("platform"), dict) else None)
                    or id_to_name.get(p_slug_item.lower())
                    or id_to_name.get(str(rep_data.get("platform_id")))
                    or p_slug_item.upper()
                )

                tags_dict: dict[str, str] = {"0": "RomM", "1": p_display_name}
                tag_idx = 2

                raw_collections = rep_data.get("collections") or []
                if isinstance(raw_collections, list):
                    for col in raw_collections:
                        col_name = col.get("name") if isinstance(col, dict) else (col if isinstance(col, str) else None)
                        if col_name and col_name not in tags_dict.values():
                            tags_dict[str(tag_idx)] = col_name
                            tag_idx += 1

                app_id_32, app_id_64, str_app_id = generate_app_id(launcher_exe, canonical_name)

                master_app_ids_64.add(app_id_64)
                if p_display_name not in platform_app_ids_64:
                    platform_app_ids_64[p_display_name] = set()
                platform_app_ids_64[p_display_name].add(app_id_64)

                icon_path = str(grid_dir / f"{str_app_id}_icon.png")
                cover_path = str(grid_dir / f"{str_app_id}p.png")
                wide_cover_path = str(grid_dir / f"{str_app_id}.png")
                hero_path = str(grid_dir / f"{str_app_id}_hero.png")
                logo_path = str(grid_dir / f"{str_app_id}_logo.png")

                igdb_id = rep_data.get("igdb_id") or rep_data.get("igdbId")
                if not igdb_id and isinstance(rep_data.get("metadata"), dict):
                    igdb_id = rep_data.get("metadata", {}).get("igdb_id")

                sgdb_id = rep_data.get("sgdb_id") or rep_data.get("sgdbId")
                if not sgdb_id and isinstance(rep_data.get("metadata"), dict):
                    sgdb_id = rep_data.get("metadata", {}).get("sgdb_id")

                if sgdb_client:
                    if not sgdb_id and igdb_id:
                        try:
                            sgdb_id = sgdb_client.get_game_by_igdb_id(int(igdb_id))
                        except (ValueError, TypeError):
                            sgdb_id = None

                    if not sgdb_id:
                        sgdb_id = sgdb_client.search_game_by_name(canonical_name)

                    if sgdb_id:
                        hero_url = sgdb_client.get_asset_url("hero", sgdb_id)
                        if hero_url:
                            sgdb_client.download_image(hero_url, hero_path)

                        logo_url = sgdb_client.get_asset_url("logo", sgdb_id)
                        if logo_url:
                            sgdb_client.download_image(logo_url, logo_path)

                        grid_url = sgdb_client.get_asset_url("grid", sgdb_id)
                        if grid_url:
                            sgdb_client.download_image(grid_url, wide_cover_path)

                        grid_p_url = sgdb_client.get_asset_url("grid_p", sgdb_id)
                        if grid_p_url:
                            sgdb_client.download_image(grid_p_url, cover_path)

                        icon_url = sgdb_client.get_asset_url("icon", sgdb_id)
                        if icon_url:
                            sgdb_client.download_image(icon_url, icon_path)

                if not Path(cover_path).exists() and (cover_url or rep_id):
                    client.download_cover(rep_id, cover_path, cover_url)

                if not Path(wide_cover_path).exists() and (cover_url or rep_id):
                    client.download_cover(rep_id, wide_cover_path, cover_url)

                entry = {
                    "AppName": canonical_name,
                    "Exe": f'"{launcher_exe}"',
                    "StartDir": f'"{str(Path(launcher_exe).parent)}"',
                    "icon": icon_path if Path(icon_path).exists() else "",
                    "ShortcutPath": "",
                    "LaunchOptions": f"--rom-id {rep_id} --platform {p_slug_item}",
                    "IsHidden": 0,
                    "AllowDesktopConfig": 1,
                    "AllowOverlay": 1,
                    "OpenVR": 0,
                    "Devkit": 0,
                    "DevkitGameID": "",
                    "DevkitOverrideAppID": 0,
                    "LastPlayTime": 0,
                    "flatpakAppID": "",
                    "tags": tags_dict,
                    "appid": app_id_32,
                }
                shortcut_map[canonical_name] = entry

                # Unbind existing bindings in group so only representative is bound
                db.roms.unbind_all_in_group(g_key)

                # Persist ALL member ROMs into SQLite DB
                for m in members:
                    m_id = int(m.get("id") or m.get("rom_id") or 0)
                    m_name = m.get("name") or f"ROM {m_id}"
                    m_p_slug = m.get("platform_slug") or (m.get("platform", {}).get("slug") if isinstance(m.get("platform"), dict) else None) or p_slug_item
                    m_summary = m.get("summary")
                    m_cover_url = (
                        m.get("path_cover_large")
                        or m.get("path_cover_small")
                        or m.get("cover_url")
                        or m.get("cover_path")
                        or m.get("url_cover")
                    )
                    m_sgdb = m.get("sgdb_id") or (m.get("metadata", {}).get("sgdb_id") if isinstance(m.get("metadata"), dict) else None)
                    m_igdb = m.get("igdb_id") or (m.get("metadata", {}).get("igdb_id") if isinstance(m.get("metadata"), dict) else None)

                    m_fs_name = m.get("fs_name") or m.get("file_name") or m.get("filename") or m.get("fs_name_no_ext")

                    m_entity = Rom(
                        rom_id=m_id,
                        platform_slug=m_p_slug,
                        name=m_name,
                        shortcut_app_id=app_id_32 if m_id == rep_id else None,
                        sibling_group_key=g_key,
                        summary=m_summary,
                        cover_url=m_cover_url,
                        fs_name=m_fs_name,
                        sgdb_id=int(m_sgdb) if m_sgdb else None,
                        igdb_id=int(m_igdb) if m_igdb else None,
                    )
                    db.roms.add(m_entity)


                synced_count += 1
                work_idx += 1
                progress_pct = 0.40 + (0.50 * (work_idx / max(1, total_work_items)))
                log_progress(progress_pct, f"Added [{work_idx}/{total_work_items}]: {canonical_name}", cover_path=cover_path, rom_name=canonical_name)


            # Stage 2C: Process Removals (Only in "full" sync mode)
            if user_mode == "full":
                for rom in all_removals_roms:
                    if is_cancelled_callback and is_cancelled_callback() in ("cancel", "rollback"):
                        logger.info("User requested cancellation during removal pass.")
                        break

                    rom_name = rom.name
                    _, _, str_app_id = generate_app_id(launcher_exe, rom_name)

                    if rom_name in shortcut_map:
                        del shortcut_map[rom_name]

                    if str_app_id and grid_dir.exists():
                        for suffix in [".png", "p.png", "_icon.png", "_hero.png", "_logo.png"]:
                            art_file = grid_dir / f"{str_app_id}{suffix}"
                            if art_file.exists():
                                try:
                                    art_file.unlink()
                                except Exception as e:
                                    logger.warning("Failed unlinking grid art file %s: %s", art_file, e)

                    db.roms.delete(rom.rom_id)
                    work_idx += 1
                    progress_pct = 0.40 + (0.50 * (work_idx / max(1, total_work_items)))
                    log_progress(progress_pct, f"Removed [{work_idx}/{total_work_items}]: {rom_name}")

                for s in all_removals_shortcuts:
                    app_name = s.get("AppName")
                    if app_name and app_name in shortcut_map:
                        del shortcut_map[app_name]

            # Save shortcuts.vdf
            log_progress(0.95, "Saving binary shortcuts.vdf file...")
            updated_shortcuts_list = list(shortcut_map.values())
            vdf_mgr.save_shortcuts(updated_shortcuts_list)

            # 7. Update Steam CloudCollections in localconfig.vdf
            log_progress(0.98, "Updating Steam Library Collections in localconfig.vdf...")
            localconfig_mgr = SteamLocalConfigManager(str(config_dir))
            localconfig_mgr.update_collections(platform_app_ids_64, master_app_ids_64)

            # Record completed SyncRun
            sync_run.complete(synced_count)
            db.sync_runs.add(sync_run)
            db.commit()
            logger.info(
                "Library sync completed in %.2f seconds (%d ROMs processed)",
                sync_run.duration_seconds or 0.0,
                synced_count,
            )

        msg = f"Library sync complete! {sync_diff.total_additions} added, {sync_diff.total_removals if user_mode == 'full' else 0} removed, {sync_diff.total_unchanged} unchanged."
        log_progress(1.0, msg)
        return True, msg, synced_count

    def get_synced_libraries(self) -> List[Dict[str, Any]]:
        """Fetch list of currently synced collections and shortcut counts."""
        config_dir, _ = SteamPathResolver.get_user_config_dir(
            user_id=self.settings.steam_user_id,
            custom_steam_path=self.settings.steam_custom_path,
        )

        collections: Dict[str, Dict[str, Any]] = {}

        # 1. Inspect SQLite DB records
        with self.db_session as db:
            counts = db.roms.get_platform_counts()
            for slug, count in counts.items():
                canonical_key, display_name = normalize_platform_identifier(slug)
                if canonical_key in collections:
                    collections[canonical_key]["count"] += count
                else:
                    collections[canonical_key] = {
                        "name": display_name,
                        "slug": canonical_key,
                        "count": count,
                    }

        # 2. Inspect shortcuts.vdf tags
        if config_dir:
            vdf_path = config_dir / "shortcuts.vdf"
            if vdf_path.exists():
                vdf_mgr = SteamVdfManager(str(vdf_path))
                shortcuts = vdf_mgr.load_shortcuts()
                vdf_counts: Dict[str, Tuple[str, int]] = {}
                for s in shortcuts:
                    tags = s.get("tags", {})
                    tag_vals = list(tags.values()) if isinstance(tags, dict) else []
                    if "RomM" in tag_vals:
                        p_tag = None
                        if isinstance(tags, dict) and "1" in tags and tags["1"] != "RomM":
                            p_tag = tags["1"]
                        else:
                            for val in tag_vals:
                                if val != "RomM":
                                    p_tag = val
                                    break
                        if p_tag:
                            ckey, dname = normalize_platform_identifier(p_tag)
                            curr_dname, curr_count = vdf_counts.get(ckey, (dname, 0))
                            vdf_counts[ckey] = (dname or curr_dname, curr_count + 1)

                for ckey, (display_name, count) in vdf_counts.items():
                    if ckey in collections:
                        if display_name and display_name != ckey:
                            collections[ckey]["name"] = display_name
                        collections[ckey]["count"] = max(collections[ckey]["count"], count)
                    else:
                        collections[ckey] = {
                            "name": display_name,
                            "slug": ckey,
                            "count": count,
                        }

        return sorted(list(collections.values()), key=lambda x: str(x["name"]))

    def remove_synced_library(
        self,
        platform_identifier: str,
        skip_steam_guard: bool = False,
    ) -> Tuple[bool, str, int]:
        """Remove shortcuts, grid files, Steam collection, and DB state for a specific library."""
        if not skip_steam_guard and SteamGuard.is_steam_running():
            raise SteamRunningException("Steam is currently running. Please close Steam before proceeding with cleanup.")

        config_dir, selected_user_id = SteamPathResolver.get_user_config_dir(
            user_id=self.settings.steam_user_id,
            custom_steam_path=self.settings.steam_custom_path,
        )
        if not config_dir:
            return False, "Could not locate Steam userdata config directory.", 0

        grid_dir = config_dir / "grid"
        vdf_path = config_dir / "shortcuts.vdf"

        # Create pre-cleanup backup
        self.backup_manager.create_backup(str(config_dir))

        vdf_mgr = SteamVdfManager(str(vdf_path))
        shortcuts = vdf_mgr.load_shortcuts()

        target_key, target_display = normalize_platform_identifier(platform_identifier)
        target_aliases = [a.lower() for a in get_platform_aliases(target_key)]

        removed_count = 0
        retained_shortcuts = []
        app_ids_64_to_remove: set[int] = set()

        for s in shortcuts:
            tags = s.get("tags", {})
            tag_vals = [str(v).lower() for v in tags.values()] if isinstance(tags, dict) else []

            is_romm_shortcut = "romm" in tag_vals
            matches_platform = any(
                str(v).lower() in target_aliases
                or str(v).lower().replace(" ", "-") in target_aliases
                or normalize_platform_identifier(str(v))[0] == target_key
                for v in tag_vals
            )

            if is_romm_shortcut and matches_platform:
                removed_count += 1
                app_name = s.get("AppName", "")
                exe = s.get("Exe", "").strip('"')
                app_id_32 = s.get("appid")

                if exe and app_name:
                    _, app_id_64, str_app_id = generate_app_id(exe, app_name)
                    app_ids_64_to_remove.add(app_id_64)
                elif app_id_32:
                    unsigned_32 = app_id_32 if app_id_32 >= 0 else app_id_32 + 0x100000000
                    app_id_64 = (unsigned_32 << 32) | 0x02000000
                    app_ids_64_to_remove.add(app_id_64)
                    str_app_id = str(unsigned_32)
                else:
                    str_app_id = ""

                # Delete grid artwork
                if str_app_id and grid_dir.exists():
                    for suffix in [".png", "p.png", "_icon.png"]:
                        art_file = grid_dir / f"{str_app_id}{suffix}"
                        if art_file.exists():
                            try:
                                art_file.unlink()
                            except Exception as e:
                                logger.warning("Failed unlinking grid art file %s: %s", art_file, e)
            else:
                retained_shortcuts.append(s)

        # Save shortcuts.vdf
        vdf_mgr.save_shortcuts(retained_shortcuts)

        # Remove collection from localconfig.vdf and cloudstorage
        localconfig_mgr = SteamLocalConfigManager(str(config_dir))
        localconfig_mgr.remove_collection(target_display, app_ids_64_to_remove)

        # Delete from SQLite DB
        with self.db_session as db:
            db_removed = db.roms.delete_by_platform(platform_identifier, aliases=target_aliases)
            if db_removed > removed_count:
                removed_count = db_removed
            db.commit()

        msg = f"Successfully removed collection '{target_display}' ({removed_count} games removed)."
        logger.info(msg)
        return True, msg, removed_count

    def remove_all_synced_libraries(
        self,
        skip_steam_guard: bool = False,
    ) -> Tuple[bool, str, int]:
        """Remove all RomM shortcuts, grid artwork files, collections, and DB state."""
        if not skip_steam_guard and SteamGuard.is_steam_running():
            logger.warning("Remove all synced libraries blocked: Steam process running.")
            raise SteamRunningException("Steam is currently running. Please close Steam before proceeding with cleanup.")

        config_dir, selected_user_id = SteamPathResolver.get_user_config_dir(
            user_id=self.settings.steam_user_id,
            custom_steam_path=self.settings.steam_custom_path,
        )
        if not config_dir:
            return False, "Could not locate Steam userdata config directory.", 0

        grid_dir = config_dir / "grid"
        vdf_path = config_dir / "shortcuts.vdf"

        # Create pre-cleanup backup
        self.backup_manager.create_backup(str(config_dir))

        vdf_mgr = SteamVdfManager(str(vdf_path))
        shortcuts = vdf_mgr.load_shortcuts()

        removed_count = 0
        retained_shortcuts = []

        for s in shortcuts:
            tags = s.get("tags", {})
            tag_vals = [str(v).lower() for v in tags.values()] if isinstance(tags, dict) else []

            if "romm" in tag_vals:
                removed_count += 1
                app_name = s.get("AppName", "")
                exe = s.get("Exe", "").strip('"')
                app_id_32 = s.get("appid")

                if exe and app_name:
                    _, _, str_app_id = generate_app_id(exe, app_name)
                elif app_id_32:
                    unsigned_32 = app_id_32 if app_id_32 >= 0 else app_id_32 + 0x100000000
                    str_app_id = str(unsigned_32)
                else:
                    str_app_id = ""

                # Delete grid artwork
                if str_app_id and grid_dir.exists():
                    for suffix in [".png", "p.png", "_icon.png"]:
                        art_file = grid_dir / f"{str_app_id}{suffix}"
                        if art_file.exists():
                            try:
                                art_file.unlink()
                            except Exception as e:
                                logger.warning("Failed unlinking grid art file %s: %s", art_file, e)

            else:
                retained_shortcuts.append(s)

        # Save shortcuts.vdf
        vdf_mgr.save_shortcuts(retained_shortcuts)

        # Remove all RomM collections from localconfig.vdf & cloudstorage
        localconfig_mgr = SteamLocalConfigManager(str(config_dir))
        localconfig_mgr.remove_all_romm_collections()

        # Delete all records from SQLite DB
        with self.db_session as db:
            db_removed = db.roms.delete_all()
            if db_removed > removed_count:
                removed_count = db_removed
            db.commit()

        msg = f"Successfully removed all RomM synced libraries ({removed_count} total games removed)."
        return True, msg, removed_count

