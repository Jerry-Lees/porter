"""FileTable — DataTable subclass that drives pane navigation."""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import events
from textual.coordinate import Coordinate
from textual.message import Message
from textual.widgets import DataTable

from porter.models.entry import FileEntry

_PARENT_KEY = "__parent__"


class FileTable(DataTable):
    """A DataTable pre-configured for file listings.

    Posts custom messages instead of letting RowSelected bubble — keeps
    navigation logic in FilePane rather than the app.
    """

    # ── Custom messages ────────────────────────────────────────────────────

    class DirectoryOpened(Message):
        def __init__(self, path: Path) -> None:
            self.path = path
            super().__init__()

    class NavigateUp(Message):
        pass

    class FileActivated(Message):
        def __init__(self, entry: FileEntry) -> None:
            self.entry = entry
            super().__init__()

    class ArchiveOpened(Message):
        def __init__(self, entry: FileEntry) -> None:
            self.entry = entry
            super().__init__()

    class ContextMenuRequested(Message):
        def __init__(self, entry: FileEntry | None, x: int, y: int) -> None:
            self.entry = entry
            self.x = x
            self.y = y
            super().__init__()

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def __init__(self, **kwargs) -> None:
        super().__init__(cursor_type="row", zebra_stripes=True, **kwargs)
        self._row_entries: dict[str, FileEntry | None] = {}
        self._current_row_key: str | None = _PARENT_KEY
        self._selected: set[str] = set()

    def on_mount(self) -> None:
        self.add_column("Name",     key="name",  width=30)
        self.add_column("Perms",    key="perms", width=10)
        self.add_column("Owner",    key="owner", width=8)
        self.add_column("Size",     key="size",  width=7)
        self.add_column("Modified", key="mtime", width=16)

    # ── Public API ─────────────────────────────────────────────────────────

    def load_entries(self, entries: list[FileEntry]) -> None:
        """Replace the table contents with *entries*.  Cursor returns to top."""
        with self.prevent(DataTable.RowHighlighted, DataTable.RowSelected):
            self.clear()
            self._row_entries.clear()
            self._selected.clear()

            # ".." is always first
            self.add_row(Text("..", style="bold"), "", "", "", "", key=_PARENT_KEY)
            self._row_entries[_PARENT_KEY] = None

            for entry in entries:
                key = entry.name
                if entry.is_dir:
                    name_text = Text(entry.name + "/", style="bold cyan")
                elif entry.is_archive:
                    name_text = Text(entry.name, style="bold yellow")
                else:
                    name_text = Text(entry.name)

                self.add_row(
                    name_text,
                    entry.permissions_str,
                    entry.owner,
                    entry.size_str,
                    entry.mtime_str,
                    key=key,
                )
                self._row_entries[key] = entry

        # After reload cursor is at row 0 (..)
        self._current_row_key = _PARENT_KEY

    def current_entry(self) -> FileEntry | None:
        """Return the FileEntry for the highlighted row, or None for '..'."""
        if self._current_row_key is None or self._current_row_key == _PARENT_KEY:
            return None
        return self._row_entries.get(self._current_row_key)

    def selected_entries(self) -> list[FileEntry]:
        """Return all explicitly selected entries (space-tagged), or [] if none."""
        result = []
        for key in self._selected:
            entry = self._row_entries.get(key)
            if entry is not None:
                result.append(entry)
        return result

    def clear_selection(self) -> None:
        """Deselect all selected entries and restore their normal row style."""
        to_update = [(key, self._row_entries.get(key)) for key in self._selected]
        self._selected.clear()
        for key, entry in to_update:
            if entry is not None:
                self._update_row_style(key, entry)

    def restore_selection(self, names: set[str]) -> None:
        """Re-select rows whose name is in *names* (used after a partial failure)."""
        for key, entry in self._row_entries.items():
            if entry is not None and entry.name in names:
                self._selected.add(key)
                self._update_row_style(key, entry)

    def _update_row_style(self, key: str, entry: FileEntry) -> None:
        """Re-render the name cell to reflect selected/unselected state."""
        if key in self._selected:
            name_text = Text("* " + (entry.name + "/" if entry.is_dir else entry.name),
                             style="bold yellow")
        elif entry.is_dir:
            name_text = Text(entry.name + "/", style="bold cyan")
        elif entry.is_archive:
            name_text = Text(entry.name, style="bold yellow")
        else:
            name_text = Text(entry.name)
        try:
            self.update_cell(key, "name", name_text)
        except Exception:
            pass

    # ── Event handlers ─────────────────────────────────────────────────────

    async def _on_click(self, event: events.Click) -> None:
        """Single-click moves cursor; right-click and archives skip activation."""
        if event.button == 3:
            return  # right-click handled by on_mouse_up
        meta = event.style.meta
        if "row" in meta and "column" in meta:
            row_index = meta["row"]
            is_header = self.show_header and row_index == -1
            if not is_header and self.show_cursor and self.cursor_type != "none":
                self.cursor_coordinate = Coordinate(row_index, meta["column"])
                # Archives require Enter/double-click to open; single-click just highlights
                entry = self.current_entry()
                if entry is None or not entry.is_archive:
                    self._post_selected_message()
                self._scroll_cursor_into_view(animate=True)
                event.prevent_default()
                event.stop()
                return
        await super()._on_click(event)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key is not None:
            self._current_row_key = str(event.row_key.value)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        event.stop()
        key = str(event.row_key.value) if event.row_key else None
        if key == _PARENT_KEY or key is None:
            self.post_message(self.NavigateUp())
            return
        entry = self._row_entries.get(key)
        if entry is None:
            return
        if entry.is_dir:
            self.post_message(self.DirectoryOpened(entry.path))
        elif entry.is_archive:
            self.post_message(self.ArchiveOpened(entry))
        else:
            self.post_message(self.FileActivated(entry))

    def on_key(self, event) -> None:
        if event.key == "backspace":
            event.stop()
            self.post_message(self.NavigateUp())
        elif event.key == "f1":
            event.stop()
            self.app.action_help()
        elif event.character == "." or event.key in ("period", "full_stop"):
            event.stop()
            self.app.action_toggle_hidden()
        elif event.key == "grave_accent":
            event.stop()
            self.post_message(self.ContextMenuRequested(self.current_entry(), 4, 4))
        elif event.key == "space":
            event.stop()
            key = self._current_row_key
            if key and key != _PARENT_KEY:
                entry = self._row_entries.get(key)
                if entry is not None:
                    if key in self._selected:
                        self._selected.discard(key)
                    else:
                        self._selected.add(key)
                    self._update_row_style(key, entry)
            self.action_cursor_down()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if event.button == 3:  # right-click
            event.stop()
            self.post_message(self.ContextMenuRequested(
                self.current_entry(), event.screen_x, event.screen_y
            ))
