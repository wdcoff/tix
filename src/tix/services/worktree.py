"""Git worktree operations as plain functions.

All subprocess calls use shell=False and strip sensitive environment
variables from the child process environment.
"""
from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

from tix.errors import GitOperationError
from tix.subprocess_utils import clean_env

logger = logging.getLogger(__name__)


def create_worktree(
    repo_path: Path,
    worktree_dir: Path,
    branch_name: str,
    base_branch: str,
) -> Path:
    """Create a git worktree. Returns the worktree path.

    If the branch already exists, reuses it (no ``-b`` flag).
    """
    # Validate branch name
    if not re.match(r"^[a-zA-Z0-9._/-]+$", branch_name):
        raise GitOperationError(f"Invalid branch name: {branch_name}")

    # Validate base_branch with the same rules
    if not re.match(r"^[a-zA-Z0-9._/-]+$", base_branch):
        raise GitOperationError(f"Invalid base branch name: {base_branch}")

    worktree_path = worktree_dir / branch_name

    # Validate no path traversal
    if not worktree_path.resolve().is_relative_to(worktree_dir.resolve()):
        raise GitOperationError(f"Path traversal detected: {worktree_path}")

    # Ensure worktree_dir exists
    worktree_dir.mkdir(parents=True, exist_ok=True)

    # Try with -b first (new branch), fall back to without (existing branch)
    result = subprocess.run(
        [
            "git", "-C", str(repo_path),
            "worktree", "add", "-b", branch_name,
            "--", str(worktree_path), base_branch,
        ],
        capture_output=True,
        text=True,
        env=clean_env(),
    )
    if result.returncode != 0:
        # Branch might already exist, try without -b
        result = subprocess.run(
            [
                "git", "-C", str(repo_path),
                "worktree", "add",
                "--", str(worktree_path), branch_name,
            ],
            capture_output=True,
            text=True,
            env=clean_env(),
        )
        if result.returncode != 0:
            logger.error("Failed to create worktree for branch %s: %s", branch_name, result.stderr.strip())
            raise GitOperationError(
                f"Failed to create worktree: {result.stderr.strip()}"
            )

    logger.info("Created worktree for branch %s at %s", branch_name, worktree_path)
    return worktree_path


def worktree_exists(path: Path) -> bool:
    """Check if a path is a valid git worktree."""
    if not path.is_dir():
        return False
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        env=clean_env(),
    )
    return result.returncode == 0


def remove_worktree(repo_path: Path, worktree_path: Path) -> None:
    """Remove a git worktree."""
    result = subprocess.run(
        [
            "git", "-C", str(repo_path),
            "worktree", "remove", "--", str(worktree_path),
        ],
        capture_output=True,
        text=True,
        env=clean_env(),
    )
    if result.returncode != 0:
        raise GitOperationError(
            f"Failed to remove worktree: {result.stderr.strip()}"
        )


def list_worktrees(repo_path: Path) -> list[dict[str, str]]:
    """List all worktrees for a repo.

    Returns a list of dicts with keys ``path``, ``branch``, and ``commit``.
    """
    result = subprocess.run(
        ["git", "-C", str(repo_path), "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
        env=clean_env(),
    )
    if result.returncode != 0:
        return []

    worktrees: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in result.stdout.split("\n"):
        if line.startswith("worktree "):
            if current:
                worktrees.append(current)
            current = {"path": line[9:]}
        elif line.startswith("HEAD "):
            current["commit"] = line[5:]
        elif line.startswith("branch "):
            current["branch"] = line[7:].replace("refs/heads/", "")
    if current:
        worktrees.append(current)

    return worktrees
