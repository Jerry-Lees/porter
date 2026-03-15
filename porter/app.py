"""PorterApp — top-level Textual application."""

from __future__ import annotations

import grp
import hashlib
import io
import os
import platform
import pwd
import shutil
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path

import yaml


# ── Manifest helpers ───────────────────────────────────────────────────────────

def _gather_packages() -> dict:
    """Query the system package manager for installed packages."""
    if shutil.which("dpkg-query"):
        try:
            r = subprocess.run(
                ["dpkg-query", "-W", "-f=${Package}\t${Version}\n"],
                capture_output=True, text=True, timeout=60,
            )
            pkgs = []
            for line in r.stdout.strip().splitlines():
                if "\t" in line:
                    name, ver = line.split("\t", 1)
                    pkgs.append({"name": name.strip(), "version": ver.strip()})
            return {"manager": "apt/dpkg", "count": len(pkgs), "installed": pkgs}
        except Exception:
            pass

    if shutil.which("rpm"):
        try:
            r = subprocess.run(
                ["rpm", "-qa", "--queryformat", "%{NAME}\t%{VERSION}-%{RELEASE}\n"],
                capture_output=True, text=True, timeout=60,
            )
            pkgs = []
            for line in r.stdout.strip().splitlines():
                if "\t" in line:
                    name, ver = line.split("\t", 1)
                    pkgs.append({"name": name.strip(), "version": ver.strip()})
            pkgs.sort(key=lambda x: x["name"])
            return {"manager": "rpm", "count": len(pkgs), "installed": pkgs}
        except Exception:
            pass

    if shutil.which("pacman"):
        try:
            r = subprocess.run(["pacman", "-Q"], capture_output=True, text=True, timeout=60)
            pkgs = []
            for line in r.stdout.strip().splitlines():
                parts = line.split(None, 1)
                if len(parts) == 2:
                    pkgs.append({"name": parts[0], "version": parts[1]})
            return {"manager": "pacman", "count": len(pkgs), "installed": pkgs}
        except Exception:
            pass

    return {"manager": "unknown", "count": 0, "installed": [],
            "note": "Could not detect package manager"}


def _gather_systemd_services() -> list[str]:
    """Return names of active systemd service units."""
    if not shutil.which("systemctl"):
        return []
    try:
        r = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--state=active",
             "--no-pager", "--no-legend"],
            capture_output=True, text=True, timeout=15,
        )
        services = []
        for line in r.stdout.strip().splitlines():
            parts = line.split()
            if parts and parts[0].endswith(".service"):
                services.append(parts[0])
        return sorted(services)
    except Exception:
        return []


def _gather_local_users() -> list[dict]:
    """Return non-system user accounts (uid 1000–60000)."""
    users = []
    for p in pwd.getpwall():
        if 1000 <= p.pw_uid < 60000:
            try:
                primary_group = grp.getgrgid(p.pw_gid).gr_name
            except KeyError:
                primary_group = str(p.pw_gid)
            users.append({
                "username": p.pw_name,
                "uid": p.pw_uid,
                "gid": p.pw_gid,
                "primary_group": primary_group,
                "home": p.pw_dir,
                "shell": p.pw_shell,
            })
    return sorted(users, key=lambda u: u["uid"])


def _read_os_info() -> dict:
    """Parse /etc/os-release into a dict."""
    info: dict[str, str] = {}
    os_release = Path("/etc/os-release")
    if os_release.exists():
        for line in os_release.read_text().splitlines():
            if "=" in line:
                k, _, v = line.partition("=")
                info[k.lower()] = v.strip().strip('"')
    return info


def _build_manifest(
    base: Path,
    changed: list[tuple[str, str]],
    changed_paths: list[Path],
) -> bytes:
    """Build a YAML manifest describing the diff archive contents."""
    os_info = _read_os_info()

    file_entries = []
    for (status, _rel), p in zip(changed, changed_paths):
        try:
            st = p.stat()
            try:
                owner = pwd.getpwuid(st.st_uid).pw_name
            except KeyError:
                owner = str(st.st_uid)
            try:
                group = grp.getgrgid(st.st_gid).gr_name
            except KeyError:
                group = str(st.st_gid)
            sha256 = hashlib.sha256(p.read_bytes()).hexdigest()
            file_entries.append({
                "path": str(p),
                "archive_path": str(p).lstrip("/"),
                "status": status,
                "mode": oct(st.st_mode & 0o7777),
                "owner": owner,
                "group": group,
                "uid": st.st_uid,
                "gid": st.st_gid,
                "size_bytes": st.st_size,
                "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                "sha256": sha256,
            })
        except OSError:
            pass

    manifest = {
        "porter_manifest": {
            "version": "1.0",
            "created": datetime.now().isoformat(timespec="seconds"),
            "hostname": socket.gethostname(),
            "source_base": str(base),
            "file_count": len(file_entries),
        },
        "os": {
            "pretty_name": os_info.get("pretty_name", platform.system()),
            "id": os_info.get("id", ""),
            "version_id": os_info.get("version_id", ""),
            "kernel": platform.release(),
            "arch": platform.machine(),
        },
        "extraction": {
            "command": "sudo tar -xzf <archive_name> -C /",
            "notes": [
                "Files are stored with absolute paths from /.",
                "Extract to / to place files in their correct locations.",
                "Verify uid/gid match after extraction — create users first if needed.",
                "Enable any required systemd services after extraction.",
            ],
        },
        "local_users": _gather_local_users(),
        "systemd_services": {
            "note": "Services that were active on the source system",
            "active": _gather_systemd_services(),
        },
        "packages": _gather_packages(),
        "files": file_entries,
    }

    return yaml.dump(manifest, default_flow_style=False, sort_keys=False,
                     allow_unicode=True).encode("utf-8")

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual import events

from porter.widgets.confirm_dialog import ConfirmDialog, InputDialog, SnapshotDiffDialog, SystemSnapshotDialog
from porter.widgets.connect_dialog import ConnectDialog
from porter.widgets.context_menu import ContextMenu
from porter.widgets.fkey_bar import FKeyBar
from porter.widgets.jump_bar import JumpScreen
from porter.widgets.pane import FilePane
from porter.widgets.viewer import ViewerScreen
from porter.fs.sftp import SFTPFilesystem
from porter.fs.ssh_config import SSHHost
from porter.fs.archive import ArchiveFilesystem
from porter.fs.local import LocalFilesystem
from porter.widgets.file_table import FileTable


class PorterApp(App):
    """Porter — dual-pane terminal file manager."""

    CSS_PATH = "porter.tcss"

    BINDINGS = [
        Binding("f3",  "view_file",     "View",    show=False, priority=True),
        Binding("f4",  "edit_file",     "Edit",    show=False, priority=True),
        Binding("f5",  "copy_file",     "Copy",    show=False, priority=True),
        Binding("f6",  "move_file",     "Move",    show=False, priority=True),
        Binding("f7",  "mkdir",         "MkDir",   show=False, priority=True),
        Binding("f8",  "delete_file",   "Delete",  show=False, priority=True),
        Binding("ctrl+h", "toggle_hidden",  "Hidden",  show=False, priority=True),
        Binding("ctrl+r", "refresh_pane",   "Refresh", show=False, priority=True),
        Binding("alt+left", "go_back",      "Back",    show=False, priority=True),
        Binding("grave_accent", "context_menu", "Menu", show=False, priority=True),
        Binding("ctrl+o", "connect", "Connect", show=False, priority=True),
        Binding("ctrl+n", "new_archive", "New Archive", show=False, priority=True),
        Binding("ctrl+q", "quit",       "Quit",    show=False, priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._active_side: str = "left"
        # snapshot state: pane_id → (base_dir, {rel_path: (mtime, size, mode, uid, gid)})
        self._snapshots: dict[str, tuple[Path, dict[str, tuple[float, int, int, int, int]]]] = {}

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

    # ── Key handling ───────────────────────────────────────────────────────

    def on_key(self, event: events.Key) -> None:
        if event.key == "tab":
            event.stop()
            event.prevent_default()
            self._switch_pane()
        elif event.character == ":":
            event.stop()
            self.action_jump()

    # ── Actions ────────────────────────────────────────────────────────────

    def action_toggle_hidden(self) -> None:
        self._active_pane().toggle_hidden()

    def action_refresh_pane(self) -> None:
        self._active_pane().refresh_listing()

    def action_go_back(self) -> None:
        self._active_pane().go_back()

    def action_context_menu(self) -> None:
        entry = self._active_pane().active_entry
        self._show_context_menu(entry, 4, 4)

    def on_file_table_context_menu_requested(self, event: FileTable.ContextMenuRequested) -> None:
        event.stop()
        self._show_context_menu(event.entry, event.x, event.y)

    def _show_context_menu(self, entry, x: int, y: int) -> None:
        pane = self._active_pane()

        def handle(action: str | None) -> None:
            if action is None:
                return
            if action == "view":
                self.action_view_file()
            elif action == "edit":
                self.action_edit_file()
            elif action == "copy":
                self.action_copy_file()
            elif action == "delete":
                self.action_delete_file()
            elif action == "open":
                if entry:
                    pane.navigate_to(entry.path)
            elif action == "archive_open":
                if entry:
                    from porter.fs.archive import ArchiveFilesystem
                    try:
                        pane.set_filesystem(ArchiveFilesystem(entry.path))
                    except Exception as e:
                        self.notify(f"Cannot open archive: {e}", severity="error")
            elif action == "archive_verify":
                self._verify_archive(entry)
            elif action == "rename":
                self._rename_entry(entry, pane)
            elif action == "props":
                self._show_props(entry)
            elif action == "move":
                self.action_move_file()
            elif action == "new_archive":
                self.action_new_archive()
            elif action == "snapshot":
                self.action_snapshot()
            elif action == "system_snapshot":
                self.action_system_snapshot()
            elif action == "build_archive":
                self.action_build_archive_from_diff()

        self.push_screen(ContextMenu(entry, x, y), handle)

    def _rename_entry(self, entry, pane) -> None:
        if entry is None:
            return
        def do_rename(new_name: str | None) -> None:
            if not new_name or new_name == entry.name:
                return
            try:
                if isinstance(pane.fs, ArchiveFilesystem):
                    pane.fs.rename_member(entry.path, new_name)
                else:
                    entry.path.rename(entry.path.parent / new_name)
                pane.refresh_listing()
                self.notify(f"Renamed to {new_name}")
            except Exception as e:
                self.notify(f"Rename failed: {e}", severity="error")
        self.push_screen(InputDialog("Rename to:", default=entry.name), do_rename)

    def _show_props(self, entry) -> None:
        if entry is None:
            return
        msg = (
            f"[bold]{entry.name}[/bold]\n"
            f"Path:  {entry.path}\n"
            f"Size:  {entry.size_str}  ({entry.size:,} bytes)\n"
            f"Perms: {entry.permissions_str}\n"
            f"Owner: {entry.owner}:{entry.group}\n"
            f"Modified: {entry.mtime_str}"
        )
        self.notify(msg, title="Properties", timeout=8)

    def _verify_archive(self, entry) -> None:
        if entry is None:
            return
        import tarfile, zipfile
        name = entry.name.lower()
        try:
            if name.endswith((".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".tar")):
                with tarfile.open(entry.path, "r:*") as tf:
                    tf.getmembers()
                self.notify(f"{entry.name} — archive OK", timeout=4)
            elif name.endswith(".zip"):
                with zipfile.ZipFile(entry.path, "r") as zf:
                    bad = zf.testzip()
                if bad:
                    self.notify(f"Bad file in archive: {bad}", severity="error", timeout=6)
                else:
                    self.notify(f"{entry.name} — archive OK", timeout=4)
        except Exception as e:
            self.notify(f"Verify failed: {e}", severity="error", timeout=6)

    # ── Ctrl+O Connect ─────────────────────────────────────────────────────

    def action_connect(self) -> None:
        pane = self._active_pane()

        def do_connect(host: SSHHost | None) -> None:
            if host is None:
                return
            fs = SFTPFilesystem(
                hostname=host.hostname,
                username=host.username or None,
                port=host.port,
                key_filename=host.identity_file or None,
                proxy_jump=host.proxy_jump or None,
            )
            self.notify(f"Connecting to {host.alias}…", timeout=3)
            try:
                fs.connect()
                pane.set_filesystem(fs)
                self.notify(f"Connected to {host.alias}", timeout=2)
            except Exception as e:
                self.notify(f"Connection failed: {e}", severity="error", timeout=6)

        self.push_screen(ConnectDialog(), do_connect)

    # ── ^N New Archive ─────────────────────────────────────────────────────

    def action_new_archive(self) -> None:
        pane = self._active_pane()
        if isinstance(pane.fs, (ArchiveFilesystem, SFTPFilesystem)):
            self.notify("New archive only supported on local filesystem", severity="warning")
            return

        def do_create(name: str | None) -> None:
            if not name:
                return
            known_exts = (".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".tar", ".zip")
            if not any(name.lower().endswith(ext) for ext in known_exts):
                name += ".tar.gz"
            target = pane.cwd / name
            if target.exists():
                self.notify(f"'{name}' already exists", severity="error")
                return
            try:
                n = name.lower()
                if n.endswith(".zip"):
                    import zipfile
                    with zipfile.ZipFile(target, "w"):
                        pass
                else:
                    import tarfile
                    if n.endswith((".tar.gz", ".tgz")):
                        mode = "w:gz"
                    elif n.endswith(".tar.bz2"):
                        mode = "w:bz2"
                    elif n.endswith(".tar.xz"):
                        mode = "w:xz"
                    else:
                        mode = "w:"
                    with tarfile.open(target, mode):
                        pass
                pane.refresh_listing()
                self.notify(f"Created {name}")
            except Exception as e:
                self.notify(f"Create archive failed: {e}", severity="error")

        self.push_screen(InputDialog("New archive name:", default="archive.tar.gz"), do_create)

    # ── Snapshot + diff-archive ─────────────────────────────────────────────

    def action_snapshot(self) -> None:
        """Record current state of the active pane's directory for later diff."""
        pane = self._active_pane()
        if not isinstance(pane.fs, LocalFilesystem):
            self.notify("Snapshot only supported on local filesystem", severity="warning")
            return
        base = pane.cwd
        snap: dict[str, tuple[float, int, int, int, int]] = {}
        for p in base.rglob("*"):
            if p.is_file():
                try:
                    st = p.stat()
                    snap[str(p.relative_to(base))] = (
                        st.st_mtime, st.st_size, st.st_mode, st.st_uid, st.st_gid
                    )
                except OSError:
                    pass
        self._snapshots[self._active_side] = (base, snap)
        self.notify(f"Snapshot: {len(snap)} files in {base.name}/")

    def action_system_snapshot(self) -> None:
        """Take a system-wide snapshot from / in a background thread."""
        if not isinstance(self._active_pane().fs, LocalFilesystem):
            self.notify("System snapshot only supported on local filesystem", severity="warning")
            return

        def do_snapshot(exclusions: list[str] | None) -> None:
            if exclusions is None:
                return
            excl_paths = {e for e in exclusions if e.startswith("/")}
            excl_names = {e for e in exclusions if not e.startswith("/")}
            side = self._active_side

            self.notify("Snapshotting system from / — please wait…", timeout=120)

            def _on_complete(snap: dict) -> None:
                self._snapshots[side] = (Path("/"), snap)
                self.notify(f"System snapshot complete: {len(snap):,} files indexed")

            def _walk() -> None:
                snap: dict[str, tuple[float, int, int, int, int]] = {}
                for dirpath, dirnames, filenames in os.walk(
                    "/", topdown=True, followlinks=False
                ):
                    dp = Path(dirpath)
                    dirnames[:] = [
                        d for d in dirnames
                        if str(dp / d) not in excl_paths and d not in excl_names
                    ]
                    for filename in filenames:
                        p = dp / filename
                        try:
                            st = p.stat()
                            snap[str(p.relative_to(Path("/")))] = (
                                st.st_mtime, st.st_size, st.st_mode, st.st_uid, st.st_gid
                            )
                        except OSError:
                            pass
                self.call_from_thread(_on_complete, snap)

            import threading
            threading.Thread(target=_walk, daemon=True, name="porter-system-snapshot").start()

        self.push_screen(SystemSnapshotDialog(), do_snapshot)

    def action_build_archive_from_diff(self) -> None:
        """Compare current directory against snapshot and build a tar.gz of changes."""
        side = self._active_side
        pane = self._active_pane()
        if side not in self._snapshots:
            self.notify("No snapshot — right-click background → Take Snapshot first",
                        severity="warning")
            return
        if not isinstance(pane.fs, LocalFilesystem):
            self.notify("Diff only supported on local filesystem", severity="warning")
            return
        base, snap = self._snapshots[side]
        # Note: base may be "/" for system snapshots — no pane.cwd check needed

        changed: list[tuple[str, str]] = []   # (status, rel_path)
        changed_paths: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(str(base), topdown=True, followlinks=False):
            dp = Path(dirpath)
            # Prune directories that were excluded at snapshot time from the diff walk too
            dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
            for filename in sorted(filenames):
                p = dp / filename
                try:
                    rel = str(p.relative_to(base))
                    st = p.stat()
                    if rel not in snap:
                        changed.append(("NEW", rel))
                        changed_paths.append(p)
                    elif (st.st_mtime, st.st_size, st.st_mode, st.st_uid, st.st_gid) != snap[rel]:
                        changed.append(("MOD", rel))
                        changed_paths.append(p)
                except OSError:
                    pass

        if not changed:
            self.notify("No changes detected since snapshot")
            return

        base_label = str(base)
        default_name = f"{base.name or 'system'}-changes.tar.gz"

        def do_build(archive_name: str | None) -> None:
            if not archive_name:
                return
            known_exts = (".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".tar", ".zip")
            if not any(archive_name.lower().endswith(ext) for ext in known_exts):
                archive_name += ".tar.gz"
            target = self._inactive_pane().cwd / archive_name
            try:
                self.notify("Building manifest…", timeout=60)
                manifest_bytes = _build_manifest(base, changed, changed_paths)

                n = archive_name.lower()
                if n.endswith(".zip"):
                    import zipfile
                    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                        for p in changed_paths:
                            # Store with absolute path so extraction to / is correct
                            zf.write(str(p), str(p).lstrip("/"))
                        zf.writestr("manifest.yaml", manifest_bytes.decode("utf-8"))
                else:
                    import tarfile
                    if n.endswith((".tar.gz", ".tgz")):
                        mode = "w:gz"
                    elif n.endswith(".tar.bz2"):
                        mode = "w:bz2"
                    elif n.endswith(".tar.xz"):
                        mode = "w:xz"
                    else:
                        mode = "w:"
                    with tarfile.open(target, mode) as tf:
                        for p in changed_paths:
                            tf.add(str(p), arcname=str(p).lstrip("/"))
                        minfo = tarfile.TarInfo(name="manifest.yaml")
                        minfo.size = len(manifest_bytes)
                        minfo.mtime = int(time.time())
                        minfo.mode = 0o644
                        tf.addfile(minfo, io.BytesIO(manifest_bytes))

                self._inactive_pane().refresh_listing()
                self.notify(f"Created {archive_name} ({len(changed_paths)} files + manifest)")
            except Exception as e:
                self.notify(f"Build failed: {e}", severity="error")

        self.push_screen(SnapshotDiffDialog(changed, default_name, base=base_label), do_build)

    def action_jump(self) -> None:
        pane = self._active_pane()
        def on_result(path: Path | None) -> None:
            if path:
                pane.navigate_to(path)
        self.push_screen(JumpScreen(pane.cwd), on_result)

    # ── F3 View ────────────────────────────────────────────────────────────

    def action_view_file(self) -> None:
        import tempfile
        pane = self._active_pane()
        entry = pane.active_entry
        if entry is None:
            return
        if entry.is_dir:
            self.notify("Select a file to view", severity="warning")
            return
        if isinstance(pane.fs, ArchiveFilesystem):
            tmp_dir = Path(tempfile.mkdtemp())
            try:
                pane.fs.extract_to(entry.path, tmp_dir)
                tmp_file = tmp_dir / entry.name
                def _cleanup(_):
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                self.push_screen(ViewerScreen(tmp_file), _cleanup)
            except Exception as e:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                self.notify(f"Cannot extract for view: {e}", severity="error")
        else:
            self.push_screen(ViewerScreen(entry.path))

    # ── F4 Edit ────────────────────────────────────────────────────────────

    def action_edit_file(self) -> None:
        import tempfile
        pane = self._active_pane()
        entry = pane.active_entry
        if entry is None:
            return
        if entry.is_dir:
            self.notify("Select a file to edit", severity="warning")
            return
        editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "nano"
        if isinstance(pane.fs, ArchiveFilesystem):
            tmp_dir = Path(tempfile.mkdtemp())
            tmp_file = tmp_dir / entry.name
            try:
                pane.fs.extract_to(entry.path, tmp_dir)
                with self.suspend():
                    subprocess.run([editor, str(tmp_file)])
                pane.fs.replace_member(entry.path, tmp_file)
                pane.refresh_listing()
                self.notify(f"Saved {entry.name}")
            except Exception as e:
                self.notify(f"Edit failed: {e}", severity="error")
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)
        else:
            with self.suspend():
                subprocess.run([editor, str(entry.path)])
            pane.refresh_listing()

    # ── F5 Copy ────────────────────────────────────────────────────────────

    def action_copy_file(self) -> None:
        active_pane = self._active_pane()
        inactive = self._inactive_pane()
        dst_dir = inactive.cwd

        entries = active_pane.selected_entries or (
            [active_pane.active_entry] if active_pane.active_entry else []
        )
        if not entries:
            self.notify("Nothing selected", severity="warning")
            return

        if len(entries) == 1:
            src = entries[0]
            dst = dst_dir / src.name
            msg = f"Copy [bold]{src.name}[/bold]\n  → {dst_dir}"
            try:
                if dst.exists():
                    msg += f"\n\n[yellow]'{src.name}' already exists — overwrite?[/yellow]"
            except OSError:
                pass  # remote/archive path — skip exists check
        else:
            names = ", ".join(e.name for e in entries[:5])
            if len(entries) > 5:
                names += f" … (+{len(entries) - 5} more)"
            msg = f"Copy [bold]{len(entries)} items[/bold]\n  → {dst_dir}\n\n{names}"

        def do_copy(confirmed: bool) -> None:
            if not confirmed:
                return
            import tempfile
            errors = []
            src_fs = active_pane.fs
            dst_fs = inactive.fs
            src_sftp = isinstance(src_fs, SFTPFilesystem)
            dst_sftp = isinstance(dst_fs, SFTPFilesystem)
            src_arc  = isinstance(src_fs, ArchiveFilesystem)
            dst_arc  = isinstance(dst_fs, ArchiveFilesystem)

            if src_sftp and dst_sftp and src_fs.same_server_as(dst_fs):
                # SFTP → SFTP same server: server-side cp
                for src in entries:
                    try:
                        src_fs.copy_remote(src.path, dst_dir)
                    except Exception as e:
                        errors.append(f"{src.name}: {e}")

            elif src_sftp and dst_sftp:
                # SFTP → different SFTP: download to temp, upload
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_dir = Path(tmp)
                    for src in entries:
                        try:
                            src_fs.download(src.path, tmp_dir)
                            dst_fs.upload(tmp_dir / src.name, dst_dir)
                        except Exception as e:
                            errors.append(f"{src.name}: {e}")

            elif src_sftp and dst_arc:
                # SFTP → Archive: download to temp, add to archive
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_dir = Path(tmp)
                    downloaded = []
                    for src in entries:
                        try:
                            src_fs.download(src.path, tmp_dir)
                            downloaded.append(tmp_dir / src.name)
                        except Exception as e:
                            errors.append(f"{src.name}: {e}")
                    if downloaded:
                        try:
                            dst_fs.add_from(downloaded, dst_dir)
                        except Exception as e:
                            errors.extend(f"{p.name}: {e}" for p in downloaded)

            elif src_sftp:
                # SFTP → Local: download
                for src in entries:
                    try:
                        src_fs.download(src.path, dst_dir)
                    except Exception as e:
                        errors.append(f"{src.name}: {e}")

            elif dst_sftp and src_arc:
                # Archive → SFTP: extract to temp, upload
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_dir = Path(tmp)
                    extracted = []
                    for src in entries:
                        try:
                            src_fs.extract_to(src.path, tmp_dir)
                            extracted.append(tmp_dir / src.name)
                        except Exception as e:
                            errors.append(f"{src.name}: {e}")
                    for p in extracted:
                        try:
                            dst_fs.upload(p, dst_dir)
                        except Exception as e:
                            errors.append(f"{p.name}: {e}")

            elif dst_sftp:
                # Local → SFTP: upload
                for src in entries:
                    try:
                        dst_fs.upload(src.path, dst_dir)
                    except Exception as e:
                        errors.append(f"{src.name}: {e}")

            elif src_arc and dst_arc:
                # Archive → Archive: extract to temp, add
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_dir = Path(tmp)
                    extracted = []
                    for src in entries:
                        try:
                            src_fs.extract_to(src.path, tmp_dir)
                            extracted.append(tmp_dir / src.name)
                        except Exception as e:
                            errors.append(f"{src.name}: {e}")
                    if extracted:
                        try:
                            dst_fs.add_from(extracted, dst_dir)
                        except Exception as e:
                            errors.extend(f"{p.name}: {e}" for p in extracted)

            elif src_arc:
                # Archive → Local
                for src in entries:
                    try:
                        src_fs.extract_to(src.path, dst_dir)
                    except Exception as e:
                        errors.append(f"{src.name}: {e}")

            elif dst_arc:
                # Local → Archive
                try:
                    dst_fs.add_from([e.path for e in entries], dst_dir)
                except Exception as e:
                    errors.extend(f"{src.name}: {e}" for src in entries)

            else:
                # Local → Local
                for src in entries:
                    dst = dst_dir / src.name
                    if src.path == dst:
                        errors.append(f"{src.name}: source and destination are the same")
                        continue
                    try:
                        if src.is_dir:
                            if dst.exists():
                                shutil.rmtree(dst)
                            shutil.copytree(str(src.path), str(dst))
                        else:
                            shutil.copy2(str(src.path), str(dst))
                    except shutil.SameFileError:
                        errors.append(f"{src.name}: source and destination are the same")
                    except OSError as e:
                        errors.append(f"{src.name}: {e}")

            inactive.refresh_listing()
            if errors:
                self.notify("Copy errors:\n" + "\n".join(errors), severity="error", timeout=8)
            else:
                active_pane.clear_selection()
                n = len(entries)
                self.notify(f"Copied {n} item{'s' if n > 1 else ''}")

        self.push_screen(ConfirmDialog(msg, title="Copy"), do_copy)

    # ── F6 Move ────────────────────────────────────────────────────────────

    def action_move_file(self) -> None:
        active_pane = self._active_pane()
        inactive = self._inactive_pane()
        dst_dir = inactive.cwd

        entries = active_pane.selected_entries or (
            [active_pane.active_entry] if active_pane.active_entry else []
        )
        if not entries:
            self.notify("Nothing selected", severity="warning")
            return

        if len(entries) == 1:
            src = entries[0]
            dst = dst_dir / src.name
            msg = f"Move [bold]{src.name}[/bold]\n  → {dst_dir}"
            try:
                if dst.exists():
                    msg += f"\n\n[yellow]'{src.name}' already exists — overwrite?[/yellow]"
            except OSError:
                pass  # remote/archive path — skip exists check
        else:
            names = ", ".join(e.name for e in entries[:5])
            if len(entries) > 5:
                names += f" … (+{len(entries) - 5} more)"
            msg = f"Move [bold]{len(entries)} items[/bold]\n  → {dst_dir}\n\n{names}"

        def do_move(confirmed: bool) -> None:
            if not confirmed:
                return
            import tempfile
            errors = []
            src_fs = active_pane.fs
            dst_fs = inactive.fs
            src_sftp = isinstance(src_fs, SFTPFilesystem)
            dst_sftp = isinstance(dst_fs, SFTPFilesystem)
            src_arc  = isinstance(src_fs, ArchiveFilesystem)
            dst_arc  = isinstance(dst_fs, ArchiveFilesystem)

            if src_sftp and dst_sftp and src_fs.same_server_as(dst_fs):
                # SFTP → SFTP same server: server-side mv
                for src in entries:
                    try:
                        src_fs.move_remote(src.path, dst_dir)
                    except Exception as e:
                        errors.append(f"{src.name}: {e}")

            elif src_sftp and dst_sftp:
                # SFTP → different SFTP: download to temp, upload, delete source
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_dir = Path(tmp)
                    for src in entries:
                        try:
                            src_fs.download(src.path, tmp_dir)
                            dst_fs.upload(tmp_dir / src.name, dst_dir)
                            src_fs.remove(src.path)
                        except Exception as e:
                            errors.append(f"{src.name}: {e}")

            elif src_sftp and dst_arc:
                # SFTP → Archive: download to temp, add, delete source
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_dir = Path(tmp)
                    downloaded = []
                    for src in entries:
                        try:
                            src_fs.download(src.path, tmp_dir)
                            downloaded.append(tmp_dir / src.name)
                        except Exception as e:
                            errors.append(f"{src.name}: {e}")
                    if downloaded:
                        try:
                            dst_fs.add_from(downloaded, dst_dir)
                            for src in entries:
                                if not any(src.name in e for e in errors):
                                    try:
                                        src_fs.remove(src.path)
                                    except Exception as e:
                                        errors.append(f"{src.name} (delete): {e}")
                        except Exception as e:
                            errors.extend(f"{p.name}: {e}" for p in downloaded)

            elif src_sftp:
                # SFTP → Local: download, delete source
                for src in entries:
                    try:
                        src_fs.download(src.path, dst_dir)
                        src_fs.remove(src.path)
                    except Exception as e:
                        errors.append(f"{src.name}: {e}")

            elif dst_sftp and src_arc:
                # Archive → SFTP: extract to temp, upload, remove member
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_dir = Path(tmp)
                    extracted = []
                    for src in entries:
                        try:
                            src_fs.extract_to(src.path, tmp_dir)
                            extracted.append(tmp_dir / src.name)
                        except Exception as e:
                            errors.append(f"{src.name}: {e}")
                    for p in extracted:
                        try:
                            dst_fs.upload(p, dst_dir)
                        except Exception as e:
                            errors.append(f"{p.name}: {e}")
                    for src in entries:
                        if not any(src.name in e for e in errors):
                            try:
                                src_fs.remove_member(src.path)
                            except Exception as e:
                                errors.append(f"{src.name} (remove): {e}")

            elif dst_sftp:
                # Local → SFTP: upload, delete local source
                for src in entries:
                    try:
                        dst_fs.upload(src.path, dst_dir)
                        if src.is_dir:
                            shutil.rmtree(str(src.path))
                        else:
                            src.path.unlink()
                    except Exception as e:
                        errors.append(f"{src.name}: {e}")

            elif src_arc and dst_arc:
                # Archive → Archive
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_dir = Path(tmp)
                    extracted = []
                    for src in entries:
                        try:
                            src_fs.extract_to(src.path, tmp_dir)
                            extracted.append(tmp_dir / src.name)
                        except Exception as e:
                            errors.append(f"{src.name}: {e}")
                    if extracted:
                        try:
                            dst_fs.add_from(extracted, dst_dir)
                        except Exception as e:
                            errors.extend(f"{p.name}: {e}" for p in extracted)
                    for src in entries:
                        if not any(src.name in e for e in errors):
                            try:
                                src_fs.remove_member(src.path)
                            except Exception as e:
                                errors.append(f"{src.name} (remove): {e}")

            elif src_arc:
                # Archive → Local: extract then remove member
                for src in entries:
                    try:
                        src_fs.extract_to(src.path, dst_dir)
                        src_fs.remove_member(src.path)
                    except Exception as e:
                        errors.append(f"{src.name}: {e}")

            elif dst_arc:
                # Local → Archive: add then delete source
                try:
                    dst_fs.add_from([e.path for e in entries], dst_dir)
                    for src in entries:
                        try:
                            if src.is_dir:
                                shutil.rmtree(str(src.path))
                            else:
                                src.path.unlink()
                        except OSError as e:
                            errors.append(f"{src.name} (delete): {e}")
                except Exception as e:
                    errors.extend(f"{src.name}: {e}" for src in entries)

            else:
                # Local → Local
                for src in entries:
                    dst = dst_dir / src.name
                    if src.path == dst:
                        errors.append(f"{src.name}: source and destination are the same")
                        continue
                    try:
                        if dst.exists():
                            if src.is_dir:
                                shutil.rmtree(dst)
                            else:
                                dst.unlink()
                        shutil.move(str(src.path), str(dst))
                    except OSError as e:
                        errors.append(f"{src.name}: {e}")

            active_pane.refresh_listing()
            inactive.refresh_listing()
            active_pane.refresh_listing()
            if errors:
                failed = {e.name for e in entries if any(e.name in err for err in errors)}
                active_pane.restore_selection(failed)
                self.notify("Move errors:\n" + "\n".join(errors), severity="error", timeout=8)
            else:
                n = len(entries)
                self.notify(f"Moved {n} item{'s' if n > 1 else ''}")

        self.push_screen(ConfirmDialog(msg, title="Move"), do_move)

    # ── F7 MkDir ───────────────────────────────────────────────────────────

    def action_mkdir(self) -> None:
        pane = self._active_pane()

        def do_mkdir(name: str | None) -> None:
            if not name:
                return
            target = pane.cwd / name
            try:
                if isinstance(pane.fs, ArchiveFilesystem):
                    pane.fs.mkdir_member(target)
                else:
                    target.mkdir(parents=False, exist_ok=False)
                pane.refresh_listing()
                self.notify(f"Created {name}/")
            except FileExistsError:
                self.notify(f"'{name}' already exists", severity="error")
            except Exception as e:
                self.notify(f"MkDir failed: {e}", severity="error")

        self.push_screen(InputDialog("New directory name:", default=""), do_mkdir)

    # ── F8 Delete ──────────────────────────────────────────────────────────

    def action_delete_file(self) -> None:
        pane = self._active_pane()
        entries = pane.selected_entries or (
            [pane.active_entry] if pane.active_entry else []
        )
        if not entries:
            return

        if len(entries) == 1:
            entry = entries[0]
            kind = "directory" if entry.is_dir else "file"
            msg = f"Delete {kind} [bold]{entry.name}[/bold]?"
            if entry.is_dir:
                msg += "\n\n[yellow]This will delete all contents recursively.[/yellow]"
        else:
            names = ", ".join(e.name for e in entries[:5])
            if len(entries) > 5:
                names += f" … (+{len(entries) - 5} more)"
            msg = f"Delete [bold]{len(entries)} items[/bold]?\n\n{names}\n\n[yellow]Directories will be deleted recursively.[/yellow]"

        def do_delete(confirmed: bool) -> None:
            if not confirmed:
                return
            errors = []
            for entry in entries:
                try:
                    if isinstance(pane.fs, ArchiveFilesystem):
                        pane.fs.remove_member(entry.path)
                    elif isinstance(pane.fs, SFTPFilesystem):
                        pane.fs.remove(entry.path)
                    elif entry.is_dir:
                        shutil.rmtree(str(entry.path))
                    else:
                        entry.path.unlink()
                except Exception as e:
                    errors.append(f"{entry.name}: {e}")
            pane.refresh_listing()
            if errors:
                failed = {e.name for e in entries if any(e.name in err for err in errors)}
                pane.restore_selection(failed)
                self.notify("Delete errors:\n" + "\n".join(errors), severity="error", timeout=8)
            else:
                n = len(entries)
                self.notify(f"Deleted {n} item{'s' if n > 1 else ''}")

        self.push_screen(ConfirmDialog(msg, title="Delete"), do_delete)

    # ── Title ──────────────────────────────────────────────────────────────

    def get_default_screen(self):
        screen = super().get_default_screen()
        screen.title = "porter"
        return screen
