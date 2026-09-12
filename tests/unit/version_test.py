"""Unit tests for application release versioning and SemVer compliance."""

import pytest

import romm_steam_sync
from romm_steam_sync.version import (
    VERSION_INFO,
    VersionInfo,
    __version__,
    get_version,
    get_version_info,
)


def test_versionInfo_hasThreeDigitsConformingToSemVer():
    """Verify VersionInfo contains major, minor, and bugfix attributes."""
    v = VersionInfo(major=1, minor=2, bugfix=3)
    assert v.major == 1
    assert v.minor == 2
    assert v.bugfix == 3
    assert v.patch == 3
    assert v.version_string == "1.2.3"
    assert v.display_version == "v1.2.3"
    assert str(v) == "1.2.3"


def test_versionInfo_conformsToSemVerFormat():
    """Verify that release VERSION_INFO adheres to SemVer structure."""
    assert isinstance(VERSION_INFO.major, int) and VERSION_INFO.major >= 0
    assert isinstance(VERSION_INFO.minor, int) and VERSION_INFO.minor >= 0
    assert isinstance(VERSION_INFO.bugfix, int) and VERSION_INFO.bugfix >= 0
    assert VERSION_INFO.patch == VERSION_INFO.bugfix
    assert VERSION_INFO.version_string == f"{VERSION_INFO.major}.{VERSION_INFO.minor}.{VERSION_INFO.bugfix}"
    assert VERSION_INFO.display_version == f"v{VERSION_INFO.version_string}"
    assert str(VERSION_INFO) == VERSION_INFO.version_string


def test_packageVersion_matchesVersionInfo():
    """Verify __version__ and get_version() match VERSION_INFO."""
    assert __version__ == VERSION_INFO.version_string
    assert get_version() == VERSION_INFO.version_string
    assert get_version_info() == VERSION_INFO
    assert romm_steam_sync.__version__ == VERSION_INFO.version_string
    assert romm_steam_sync.VERSION_INFO == VERSION_INFO


def test_versionString_isThreeIntegerComponents():
    """Verify version string parses into exactly 3 non-negative integer components."""
    parts = __version__.split(".")
    assert len(parts) == 3, f"Expected 3 components in version '{__version__}', got {len(parts)}"
    major, minor, bugfix = [int(p) for p in parts]
    assert major >= 0
    assert minor >= 0
    assert bugfix >= 0
