"""Unit tests for Rom aggregate root."""

from romm_steam_sync.domain.rom import Rom


def test_bindShortcut_setsShortcutAppId():
    # Arrange
    rom = Rom(
        rom_id=101,
        platform_slug="snes",
        name="Super Mario World",
        summary="Classic platformer",
    )

    # Act
    rom.bind_shortcut(-123456789)

    # Assert
    assert rom.shortcut_app_id == -123456789
    assert rom.is_bound is True


def test_unbindShortcut_clearsShortcutAppId():
    # Arrange
    rom = Rom(
        rom_id=101,
        platform_slug="snes",
        name="Super Mario World",
        shortcut_app_id=987654321,
    )

    # Act
    rom.unbind_shortcut()

    # Assert
    assert rom.shortcut_app_id is None
    assert rom.is_bound is False


def test_romClass_creationWithDefaults_initializesUnboundEntity():
    # Arrange & Act
    rom = Rom(
        rom_id=202,
        platform_slug="n64",
        name="The Legend of Zelda: Ocarina of Time",
    )

    # Assert
    assert rom.rom_id == 202
    assert rom.platform_slug == "n64"
    assert rom.name == "The Legend of Zelda: Ocarina of Time"
    assert rom.shortcut_app_id is None
    assert rom.is_bound is False
    assert rom.sibling_group_key is None
