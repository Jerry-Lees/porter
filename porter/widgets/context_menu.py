"""ContextMenu — stub for v0.1.  Will be a flyout menu in a future version."""

from __future__ import annotations

from textual.widget import Widget


class ContextMenu(Widget):
    """Placeholder.  Right-click and backtick bindings are wired in the App
    but call a no-op until this is implemented."""

    def show_for(self, x: int, y: int) -> None:
        self.app.notify("Context menu — coming soon", timeout=1.5)
