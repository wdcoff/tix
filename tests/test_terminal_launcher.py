"""Tests for tix.services.terminal_launcher — detection logic."""
from __future__ import annotations

import pytest

from tix.services.terminal_launcher import _detect_terminal


class TestDetectTerminal:
    """_detect_terminal should map TERM_PROGRAM to a normalised name."""

    @pytest.mark.parametrize(
        ("term_program", "expected"),
        [
            ("WarpTerminal", "warp"),
            ("iTerm.app", "iterm"),
            ("Apple_Terminal", "terminal"),
            ("kitty", "kitty"),
        ],
    )
    def test_known_terminals(
        self,
        term_program: str,
        expected: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("TERM_PROGRAM", term_program)
        assert _detect_terminal() == expected

    def test_unknown_terminal_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TERM_PROGRAM", "SomeObscureTerminal")
        assert _detect_terminal() == "default"

    def test_missing_term_program_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("TERM_PROGRAM", raising=False)
        assert _detect_terminal() == "default"
