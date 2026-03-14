"""ConnectDialog — SSH host picker and manual entry."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, ListView, ListItem

from porter.fs.ssh_config import SSHHost, load_ssh_config, load_saved_hosts, save_host


class ConnectDialog(ModalScreen[SSHHost | None]):
    """Pick a host from ~/.ssh/config, saved connections, or type one manually."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", priority=True)]

    DEFAULT_CSS = """
    ConnectDialog {
        align: center middle;
    }
    ConnectDialog > Vertical {
        width: 70;
        height: auto;
        max-height: 85%;
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
        max-height: 8;
        border: solid $panel-lighten-1;
        margin-bottom: 1;
    }
    ConnectDialog Input {
        width: 100%;
        color: white;
        margin-bottom: 1;
    }
    ConnectDialog Checkbox {
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
        self._saved_hosts = load_saved_hosts()

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("[bold]Connect to SSH host[/bold]")

            if self._ssh_hosts:
                yield Label("Known hosts (~/.ssh/config):", classes="section")
                items = [ListItem(Label(f"{h.alias}  ({h.hostname})"), id=f"ssh-{i}")
                         for i, h in enumerate(self._ssh_hosts)]
                yield ListView(*items, id="ssh-list")

            if self._saved_hosts:
                yield Label("Saved connections:", classes="section")
                items = [ListItem(Label(f"{h.alias}  ({h.username}@{h.hostname}:{h.port})"), id=f"saved-{i}")
                         for i, h in enumerate(self._saved_hosts)]
                yield ListView(*items, id="saved-list")

            yield Label("Or enter manually  (user@host:port):", classes="section")
            yield Input(placeholder="e.g.  pi@raspberrypi.local  or  admin@10.0.0.5:2222",
                        id="manual-input")
            yield Checkbox("Save this connection", id="save-check")

            with Horizontal():
                yield Button("Connect", id="connect", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        if self._ssh_hosts:
            self.query_one("#ssh-list", ListView).focus()
        elif self._saved_hosts:
            self.query_one("#saved-list", ListView).focus()
        else:
            self.query_one(Input).focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id or ""
        if item_id.startswith("ssh-"):
            idx = int(item_id[4:])
            self.dismiss(self._ssh_hosts[idx])
        elif item_id.startswith("saved-"):
            idx = int(item_id[6:])
            self.dismiss(self._saved_hosts[idx])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id == "connect":
            self._connect_manual()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._connect_manual()

    def _connect_manual(self) -> None:
        raw = self.query_one("#manual-input", Input).value.strip()
        if not raw:
            # If a list item is highlighted, use that
            for list_id, hosts in (("ssh-list", self._ssh_hosts), ("saved-list", self._saved_hosts)):
                try:
                    lv = self.query_one(f"#{list_id}", ListView)
                    idx = lv.index
                    if idx is not None and 0 <= idx < len(hosts):
                        self.dismiss(hosts[idx])
                        return
                except Exception:
                    pass
            return

        # Parse  user@host:port
        user = ""
        if "@" in raw:
            user, _, raw = raw.partition("@")
        host, _, port_str = raw.partition(":")
        port = int(port_str) if port_str.isdigit() else 22

        alias = f"{user}@{host}" if user else host
        ssh_host = SSHHost(alias=alias, hostname=host, username=user, port=port)

        try:
            should_save = self.query_one("#save-check", Checkbox).value
        except Exception:
            should_save = False

        if should_save:
            try:
                save_host(ssh_host)
            except Exception:
                pass

        self.dismiss(ssh_host)

    def action_cancel(self) -> None:
        self.dismiss(None)
