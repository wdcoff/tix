from __future__ import annotations

import os
import re
import stat
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tix.errors import TixError

DEFAULT_CONFIG_DIR = Path("~/.config/tix").expanduser()
DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_DIR / "config.toml"

DEFAULT_COLUMNS = ["Triage", "Investigating", "Waiting", "In Review", "Done"]

DEFAULT_STALENESS_RULES = [
    {"local": "Needs Notify", "ok_zendesk": ["solved", "pending"]},
    {"local": "Awaiting Close", "ok_zendesk": ["solved", "closed"]},
    {"local": "PR Submitted", "ok_zendesk": ["pending", "hold"]},
]

_SUBDOMAIN_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9-]*$")


class ConfigError(TixError):
    """Configuration is missing or invalid."""


@dataclass
class Config:
    zendesk_subdomain: str
    zendesk_email: str
    zendesk_token: str
    repo_path: Path
    worktree_dir: Path
    zendesk_group: str | None = None
    base_branch: str = "main"
    sync_interval_seconds: int = 300
    terminal: str | None = None
    claude_launch_command: str = "cld -r"
    column_names: list[str] = field(default_factory=lambda: list(DEFAULT_COLUMNS))
    staleness_rules: list[dict[str, Any]] = field(default_factory=lambda: list(DEFAULT_STALENESS_RULES))
    warn_after_hours: int = 24


def load_config(path: Path | None = None) -> Config:
    """Load and validate configuration from a TOML file.

    The Zendesk API token is always read from the ZENDESK_API_TOKEN
    environment variable, never from the config file.
    """
    config_path = path or DEFAULT_CONFIG_PATH

    if not config_path.exists():
        raise ConfigError(
            f"Config file not found at {config_path}. "
            f"Run 'tix' once to generate a template at ~/.config/tix/config.example.toml"
        )

    # Warn if config file is readable by group or others
    mode = config_path.stat().st_mode
    if mode & (stat.S_IRGRP | stat.S_IROTH):
        print(
            f"WARNING: {config_path} is readable by group/others "
            f"(mode {oct(mode & 0o777)}). Consider running: "
            f"chmod 600 {config_path}"
        )

    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    zendesk = raw.get("zendesk", {})
    subdomain = zendesk.get("subdomain", "")
    if not _SUBDOMAIN_RE.match(subdomain):
        raise ConfigError(
            f"Invalid zendesk.subdomain: {subdomain!r}. "
            "Must match ^[a-zA-Z0-9][a-zA-Z0-9-]*$"
        )

    email = zendesk.get("email", "")
    if not email:
        raise ConfigError("zendesk.email is required in config file")

    group = zendesk.get("group") or None

    token = os.environ.get("ZENDESK_API_TOKEN", "")
    if not token:
        raise ConfigError(
            "ZENDESK_API_TOKEN environment variable is not set. "
            "Export your Zendesk API token before running tix."
        )

    git = raw.get("git", {})
    repo_path_str = git.get("repo_path", "")
    if not repo_path_str:
        raise ConfigError("git.repo_path is required in config file")
    repo_path = Path(repo_path_str).expanduser().resolve()

    worktree_dir_str = git.get("worktree_dir", "")
    if worktree_dir_str:
        worktree_dir = Path(worktree_dir_str).expanduser().resolve()
    else:
        worktree_dir = repo_path / ".worktrees"

    base_branch = git.get("base_branch", "main")

    app = raw.get("app", {})
    sync_interval = app.get("sync_interval_seconds", 300)
    terminal = app.get("terminal") or None
    claude_cmd = app.get(
        "claude_launch_command",
        "cld -r",
    )

    board = raw.get("board", {})
    column_names = board.get("columns", list(DEFAULT_COLUMNS))
    warn_after_hours = board.get("warn_after_hours", 24)

    staleness_raw = board.get("staleness_rules", None)
    if staleness_raw is not None:
        staleness_rules = [
            {"local": r["local"], "ok_zendesk": list(r["ok_zendesk"])}
            for r in staleness_raw
        ]
    else:
        staleness_rules = list(DEFAULT_STALENESS_RULES)

    return Config(
        zendesk_subdomain=subdomain,
        zendesk_email=email,
        zendesk_token=token,
        zendesk_group=group,
        repo_path=repo_path,
        worktree_dir=worktree_dir,
        base_branch=base_branch,
        sync_interval_seconds=sync_interval,
        terminal=terminal,
        claude_launch_command=claude_cmd,
        column_names=column_names,
        staleness_rules=staleness_rules,
        warn_after_hours=warn_after_hours,
    )


def create_default_config(target: Path | None = None) -> Path:
    """Write a documented example config file if none exists.

    Returns the path to the created (or already-existing) file.
    """
    dest = target or (DEFAULT_CONFIG_DIR / "config.example.toml")
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        return dest

    content = """\
# tix configuration
# Copy this file to ~/.config/tix/config.toml and edit as needed.
# The Zendesk API token must be set via the ZENDESK_API_TOKEN env var.

[zendesk]
# Your Zendesk subdomain (e.g. "mycompany" for mycompany.zendesk.com)
subdomain = "mycompany"
# The email address associated with your Zendesk account
email = "you@example.com"

[git]
# Path to your local repo checkout
repo_path = "~/src/myproject"
# Directory where git worktrees will be created (default: <repo_path>/.worktrees)
# worktree_dir = "~/src/myproject/.worktrees"
# Base branch for new worktrees (default: "main")
# base_branch = "main"

[app]
# How often to poll Zendesk for updates, in seconds (default: 300)
# sync_interval_seconds = 300
# Terminal emulator to launch for Claude sessions (default: auto-detect)
# terminal = "iTerm"
# Command used to launch Claude in a worktree (default shown below)
# claude_launch_command = "cld -r"

[board]
# Kanban column names, in display order
# columns = ["Triage", "Investigating", "Waiting", "In Review", "Done"]
# Hours before a stale mismatch triggers a warning (default: 24)
# warn_after_hours = 24
# Staleness rules: local column + acceptable Zendesk statuses
# [[board.staleness_rules]]
# local = "Needs Notify"
# ok_zendesk = ["solved", "pending"]
# [[board.staleness_rules]]
# local = "Awaiting Close"
# ok_zendesk = ["solved", "closed"]
# [[board.staleness_rules]]
# local = "PR Submitted"
# ok_zendesk = ["pending", "hold"]
"""
    fd = os.open(str(dest), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(content)
    return dest
