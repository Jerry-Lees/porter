"""PorterApp — top-level Textual application."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual import events

from porter.widgets.confirm_dialog import ConfirmDialog, InputDialog
from porter.widgets.connect_dialog import ConnectDialog
from porter.widgets.context_menu import ContextMenu
from porter.widgets.fkey_bar import FKeyBar
from porter.widgets.jump_bar import JumpScreen
from porter.widgets.pane import FilePane
from porter.widgets.viewer import ViewerScreen
from porter.fs.sftp import SFTPFilesystem
from porter.fs.ssh_config import SSHHost
from porter.widgets.file_table import FileTable


class PorterApp(App):
    """Porter — dual-pane terminal file manager."""

    CSS_PATH = "porter.tcss"

    BINDINGS = [
        Binding("f3",  "view_file",     "View",    show=False, priority=True),
        Binding("f4",  "edit_file",     "Edit",    show=False, priority=True),
        Binding("f5",  "copy_file",     "Copy",    show=False, priority=True),
        Binding("f7",  "mkdir",         "MkDir",   show=False, priority=True),
        Binding("f8",  "delete_file",   "Delete",  show=False, priority=True),
        Binding("ctrl+h", "toggle_hidden",  "Hidden",  show=False, priority=True),
        Binding("ctrl+r", "refresh_pane",   "Refresh", show=False, priority=True),
        Binding("alt+left", "go_back",      "Back",    show=False, priority=True),
        Binding("grave_accent", "context_menu", "Menu", show=False, priority=True),
        Binding("ctrl+o", "connect", "Connect", show=False, priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._active_side: str = "left"

    # ── Layout ─────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Horizontal(
            FilePane(id="left-pane"),
            FilePane(id="right-pane"),
            id="pane-row",
        )
        yield FKeyBar()

    def on_mount(self) -> None:
        self._activate_pane("left")

    # ── Pane management ────────────────────────────────────────────────────

    def _activate_pane(self, side: str) -> None:
        self._active_side = side
        for pane in self.query(FilePane):
            pane.remove_class("active")
        active = self.query_one(f"#{side}-pane", FilePane)
        active.add_class("active")
        active.focus_table()

    def _active_pane(self) -> FilePane:
        return self.query_one(f"#{self._active_side}-pane", FilePane)

    def _inactive_pane(self) -> FilePane:
        other = "right" if self._active_side == "left" else "left"
        return self.query_one(f"#{other}-pane", FilePane)

    def _switch_pane(self) -> None:
        other = "right" if self._active_side == "left" else "left"
        self._activate_pane(other)

    # ── Key handling ───────────────────────────────────────────────────────

    def on_key(self, event: events.Key) -> None:
        if event.key == "tab":
            event.stop()
            event.prevent_default()
            self._switch_pane()
        elif event.character == ":":
            event.stop()
            self.action_jump()

    # ── Actions ────────────────────────────────────────────────────────────

    def action_toggle_hidden(self) -> None:
        self._active_pane().toggle_hidden()

    def action_refresh_pane(self) -> None:
        self._active_pane().refresh_listing()

    def action_go_back(self) -> None:
        self._active_pane().go_back()

    def action_context_menu(self) -> None:
        entry = self._active_pane().active_entry
        self._show_context_menu(entry, 4, 4)

    def on_file_table_context_menu_requested(self, event: FileTable.ContextMenuRequested) -> None:
        event.stop()
        self._show_context_menu(event.entry, event.x, event.y)

    def _show_context_menu(self, entry, x: int, y: int) -> None:
        pane = self._active_pane()

        def handle(action: str | None) -> None:
            if action is None:
                return
            if action == "view":
                self.action_view_file()
            elif action == "edit":
                self.action_edit_file()
            elif action == "copy":
                self.action_copy_file()
            elif action == "delete":
                self.action_delete_file()
            elif action == "open":
                if entry:
                    pane.navigate_to(entry.path)
            elif action == "archive_open":
                if entry:
                    from porter.fs.archive import ArchiveFilesystem
                    try:
                        pane.set_filesystem(ArchiveFilesystem(entry.path))
                    except Exception as e:
                        self.notify(f"Cannot open archive: {e}", severity="error")
            elif action == "archive_verify":
                self._verify_archive(entry)
            elif action == "rename":
                self._rename_entry(entry, pane)
            elif action == "props":
                self._show_props(entry)
            elif action == "move":
                self.notify("Move — coming soon", timeout=2)

        self.push_screen(ContextMenu(entry, x, y), handle)

    def _rename_entry(self, entry, pane) -> None:
        if entry is None:
            return
        def do_rename(new_name: str | None) -> None:
            if not new_name or new_name == entry.name:
                return
            dst = entry.path.parent / new_name
            try:
                entry.path.rename(dst)
                pane.refresh_listing()
                self.notify(f"Renamed to {new_name}")
            except OSError as e:
                self.notify(f"Rename failed: {e}", severity="error")
        self.push_screen(InputDialog("Rename to:", default=entry.name), do_rename)

    def _show_props(self, entry) -> None:
        if entry is None:
            return
        msg = (
            f"[bold]{entry.name}[/bold]\n"
            f"Path:  {entry.path}\n"
            f"Size:  {entry.size_str}  ({entry.size:,} bytes)\n"
            f"Perms: {entry.permissions_str}\n"
            f"Owner: {entry.owner}:{entry.group}\n"
            f"Modified: {entry.mtime_str}"
        )
        self.notify(msg, title="Properties", timeout=8)

    def _verify_archive(self, entry) -> None:
        if entry is None:
            return
        import tarfile, zipfile
        name = entry.name.lower()
        try:
            if name.endswith((".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".tar")):
                with tarfile.open(entry.path, "r:*") as tf:
                    tf.getmembers()
                self.notify(f"{entry.name} — archive OK", timeout=4)
            elif name.endswith(".zip"):
                with zipfile.ZipFile(entry.path, "r") as zf:
                    bad = zf.testzip()
                if bad:
                    self.notify(f"Bad file in archive: {bad}", severity="error", timeout=6)
                else:
                    self.notify(f"{entry.name} — archive OK", timeout=4)
        except Exception as e:
            self.notify(f"Verify failed: {e}", severity="error", timeout=6)

    # ── Ctrl+O Connect ─────────────────────────────────────────────────────

    def action_connect(self) -> None:
        pane = self._active_pane()

        def do_connect(host: SSHHost | None) -> None:
            if host is None:
                return
            fs = SFTPFilesystem(
                hostname=host.hostname,
                username=host.username or None,
                port=host.port,
                key_filename=host.identity_file or None,
                proxy_jump=host.proxy_jump or None,
            )
            self.notify(f"Connecting to {host.alias}…", timeout=3)
            try:
                fs.connect()
                pane.set_filesystem(fs)
                self.notify(f"Connected to {host.alias}", timeout=2)
            except Exception as e:
                self.notify(f"Connection failed: {e}", severity="error", timeout=6)

        self.push_screen(ConnectDialog(), do_connect)

    def action_jump(self) -> None:
        pane = self._active_pane()
        def on_result(path: Path | None) -> None:
            if path:
                pane.navigate_to(path)
        self.push_screen(JumpScreen(pane.cwd), on_result)

    # ── F3 View ────────────────────────────────────────────────────────────

    def action_view_file(self) -> None:
        entry = self._active_pane().active_entry
        if entry is None:
            return
        if entry.is_dir:
            self.notify("Select a file to view", severity="warning")
            return
        self.push_screen(ViewerScreen(entry.path))

    # ── F4 Edit ────────────────────────────────────────────────────────────

    def action_edit_file(self) -> None:
        entry = self._active_pane().active_entry
        if entry is None:
            return
        if entry.is_dir:
            self.notify("Select a file to edit", severity="warning")
            return
        editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "nano"
        with self.suspend():
            subprocess.run([editor, str(entry.path)])
        self._active_pane().refresh_listing()

    # ── F5 Copy ────────────────────────────────────────────────────────────

    def action_copy_file(self) -> None:
        src_entry = self._active_pane().active_entry
        dst_dir = self._inactive_pane().cwd
        if src_entry is None:
            self.notify("Nothing selected", severity="warning")
            return

        dst = dst_dir / src_entry.name
        msg = f"Copy [bold]{src_entry.name}[/bold]\n  → {dst_dir}"
        if dst.exists():
            msg += f"\n\n[yellow]'{src_entry.name}' already exists — overwrite?[/yellow]"

        inactive = self._inactive_pane()

        def do_copy(confirmed: bool) -> None:
            if not confirmed:
                return
            try:
                if src_entry.is_dir:
                    if dst.exists():
                        shutil.rmtree(dst)
                    shutil.copytree(str(src_entry.path), str(dst))
                else:
                    shutil.copy2(str(src_entry.path), str(dst))
                inactive.refresh_listing()
                self.notify(f"Copied {src_entry.name}")
            except OSError as e:
                self.notify(f"Copy failed: {e}", severity="error")

        self.push_screen(ConfirmDialog(msg, title="Copy"), do_copy)

    # ── F7 MkDir ───────────────────────────────────────────────────────────

    def action_mkdir(self) -> None:
        pane = self._active_pane()

        def do_mkdir(name: str | None) -> None:
            if not name:
                return
            target = pane.cwd / name
            try:
                target.mkdir(parents=False, exist_ok=False)
                pane.refresh_listing()
                self.notify(f"Created {name}/")
            except FileExistsError:
                self.notify(f"'{name}' already exists", severity="error")
            except OSError as e:
                self.notify(f"MkDir failed: {e}", severity="error")

        self.push_screen(InputDialog("New directory name:", default=""), do_mkdir)

    # ── F8 Delete ──────────────────────────────────────────────────────────

    def action_delete_file(self) -> None:
        entry = self._active_pane().active_entry
        if entry is None:
            return

        kind = "directory" if entry.is_dir else "file"
        msg = f"Delete {kind} [bold]{entry.name}[/bold]?"
        if entry.is_dir:
            msg += "\n\n[yellow]This will delete all contents recursively.[/yellow]"

        pane = self._active_pane()

        def do_delete(confirmed: bool) -> None:
            if not confirmed:
                return
            try:
                if entry.is_dir:
                    shutil.rmtree(str(entry.path))
                else:
                    entry.path.unlink()
                pane.refresh_listing()
                self.notify(f"Deleted {entry.name}")
            except OSError as e:
                self.notify(f"Delete failed: {e}", severity="error")

        self.push_screen(ConfirmDialog(msg, title="Delete"), do_delete)

    # ── Title ──────────────────────────────────────────────────────────────

    def get_default_screen(self):
        screen = super().get_default_screen()
        screen.title = "porter"
        return screen
