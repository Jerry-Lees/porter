"""ArchiveFilesystem — browse .tar.gz, .tar.bz2, .tar.xz, .zip as virtual directories."""

from __future__ import annotations

import shutil
import stat as stat_module
import tarfile
import tempfile
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

    # ── Transfer helpers ───────────────────────────────────────────────────

    def _virtual_to_member(self, virtual_path: Path) -> str:
        """Convert virtual path /dir/file → archive member name dir/file."""
        return "/".join(p for p in virtual_path.parts if p not in ("", "/"))

    def _is_tar(self) -> bool:
        return self._archive_path.name.lower().endswith(
            (".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".tar")
        )

    def _tar_mode(self, rw: str) -> str:
        name = self._archive_path.name.lower()
        if name.endswith((".tar.gz", ".tgz")):
            return f"{rw}:gz"
        if name.endswith(".tar.bz2"):
            return f"{rw}:bz2"
        if name.endswith(".tar.xz"):
            return f"{rw}:xz"
        return f"{rw}:"  # plain tar

    def extract_to(self, virtual_path: Path, dst_dir: Path) -> None:
        """Extract the file or directory at *virtual_path* into *dst_dir*."""
        member_name = self._virtual_to_member(virtual_path)
        dst_dir.mkdir(parents=True, exist_ok=True)
        if self._is_tar():
            self._tar_extract(member_name, dst_dir)
        else:
            self._zip_extract(member_name, dst_dir)

    def _norm_tar(self, name: str) -> str:
        """Strip leading './' sequences only — preserves dotfile names like .gitignore."""
        while name.startswith("./"):
            name = name[2:]
        return name

    def _tar_extract(self, member_name: str, dst_dir: Path) -> None:
        out_name = Path(member_name).name
        with tarfile.open(self._archive_path, self._tar_mode("r")) as tf:
            for m in tf.getmembers():
                norm = self._norm_tar(m.name)
                if norm == member_name:
                    if m.isdir():
                        (dst_dir / out_name).mkdir(parents=True, exist_ok=True)
                    else:
                        fobj = tf.extractfile(m)
                        if fobj:
                            (dst_dir / out_name).write_bytes(fobj.read())
                elif norm.startswith(member_name + "/"):
                    rel = norm[len(member_name) + 1:]
                    target = dst_dir / out_name / rel
                    if m.isdir():
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        fobj = tf.extractfile(m)
                        if fobj:
                            target.write_bytes(fobj.read())

    def _zip_extract(self, member_name: str, dst_dir: Path) -> None:
        out_name = Path(member_name).name
        with zipfile.ZipFile(self._archive_path, "r") as zf:
            for info in zf.infolist():
                norm = info.filename.rstrip("/")
                if norm == member_name:
                    if info.filename.endswith("/"):
                        (dst_dir / out_name).mkdir(parents=True, exist_ok=True)
                    else:
                        (dst_dir / out_name).write_bytes(zf.read(info.filename))
                elif norm.startswith(member_name + "/"):
                    rel = norm[len(member_name) + 1:]
                    target = dst_dir / out_name / rel
                    if info.filename.endswith("/"):
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(zf.read(info.filename))

    def add_from(self, src_paths: list[Path], virtual_dir: Path) -> None:
        """Add real files/dirs in *src_paths* into the archive under *virtual_dir*."""
        prefix = self._virtual_to_member(virtual_dir)
        if self._is_tar():
            self._tar_add(src_paths, prefix)
        else:
            self._zip_add(src_paths, prefix)
        # Reload the in-memory tree
        self._root = _Node(name="", is_dir=True)
        self._load()

    def _arcname(self, prefix: str, src_path: Path) -> str:
        base = (prefix + "/" + src_path.name) if prefix else src_path.name
        return base

    def _tar_add(self, src_paths: list[Path], prefix: str) -> None:
        name = self._archive_path.name.lower()
        can_append = name.endswith(".tar")  # only plain tar supports 'a' mode
        if can_append:
            with tarfile.open(self._archive_path, "a") as tf:
                for src in src_paths:
                    tf.add(str(src), arcname=self._arcname(prefix, src),
                           recursive=src.is_dir())
        else:
            # Compressed tar: repack with new members appended
            tmp_fd, tmp_name = tempfile.mkstemp(suffix=self._archive_path.suffix)
            tmp = Path(tmp_name)
            try:
                with (tarfile.open(self._archive_path, self._tar_mode("r")) as src_tf,
                      tarfile.open(tmp, self._tar_mode("w")) as dst_tf):
                    for m in src_tf.getmembers():
                        fobj = src_tf.extractfile(m) if m.isfile() else None
                        dst_tf.addfile(m, fobj)
                    for src in src_paths:
                        dst_tf.add(str(src), arcname=self._arcname(prefix, src),
                                   recursive=src.is_dir())
                shutil.move(str(tmp), str(self._archive_path))
            except Exception:
                tmp.unlink(missing_ok=True)
                raise

    def _zip_add(self, src_paths: list[Path], prefix: str) -> None:
        with zipfile.ZipFile(self._archive_path, "a") as zf:
            for src in src_paths:
                if src.is_dir():
                    for item in src.rglob("*"):
                        if not item.is_dir():
                            rel = str(item.relative_to(src.parent))
                            arcname = (prefix + "/" + rel) if prefix else rel
                            zf.write(str(item), arcname)
                else:
                    zf.write(str(src), self._arcname(prefix, src))

    def remove_member(self, virtual_path: Path) -> None:
        """Remove a single member from the archive."""
        self.remove_members([virtual_path])

    def remove_members(self, virtual_paths: list[Path]) -> None:
        """Remove multiple members in a single repack pass."""
        names = {self._virtual_to_member(p) for p in virtual_paths}
        if self._is_tar():
            self._tar_remove_many(names)
        else:
            self._zip_remove_many(names)
        self._root = _Node(name="", is_dir=True)
        self._load()

    def _tar_remove(self, member_name: str) -> None:
        self._tar_remove_many({member_name})

    def _tar_remove_many(self, member_names: set[str]) -> None:
        tmp_fd, tmp_name = tempfile.mkstemp(suffix=self._archive_path.suffix)
        tmp = Path(tmp_name)
        try:
            with (tarfile.open(self._archive_path, self._tar_mode("r")) as src_tf,
                  tarfile.open(tmp, self._tar_mode("w")) as dst_tf):
                for m in src_tf.getmembers():
                    norm = self._norm_tar(m.name)
                    if any(norm == n or norm.startswith(n + "/") for n in member_names):
                        continue
                    fobj = src_tf.extractfile(m) if m.isfile() else None
                    dst_tf.addfile(m, fobj)
            shutil.move(str(tmp), str(self._archive_path))
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    def _zip_remove(self, member_name: str) -> None:
        self._zip_remove_many({member_name})

    def _zip_remove_many(self, member_names: set[str]) -> None:
        tmp_fd, tmp_name = tempfile.mkstemp(suffix=".zip")
        tmp = Path(tmp_name)
        try:
            with (zipfile.ZipFile(self._archive_path, "r") as src_zf,
                  zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as dst_zf):
                for info in src_zf.infolist():
                    norm = info.filename.rstrip("/")
                    if any(norm == n or norm.startswith(n + "/") for n in member_names):
                        continue
                    dst_zf.writestr(info, src_zf.read(info.filename))
            shutil.move(str(tmp), str(self._archive_path))
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    def mkdir_member(self, virtual_path: Path) -> None:
        """Create an empty directory entry in the archive."""
        member_name = self._virtual_to_member(virtual_path)
        if not member_name:
            return
        if self._is_tar():
            self._tar_mkdir(member_name)
        else:
            self._zip_mkdir(member_name)
        self._root = _Node(name="", is_dir=True)
        self._load()

    def _tar_mkdir(self, member_name: str) -> None:
        name = self._archive_path.name.lower()
        if name.endswith(".tar"):
            with tarfile.open(self._archive_path, "a") as tf:
                info = tarfile.TarInfo(name=member_name)
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                tf.addfile(info)
        else:
            tmp_fd, tmp_name = tempfile.mkstemp(suffix=self._archive_path.suffix)
            tmp = Path(tmp_name)
            try:
                with (tarfile.open(self._archive_path, self._tar_mode("r")) as src_tf,
                      tarfile.open(tmp, self._tar_mode("w")) as dst_tf):
                    for m in src_tf.getmembers():
                        fobj = src_tf.extractfile(m) if m.isfile() else None
                        dst_tf.addfile(m, fobj)
                    info = tarfile.TarInfo(name=member_name)
                    info.type = tarfile.DIRTYPE
                    info.mode = 0o755
                    dst_tf.addfile(info)
                shutil.move(str(tmp), str(self._archive_path))
            except Exception:
                tmp.unlink(missing_ok=True)
                raise

    def _zip_mkdir(self, member_name: str) -> None:
        with zipfile.ZipFile(self._archive_path, "a") as zf:
            zf.writestr(member_name.rstrip("/") + "/", "")

    def rename_member(self, virtual_path: Path, new_name: str) -> None:
        """Rename a member (and its children if a directory) inside the archive."""
        old_member = self._virtual_to_member(virtual_path)
        parent_parts = [p for p in virtual_path.parts[:-1] if p not in ("", "/")]
        new_member = "/".join(parent_parts + [new_name]) if parent_parts else new_name
        if self._is_tar():
            self._tar_rename(old_member, new_member)
        else:
            self._zip_rename(old_member, new_member)
        self._root = _Node(name="", is_dir=True)
        self._load()

    def _tar_rename(self, old_member: str, new_member: str) -> None:
        tmp_fd, tmp_name = tempfile.mkstemp(suffix=self._archive_path.suffix)
        tmp = Path(tmp_name)
        try:
            with (tarfile.open(self._archive_path, self._tar_mode("r")) as src_tf,
                  tarfile.open(tmp, self._tar_mode("w")) as dst_tf):
                for m in src_tf.getmembers():
                    norm = self._norm_tar(m.name)
                    if norm == old_member:
                        m = m.tobuf and m  # keep object, just mutate name
                        m.name = new_member
                    elif norm.startswith(old_member + "/"):
                        m.name = new_member + norm[len(old_member):]
                    fobj = src_tf.extractfile(m) if m.isfile() else None
                    dst_tf.addfile(m, fobj)
            shutil.move(str(tmp), str(self._archive_path))
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    def _zip_rename(self, old_member: str, new_member: str) -> None:
        tmp_fd, tmp_name = tempfile.mkstemp(suffix=".zip")
        tmp = Path(tmp_name)
        try:
            with (zipfile.ZipFile(self._archive_path, "r") as src_zf,
                  zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as dst_zf):
                for info in src_zf.infolist():
                    orig_filename = info.filename
                    norm = orig_filename.rstrip("/")
                    is_dir_entry = orig_filename.endswith("/")
                    if norm == old_member:
                        info.filename = new_member + ("/" if is_dir_entry else "")
                    elif norm.startswith(old_member + "/"):
                        info.filename = new_member + norm[len(old_member):] + ("/" if is_dir_entry else "")
                    data = b"" if is_dir_entry else src_zf.read(orig_filename)
                    dst_zf.writestr(info, data)
            shutil.move(str(tmp), str(self._archive_path))
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    def replace_member(self, virtual_path: Path, new_real_path: Path) -> None:
        """Replace the content of a member with a real file (used after in-archive edit)."""
        member_name = self._virtual_to_member(virtual_path)
        if self._is_tar():
            self._tar_replace(member_name, new_real_path)
        else:
            self._zip_replace(member_name, new_real_path)
        self._root = _Node(name="", is_dir=True)
        self._load()

    def _tar_replace(self, member_name: str, new_real_path: Path) -> None:
        tmp_fd, tmp_name = tempfile.mkstemp(suffix=self._archive_path.suffix)
        tmp = Path(tmp_name)
        try:
            replaced = False
            with (tarfile.open(self._archive_path, self._tar_mode("r")) as src_tf,
                  tarfile.open(tmp, self._tar_mode("w")) as dst_tf):
                for m in src_tf.getmembers():
                    norm = self._norm_tar(m.name)
                    if norm == member_name:
                        dst_tf.add(str(new_real_path), arcname=m.name)
                        replaced = True
                    else:
                        fobj = src_tf.extractfile(m) if m.isfile() else None
                        dst_tf.addfile(m, fobj)
                if not replaced:
                    dst_tf.add(str(new_real_path), arcname=member_name)
            shutil.move(str(tmp), str(self._archive_path))
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    def _zip_replace(self, member_name: str, new_real_path: Path) -> None:
        tmp_fd, tmp_name = tempfile.mkstemp(suffix=".zip")
        tmp = Path(tmp_name)
        try:
            replaced = False
            with (zipfile.ZipFile(self._archive_path, "r") as src_zf,
                  zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as dst_zf):
                for info in src_zf.infolist():
                    norm = info.filename.rstrip("/")
                    if norm == member_name:
                        dst_zf.write(str(new_real_path), member_name)
                        replaced = True
                    else:
                        dst_zf.writestr(info, src_zf.read(info.filename))
                if not replaced:
                    dst_zf.write(str(new_real_path), member_name)
            shutil.move(str(tmp), str(self._archive_path))
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

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
