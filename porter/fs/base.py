"""Abstract filesystem interface — all backends implement this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from porter.models.entry import FileEntry


class Filesystem(ABC):
    """Common interface for local, SFTP, and archive filesystems."""

    @abstractmethod
    def listdir(self, path: Path, show_hidden: bool = False) -> list[FileEntry]:
        """Return sorted FileEntry list for *path*."""

    @abstractmethod
    def stat(self, path: Path) -> FileEntry:
        """Return FileEntry for a single path."""

    @property
    @abstractmethod
    def label(self) -> str:
        """Short display label for the pane header (e.g. 'local' or 'user@host')."""

    @property
    @abstractmethod
    def home(self) -> Path:
        """Starting directory for this filesystem."""
