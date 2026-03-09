"""JumpBar — quick path-entry bar, triggered by ':'.  Esc to cancel, Enter to jump."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, Label


class JumpBar(Widget):
    """A single-line path input that slides in at the bottom of a FilePane."""

    class Jump(Message):
        def __init__(self, path: Path) -> None:
            self.path = path
            super().__init__()

    class Cancelled(Message):
        pass

    DEFAULT_CSS = """
    JumpBar {
        height: 1;
        layout: horizontal;
    }
    JumpBar > Label {
        width: auto;
        padding: 0 1;
        background: $accent;
        color: $text;
    }
    JumpBar > Input {
        width: 1fr;
        height: 1;
        border: none;
        background: $panel-lighten-1;
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("Go to:")
        yield Input(placeholder="path  (Tab to complete)", id="jump-input")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        raw = event.value.strip()
        path = Path(raw).expanduser().resolve()
        if path.is_dir():
            self.post_message(self.Jump(path))
        else:
            self.query_one(Input).add_class("-invalid")
            self.app.notify(f"Not a directory: {raw}", severity="error", timeout=2)

    def on_key(self, event) -> None:
        if event.key == "escape":
            event.stop()
            self.post_message(self.Cancelled())
        elif event.key == "tab":
            event.stop()
            self._complete()

    def _complete(self) -> None:
        inp = self.query_one(Input)
        raw = inp.value
        path = Path(raw).expanduser()
        parent = path.parent if not raw.endswith("/") else path
        stem = path.name if not raw.endswith("/") else ""
        try:
            matches = sorted(
                p for p in parent.iterdir()
                if p.is_dir() and p.name.startswith(stem)
            )
        except OSError:
            return
        if len(matches) == 1:
            inp.value = str(matches[0]) + "/"
            inp.cursor_position = len(inp.value)
        elif len(matches) > 1:
            # Fill common prefix
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
