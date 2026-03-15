"""HelpScreen — F1 keyboard shortcut reference."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import DataTable, Label
from textual.containers import Vertical


_SHORTCUTS = [
    # (key, action)
    ("F1",          "This help screen"),
    ("F3",          "View file"),
    ("F4",          "Edit file (download → $EDITOR → upload)"),
    ("F5",          "Copy selected file(s) to other pane"),
    ("F6",          "Move selected file(s) to other pane"),
    ("F7",          "Make directory"),
    ("F8",          "Delete selected file(s)"),
    ("",            ""),
    ("Enter",       "Open directory / activate file / open archive"),
    ("Backspace",   "Navigate up one directory"),
    ("Tab",         "Switch active pane"),
    ("Space",       "Select / deselect file and move down"),
    ("",            ""),
    ("` (backtick)","Context menu at cursor"),
    (": (colon)",   "Jump to path  (Tab completes, Enter jumps, Esc cancels)"),
    (". (period)",  "Toggle hidden (dot) files"),
    ("Alt+Left",    "Navigate back in pane history"),
    ("Ctrl+R",      "Refresh active pane"),
    ("",            ""),
    ("Ctrl+N",      "New empty archive"),
    ("Ctrl+O",      "Connect to SSH/SFTP host"),
    ("Ctrl+Q",      "Quit"),
    ("",            ""),
    ("Right-click", "Context menu at mouse position"),
]


class HelpScreen(ModalScreen[None]):
    """F1 keyboard shortcut reference overlay."""

    BINDINGS = [
        Binding("escape", "dismiss_help", "Close", priority=True),
        Binding("f1",     "dismiss_help", "Close", priority=True),
    ]

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    HelpScreen > Vertical {
        width: 64;
        height: auto;
        max-height: 90%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    HelpScreen Label.title {
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }
    HelpScreen DataTable {
        height: auto;
        max-height: 40;
        border: none;
        background: $surface;
    }
    HelpScreen Label.footer {
        width: 100%;
        text-align: center;
        margin-top: 1;
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[bold]Porter — Keyboard Shortcuts[/bold]", classes="title")
            tbl = DataTable(show_header=False, cursor_type="none", zebra_stripes=True)
            tbl.add_column("key",    width=18)
            tbl.add_column("action", width=38)
            for key, action in _SHORTCUTS:
                tbl.add_row(key, action)
            yield tbl
            yield Label("F1 or Esc to close", classes="footer")

    def on_mount(self) -> None:
        self.query_one(DataTable).focus()

    def action_dismiss_help(self) -> None:
        self.dismiss(None)
