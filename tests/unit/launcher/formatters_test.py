"""Unit tests for launcher display and string formatting helpers."""

from romm_steam_sync.launcher.formatters import (
    format_size,
    format_version_display,
)


def test_formatSize_convertsBytesToHumanReadableStrings():
    # Arrange & Act & Assert
    assert format_size(0) == "Unknown size"
    assert format_size(-10) == "Unknown size"
    assert format_size(500) == "0.5 KB"
    assert format_size(1024 * 500) == "500.0 KB"
    assert format_size(1024 * 1024 * 14) == "14 MB"
    assert format_size(1024 * 1024 * 1024 * 2) == "2.00 GB"


def test_formatVersionDisplay_generatesTitlesAndSubtitles():
    # Arrange
    v1 = {
        "id": 101,
        "name": "Dark Cloud 2",
        "fs_name": "Dark Cloud 2 (USA) (v1.00).iso",
        "fs_name_no_ext": "Dark Cloud 2 (USA) (v1.00)",
        "regions": ["USA"],
        "revision": "v1.00",
        "fs_size_bytes": 1450000000,
    }

    # Act
    title1, sub1 = format_version_display(v1, "Dark Cloud 2")

    # Assert
    assert title1 == "Dark Cloud 2 (USA) (v1.00)"
    assert "Region: USA" in sub1
    assert "Version: v1.00" in sub1
    assert "1.35 GB" in sub1


def test_formatVersionDisplay_handlesFallbackFields():
    # Arrange
    v2 = {
        "id": 202,
        "region": "EUR",
        "languages": ["English", "French"],
        "disc": "1",
        "file_path": "/roms/ps1/Game.bin",
    }

    # Act
    title2, sub2 = format_version_display(v2, "Fallback Game")

    # Assert
    assert title2 == "Game"
    assert "Region: EUR" in sub2
    assert "Disc: 1" in sub2
    assert "Languages: English, French" in sub2


def test_formatVersionDisplay_handlesMinimalMetadata():
    # Arrange
    v3 = {
        "id": 303,
    }

    # Act
    title3, sub3 = format_version_display(v3, "Generic Game")

    # Assert
    assert title3 == "ROM #303"
    assert "ROM ID: #303" in sub3
