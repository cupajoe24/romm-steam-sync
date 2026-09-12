"""Unit tests for BaseRetroArchAdapter and shared RetroArch utility functions."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from romm_steam_sync.adapters.retroarch.base import (
    BaseRetroArchAdapter,
    CORE_NAME_FALLBACKS,
    DEFAULT_CORE_MAPPINGS,
    PLATFORM_CORE_CANDIDATES,
    RetroArchFlavor,
    clean_subprocess_env,
    get_core_suffix,
    is_retroarch_running,
    lookup_platform_mapping,
    normalize_core_stem,
    normalize_platform_slug,
    parse_core_info,
    parse_retroarch_cfg_line,
    strip_core_suffix,
)


class DummyRetroArchAdapter(BaseRetroArchAdapter):
    """Concrete implementation of BaseRetroArchAdapter for testing shared logic."""

    @property
    def flavor(self) -> RetroArchFlavor:
        return RetroArchFlavor.STANDALONE

    @property
    def flavor_name(self) -> str:
        return "Dummy RetroArch"

    def resolve_binary(self) -> Path:
        return Path("/dummy/bin/retroarch")

    def resolve_cfg_path(self) -> Path:
        return Path("/dummy/config/retroarch.cfg")

    def get_core_search_dirs(self) -> list[Path]:
        return [Path("/dummy/cores")]

    def get_info_search_dirs(self, raw_info_path: str = "") -> list[Path]:
        return [Path("/dummy/info")]

    def resolve_saves_base_dir(self, settings=None) -> Path:
        return Path("/dummy/saves")

    def resolve_states_base_dir(self, settings=None) -> Path:
        return Path("/dummy/states")

    def resolve_system_dir(self, settings=None) -> Path:
        return Path("/dummy/system")

    def build_launch_command(self, rom_path: str, core_path: str, binary_path=None) -> list[str]:
        return ["/dummy/bin/retroarch", "-L", core_path, rom_path]


def test_normalize_platform_slug():
    """Verify platform slug normalization returns expected tuple."""
    raw, clean, no_hyphen = normalize_platform_slug("Game Boy Advance")
    assert raw == "game boy advance"
    assert clean == "game-boy-advance"
    assert no_hyphen == "gameboyadvance"

    assert normalize_platform_slug("") == ("", "", "")


def test_lookup_platform_mapping():
    """Verify platform slug lookup checks all normalized variants."""
    mapping = {
        "game-boy-advance": "mgba_libretro",
        "supernintendo": "snes9x_libretro",
    }
    assert lookup_platform_mapping(mapping, "Game Boy Advance") == "mgba_libretro"
    assert lookup_platform_mapping(mapping, "Super Nintendo") == "snes9x_libretro"
    assert lookup_platform_mapping(mapping, "Unknown Platform") is None
    assert lookup_platform_mapping({}, "snes") is None


def test_get_core_suffix_and_strip():
    """Verify core suffixes per OS platform and stripping helpers."""
    assert get_core_suffix("win32") == ".dll"
    assert get_core_suffix("darwin") == ".dylib"
    assert get_core_suffix("linux") == ".so"

    assert strip_core_suffix("snes9x_libretro.dll") == "snes9x_libretro"
    assert strip_core_suffix("mgba_libretro.so") == "mgba_libretro"
    assert strip_core_suffix("genesis_plus_gx.dylib") == "genesis_plus_gx"


def test_normalize_core_stem():
    """Verify normalize_core_stem removes both OS extension and _libretro suffix."""
    assert normalize_core_stem("mgba_libretro.dll") == "mgba"
    assert normalize_core_stem("snes9x_libretro.so") == "snes9x"
    assert normalize_core_stem("picodrive") == "picodrive"


def test_parse_retroarch_cfg_line():
    """Verify parsing key=value lines from retroarch.cfg."""
    assert parse_retroarch_cfg_line("savefile_directory = \"/path/to/saves\"") == (
        "savefile_directory",
        "/path/to/saves",
    )
    assert parse_retroarch_cfg_line("sort_savefiles_enable = true") == (
        "sort_savefiles_enable",
        "true",
    )
    assert parse_retroarch_cfg_line("# Comment line") == ("", "")
    assert parse_retroarch_cfg_line("") == ("", "")


def test_parse_core_info():
    """Verify parsing .info metadata file key-value pairs."""
    sample_info = (
        "# Libretro core info\n"
        "display_name = \"Nintendo - Game Boy Advance (mGBA)\"\n"
        "authors = \"Vicki Pfau\"\n"
        "corename = \"mGBA\"\n"
        "systemname = \"Game Boy Advance\"\n"
    )
    parsed = parse_core_info(sample_info)
    assert parsed["corename"] == "mGBA"
    assert parsed["systemname"] == "Game Boy Advance"
    assert parsed["display_name"] == "Nintendo - Game Boy Advance (mGBA)"


def test_adapter_get_default_core_and_candidates():
    """Verify default core and candidate resolution on adapter."""
    adapter = DummyRetroArchAdapter()
    default_core = adapter.get_default_core_for_platform("gba")
    assert default_core == "mgba_libretro"

    candidates = adapter.get_core_candidates_for_platform("gba")
    assert "mgba_libretro" in candidates
    assert candidates[0] == "mgba_libretro"

    assert adapter.get_default_core_for_platform("") is None
    assert adapter.get_core_candidates_for_platform("") == []


def test_adapter_list_installed_cores(tmp_path):
    """Verify list_installed_cores scans search directories for matching files."""
    cores_dir = tmp_path / "cores"
    cores_dir.mkdir()
    (cores_dir / "mgba_libretro.dll").write_text("dummy")
    (cores_dir / "snes9x_libretro.dll").write_text("dummy")
    (cores_dir / "not_a_core.txt").write_text("dummy")

    adapter = DummyRetroArchAdapter(os_platform="win32")
    with patch.object(adapter, "get_core_search_dirs", return_value=[cores_dir]):
        installed = adapter.list_installed_cores()
        assert "mgba_libretro" in installed
        assert "snes9x_libretro" in installed
        assert "not_a_core" not in installed


def test_adapter_resolve_save_directory_flat(tmp_path):
    """Verify flat save file path resolution when sorting is disabled."""
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()

    adapter = DummyRetroArchAdapter()
    settings = {
        "savefiles_in_content_dir": False,
        "sort_savefiles_by_content_enable": False,
        "sort_savefiles_enable": False,
    }

    with patch.object(adapter, "resolve_saves_base_dir", return_value=saves_dir), \
         patch.object(adapter, "get_config_settings", return_value=settings):
        save_dir = adapter.resolve_save_directory(
            rom_path=str(tmp_path / "Pokemon.gba"),
            platform_slug="gba",
        )
        assert save_dir == saves_dir.resolve()


def test_adapter_resolve_save_directory_content_sorted(tmp_path):
    """Verify content-sorted save file path resolution when sort_savefiles_by_content_enable is True."""
    saves_dir = tmp_path / "saves"
    saves_dir.mkdir()

    adapter = DummyRetroArchAdapter()
    settings = {
        "savefiles_in_content_dir": False,
        "sort_savefiles_by_content_enable": True,
        "sort_savefiles_enable": False,
    }

    with patch.object(adapter, "resolve_saves_base_dir", return_value=saves_dir), \
         patch.object(adapter, "get_config_settings", return_value=settings):
        save_dir = adapter.resolve_save_directory(
            rom_path=str(tmp_path / "Pokemon.gba"),
            platform_slug="gba",
        )
        assert save_dir == (saves_dir / "gba").resolve()


def test_adapter_launch_game(tmp_path):
    """Verify launch_game executes subprocess and returns process object."""
    adapter = DummyRetroArchAdapter()
    rom = tmp_path / "test.gba"
    rom.write_text("rom-data")

    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_proc.stderr = None

    with patch("subprocess.Popen", return_value=mock_proc) as mock_popen, \
         patch.object(adapter, "resolve_core_path", return_value="/dummy/cores/mgba_libretro.dll"):
        ok, msg, proc = adapter.launch_game(
            rom_path=str(rom),
            platform_slug="gba",
        )
        assert ok is True
        assert proc is mock_proc
        assert mock_popen.called


def test_is_retroarch_running():
    """Verify is_retroarch_running identifies running retroarch processes."""
    proc1 = MagicMock()
    proc1.info = {"name": "retroarch.exe", "exe": "C:\\RetroArch\\retroarch.exe", "cmdline": []}

    proc2 = MagicMock()
    proc2.info = {"name": "python.exe", "exe": "C:\\Python\\python.exe", "cmdline": ["romm-steam-sync"]}

    with patch("psutil.process_iter", return_value=[proc2, proc1]):
        assert is_retroarch_running() is True

    with patch("psutil.process_iter", return_value=[proc2]):
        assert is_retroarch_running() is False


def test_clean_subprocess_env_restores_orig_var():
    """Verify clean_subprocess_env restores variables from *_ORIG and removes the _ORIG key."""
    fake_env = {
        "LD_LIBRARY_PATH": "/tmp/_MEI000018bclp0Mqq:/usr/local/lib",
        "LD_LIBRARY_PATH_ORIG": "/usr/local/lib",
        "DYLD_LIBRARY_PATH": "/tmp/_MEI000018bclp0Mqq:/opt/homebrew/lib",
        "DYLD_LIBRARY_PATH_ORIG": "/opt/homebrew/lib",
        "PATH": "/usr/bin:/bin",
    }
    cleaned = clean_subprocess_env(fake_env)
    assert cleaned["LD_LIBRARY_PATH"] == "/usr/local/lib"
    assert "LD_LIBRARY_PATH_ORIG" not in cleaned
    assert cleaned["DYLD_LIBRARY_PATH"] == "/opt/homebrew/lib"
    assert "DYLD_LIBRARY_PATH_ORIG" not in cleaned
    assert cleaned["PATH"] == "/usr/bin:/bin"


def test_clean_subprocess_env_removes_empty_orig():
    """Verify clean_subprocess_env removes variable if *_ORIG was set to empty string."""
    fake_env = {
        "LD_LIBRARY_PATH": "/tmp/_MEI123456",
        "LD_LIBRARY_PATH_ORIG": "",
    }
    cleaned = clean_subprocess_env(fake_env)
    assert "LD_LIBRARY_PATH" not in cleaned
    assert "LD_LIBRARY_PATH_ORIG" not in cleaned


def test_clean_subprocess_env_removes_meipass_without_orig(monkeypatch, tmp_path):
    """Verify clean_subprocess_env strips _MEIPASS directory when _ORIG was not saved."""
    fake_meipass = tmp_path / "_MEI999999"
    fake_meipass.mkdir()
    monkeypatch.setattr("sys._MEIPASS", str(fake_meipass), raising=False)

    fake_env = {
        "LD_LIBRARY_PATH": str(fake_meipass),
        "HOME": "/home/user",
    }
    cleaned = clean_subprocess_env(fake_env)
    assert "LD_LIBRARY_PATH" not in cleaned
    assert cleaned["HOME"] == "/home/user"


def test_clean_subprocess_env_filters_meipass_keeping_other_paths(monkeypatch):
    """Verify clean_subprocess_env preserves non-MEIPASS entries in LD_LIBRARY_PATH."""
    fake_meipass = "/tmp/_MEI888888"
    monkeypatch.setattr("sys._MEIPASS", fake_meipass, raising=False)

    fake_env = {
        "LD_LIBRARY_PATH": f"{fake_meipass}:/usr/lib/x86_64-linux-gnu:/opt/custom/lib",
    }
    cleaned = clean_subprocess_env(fake_env)
    assert "LD_LIBRARY_PATH" in cleaned
    assert fake_meipass not in cleaned["LD_LIBRARY_PATH"]
    assert "/usr/lib/x86_64-linux-gnu" in cleaned["LD_LIBRARY_PATH"]
    assert "/opt/custom/lib" in cleaned["LD_LIBRARY_PATH"]


def test_clean_subprocess_env_detects_mei_naming_pattern():
    """Verify clean_subprocess_env strips paths with _MEIxxxxxx naming even without sys._MEIPASS."""
    fake_env = {
        "LD_LIBRARY_PATH": "/tmp/_MEI000018bclp0Mqq",
    }
    cleaned = clean_subprocess_env(fake_env)
    assert "LD_LIBRARY_PATH" not in cleaned


def test_clean_subprocess_env_preserves_clean_environment():
    """Verify clean_subprocess_env does not modify normal environment variables."""
    normal_env = {
        "LD_LIBRARY_PATH": "/usr/local/lib:/usr/lib",
        "PATH": "/usr/bin:/bin",
        "HOME": "/home/user",
    }
    cleaned = clean_subprocess_env(normal_env)
    assert cleaned == normal_env


def test_adapter_prepare_launch_environment_sanitizes(monkeypatch, tmp_path):
    """Verify BaseRetroArchAdapter.prepare_launch_environment produces a clean environment."""
    fake_meipass = tmp_path / "_MEI555555"
    fake_meipass.mkdir()
    monkeypatch.setattr("sys._MEIPASS", str(fake_meipass), raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", str(fake_meipass))

    adapter = DummyRetroArchAdapter()
    env = adapter.prepare_launch_environment(
        rom_path="/games/test.gba",
        core_path="/cores/mgba_libretro.so",
    )
    assert "LD_LIBRARY_PATH" not in env

