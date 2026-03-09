"""FilePane — one side of the dual-pane browser."""

from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Label

from porter.fs.local import listdir
from porter.models.entry import FileEntry
from porter.widgets.file_table import FileTable
from porter.widgets.jump_bar import JumpBar


class FilePane(Widget):
    """Container: path header + file table.  Never directly focused (can_focus=False).
    The FileTable inside takes focus."""

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
    FilePane > JumpBar {
        display: none;
    }
    FilePane > JumpBar.visible {
        display: block;
    }
    """

    def __init__(self, start_path: Path | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._cwd: Path = start_path or Path.home()
        self._show_hidden: bool = False
        self._history: list[Path] = []

    # ── Composition ────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Label(str(self._cwd), id="path-header")
        yield FileTable(id="file-table")
        yield JumpBar(id="jump-bar")

    def on_mount(self) -> None:
        self._refresh()

    # ── Public API ─────────────────────────────────────────────────────────

    def focus_table(self) -> None:
        self.query_one(FileTable).focus()

    def navigate_to(self, path: Path) -> None:
        self._history.append(self._cwd)
        self._cwd = path
        self._refresh()

    def go_up(self) -> None:
        parent = self._cwd.parent
        if parent != self._cwd:
            self._history.append(self._cwd)
            self._cwd = parent
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

    def open_jump_bar(self) -> None:
        bar = self.query_one(JumpBar)
        bar.add_class("visible")
        bar.query_one("#jump-input").value = str(self._cwd) + "/"
        bar.query_one("#jump-input").focus()

    @property
    def cwd(self) -> Path:
        return self._cwd

    @property
    def active_entry(self) -> FileEntry | None:
        return self.query_one(FileTable).current_entry()

    # ── Internal ───────────────────────────────────────────────────────────

    def _refresh(self) -> None:
        self.query_one("#path-header", Label).update(f" {self._cwd}")
        entries = listdir(self._cwd, self._show_hidden)
        self.query_one(FileTable).load_entries(entries)

    def _close_jump_bar(self) -> None:
        self.query_one(JumpBar).remove_class("visible")
        self.focus_table()

    # ── Message handlers ───────────────────────────────────────────────────

    def on_file_table_directory_opened(self, event: FileTable.DirectoryOpened) -> None:
        event.stop()
        self.navigate_to(event.path)

    def on_file_table_navigate_up(self, event: FileTable.NavigateUp) -> None:
        event.stop()
        self.go_up()

    def on_jump_bar_jump(self, event: JumpBar.Jump) -> None:
        event.stop()
        self._close_jump_bar()
        self.navigate_to(event.path)

    def on_jump_bar_cancelled(self, event: JumpBar.Cancelled) -> None:
        event.stop()
        self._close_jump_bar()
