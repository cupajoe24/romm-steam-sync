"""Unit tests for RomInstall domain model."""

from datetime import datetime

from romm_steam_sync.domain.rom_install import RomInstall


def test_romInstallClass_initialization_setsDefaultTimestampAndAttributes():
    # Arrange & Act
    install = RomInstall(
        rom_id=55,
        file_path="/roms/snes/smw.sfc",
        rom_dir="/roms/snes",
        launchable=True,
    )

    # Assert
    assert install.rom_id == 55
    assert install.file_path == "/roms/snes/smw.sfc"
    assert install.rom_dir == "/roms/snes"
    assert install.launchable is True
    assert isinstance(install.installed_at, datetime)
