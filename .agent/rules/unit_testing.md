---
trigger: always_on
---

# Unit Testing Guidelines & Execution Rule

## Execution Environment & Commands
Always run unit tests using the project's virtual environment Python interpreter (`.venv`):

- **Windows (PowerShell/CMD)**:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests/unit
  ```

- **Linux / macOS (Bash/Zsh)**:
  ```bash
  ./.venv/bin/python -m pytest tests/unit
  ```

### Why system `python` / `py` fails:
System Python does not contain the workspace dependencies (`pytest`, `requests`, `customtkinter`, `vdf`, `pydantic`, etc.). Calling `python -m pytest` or `py -m pytest` directly uses global Python 3.9 and fails with `No module named pytest`.

## Test Organization & Guidelines
1. **1:1 File Mapping**: Each source code file with testable logic has a corresponding test file called `<source_filename>_test.py`. All tests for that source file MUST reside exclusively in that corresponding test file.
2. **No One-Off Test Files**: All tests must reside in test files as defined above; arbitrary or one-off test files (e.g. `test_feature_x.py`, `test_deduplication.py`) that do not map directly to a source file are forbidden.
3. **Directory Structure Mirroring**: To support source files with identical names across subpackages (such as `launcher/app.py` vs `ui/app.py`), the directory structure under `tests/unit/` mirrors the package layout of `src/romm_steam_sync/` (e.g., `tests/unit/launcher/app_test.py` and `tests/unit/ui/app_test.py`).
4. **Test Naming Convention**: Each unit test function must be named according to this pattern:
   `test_<classOrFunctionUnderTest>_<behaviorUnderTest>`
   If the behavior can have multiple outcomes or error states:
   `test_<classOrFunctionUnderTest>_<behaviorUnderTest>_<expectedOutcome>`
   Each segment between underscores (`<classOrFunctionUnderTest>`, `<behaviorUnderTest>`, `<expectedOutcome>`) must be in `lowerCamelCase`:
   - Standalone function: function name in lowerCamelCase (e.g., `computeSiblingGroupKey` for `compute_sibling_group_key`).
   - Class method: method name in lowerCamelCase (e.g., `bindShortcut` for `Rom.bind_shortcut`).
   - Class/Constructor: class name in lowerCamelCase with `Class` suffix (e.g., `romClass` for `Rom`, `appSettingsClass` for `AppSettings`).
   Examples:
   - `test_bindShortcut_setsShortcutAppId`
   - `test_romClass_creationWithDefaults_initializesUnboundEntity`
   - `test_computeSiblingGroupKey_scopesByPlatformSlug`
   - `test_getRoms_returnsPayload`
   - `test_setupLogging_configuresFileAndStreamHandlers`
5. **Arrange/Act/Assert (AAA) Pattern**: Each unit test must be structured according to the Arrange, Act, and Assert pattern, with a blank new line separating each block:
   ```python
   def test_bindShortcut_setsShortcutAppId():
       # Arrange
       rom = Rom(rom_id=101, platform_slug="snes", name="Super Mario World")

       # Act
       rom.bind_shortcut(-123456789)

       # Assert
       assert rom.shortcut_app_id == -123456789
   ```
6. **Isolation & Mocking**: Use `pytest` fixtures and `unittest.mock` for mocking external network requests (RomM API, SteamGridDB API) and system interactions (Steam process status, subprocess invocations). Never hit external network endpoints in unit tests.

