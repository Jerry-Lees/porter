"""PorterApp — top-level Textual application."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual import events

from porter.widgets.fkey_bar import FKeyBar
from porter.widgets.jump_bar import JumpScreen
from porter.widgets.pane import FilePane
from porter.widgets.viewer import ViewerScreen


class PorterApp(App):
    """Porter — dual-pane terminal file manager."""

    CSS_PATH = "porter.tcss"


    BINDINGS = [
        Binding("f3",  "view_file",     "View",    show=False, priority=True),
        Binding("f4",  "edit_file",     "Edit",    show=False, priority=True),
        Binding("f5",  "copy_file",     "Copy",    show=False, priority=True),
        Binding("ctrl+h", "toggle_hidden",  "Hidden",  show=False, priority=True),
        Binding("ctrl+r", "refresh_pane",   "Refresh", show=False, priority=True),
        Binding("alt+left", "go_back",      "Back",    show=False, priority=True),
        Binding("grave_accent", "context_menu", "Menu", show=False, priority=True),
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
        """Make *side* ("left" or "right") the active pane."""
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

    # ── Key handling — Tab must be caught here, not in BINDINGS ───────────

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
        self.notify("Context menu — coming soon", timeout=1.5)

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

    # ── F5 Copy (stub) ─────────────────────────────────────────────────────

    def action_copy_file(self) -> None:
        src = self._active_pane().active_entry
        dst_dir = self._inactive_pane().cwd
        if src is None:
            self.notify("Nothing selected", severity="warning")
            return
        self.notify(f"Copy: {src.name} → {dst_dir}  (not yet implemented)")

    # ── Title ──────────────────────────────────────────────────────────────

    def get_default_screen(self):
        screen = super().get_default_screen()
        screen.title = "porter"
        return screen
