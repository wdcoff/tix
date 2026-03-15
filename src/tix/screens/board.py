from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import HorizontalScroll
from textual.screen import Screen
from textual.widgets import Footer, Input

from tix.screens.ticket_detail import TicketDetailScreen
from tix.widgets.card import TicketCardWidget
from tix.widgets.column import KanbanColumn
from tix.widgets.status_bar import SyncStatusBar


class BoardScreen(Screen):
    """Main Kanban board screen."""

    BINDINGS = [
        Binding("j,down", "cursor_down", "Next card", show=True),
        Binding("k,up", "cursor_up", "Prev card", show=True),
        Binding("h,left", "column_left", "Prev column", show=True),
        Binding("l,right", "column_right", "Next column", show=True),
        Binding("enter", "select_card", "Open card", show=True),
        Binding("r", "sync", "Sync", show=True),
        Binding("d", "detail", "Detail", show=True),
        Binding("slash", "search", "Search", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self, column_names: list[str], **kwargs) -> None:
        super().__init__(**kwargs)
        self._column_names = column_names
        self._current_col_idx = 0
        self._current_card_idx = 0
        self._filter_text: str = ""

    def compose(self) -> ComposeResult:
        yield Input(
            placeholder="Search tickets (ID or subject)...",
            id="search-input",
        )
        with HorizontalScroll(id="board-container"):
            for name in self._column_names:
                yield KanbanColumn(name, id=f"col-{name.lower().replace(' ', '-')}")
        yield SyncStatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        # Hide the search input initially
        search = self.query_one("#search-input", Input)
        search.display = False
        self.refresh_board()

    @property
    def columns(self) -> list[KanbanColumn]:
        """Return all column widgets in order."""
        return list(self.query(KanbanColumn))

    @property
    def status_bar(self) -> SyncStatusBar:
        return self.query_one("#status-bar", SyncStatusBar)

    # ------------------------------------------------------------------
    # Search / Filter
    # ------------------------------------------------------------------

    def action_search(self) -> None:
        """Show the search input and focus it."""
        search = self.query_one("#search-input", Input)
        search.display = True
        search.value = self._filter_text
        search.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Live-filter cards as the user types."""
        if event.input.id == "search-input":
            self._filter_text = event.value
            self._apply_filter()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Keep filter and return focus to the board on Enter."""
        if event.input.id == "search-input":
            self._filter_text = event.value
            search = self.query_one("#search-input", Input)
            search.display = False
            self._apply_filter()
            # Return focus to a card
            self._focus_card_at(self._current_col_idx, self._current_card_idx)

    def key_escape(self) -> None:
        """If search is visible, clear filter and hide it."""
        search = self.query_one("#search-input", Input)
        if search.display:
            self._filter_text = ""
            search.value = ""
            search.display = False
            self._apply_filter()
            self._focus_card_at(self._current_col_idx, self._current_card_idx)

    def _apply_filter(self) -> None:
        """Show/hide cards based on current filter text."""
        query = self._filter_text.strip().lower()
        for card in self.query(TicketCardWidget):
            if not query:
                card.display = True
            else:
                ticket = card.ticket
                id_match = query in str(ticket.ticket_id)
                subject_match = query in (ticket.subject or "").lower()
                card.display = id_match or subject_match

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _visible_cards(self, col: KanbanColumn) -> list[TicketCardWidget]:
        """Return only visible (not filtered out) cards in a column."""
        return [c for c in col.card_widgets() if c.display]

    def _focus_card_at(self, col_idx: int, card_idx: int) -> None:
        """Focus a specific card by column and card index."""
        cols = self.columns
        if not cols:
            return
        col_idx = max(0, min(col_idx, len(cols) - 1))
        self._current_col_idx = col_idx
        cards = self._visible_cards(cols[col_idx])
        if not cards:
            self._current_card_idx = 0
            return
        card_idx = max(0, min(card_idx, len(cards) - 1))
        self._current_card_idx = card_idx
        cards[card_idx].focus()

    def _find_focused_position(self) -> tuple[int, int]:
        """Find which column/card currently has focus."""
        focused = self.app.focused
        if isinstance(focused, TicketCardWidget):
            for ci, col in enumerate(self.columns):
                cards = self._visible_cards(col)
                for ri, card in enumerate(cards):
                    if card is focused:
                        return ci, ri
        return self._current_col_idx, self._current_card_idx

    def action_cursor_down(self) -> None:
        col_idx, card_idx = self._find_focused_position()
        self._focus_card_at(col_idx, card_idx + 1)

    def action_cursor_up(self) -> None:
        col_idx, card_idx = self._find_focused_position()
        self._focus_card_at(col_idx, card_idx - 1)

    def action_column_left(self) -> None:
        col_idx, _card_idx = self._find_focused_position()
        if col_idx > 0:
            self._focus_card_at(col_idx - 1, 0)

    def action_column_right(self) -> None:
        col_idx, _card_idx = self._find_focused_position()
        cols = self.columns
        if col_idx < len(cols) - 1:
            self._focus_card_at(col_idx + 1, 0)

    def action_select_card(self) -> None:
        focused = self.app.focused
        if isinstance(focused, TicketCardWidget):
            focused.post_message(TicketCardWidget.CardSelected(focused.ticket.ticket_id))

    def action_sync(self) -> None:
        self.app.trigger_sync()  # type: ignore[attr-defined]

    def action_detail(self) -> None:
        """Open the ticket detail modal for the focused card."""
        focused = self.app.focused
        if isinstance(focused, TicketCardWidget):
            self.app.push_screen(TicketDetailScreen(focused.ticket))

    def action_quit(self) -> None:
        self.app.exit()

    # ------------------------------------------------------------------
    # Card movement messages
    # ------------------------------------------------------------------

    def on_ticket_card_widget_card_move_left(self, event: TicketCardWidget.CardMoveLeft) -> None:
        self._move_card(event.ticket_id, -1)

    def on_ticket_card_widget_card_move_right(self, event: TicketCardWidget.CardMoveRight) -> None:
        self._move_card(event.ticket_id, 1)

    def _move_card(self, ticket_id: int, direction: int) -> None:
        """Move a card left (-1) or right (+1) by one column."""
        cols = self.columns
        col_names = [c.column_name for c in cols]

        manager = self.app.manager  # type: ignore[attr-defined]
        if manager is None:
            return

        current_col: str | None = None
        for ticket in manager.state.tickets:
            if ticket.ticket_id == ticket_id:
                current_col = ticket.local_column
                break

        if current_col is None:
            return

        try:
            idx = col_names.index(current_col)
        except ValueError:
            return

        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(col_names):
            return

        target_column = col_names[new_idx]
        try:
            manager.move_card(ticket_id, target_column)
        except KeyError:
            return

        self.refresh_board()
        self._focus_card_at(new_idx, 0)

    # ------------------------------------------------------------------
    # Board refresh
    # ------------------------------------------------------------------

    def refresh_board(self) -> None:
        """Clear all columns and re-populate from state manager."""
        manager = self.app.manager  # type: ignore[attr-defined]
        if manager is None:
            return

        cards_by_col = manager.get_cards_by_column()

        for col_widget in self.columns:
            col_widget.clear_tickets()
            tickets = cards_by_col.get(col_widget.column_name, [])
            priority_order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
            tickets.sort(
                key=lambda t: (
                    priority_order.get(t.priority.value if t.priority else "normal", 2),
                    t.updated_at or t.created_at or t.last_synced_at,
                )
            )
            for ticket in tickets:
                col_widget.add_ticket(ticket)
            col_widget._update_title()

        # Re-apply active filter
        if self._filter_text:
            self._apply_filter()

        total = len(manager.state.tickets)
        self.status_bar.update_sync(total)

        self._focus_card_at(self._current_col_idx, self._current_card_idx)
