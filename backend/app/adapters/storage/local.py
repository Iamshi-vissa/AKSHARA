"""Local filesystem blob storage (development and single-node deployments).

Layout: ``<root>/sha256/ab/cd/<sha256>``. Files are written to a temporary name in the same
directory, fsynced, made read-only and then atomically renamed into place. Existing blobs are
never replaced.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from collections.abc import Iterator
from pathlib import Path

from app.adapters.storage.base import StoredBlob

_CHUNK = 1024 * 1024
_KEY_RE = re.compile(r"^sha256/[0-9a-f]{2}/[0-9a-f]{2}/[0-9a-f]{64}$")


def sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as fh:
        while chunk := fh.read(_CHUNK):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


class LocalBlobStorage:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def key_for(sha: str) -> str:
        return f"sha256/{sha[:2]}/{sha[2:4]}/{sha}"

    def _resolve(self, storage_key: str) -> Path:
        if not _KEY_RE.match(storage_key):
            raise ValueError("invalid storage key")
        return self._root / storage_key

    def put_file(self, path: Path) -> StoredBlob:
        sha, size = sha256_file(path)
        key = self.key_for(sha)
        target = self._resolve(key)
        if target.exists():
            return StoredBlob(sha256=sha, size_bytes=size, storage_key=key, created=False)

        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=".incoming-")
        try:
            with os.fdopen(fd, "wb") as out, path.open("rb") as src:
                while chunk := src.read(_CHUNK):
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
            os.chmod(tmp_name, 0o444)
            try:
                # link() fails if the target exists, so a concurrent writer cannot be clobbered.
                os.link(tmp_name, target)
                created = True
            except FileExistsError:
                created = False
        finally:
            os.unlink(tmp_name)
        return StoredBlob(sha256=sha, size_bytes=size, storage_key=key, created=created)

    def open(self, storage_key: str) -> Iterator[bytes]:
        path = self._resolve(storage_key)
        with path.open("rb") as fh:
            while chunk := fh.read(_CHUNK):
                yield chunk

    def exists(self, storage_key: str) -> bool:
        return self._resolve(storage_key).exists()

    def healthy(self) -> bool:
        return self._root.is_dir() and os.access(self._root, os.W_OK)
