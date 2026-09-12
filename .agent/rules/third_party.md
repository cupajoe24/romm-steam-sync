---
trigger: always_on
---

# Third-Party Dependencies Guidelines

This rule enforces standards for managing, storing, modifying, and checking third-party packages and dependencies in this project.

## 1. Directory Location
- **Mandatory Location**: Any third-party package, library, vendored code, or external module used in this project (i.e., anything where the source code was not created directly in this project) MUST reside under the `third_party/` directory.
- **No External Placement**: Do not place third-party source files outside of `third_party/`.

## 2. Direct Modifications Prohibited
- **Immutability**: Source files located within the `third_party/` directory MUST NEVER be modified directly.
- **Maintenance**: Updates or fixes to third-party code should be handled via package manager updates, upstream vendor syncs, or tracked patch mechanisms rather than manual edits.

## 3. Linting and Formatting Exemption
- **Exclusion from Checks**: All files and directories under `third_party/` are strictly EXEMPT from all project linting, formatting, type checking, and static analysis checks (e.g., Flake8, Ruff, Black, Prettier, ESLint, Mypy).
- **Tooling Configuration**: All linter and formatter configuration files must ignore or exclude the `third_party/` directory path.
