"""Reusable confirmation and input dialogs."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListView, ListItem


class ConfirmDialog(ModalScreen[bool]):
    """Yes / No confirmation dialog."""

    BINDINGS = [
        Binding("y", "yes", "Yes", priority=True),
        Binding("n", "no", "No", priority=True),
        Binding("escape", "no", "Cancel", priority=True),
    ]

    DEFAULT_CSS = """
    ConfirmDialog {
        align: center middle;
    }
    ConfirmDialog > Vertical {
        width: 60;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    ConfirmDialog Label {
        width: 100%;
        margin-bottom: 1;
    }
    ConfirmDialog Horizontal {
        width: 100%;
        height: auto;
        align: center middle;
    }
    ConfirmDialog Button {
        margin: 0 2;
    }
    """

    def __init__(self, message: str, title: str = "Confirm") -> None:
        super().__init__()
        self._message = message
        self._title = title

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"[bold]{self._title}[/bold]")
            yield Label(self._message)
            with Horizontal():
                yield Button("Yes (Y)", id="yes", variant="error")
                yield Button("No (N)", id="no", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#no", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def action_yes(self) -> None:
        self.dismiss(True)

    def action_no(self) -> None:
        self.dismiss(False)


class InputDialog(ModalScreen[str | None]):
    """Single-line text input dialog."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", priority=True)]

    DEFAULT_CSS = """
    InputDialog {
        align: center middle;
    }
    InputDialog > Vertical {
        width: 60;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    InputDialog Label {
        width: 100%;
        margin-bottom: 1;
    }
    InputDialog Input {
        width: 100%;
        color: white;
    }
    """

    def __init__(self, prompt: str, default: str = "") -> None:
        super().__init__()
        self._prompt = prompt
        self._default = default

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self._prompt)
            yield Input(value=self._default, id="input")

    def on_mount(self) -> None:
        inp = self.query_one(Input)
        inp.focus()
        inp.cursor_position = len(inp.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        self.dismiss(value if value else None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class SnapshotDiffDialog(ModalScreen[str | None]):
    """Show changed/new files since snapshot and prompt for archive name."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", priority=True)]

    DEFAULT_CSS = """
    SnapshotDiffDialog {
        align: center middle;
    }
    SnapshotDiffDialog > Vertical {
        width: 72;
        height: auto;
        max-height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    SnapshotDiffDialog ListView {
        height: auto;
        max-height: 14;
        border: solid $panel-lighten-1;
        margin-bottom: 1;
    }
    SnapshotDiffDialog Input {
        width: 100%;
        color: white;
        margin-bottom: 1;
    }
    SnapshotDiffDialog Horizontal {
        height: auto;
        align: right middle;
    }
    SnapshotDiffDialog Button { margin-left: 1; }
    """

    def __init__(self, changed: list[tuple[str, str]], default_name: str = "changes.tar.gz",
                 base: str = "") -> None:
        super().__init__()
        self._changed = changed   # list of ("NEW"|"MOD", relative_path_str)
        self._default = default_name
        self._base = base

    def compose(self) -> ComposeResult:
        with Vertical():
            base_info = f" (from [bold]{self._base}[/bold])" if self._base else ""
            yield Label(f"[bold]{len(self._changed)} file(s) changed or new[/bold]{base_info}")
            items = []
            for status, rel in self._changed:
                color = "green" if status == "NEW" else "yellow"
                items.append(ListItem(Label(f"[{color}]{status}[/]  {rel}")))
            yield ListView(*items)
            yield Label("Archive name (created in other pane):")
            yield Input(value=self._default, id="name-input")
            with Horizontal():
                yield Button("Create", id="ok", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        inp = self.query_one("#name-input", Input)
        inp.focus()
        inp.cursor_position = len(inp.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
        else:
            val = self.query_one("#name-input", Input).value.strip()
            self.dismiss(val or None)

    def on_input_submitted(self, _: Input.Submitted) -> None:
        val = self.query_one("#name-input", Input).value.strip()
        self.dismiss(val or None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class SystemSnapshotDialog(ModalScreen[list[str] | None]):
    """Review exclusions and confirm before taking a system-wide snapshot from /."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", priority=True)]

    # Full-path prefixes — entire subtree is skipped
    DEFAULT_EXCLUDED_PATHS: list[str] = [
        "/proc", "/sys", "/dev", "/run", "/tmp",
        "/var/tmp", "/var/log", "/var/cache", "/var/run",
        "/snap", "/mnt", "/media",
    ]

    # Directory name patterns — skipped wherever they appear in the tree
    DEFAULT_EXCLUDED_NAMES: list[str] = [
        ".git", "__pycache__", "node_modules", ".venv", ".cache",
    ]

    DEFAULT_CSS = """
    SystemSnapshotDialog {
        align: center middle;
    }
    SystemSnapshotDialog > Vertical {
        width: 72;
        height: auto;
        max-height: 85%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    SystemSnapshotDialog Label.section {
        color: $accent;
        margin-top: 1;
    }
    SystemSnapshotDialog #add-row {
        height: auto;
        margin-bottom: 1;
    }
    SystemSnapshotDialog #add-row Input {
        width: 1fr;
        color: white;
    }
    SystemSnapshotDialog #add-row Button {
        width: auto;
        margin-left: 1;
    }
    SystemSnapshotDialog Horizontal.buttons {
        height: auto;
        align: right middle;
        margin-top: 1;
    }
    SystemSnapshotDialog Horizontal.buttons Button {
        margin-left: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._custom: list[str] = []

    def compose(self) -> ComposeResult:
        paths_str = "  ".join(self.DEFAULT_EXCLUDED_PATHS)
        names_str = "  ".join(self.DEFAULT_EXCLUDED_NAMES)
        with Vertical():
            yield Label("[bold]System Snapshot[/bold] — indexes every file from /")
            yield Label("This may take 15–30 seconds on a typical system.", classes="section")
            yield Label("Excluded path prefixes (entire subtree skipped):", classes="section")
            yield Label(f"  {paths_str}")
            yield Label("Excluded directory names (skipped anywhere in tree):", classes="section")
            yield Label(f"  {names_str}")
            yield Label("Add custom exclusion (full path or directory name):", classes="section")
            with Horizontal(id="add-row"):
                yield Input(placeholder="/path/to/skip  or  dirname", id="excl-input")
                yield Button("Add", id="add-btn")
            yield Label("Custom: (none)", id="custom-label")
            with Horizontal(classes="buttons"):
                yield Button("Take Snapshot", id="ok", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#excl-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id == "add-btn":
            self._add_custom()
        elif event.button.id == "ok":
            self._submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "excl-input":
            self._add_custom()

    def _add_custom(self) -> None:
        val = self.query_one("#excl-input", Input).value.strip()
        if val and val not in self._custom:
            self._custom.append(val)
            self.query_one("#custom-label", Label).update(
                "Custom: " + "  ".join(self._custom)
            )
        self.query_one("#excl-input", Input).clear()

    def _submit(self) -> None:
        self.dismiss(
            self.DEFAULT_EXCLUDED_PATHS + self.DEFAULT_EXCLUDED_NAMES + self._custom
        )

    def action_cancel(self) -> None:
        self.dismiss(None)
