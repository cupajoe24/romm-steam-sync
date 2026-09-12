"""Unit tests for GameDetailModal dialog functionality, layout, and actions."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from romm_steam_sync.ui.components.game_detail_modal import GameDetailModal, format_size


def test_formatSize_handlesVariousRanges():
    assert format_size(0) == "Unknown size"
    assert format_size(-100) == "Unknown size"
    assert format_size(500 * 1024) == "500.0 KB"
    assert format_size(15 * 1024 * 1024) == "15.00 MB"
    assert format_size(2 * 1024 * 1024 * 1024) == "2.00 GB"


def test_gameDetailModal_initializesAndPopulatesUI(tmp_path):
    import customtkinter as ctk

    try:
        root = ctk.CTk()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available in test environment: {e}")
        raise

    try:
        root.withdraw()
        test_file = tmp_path / "game.iso"
        test_file.write_bytes(b"dummy iso bytes")

        modal = GameDetailModal(
            parent=root,
            rom_id=123,
            rom_name="Metal Gear Solid",
            platform_slug="psx",
            file_path=str(test_file),
            cover_path=None,
        )
        root.update_idletasks()

        assert modal.winfo_exists() == 1
        assert modal.rom_name == "Metal Gear Solid"
        assert modal.launch_btn is not None
        assert modal.uninstall_btn is not None
        modal.destroy()
    finally:
        root.destroy()


def test_gameDetailModal_whenPillowTkFails_rendersCleanFallback(tmp_path):
    import customtkinter as ctk
    from PIL import Image

    try:
        root = ctk.CTk()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available in test environment: {e}")
        raise

    try:
        root.withdraw()
        test_file = tmp_path / "game.chd"
        test_file.write_bytes(b"dummy chd bytes")
        cover_file = tmp_path / "cover.png"
        img = Image.new("RGB", (60, 60), color="purple")
        img.save(cover_file)

        with patch("customtkinter.CTkImage", side_effect=ModuleNotFoundError("No module named 'PIL._imagingtk'")):
            modal = GameDetailModal(
                parent=root,
                rom_id=456,
                rom_name="Silent Hill",
                platform_slug="psx",
                file_path=str(test_file),
                cover_path=str(cover_file),
            )
            root.update_idletasks()

            assert modal.winfo_exists() == 1
            assert modal.launch_btn is not None
            modal.destroy()
    finally:
        root.destroy()


def test_gameDetailModal_launchAction_invokesCallbackAndDestroys(tmp_path):
    import customtkinter as ctk

    try:
        root = ctk.CTk()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available in test environment: {e}")
        raise

    try:
        root.withdraw()
        test_file = tmp_path / "zelda.z64"
        test_file.write_bytes(b"dummy rom bytes")

        launch_mock = MagicMock()
        modal = GameDetailModal(
            parent=root,
            rom_id=789,
            rom_name="The Legend of Zelda",
            platform_slug="n64",
            file_path=str(test_file),
            cover_path=None,
            on_launch=launch_mock,
        )
        root.update_idletasks()

        modal.launch_btn.invoke()
        launch_mock.assert_called_once_with(789, "n64")
    finally:
        root.destroy()


def test_gameDetailModal_uninstallConfirmationFlow(tmp_path):
    import customtkinter as ctk

    try:
        root = ctk.CTk()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available in test environment: {e}")
        raise

    try:
        root.withdraw()
        test_file = tmp_path / "sonic.bin"
        test_file.write_bytes(b"dummy bin bytes")

        uninstall_mock = MagicMock()
        modal = GameDetailModal(
            parent=root,
            rom_id=1010,
            rom_name="Sonic Adventure",
            platform_slug="dc",
            file_path=str(test_file),
            cover_path=None,
            on_uninstall=uninstall_mock,
        )
        root.update_idletasks()

        # Step 1: Click Uninstall button to show confirmation
        modal.uninstall_btn.invoke()
        root.update_idletasks()

        # Step 2: Confirm Uninstall button should now be present in action frame
        confirm_btn = None
        for child in modal.action_frame.winfo_children():
            if isinstance(child, ctk.CTkButton) and child.cget("text") == "Confirm Uninstall":
                confirm_btn = child
                break

        assert confirm_btn is not None
        confirm_btn.invoke()
        uninstall_mock.assert_called_once_with(1010, str(test_file))
    finally:
        root.destroy()
