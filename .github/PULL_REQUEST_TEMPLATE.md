## Description

Please include a summary of the change and which issue it resolves or feature it introduces.

Fixes # (issue)

---

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Refactoring (code improvement with no functional changes)
- [ ] Documentation update

---

## Checklist

- [ ] My code adheres to the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html).
- [ ] My code has appropriate type annotations and docstrings.
- [ ] **No emojis** are included in any UI text, labels, modals, status messages, logs, or exceptions.
- [ ] I have verified that Steam safety checks are respected (Steam is not running during `shortcuts.vdf` or artwork modifications).
- [ ] I have added unit tests for new or modified functionality.
- [ ] All unit tests pass cleanly when run via the project virtual environment interpreter:
  - Windows: `.\.venv\Scripts\python.exe -m pytest tests/unit`
  - Linux / macOS: `./.venv/bin/python -m pytest tests/unit`
