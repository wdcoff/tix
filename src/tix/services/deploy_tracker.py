"""Deploy detection via git tags.

After a PR is merged, this module checks whether the merge commit
appears in any release tag, indicating that the fix has been deployed.
Tag fetching is throttled to avoid hammering the remote.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

from tix.services.worktree import _clean_env

_last_tag_fetch: float = 0
TAG_FETCH_INTERVAL = 900  # 15 minutes


def maybe_fetch_tags(repo_path: Path) -> None:
    """Fetch tags from remote, throttled to every 15 minutes."""
    global _last_tag_fetch
    now = time.monotonic()
    if now - _last_tag_fetch > TAG_FETCH_INTERVAL:
        subprocess.run(
            ["git", "-C", str(repo_path), "fetch", "--tags", "--quiet"],
            capture_output=True,
            text=True,
            env=_clean_env(),
        )
        _last_tag_fetch = now


def check_deploy(repo_path: Path, merge_sha: str) -> str | None:
    """Check if a merge SHA is included in any release tag.

    Returns the newest tag containing the SHA, or ``None``.
    """
    if not merge_sha:
        return None

    result = subprocess.run(
        [
            "git", "-C", str(repo_path),
            "tag", "--contains", merge_sha, "--sort=-creatordate",
        ],
        capture_output=True,
        text=True,
        env=_clean_env(),
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None

    # Return the first (newest) tag
    return result.stdout.strip().split("\n")[0]
