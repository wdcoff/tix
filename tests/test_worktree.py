"""Tests for tix.services.worktree — validation logic only.

Does NOT test actual git operations (would need a real repo).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from tix.errors import GitOperationError
from tix.services.worktree import create_worktree, worktree_exists
from tix.subprocess_utils import clean_env


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


class TestBaseBranchValidation:
    """create_worktree must reject invalid base branch names."""

    @pytest.mark.parametrize(
        "base",
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
    def test_invalid_base_branch_raises(self, base: str, tmp_path: Path) -> None:
        with pytest.raises(GitOperationError, match="Invalid base branch name"):
            create_worktree(
                repo_path=tmp_path,
                worktree_dir=tmp_path / "wt",
                branch_name="valid-branch",
                base_branch=base,
            )

    @pytest.mark.parametrize(
        "base",
        ["main", "develop", "release/1.0", "my.branch"],
    )
    def test_valid_base_branch_passes_validation(self, base: str, tmp_path: Path) -> None:
        """Valid base branches pass validation but fail at git subprocess."""
        with pytest.raises(GitOperationError, match="Failed to create worktree"):
            create_worktree(
                repo_path=tmp_path,
                worktree_dir=tmp_path / "wt",
                branch_name="valid-branch",
                base_branch=base,
            )


class TestCleanEnv:
    """clean_env must strip sensitive environment variables."""

    def test_strips_zendesk_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ZENDESK_API_TOKEN", "secret-token")
        monkeypatch.setenv("HOME", "/home/test")
        env = clean_env()
        assert "ZENDESK_API_TOKEN" not in env
        assert env["HOME"] == "/home/test"

    def test_works_when_token_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ZENDESK_API_TOKEN", raising=False)
        env = clean_env()
        assert "ZENDESK_API_TOKEN" not in env

    @pytest.mark.parametrize(
        "var_name",
        [
            "ZENDESK_API_TOKEN",
            "AWS_SECRET_ACCESS_KEY",
            "GITHUB_TOKEN",
            "DB_PASSWORD",
            "MY_SECRET_VALUE",
            "SSH_KEY",
            "SERVICE_CREDENTIAL",
            "some_token_here",
            "my_password_var",
        ],
    )
    def test_strips_secret_patterns(self, var_name: str, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(var_name, "sensitive-value")
        env = clean_env()
        assert var_name not in env

    @pytest.mark.parametrize(
        "var_name",
        [
            "HOME",
            "PATH",
            "SHELL",
            "TERM",
            "LANG",
            "USER",
            "EDITOR",
        ],
    )
    def test_preserves_safe_vars(self, var_name: str, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(var_name, "safe-value")
        env = clean_env()
        assert env[var_name] == "safe-value"


class TestWorktreeExists:
    """worktree_exists returns False for non-existent paths."""

    def test_nonexistent_path(self, tmp_path: Path) -> None:
        assert worktree_exists(tmp_path / "does-not-exist") is False

    def test_plain_directory_not_a_worktree(self, tmp_path: Path) -> None:
        plain_dir = tmp_path / "plain"
        plain_dir.mkdir()
        assert worktree_exists(plain_dir) is False
