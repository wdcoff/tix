from __future__ import annotations

from datetime import datetime, timezone

from textual.message import Message
from textual.widgets import Static


from tix.models import TicketData, Priority


class TicketCardWidget(Static):
    """A single ticket card in a Kanban column."""

    can_focus = True

    class CardSelected(Message):
        """Emitted when Enter is pressed on a card."""

        def __init__(self, ticket_id: int) -> None:
            super().__init__()
            self.ticket_id = ticket_id

    class CardMoveLeft(Message):
        """Emitted when Shift+H is pressed — move card one column left."""

        def __init__(self, ticket_id: int) -> None:
            super().__init__()
            self.ticket_id = ticket_id

    class CardMoveRight(Message):
        """Emitted when Shift+H is pressed — move card one column right."""

        def __init__(self, ticket_id: int) -> None:
            super().__init__()
            self.ticket_id = ticket_id

    def __init__(self, ticket: TicketData, **kwargs) -> None:
        super().__init__(**kwargs)
        self.ticket = ticket

    def on_mount(self) -> None:
        self._apply_priority_class()
        self._apply_stale_class()

    def _apply_priority_class(self) -> None:
        priority = self.ticket.priority
        if priority == Priority.URGENT:
            self.add_class("priority-urgent")
        elif priority == Priority.HIGH:
            self.add_class("priority-high")
        elif priority == Priority.LOW:
            self.add_class("priority-low")

    def _apply_stale_class(self) -> None:
        if self.ticket.stale_since is not None:
            self.add_class("stale")

    def render(self) -> str:
        t = self.ticket

        # Line 1: ticket ID + subject
        tid = f"#{t.ticket_id}"
        subject = t.subject[:30] if t.subject else ""
        line1 = f"{tid}  {subject}"

        # Line 2: priority | requester | age
        priority_str = (t.priority.value if t.priority else "normal").capitalize()
        requester = t.requester_name or "Unknown"
        if len(requester) > 12:
            requester = requester[:11] + "\u2026"

        age_str = self._format_age()

        # Color the priority label
        priority_color = {
            Priority.URGENT: "red",
            Priority.HIGH: "yellow",
            Priority.NORMAL: "white",
            Priority.LOW: "dim white",
        }.get(t.priority, "white")

        line2 = (
            f"[{priority_color}]{priority_str}[/] | "
            f"{requester} | "
            f"{age_str}"
        )

        # Line 3: conditional badges
        line3 = self._render_badges()

        lines = [line1, line2]
        if line3:
            lines.append(line3)

        return "\n".join(lines)

    def _format_age(self) -> str:
        ref = self.ticket.updated_at or self.ticket.created_at
        if ref is None:
            return "?d ago"
        now = datetime.now(timezone.utc)
        delta = now - ref
        days = delta.days
        if days == 0:
            hours = int(delta.total_seconds() // 3600)
            if hours == 0:
                mins = int(delta.total_seconds() // 60)
                return f"{mins}m ago"
            return f"{hours}h ago"
        return f"{days}d ago"

    def _render_badges(self) -> str:
        t = self.ticket
        parts: list[str] = []

        # Stale badge
        if self.has_class("stale"):
            parts.append("[bold yellow]\u26a0 Stale[/]")

        # PR status
        if t.pr.status is not None:
            pr_colors = {
                "open": "green",
                "draft": "dim white",
                "merged": "magenta",
                "closed": "red",
            }
            color = pr_colors.get(t.pr.status.value, "white")
            pr_label = "PR"
            if t.pr.number:
                pr_label = f"PR#{t.pr.number}"
            if t.pr.repo:
                # Show just the repo name, not owner/repo
                short_repo = t.pr.repo.split("/")[-1] if "/" in t.pr.repo else t.pr.repo
                pr_label = f"{short_repo}#{t.pr.number or '?'}"
            parts.append(f"[{color}]{pr_label}:{t.pr.status.value}[/]")

        # Deploy tag
        if t.deployed_in_tag:
            parts.append(f"[cyan]\U0001f680 {t.deployed_in_tag}[/]")

        return "  ".join(parts)

    def key_enter(self) -> None:
        self.post_message(self.CardSelected(self.ticket.ticket_id))

    def key_H(self) -> None:
        self.post_message(self.CardMoveLeft(self.ticket.ticket_id))

    def key_L(self) -> None:
        self.post_message(self.CardMoveRight(self.ticket.ticket_id))
