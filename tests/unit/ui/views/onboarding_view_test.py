"""Unit tests for OnboardingView step navigation, verification, and wizard synchronization."""

from unittest.mock import MagicMock, patch
import customtkinter as ctk
import pytest

from romm_steam_sync.config import AppSettings
from romm_steam_sync.ui.views.onboarding_view import OnboardingView


def test_navigationAndStepTransitions(tmp_path):
    # Arrange
    try:
        root = ctk.CTk()
        root.withdraw()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available in test environment: {e}")
        raise

    try:
        settings_file = tmp_path / "settings.json"
        with patch.object(AppSettings, "get_settings_file", return_value=settings_file), \
             patch("romm_steam_sync.ui.views.onboarding_view.RomMApiClient") as mock_romm_api:

            settings = AppSettings(onboarding_complete=False)
            completed_called = False

            def on_complete():
                nonlocal completed_called
                completed_called = True

            wizard = OnboardingView(root, settings=settings, on_complete=on_complete)

            # Act 1: Initial step
            assert wizard.current_step == 1

            # Act 2: Move to Step 2
            wizard._show_step(2)
            assert wizard.current_step == 2

            # Act 3: Step 2 server test
            mock_instance = mock_romm_api.return_value
            mock_instance.authenticate.return_value = (True, "OK")
            mock_instance.test_connection.return_value = (True, "OK")
            wizard.step2_url_entry.delete(0, "end")
            wizard.step2_url_entry.insert(0, "http://localhost:8080")
            wizard.step2_key_entry.delete(0, "end")
            wizard.step2_key_entry.insert(0, "test-api-token")
            wizard._test_and_save_step2()

            # Assert 3
            assert wizard.current_step == 3
            assert settings.romm_url == "http://localhost:8080"
            assert settings.api_key == "test-api-token"

            # Act 4: Move through steps
            wizard._save_step3_and_next()
            assert wizard.current_step == 4

            wizard._show_step(5)
            assert wizard.current_step == 5

            # Act 5: Select / Deselect in Step 5
            wizard.step5_vars["nes"] = ctk.BooleanVar(value=False)
            wizard.step5_vars["snes"] = ctk.BooleanVar(value=False)
            wizard._step5_select_all()
            assert wizard.step5_vars["nes"].get() is True
            assert wizard.step5_vars["snes"].get() is True

            wizard._step5_deselect_all()
            assert wizard.step5_vars["nes"].get() is False
            assert wizard.step5_vars["snes"].get() is False

            # Act 6: Save Step 5 selection
            wizard.step5_vars["nes"].set(True)
            wizard._save_step5_and_next()
            assert wizard.current_step == 6
            assert "nes" in settings.enabled_platforms
            assert settings.onboarding_complete is False

            # Act 7: Transition to Step 7 (viewing step 7 flags onboarding_complete)
            wizard._show_step(7)
            assert wizard.current_step == 7
            assert settings.onboarding_complete is True
            assert completed_called is False
            expected_msg = (
                "Library sync is complete, you can re-open Steam and your games "
                "should appear in Library > Collections. If you want to uninstall "
                "or manage games come back to this app. Press \"Finish\" to finalize "
                "onboarding."
            )
            assert wizard.step7_msg_label.cget("text") == expected_msg

            # Act 8: Complete onboarding via finish button
            wizard._complete_onboarding()
            assert settings.onboarding_complete is True
            assert completed_called is True
    finally:
        root.destroy()


def test_step4SgdbKeyVerification(tmp_path):
    # Arrange
    try:
        root = ctk.CTk()
        root.withdraw()
    except Exception as e:
        if "Tcl" in type(e).__name__ or "init.tcl" in str(e):
            pytest.skip(f"Tkinter/Tcl not available in test environment: {e}")
        raise

    try:
        settings_file = tmp_path / "settings.json"
        with patch.object(AppSettings, "get_settings_file", return_value=settings_file):
            settings = AppSettings(onboarding_complete=False)
            wizard = OnboardingView(root, settings=settings, on_complete=lambda: None)
            wizard._show_step(4)

            # Act 1: Empty key
            wizard.step4_key_entry.delete(0, "end")
            wizard._test_sgdb_key()
            assert "Please enter an API Key" in wizard.step4_status_lbl.cget("text")

            # Act 2: Valid key
            wizard.step4_key_entry.insert(0, "sgdb_test_key_123")
            with patch("romm_steam_sync.ui.views.onboarding_view.SteamGridDbClient") as mock_client_cls:
                mock_client = mock_client_cls.return_value
                mock_client.verify_api_key.return_value = (True, "SteamGridDB API key is valid")
                wizard._test_sgdb_key()
                assert "SteamGridDB API key is valid" in wizard.step4_status_lbl.cget("text")

            # Act 3: Save and advance
            wizard._save_step4_and_next()
            assert wizard.current_step == 5
            assert settings.steamgriddb_api_key == "sgdb_test_key_123"
    finally:
        root.destroy()


def test_step5SelectAndDeselectAll_togglesVariables():
    # Arrange
    view = OnboardingView.__new__(OnboardingView)
    mock_var1 = MagicMock()
    mock_var2 = MagicMock()
    view.step5_vars = {"nes": mock_var1, "snes": mock_var2}

    # Act 1: Select All
    view._step5_select_all()

    # Assert 1
    mock_var1.set.assert_called_with(True)
    mock_var2.set.assert_called_with(True)

    # Act 2: Deselect All
    view._step5_deselect_all()

    # Assert 2
    mock_var1.set.assert_called_with(False)
    mock_var2.set.assert_called_with(False)


def test_updateStep6Ui_indeterminateOnCalculating():
    # Arrange
    view = OnboardingView.__new__(OnboardingView)
    view.settings = AppSettings()
    view.step6_progress_bar = MagicMock()
    view.step6_progress_bar.cget.return_value = "determinate"
    view.step6_status_lbl = MagicMock()
    view.step6_conveyor = MagicMock()

    # Act
    view._update_step6_ui(0.25, "Checking RomM library and calculating library changes...")

    # Assert
    view.step6_progress_bar.configure.assert_called_with(mode="indeterminate")
    view.step6_progress_bar.start.assert_called_once()
    view.step6_status_lbl.configure.assert_called_with(text="Checking RomM library and calculating library changes...")
    view.step6_conveyor.append_log.assert_called_with("[25%] Checking RomM library and calculating library changes...")


def test_updateStep6Ui_switchesBackToDeterminate():
    # Arrange
    view = OnboardingView.__new__(OnboardingView)
    view.settings = AppSettings()
    view.step6_progress_bar = MagicMock()
    view.step6_progress_bar.cget.return_value = "indeterminate"
    view.step6_status_lbl = MagicMock()
    view.step6_conveyor = MagicMock()

    # Act
    view._update_step6_ui(0.50, "Added [1/2]: Chrono Trigger", rom_name="Chrono Trigger")

    # Assert
    view.step6_progress_bar.stop.assert_called_once()
    view.step6_progress_bar.configure.assert_called_with(mode="determinate")
    view.step6_progress_bar.set.assert_called_with(0.50)
    view.step6_status_lbl.configure.assert_called_with(text="Added [1/2]: Chrono Trigger")
    view.step6_conveyor.add_cover.assert_called_once_with("Chrono Trigger", None)


def test_runWizardSyncThread_resetsProgress():
    # Arrange
    view = OnboardingView.__new__(OnboardingView)
    view.settings = AppSettings()
    view.step6_start_btn = MagicMock()
    view.step6_cancel_btn = MagicMock()
    view.step6_finish_btn = MagicMock()
    view.step6_back_btn = MagicMock()
    view.step6_progress_bar = MagicMock()
    view.step6_status_lbl = MagicMock()
    view.step6_conveyor = MagicMock()

    # Act
    with patch("threading.Thread") as mock_thread_cls:
        view._run_wizard_sync_thread()

    # Assert
    view.step6_start_btn.configure.assert_called_with(state="disabled")
    view.step6_cancel_btn.configure.assert_called_with(state="normal")
    view.step6_finish_btn.configure.assert_called_with(state="disabled")
    view.step6_back_btn.configure.assert_called_with(state="disabled")
    view.step6_progress_bar.stop.assert_called_once()
    view.step6_progress_bar.configure.assert_called_with(mode="determinate")
    view.step6_progress_bar.set.assert_called_with(0.0)
    view.step6_conveyor.clear.assert_called_once()
    assert mock_thread_cls.return_value.start.called


def test_onStep6Finished_success():
    # Arrange
    view = OnboardingView.__new__(OnboardingView)
    view.settings = AppSettings()
    view.step6_start_btn = MagicMock()
    view.step6_cancel_btn = MagicMock()
    view.step6_finish_btn = MagicMock()
    view.step6_back_btn = MagicMock()
    view.step6_progress_bar = MagicMock()
    view.step6_status_lbl = MagicMock()
    view.step6_conveyor = MagicMock()
    view.winfo_toplevel = MagicMock()

    # Act
    with patch("romm_steam_sync.ui.views.onboarding_view.show_sync_complete_modal") as mock_complete_modal:
        view._on_step6_finished(True, "Sync complete", 5)

    # Assert
    view.step6_progress_bar.stop.assert_called_once()
    view.step6_progress_bar.configure.assert_called_with(mode="determinate")
    view.step6_progress_bar.set.assert_called_with(1.0)
    view.step6_start_btn.configure.assert_called_with(state="normal")
    view.step6_cancel_btn.configure.assert_called_with(state="disabled")
    view.step6_finish_btn.configure.assert_called_with(state="normal")
    view.step6_back_btn.configure.assert_called_with(state="normal")
    mock_complete_modal.assert_called_once_with(view.winfo_toplevel.return_value)


def test_onStep6Finished_failure():
    # Arrange
    view = OnboardingView.__new__(OnboardingView)
    view.settings = AppSettings()
    view.step6_start_btn = MagicMock()
    view.step6_cancel_btn = MagicMock()
    view.step6_finish_btn = MagicMock()
    view.step6_back_btn = MagicMock()
    view.step6_progress_bar = MagicMock()
    view.step6_status_lbl = MagicMock()
    view.step6_conveyor = MagicMock()
    view.winfo_toplevel = MagicMock()

    # Act
    view._on_step6_finished(False, "Sync cancelled by user.", 0)

    # Assert
    view.step6_progress_bar.stop.assert_called_once()
    view.step6_progress_bar.configure.assert_called_with(mode="determinate")
    view.step6_status_lbl.configure.assert_called_with(
        text="Sync cancelled by user.",
        text_color="#e67e22",
    )
    view.step6_finish_btn.configure.assert_called_with(state="normal")


def test_promptStep6OnTimeout():
    # Arrange
    view = OnboardingView.__new__(OnboardingView)
    view.step6_progress_bar = MagicMock()
    view.winfo_toplevel = MagicMock()
    view.after = lambda delay, cb: cb()

    with patch("romm_steam_sync.ui.views.onboarding_view.RomMTimeoutModal") as mock_timeout_modal:
        def invoke_choice(parent, platform_name, backup_id, on_choice):
            on_choice("retry")

        mock_timeout_modal.side_effect = invoke_choice

        # Act
        choice = view._prompt_step6_on_timeout("Nintendo Switch", "backup_123")

        # Assert
        assert choice == "retry"
        view.step6_progress_bar.stop.assert_called_once()
        view.step6_progress_bar.configure.assert_called_with(mode="determinate")


def test_showStep_step7FlagsOnboardingComplete():
    # Arrange
    view = OnboardingView.__new__(OnboardingView)
    mock_settings = MagicMock()
    mock_settings.onboarding_complete = False
    view.settings = mock_settings
    view.TOTAL_STEPS = 7
    view.progress_bar = MagicMock()
    view.step_indicator_label = MagicMock()
    view.step_frames = [MagicMock() for _ in range(7)]

    # Act
    view._show_step(7)

    # Assert
    assert mock_settings.onboarding_complete is True
    mock_settings.save.assert_called_once()
    assert view.current_step == 7


def test_completeOnboarding_setsFlagAndCallsCallback():
    # Arrange
    view = OnboardingView.__new__(OnboardingView)
    mock_settings = MagicMock()
    mock_settings.onboarding_complete = False
    view.settings = mock_settings
    mock_callback = MagicMock()
    view.on_complete = mock_callback

    # Act
    view._complete_onboarding()

    # Assert
    assert mock_settings.onboarding_complete is True
    mock_settings.save.assert_called_once()
    mock_callback.assert_called_once()


def test_initStep7Completion_rendersExpectedMessage():
    # Arrange
    view = OnboardingView.__new__(OnboardingView)
    view.content_card = MagicMock()
    view.step_frames = []

    # Act
    with patch("customtkinter.CTkFrame"), \
         patch("customtkinter.CTkLabel") as mock_label, \
         patch("customtkinter.CTkButton"), \
         patch("customtkinter.CTkFont"):
        view._init_step_7_completion()

    # Assert
    assert len(view.step_frames) == 1
    expected_msg = (
        "Library sync is complete, you can re-open Steam and your games "
        "should appear in Library > Collections. If you want to uninstall "
        "or manage games come back to this app. Press \"Finish\" to finalize "
        "onboarding."
    )
    called_texts = [call.kwargs.get("text") for call in mock_label.call_args_list]
    assert expected_msg in called_texts



