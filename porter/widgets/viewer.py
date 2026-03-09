"""ViewerScreen — full-screen file viewer, launched by F3."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, TextArea


class ViewerScreen(ModalScreen):
    """Read-only file viewer.  Esc or Q to close."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    ViewerScreen {
        align: center middle;
    }
    ViewerScreen > Vertical {
        width: 92%;
        height: 92%;
        border: thick $accent;
        background: $surface;
    }
    ViewerScreen > Vertical > Label {
        background: $accent;
        color: $text;
        width: 100%;
        height: 1;
        padding: 0 1;
    }
    ViewerScreen > Vertical > TextArea {
        height: 1fr;
    }
    """

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path

    def compose(self) -> ComposeResult:
        try:
            content = self._path.read_text(errors="replace")
        except OSError as e:
            content = f"[error reading file: {e}]"

        with Vertical():
            yield Label(f" {self._path}   (Esc / Q to close)")
            yield TextArea(content, read_only=True)
