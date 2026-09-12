"""Unit tests for RetroArch launcher adapter."""

import os
from pathlib import Path
import shutil
import sys
from unittest.mock import MagicMock, patch

from romm_steam_sync.adapters.retroarch_launcher import (
    RetroArchLauncher,
    get_core_suffix,
)


def test_getCoreSuffix_returnsPlatformExtension():
    # Arrange & Act
    suffix = get_core_suffix()

    # Assert
    if os.name == "nt":
        assert suffix == ".dll"
    elif sys.platform == "darwin":
        assert suffix == ".dylib"
    else:
        assert suffix == ".so"


def test_resolveCorePath_withDefaults_returnsExpectedCore():
    # Arrange
    platforms_and_expected = [
        ("snes", "snes9x_libretro"),
        ("gba", "mgba_libretro"),
        ("dc", "flycast_libretro"),
        ("dreamcast", "flycast_libretro"),
        ("sega-dreamcast", "flycast_libretro"),
        ("ps", "pcsx_rearmed_libretro"),
        ("psx", "pcsx_rearmed_libretro"),
        ("ps1", "pcsx_rearmed_libretro"),
        ("gc", "dolphin_libretro"),
        ("ngc", "dolphin_libretro"),
        ("gamecube", "dolphin_libretro"),
    ]

    # Act & Assert
    for slug, expected_core in platforms_and_expected:
        resolved = RetroArchLauncher.resolve_core_path(slug)
        assert expected_core in resolved


def test_resolveCorePath_withCustomMapping_returnsOverride():
    # Arrange
    custom = {"snes": "bsnes_libretro", "dc": "reicast_libretro"}

    # Act
    core_snes = RetroArchLauncher.resolve_core_path("snes", custom_mappings=custom)
    core_dc = RetroArchLauncher.resolve_core_path("dc", custom_mappings=custom)

    # Assert
    assert "bsnes_libretro" in core_snes
    assert "reicast_libretro" in core_dc


def test_resolveRetroarchBinary_withConfiguredPath_returnsExecutable(tmp_path):
    # Arrange
    exe_name = "retroarch.exe" if sys.platform == "win32" else "retroarch"
    fake_exe = tmp_path / exe_name
    fake_exe.touch()

    # Act
    resolved_file = RetroArchLauncher.resolve_retroarch_binary(str(fake_exe))
    resolved_dir = RetroArchLauncher.resolve_retroarch_binary(str(tmp_path))

    # Assert
    assert resolved_file == str(fake_exe.resolve())
    assert resolved_dir == str(fake_exe.resolve())


def test_resolveRetroarchBinary_checksSteamPaths(tmp_path):
    # Arrange
    exe_name = "retroarch.exe" if sys.platform == "win32" else "retroarch"
    steam_root = tmp_path / "Steam"
    steam_ra = steam_root / "steamapps" / "common" / "RetroArch" / exe_name
    steam_ra.parent.mkdir(parents=True, exist_ok=True)
    steam_ra.touch()

    # Act
    with patch("romm_steam_sync.adapters.steam_path.SteamPathResolver.get_steam_root", return_value=steam_root):
        with patch("shutil.which", return_value=None):
            resolved = RetroArchLauncher.resolve_retroarch_binary()

    # Assert
    assert resolved is not None
    assert "RetroArch" in resolved


def test_launchGame_setsCwdAndInvokesPopen(tmp_path):
    # Arrange
    fake_exe = tmp_path / "retroarch.exe"
    fake_exe.touch()
    fake_rom = tmp_path / "Vigilante 8.gdi"
    fake_rom.touch()

    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.pid = 9999
        mock_popen.return_value = mock_proc

        # Act
        success, msg, proc = RetroArchLauncher.launch_game(
            rom_path=str(fake_rom),
            platform_slug="dc",
            configured_retroarch_path=str(fake_exe),
        )

        # Assert
        assert success is True
        assert proc == mock_proc
        mock_popen.assert_called_once()
        call_args, call_kwargs = mock_popen.call_args
        assert call_kwargs.get("cwd") == str(tmp_path.resolve())
        cmd = call_args[0]
        assert "flycast_libretro" in cmd[2]
        assert cmd[3] == str(fake_rom)


def test_resolveRetroarchBinary_findsFlatpakBinary():
    # Arrange & Act
    with patch("shutil.which", side_effect=lambda name: "/usr/bin/flatpak-retroarch" if name == "org.libretro.RetroArch" else None), \
         patch("pathlib.Path.is_file", return_value=True):
        res = RetroArchLauncher.resolve_retroarch_binary()

    # Assert
    assert res == "/usr/bin/flatpak-retroarch"


def test_listInstalledCores_scansFedoraAndDebianPaths():
    # Arrange
    from romm_steam_sync.adapters.retroarch_launcher import list_installed_cores

    checked_paths = []

    def fake_exists(self):
        checked_paths.append(str(self))
        return False

    with patch("romm_steam_sync.adapters.retroarch_launcher.sys.platform", "linux"), \
         patch("romm_steam_sync.adapters.retroarch_launcher.RetroArchLauncher.resolve_retroarch_binary", return_value=None):
        with patch.object(Path, "exists", fake_exists):
            list_installed_cores()
            # Verify Fedora /usr/lib64/libretro and Debian multiarch directories are checked
            assert any("lib64" in p for p in checked_paths)
            assert any("x86_64-linux-gnu" in p for p in checked_paths)
            assert any("aarch64-linux-gnu" in p for p in checked_paths)


def test_listInstalledCores_scansMacOsPaths():
    # Arrange
    from romm_steam_sync.adapters.retroarch_launcher import list_installed_cores

    checked_paths = []

    def fake_exists(self):
        checked_paths.append(str(self))
        return False

    with patch("romm_steam_sync.adapters.retroarch_launcher.sys.platform", "darwin"), \
         patch("romm_steam_sync.adapters.retroarch_launcher.RetroArchLauncher.resolve_retroarch_binary", return_value=None):
        with patch.object(Path, "exists", fake_exists):
            list_installed_cores()
            # Verify macOS Application Support directory is checked
            assert any("Application Support" in p for p in checked_paths)


def test_resolveSteamLinuxRuntime_findsSniperRun(tmp_path):
    # Arrange
    steam_common = tmp_path / "steamapps" / "common"
    ra_dir = steam_common / "RetroArch"
    ra_dir.mkdir(parents=True)
    ra_exe = ra_dir / "retroarch"
    ra_exe.touch()

    sniper_dir = steam_common / "SteamLinuxRuntime_sniper"
    sniper_dir.mkdir(parents=True)
    sniper_run = sniper_dir / "run"
    sniper_run.touch()

    with patch("romm_steam_sync.adapters.retroarch_launcher.sys.platform", "linux"):
        # Act
        runner = RetroArchLauncher.resolve_steam_linux_runtime(str(ra_exe))

        # Assert
        assert runner == sniper_run.resolve()


def test_launchGame_onLinux_steamRetroArch_wrapsWithRuntime(tmp_path):
    # Arrange
    steam_common = tmp_path / "steamapps" / "common"
    ra_dir = steam_common / "RetroArch"
    ra_dir.mkdir(parents=True)
    ra_exe = ra_dir / "retroarch"
    ra_exe.touch()

    sniper_dir = steam_common / "SteamLinuxRuntime_sniper"
    sniper_dir.mkdir(parents=True)
    sniper_run = sniper_dir / "run"
    sniper_run.touch()

    rom_file = tmp_path / "roms" / "snes" / "game.zip"
    rom_file.parent.mkdir(parents=True)
    rom_file.touch()

    with patch("romm_steam_sync.adapters.retroarch_launcher.sys.platform", "linux"), \
         patch("romm_steam_sync.adapters.retroarch_launcher.RetroArchLauncher.resolve_core_path", return_value="/cores/snes9x_libretro.so"), \
         patch("romm_steam_sync.adapters.retroarch_launcher.RetroArchLauncher.resolve_retroarch_binary", return_value=str(ra_exe)), \
         patch("subprocess.Popen") as mock_popen:

        mock_proc = MagicMock()
        mock_proc.pid = 1234
        mock_proc.stderr = None
        mock_popen.return_value = mock_proc

        # Act
        success, msg, proc = RetroArchLauncher.launch_game(
            rom_path=str(rom_file),
            platform_slug="snes",
            configured_retroarch_path=str(ra_exe),
        )

        # Assert
        assert success is True
        assert proc == mock_proc
        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        assert cmd[0] == str(sniper_run.resolve())
        assert cmd[1] == "--"
        wrapper_sh = ra_dir / "retroarch.sh"
        assert cmd[2] == str(wrapper_sh.resolve())
        assert wrapper_sh.is_file()
        assert "export LD_LIBRARY_PATH" in wrapper_sh.read_text(encoding="utf-8")
        assert cmd[3] == "-L"
        assert cmd[4] == "/cores/snes9x_libretro.so"
        assert cmd[5] == str(rom_file)

        env = mock_popen.call_args[1].get("env", {})
        assert "PRESSURE_VESSEL_FILESYSTEMS_RW" in env
        assert str(rom_file.parent.resolve()) in env["PRESSURE_VESSEL_FILESYSTEMS_RW"]
        assert "LD_LIBRARY_PATH" in env
        assert str(ra_dir.resolve()) in env["LD_LIBRARY_PATH"]


def test_launchGame_capturesStderrInThread(tmp_path):
    # Arrange
    import io
    fake_exe = tmp_path / "retroarch.exe"
    fake_exe.touch()
    fake_rom = tmp_path / "game.sfc"
    fake_rom.touch()

    stderr_io = io.StringIO("error while loading shared libraries: libfoo.so\n")

    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.pid = 9999
        mock_proc.stderr = stderr_io
        mock_popen.return_value = mock_proc

        # Act
        success, msg, proc = RetroArchLauncher.launch_game(
            rom_path=str(fake_rom),
            platform_slug="snes",
            configured_retroarch_path=str(fake_exe),
        )

        # Assert
        import time
        time.sleep(0.1)
        assert success is True
        assert hasattr(proc, "_captured_stderr")
        assert any("libfoo.so" in line for line in proc._captured_stderr)


def test_getOrCreateRetroarchWrapper_existingShReturnsIt(tmp_path):
    # Arrange
    ra_dir = tmp_path / "RetroArch"
    ra_dir.mkdir()
    ra_exe = ra_dir / "retroarch"
    ra_exe.touch()
    existing_sh = ra_dir / "retroarch.sh"
    existing_sh.write_text("#!/bin/sh\n./retroarch \"$@\"\n", encoding="utf-8")

    with patch("romm_steam_sync.adapters.retroarch_launcher.sys.platform", "linux"):
        # Act
        result = RetroArchLauncher.get_or_create_retroarch_wrapper(str(ra_exe))

        # Assert
        assert result == str(existing_sh.resolve())


def test_getOrCreateRetroarchWrapper_createsShIfMissing(tmp_path):
    # Arrange
    ra_dir = tmp_path / "RetroArch"
    ra_dir.mkdir()
    ra_exe = ra_dir / "retroarch"
    ra_exe.touch()

    with patch("romm_steam_sync.adapters.retroarch_launcher.sys.platform", "linux"):
        # Act
        result = RetroArchLauncher.get_or_create_retroarch_wrapper(str(ra_exe))

        # Assert
        expected_sh = ra_dir / "retroarch.sh"
        assert result == str(expected_sh.resolve())
        assert expected_sh.is_file()
        content = expected_sh.read_text(encoding="utf-8")
        assert "export LD_LIBRARY_PATH" in content
        assert "SteamAppId" not in content
        assert 'exec "$DIR/retroarch" "$@"' in content
        appid_file = ra_dir / "steam_appid.txt"
        assert not appid_file.exists()


def test_getOrCreateRetroarchWrapper_removesSteamAppIdTxtAndCleansWrapper(tmp_path):
    # Arrange
    ra_dir = tmp_path / "RetroArch"
    ra_dir.mkdir()
    ra_exe = ra_dir / "retroarch"
    ra_exe.touch()

    # Pre-create leftover steam_appid.txt and wrapper with SteamAppId
    appid_file = ra_dir / "steam_appid.txt"
    appid_file.write_text("1118310\n", encoding="utf-8")

    existing_sh = ra_dir / "retroarch.sh"
    existing_sh.write_text(
        '#!/bin/sh\nexport SteamAppId="1118310"\nexport LD_LIBRARY_PATH="$DIR"\nexec ./retroarch "$@"\n',
        encoding="utf-8",
    )

    with patch("romm_steam_sync.adapters.retroarch_launcher.sys.platform", "linux"):
        # Act
        result = RetroArchLauncher.get_or_create_retroarch_wrapper(str(ra_exe))

        # Assert: steam_appid.txt should be unlinked, and wrapper cleaned of SteamAppId
        assert not appid_file.exists()
        cleaned_content = existing_sh.read_text(encoding="utf-8")
        assert "SteamAppId" not in cleaned_content
        assert "export LD_LIBRARY_PATH" in cleaned_content


def test_isRetroarchRunning_detectsActiveProcess():
    from romm_steam_sync.adapters.retroarch_launcher import is_retroarch_running

    fake_ra_proc = MagicMock()
    fake_ra_proc.info = {
        "name": "retroarch",
        "exe": "/home/joe/.local/share/Steam/steamapps/common/RetroArch/retroarch",
        "cmdline": ["retroarch", "-L", "core.so", "game.zip"],
    }

    with patch("psutil.process_iter", return_value=[fake_ra_proc]):
        assert is_retroarch_running() is True


def test_isRetroarchRunning_excludesLauncherProcess():
    from romm_steam_sync.adapters.retroarch_launcher import is_retroarch_running

    fake_launcher_proc = MagicMock()
    fake_launcher_proc.info = {
        "name": "romm-steam-sync",
        "exe": "/usr/bin/python3",
        "cmdline": ["python3", "-m", "romm_steam_sync.launcher.app", "--rom-id", "123"],
    }

    with patch("psutil.process_iter", return_value=[fake_launcher_proc]):
        assert is_retroarch_running() is False


def test_isRetroarchRunning_returnsFalseWhenNoMatch():
    from romm_steam_sync.adapters.retroarch_launcher import is_retroarch_running

    fake_other_proc = MagicMock()
    fake_other_proc.info = {
        "name": "steam",
        "exe": "/usr/bin/steam",
        "cmdline": ["steam"],
    }

    with patch("psutil.process_iter", return_value=[fake_other_proc]):
        assert is_retroarch_running() is False





