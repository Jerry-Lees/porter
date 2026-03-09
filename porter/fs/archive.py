"""ArchiveFilesystem — browse .tar.gz, .tar.bz2, .tar.xz, .zip as virtual directories."""

from __future__ import annotations

import stat as stat_module
import tarfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from porter.fs.base import Filesystem
from porter.models.entry import FileEntry


@dataclass
class _Node:
    """One entry in the archive tree."""
    name: str
    is_dir: bool
    size: int = 0
    mode: int = 0o644
    uid: int = 0
    gid: int = 0
    mtime: float = 0.0
    children: dict[str, "_Node"] = field(default_factory=dict)


class ArchiveFilesystem(Filesystem):
    """Read-only virtual filesystem backed by a tar or zip archive."""

    def __init__(self, archive_path: Path) -> None:
        self._archive_path = archive_path
        self._root = _Node(name="", is_dir=True)
        self._load()

    # ── Loading ────────────────────────────────────────────────────────────

    def _load(self) -> None:
        name = self._archive_path.name.lower()
        if name.endswith((".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".tar")):
            self._load_tar()
        elif name.endswith(".zip"):
            self._load_zip()

    def _load_tar(self) -> None:
        with tarfile.open(self._archive_path, "r:*") as tf:
            for member in tf.getmembers():
                parts = _split(member.name)
                if not parts:
                    continue
                is_dir = member.isdir()
                node = _Node(
                    name=parts[-1],
                    is_dir=is_dir,
                    size=member.size,
                    mode=member.mode or (0o755 if is_dir else 0o644),
                    uid=member.uid,
                    gid=member.gid,
                    mtime=float(member.mtime),
                )
                self._insert(parts, node)

    def _load_zip(self) -> None:
        with zipfile.ZipFile(self._archive_path, "r") as zf:
            for info in zf.infolist():
                parts = _split(info.filename)
                if not parts:
                    continue
                is_dir = info.filename.endswith("/")
                mtime = 0.0
                try:
                    import time
                    mtime = time.mktime(info.date_time + (0, 0, -1))
                except Exception:
                    pass
                node = _Node(
                    name=parts[-1],
                    is_dir=is_dir,
                    size=info.file_size,
                    mtime=mtime,
                )
                self._insert(parts, node)

    def _insert(self, parts: list[str], node: _Node) -> None:
        """Walk the tree, creating intermediate directories as needed."""
        current = self._root
        for part in parts[:-1]:
            if part not in current.children:
                current.children[part] = _Node(name=part, is_dir=True)
            current = current.children[part]
        existing = current.children.get(node.name)
        if existing and existing.is_dir and node.is_dir:
            # Update metadata but keep children already populated from file paths
            existing.mode = node.mode or existing.mode
            existing.uid = node.uid
            existing.gid = node.gid
            existing.mtime = node.mtime or existing.mtime
        else:
            current.children[node.name] = node

    # ── Filesystem interface ───────────────────────────────────────────────

    @property
    def label(self) -> str:
        return f"archive:{self._archive_path.name}"

    @property
    def home(self) -> Path:
        return Path("/")

    def listdir(self, path: Path, show_hidden: bool = False) -> list[FileEntry]:
        node = self._resolve(path)
        if node is None or not node.is_dir:
            return []
        entries: list[FileEntry] = []
        for child in node.children.values():
            if not show_hidden and child.name.startswith("."):
                continue
            entries.append(self._node_to_entry(child, path / child.name))
        entries.sort(key=lambda e: (not e.is_dir, e.name.lower()))
        return entries

    def stat(self, path: Path) -> FileEntry:
        node = self._resolve(path)
        if node is None:
            raise FileNotFoundError(path)
        return self._node_to_entry(node, path)

    # ── Internal ───────────────────────────────────────────────────────────

    def _resolve(self, path: Path) -> _Node | None:
        """Walk the tree to find the node at *path*."""
        parts = [p for p in path.parts if p not in ("", "/")]
        current = self._root
        for part in parts:
            if part not in current.children:
                return None
            current = current.children[part]
        return current

    def _node_to_entry(self, node: _Node, path: Path) -> FileEntry:
        mode = node.mode
        if node.is_dir and not stat_module.S_ISDIR(mode):
            mode = stat_module.S_IFDIR | 0o755
        elif not node.is_dir and not stat_module.S_ISREG(mode):
            mode = stat_module.S_IFREG | node.mode
        return FileEntry(
            name=node.name,
            path=path,
            is_dir=node.is_dir,
            is_link=False,
            size=node.size,
            mode=mode,
            uid=node.uid,
            gid=node.gid,
            owner=str(node.uid) if node.uid else "root",
            group=str(node.gid) if node.gid else "root",
            mtime=node.mtime,
        )


def _split(raw: str) -> list[str]:
    """Normalize archive member name into path parts, stripping leading ./ and blanks."""
    parts = [p for p in raw.replace("\\", "/").split("/") if p and p != "."]
    return parts
