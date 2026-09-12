"""Unit tests for RetroArchPathResolver and core/platform path helpers."""

from pathlib import Path
from unittest.mock import patch

from romm_steam_sync.adapters.retroarch_paths import (
    RetroArchPathResolver,
    ensure_core_suffix,
    get_core_suffix,
    lookup_platform_mapping,
    normalize_core_stem,
    normalize_platform_slug,
    strip_core_suffix,
)


def test_normalizePlatformSlug_handlesEmpty():
    assert normalize_platform_slug("") == ("", "", "")
    assert normalize_platform_slug(None) == ("", "", "")


def test_normalizePlatformSlug_generatesVariants():
    raw, clean, clean_no_hyphen = normalize_platform_slug(
        "Super Nintendo: Entertainment_System"
    )
    assert raw == "super nintendo: entertainment_system"
    assert clean == "super-nintendo-entertainment-system"
    assert clean_no_hyphen == "supernintendoentertainmentsystem"


def test_lookupPlatformMapping_matchesVariants():
    mapping = {
        "super-nintendo": "snes9x_libretro",
        "genesis": "genesis_plus_gx_libretro",
        "gameboyadvance": "mgba_libretro",
    }
    # Matches hyphenated
    assert lookup_platform_mapping(mapping, "Super Nintendo") == "snes9x_libretro"
    # Matches raw lower
    assert lookup_platform_mapping(mapping, "GENESIS") == "genesis_plus_gx_libretro"
    # Matches unhyphenated
    assert lookup_platform_mapping(mapping, "game-boy-advance") == "mgba_libretro"
    # Missing returns None
    assert lookup_platform_mapping(mapping, "unknown_console") is None


def test_getCoreSuffix_returnsCorrectExtensions():
    assert get_core_suffix("win32") == ".dll"
    assert get_core_suffix("darwin") == ".dylib"
    assert get_core_suffix("linux") == ".so"


def test_stripCoreSuffix_removesExtension():
    assert strip_core_suffix("mgba_libretro.dll") == "mgba_libretro"
    assert strip_core_suffix("snes9x_libretro.so") == "snes9x_libretro"
    assert strip_core_suffix("flycast_libretro.dylib") == "flycast_libretro"
    assert strip_core_suffix("nestopia_libretro") == "nestopia_libretro"
    assert strip_core_suffix("") == ""


def test_ensureCoreSuffix_appendsSuffix():
    assert ensure_core_suffix("mgba_libretro", os_platform="win32") == "mgba_libretro.dll"
    assert (
        ensure_core_suffix("mgba_libretro.dll", os_platform="win32")
        == "mgba_libretro.dll"
    )
    assert (
        ensure_core_suffix("snes9x_libretro", os_platform="linux")
        == "snes9x_libretro.so"
    )
    assert ensure_core_suffix("", os_platform="win32") == ""


def test_normalizeCoreStem_removesSuffixAndLibretro():
    assert normalize_core_stem("mgba_libretro.dll") == "mgba"
    assert normalize_core_stem("snes9x_libretro.so") == "snes9x"
    assert normalize_core_stem("beetle_psx_hw_libretro.dylib") == "beetle_psx_hw"
    assert normalize_core_stem("nestopia") == "nestopia"


def test_resolveRetroarchBinary_withConfiguredFile(tmp_path):
    exe = tmp_path / "retroarch.exe"
    exe.write_bytes(b"dummy")

    resolved = RetroArchPathResolver.resolve_retroarch_binary(
        configured_path=str(exe), os_platform="win32"
    )
    assert resolved == exe.resolve()


def test_resolveRetroarchBinary_withConfiguredDirectory(tmp_path):
    exe = tmp_path / "retroarch"
    exe.write_bytes(b"dummy")

    resolved = RetroArchPathResolver.resolve_retroarch_binary(
        configured_path=str(tmp_path), os_platform="linux"
    )
    assert resolved == exe.resolve()


def test_resolveRetroarchBinary_withMacAppBundle(tmp_path):
    mac_app = tmp_path / "Contents" / "MacOS" / "RetroArch"
    mac_app.parent.mkdir(parents=True)
    mac_app.write_bytes(b"dummy")

    resolved = RetroArchPathResolver.resolve_retroarch_binary(
        configured_path=str(tmp_path), os_platform="darwin"
    )
    assert resolved == mac_app.resolve()


def test_resolveRetroarchBinary_fromPath():
    with patch("shutil.which", side_effect=lambda cmd: "/usr/bin/retroarch" if cmd == "retroarch" else None), \
         patch("pathlib.Path.is_file", return_value=True):
        resolved = RetroArchPathResolver.resolve_retroarch_binary(os_platform="linux")
        assert resolved == Path("/usr/bin/retroarch")


def test_resolveRetroarchCfgPath_withConfiguredCfg(tmp_path):
    cfg = tmp_path / "custom.cfg"
    cfg.write_text("savefile_directory = /saves", encoding="utf-8")

    resolved = RetroArchPathResolver.resolve_retroarch_cfg_path(
        configured_path=str(cfg)
    )
    # Since name is not retroarch.cfg, checks parent / retroarch.cfg or if cfg.name == retroarch.cfg
    # Let's test with retroarch.cfg
    cfg_ra = tmp_path / "retroarch.cfg"
    cfg_ra.write_text("savefile_directory = /saves", encoding="utf-8")
    resolved_ra = RetroArchPathResolver.resolve_retroarch_cfg_path(
        configured_path=str(cfg_ra)
    )
    assert resolved_ra == cfg_ra.resolve()


def test_resolveRetroarchCfgPath_alongsideResolvedBinary(tmp_path):
    ra_dir = tmp_path / "RetroArch"
    ra_dir.mkdir()
    exe = ra_dir / "retroarch.exe"
    exe.write_bytes(b"dummy")
    cfg = ra_dir / "retroarch.cfg"
    cfg.write_text("savefile_directory = /saves", encoding="utf-8")

    resolved = RetroArchPathResolver.resolve_retroarch_cfg_path(
        configured_path=str(exe), os_platform="win32"
    )
    assert resolved == cfg.resolve()


def test_getCoreSearchDirs_includesBinaryParent(tmp_path):
    exe = tmp_path / "retroarch.exe"
    exe.write_bytes(b"dummy")

    dirs = RetroArchPathResolver.get_core_search_dirs(
        retroarch_path=str(exe), os_platform="win32"
    )
    assert (tmp_path / "cores") in dirs
    assert tmp_path in dirs


def test_getInfoSearchDirs_withPrefixColon(tmp_path):
    ra_dir = tmp_path / "RetroArch"
    ra_dir.mkdir()
    exe = ra_dir / "retroarch.exe"
    exe.write_bytes(b"dummy")

    dirs = RetroArchPathResolver.get_info_search_dirs(
        retroarch_path=str(exe),
        raw_info_path=r":\info",
        os_platform="win32",
    )
    assert (ra_dir / "info") in dirs


def test_resolveSavesBaseDir_prefixColon(tmp_path):
    ra_dir = tmp_path / "RetroArch"
    ra_dir.mkdir()
    exe = ra_dir / "retroarch.exe"
    exe.write_bytes(b"dummy")

    save_dir = RetroArchPathResolver.resolve_saves_base_dir(
        configured_path=str(exe),
        savefile_directory=r":\saves",
        os_platform="win32",
    )
    assert save_dir == (ra_dir / "saves").resolve()


def test_resolveSavesBaseDir_defaultOrEmpty(tmp_path):
    fake_home = tmp_path / "userhome"
    fake_home.mkdir()

    with patch.object(RetroArchPathResolver, "resolve_retroarch_binary", return_value=None):
        save_dir = RetroArchPathResolver.resolve_saves_base_dir(
            configured_path="",
            savefile_directory="default",
            os_platform="win32",
            home_dir=fake_home,
        )
        expected = (fake_home / "AppData" / "Roaming" / "RetroArch" / "saves").resolve()
        assert save_dir == expected


def test_resolveSavesBaseDir_defaultWithInstalledRaSavesDir(tmp_path):
    ra_dir = tmp_path / "RetroArch"
    ra_dir.mkdir()
    saves_dir = ra_dir / "saves"
    saves_dir.mkdir()
    ra_exe = ra_dir / "retroarch.exe"
    ra_exe.write_bytes(b"dummy")

    with patch.object(RetroArchPathResolver, "resolve_retroarch_binary", return_value=ra_exe):
        save_dir = RetroArchPathResolver.resolve_saves_base_dir(
            configured_path=str(ra_exe),
            savefile_directory="default",
            os_platform="win32",
        )
        assert save_dir == saves_dir.resolve()


def test_resolveSavesBaseDir_explicitPath(tmp_path):
    custom_saves = tmp_path / "my_custom_saves"
    custom_saves.mkdir()

    save_dir = RetroArchPathResolver.resolve_saves_base_dir(
        configured_path="",
        savefile_directory=str(custom_saves),
        os_platform="linux",
    )
    assert save_dir == custom_saves.resolve()


def test_resolveSteamLinuxRuntime_returnsNoneOnNonLinux():
    assert (
        RetroArchPathResolver.resolve_steam_linux_runtime(os_platform="win32") is None
    )
    assert (
        RetroArchPathResolver.resolve_steam_linux_runtime(os_platform="darwin") is None
    )
