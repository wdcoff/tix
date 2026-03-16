"""Tests for tix.services.terminal_launcher — detection and escaping logic."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tix.services.terminal_launcher import (
    _detect_terminal,
    _escape_applescript,
    _launch_iterm,
    _launch_terminal_app,
    _launch_warp,
)


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


class TestEscapeApplescript:
    """_escape_applescript should neutralise special characters."""

    def test_double_quote(self) -> None:
        assert _escape_applescript('say "hello"') == 'say \\"hello\\"'

    def test_backslash(self) -> None:
        assert _escape_applescript("back\\slash") == "back\\\\slash"

    def test_single_quote_unchanged(self) -> None:
        assert _escape_applescript("it's") == "it's"

    def test_dollar_sign_unchanged(self) -> None:
        assert _escape_applescript("$HOME") == "$HOME"

    def test_combined(self) -> None:
        result = _escape_applescript('path\\"with$stuff')
        assert result == 'path\\\\\\"with$stuff'

    def test_plain_string_unchanged(self) -> None:
        assert _escape_applescript("hello world") == "hello world"


class TestLauncherEscaping:
    """Verify that launcher functions apply escaping to cwd and command."""

    MALICIOUS_PATH = Path('/Users/wyatt/code/"worktree')
    MALICIOUS_CMD = 'echo "injected" && rm -rf /'

    @patch("tix.services.terminal_launcher.subprocess.run")
    def test_iterm_escapes_applescript(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        _launch_iterm(self.MALICIOUS_PATH, self.MALICIOUS_CMD, 42)

        script = mock_run.call_args[0][0][2]  # ["osascript", "-e", script]
        assert '\\"worktree' in script
        assert '\\"injected\\"' in script
        assert 'cd /Users/wyatt/code/"worktree' not in script

    @patch("tix.services.terminal_launcher.subprocess.run")
    def test_terminal_app_escapes_applescript(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        _launch_terminal_app(self.MALICIOUS_PATH, self.MALICIOUS_CMD, 42)

        script = mock_run.call_args[0][0][2]
        assert '\\"worktree' in script
        assert '\\"injected\\"' in script
        assert 'cd /Users/wyatt/code/"worktree' not in script

    @patch("tix.services.terminal_launcher.subprocess.Popen")
    @patch("tix.services.terminal_launcher.subprocess.run")
    def test_warp_escapes_command(self, mock_run: MagicMock, mock_popen: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        _launch_warp(self.MALICIOUS_PATH, self.MALICIOUS_CMD, 42)

        # Step 1: URI scheme opens tab with CWD
        uri_call = mock_run.call_args[0][0]
        assert uri_call[0] == "open"
        assert "warp://action/new_tab?path=" in uri_call[1]

        # Step 2: AppleScript types escaped command
        script = mock_popen.call_args[0][0][2]
        assert '\\"injected\\"' in script
        assert 'echo "injected"' not in script
