"""Read ~/.ssh/config and return connection parameters for known hosts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SSHHost:
    alias: str          # the Host block name
    hostname: str       # HostName (or alias if not specified)
    username: str = ""
    port: int = 22
    identity_file: str = ""
    proxy_jump: str = ""


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
