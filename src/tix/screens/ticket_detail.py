from __future__ import annotations

from datetime import datetime, timezone

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from tix.models import TicketData


class TicketDetailScreen(ModalScreen[None]):
    """Modal screen showing full ticket details."""

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close", show=True),
    ]

    DEFAULT_CSS = """
    TicketDetailScreen {
        align: center middle;
    }
    """

    def __init__(self, ticket: TicketData, **kwargs) -> None:
        super().__init__(**kwargs)
        self.ticket = ticket

    def compose(self) -> ComposeResult:
        t = self.ticket

        with Container(id="detail-modal"):
            yield Static(
                f"[bold]#{t.ticket_id}[/]  {t.subject}",
                id="detail-title",
            )
            with Vertical(id="detail-body"):
                yield Static(f"[b]Zendesk Status:[/]  {t.zendesk_status}", classes="detail-field")
                yield Static(f"[b]Local Column:[/]    {t.local_column}", classes="detail-field")
                yield Static(
                    f"[b]Priority:[/]        {t.priority.value.capitalize() if t.priority else 'Normal'}",
                    classes="detail-field",
                )
                yield Static(
                    f"[b]Requester:[/]       {t.requester_name or 'Unknown'}",
                    classes="detail-field",
                )

                # Dates
                created = _format_dt(t.created_at) if t.created_at else "N/A"
                updated = _format_dt(t.updated_at) if t.updated_at else "N/A"
                yield Static(f"[b]Created:[/]         {created}", classes="detail-field")
                yield Static(f"[b]Updated:[/]         {updated}", classes="detail-field")

                # Git context
                if t.git.worktree_path:
                    yield Static(
                        f"[b]Worktree:[/]        {t.git.worktree_path}",
                        classes="detail-field",
                    )
                if t.git.branch_name:
                    yield Static(
                        f"[b]Branch:[/]          {t.git.branch_name}",
                        classes="detail-field",
                    )

                # PR context
                if t.pr.url:
                    yield Static(
                        f"[b]PR URL:[/]          {t.pr.url}",
                        classes="detail-field",
                    )
                if t.pr.status:
                    yield Static(
                        f"[b]PR Status:[/]       {t.pr.status.value}",
                        classes="detail-field",
                    )

                # Deploy
                if t.deployed_in_tag:
                    yield Static(
                        f"[b]Deploy Tag:[/]      {t.deployed_in_tag}",
                        classes="detail-field",
                    )

                # Notes
                if t.notes:
                    yield Static("[b]Notes:[/]", classes="detail-field")
                    yield Static(
                        t.notes,
                        classes="detail-field detail-notes",
                    )

                # Staleness
                if t.stale_since:
                    hours = (datetime.now(timezone.utc) - t.stale_since).total_seconds() / 3600
                    yield Static(
                        f"[b]Stale:[/]           {hours:.1f}h (since {_format_dt(t.stale_since)})",
                        classes="detail-field detail-stale",
                    )

            yield Button("Close", id="detail-close-btn", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "detail-close-btn":
            self.dismiss(None)

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)


def _format_dt(dt: datetime) -> str:
    """Format a datetime for display."""
    return dt.strftime("%Y-%m-%d %H:%M UTC")
