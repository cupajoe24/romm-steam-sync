"""RomM v4.9+ REST API Client Adapter."""

import logging
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


class RomMTimeoutError(Exception):
    """Raised when RomM API requests time out after retries."""


class RomMApiClient:
    """REST API Client for communicating with a RomM server instance.

    Attributes:
        base_url: Normalized base URL of the RomM server.
        api_key: Bearer token / API key.
        session: Underlying requests.Session instance.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
    ) -> None:
        """Initialize RomMApiClient with server credentials.

        Args:
            base_url: Base URL of the RomM server (e.g. 'http://localhost:8080').
            api_key: API key or access token for Bearer authentication.
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()

        if self.api_key:
            self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def _request_with_retry(
        self,
        method: str,
        url: str,
        retries: int = 3,
        backoff: float = 1.0,
        **kwargs: Any,
    ) -> requests.Response:
        """Execute HTTP request with automatic retries on timeout or connection errors.

        Args:
            method: HTTP method string (e.g. 'GET', 'POST', 'PUT').
            url: Destination request URL.
            retries: Maximum number of retry attempts.
            backoff: Multiplier for exponential backoff sleep.
            **kwargs: Additional parameters passed to requests call.

        Returns:
            Successful requests.Response object.

        Raises:
            RomMTimeoutError: If request times out across all retry attempts.
        """
        timeout = kwargs.pop("timeout", 15)
        last_exc = None

        m = method.upper()
        if m == "GET":
            req_func = lambda u, **k: self.session.get(u, **k)
        elif m == "POST":
            req_func = lambda u, **k: self.session.post(u, **k)
        else:
            req_func = lambda u, **k: self.session.request(method, u, **k)

        for attempt in range(1, retries + 1):
            try:
                resp = req_func(url, timeout=timeout, **kwargs)
                return resp
            except (
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
            ) as e:
                last_exc = e
                logger.warning(
                    "[%d/%d] RomM API request to %s timed out/failed: %s",
                    attempt,
                    retries,
                    url,
                    e,
                )
                if attempt < retries:
                    time.sleep(backoff * attempt)

        raise RomMTimeoutError(
            f"RomM API request to {url} timed out after {retries} attempts: {last_exc}"
        )

    def test_connection(self) -> Tuple[bool, str]:
        """Test connection and authenticate with RomM server.

        Returns:
            Tuple of (success_boolean, status_message).
        """
        return self.authenticate()

    def authenticate(self) -> Tuple[bool, str]:
        """Authenticate with RomM server and verify connection.

        Returns:
            Tuple of (authenticated_boolean, message_string).
        """
        if not self.base_url:
            return False, "Server URL is required"

        try:
            # 1. Try API key via /api/users/me endpoint
            if self.api_key:
                resp = self.session.get(f"{self.base_url}/api/users/me", timeout=8)
                if resp.status_code == 200:
                    return True, "Successfully authenticated via API key"

            # 2. Check public API endpoint /api/platforms if no auth set
            resp = self.session.get(f"{self.base_url}/api/platforms", timeout=8)
            if resp.status_code == 200:
                return True, "Connected to RomM (unauthenticated/guest mode)"
            if resp.status_code in (401, 403):
                return (
                    False,
                    "Authentication required. Please provide a valid API key.",
                )
            return False, f"Server responded with status code {resp.status_code}"

        except requests.exceptions.RequestException as e:
            return False, f"Connection failed: {str(e)}"

    def get_platforms(self) -> List[Dict[str, Any]]:
        """Fetch available platforms from RomM.

        Returns:
            List of platform dictionaries.
        """
        url = f"{self.base_url}/api/platforms"
        resp = self._request_with_retry("GET", url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "platforms" in data:
            return data["platforms"]
        return []

    def get_roms(
        self,
        platform_id: Optional[int] = None,
        platform_slug: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch ROMs from RomM with platform_ids query parameter, offset pagination, and fallback matching.

        Args:
            platform_id: Optional integer ID of platform to filter.
            platform_slug: Optional platform slug string.

        Returns:
            List of ROM metadata dictionaries.
        """
        roms: List[Dict[str, Any]] = []
        offset = 0
        limit = 100

        while True:
            params: Dict[str, Any] = {"limit": limit, "offset": offset}
            if platform_id is not None:
                params["platform_ids"] = platform_id

            url = f"{self.base_url}/api/roms"
            resp = self._request_with_retry("GET", url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            items = []
            total = None
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("items") or data.get("roms") or []
                total = data.get("total")

            if not items:
                break

            for item in items:
                item_p_id = item.get("platform_id")
                if item_p_id is None and isinstance(item.get("platform"), dict):
                    item_p_id = item.get("platform", {}).get("id")

                item_p_slug = item.get("platform_slug")
                if item_p_slug is None and isinstance(item.get("platform"), dict):
                    item_p_slug = item.get("platform", {}).get("slug")

                # If server didn't filter by platform_ids, verify platform match client-side
                if platform_id is not None and item_p_id is not None:
                    if item_p_id != platform_id:
                        continue
                elif platform_slug is not None and item_p_slug is not None:
                    if item_p_slug.lower() != platform_slug.lower():
                        continue

                roms.append(item)

            offset += len(items)
            if len(items) < limit or (total is not None and offset >= total):
                break

        # Fallback: if platform_ids query returned 0 items but platform_slug/platform_id was given,
        # perform an unfiltered fetch of initial ROMs and match client-side
        if not roms and (platform_id is not None or platform_slug is not None):
            logger.info(
                "platform_ids query returned 0 items; attempting fallback fetch for %s (id=%s)",
                platform_slug,
                platform_id,
            )
            try:
                resp = self._request_with_retry(
                    "GET",
                    f"{self.base_url}/api/roms",
                    params={"limit": 300, "offset": 0},
                    timeout=15,
                )
                if resp.status_code == 200:
                    fb_data = resp.json()
                    fb_items = (
                        fb_data.get("items", [])
                        if isinstance(fb_data, dict)
                        else (fb_data if isinstance(fb_data, list) else [])
                    )
                    for item in fb_items:
                        s = item.get("platform_slug") or (
                            item.get("platform", {}).get("slug")
                            if isinstance(item.get("platform"), dict)
                            else None
                        )
                        p = item.get("platform_id") or (
                            item.get("platform", {}).get("id")
                            if isinstance(item.get("platform"), dict)
                            else None
                        )

                        matches_id = platform_id is not None and p == platform_id
                        matches_slug = (
                            platform_slug is not None
                            and s is not None
                            and s.lower() == platform_slug.lower()
                        )

                        if matches_id or matches_slug:
                            roms.append(item)
            except Exception as e:
                logger.warning("Fallback ROM fetch error: %s", e)

        return roms

    def download_cover(
        self,
        rom_id: int,
        target_path: str,
        cover_url: Optional[str] = None,
    ) -> bool:
        """Download cover art image for a ROM and save to target path.

        Args:
            rom_id: RomM identifier of the ROM.
            target_path: Destination local file path for image.
            cover_url: Optional remote URL override.

        Returns:
            True if download succeeded, False otherwise.
        """
        try:
            url = cover_url
            if url:
                if url.startswith("http://") or url.startswith("https://"):
                    full_url = url
                elif url.startswith("/"):
                    full_url = f"{self.base_url}{url}"
                else:
                    full_url = f"{self.base_url}/{url}"
            else:
                try:
                    detail = self.get_rom_detail(rom_id)
                    cand_url = (
                        detail.get("path_cover_large")
                        or detail.get("path_cover_small")
                        or detail.get("url_cover")
                        or detail.get("cover_url")
                        or detail.get("cover_path")
                    )
                    if cand_url:
                        if cand_url.startswith("http://") or cand_url.startswith("https://"):
                            full_url = cand_url
                        elif cand_url.startswith("/"):
                            full_url = f"{self.base_url}{cand_url}"
                        else:
                            full_url = f"{self.base_url}/{cand_url}"
                    else:
                        full_url = f"{self.base_url}/api/roms/{rom_id}/cover"
                except Exception as e:
                    logger.debug("Could not fetch ROM detail for cover download: %s", e)
                    full_url = f"{self.base_url}/api/roms/{rom_id}/cover"

            resp = self._request_with_retry("GET", full_url, timeout=15, stream=True)
            if resp.status_code == 200:
                with open(target_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
            logger.warning(
                "Cover download returned status %d for URL %s",
                resp.status_code,
                full_url,
            )
            return False
        except Exception as e:
            logger.warning("Failed to download cover for ROM %s: %s", rom_id, e)
            return False

    def get_rom_detail(self, rom_id: int) -> Dict[str, Any]:
        """Fetch details for a single ROM by ID.

        Args:
            rom_id: RomM identifier of the ROM.

        Returns:
            ROM detail metadata dictionary.
        """
        url = f"{self.base_url}/api/roms/{rom_id}"
        resp = self._request_with_retry("GET", url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, dict) else {}

    def get_rom_file_size(self, rom_id: int, file_name: str = "") -> int:
        """Query HEAD endpoint on RomM server to obtain ROM file Content-Length in bytes.

        Args:
            rom_id: RomM identifier of the ROM.
            file_name: Optional filename of the ROM asset.

        Returns:
            File size in bytes, or 0 if undetermined.
        """
        name_param = file_name or "rom.bin"
        urls_to_try = [
            f"{self.base_url}/api/roms/{rom_id}/content/{name_param}",
            f"{self.base_url}/api/roms/{rom_id}/files/content/{name_param}",
            f"{self.base_url}/api/roms/{rom_id}/content",
        ]
        for url in urls_to_try:
            try:
                resp = self.session.head(url, timeout=10)
                if resp.status_code == 200 and "content-length" in resp.headers:
                    return int(resp.headers["content-length"])
            except Exception as e:
                logger.debug("HEAD request failed for url %s: %s", url, e)
        return 0

    def download_rom_content(
        self,
        rom_id: int,
        target_path: str,
        file_name: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> bool:
        """Stream download binary ROM file from RomM endpoint to target_path with progress callback.

        RomM API v4.9+ specifies GET /api/roms/{id}/content/{file_name}.

        Args:
            rom_id: RomM identifier of the ROM.
            target_path: Destination local file path.
            file_name: Optional filename on RomM server.
            progress_callback: Optional callback receiving (bytes_downloaded, total_bytes).

        Returns:
            True if download succeeded, False otherwise.
        """
        target_p = Path(target_path)
        name_param = file_name or target_p.name

        urls_to_try = [
            f"{self.base_url}/api/roms/{rom_id}/content/{name_param}",
            f"{self.base_url}/api/roms/{rom_id}/files/content/{name_param}",
            f"{self.base_url}/api/roms/{rom_id}/content",
        ]

        last_error = None
        for url in urls_to_try:
            try:
                resp = self.session.get(url, timeout=120, stream=True)
                if resp.status_code == 200:
                    total_bytes = int(resp.headers.get("content-length", 0))
                    downloaded_bytes = 0

                    target_p.parent.mkdir(parents=True, exist_ok=True)

                    with open(target_p, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=65536):
                            if chunk:
                                f.write(chunk)
                                downloaded_bytes += len(chunk)
                                if progress_callback:
                                    progress_callback(downloaded_bytes, total_bytes)
                    return True
                last_error = f"HTTP {resp.status_code} for url: {url}"
            except Exception as e:
                last_error = str(e)

        logger.error(
            "Failed to download ROM content for rom_id %s: %s", rom_id, last_error
        )
        return False

    def get_saves(
        self,
        rom_id: int,
        slot: Optional[str] = "autosave",
    ) -> List[Dict[str, Any]]:
        """Fetch save entries for a given ROM ID from RomM API, prioritizing the active slot.

        Args:
            rom_id: RomM identifier of the ROM.
            slot: Target slot name (defaults to 'autosave').

        Returns:
            List of save dictionaries with slot-matching saves ordered first.
        """
        url = f"{self.base_url}/api/saves"
        params: Dict[str, Any] = {"rom_id": rom_id}
        if slot:
            params["slot"] = slot

        resp = self._request_with_retry("GET", url, params=params, timeout=15)
        saves: List[Dict[str, Any]] = []
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list):
                saves = data
            elif isinstance(data, dict):
                saves = data.get("saves") or data.get("items") or []

        if not saves and slot:
            # Fallback query without slot parameter if slot-specific search returned no items
            params_no_slot = {"rom_id": rom_id}
            resp_no_slot = self._request_with_retry(
                "GET", url, params=params_no_slot, timeout=15
            )
            if resp_no_slot.status_code == 200:
                data2 = resp_no_slot.json()
                if isinstance(data2, list):
                    saves = data2
                elif isinstance(data2, dict):
                    saves = data2.get("saves") or data2.get("items") or []

        # Sort saves so that saves matching active slot come first
        if slot and saves:
            slot_matches = [
                s
                for s in saves
                if str(s.get("slot") or "").strip().lower() == slot.lower()
            ]
            other_saves = [s for s in saves if s not in slot_matches]
            return slot_matches + other_saves

        return saves

    def download_save_content(self, save_id: int, target_path: str) -> bool:
        """Download binary save file content from RomM to target_path.

        Args:
            save_id: RomM save record identifier.
            target_path: Local filesystem destination path.

        Returns:
            True if download succeeded, False otherwise.
        """
        url = f"{self.base_url}/api/saves/{save_id}/content"
        try:
            resp = self._request_with_retry("GET", url, timeout=30, stream=True)
            if resp.status_code == 200:
                target_p = Path(target_path)
                target_p.parent.mkdir(parents=True, exist_ok=True)
                with open(target_p, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                return True
            logger.warning(
                "Failed to download save content (HTTP %s) for save_id %s",
                resp.status_code,
                save_id,
            )
            return False
        except Exception as e:
            logger.error(
                "Error downloading save content for save_id %s: %s", save_id, e
            )
            return False

    def upload_save(
        self,
        rom_id: int,
        file_path: str,
        save_id: Optional[int] = None,
        emulator: str = "retroarch",
        slot: Optional[str] = "autosave",
    ) -> Dict[str, Any]:
        """Upload local save file to RomM. Creates a new save entry (POST) or updates existing (PUT).

        Args:
            rom_id: RomM identifier of the ROM.
            file_path: Local save file path to upload.
            save_id: Optional save record ID for in-place updates.
            emulator: Emulator identifier string (e.g. 'retroarch', 'dolphin').
            slot: Target save slot name (e.g. 'autosave').

        Returns:
            Response dictionary from RomM API containing save metadata.

        Raises:
            FileNotFoundError: If the local save file does not exist.
        """
        file_p = Path(file_path)
        if not file_p.exists():
            raise FileNotFoundError(f"Local save file not found: {file_path}")

        params = {"rom_id": str(rom_id), "emulator": emulator}
        if slot:
            params["slot"] = slot

        if save_id:
            url = f"{self.base_url}/api/saves/{save_id}"
            method = "PUT"
        else:
            url = f"{self.base_url}/api/saves"
            method = "POST"

        with open(file_p, "rb") as f:
            # RomM v4.9+ API expects form field name "saveFile"
            files = {"saveFile": (file_p.name, f, "application/octet-stream")}
            resp = self._request_with_retry(
                method, url, params=params, files=files, timeout=45
            )
            resp.raise_for_status()
            res_data = resp.json()
            return res_data if isinstance(res_data, dict) else {"id": save_id}

    def ingest_play_sessions(
        self,
        device_id: str,
        sessions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Ingest play session entries to RomM to record playtime and update recently played.

        Args:
            device_id: Unique UUID string for this client machine.
            sessions: List of serialized PlaySession dictionaries.

        Returns:
            Response dictionary from RomM API.
        """
        url = f"{self.base_url}/api/play-sessions"
        payload = {"device_id": device_id, "sessions": sessions}
        try:
            resp = self._request_with_retry("POST", url, json=payload, timeout=20)
            if resp.status_code in (200, 201):
                logger.info(
                    "Successfully ingested %d play session(s) to RomM", len(sessions)
                )
                return resp.json() if resp.text else {"status": "ok"}
            logger.warning(
                "Failed ingesting play sessions (HTTP %s): %s",
                resp.status_code,
                resp.text[:200],
            )
            return {"error": f"HTTP {resp.status_code}"}
        except Exception as e:
            logger.warning("Error ingesting play sessions to RomM: %s", e)
            return {"error": str(e)}
