"""FKeyBar — mc-style function-key strip at the bottom of the screen."""

from __future__ import annotations

from rich.text import Text
from textual.widget import Widget

# Default key definitions: (number, label)
_FKEYS = [
    (3,  "View"),
    (4,  "Edit"),
    (5,  "Copy"),
    (6,  "Move"),
    (7,  "MkDir"),
    (8,  "Del"),
]


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
        for num, label in _FKEYS:
            text.append(f" F{num} ", style="bold black on #5f87af")
            text.append(f"{label} ", style="white on #005f87")
        text.append(" ^N ", style="bold black on #5f87af")
        text.append("Archive ", style="white on #005f87")
        text.append(" ^O ", style="bold black on #5f87af")
        text.append("Connect ", style="white on #005f87")
        text.append(" ^Q ", style="bold black on #5f87af")
        text.append("Quit ", style="white on #005f87")
        return text
