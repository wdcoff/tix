from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static, TextArea


class NoteEditorScreen(ModalScreen[str | None]):
    """Modal screen for editing notes on a ticket."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    DEFAULT_CSS = """
    NoteEditorScreen {
        align: center middle;
    }
    """

    def __init__(self, ticket_id: int, existing_notes: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.ticket_id = ticket_id
        self.existing_notes = existing_notes or ""

    def compose(self) -> ComposeResult:
        with Container(id="note-modal"):
            yield Static(
                f"[bold]Notes for #{self.ticket_id}[/]",
                id="note-title",
            )
            yield TextArea(self.existing_notes, id="note-textarea")
            with Horizontal(id="note-buttons"):
                yield Button("Save", id="note-save-btn", variant="primary")
                yield Button("Cancel", id="note-cancel-btn", variant="default")

    def on_mount(self) -> None:
        self.query_one("#note-textarea", TextArea).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "note-save-btn":
            text = self.query_one("#note-textarea", TextArea).text
            self.dismiss(text)
        elif event.button.id == "note-cancel-btn":
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
