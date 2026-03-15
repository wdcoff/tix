from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual import work

from tix.config import Config, ConfigError, create_default_config, load_config
from tix.errors import TixError
from tix.models import BoardState
from tix.persistence import load_state
from tix.screens.board import BoardScreen
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
                # Will handle gracefully — just no sync
                pass

    def on_mount(self) -> None:
        board = BoardScreen(column_names=self._column_names)
        self.push_screen(board)

        if not self._has_config:
            self.notify(
                "No config found \u2014 create ~/.config/tix/config.toml",
                severity="warning",
                timeout=8,
            )
        else:
            self.trigger_sync()

            # Set up periodic sync
            if self.config is not None:
                self.set_interval(
                    self.config.sync_interval_seconds,
                    self.trigger_sync,
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

            # Fetch custom statuses once
            custom_statuses = None
            if not self._custom_statuses_fetched:
                custom_statuses = self._zendesk.fetch_custom_statuses()
                self._custom_statuses_fetched = True

            self.manager.apply_sync(tickets, custom_statuses)
            self.manager.archive_closed_tickets()
            self.manager.save()

            count = len(self.manager.state.tickets)

            self.call_from_thread(self._post_sync_refresh, count, None)

        except TixError as exc:
            self.call_from_thread(self._post_sync_refresh, 0, str(exc))

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
        self.notify(f"Would open ticket #{event.ticket_id}")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_unmount(self) -> None:
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
    config: Config | None = None
    try:
        config = load_config()
    except ConfigError:
        create_default_config()

    app = TixApp(config)
    app.run()


if __name__ == "__main__":
    main()
