---
trigger: always_on
---

# Python Style, Readability & String Guidelines

This document defines the mandatory Python coding style, typing standards, and UI/string rules for the `romm-steam-sync` repository, strictly adhering to the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html).

---

## 1. Core Directives

1. **Google Python Style Guide**: All Python code written or modified in this repository must comply with Google's Python Style Guide.
2. **No Emojis in Strings**: NEVER include emojis in strings (UI text, buttons, modal titles, status text, placeholders, logs, errors, test fixtures) anywhere in the codebase unless the user explicitly requests them.

---

## 2. Docstring Standards

### A. Requirement
- Every module, class, public method, and non-trivial helper function MUST have a clear docstring.
- Docstrings must use triple double quotes `"""..."""`.

### B. Format
Follow Google docstring format with 4-space indentation for argument and return descriptions:

```python
def sync_save_file(
    rom_id: int,
    file_path: str,
    slot: str = "autosave",
    force_upload: bool = False,
) -> Tuple[bool, str]:
    """Synchronize a local save file with the RomM cloud server.

    Args:
        rom_id: Unique RomM identifier for the target game.
        file_path: Absolute filesystem path to the local save file.
        slot: Save slot identifier (defaults to 'autosave').
        force_upload: Whether to bypass conflict checking and overwrite remote save.

    Returns:
        Tuple containing a boolean success indicator and a descriptive message.

    Raises:
        RomMTimeoutError: If the remote server fails to respond within timeout.
        FileNotFoundError: If the specified local save file path does not exist.
    """
```

### C. Sections
- **`Args:`**: Describe each parameter, its type/meaning, and default value if applicable.
- **`Returns:`**: Describe the return type and semantics.
- **`Raises:`**: List any explicitly raised custom or critical exceptions.

---

## 3. Import Grouping and Ordering

Imports MUST be organized into three distinct blocks separated by a single blank line, sorted alphabetically within each block:

1. **Standard Library Imports** (e.g., `argparse`, `dataclasses`, `logging`, `os`, `pathlib`, `sys`, `typing`)
2. **Third-Party Imports** (e.g., `customtkinter`, `PIL`, `psutil`, `requests`, `vdf`)
3. **Local Application Imports** (e.g., `from romm_steam_sync.domain import ...`, `from romm_steam_sync.adapters import ...`)

```python
import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import customtkinter as ctk
import requests

from romm_steam_sync.adapters.romm_api import RomMApiClient
from romm_steam_sync.config import AppSettings
from romm_steam_sync.domain import RomInstall
```

> [!IMPORTANT]
> **No Mid-File Imports**: All imports must be placed at the top of the module. Do not import inside functions or methods unless strictly required to avoid circular dependency cycles.

---

## 4. String & UI Guidelines: No Emojis Rule

**Do NOT include emojis in strings anywhere in the codebase unless explicitly requested by the user.**

This applies universally across:

1. **View & UI Components**:
   - Button text (e.g., use `"Launch Game"`, not `"🚀 Launch Game"`; `"Save Selections"`, not `"💾 Save Selections"`)
   - Modal dialog titles & headers (e.g., use `"Cancel Library Synchronization?"`, not `"⛔ Cancel Library Synchronization?"`)
   - Status & feedback messages (e.g., use `"Connection failed: ..."`, not `"❌ Connection failed: ..."`)
   - Input placeholders & field labels (e.g., use `"Search installed ROMs..."`, not `"🔍 Search installed ROMs..."`)
   - Form toggle buttons (e.g., use `"Show"` / `"Hide"`, not `"👁"` / `"🙈"`)
   - Badges & fallback labels (e.g., use `"Installed"` / `"RomM Cloud"`, not `"💾 Installed"` / `"☁️ RomM Cloud"`)

2. **Backend, CLI & Logging**:
   - Console outputs, logs, error messages, and exceptions
   - Domain entity fields and database records

3. **Tests**:
   - Unit test assertions and fixtures should match plain text strings without emoji characters.

### Rationale
- **Cross-Platform Consistency**: Emojis render inconsistently or as broken glyphs/question marks depending on system fonts, OS platforms (Windows, macOS, Linux), and terminal encodings.
- **Clean & Professional UI**: Standard typography and cohesive color styling provide a more polished, accessible, and native desktop look and feel.

---

## 5. Type Annotations

- Provide explicit type annotations on all function signatures, method parameters, and return types (including `-> None`).
- Use standard Python 3.9+ compatible typing constructs (`typing.Dict`, `typing.List`, `typing.Optional`, `typing.Tuple`, `typing.Union`, `typing.Callable`, `typing.Any`).
- Where necessary for self-referencing classes, use string annotations or `from __future__ import annotations`.

---

## 6. Exception Handling & Logging

- Never silently swallow exceptions with `pass`.
- Always catch specific exception types where possible.
- Log exceptions using appropriate log levels (`logger.error()`, `logger.warning()`, or `logger.debug()`).

```python
# GOOD: Contextual logging of exceptions
try:
    with open(config_file, "r", encoding="utf-8") as f:
        data = json.load(f)
except FileNotFoundError:
    logger.debug("Config file %s not found; initializing defaults.", config_file)
except Exception as e:
    logger.error("Failed to parse config file %s: %s", config_file, e)
    raise

# BAD: Silent swallow
try:
    do_something()
except Exception:
    pass
```

---

## 7. Naming Conventions

- **Modules & Packages**: `lowercase_with_underscores.py`
- **Classes & Exceptions**: `PascalCase` (e.g., `SteamGuardModal`, `RomMTimeoutError`)
- **Functions, Methods & Variables**: `lowercase_with_underscores` (e.g., `find_local_save_file`, `is_steam_running`)
- **Constants**: `UPPERCASE_WITH_UNDERSCORES` (e.g., `TILE_WIDTH`, `DEFAULT_SAVE_SLOT`)
- **Internal / Protected Attributes**: Single leading underscore (e.g., `_build_ui`, `_record_baseline`)
- Always prefer verbose variable names with complete words, avoid abbreviations.
