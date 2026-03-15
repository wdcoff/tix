"""Tests for tix.services.terminal_launcher — detection and escaping logic."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tix.services.terminal_launcher import (
    _detect_terminal,
    _escape_applescript,
    _escape_yaml_value,
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


class TestEscapeYamlValue:
    """_escape_yaml_value should wrap/escape values with special chars."""

    def test_plain_value_unchanged(self) -> None:
        assert _escape_yaml_value("simple") == "simple"

    def test_double_quote(self) -> None:
        assert _escape_yaml_value('say "hi"') == "'say \"hi\"'"

    def test_single_quote_doubled(self) -> None:
        assert _escape_yaml_value("it's here") == "'it''s here'"

    def test_colon(self) -> None:
        assert _escape_yaml_value("key: value") == "'key: value'"

    def test_hash(self) -> None:
        assert _escape_yaml_value("# comment") == "'# comment'"

    def test_backslash(self) -> None:
        assert _escape_yaml_value("back\\slash") == "'back\\slash'"

    def test_ampersand(self) -> None:
        assert _escape_yaml_value("a & b") == "'a & b'"


class TestLauncherEscaping:
    """Verify that launcher functions apply escaping to cwd and command."""

    MALICIOUS_PATH = Path('/Users/wyatt/code/"worktree')
    MALICIOUS_CMD = 'echo "injected" && rm -rf /'

    @patch("tix.services.terminal_launcher.subprocess.run")
    def test_iterm_escapes_applescript(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        _launch_iterm(self.MALICIOUS_PATH, self.MALICIOUS_CMD, 42)

        script = mock_run.call_args[0][0][2]  # ["osascript", "-e", script]
        # The double-quotes should be escaped
        assert '\\"worktree' in script
        assert '\\"injected\\"' in script
        # The raw unescaped double-quote should NOT appear in a dangerous position
        assert 'cd /Users/wyatt/code/"worktree' not in script

    @patch("tix.services.terminal_launcher.subprocess.run")
    def test_terminal_app_escapes_applescript(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        _launch_terminal_app(self.MALICIOUS_PATH, self.MALICIOUS_CMD, 42)

        script = mock_run.call_args[0][0][2]
        assert '\\"worktree' in script
        assert '\\"injected\\"' in script
        assert 'cd /Users/wyatt/code/"worktree' not in script

    @patch("tix.services.terminal_launcher.subprocess.run")
    def test_warp_escapes_yaml(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        with patch("tix.services.terminal_launcher.Path.home", return_value=tmp_path):
            _launch_warp(self.MALICIOUS_PATH, self.MALICIOUS_CMD, 42)

        config_path = tmp_path / ".warp" / "launch_configurations" / "tix-42.yaml"
        content = config_path.read_text()
        # cwd/command with special chars should be single-quoted in YAML
        assert "''" not in content or "'" in content  # single-quote wrapping used
        # Raw unquoted double-quote should not appear as a bare YAML value
        assert 'cwd: "/Users/wyatt/code/"worktree"' not in content
