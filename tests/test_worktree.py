"""Tests for tix.services.worktree — validation logic only.

Does NOT test actual git operations (would need a real repo).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from tix.errors import GitOperationError
from tix.services.worktree import _clean_env, create_worktree, worktree_exists


class TestBranchNameValidation:
    """create_worktree must reject invalid branch names."""

    @pytest.mark.parametrize(
        "name",
        [
            "ticket-123",
            "feature/my-thing",
            "fix.hotfix",
            "release/2.0",
            "simple",
            "UPPER_case-123",
        ],
    )
    def test_valid_branch_names_pass(self, name: str, tmp_path: Path) -> None:
        """Valid names should not raise on the regex check.

        They will still fail at the git subprocess step, but the
        validation itself should pass.  We catch GitOperationError from
        the subprocess (not from validation).
        """
        with pytest.raises(GitOperationError, match="Failed to create worktree"):
            create_worktree(
                repo_path=tmp_path,
                worktree_dir=tmp_path / "wt",
                branch_name=name,
                base_branch="main",
            )

    @pytest.mark.parametrize(
        "name",
        [
            "has space",
            "semi;colon",
            "back`tick",
            "dollar$sign",
            "pipe|char",
            "new\nline",
            "",
        ],
    )
    def test_invalid_branch_names_raise(self, name: str, tmp_path: Path) -> None:
        with pytest.raises(GitOperationError, match="Invalid branch name"):
            create_worktree(
                repo_path=tmp_path,
                worktree_dir=tmp_path / "wt",
                branch_name=name,
                base_branch="main",
            )


class TestPathTraversal:
    """create_worktree must block path traversal attempts."""

    def test_path_traversal_detected(self, tmp_path: Path) -> None:
        with pytest.raises(GitOperationError, match="Path traversal detected"):
            create_worktree(
                repo_path=tmp_path,
                worktree_dir=tmp_path / "wt",
                branch_name="../../../etc/evil",
                base_branch="main",
            )


class TestCleanEnv:
    """_clean_env must strip ZENDESK_API_TOKEN."""

    def test_strips_zendesk_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ZENDESK_API_TOKEN", "secret-token")
        monkeypatch.setenv("HOME", "/home/test")
        env = _clean_env()
        assert "ZENDESK_API_TOKEN" not in env
        assert env["HOME"] == "/home/test"

    def test_works_when_token_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ZENDESK_API_TOKEN", raising=False)
        env = _clean_env()
        assert "ZENDESK_API_TOKEN" not in env


class TestWorktreeExists:
    """worktree_exists returns False for non-existent paths."""

    def test_nonexistent_path(self, tmp_path: Path) -> None:
        assert worktree_exists(tmp_path / "does-not-exist") is False

    def test_plain_directory_not_a_worktree(self, tmp_path: Path) -> None:
        plain_dir = tmp_path / "plain"
        plain_dir.mkdir()
        assert worktree_exists(plain_dir) is False
