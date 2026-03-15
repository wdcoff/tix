"""Terminal tab launcher with auto-detection.

Detects the running terminal via ``$TERM_PROGRAM`` and dispatches to the
appropriate launch mechanism.  All subprocess calls use ``shell=False`` and
strip ``ZENDESK_API_TOKEN`` from the child environment.
"""
from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

from tix.errors import ExternalToolError


def _escape_applescript(s: str) -> str:
    """Escape a string for safe embedding in AppleScript double-quoted strings."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _escape_yaml_value(s: str) -> str:
    """Escape a string for safe embedding in YAML values.

    If the value contains any special characters, wrap it in single quotes
    and escape embedded single quotes by doubling them.
    """
    if any(c in s for c in '"\'\\:#{}[]|>&*!%@`'):
        return "'" + s.replace("'", "''") + "'"
    return s


_TERM_PROGRAM_MAP: dict[str, str] = {
    "WarpTerminal": "warp",
    "iTerm.app": "iterm",
    "Apple_Terminal": "terminal",
    "kitty": "kitty",
}


def _clean_env() -> dict[str, str]:
    """Return environment with sensitive vars stripped."""
    return {k: v for k, v in os.environ.items() if k != "ZENDESK_API_TOKEN"}


def _detect_terminal() -> str:
    """Return a normalised terminal name based on ``$TERM_PROGRAM``."""
    term_program = os.environ.get("TERM_PROGRAM", "")
    return _TERM_PROGRAM_MAP.get(term_program, "default")


def launch_terminal(
    cwd: Path,
    command: str,
    ticket_id: int,
    terminal_override: str | None = None,
) -> None:
    """Open a new terminal tab/window running *command* in *cwd*.

    Parameters
    ----------
    cwd:
        Working directory for the new terminal session.
    command:
        Shell command to execute (e.g. ``claude --remote-control``).
    ticket_id:
        Ticket identifier, used for naming tabs/configs.
    terminal_override:
        If given, skip auto-detection and use this terminal name directly.
        Accepted values: ``warp``, ``iterm``, ``terminal``, ``kitty``.
    """
    terminal = terminal_override or _detect_terminal()

    launchers = {
        "warp": _launch_warp,
        "iterm": _launch_iterm,
        "terminal": _launch_terminal_app,
        "kitty": _launch_kitty,
    }

    launcher = launchers.get(terminal, _launch_default)
    launcher(cwd, command, ticket_id)


# ------------------------------------------------------------------
# Per-terminal launchers
# ------------------------------------------------------------------


def _launch_warp(cwd: Path, command: str, ticket_id: int) -> None:
    """Launch via Warp launch configuration + URI scheme."""
    config_dir = Path.home() / ".warp" / "launch_configurations"
    config_dir.mkdir(parents=True, exist_ok=True)

    config_name = f"tix-{ticket_id}"
    config_path = config_dir / f"{config_name}.yaml"

    # Warp launch configs require absolute paths (no ~)
    abs_cwd = str(cwd.resolve())
    safe_cwd = _escape_yaml_value(abs_cwd)
    safe_command = _escape_yaml_value(command)
    yaml_content = textwrap.dedent(f"""\
        ---
        name: "{config_name}"
        windows:
          - tabs:
              - title: "tix #{ticket_id}"
                layout:
                  cwd: {safe_cwd}
                  command: {safe_command}
    """)
    config_path.write_text(yaml_content)

    result = subprocess.run(
        ["open", f"warp://launch/{config_name}"],
        capture_output=True,
        text=True,
        env=_clean_env(),
    )
    if result.returncode != 0:
        raise ExternalToolError(
            f"Failed to launch Warp: {result.stderr.strip()}"
        )


def _launch_iterm(cwd: Path, command: str, ticket_id: int) -> None:
    """Launch via iTerm2 AppleScript."""
    abs_cwd = str(cwd.resolve())
    safe_cwd = _escape_applescript(abs_cwd)
    safe_command = _escape_applescript(command)
    script = textwrap.dedent(f"""\
        tell application "iTerm"
            activate
            tell current window
                create tab with default profile
                tell current session
                    write text "cd {safe_cwd} && {safe_command}"
                end tell
            end tell
        end tell
    """)
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        env=_clean_env(),
    )
    if result.returncode != 0:
        raise ExternalToolError(
            f"Failed to launch iTerm: {result.stderr.strip()}"
        )


def _launch_terminal_app(cwd: Path, command: str, ticket_id: int) -> None:
    """Launch via Terminal.app AppleScript."""
    abs_cwd = str(cwd.resolve())
    safe_cwd = _escape_applescript(abs_cwd)
    safe_command = _escape_applescript(command)
    script = textwrap.dedent(f"""\
        tell application "Terminal"
            activate
            do script "cd {safe_cwd} && {safe_command}"
        end tell
    """)
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        env=_clean_env(),
    )
    if result.returncode != 0:
        raise ExternalToolError(
            f"Failed to launch Terminal.app: {result.stderr.strip()}"
        )


def _launch_kitty(cwd: Path, command: str, ticket_id: int) -> None:
    """Launch via kitty remote control."""
    abs_cwd = str(cwd.resolve())
    result = subprocess.run(
        [
            "kitty", "@", "launch",
            "--type=tab",
            f"--tab-title=tix #{ticket_id}",
            f"--cwd={abs_cwd}",
            "sh", "-c", command,
        ],
        capture_output=True,
        text=True,
        env=_clean_env(),
    )
    if result.returncode != 0:
        raise ExternalToolError(
            f"Failed to launch kitty tab: {result.stderr.strip()}"
        )


def _launch_default(cwd: Path, command: str, ticket_id: int) -> None:
    """Fallback: open default Terminal.app window."""
    _launch_terminal_app(cwd, command, ticket_id)
