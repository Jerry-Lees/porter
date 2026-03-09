"""ConnectDialog — SSH host picker and manual entry."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListView, ListItem

from porter.fs.ssh_config import SSHHost, load_ssh_config


class ConnectDialog(ModalScreen[SSHHost | None]):
    """Pick a host from ~/.ssh/config or type one manually."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", priority=True)]

    DEFAULT_CSS = """
    ConnectDialog {
        align: center middle;
    }
    ConnectDialog > Vertical {
        width: 70;
        height: auto;
        max-height: 80%;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    ConnectDialog Label.section {
        color: $accent;
        margin-top: 1;
    }
    ConnectDialog ListView {
        height: auto;
        max-height: 12;
        border: solid $panel-lighten-1;
        margin-bottom: 1;
    }
    ConnectDialog Input {
        width: 100%;
        color: white;
        margin-bottom: 1;
    }
    ConnectDialog Horizontal {
        height: auto;
        align: right middle;
    }
    ConnectDialog Button {
        margin-left: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._ssh_hosts = load_ssh_config()

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[bold]Connect to SSH host[/bold]")

            if self._ssh_hosts:
                yield Label("Known hosts (~/.ssh/config):", classes="section")
                items = [ListItem(Label(f"{h.alias}  ({h.hostname})"), id=f"host-{i}")
                         for i, h in enumerate(self._ssh_hosts)]
                yield ListView(*items, id="host-list")

            yield Label("Or enter manually  (user@host:port):", classes="section")
            yield Input(placeholder="e.g.  pi@raspberrypi.local  or  admin@10.0.0.5:2222",
                        id="manual-input")

            with Horizontal():
                yield Button("Connect", id="connect", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        if self._ssh_hosts:
            self.query_one(ListView).focus()
        else:
            self.query_one(Input).focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # Double-click / Enter on a list item — connect immediately
        idx = int(event.item.id.split("-")[1])
        self.dismiss(self._ssh_hosts[idx])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id == "connect":
            self._connect_manual()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._connect_manual()

    def _connect_manual(self) -> None:
        raw = self.query_one(Input).value.strip()
        if not raw:
            # If a list item is highlighted, use that
            lv = self.query(ListView)
            if lv and self._ssh_hosts:
                lv_widget = lv.first()
                idx = lv_widget.index
                if idx is not None and 0 <= idx < len(self._ssh_hosts):
                    self.dismiss(self._ssh_hosts[idx])
                    return
            return

        # Parse  user@host:port
        user = ""
        if "@" in raw:
            user, _, raw = raw.partition("@")
        host, _, port_str = raw.partition(":")
        port = int(port_str) if port_str.isdigit() else 22

        self.dismiss(SSHHost(
            alias=host,
            hostname=host,
            username=user,
            port=port,
        ))

    def action_cancel(self) -> None:
        self.dismiss(None)
