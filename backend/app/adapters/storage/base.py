"""Blob storage interface.

Blobs are content-addressed (SHA-256) and write-once. The interface deliberately has **no
delete or overwrite operation**: that is how "never destroy original user documents" is
enforced structurally rather than by convention. Retention/purge, when it exists, will be a
separate, audited administrative tool.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class StoredBlob:
    sha256: str
    size_bytes: int
    storage_key: str
    created: bool  # False when identical content was already stored


class BlobStorage(Protocol):
    def put_file(self, path: Path) -> StoredBlob:
        """Store the file's content. Idempotent: identical content maps to the same blob."""
        ...

    def open(self, storage_key: str) -> Iterator[bytes]:
        """Stream the blob's bytes."""
        ...

    def exists(self, storage_key: str) -> bool: ...

    def healthy(self) -> bool:
        """True when the backend is reachable and writable."""
        ...
