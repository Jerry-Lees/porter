"""FKeyBar — mc-style function-key strip at the bottom of the screen."""

from __future__ import annotations

from rich.text import Text
from textual.widget import Widget

class FKeyBar(Widget):
    DEFAULT_CSS = """
    FKeyBar {
        height: 1;
        dock: bottom;
        background: $panel-darken-1;
    }
    """

    def render(self) -> Text:
        text = Text(no_wrap=True, overflow="ellipsis")
        keys = [
            ("F1", "Help"),
            ("F3", "View"),
            ("F4", "Edit"),
            ("F5", "Copy"),
            ("F6", "Move"),
            ("F7", "MkDir"),
            ("F8", "Del"),
            ("^N", "Archive"),
            ("^O", "Connect"),
            (" .", "Hidden"),
            ("^Q", "Quit"),
        ]
        for key, label in keys:
            text.append(f" {key} ", style="bold black on #5f87af")
            text.append(f"{label} ", style="white on #005f87")
        return text
