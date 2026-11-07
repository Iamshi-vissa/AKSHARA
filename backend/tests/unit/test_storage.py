from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

import pytest

from app.adapters.storage import LocalBlobStorage


def test_put_is_content_addressed_and_idempotent(tmp_path: Path) -> None:
    store = LocalBlobStorage(tmp_path / "blobs")
    src = tmp_path / "in.bin"
    src.write_bytes(b"akshara" * 1000)
    first = store.put_file(src)
    second = store.put_file(src)
    assert first.sha256 == hashlib.sha256(src.read_bytes()).hexdigest()
    assert first.created and not second.created
    assert first.storage_key == second.storage_key
    assert b"".join(store.open(first.storage_key)) == src.read_bytes()


def test_stored_blobs_are_read_only(tmp_path: Path) -> None:
    store = LocalBlobStorage(tmp_path / "blobs")
    src = tmp_path / "in.bin"
    src.write_bytes(b"original")
    blob = store.put_file(src)
    mode = os.stat(tmp_path / "blobs" / blob.storage_key).st_mode
    assert not mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)


def test_no_delete_or_overwrite_api() -> None:
    assert not hasattr(LocalBlobStorage, "delete")
    assert not hasattr(LocalBlobStorage, "overwrite")


@pytest.mark.parametrize("key", ["../etc/passwd", "sha256/../../x", "sha256/ab/cd/zz"])
def test_invalid_keys_rejected(tmp_path: Path, key: str) -> None:
    store = LocalBlobStorage(tmp_path / "blobs")
    with pytest.raises(ValueError):
        store.exists(key)


def test_no_temp_files_left(tmp_path: Path) -> None:
    store = LocalBlobStorage(tmp_path / "blobs")
    src = tmp_path / "in.bin"
    src.write_bytes(b"data")
    store.put_file(src)
    leftovers = [p for p in (tmp_path / "blobs").rglob(".incoming-*")]
    assert leftovers == []
