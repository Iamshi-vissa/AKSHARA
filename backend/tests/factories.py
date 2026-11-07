"""Builders for test documents with known properties.

Files are produced byte-by-byte so each test controls exactly one property (a macro part, a
traversal path, an encrypted PDF...). Phase 2 adds richer fixtures built with python-docx,
python-pptx and ReportLab.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

WORD_MAIN = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
PPT_MAIN = "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"
WORD_MACRO_MAIN = "application/vnd.ms-word.document.macroEnabled.main+xml"


def content_types(main_part: str, main_type: str, extra: str = "") -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f'<Override PartName="/{main_part}" ContentType="{main_type}"/>'
        f"{extra}</Types>"
    )


def ooxml_bytes(
    kind: str = "docx",
    *,
    main_type: str | None = None,
    extra_parts: dict[str, bytes] | None = None,
    ct_override: str | None = None,
) -> bytes:
    main_part = "word/document.xml" if kind == "docx" else "ppt/presentation.xml"
    main_type = main_type or (WORD_MAIN if kind == "docx" else PPT_MAIN)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", ct_override or content_types(main_part, main_type))
        zf.writestr("_rels/.rels", "<Relationships/>")
        zf.writestr(main_part, "<document>AKSHARA test</document>")
        for name, data in (extra_parts or {}).items():
            zf.writestr(name, data)
    return buf.getvalue()


def pdf_bytes(
    *, javascript: bool = False, encrypted: bool = False, hex_escaped: bool = False
) -> bytes:
    catalog_extra = b""
    if javascript:
        name = b"/J#61vaScript" if hex_escaped else b"/JavaScript"
        catalog_extra = b" /OpenAction << /S " + name + b" /JS (app.alert(1)) >>"
    trailer_extra = b" /Encrypt 5 0 R" if encrypted else b""
    return (
        b"%PDF-1.7\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R" + catalog_extra + b" >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >> endobj\n"
        b"trailer << /Root 1 0 R /Size 4" + trailer_extra + b" >>\n%%EOF\n"
    )


def write(tmp: Path, name: str, data: bytes) -> Path:
    path = tmp / name
    path.write_bytes(data)
    return path


def zip_with_entries(entries: dict[str, bytes], ct: str | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if ct is not None:
            zf.writestr("[Content_Types].xml", ct)
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()
