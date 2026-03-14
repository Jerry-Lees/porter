"""ContextMenu — right-click / backtick flyout menu."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Label, ListView, ListItem

from porter.models.entry import FileEntry


class ContextMenu(ModalScreen[str | None]):
    """Flyout context menu that returns the chosen action key or None."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", priority=True)]

    DEFAULT_CSS = """
    ContextMenu {
        background: transparent;
    }
    ContextMenu > ListView {
        width: 28;
        height: auto;
        max-height: 20;
        border: solid $accent;
        background: $surface;
    }
    ContextMenu ListView > ListItem {
        padding: 0 1;
    }
    ContextMenu ListView > ListItem.separator {
        height: 1;
        background: $panel-lighten-1;
        padding: 0;
    }
    """

    # action key → label
    _BACKGROUND_ITEMS = [
        ("new_archive",     "New Archive…"),
        (None,              "─────────────────────"),
        ("snapshot",        "Take Snapshot"),
        ("system_snapshot", "System Snapshot (from /)"),
        ("build_archive",   "Build Archive from Diff"),
    ]

    _FILE_ITEMS = [
        ("view",    "View"),
        ("edit",    "Edit"),
        (None,      "─────────────────────"),
        ("copy",    "Copy to other pane"),
        ("move",    "Move to other pane"),
        (None,      "─────────────────────"),
        ("rename",  "Rename"),
        ("delete",  "Delete"),
        (None,      "─────────────────────"),
        ("props",   "Properties"),
    ]

    _DIR_ITEMS = [
        ("open",    "Open"),
        (None,      "─────────────────────"),
        ("copy",    "Copy to other pane"),
        ("move",    "Move to other pane"),
        (None,      "─────────────────────"),
        ("delete",  "Delete"),
        ("rename",  "Rename"),
        (None,      "─────────────────────"),
        ("props",   "Properties"),
    ]

    _ARCHIVE_ITEMS = [
        ("archive_open",   "Open Archive"),
        ("archive_verify", "Verify Integrity"),
        ("copy",           "Copy to other pane"),
        (None,             "─────────────────────"),
        ("delete",         "Delete"),
    ]

    def __init__(self, entry: FileEntry | None, x: int = 0, y: int = 0) -> None:
        super().__init__()
        self._entry = entry
        self._x = x
        self._y = y
        self._action_keys: list[str | None] = []

    def compose(self) -> ComposeResult:
        if self._entry is None:
            items_def = self._BACKGROUND_ITEMS
        elif self._entry.is_archive:
            items_def = self._ARCHIVE_ITEMS
        elif self._entry.is_dir:
            items_def = self._DIR_ITEMS
        else:
            items_def = self._FILE_ITEMS

        items = []
        for key, label in items_def:
            self._action_keys.append(key)
            if key is None:
                item = ListItem(Label(label), classes="separator")
                item.disabled = True
            else:
                item = ListItem(Label(label))
            items.append(item)

        lv = ListView(*items, id="menu-list")
        yield lv

    def on_mount(self) -> None:
        lv = self.query_one(ListView)
        # Position near click; clamp so it stays on screen
        lv.styles.offset = (self._x, self._y)
        lv.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = self.query_one(ListView).index
        if idx is not None and idx < len(self._action_keys):
            key = self._action_keys[idx]
            if key is not None:
                self.dismiss(key)

    def action_cancel(self) -> None:
        self.dismiss(None)
