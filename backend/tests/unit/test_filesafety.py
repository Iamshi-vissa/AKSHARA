from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from app.core.filesafety import FileRejected, SafetyLimits, inspect_file
from tests import factories as f

LIMITS = SafetyLimits(
    max_bytes=5 * 1024 * 1024,
    max_uncompressed_bytes=20 * 1024 * 1024,
    max_entries=50,
    max_compression_ratio=100,
)


def rejected(path: Path, name: str) -> str:
    with pytest.raises(FileRejected) as exc:
        inspect_file(path, name, LIMITS)
    return exc.value.code


def test_valid_docx(tmp_path: Path) -> None:
    p = f.write(tmp_path, "a.docx", f.ooxml_bytes("docx"))
    r = inspect_file(p, "a.docx", LIMITS)
    assert r.kind == "docx" and r.warnings == []
    assert r.mime_type.endswith("wordprocessingml.document")


def test_valid_pptx(tmp_path: Path) -> None:
    p = f.write(tmp_path, "deck.pptx", f.ooxml_bytes("pptx"))
    assert inspect_file(p, "deck.pptx", LIMITS).kind == "pptx"


def test_valid_pdf(tmp_path: Path) -> None:
    p = f.write(tmp_path, "paper.pdf", f.pdf_bytes())
    r = inspect_file(p, "paper.pdf", LIMITS)
    assert r.kind == "pdf" and r.warnings == []


def test_extension_case_insensitive(tmp_path: Path) -> None:
    p = f.write(tmp_path, "A.DOCX", f.ooxml_bytes("docx"))
    assert inspect_file(p, "A.DOCX", LIMITS).kind == "docx"


@pytest.mark.parametrize(
    ("name", "code"),
    [
        ("x.docm", "MACRO_ENABLED"),
        ("x.pptm", "MACRO_ENABLED"),
        ("x.doc", "LEGACY_FORMAT"),
        ("x.exe", "UNSUPPORTED_EXTENSION"),
        ("noext", "UNSUPPORTED_EXTENSION"),
    ],
)
def test_rejected_extensions(tmp_path: Path, name: str, code: str) -> None:
    p = f.write(tmp_path, "file.bin", f.ooxml_bytes("docx"))
    assert rejected(p, name) == code


def test_docx_renamed_to_pdf_is_rejected(tmp_path: Path) -> None:
    p = f.write(tmp_path, "a.pdf", f.ooxml_bytes("docx"))
    assert rejected(p, "a.pdf") == "EXTENSION_MISMATCH"


def test_pptx_named_docx_is_rejected(tmp_path: Path) -> None:
    p = f.write(tmp_path, "a.docx", f.ooxml_bytes("pptx"))
    assert rejected(p, "a.docx") == "EXTENSION_MISMATCH"


def test_macro_content_type_rejected(tmp_path: Path) -> None:
    data = f.ooxml_bytes("docx", main_type=f.WORD_MACRO_MAIN)
    assert rejected(f.write(tmp_path, "a.docx", data), "a.docx") == "MACRO_ENABLED"


def test_vba_project_part_rejected(tmp_path: Path) -> None:
    data = f.ooxml_bytes("docx", extra_parts={"word/vbaProject.bin": b"\x00" * 64})
    assert rejected(f.write(tmp_path, "a.docx", data), "a.docx") == "MACRO_ENABLED"


def test_path_traversal_rejected(tmp_path: Path) -> None:
    data = f.ooxml_bytes("docx", extra_parts={"../../evil.txt": b"x"})
    assert rejected(f.write(tmp_path, "a.docx", data), "a.docx") == "UNSAFE_PATH"


def test_zip_bomb_ratio_rejected(tmp_path: Path) -> None:
    data = f.ooxml_bytes("docx", extra_parts={"word/media/big.bin": b"\x00" * (8 * 1024 * 1024)})
    assert rejected(f.write(tmp_path, "a.docx", data), "a.docx") == "COMPRESSION_RATIO"


def test_decompression_limit(tmp_path: Path) -> None:
    import os

    limits = SafetyLimits(5 * 1024 * 1024, 2 * 1024 * 1024, 50, 1000)
    data = f.ooxml_bytes("docx", extra_parts={"word/media/r.bin": os.urandom(3 * 1024 * 1024)})
    p = f.write(tmp_path, "a.docx", data)
    with pytest.raises(FileRejected) as exc:
        inspect_file(p, "a.docx", limits)
    assert exc.value.code in {"DECOMPRESSION_LIMIT", "FILE_TOO_LARGE"}


def test_too_many_entries(tmp_path: Path) -> None:
    parts = {f"word/p{i}.xml": b"<a/>" for i in range(60)}
    data = f.ooxml_bytes("docx", extra_parts=parts)
    assert rejected(f.write(tmp_path, "a.docx", data), "a.docx") == "TOO_MANY_PARTS"


def test_plain_zip_rejected(tmp_path: Path) -> None:
    data = f.zip_with_entries({"readme.txt": b"hello"})
    assert rejected(f.write(tmp_path, "a.docx", data), "a.docx") == "NOT_OOXML"


def test_xxe_content_types_rejected(tmp_path: Path) -> None:
    evil = (
        '<?xml version="1.0"?><!DOCTYPE t [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">&x;</Types>'
    )
    data = f.zip_with_entries({"word/document.xml": b"<a/>"}, ct=evil)
    assert rejected(f.write(tmp_path, "a.docx", data), "a.docx") == "CORRUPT_PACKAGE"


def test_billion_laughs_rejected(tmp_path: Path) -> None:
    lol = (
        '<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">]>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">&b;</Types>'
    )
    data = f.zip_with_entries({"word/document.xml": b"<a/>"}, ct=lol)
    assert rejected(f.write(tmp_path, "a.docx", data), "a.docx") == "CORRUPT_PACKAGE"


def test_encrypted_zip_entry_rejected(tmp_path: Path) -> None:
    p = f.write(tmp_path, "a.docx", f.ooxml_bytes("docx"))
    raw = bytearray(p.read_bytes())
    # Set the "encrypted" general-purpose flag on every central directory record.
    with zipfile.ZipFile(p) as zf:
        count = len(zf.infolist())
    idx = 0
    for _ in range(count):
        idx = raw.index(b"PK\x01\x02", idx)
        raw[idx + 8] |= 0x01
        idx += 4
    p.write_bytes(bytes(raw))
    assert rejected(p, "a.docx") == "ENCRYPTED_PART"


def test_corrupt_zip(tmp_path: Path) -> None:
    p = f.write(tmp_path, "a.docx", b"PK\x03\x04" + b"garbage" * 10)
    assert rejected(p, "a.docx") == "CORRUPT_PACKAGE"


def test_ole_file_rejected(tmp_path: Path) -> None:
    p = f.write(tmp_path, "a.docx", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 600)
    assert rejected(p, "a.docx") == "ENCRYPTED_OR_LEGACY"


def test_empty_file(tmp_path: Path) -> None:
    assert rejected(f.write(tmp_path, "a.pdf", b""), "a.pdf") == "EMPTY_FILE"


def test_too_large(tmp_path: Path) -> None:
    p = f.write(tmp_path, "a.pdf", f.pdf_bytes() + b"\x00" * (6 * 1024 * 1024))
    assert rejected(p, "a.pdf") == "FILE_TOO_LARGE"


def test_random_bytes_rejected(tmp_path: Path) -> None:
    assert rejected(f.write(tmp_path, "a.pdf", b"hello world"), "a.pdf") == "UNRECOGNISED_CONTENT"


def test_encrypted_pdf_rejected(tmp_path: Path) -> None:
    p = f.write(tmp_path, "a.pdf", f.pdf_bytes(encrypted=True))
    assert rejected(p, "a.pdf") == "ENCRYPTED_PDF"


def test_pdf_javascript_is_warned_not_executed(tmp_path: Path) -> None:
    r = inspect_file(f.write(tmp_path, "a.pdf", f.pdf_bytes(javascript=True)), "a.pdf", LIMITS)
    assert r.warnings == ["pdf_active_content:javascript"]


def test_pdf_open_action_alone_is_not_flagged(tmp_path: Path) -> None:
    """Benign PDFs (e.g. from LibreOffice) use /OpenAction just to set the initial view."""
    data = f.pdf_bytes().replace(
        b"/Pages 2 0 R", b"/Pages 2 0 R /OpenAction [3 0 R /XYZ null null 0]"
    )
    r = inspect_file(f.write(tmp_path, "a.pdf", data), "a.pdf", LIMITS)
    assert r.warnings == []


def test_pdf_hex_escaped_javascript_detected(tmp_path: Path) -> None:
    data = f.pdf_bytes(javascript=True, hex_escaped=True)
    r = inspect_file(f.write(tmp_path, "a.pdf", data), "a.pdf", LIMITS)
    assert "pdf_active_content:javascript" in r.warnings
