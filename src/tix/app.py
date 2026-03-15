from __future__ import annotations

import logging
import shutil
from pathlib import Path

from textual.app import App
from textual import work

from tix.config import (
    Config,
    ConfigError,
    DEFAULT_CONFIG_PATH,
    create_default_config,
    load_config,
)
from tix.errors import GitOperationError, ExternalToolError
from tix.models import GitContext
from tix.persistence import load_state
from tix.screens.board import BoardScreen
from tix.services.deploy_tracker import DeployTracker
from tix.services.terminal_launcher import launch_terminal
from tix.services.worktree import create_worktree, worktree_exists
from tix.state_manager import StateManager
from tix.sync import SyncCoordinator
from tix.widgets.card import TicketCardWidget

LOG_PATH = Path("~/.config/tix/tix.log").expanduser()


def _setup_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(LOG_PATH),
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


class TixApp(App):
    """Zendesk investigation tracker TUI."""

    TITLE = "tix"
    CSS_PATH = "css/app.tcss"

    def __init__(self, config: Config | None = None) -> None:
        super().__init__()
        self.config = config
        self._has_config = config is not None
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

        # Initialize Zendesk service and sync coordinator (only if config is present)
        self._zendesk = None
        self._sync_coordinator: SyncCoordinator | None = None
        self._init_error: str | None = None
        if config is not None:
            try:
                from tix.services.zendesk import ZendeskService
                self._zendesk = ZendeskService(
                    subdomain=config.zendesk_subdomain,
                    email=config.zendesk_email,
                    token=config.zendesk_token,
                )
                self._deploy_tracker = DeployTracker()
            except Exception as e:
                self._zendesk = None
                # Will be surfaced as a warning after mount
                self._init_error = str(e)

    def on_mount(self) -> None:
        board = BoardScreen(column_names=self._column_names)
        self.push_screen(board)

        if self._init_error is not None:
            self.notify(
                f"Zendesk init failed: {self._init_error}",
                severity="warning",
                timeout=8,
            )

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
        if self.config is None:
            return

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

        # Build the sync coordinator now that gh_available is known
        if self._zendesk is not None:
            self._sync_coordinator = SyncCoordinator(
                zendesk_service=self._zendesk,
                state_manager=self.manager,
                deploy_tracker=self._deploy_tracker,
                config=self.config,
                gh_available=self._gh_available,
            )

    def trigger_sync(self) -> None:
        """Public method to kick off a sync (called from screen and timer)."""
        if self._sync_coordinator is not None:
            self._do_sync()

    @work(exclusive=True, thread=True, group="zendesk")
    def _do_sync(self) -> None:
        """Background sync: delegate to SyncCoordinator and refresh UI."""
        if self._sync_coordinator is None:
            return

        count, error = self._sync_coordinator.run_sync()

        if error is None:
            self._zendesk_reachable = True
        else:
            self._zendesk_reachable = False

        self.call_from_thread(self._post_sync_refresh, count, error)

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
            self.notify("No config -- cannot open ticket", severity="warning")
            return
        self._open_ticket(event.ticket_id)

    @work(exclusive=False, thread=True, group="open-ticket")
    def _open_ticket(self, ticket_id: int) -> None:
        """Create worktree if needed and launch a terminal session."""
        if self.config is None:
            return

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

        if worktree_path is None:
            self.call_from_thread(
                self.notify, "Worktree path is unexpectedly None", severity="error"
            )
            return

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
    _setup_logging()
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
