"""JumpScreen — quick-jump modal, triggered by ':'.  Esc to cancel, Enter to jump."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Input, Label
from textual.containers import Vertical


class JumpScreen(ModalScreen[Path | None]):
    """Small overlay at the bottom of the screen for typing a path."""

    BINDINGS = [Binding("escape", "dismiss_none", "Cancel", priority=True)]

    DEFAULT_CSS = """
    JumpScreen {
        align: left bottom;
        background: transparent;
    }
    JumpScreen > Vertical {
        width: 100%;
        height: auto;
        background: $panel-darken-1;
        padding: 0;
    }
    JumpScreen Label {
        background: $accent;
        color: $text;
        width: 100%;
        padding: 0 1;
    }
    JumpScreen Input {
        width: 100%;
        background: $panel-lighten-2;
        color: white;
        border: none;
    }
    """

    def __init__(self, start: Path) -> None:
        super().__init__()
        self._start = start

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Jump to directory  (Tab to complete, Esc to cancel)")
            yield Input(value=str(self._start) + "/", id="jump-input")

    def on_mount(self) -> None:
        inp = self.query_one(Input)
        inp.focus()
        inp.cursor_position = len(inp.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        path = Path(raw).expanduser().resolve()
        if path.is_dir():
            self.dismiss(path)
        else:
            self.app.notify(f"Not a directory: {raw}", severity="error", timeout=2)

    def on_key(self, event) -> None:
        if event.key == "tab":
            event.stop()
            self._complete()

    def action_dismiss_none(self) -> None:
        self.dismiss(None)

    def _complete(self) -> None:
        inp = self.query_one(Input)
        raw = inp.value
        path = Path(raw).expanduser()
        parent = path.parent if not raw.endswith("/") else path
        stem = path.name if not raw.endswith("/") else ""
        try:
            matches = sorted(p for p in parent.iterdir() if p.is_dir() and p.name.startswith(stem))
        except OSError:
            return
        if len(matches) == 1:
            inp.value = str(matches[0]) + "/"
            inp.cursor_position = len(inp.value)
        elif len(matches) > 1:
            common = _common_prefix([m.name for m in matches])
            inp.value = str(parent / common)
            inp.cursor_position = len(inp.value)
            self.app.notify("  ".join(m.name for m in matches[:8]), timeout=3)


def _common_prefix(names: list[str]) -> str:
    if not names:
        return ""
    prefix = names[0]
    for name in names[1:]:
        while not name.startswith(prefix):
            prefix = prefix[:-1]
        if not prefix:
            break
    return prefix
