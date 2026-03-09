"""LocalFilesystem — reads the local filesystem into FileEntry lists."""

from __future__ import annotations

import grp
import os
import pwd
from pathlib import Path

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
    """Return sorted FileEntry list for *path*.  Dirs first, then files, both alphabetical."""
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
