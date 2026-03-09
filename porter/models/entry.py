"""FileEntry — shared data contract for all filesystem backends."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ARCHIVE_SUFFIXES = (".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".zip")


def _is_archive(name: str) -> bool:
    lower = name.lower()
    return any(lower.endswith(s) for s in ARCHIVE_SUFFIXES)


@dataclass
class FileEntry:
    name: str
    path: Path
    is_dir: bool
    is_link: bool
    size: int       # bytes
    mode: int       # stat mode bits
    uid: int
    gid: int
    owner: str      # resolved name, falls back to str(uid)
    group: str      # resolved name, falls back to str(gid)
    mtime: float    # unix timestamp

    @classmethod
    def from_stat(cls, path: Path, st: os.stat_result, owner: str, group: str) -> FileEntry:
        return cls(
            name=path.name,
            path=path,
            is_dir=stat.S_ISDIR(st.st_mode),
            is_link=stat.S_ISLNK(st.st_mode),
            size=st.st_size,
            mode=st.st_mode,
            uid=st.st_uid,
            gid=st.st_gid,
            owner=owner,
            group=group,
            mtime=st.st_mtime,
        )

    @property
    def is_archive(self) -> bool:
        return not self.is_dir and _is_archive(self.name)

    @property
    def permissions_str(self) -> str:
        return stat.filemode(self.mode)

    @property
    def size_str(self) -> str:
        if self.is_dir:
            return ""
        size = self.size
        for unit in ("B", "K", "M", "G", "T"):
            if size < 1024:
                return f"{size:.0f}{unit}"
            size //= 1024
        return f"{size:.0f}P"

    @property
    def mtime_str(self) -> str:
        return datetime.fromtimestamp(self.mtime).strftime("%Y-%m-%d %H:%M")
