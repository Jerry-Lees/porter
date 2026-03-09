"""PorterApp — top-level Textual application."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual import events

from porter.widgets.fkey_bar import FKeyBar
from porter.widgets.pane import FilePane


class PorterApp(App):
    """Porter — dual-pane terminal file manager."""

    CSS_PATH = "porter.tcss"

    BINDINGS = [
        Binding("f10", "quit", "Quit"),
        Binding("ctrl+h", "toggle_hidden", "Hidden", show=False),
        Binding("ctrl+r", "refresh_pane", "Refresh", show=False),
        Binding("alt+left", "go_back", "Back", show=False),
        Binding("grave_accent", "context_menu", "Menu", show=False),  # backtick
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

    # ── Actions ────────────────────────────────────────────────────────────

    def action_toggle_hidden(self) -> None:
        self._active_pane().toggle_hidden()

    def action_refresh_pane(self) -> None:
        self._active_pane().refresh_listing()

    def action_go_back(self) -> None:
        self._active_pane().go_back()

    def action_context_menu(self) -> None:
        self.notify("Context menu — coming soon", timeout=1.5)

    # ── F5 Copy (stub) ─────────────────────────────────────────────────────

    def action_copy(self) -> None:
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
