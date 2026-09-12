"""Unit tests for wrapper installer adapter."""

import os
from pathlib import Path

from romm_steam_sync.adapters.wrapper_installer import (
    get_installed_wrapper_path,
    install_wrapper,
)

# Platform-appropriate binary magic bytes so that _is_platform_native_binary
# accepts the fake binaries written in test fixtures.
PLATFORM_MAGIC = b"MZ\x00\x00" if os.name == "nt" else b"\x7fELF"


def test_getInstalledWrapperPath_returnsPlatformSpecificWrapper(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))

    # Act
    path = get_installed_wrapper_path()

    # Assert
    assert isinstance(path, Path)
    assert path.parent.name == "bin"
    if os.name == "nt":
        assert path.name == "romm-steam-sync-launcher.vbs"
    else:
        assert path.name == "romm-steam-sync-launcher"


def test_installWrapper_createsExecutableWrapperScript(tmp_path, monkeypatch):
    # Arrange
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path))

    # Act
    wrapper_path = install_wrapper()

    # Assert
    assert wrapper_path.exists()
    content = wrapper_path.read_text(encoding="utf-8")
    assert "romm_steam_sync.launcher" in content


def test_getBundledLauncherPath_fromMeipass(tmp_path, monkeypatch):
    # Arrange
    binary_name = (
        "romm-steam-sync-launcher.exe"
        if os.name == "nt"
        else "romm-steam-sync-launcher"
    )
    fake_meipass = tmp_path / "meipass"
    fake_meipass.mkdir()
    fake_binary = fake_meipass / binary_name
    fake_binary.write_bytes(PLATFORM_MAGIC)

    import sys
    from romm_steam_sync.adapters.wrapper_installer import (
        get_bundled_launcher_path,
    )

    monkeypatch.setattr(sys, "_MEIPASS", str(fake_meipass), raising=False)

    # Act
    found = get_bundled_launcher_path()

    # Assert
    assert found == fake_binary


def test_getBundledLauncherPath_fromSibling(tmp_path, monkeypatch):
    # Arrange
    binary_name = (
        "romm-steam-sync-launcher.exe"
        if os.name == "nt"
        else "romm-steam-sync-launcher"
    )
    fake_bin_dir = tmp_path / "dist"
    fake_bin_dir.mkdir()
    fake_exe = fake_bin_dir / "romm-steam-sync.exe"
    fake_exe.write_bytes(b"main-binary")
    fake_launcher = fake_bin_dir / binary_name
    fake_launcher.write_bytes(PLATFORM_MAGIC)

    import sys
    from romm_steam_sync.adapters.wrapper_installer import (
        get_bundled_launcher_path,
    )

    if hasattr(sys, "_MEIPASS"):
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))

    # Act
    found = get_bundled_launcher_path()

    # Assert
    assert found == fake_launcher


def test_installWrapper_copiesBundledLauncherExe(tmp_path, monkeypatch):
    # Arrange
    binary_name = (
        "romm-steam-sync-launcher.exe"
        if os.name == "nt"
        else "romm-steam-sync-launcher"
    )
    fake_source_dir = tmp_path / "source"
    fake_source_dir.mkdir()
    fake_source_binary = fake_source_dir / binary_name
    fake_source_binary.write_bytes(PLATFORM_MAGIC + b"launcher-binary-content")

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "config"))

    import sys

    monkeypatch.setattr(sys, "_MEIPASS", str(fake_source_dir), raising=False)

    # Act
    result_path = install_wrapper()

    # Assert
    assert result_path.exists()
    assert result_path.name == binary_name
    assert result_path.read_bytes() == PLATFORM_MAGIC + b"launcher-binary-content"


def test_getInstalledWrapperPath_whenLauncherExePresent_returnsExe():
    # Arrange
    from romm_steam_sync.config import get_default_config_dir

    bin_dir = get_default_config_dir() / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    exe_file = bin_dir / "romm-steam-sync-launcher.exe"
    exe_file.write_bytes(b"binary")

    if os.name == "nt":
        # Act
        path = get_installed_wrapper_path()

        # Assert
        assert path == exe_file


