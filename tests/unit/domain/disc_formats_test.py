"""Unit tests for disc format classification and launch file detection."""

from pathlib import Path

from romm_steam_sync.domain.disc_formats import (
    can_play_archives,
    detect_launch_file,
    extract_disc_identifier,
    extract_revision_identifier,
    is_archive_file,
    is_disc_based_platform,
    should_extract_rom,
    titles_match,
)


def test_isDiscBasedPlatform_evaluatesKnownPlatformSlugs():
    # Arrange
    disc_slugs = [
        "ps1", "psx", "ps", "playstation", "playstation-1", "playstation 1", "sony playstation",
        "ps2", "playstation2", "playstation-2", "playstation 2", "sony playstation 2",
        "ps3", "playstation3",
        "psp", "playstation portable", "playstation-portable",
        "psvita", "vita",
        "dreamcast", "dc", "sega dreamcast", "sega-dreamcast",
        "saturn", "sega saturn", "sega-saturn",
        "segacd", "sega cd", "sega-cd", "megacd", "mega cd",
        "gc", "ngc", "gamecube", "game cube", "nintendo gamecube",
        "wii", "nintendo wii",
        "wiiu", "wii u", "nintendo wii u",
        "3do", "panasonic 3do",
        "pcecd", "turbografxcd", "turbografx-cd", "pc engine cd",
        "neogeocd", "neo geo cd",
        "xbox", "original xbox",
        "xbox360", "xbox 360",
    ]
    cartridge_slugs = [
        "snes", "super nintendo", "sfc", "super famicom",
        "nes", "famicom", "fc",
        "n64", "nintendo 64",
        "gb", "game boy",
        "gbc", "game boy color",
        "gba", "game boy advance",
        "nds", "ds", "nintendo ds",
        "3ds", "n3ds", "nintendo 3ds",
        "genesis", "megadrive", "sega genesis",
        "mastersystem", "master system", "sms",
        "gamegear", "game gear", "gg",
        "sega32x", "32x",
        "atari2600", "atari7800",
        "wonderswan", "ngp", "neogeopocket",
    ]

    # Act & Assert
    for slug in disc_slugs:
        assert is_disc_based_platform(slug) is True, f"Failed for disc slug: {slug}"
        assert can_play_archives(slug) is False, f"Failed can_play_archives for disc slug: {slug}"

    for slug in cartridge_slugs:
        assert is_disc_based_platform(slug) is False, f"Failed for cartridge slug: {slug}"
        assert can_play_archives(slug) is True, f"Failed can_play_archives for cartridge slug: {slug}"

    assert is_disc_based_platform(None) is False
    assert is_disc_based_platform("") is False
    assert can_play_archives(None) is True
    assert can_play_archives("") is True


def test_isArchiveFile_classifiesArchiveExtensions():
    # Arrange
    archives = ["game.zip", "game.7z", "game.rar", "game.tar", "game.tar.gz", "game.tgz", "game.tar.bz2", "game.tar.xz", Path("C:/Games/game.zip"), Path("/home/user/game.7z")]
    non_archives = ["game.iso", "game.cue", "game.chd", "game.bin", "game.rvz", "game.gdi", "game.sfc", "game.nes"]

    # Act & Assert
    for path in archives:
        assert is_archive_file(path) is True, f"Failed for archive: {path}"

    for path in non_archives:
        assert is_archive_file(path) is False, f"Failed for non-archive: {path}"


def test_shouldExtractRom_returnsTrueOnlyForDiscArchives():
    # Arrange
    disc_archives = [("ps1", "Crash.zip"), ("ps2", "FFX.7z"), ("dreamcast", "Shenmue.tar.gz"), ("gc", "Melee.7z")]
    disc_non_archives = [("ps1", "Crash.chd"), ("ps2", "FFX.iso"), ("gc", "Melee.rvz"), ("dreamcast", "CrazyTaxi.gdi")]
    cartridge_archives = [("snes", "Mario.zip"), ("nes", "Zelda.7z"), ("gba", "Pokemon.zip"), ("genesis", "Sonic.7z")]

    # Act & Assert
    for platform, filename in disc_archives:
        assert should_extract_rom(platform, filename) is True

    for platform, filename in disc_non_archives:
        assert should_extract_rom(platform, filename) is False

    for platform, filename in cartridge_archives:
        assert should_extract_rom(platform, filename) is False


def test_detectLaunchFile_singleFileReturnsSoleEntry(tmp_path):
    # Arrange
    file_path = tmp_path / "game.iso"
    file_path.write_bytes(b"content")

    # Act
    chosen = detect_launch_file([file_path])

    # Assert
    assert chosen == file_path


def test_detectLaunchFile_cueBinPrefersCueSheet(tmp_path):
    # Arrange
    cue = tmp_path / "Crash Bandicoot.cue"
    bin1 = tmp_path / "Crash Bandicoot (Track 1).bin"
    bin2 = tmp_path / "Crash Bandicoot (Track 2).bin"
    cue.write_bytes(b'FILE "Crash Bandicoot (Track 1).bin" BINARY')
    bin1.write_bytes(b"\x00" * 1000)
    bin2.write_bytes(b"\x00" * 500)

    # Act
    chosen = detect_launch_file([bin1, cue, bin2], preferred_stem="Crash Bandicoot")

    # Assert
    assert chosen == cue


def test_detectLaunchFile_m3uMultiDiscPrefersPlaylist(tmp_path):
    # Arrange
    m3u = tmp_path / "Final Fantasy VII.m3u"
    disc1 = tmp_path / "Final Fantasy VII (Disc 1).chd"
    disc2 = tmp_path / "Final Fantasy VII (Disc 2).chd"
    disc3 = tmp_path / "Final Fantasy VII (Disc 3).chd"
    m3u.write_bytes(b"Final Fantasy VII (Disc 1).chd\n")
    disc1.write_bytes(b"\x00" * 2000)
    disc2.write_bytes(b"\x00" * 2000)
    disc3.write_bytes(b"\x00" * 2000)

    # Act
    chosen = detect_launch_file([disc1, disc2, m3u, disc3], preferred_stem="Final Fantasy VII")

    # Assert
    assert chosen == m3u


def test_detectLaunchFile_gdiDreamcastPrefersGdiDescriptor(tmp_path):
    # Arrange
    gdi = tmp_path / "Sonic Adventure.gdi"
    raw1 = tmp_path / "track01.bin"
    raw2 = tmp_path / "track02.raw"
    gdi.write_bytes(b"3\n1 0 4 2352 track01.bin 0\n")
    raw1.write_bytes(b"\x00" * 1000)
    raw2.write_bytes(b"\x00" * 1000)

    # Act
    chosen = detect_launch_file([raw1, raw2, gdi])

    # Assert
    assert chosen == gdi


def test_detectLaunchFile_ignoresMetadataFiles(tmp_path):
    # Arrange
    txt = tmp_path / "readme.txt"
    nfo = tmp_path / "game.nfo"
    jpg = tmp_path / "cover.jpg"
    chd = tmp_path / "game.chd"
    txt.write_bytes(b"info")
    nfo.write_bytes(b"scene info")
    jpg.write_bytes(b"image")
    chd.write_bytes(b"disc content")

    # Act
    chosen = detect_launch_file([txt, nfo, jpg, chd])

    # Assert
    assert chosen == chd


def test_extractDiscIdentifier_parsesVariousDiscNotations():
    # Arrange & Act & Assert
    assert extract_disc_identifier("Devil May Cry 2 (USA) (Disc 1)") == "disc 1"
    assert extract_disc_identifier("Devil May Cry 2 (USA) (Disc 2)") == "disc 2"
    assert extract_disc_identifier("Final Fantasy VII (USA) (Disc 1 of 3)") == "disc 1"
    assert extract_disc_identifier("Final Fantasy VII (USA) (Disc 2 of 3)") == "disc 2"
    assert extract_disc_identifier("Resident Evil 2 (USA) (Leon Disc)") == "leon disc"
    assert extract_disc_identifier("Resident Evil 2 (USA) (Claire Disc)") == "claire disc"
    assert extract_disc_identifier("Game (Disk 2)") == "disc 2"
    assert extract_disc_identifier("Game (CD 1)") == "disc 1"
    assert extract_disc_identifier("Game (Side A)") == "side a"
    assert extract_disc_identifier("Game (Part 2)") == "part 2"
    assert extract_disc_identifier("Game_Disc2.iso") == "disc 2"
    assert extract_disc_identifier("Game-Disc1.bin") == "disc 1"
    assert extract_disc_identifier("Super Mario World") is None
    assert extract_disc_identifier("") is None
    assert extract_disc_identifier(None) is None


def test_extractRevisionIdentifier_parsesRevisionTags():
    # Arrange & Act & Assert
    assert extract_revision_identifier("Game (USA) (v1.01)") == "v1.01"
    assert extract_revision_identifier("Game (USA) (v1.0)") == "v1.0"
    assert extract_revision_identifier("Game (USA) (Rev 1)") == "rev 1"
    assert extract_revision_identifier("Game (USA) (Rev A)") == "rev a"
    assert extract_revision_identifier("Game (USA)") is None
    assert extract_revision_identifier(None) is None


def test_titlesMatch_evaluatesDiscAndRevisionEquality():
    # Arrange & Act & Assert
    assert titles_match("Crash Bandicoot (USA)", "Crash Bandicoot") is True
    assert titles_match("Final Fantasy VII (Disc 1) [!]", "Final Fantasy VII") is True
    assert titles_match("Super Mario World", "Super Mario World") is True
    assert titles_match("Dark Cloud", "Dark Cloud 2") is False
    assert titles_match("Mega Man X", "Mega Man X2") is False

    # Multi-disc matching: same disc matches, different discs MUST NOT match
    assert titles_match("Devil May Cry 2 (USA) (Disc 1)", "Devil May Cry 2 (USA) (Disc 1)") is True
    assert titles_match("Devil May Cry 2 (USA) (Disc 1)", "Devil May Cry 2 (USA) (Disc 2)") is False
    assert titles_match("Devil May Cry 2 (USA) (Disc 2)", "Devil May Cry 2 (USA) (Disc 1)") is False
    assert titles_match("Resident Evil 2 (USA) (Leon Disc)", "Resident Evil 2 (USA) (Claire Disc)") is False
    assert titles_match("Final Fantasy VII (USA) (Disc 1)", "Final Fantasy VII (USA) (Disc 3)") is False

    # Revision matching: different revisions MUST NOT match
    assert titles_match("Dark Cloud 2 (USA) (v1.0)", "Dark Cloud 2 (USA) (v1.1)") is False
    assert titles_match("Sonic Adventure (USA) (Rev 1)", "Sonic Adventure (USA) (Rev 2)") is False
