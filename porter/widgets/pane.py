"""FilePane — one side of the dual-pane browser."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label

from porter.fs.archive import ArchiveFilesystem
from porter.fs.base import Filesystem
from porter.fs.local import LocalFilesystem
from porter.models.entry import FileEntry
from porter.widgets.file_table import FileTable

_LOCAL = LocalFilesystem()


class FilePane(Widget):
    """Container: path header + file table.  Supports local and SFTP backends."""

    can_focus = False

    DEFAULT_CSS = """
    FilePane {
        width: 1fr;
        height: 100%;
        border: tall $panel-lighten-1;
    }
    FilePane.active {
        border: tall $accent;
    }
    FilePane > Label {
        background: $panel-lighten-2;
        color: $text;
        width: 100%;
        height: 1;
        padding: 0 1;
    }
    FilePane > FileTable {
        height: 1fr;
    }
    """

    def __init__(self, start_path: Path | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._fs: Filesystem = _LOCAL
        self._cwd: Path = start_path or Path.home()
        self._show_hidden: bool = False
        self._history: list[Path] = []

    def compose(self) -> ComposeResult:
        yield Label("", id="path-header")
        yield FileTable(id="file-table")

    def on_mount(self) -> None:
        self._refresh()

    # ── Public API ─────────────────────────────────────────────────────────

    def focus_table(self) -> None:
        self.query_one(FileTable).focus()

    def set_filesystem(self, fs: Filesystem) -> None:
        """Swap to a different filesystem backend (e.g. SFTP) and navigate home."""
        self._fs = fs
        self._history.clear()
        self._cwd = fs.home
        self._refresh()

    def navigate_to(self, path: Path) -> None:
        self._history.append(self._cwd)
        self._cwd = path
        self._refresh()

    def go_up(self) -> None:
        parent = self._cwd.parent
        if parent != self._cwd:
            self._cwd = parent
            self._refresh()
        elif isinstance(self._fs, ArchiveFilesystem):
            # At archive virtual root — exit back to the local directory containing the archive
            archive_path = self._fs._archive_path
            self._fs = _LOCAL
            self._history.clear()
            self._cwd = archive_path.parent
            self._refresh()

    def go_back(self) -> None:
        if self._history:
            self._cwd = self._history.pop()
            self._refresh()

    def toggle_hidden(self) -> None:
        self._show_hidden = not self._show_hidden
        self._refresh()

    def refresh_listing(self) -> None:
        self._refresh()

    def enable_hidden(self) -> None:
        """Turn on hidden-file display if not already on, then refresh."""
        if not self._show_hidden:
            self._show_hidden = True
            self._refresh()

    def clear_selection(self) -> None:
        self.query_one(FileTable).clear_selection()

    def restore_selection(self, names: set[str]) -> None:
        self.query_one(FileTable).restore_selection(names)

    @property
    def cwd(self) -> Path:
        return self._cwd

    @property
    def fs(self) -> Filesystem:
        return self._fs

    @property
    def active_entry(self) -> FileEntry | None:
        return self.query_one(FileTable).current_entry()

    @property
    def selected_entries(self) -> list[FileEntry]:
        return self.query_one(FileTable).selected_entries()

    # ── Internal ───────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        label = self._fs.label
        header = f" [{label}]  {self._cwd}" if label != "local" else f" {self._cwd}"
        self.query_one("#path-header", Label).update(header)
        try:
            entries = self._fs.listdir(self._cwd, self._show_hidden)
        except Exception as e:
            self.app.notify(f"Error listing directory: {e}", severity="error")
            entries = []
        self.query_one(FileTable).load_entries(entries)

    def on_file_table_directory_opened(self, event: FileTable.DirectoryOpened) -> None:
        event.stop()
        self.navigate_to(event.path)

    def on_file_table_navigate_up(self, event: FileTable.NavigateUp) -> None:
        event.stop()
        self.go_up()

    def on_file_table_archive_opened(self, event: FileTable.ArchiveOpened) -> None:
        event.stop()
        try:
            fs = ArchiveFilesystem(event.entry.path)
            self.set_filesystem(fs)
        except Exception as e:
            self.app.notify(f"Cannot open archive: {e}", severity="error")
