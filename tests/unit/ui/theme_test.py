"""Unit tests for UI theme color constants."""

import re

from romm_steam_sync.ui import theme


def test_themeColorConstants_areValidHexCodes() -> None:
    hex_color_pattern = re.compile(r"^#[0-9a-fA-F]{6}$")

    color_constants = [
        theme.COLOR_ERROR,
        theme.COLOR_ERROR_HOVER,
        theme.COLOR_SUCCESS,
        theme.COLOR_SUCCESS_HOVER,
        theme.COLOR_WARNING,
        theme.COLOR_WARNING_HOVER,
        theme.COLOR_INFO,
        theme.COLOR_INFO_HOVER,
        theme.COLOR_NEUTRAL,
        theme.COLOR_NEUTRAL_HOVER,
        theme.COLOR_MUTED,
        theme.COLOR_SLATE,
        theme.COLOR_SLATE_HOVER,
        theme.COLOR_PURPLE,
        theme.COLOR_PURPLE_HOVER,
        theme.COLOR_TEXT,
        theme.COLOR_TEXT_MUTED,
        theme.COLOR_CARD_BG,
        theme.COLOR_SURFACE,
        theme.COLOR_SURFACE_DARK,
        theme.COLOR_SURFACE_INSET,
        theme.COLOR_BORDER,
    ]

    for color in color_constants:
        assert isinstance(color, str)
        assert hex_color_pattern.match(color) is not None, f"{color} is not a valid hex code"

