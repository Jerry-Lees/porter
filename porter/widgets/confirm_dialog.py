"""Reusable confirmation and input dialogs."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class ConfirmDialog(ModalScreen[bool]):
    """Yes / No confirmation dialog."""

    BINDINGS = [
        Binding("y", "yes", "Yes", priority=True),
        Binding("n", "no", "No", priority=True),
        Binding("escape", "no", "Cancel", priority=True),
    ]

    DEFAULT_CSS = """
    ConfirmDialog {
        align: center middle;
    }
    ConfirmDialog > Vertical {
        width: 60;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    ConfirmDialog Label {
        width: 100%;
        margin-bottom: 1;
    }
    ConfirmDialog Horizontal {
        width: 100%;
        height: auto;
        align: center middle;
    }
    ConfirmDialog Button {
        margin: 0 2;
    }
    """

    def __init__(self, message: str, title: str = "Confirm") -> None:
        super().__init__()
        self._message = message
        self._title = title

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"[bold]{self._title}[/bold]")
            yield Label(self._message)
            with Horizontal():
                yield Button("Yes (Y)", id="yes", variant="error")
                yield Button("No (N)", id="no", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#no", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)


class InputDialog(ModalScreen[str | None]):
    """Single-line text input dialog."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", priority=True)]

    DEFAULT_CSS = """
    InputDialog {
        align: center middle;
    }
    InputDialog > Vertical {
        width: 60;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    InputDialog Label {
        width: 100%;
        margin-bottom: 1;
    }
    InputDialog Input {
        width: 100%;
        color: white;
    }
    """

    def __init__(self, prompt: str, default: str = "") -> None:
        super().__init__()
        self._prompt = prompt
        self._default = default

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._prompt)
            yield Input(value=self._default, id="input")

    def on_mount(self) -> None:
        inp = self.query_one(Input)
        inp.focus()
        inp.cursor_position = len(inp.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        self.dismiss(value if value else None)

    def action_cancel(self) -> None:
        self.dismiss(None)
