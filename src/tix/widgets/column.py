from __future__ import annotations

from textual.containers import VerticalScroll

from tix.models import TicketData
from tix.widgets.card import TicketCardWidget


class KanbanColumn(VerticalScroll):
    """A single column in the Kanban board, displayed as a scrollable vertical list."""

    DEFAULT_CSS = """
    KanbanColumn {
        width: 42;
    }
    """

    def __init__(self, column_name: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._column_name = column_name
        self.border_title = f"{column_name} (0)"

    @property
    def column_name(self) -> str:
        return self._column_name

    def add_ticket(self, ticket: TicketData) -> TicketCardWidget:
        """Mount a new card widget for the given ticket."""
        card = TicketCardWidget(ticket)
        self.mount(card)
        self._update_title()
        return card

    def remove_ticket(self, ticket_id: int) -> None:
        """Remove a card widget by ticket id."""
        for child in self.query(TicketCardWidget):
            if child.ticket.ticket_id == ticket_id:
                child.remove()
                break
        self._update_title()

    def clear_tickets(self) -> None:
        """Remove all ticket cards from this column."""
        for child in list(self.query(TicketCardWidget)):
            child.remove()
        self._update_title()

    def card_widgets(self) -> list[TicketCardWidget]:
        """Return all card widgets in this column, in DOM order."""
        return list(self.query(TicketCardWidget))

    def _update_title(self) -> None:
        count = len(self.query(TicketCardWidget))
        self.border_title = f"{self._column_name} ({count})"
