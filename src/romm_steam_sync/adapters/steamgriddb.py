"""SteamGridDB v2 REST API Client Adapter."""

import logging
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

SGDB_BASE_URL = "https://www.steamgriddb.com/api/v2"
USER_AGENT = "romm-steam-sync/1.0"


class SteamGridDbError(Exception):
    """Raised when SteamGridDB API request fails."""


class SteamGridDbClient:
    """Client adapter for interacting with SteamGridDB API v2.

    Attributes:
        api_key: User's SteamGridDB API authentication key.
        base_url: Base URL for the SteamGridDB API v2.
        session: Underlying requests.Session instance.
    """

    def __init__(self, api_key: str = "", base_url: str = SGDB_BASE_URL) -> None:
        """Initialize SteamGridDbClient.

        Args:
            api_key: Optional SteamGridDB API key.
            base_url: Base URL for SteamGridDB API.
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
        })
        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def set_api_key(self, api_key: str) -> None:
        """Update API key header in session.

        Args:
            api_key: New SteamGridDB API key.
        """
        self.api_key = api_key
        if api_key:
            self.session.headers.update({"Authorization": f"Bearer {api_key}"})
        else:
            self.session.headers.pop("Authorization", None)

    def verify_api_key(self, api_key: Optional[str] = None) -> Tuple[bool, str]:
        """Verify API key against SteamGridDB autocomplete test endpoint.

        Args:
            api_key: Optional API key string to test.

        Returns:
            Tuple of (is_valid_boolean, message_string).
        """
        key_to_test = api_key if api_key is not None else self.api_key
        if not key_to_test:
            return False, "API key is required"

        headers = {
            "User-Agent": USER_AGENT,
            "Authorization": f"Bearer {key_to_test}",
        }
        url = f"{self.base_url}/search/autocomplete/test"

        try:
            resp = self.session.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and data.get("success"):
                    return True, "SteamGridDB API key is valid"
                return False, "Invalid response from SteamGridDB"
            if resp.status_code in (401, 403):
                return False, "Invalid or unauthorized SteamGridDB API key"
            return (
                False,
                f"SteamGridDB server returned HTTP {resp.status_code}",
            )
        except requests.exceptions.RequestException as e:
            return False, f"Connection to SteamGridDB failed: {e}"

    def get_game_by_igdb_id(self, igdb_id: int) -> Optional[int]:
        """Lookup SteamGridDB Game ID using IGDB ID.

        Args:
            igdb_id: IGDB integer identifier.

        Returns:
            SteamGridDB game ID if found, or None.
        """
        if not self.api_key:
            return None

        url = f"{self.base_url}/games/igdb/{igdb_id}"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if (
                    isinstance(data, dict)
                    and data.get("success")
                    and "data" in data
                ):
                    game_data = data["data"]
                    if isinstance(game_data, dict) and "id" in game_data:
                        return int(game_data["id"])
            return None
        except Exception as e:
            logger.warning(
                "SteamGridDB IGDB lookup failed for igdb_id %s: %s", igdb_id, e
            )
            return None

    def search_game_by_name(self, name: str) -> Optional[int]:
        """Search SteamGridDB for game by display name and return first matching game ID.

        Args:
            name: Game title to search.

        Returns:
            SteamGridDB game ID if found, or None.
        """
        if not self.api_key or not name:
            return None

        encoded_name = quote(name)
        url = f"{self.base_url}/search/autocomplete/{encoded_name}"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if (
                    isinstance(data, dict)
                    and data.get("success")
                    and "data" in data
                ):
                    results = data["data"]
                    if isinstance(results, list) and len(results) > 0:
                        first = results[0]
                        if isinstance(first, dict) and "id" in first:
                            return int(first["id"])
            return None
        except Exception as e:
            logger.warning("SteamGridDB name search failed for %s: %s", name, e)
            return None

    def search_game(self, name: str) -> Optional[int]:
        """Search SteamGridDB for game by display name (alias for search_game_by_name).

        Args:
            name: Game title to search.

        Returns:
            SteamGridDB game ID if found, or None.
        """
        return self.search_game_by_name(name)

    def get_asset_url(
        self, asset_type: str, sgdb_game_id: int
    ) -> Optional[str]:
        """Fetch highest-rated asset image URL from SGDB for a game ID and asset type.

        Supported asset_types:
          - 'grid_p': Portrait cover (600x900)
          - 'grid': Wide landscape grid (920x430 or 460x215)
          - 'hero': Hero banner (1920x620)
          - 'logo': Logo overlay (transparent PNG)
          - 'icon': App Icon (256x256)

        Args:
            asset_type: Grid asset classification string.
            sgdb_game_id: SteamGridDB game ID.

        Returns:
            Direct image download URL, or None.
        """
        if not self.api_key or not sgdb_game_id:
            return None

        path_map = {
            "hero": f"/heroes/game/{sgdb_game_id}",
            "logo": f"/logos/game/{sgdb_game_id}",
            "grid": f"/grids/game/{sgdb_game_id}?dimensions=460x215,920x430",
            "grid_p": f"/grids/game/{sgdb_game_id}?dimensions=600x900",
            "icon": f"/icons/game/{sgdb_game_id}",
        }

        endpoint = path_map.get(asset_type)
        if not endpoint:
            logger.warning("Unsupported SGDB asset type: %s", asset_type)
            return None

        url = f"{self.base_url}{endpoint}"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if (
                    isinstance(data, dict)
                    and data.get("success")
                    and "data" in data
                ):
                    items = data["data"]
                    if isinstance(items, list) and len(items) > 0:
                        # SteamGridDB sorts returned lists by score / votes descending by default
                        first = items[0]
                        if isinstance(first, dict):
                            # Prefer 'url', fallback to 'thumb'
                            return first.get("url") or first.get("thumb")
            return None
        except Exception as e:
            logger.warning(
                "SteamGridDB asset lookup failed for type %s game %s: %s",
                asset_type,
                sgdb_game_id,
                e,
            )
            return None

    def download_image(self, image_url: str, target_path: str) -> bool:
        """Download image from image_url and save atomically to target_path.

        Args:
            image_url: Remote image URL.
            target_path: Local filesystem destination path.

        Returns:
            True if image was downloaded and written successfully, False otherwise.
        """
        if not image_url or not image_url.startswith("http"):
            return False

        target_p = Path(target_path)
        tmp_p = target_p.with_suffix(target_p.suffix + ".tmp")

        try:
            target_p.parent.mkdir(parents=True, exist_ok=True)
            resp = self.session.get(image_url, timeout=15, stream=True)
            if resp.status_code == 200:
                with open(tmp_p, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                tmp_p.replace(target_p)
                return True

            logger.warning(
                "HTTP %s when downloading image from %s",
                resp.status_code,
                image_url,
            )
            if tmp_p.exists():
                tmp_p.unlink(missing_ok=True)
            return False
        except Exception as e:
            logger.warning("Failed to download image from %s: %s", image_url, e)
            if tmp_p.exists():
                tmp_p.unlink(missing_ok=True)
            return False
