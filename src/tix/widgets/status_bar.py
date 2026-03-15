from __future__ import annotations

from textual.widgets import Static


class SyncStatusBar(Static):
    """Bottom bar showing last sync information."""

    def __init__(self, **kwargs) -> None:
        super().__init__("No sync yet", **kwargs)
        self._ticket_count = 0
        self._error: str | None = None

    def update_sync(self, count: int, error: str | None = None) -> None:
        """Update the status bar with sync results."""
        self._ticket_count = count
        self._error = error
        if error:
            self.update(f"[bold red]Sync error:[/] {error}")
        else:
            self.update(f"Synced {count} tickets just now")

    def update_age(self, minutes: int) -> None:
        """Update the displayed age since last sync."""
        if self._error:
            return
        self.update(f"Synced {self._ticket_count} tickets {minutes}m ago")
