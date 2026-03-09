"""LocalFilesystem — reads the local filesystem into FileEntry lists."""

from __future__ import annotations

import grp
import os
import pwd
from pathlib import Path

from porter.fs.base import Filesystem
from porter.models.entry import FileEntry


def _resolve_owner(uid: int) -> str:
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return str(uid)


def _resolve_group(gid: int) -> str:
    try:
        return grp.getgrgid(gid).gr_name
    except KeyError:
        return str(gid)


def listdir(path: Path, show_hidden: bool = False) -> list[FileEntry]:
    """Module-level helper kept for backwards compatibility."""
    return LocalFilesystem().listdir(path, show_hidden)


class LocalFilesystem(Filesystem):
    """Local filesystem backend."""

    @property
    def label(self) -> str:
        return "local"

    @property
    def home(self) -> Path:
        return Path.home()

    def listdir(self, path: Path, show_hidden: bool = False) -> list[FileEntry]:
        entries: list[FileEntry] = []
        try:
            with os.scandir(path) as it:
                for de in it:
                    if not show_hidden and de.name.startswith("."):
                        continue
                    try:
                        st = de.stat(follow_symlinks=False)
                        entries.append(FileEntry.from_stat(
                            path=Path(de.path),
                            st=st,
                            owner=_resolve_owner(st.st_uid),
                            group=_resolve_group(st.st_gid),
                        ))
                    except OSError:
                        pass
        except PermissionError:
            pass
        entries.sort(key=lambda e: (not e.is_dir, e.name.lower()))
        return entries

    def stat(self, path: Path) -> FileEntry:
        st = path.stat()
        return FileEntry.from_stat(
            path=path,
            st=st,
            owner=_resolve_owner(st.st_uid),
            group=_resolve_group(st.st_gid),
        )
