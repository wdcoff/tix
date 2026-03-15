"""Tests for tix.services.deploy_tracker — SHA validation."""
from __future__ import annotations

from pathlib import Path

import pytest

from tix.errors import GitOperationError
from tix.services.deploy_tracker import DeployTracker


class TestMergeShaValidation:
    """check_deploy must validate merge_sha format."""

    def setup_method(self) -> None:
        self.tracker = DeployTracker()

    @pytest.mark.parametrize(
        "sha",
        [
            "abc1234",               # 7 chars, valid
            "abc1234567890def",       # 16 chars, valid
            "a" * 40,                # full 40-char SHA
        ],
    )
    def test_valid_sha_passes_validation(self, sha: str, tmp_path: Path) -> None:
        """Valid SHAs pass validation (git command will fail, but no ValueError)."""
        # Should not raise GitOperationError about invalid SHA
        # (will return None because git subprocess fails in tmp_path)
        result = self.tracker.check_deploy(tmp_path, sha)
        assert result is None

    @pytest.mark.parametrize(
        "sha",
        [
            "--option-injection",
            "abc123; rm -rf /",
            "ABCDEF1234567890",      # uppercase not valid hex
            "abc12",                  # too short (< 7)
            "xyz1234",               # non-hex chars
            "abc1234\n",             # newline
            "../../../etc/passwd",
        ],
    )
    def test_invalid_sha_raises(self, sha: str, tmp_path: Path) -> None:
        with pytest.raises(GitOperationError, match="Invalid merge SHA"):
            self.tracker.check_deploy(tmp_path, sha)

    def test_empty_sha_returns_none(self, tmp_path: Path) -> None:
        """Empty string should return None without raising."""
        assert self.tracker.check_deploy(tmp_path, "") is None
