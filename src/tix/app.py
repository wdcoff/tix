from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Static

from tix.config import Config, load_config, create_default_config, ConfigError
from tix.persistence import load_state
from tix.state_manager import StateManager


class TixApp(App):
    """Zendesk investigation tracker TUI."""

    TITLE = "tix"

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        self.manager: StateManager | None = None

    def compose(self) -> ComposeResult:
        yield Static("Loading...")

    def on_mount(self) -> None:
        state = load_state()
        self.manager = StateManager(
            state=state,
            default_column=self.config.column_names[0] if self.config.column_names else "Triage",
        )


def main() -> None:
    try:
        config = load_config()
    except ConfigError as exc:
        create_default_config()
        raise SystemExit(str(exc)) from exc

    app = TixApp(config)
    app.run()


if __name__ == "__main__":
    main()
