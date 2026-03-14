"""Read ~/.ssh/config and return connection parameters for known hosts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

SAVED_HOSTS_PATH = Path.home() / ".config" / "porter" / "hosts.yaml"


@dataclass
class SSHHost:
    alias: str          # the Host block name
    hostname: str       # HostName (or alias if not specified)
    username: str = ""
    port: int = 22
    identity_file: str = ""
    proxy_jump: str = ""


def load_saved_hosts(path: Path | None = None) -> list[SSHHost]:
    """Load porter-saved connection profiles from ~/.config/porter/hosts.yaml."""
    p = path or SAVED_HOSTS_PATH
    if not p.exists():
        return []
    try:
        data = yaml.safe_load(p.read_text()) or []
        hosts = []
        for d in data:
            if isinstance(d, dict) and "hostname" in d:
                hosts.append(SSHHost(
                    alias=d.get("alias", d["hostname"]),
                    hostname=d["hostname"],
                    username=d.get("username", ""),
                    port=int(d.get("port", 22)),
                    identity_file=d.get("identity_file", ""),
                    proxy_jump=d.get("proxy_jump", ""),
                ))
        return hosts
    except Exception:
        return []


def save_host(host: SSHHost, path: Path | None = None) -> None:
    """Persist a connection profile to ~/.config/porter/hosts.yaml."""
    p = path or SAVED_HOSTS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = load_saved_hosts(p)
    for i, h in enumerate(existing):
        if h.alias == host.alias:
            existing[i] = host
            break
    else:
        existing.append(host)
    data = [
        {
            "alias": h.alias,
            "hostname": h.hostname,
            "username": h.username,
            "port": h.port,
            "identity_file": h.identity_file,
            "proxy_jump": h.proxy_jump,
        }
        for h in existing
    ]
    p.write_text(yaml.dump(data, default_flow_style=False))


def load_ssh_config(config_path: Path | None = None) -> list[SSHHost]:
    """Parse ~/.ssh/config and return a list of SSHHost entries.
    Skips wildcard patterns (Host * or Host *.example.com)."""
    path = config_path or Path.home() / ".ssh" / "config"
    if not path.exists():
        return []

    hosts: list[SSHHost] = []
    current_alias: str | None = None
    current: dict[str, str] = {}

    def _flush() -> None:
        if current_alias and "*" not in current_alias:
            hosts.append(SSHHost(
                alias=current_alias,
                hostname=current.get("hostname", current_alias),
                username=current.get("user", ""),
                port=int(current.get("port", 22)),
                identity_file=_expand(current.get("identityfile", "")),
                proxy_jump=current.get("proxyjump", ""),
            ))

    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition(" ")
        key = key.lower()
        value = value.strip()
        if key == "host":
            _flush()
            current_alias = value
            current = {}
        elif current_alias:
            current[key] = value

    _flush()
    return hosts


def _expand(path: str) -> str:
    if not path:
        return ""
    return str(Path(path).expanduser())
