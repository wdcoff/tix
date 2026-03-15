"""Deploy detection via git tags.

After a PR is merged, this module checks whether the merge commit
appears in any release tag, indicating that the fix has been deployed.
Tag fetching is throttled to avoid hammering the remote.
"""
from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

from tix.errors import GitOperationError
from tix.subprocess_utils import clean_env

_SHA_RE = re.compile(r"^[0-9a-f]{7,40}\Z")

TAG_FETCH_INTERVAL = 900  # 15 minutes


class DeployTracker:
    """Tracks whether merged PRs have been deployed via git tags.

    Encapsulates the mutable fetch-throttle state that was previously
    stored in a module-level global.
    """

    def __init__(self, fetch_interval: int = TAG_FETCH_INTERVAL) -> None:
        self._last_tag_fetch: float = 0
        self._fetch_interval = fetch_interval

    def maybe_fetch_tags(self, repo_path: Path) -> None:
        """Fetch tags from remote, throttled to *fetch_interval* seconds."""
        now = time.monotonic()
        if now - self._last_tag_fetch > self._fetch_interval:
            subprocess.run(
                ["git", "-C", str(repo_path), "fetch", "--tags", "--quiet"],
                capture_output=True,
                text=True,
                env=clean_env(),
            )
            self._last_tag_fetch = now

    def check_deploy(self, repo_path: Path, merge_sha: str) -> str | None:
        """Check if a merge SHA is included in any release tag.

        Returns the newest tag containing the SHA, or ``None``.
        """
        if not merge_sha:
            return None

        if not _SHA_RE.match(merge_sha):
            raise GitOperationError(f"Invalid merge SHA: {merge_sha!r}")

        result = subprocess.run(
            [
                "git", "-C", str(repo_path),
                "tag", "--contains", "--sort=-creatordate",
                "--", merge_sha,
            ],
            capture_output=True,
            text=True,
            env=clean_env(),
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        # Return the first (newest) tag
        return result.stdout.strip().split("\n")[0]
