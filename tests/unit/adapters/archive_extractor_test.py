"""Unit tests for ArchiveExtractor and ZIP-slip protection."""

import io
from pathlib import Path
import tarfile
import zipfile
import pytest

from romm_steam_sync.adapters.archive_extractor import (
    ArchiveExtractor,
    ArchiveExtractorError,
    ZipSlipSecurityError,
)


def test_extractAndCleanup_zipUnpacksAndDeletesArchive(tmp_path):
    # Arrange
    dest_dir = tmp_path / "ps1"
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_file = dest_dir / "Crash Bandicoot (USA).zip"
    with zipfile.ZipFile(zip_file, "w") as zf:
        zf.writestr("Crash Bandicoot (USA).cue", 'FILE "Crash Bandicoot (USA).bin" BINARY\n')
        zf.writestr("Crash Bandicoot (USA).bin", b"\x00" * 4096)
        zf.writestr("readme.txt", "Ripped by SceneGroup")
    progress_messages = []

    # Act
    extracted, launch_file = ArchiveExtractor.extract_and_cleanup(
        archive_path=zip_file,
        dest_dir=dest_dir,
        preferred_stem="Crash Bandicoot (USA)",
        progress_callback=lambda msg: progress_messages.append(msg),
    )

    # Assert
    assert not zip_file.exists()
    cue_path = dest_dir / "Crash Bandicoot (USA).cue"
    bin_path = dest_dir / "Crash Bandicoot (USA).bin"
    txt_path = dest_dir / "readme.txt"
    assert cue_path.exists()
    assert bin_path.exists()
    assert txt_path.exists()
    assert launch_file == cue_path
    assert len(extracted) == 3
    assert len(progress_messages) > 0


def test_extractAndCleanup_7zUnpacksAndIdentifiesLaunchFile(tmp_path):
    # Arrange
    try:
        import py7zr
    except ImportError:
        pytest.skip("py7zr not installed")

    dest_dir = tmp_path / "dreamcast"
    dest_dir.mkdir(parents=True, exist_ok=True)
    seven_zip_file = dest_dir / "Crazy Taxi.7z"
    with py7zr.SevenZipFile(seven_zip_file, "w") as sz:
        sz.writestr(b"MComprHD" + b"\x00" * 1024, "Crazy Taxi.chd")
        sz.writestr(b"image data", "cover.jpg")

    # Act
    extracted, launch_file = ArchiveExtractor.extract_and_cleanup(
        archive_path=seven_zip_file,
        dest_dir=dest_dir,
        preferred_stem="Crazy Taxi",
    )

    # Assert
    assert not seven_zip_file.exists()
    chd_path = dest_dir / "Crazy Taxi.chd"
    assert chd_path.exists()
    assert launch_file == chd_path


def test_extractAndCleanup_tarGzUnpacksAndIdentifiesLaunchFile(tmp_path):
    # Arrange
    dest_dir = tmp_path / "ps2"
    dest_dir.mkdir(parents=True, exist_ok=True)
    tar_path = dest_dir / "Final Fantasy X.tar.gz"
    iso_content = b"CD001" + b"\x00" * 2048
    with tarfile.open(tar_path, "w:gz") as tf:
        ti = tarfile.TarInfo(name="Final Fantasy X.iso")
        ti.size = len(iso_content)
        tf.addfile(ti, io.BytesIO(iso_content))

    # Act
    extracted, launch_file = ArchiveExtractor.extract_and_cleanup(
        archive_path=tar_path,
        dest_dir=dest_dir,
    )

    # Assert
    assert not tar_path.exists()
    iso_path = dest_dir / "Final Fantasy X.iso"
    assert iso_path.exists()
    assert launch_file == iso_path


def test_extractArchive_withZipSlipRaisesSecurityError(tmp_path):
    # Arrange
    dest_dir = tmp_path / "safe_dir"
    dest_dir.mkdir(parents=True, exist_ok=True)
    malicious_zip = tmp_path / "malicious.zip"
    with zipfile.ZipFile(malicious_zip, "w") as zf:
        zf.writestr("../../evil.txt", "pwned")

    # Act & Assert
    with pytest.raises(ZipSlipSecurityError):
        ArchiveExtractor.extract_archive(malicious_zip, dest_dir)

    assert not (tmp_path / "evil.txt").exists()


def test_extractArchive_filtersMacosMetadata(tmp_path):
    # Arrange
    dest_dir = tmp_path / "gc"
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_file = dest_dir / "Metroid Prime.zip"
    with zipfile.ZipFile(zip_file, "w") as zf:
        zf.writestr("Metroid Prime.rvz", b"RVZ1" + b"\x00" * 512)
        zf.writestr("__MACOSX/._Metroid Prime.rvz", b"metadata")
        zf.writestr(".DS_Store", b"junk")

    # Act
    extracted = ArchiveExtractor.extract_archive(zip_file, dest_dir)

    # Assert
    assert len(extracted) == 1
    assert extracted[0].name == "Metroid Prime.rvz"
    assert not (dest_dir / "__MACOSX").exists()
