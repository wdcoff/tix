"""Tests for tix.services.pr_tracker."""
from __future__ import annotations

import json
import subprocess
from unittest import mock

from tix.models import PRContext, PRStatus
from tix.services.pr_tracker import check_all_prs


def _make_completed_process(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=""
    )


class TestCheckAllPrs:
    """Tests for check_all_prs()."""

    def test_empty_branch_list_returns_empty(self) -> None:
        result = check_all_prs([])
        assert result == {}

    @mock.patch("tix.services.pr_tracker.subprocess.run")
    def test_gh_not_installed_returns_empty(self, mock_run: mock.Mock) -> None:
        mock_run.return_value = _make_completed_process(returncode=1)
        result = check_all_prs(["feature-branch"])
        assert result == {}

    @mock.patch("tix.services.pr_tracker.subprocess.run")
    def test_malformed_json_returns_empty(self, mock_run: mock.Mock) -> None:
        mock_run.return_value = _make_completed_process(stdout="not json at all")
        result = check_all_prs(["feature-branch"])
        assert result == {}

    @mock.patch("tix.services.pr_tracker.subprocess.run")
    def test_parses_open_pr(self, mock_run: mock.Mock) -> None:
        prs = [
            {
                "headRefName": "ticket-100",
                "url": "https://github.com/org/repo/pull/1",
                "state": "OPEN",
                "mergeCommit": None,
            }
        ]
        mock_run.return_value = _make_completed_process(stdout=json.dumps(prs))

        result = check_all_prs(["ticket-100", "ticket-200"])

        assert "ticket-100" in result
        assert result["ticket-100"].status == PRStatus.OPEN
        assert result["ticket-100"].url == "https://github.com/org/repo/pull/1"
        assert result["ticket-100"].merge_sha is None
        assert "ticket-200" not in result

    @mock.patch("tix.services.pr_tracker.subprocess.run")
    def test_parses_merged_pr_with_sha(self, mock_run: mock.Mock) -> None:
        prs = [
            {
                "headRefName": "ticket-42",
                "url": "https://github.com/org/repo/pull/7",
                "state": "MERGED",
                "mergeCommit": {"oid": "abc123def456"},
            }
        ]
        mock_run.return_value = _make_completed_process(stdout=json.dumps(prs))

        result = check_all_prs(["ticket-42"])

        assert result["ticket-42"].status == PRStatus.MERGED
        assert result["ticket-42"].merge_sha == "abc123def456"

    @mock.patch("tix.services.pr_tracker.subprocess.run")
    def test_parses_closed_pr(self, mock_run: mock.Mock) -> None:
        prs = [
            {
                "headRefName": "ticket-99",
                "url": "https://github.com/org/repo/pull/5",
                "state": "CLOSED",
                "mergeCommit": None,
            }
        ]
        mock_run.return_value = _make_completed_process(stdout=json.dumps(prs))

        result = check_all_prs(["ticket-99"])

        assert result["ticket-99"].status == PRStatus.CLOSED

    @mock.patch("tix.services.pr_tracker.subprocess.run")
    def test_unknown_state_defaults_to_open(self, mock_run: mock.Mock) -> None:
        prs = [
            {
                "headRefName": "ticket-50",
                "url": "https://github.com/org/repo/pull/3",
                "state": "UNKNOWN",
                "mergeCommit": None,
            }
        ]
        mock_run.return_value = _make_completed_process(stdout=json.dumps(prs))

        result = check_all_prs(["ticket-50"])

        assert result["ticket-50"].status == PRStatus.OPEN

    @mock.patch("tix.services.pr_tracker.subprocess.run")
    def test_branches_not_in_prs_are_absent(self, mock_run: mock.Mock) -> None:
        prs = [
            {
                "headRefName": "other-branch",
                "url": "https://github.com/org/repo/pull/1",
                "state": "OPEN",
                "mergeCommit": None,
            }
        ]
        mock_run.return_value = _make_completed_process(stdout=json.dumps(prs))

        result = check_all_prs(["ticket-100"])

        assert result == {}
