"""Unit tests for LibraryView game list, uninstall feature, and title matching."""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from romm_steam_sync.config import AppSettings
from romm_steam_sync.domain import Rom, RomInstall
from romm_steam_sync.service_layer.db_session import DatabaseSession
from romm_steam_sync.ui.views.library_view import (
    LibraryGameTile,
    LibraryView,
    _sanitize_title,
    _titles_match,
)


def test_titlesMatch_preventsFalsePositiveSequelMatches():
    # Arrange & Act & Assert
    assert _sanitize_title("Dark Cloud 2 (USA) (v1.0)") == "dark cloud 2"
    assert _sanitize_title("Ape Escape 3 [!]") == "ape escape 3"

    assert _titles_match("Dark Cloud", "Dark Cloud 2 (USA)") is False
    assert _titles_match("Ape Escape", "Ape Escape 3 (USA)") is False
    assert _titles_match("Super Mario 64", "Super Mario Sunshine") is False
    assert _titles_match("Final Fantasy VII", "Final Fantasy VIII") is False

    assert _titles_match("Dark Cloud 2", "Dark Cloud 2 (USA)") is True
    assert _titles_match("Ape Escape 3", "Ape Escape 3 (USA) (v1.01)") is True
    assert _titles_match("Pokemon Red Version", "Pokemon Red (USA)") is True


def test_loadAndUninstall_deletesFileAndDbRecord(tmp_path, monkeypatch):
    # Arrange
    db_path = tmp_path / "test_library.db"
    download_dir = tmp_path / "roms"
    download_dir.mkdir(parents=True, exist_ok=True)
    n64_dir = download_dir / "n64"
    n64_dir.mkdir(parents=True, exist_ok=True)

    rom_file = n64_dir / "SuperMario64.z64"
    rom_file.write_bytes(b"dummy rom bytes 12345")

    with DatabaseSession(db_path) as db:
        rom_entity = Rom(rom_id=999, platform_slug="n64", name="Super Mario 64")
        db.roms.add(rom_entity)
        install_entity = RomInstall(rom_id=999, file_path=str(rom_file), rom_dir=str(n64_dir))
        db.installs.add(install_entity)
        db.commit()

    settings = AppSettings(download_dir=str(download_dir))
    monkeypatch.setattr("romm_steam_sync.ui.views.library_view.DatabaseSession", lambda: DatabaseSession(db_path))

    view = LibraryView.__new__(LibraryView)
    view.settings = settings
    view.on_navigate_tab = None
    view.db_session = DatabaseSession(db_path)
    view.installed_games = []

    # Act 1: Load installed games
    view.load_installed_games()

    # Assert 1
    assert len(view.installed_games) == 1
    assert view.installed_games[0]["rom_id"] == 999
    assert view.installed_games[0]["name"] == "Super Mario 64"
    assert Path(view.installed_games[0]["file_path"]).exists()

    # Act 2: Uninstall game
    with patch.object(view, "refresh"):
        view._uninstall_game(999, str(rom_file))

    # Assert 2
    assert not rom_file.exists()
    with DatabaseSession(db_path) as db:
        inst = db.installs.get(999)
        assert inst is None


def test_launchGame_spawnsSubprocess():
    # Arrange
    with patch("romm_steam_sync.ui.views.library_view.subprocess.Popen") as mock_popen, \
         patch("romm_steam_sync.ui.views.library_view.get_installed_wrapper_path") as mock_wrapper:

        fake_wrapper = Path("/fake/path/romm-steam-sync-launcher")
        mock_wrapper.return_value = fake_wrapper

        view = LibraryView.__new__(LibraryView)
        view.settings = AppSettings()

        # Act
        view._launch_game(123, "gba")

        # Assert
        assert mock_popen.called
        args, _ = mock_popen.call_args
        cmd = args[0]
        assert "--rom-id" in cmd
        assert "123" in cmd
        assert "--platform" in cmd
        assert "gba" in cmd


def test_launchGame_posix_usesStartNewSession():
    # Arrange
    fake_wrapper = Path("/fake/path/romm-steam-sync-launcher")
    with patch("romm_steam_sync.ui.views.library_view.subprocess.Popen") as mock_popen, \
         patch("romm_steam_sync.ui.views.library_view.get_installed_wrapper_path", return_value=fake_wrapper), \
         patch("romm_steam_sync.ui.views.library_view.sys.platform", "linux"):

        view = LibraryView.__new__(LibraryView)
        view.settings = AppSettings()

        # Act
        view._launch_game(123, "gba")

        # Assert
        assert mock_popen.called
        _, kwargs = mock_popen.call_args
        assert kwargs.get("start_new_session") is True
        assert "creationflags" not in kwargs


def test_effectiveWidthAndColCount_calculatesGrid():
    # Arrange
    view = LibraryView.__new__(LibraryView)
    view.winfo_width = MagicMock(return_value=1)
    view.scroll_frame = MagicMock()
    view.scroll_frame.winfo_width.return_value = 1
    view.master = MagicMock()
    view.master.winfo_width.return_value = 1
    toplevel_mock = MagicMock()
    toplevel_mock.winfo_width.return_value = 1
    view.winfo_toplevel = MagicMock(return_value=toplevel_mock)

    # Act 1: Fallback when unrendered (winfo_width <= 1)
    eff_w_1 = view._get_effective_width()
    col_cnt_1 = view._get_col_count()

    # Assert 1
    assert eff_w_1 == 800
    assert col_cnt_1 == 5

    # Act 2: Fallback when Tkinter root reports default unmapped 200px
    view.winfo_width.return_value = 150
    toplevel_mock.winfo_width.return_value = 200
    eff_w_unmapped_tk = view._get_effective_width()
    col_cnt_unmapped_tk = view._get_col_count()

    # Assert 2
    assert eff_w_unmapped_tk == 800
    assert col_cnt_unmapped_tk == 5

    # Act 3: Rendered width
    view.winfo_width.return_value = 950
    eff_w_2 = view._get_effective_width()
    col_cnt_2 = view._get_col_count()

    # Assert 3
    assert eff_w_2 == 950
    assert col_cnt_2 == 6


def test_hover_updatesColors():
    # Arrange
    tile = LibraryGameTile.__new__(LibraryGameTile)
    tile.configure = MagicMock()
    tile.img_frame = MagicMock()
    tile.name_lbl = MagicMock()
    tile.fallback_label = MagicMock()

    # Act 1: Enter
    tile._on_enter()

    # Assert 1
    tile.configure.assert_called_with(border_color="#4299e1", fg_color="#2b374e")
    tile.img_frame.configure.assert_called_with(fg_color="#1a202c")
    tile.name_lbl.configure.assert_called_with(text_color="#63b3ed")
    tile.fallback_label.configure.assert_called_with(text_color="#63b3ed")

    # Act 2: Leave
    tile.winfo_containing = MagicMock(return_value=None)
    event_mock = MagicMock(x_root=100, y_root=100)
    tile._on_leave(event_mock)

    # Assert 2
    tile.configure.assert_called_with(border_color="#2d3748", fg_color="#1a202c")
    tile.img_frame.configure.assert_called_with(fg_color="#12161f")
    tile.name_lbl.configure.assert_called_with(text_color="#edf2f7")
    tile.fallback_label.configure.assert_called_with(text_color="#a0aec0")


def test_scanAndUninstallSubfolder_removesGameDirectory(tmp_path, monkeypatch):
    # Arrange
    db_path = tmp_path / "test_library_subfolder.db"
    download_dir = tmp_path / "roms"
    download_dir.mkdir(parents=True, exist_ok=True)
    dc_dir = download_dir / "dc"
    dc_dir.mkdir(parents=True, exist_ok=True)

    game_dir = dc_dir / "Vigilante 8 - 2nd Offense (USA)"
    game_dir.mkdir(parents=True, exist_ok=True)
    gdi_file = game_dir / "Vigilante 8 - 2nd Offense (USA).gdi"
    gdi_file.write_text("3\n1 0 4 2352 track01.bin 0\n")
    (game_dir / "track01.bin").write_bytes(b"\x00" * 1024)

    with DatabaseSession(db_path) as db:
        rom_entity = Rom(
            rom_id=6326,
            platform_slug="dc",
            name="Vigilante 8: 2nd Offense",
            fs_name="Vigilante 8 - 2nd Offense (USA).zip",
        )
        db.roms.add(rom_entity)
        db.commit()

    settings = AppSettings(download_dir=str(download_dir))
    monkeypatch.setattr("romm_steam_sync.ui.views.library_view.DatabaseSession", lambda: DatabaseSession(db_path))

    view = LibraryView.__new__(LibraryView)
    view.settings = settings
    view.on_navigate_tab = None
    view.db_session = DatabaseSession(db_path)
    view.installed_games = []

    # Act 1: Scan
    view.load_installed_games()

    # Assert 1
    assert len(view.installed_games) == 1
    assert view.installed_games[0]["rom_id"] == 6326
    assert view.installed_games[0]["file_path"] == str(gdi_file)

    with DatabaseSession(db_path) as db:
        inst = db.installs.get(6326)
        assert inst is not None
        assert inst.file_path == str(gdi_file)
        assert inst.rom_dir == str(game_dir)

    # Act 2: Uninstall
    with patch.object(view, "refresh"):
        view._uninstall_game(6326, str(gdi_file))

    # Assert 2
    assert not game_dir.exists()
    assert not gdi_file.exists()
    assert dc_dir.exists()
    with DatabaseSession(db_path) as db:
        assert db.installs.get(6326) is None


def test_onConfigure_ignoresChildWidgetEvents():
    # Arrange
    view = LibraryView.__new__(LibraryView)
    view._resize_timer = None
    view.after = MagicMock()
    view.after_cancel = MagicMock()

    child_event = MagicMock()
    child_event.widget = MagicMock()

    # Act
    view._on_configure(child_event)

    # Assert
    assert view.after.call_count == 0


def test_onConfigure_schedulesDebounceOnSelfEvent():
    # Arrange
    view = LibraryView.__new__(LibraryView)
    view._resize_timer = "existing_timer_id"
    view.after = MagicMock(return_value="new_timer_id")
    view.after_cancel = MagicMock()

    self_event = MagicMock()
    self_event.widget = view

    # Act
    view._on_configure(self_event)

    # Assert
    view.after_cancel.assert_called_once_with("existing_timer_id")
    view.after.assert_called_once_with(100, view._check_col_count_and_render)
    assert view._resize_timer == "new_timer_id"


def test_onConfigure_schedulesDebounceOnCanvasEvent():
    # Arrange
    view = LibraryView.__new__(LibraryView)
    canvas_mock = MagicMock()
    view._canvas = canvas_mock
    view._resize_timer = "existing_timer_id"
    view.after = MagicMock(return_value="new_timer_id")
    view.after_cancel = MagicMock()

    canvas_event = MagicMock()
    canvas_event.widget = canvas_mock

    # Act
    view._on_configure(canvas_event)

    # Assert
    view.after_cancel.assert_called_once_with("existing_timer_id")
    view.after.assert_called_once_with(100, view._check_col_count_and_render)
    assert view._resize_timer == "new_timer_id"


def test_libraryGameTile_whenPillowTkFails_fallsBackGracefullyWithoutCrash(tmp_path):
    # Arrange
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
        img_path = tmp_path / "test_tile_cover.png"
        img = Image.new("RGB", (60, 60), color="green")
        img.save(img_path)

        with patch("customtkinter.CTkImage", side_effect=ModuleNotFoundError("No module named 'PIL._imagingtk'")):
            tile = LibraryGameTile(
                root,
                rom_id=101,
                rom_name="Castlevania",
                platform_slug="psx",
                file_path="/roms/castlevania.chd",
                cover_path=str(img_path),
            )
            root.update_idletasks()

            assert tile is not None
            assert tile.winfo_exists() == 1
            assert tile.name_lbl is not None
            assert tile.cover_widget is not None
    finally:
        root.destroy()


def test_openDetailModal_createsAndTracksInstance_andFocusesExistingIfOpen():
    # Arrange
    view = LibraryView.__new__(LibraryView)
    view._detail_modal = None
    view._launch_game = MagicMock()
    view._uninstall_game = MagicMock()

    game_item = {
        "rom_id": 555,
        "name": "Chrono Trigger",
        "platform_slug": "snes",
        "file_path": "/roms/snes/chrono.sfc",
        "cover_path": "/covers/chrono.png",
    }

    with patch("romm_steam_sync.ui.views.library_view.GameDetailModal") as mock_modal_cls:
        mock_instance = MagicMock()
        mock_instance.winfo_exists.return_value = True
        mock_modal_cls.return_value = mock_instance

        # Act 1: Open modal when none is open
        view._open_detail_modal(game_item)

        # Assert 1: Modal is instantiated and tracked
        mock_modal_cls.assert_called_once_with(
            view,
            rom_id=555,
            rom_name="Chrono Trigger",
            platform_slug="snes",
            file_path="/roms/snes/chrono.sfc",
            cover_path="/covers/chrono.png",
            on_launch=view._launch_game,
            on_uninstall=view._uninstall_game,
        )
        assert view._detail_modal is mock_instance

        # Act 2: Attempt to open again while existing modal is open
        view._open_detail_modal(game_item)

        # Assert 2: Existing modal lifted and focused, not re-instantiated
        assert mock_modal_cls.call_count == 1
        mock_instance.lift.assert_called_once()
        mock_instance.focus.assert_called_once()
