"""SFTPFilesystem — remote filesystem via paramiko SFTP."""

from __future__ import annotations

import shlex
import stat as stat_module
from pathlib import Path, PurePosixPath

import paramiko

from porter.fs.base import Filesystem
from porter.models.entry import FileEntry

# We use PurePosixPath for remote paths (always POSIX, even from Windows client)
RemotePath = PurePosixPath


class SFTPFilesystem(Filesystem):
    """SFTP-backed filesystem.  Call connect() before use."""

    def __init__(self, hostname: str, username: str | None = None,
                 port: int = 22, key_filename: str | None = None,
                 proxy_jump: str | None = None) -> None:
        self._hostname = hostname
        self._username = username
        self._port = port
        self._key_filename = key_filename
        self._proxy_jump = proxy_jump
        self._client: paramiko.SSHClient | None = None
        self._sftp: paramiko.SFTPClient | None = None
        self._home: Path = Path("/")

    # ── Connection ─────────────────────────────────────────────────────────

    def connect(self) -> None:
        """Open SSH connection and SFTP channel.  Raises paramiko exceptions on failure."""
        sock = self._make_socket()
        self._client = paramiko.SSHClient()
        self._client.load_system_host_keys()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._client.connect(
            hostname=self._hostname,
            port=self._port,
            username=self._username,
            key_filename=self._key_filename,
            sock=sock,
        )
        self._sftp = self._client.open_sftp()
        # Resolve remote home directory
        try:
            _, stdout, _ = self._client.exec_command("echo $HOME")
            remote_home = stdout.read().decode().strip()
            if remote_home:
                self._home = Path(remote_home)
        except Exception:
            self._home = Path("/home") / (self._username or "")

    def _make_socket(self):
        """Return a socket, optionally tunnelled through a ProxyJump host."""
        if not self._proxy_jump:
            return None  # paramiko uses direct TCP
        # ProxyJump: open a channel through the bastion
        jump_client = paramiko.SSHClient()
        jump_client.load_system_host_keys()
        jump_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        jump_host, _, jump_port_str = self._proxy_jump.partition(":")
        jump_port = int(jump_port_str) if jump_port_str else 22
        jump_client.connect(jump_host, port=jump_port)
        transport = jump_client.get_transport()
        dest_addr = (self._hostname, self._port)
        local_addr = ("", 0)
        return transport.open_channel("direct-tcpip", dest_addr, local_addr)

    def disconnect(self) -> None:
        if self._sftp:
            self._sftp.close()
        if self._client:
            self._client.close()

    def is_connected(self) -> bool:
        return self._sftp is not None

    # ── Filesystem interface ───────────────────────────────────────────────

    @property
    def label(self) -> str:
        user = f"{self._username}@" if self._username else ""
        port = f":{self._port}" if self._port != 22 else ""
        return f"{user}{self._hostname}{port}"

    @property
    def home(self) -> Path:
        return self._home

    def listdir(self, path: Path, show_hidden: bool = False) -> list[FileEntry]:
        assert self._sftp, "Not connected"
        entries: list[FileEntry] = []
        try:
            for attr in self._sftp.listdir_attr(str(path)):
                if not show_hidden and attr.filename.startswith("."):
                    continue
                if attr.st_mode is None:
                    continue
                entries.append(self._attr_to_entry(path / attr.filename, attr))
        except IOError:
            pass
        entries.sort(key=lambda e: (not e.is_dir, e.name.lower()))
        return entries

    def stat(self, path: Path) -> FileEntry:
        assert self._sftp, "Not connected"
        attr = self._sftp.stat(str(path))
        return self._attr_to_entry(path, attr)

    def same_server_as(self, other: "SFTPFilesystem") -> bool:
        return self._hostname == other._hostname and self._port == other._port

    def download(self, remote_path: Path, local_dst_dir: Path) -> None:
        """Download a remote file or directory tree into local_dst_dir."""
        assert self._sftp, "Not connected"
        attr = self._sftp.stat(str(remote_path))
        if stat_module.S_ISDIR(attr.st_mode or 0):
            self._download_dir(remote_path, local_dst_dir / remote_path.name)
        else:
            local_dst_dir.mkdir(parents=True, exist_ok=True)
            self._sftp.get(str(remote_path), str(local_dst_dir / remote_path.name))

    def _download_dir(self, remote_path: Path, local_path: Path) -> None:
        local_path.mkdir(parents=True, exist_ok=True)
        for attr in self._sftp.listdir_attr(str(remote_path)):
            child_remote = remote_path / attr.filename
            if stat_module.S_ISDIR(attr.st_mode or 0):
                self._download_dir(child_remote, local_path / attr.filename)
            else:
                self._sftp.get(str(child_remote), str(local_path / attr.filename))

    def upload(self, local_path: Path, remote_dst_dir: Path) -> None:
        """Upload a local file or directory tree into remote_dst_dir."""
        assert self._sftp and self._client, "Not connected"
        if local_path.is_dir():
            remote_subdir = remote_dst_dir / local_path.name
            self._mkdir_remote(remote_subdir)
            for child in local_path.iterdir():
                self.upload(child, remote_subdir)
        else:
            self._sftp.put(str(local_path), str(remote_dst_dir / local_path.name))

    def _mkdir_remote(self, path: Path) -> None:
        _, _, stderr = self._client.exec_command(
            f"mkdir -p {shlex.quote(str(path))}"
        )
        err = stderr.read().decode().strip()
        if err:
            raise OSError(err)

    def copy_remote(self, src: Path, dst_dir: Path) -> None:
        """Server-side copy of src into dst_dir (cp -r)."""
        assert self._client, "Not connected"
        dst = dst_dir / src.name
        _, _, stderr = self._client.exec_command(
            f"cp -r {shlex.quote(str(src))} {shlex.quote(str(dst))}"
        )
        err = stderr.read().decode().strip()
        if err:
            raise OSError(err)

    def move_remote(self, src: Path, dst_dir: Path) -> None:
        """Server-side move of src into dst_dir (mv)."""
        assert self._client, "Not connected"
        dst = dst_dir / src.name
        _, _, stderr = self._client.exec_command(
            f"mv {shlex.quote(str(src))} {shlex.quote(str(dst))}"
        )
        err = stderr.read().decode().strip()
        if err:
            raise OSError(err)

    def remove(self, path: Path) -> None:
        """Remove a file or directory tree on the remote host."""
        assert self._sftp and self._client, "Not connected"
        try:
            attr = self._sftp.stat(str(path))
        except IOError as e:
            raise OSError(str(e)) from e
        if stat_module.S_ISDIR(attr.st_mode or 0):
            # Use rm -rf over SSH — SFTP-only recursive delete is painfully slow
            _, _, stderr = self._client.exec_command(
                f"rm -rf {shlex.quote(str(path))}"
            )
            err = stderr.read().decode().strip()
            if err:
                raise OSError(err)
        else:
            try:
                self._sftp.remove(str(path))
            except IOError as e:
                raise OSError(str(e)) from e

    # ── Internal ───────────────────────────────────────────────────────────

    def _attr_to_entry(self, path: Path, attr: paramiko.SFTPAttributes) -> FileEntry:
        mode = attr.st_mode or 0
        uid = attr.st_uid or 0
        gid = attr.st_gid or 0
        # Paramiko doesn't resolve usernames — show numeric IDs
        return FileEntry(
            name=path.name,
            path=path,
            is_dir=stat_module.S_ISDIR(mode),
            is_link=stat_module.S_ISLNK(mode),
            size=attr.st_size or 0,
            mode=mode,
            uid=uid,
            gid=gid,
            owner=str(uid),
            group=str(gid),
            mtime=float(attr.st_mtime or 0),
        )
