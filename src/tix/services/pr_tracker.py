"""Batched PR detection via gh CLI.

One subprocess call fetches all PRs; matching against branch names
happens in Python.  When gh is not installed or not authenticated the
module degrades gracefully by returning empty results.
"""
from __future__ import annotations

import json
import logging
import subprocess

from tix.models import PRContext, PRStatus
from tix.subprocess_utils import clean_env

logger = logging.getLogger(__name__)


def check_all_prs(branch_names: list[str]) -> dict[str, PRContext]:
    """Check PR status for multiple branches in a single gh CLI call.

    Returns ``{branch_name: PRContext}`` for branches that have PRs.
    Returns an empty dict if *gh* is not installed or not authenticated.
    """
    if not branch_names:
        return {}

    result = subprocess.run(
        [
            "gh", "pr", "list", "--state", "all", "--json",
            "headRefName,url,state,mergeCommit", "--limit", "200",
        ],
        capture_output=True,
        text=True,
        env=clean_env(),
    )
    if result.returncode != 0:
        logger.warning("gh CLI not available or not authenticated; PR check skipped")
        return {}  # gh not installed or not authed -- degrade gracefully

    try:
        prs = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}

    branch_set = set(branch_names)
    result_map: dict[str, PRContext] = {}

    for pr in prs:
        head = pr.get("headRefName", "")
        if head in branch_set:
            state = pr.get("state", "").upper()
            # gh returns OPEN, CLOSED, MERGED
            status_map = {
                "OPEN": PRStatus.OPEN,
                "CLOSED": PRStatus.CLOSED,
                "MERGED": PRStatus.MERGED,
            }
            pr_status = status_map.get(state, PRStatus.OPEN)

            merge_commit = pr.get("mergeCommit")
            merge_sha = (
                merge_commit.get("oid")
                if isinstance(merge_commit, dict)
                else None
            )

            result_map[head] = PRContext(
                url=pr.get("url"),
                status=pr_status,
                merge_sha=merge_sha,
            )

    logger.info("PR check complete: %d PRs matched out of %d branches", len(result_map), len(branch_names))
    return result_map


def is_gh_available() -> bool:
    """Check if gh CLI is installed and authenticated."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            env=clean_env(),
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False
