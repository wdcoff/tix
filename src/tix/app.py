from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual import work

from tix.config import (
    Config,
    ConfigError,
    DEFAULT_CONFIG_PATH,
    create_default_config,
    load_config,
)
from tix.errors import GitOperationError, ExternalToolError, TixError
from tix.models import BoardState, GitContext, PRStatus
from tix.persistence import load_state
from tix.screens.board import BoardScreen
from tix.services.deploy_tracker import check_deploy, maybe_fetch_tags
from tix.services.pr_tracker import check_all_prs, is_gh_available
from tix.services.staleness import update_staleness
from tix.services.terminal_launcher import launch_terminal
from tix.services.worktree import create_worktree, worktree_exists
from tix.state_manager import StateManager
from tix.widgets.card import TicketCardWidget


class TixApp(App):
    """Zendesk investigation tracker TUI."""

    TITLE = "tix"
    CSS_PATH = "css/app.tcss"

    def __init__(self, config: Config | None = None) -> None:
        super().__init__()
        self.config = config
        self._has_config = config is not None
        self._custom_statuses_fetched = False
        self._gh_available = False
        self._zendesk_reachable = True

        # Initialize state manager (always, even without config)
        state = load_state()
        column_names = config.column_names if config else ["Triage", "Investigating", "Waiting", "In Review", "Done"]
        self.manager = StateManager(
            state=state,
            default_column=column_names[0] if column_names else "Triage",
        )
        self._column_names = column_names

        # Initialize Zendesk service (only if config is present)
        self._zendesk = None
        if config is not None:
            try:
                from tix.services.zendesk import ZendeskService
                self._zendesk = ZendeskService(
                    subdomain=config.zendesk_subdomain,
                    email=config.zendesk_email,
                    token=config.zendesk_token,
                )
            except Exception:
                pass

    def on_mount(self) -> None:
        board = BoardScreen(column_names=self._column_names)
        self.push_screen(board)

        if not self._has_config:
            self.notify(
                "No config found. Created template at ~/.config/tix/config.example.toml",
                severity="warning",
                timeout=8,
            )
        else:
            # Run startup validation
            self._validate_environment()

            self.trigger_sync()

            # Set up periodic sync
            if self.config is not None:
                self.set_interval(
                    self.config.sync_interval_seconds,
                    self.trigger_sync,
                )

    def _validate_environment(self) -> None:
        """Check that required external tools and paths exist."""
        assert self.config is not None

        # Check git repo exists
        repo = self.config.repo_path
        if not (repo / ".git").exists() and not repo.exists():
            self.notify(
                f"Git repo not found at {repo}",
                severity="warning",
                timeout=6,
            )

        # Check gh CLI
        self._gh_available = shutil.which("gh") is not None
        if not self._gh_available:
            self.notify(
                "gh CLI not found; PR and deploy features disabled",
                severity="warning",
                timeout=6,
            )

    def trigger_sync(self) -> None:
        """Public method to kick off a sync (called from screen and timer)."""
        if self._zendesk is not None:
            self._do_sync()

    @work(exclusive=True, thread=True, group="zendesk")
    def _do_sync(self) -> None:
        """Background sync: fetch from Zendesk and update state."""
        assert self._zendesk is not None

        try:
            tickets = self._zendesk.fetch_open_tickets()
            self._zendesk_reachable = True

            # Fetch custom statuses once
            custom_statuses = None
            if not self._custom_statuses_fetched:
                custom_statuses = self._zendesk.fetch_custom_statuses()
                self._custom_statuses_fetched = True

            self.manager.apply_sync(tickets, custom_statuses)
            self.manager.archive_closed_tickets()

            # --- Staleness update ---
            staleness_rules = (
                self.config.staleness_rules if self.config else []
            )
            for ticket in self.manager.state.tickets:
                update_staleness(ticket, staleness_rules)

            # --- PR detection (only if gh is available) ---
            if self._gh_available:
                branch_names = [
                    ticket.git.branch_name
                    for ticket in self.manager.state.tickets
                    if ticket.git.branch_name
                ]
                if branch_names:
                    pr_map = check_all_prs(branch_names)
                    for ticket in self.manager.state.tickets:
                        bn = ticket.git.branch_name
                        if bn and bn in pr_map:
                            ticket.pr = pr_map[bn]

                    # --- Deploy detection for merged PRs ---
                    merged_tickets = [
                        t for t in self.manager.state.tickets
                        if t.pr.status == PRStatus.MERGED
                        and t.pr.merge_sha
                        and not t.deployed_in_tag
                    ]
                    if merged_tickets and self.config:
                        maybe_fetch_tags(self.config.repo_path)
                        for ticket in merged_tickets:
                            assert ticket.pr.merge_sha is not None
                            tag = check_deploy(
                                self.config.repo_path, ticket.pr.merge_sha
                            )
                            if tag:
                                ticket.deployed_in_tag = tag

            self.manager.save()

            count = len(self.manager.state.tickets)

            self.call_from_thread(self._post_sync_refresh, count, None)

        except TixError as exc:
            self._zendesk_reachable = False
            error_msg = str(exc)
            if self.manager.state.tickets:
                error_msg += " (showing cached data)"
            self.call_from_thread(self._post_sync_refresh, len(self.manager.state.tickets), error_msg)

    def _post_sync_refresh(self, count: int, error: str | None) -> None:
        """Refresh UI after sync (must be called from main thread)."""
        screen = self.screen
        if isinstance(screen, BoardScreen):
            screen.refresh_board()
            screen.status_bar.update_sync(count, error)
        if error:
            self.notify(f"Sync error: {error}", severity="error", timeout=5)

    # ------------------------------------------------------------------
    # Card selection
    # ------------------------------------------------------------------

    def on_ticket_card_widget_card_selected(
        self, event: TicketCardWidget.CardSelected
    ) -> None:
        if self.config is None:
            self.notify("No config — cannot open ticket", severity="warning")
            return
        self._open_ticket(event.ticket_id)

    @work(exclusive=False, thread=True, group="open-ticket")
    def _open_ticket(self, ticket_id: int) -> None:
        """Create worktree if needed and launch a terminal session."""
        assert self.config is not None

        # Find the ticket
        ticket = None
        for t in self.manager.state.tickets:
            if t.ticket_id == ticket_id:
                ticket = t
                break
        if ticket is None:
            self.call_from_thread(
                self.notify, f"Ticket #{ticket_id} not found", severity="error"
            )
            return

        branch_name = f"ticket-{ticket_id}"
        worktree_path = ticket.git.worktree_path

        # Create worktree if needed
        try:
            if worktree_path is None or not worktree_exists(worktree_path):
                worktree_path = create_worktree(
                    repo_path=self.config.repo_path,
                    worktree_dir=self.config.worktree_dir,
                    branch_name=branch_name,
                    base_branch=self.config.base_branch,
                )
                ticket.git = GitContext(
                    worktree_path=worktree_path,
                    branch_name=branch_name,
                )
                self.manager.save()
        except GitOperationError as exc:
            self.call_from_thread(
                self.notify, f"Git error: {exc}", severity="error"
            )
            return

        assert worktree_path is not None

        # Launch terminal
        terminal_name = self.config.terminal
        try:
            launch_terminal(
                cwd=worktree_path,
                command=self.config.claude_launch_command,
                ticket_id=ticket_id,
                terminal_override=terminal_name,
            )
        except ExternalToolError as exc:
            self.call_from_thread(
                self.notify, f"Terminal error: {exc}", severity="error"
            )
            return

        display_terminal = terminal_name or "terminal"
        self.call_from_thread(
            self._post_open_refresh, ticket_id, display_terminal
        )

    def _post_open_refresh(self, ticket_id: int, terminal: str) -> None:
        """Refresh board and notify after opening a ticket."""
        screen = self.screen
        if isinstance(screen, BoardScreen):
            screen.refresh_board()
        self.notify(f"Opened ticket #{ticket_id} in {terminal}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_unmount(self) -> None:
        """Save state and close services on shutdown."""
        if self.manager is not None:
            try:
                self.manager.save()
            except Exception:
                pass
        if self._zendesk is not None:
            try:
                self._zendesk.close()
            except Exception:
                pass


def main() -> None:
    """Entry point for the tix command."""
    config: Config | None = None
    try:
        config = load_config()
    except ConfigError:
        # Create example config so user has a template
        created = create_default_config()
        # Also create the actual config.toml if it doesn't exist
        if not DEFAULT_CONFIG_PATH.exists():
            example = created
            if example.exists():
                DEFAULT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
                DEFAULT_CONFIG_PATH.write_text(example.read_text())

    try:
        app = TixApp(config)
        app.run()
    except KeyboardInterrupt:
        # Graceful exit on Ctrl+C
        pass


if __name__ == "__main__":
    main()
