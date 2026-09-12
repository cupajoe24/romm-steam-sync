"""Steam localconfig.vdf and cloudstorage collection manager."""

import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Set

import vdf

logger = logging.getLogger(__name__)


class SteamLocalConfigManager:
    """Manages reading, mutating, and saving Steam Library Collections in localconfig.vdf and cloudstorage.

    Attributes:
        config_dir: Path to Steam user profile configuration directory.
        localconfig_path: Path to user's localconfig.vdf file.
    """

    def __init__(self, config_dir: str) -> None:
        """Initialize SteamLocalConfigManager.

        Args:
            config_dir: Path string to the Steam user config folder.
        """
        self.config_dir = Path(config_dir)
        self.localconfig_path = self.config_dir / "localconfig.vdf"

    def update_collections(
        self,
        platform_app_ids: Dict[str, Set[int]],
        master_app_ids: Set[int],
    ) -> bool:
        """Update or create Steam Library Collections in localconfig.vdf and cloudstorage.

        Args:
            platform_app_ids: Map of platform display name to set of 64-bit AppIDs.
            master_app_ids: Set of 64-bit AppIDs for all RomM games.

        Returns:
            True if collections were updated successfully, False otherwise.
        """
        if not self.localconfig_path.exists():
            logger.warning(
                "localconfig.vdf does not exist at %s", self.localconfig_path
            )
            return False

        try:
            with open(
                self.localconfig_path, "r", encoding="utf-8", errors="ignore"
            ) as f:
                data = vdf.load(f)

            user_store = data.setdefault("UserLocalConfigStore", {})
            cloud_cols = user_store.setdefault("CloudCollections", {})

            # Build set of active RomM collection keys
            valid_romm_keys = {"user-collection-romm"}
            for p_name in platform_app_ids.keys():
                slug = (
                    p_name.lower()
                    .replace(" ", "-")
                    .replace(":", "")
                    .replace("/", "")
                )
                valid_romm_keys.add(f"user-collection-{slug}")

            # Prune stale empty collections starting with user-collection-
            stale_keys = []
            for k, v in list(cloud_cols.items()):
                if k.startswith("user-collection-romm--"):
                    stale_keys.append(k)
                elif k.startswith("user-collection-") and k not in valid_romm_keys:
                    if isinstance(v, dict):
                        raw_added = v.get("added", "[]")
                        if raw_added in ("[]", [], "") or not raw_added:
                            stale_keys.append(k)

            for k in stale_keys:
                logger.info(
                    "Removing stale empty collection from localconfig.vdf: %s", k
                )
                cloud_cols.pop(k, None)

            # 1. Update Master "RomM" Collection
            if master_app_ids:
                cloud_cols["user-collection-romm"] = {
                    "id": "user-collection-romm",
                    "name": "RomM",
                    "added": json.dumps(sorted(list(master_app_ids))),
                    "removed": "[]",
                }

            # 2. Update Platform Collections
            for p_name, app_ids in platform_app_ids.items():
                if not app_ids:
                    continue
                slug = (
                    p_name.lower()
                    .replace(" ", "-")
                    .replace(":", "")
                    .replace("/", "")
                )
                col_id = f"user-collection-{slug}"

                # Parse existing added IDs to merge if collection already exists
                existing_added: Set[int] = set()
                if col_id in cloud_cols and isinstance(cloud_cols[col_id], dict):
                    raw_existing = cloud_cols[col_id].get("added", "[]")
                    try:
                        if isinstance(raw_existing, list):
                            existing_added = set(raw_existing)
                        elif isinstance(raw_existing, str):
                            existing_added = set(json.loads(raw_existing))
                    except Exception as e:
                        logger.debug(
                            "Could not parse existing added items for %s: %s",
                            col_id,
                            e,
                        )
                        existing_added = set()

                merged_added = existing_added.union(app_ids)

                cloud_cols[col_id] = {
                    "id": col_id,
                    "name": p_name,
                    "added": json.dumps(sorted(list(merged_added))),
                    "removed": "[]",
                }

            # Write updated localconfig.vdf atomically
            tmp_path = self.config_dir / "localconfig.vdf.tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                vdf.dump(data, f, pretty=True)

            tmp_path.replace(self.localconfig_path)
            logger.info(
                "Successfully updated Steam CloudCollections in localconfig.vdf"
            )

            # Also update modern Steam cloudstorage collections
            self.update_cloudstorage_collections(platform_app_ids, master_app_ids)
            return True

        except Exception as e:
            logger.error("Failed to update localconfig.vdf collections: %s", e)
            return False

    def update_cloudstorage_collections(
        self,
        platform_app_ids: Dict[str, Set[int]],
        master_app_ids: Set[int],
    ) -> bool:
        """Update or create Steam Library Collections in cloudstorage format.

        Args:
            platform_app_ids: Mapping of platform name to 64-bit AppID sets.
            master_app_ids: Full set of 64-bit AppIDs for all RomM titles.

        Returns:
            True if cloudstorage updated successfully, False otherwise.
        """
        cs_dir = self.config_dir / "cloudstorage"
        cs_dir.mkdir(parents=True, exist_ok=True)
        json_path = cs_dir / "cloud-storage-namespace-1.json"
        ns_ver_path = cs_dir / "cloud-storage-namespaces.json"

        items = []
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    items = json.load(f)
            except Exception as e:
                logger.warning(
                    "Failed to load existing cloud-storage-namespace-1.json: %s", e
                )

        ns_ver = [[1, "1"], [3, "0"]]
        cur_ver_int = 1
        if ns_ver_path.exists():
            try:
                with open(ns_ver_path, "r", encoding="utf-8") as f:
                    ns_ver = json.load(f)
                for pair in ns_ver:
                    if pair[0] == 1:
                        cur_ver_int = int(pair[1])
            except Exception as e:
                logger.warning(
                    "Failed to load cloud-storage-namespaces.json: %s", e
                )

        next_ver_str = str(cur_ver_int + 1)
        now_ts = int(time.time())

        # Map existing items by key string
        item_map: Dict[str, int] = {}
        for idx, entry in enumerate(items):
            if isinstance(entry, list) and len(entry) == 2:
                item_map[entry[0]] = idx

        def set_cloud_entry(
            col_id: str, name: str, app_ids: Set[int]
        ) -> None:
            """Format and set a single collection record inside the namespace JSON."""
            key_name = f"user-collections.{col_id}"

            # Merge existing added IDs if collection already exists
            existing_added: Set[int] = set()
            if key_name in item_map:
                try:
                    existing_val = items[item_map[key_name]][1].get("value", "")
                    if existing_val:
                        v_data = json.loads(existing_val)
                        existing_added = set(v_data.get("added", []))
                except Exception as e:
                    logger.debug(
                        "Failed parsing existing cloudstorage entry for %s: %s",
                        key_name,
                        e,
                    )
                    existing_added = set()

            # Convert 64-bit AppIDs to 32-bit unsigned integers for cloudstorage format
            unsigned_32_ids: Set[int] = set()
            for x in app_ids.union(existing_added):
                if x > 0xFFFFFFFF:
                    unsigned_32_ids.add((x >> 32) & 0xFFFFFFFF)
                else:
                    unsigned_32_ids.add(x & 0xFFFFFFFF)

            val_dict = {
                "id": col_id,
                "name": name,
                "added": sorted(list(unsigned_32_ids)),
                "removed": [],
            }
            info_dict = {
                "key": key_name,
                "timestamp": now_ts,
                "value": json.dumps(val_dict, separators=(",", ":")),
                "version": next_ver_str,
                "conflictResolutionMethod": "custom",
                "strMethodId": "union-collections",
            }
            entry = [key_name, info_dict]
            if key_name in item_map:
                items[item_map[key_name]] = entry
            else:
                items.append(entry)
                item_map[key_name] = len(items) - 1

        # 1. Master RomM collection
        if master_app_ids:
            set_cloud_entry("user-collection-romm", "RomM", master_app_ids)

        # 2. Platform collections
        for p_name, app_ids in platform_app_ids.items():
            if not app_ids:
                continue
            slug = (
                p_name.lower()
                .replace(" ", "-")
                .replace(":", "")
                .replace("/", "")
            )
            col_id = f"user-collection-{slug}"
            set_cloud_entry(col_id, p_name, app_ids)

        # Update namespace version header
        for pair in ns_ver:
            if pair[0] == 1:
                pair[1] = next_ver_str

        # Atomic write
        tmp_json = cs_dir / "cloud-storage-namespace-1.json.tmp"
        with open(tmp_json, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2)
        tmp_json.replace(json_path)

        tmp_ns = cs_dir / "cloud-storage-namespaces.json.tmp"
        with open(tmp_ns, "w", encoding="utf-8") as f:
            json.dump(ns_ver, f)
        tmp_ns.replace(ns_ver_path)

        logger.info(
            "Successfully updated Steam cloudstorage collections (version %s)",
            next_ver_str,
        )
        return True

    def remove_collection(
        self,
        collection_identifier: str,
        app_ids_64_to_remove: Set[int],
    ) -> bool:
        """Remove a specific platform collection and update master RomM collection.

        Args:
            collection_identifier: Display name or slug of target collection.
            app_ids_64_to_remove: Set of 64-bit AppIDs belonging to the removed collection.

        Returns:
            True if removed successfully, False otherwise.
        """
        slug = (
            collection_identifier.lower()
            .replace(" ", "-")
            .replace(":", "")
            .replace("/", "")
        )
        col_id = f"user-collection-{slug}"

        # 1. Update localconfig.vdf
        if self.localconfig_path.exists():
            try:
                with open(
                    self.localconfig_path, "r", encoding="utf-8", errors="ignore"
                ) as f:
                    data = vdf.load(f)

                user_store = data.setdefault("UserLocalConfigStore", {})
                cloud_cols = user_store.setdefault("CloudCollections", {})

                # Pop target platform collection
                keys_to_pop = [
                    k
                    for k, v in list(cloud_cols.items())
                    if k == col_id
                    or (
                        isinstance(v, dict)
                        and str(v.get("name", "")).lower()
                        == collection_identifier.lower()
                    )
                ]
                for k in keys_to_pop:
                    logger.info("Removing collection %s from localconfig.vdf", k)
                    cloud_cols.pop(k, None)

                # Update master user-collection-romm
                if "user-collection-romm" in cloud_cols and isinstance(
                    cloud_cols["user-collection-romm"], dict
                ):
                    raw_existing = cloud_cols["user-collection-romm"].get(
                        "added", "[]"
                    )
                    existing_added = set()
                    try:
                        if isinstance(raw_existing, list):
                            existing_added = set(raw_existing)
                        elif isinstance(raw_existing, str):
                            existing_added = set(json.loads(raw_existing))
                    except Exception as e:
                        logger.debug(
                            "Failed parsing user-collection-romm added items during collection removal: %s",
                            e,
                        )

                    remaining = existing_added - app_ids_64_to_remove
                    if remaining:
                        cloud_cols["user-collection-romm"]["added"] = (
                            json.dumps(sorted(list(remaining)))
                        )
                    else:
                        cloud_cols.pop("user-collection-romm", None)

                tmp_path = self.config_dir / "localconfig.vdf.tmp"
                with open(tmp_path, "w", encoding="utf-8") as f:
                    vdf.dump(data, f, pretty=True)
                tmp_path.replace(self.localconfig_path)

            except Exception as e:
                logger.error(
                    "Failed to remove collection %s from localconfig.vdf: %s",
                    collection_identifier,
                    e,
                )

        # 2. Update cloudstorage
        self.remove_cloudstorage_collection(
            col_id, collection_identifier, app_ids_64_to_remove
        )
        return True

    def remove_cloudstorage_collection(
        self,
        col_id: str,
        collection_name: str,
        app_ids_64_to_remove: Set[int],
    ) -> bool:
        """Remove a collection from cloudstorage namespace JSON.

        Args:
            col_id: Collection identifier string.
            collection_name: Human readable collection name.
            app_ids_64_to_remove: Set of 64-bit AppIDs to remove.

        Returns:
            True if removed successfully, False otherwise.
        """
        cs_dir = self.config_dir / "cloudstorage"
        json_path = cs_dir / "cloud-storage-namespace-1.json"
        ns_ver_path = cs_dir / "cloud-storage-namespaces.json"

        if not json_path.exists():
            return False

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                items = json.load(f)

            ns_ver = [[1, "1"], [3, "0"]]
            cur_ver_int = 1
            if ns_ver_path.exists():
                try:
                    with open(ns_ver_path, "r", encoding="utf-8") as f:
                        ns_ver = json.load(f)
                    for pair in ns_ver:
                        if pair[0] == 1:
                            cur_ver_int = int(pair[1])
                except Exception as e:
                    logger.debug(
                        "Failed parsing cloud-storage-namespaces.json during collection removal: %s",
                        e,
                    )

            next_ver_str = str(cur_ver_int + 1)
            now_ts = int(time.time())

            target_key = f"user-collections.{col_id}"
            rem_32 = set()
            for x in app_ids_64_to_remove:
                if x > 0xFFFFFFFF:
                    rem_32.add((x >> 32) & 0xFFFFFFFF)
                else:
                    rem_32.add(x & 0xFFFFFFFF)

            new_items = []
            for entry in items:
                if not (isinstance(entry, list) and len(entry) == 2):
                    new_items.append(entry)
                    continue

                key_name, info_dict = entry[0], entry[1]

                # Filter target collection
                if key_name == target_key:
                    continue

                # Filter if name matches inside value JSON
                if (
                    key_name.startswith("user-collections.user-collection-")
                    and key_name != "user-collections.user-collection-romm"
                ):
                    try:
                        v_json = json.loads(info_dict.get("value", "{}"))
                        if (
                            str(v_json.get("name", "")).lower()
                            == collection_name.lower()
                        ):
                            continue
                    except Exception as e:
                        logger.debug(
                            "Failed parsing collection entry value JSON: %s", e
                        )

                # Update master collection
                if key_name == "user-collections.user-collection-romm":
                    try:
                        v_json = json.loads(info_dict.get("value", "{}"))
                        current_added = set(v_json.get("added", []))
                        remaining_added = current_added - rem_32
                        if not remaining_added:
                            continue
                        v_json["added"] = sorted(list(remaining_added))
                        info_dict["value"] = json.dumps(
                            v_json, separators=(",", ":")
                        )
                        info_dict["timestamp"] = now_ts
                        info_dict["version"] = next_ver_str
                    except Exception as e:
                        logger.debug(
                            "Failed updating master user-collection-romm in cloudstorage: %s",
                            e,
                        )

                new_items.append(entry)

            # Save namespace files
            for pair in ns_ver:
                if pair[0] == 1:
                    pair[1] = next_ver_str

            tmp_json = cs_dir / "cloud-storage-namespace-1.json.tmp"
            with open(tmp_json, "w", encoding="utf-8") as f:
                json.dump(new_items, f, indent=2)
            tmp_json.replace(json_path)

            if ns_ver_path.exists():
                tmp_ns = cs_dir / "cloud-storage-namespaces.json.tmp"
                with open(tmp_ns, "w", encoding="utf-8") as f:
                    json.dump(ns_ver, f)
                tmp_ns.replace(ns_ver_path)

            return True
        except Exception as e:
            logger.error("Failed to remove collection from cloudstorage: %s", e)
            return False

    def remove_all_romm_collections(self) -> bool:
        """Remove all RomM collections from localconfig.vdf and cloudstorage.

        Returns:
            True if all collections removed cleanly.
        """
        # 1. localconfig.vdf
        if self.localconfig_path.exists():
            try:
                with open(
                    self.localconfig_path, "r", encoding="utf-8", errors="ignore"
                ) as f:
                    data = vdf.load(f)

                user_store = data.setdefault("UserLocalConfigStore", {})
                cloud_cols = user_store.setdefault("CloudCollections", {})

                keys_to_pop = [
                    k
                    for k in cloud_cols.keys()
                    if k == "user-collection-romm"
                    or k.startswith("user-collection-")
                ]
                for k in keys_to_pop:
                    cloud_cols.pop(k, None)

                tmp_path = self.config_dir / "localconfig.vdf.tmp"
                with open(tmp_path, "w", encoding="utf-8") as f:
                    vdf.dump(data, f, pretty=True)
                tmp_path.replace(self.localconfig_path)
            except Exception as e:
                logger.error(
                    "Failed to remove all collections from localconfig.vdf: %s", e
                )

        # 2. cloudstorage
        cs_dir = self.config_dir / "cloudstorage"
        json_path = cs_dir / "cloud-storage-namespace-1.json"
        ns_ver_path = cs_dir / "cloud-storage-namespaces.json"

        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    items = json.load(f)

                ns_ver = [[1, "1"], [3, "0"]]
                cur_ver_int = 1
                if ns_ver_path.exists():
                    try:
                        with open(ns_ver_path, "r", encoding="utf-8") as f:
                            ns_ver = json.load(f)
                        for pair in ns_ver:
                            if pair[0] == 1:
                                cur_ver_int = int(pair[1])
                    except Exception as e:
                        logger.debug(
                            "Failed parsing cloud-storage-namespaces.json in remove_all_romm_collections: %s",
                            e,
                        )

                next_ver_str = str(cur_ver_int + 1)
                new_items = [
                    entry
                    for entry in items
                    if not (
                        isinstance(entry, list)
                        and len(entry) == 2
                        and str(entry[0]).startswith(
                            "user-collections.user-collection-"
                        )
                    )
                ]

                for pair in ns_ver:
                    if pair[0] == 1:
                        pair[1] = next_ver_str

                tmp_json = cs_dir / "cloud-storage-namespace-1.json.tmp"
                with open(tmp_json, "w", encoding="utf-8") as f:
                    json.dump(new_items, f, indent=2)
                tmp_json.replace(json_path)

                if ns_ver_path.exists():
                    tmp_ns = cs_dir / "cloud-storage-namespaces.json.tmp"
                    with open(tmp_ns, "w", encoding="utf-8") as f:
                        json.dump(ns_ver, f)
                    tmp_ns.replace(ns_ver_path)

            except Exception as e:
                logger.error(
                    "Failed to remove all collections from cloudstorage: %s", e
                )

        return True
