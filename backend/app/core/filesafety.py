"""Upload safety gate.

Every uploaded file passes through :func:`inspect_file` before it is stored. The gate never
executes or renders content. It only reads bytes and (for OOXML) the ZIP directory and
``[Content_Types].xml``, parsed with ``defusedxml`` so XML entity attacks cannot fire.

Policy (see docs/ARCHITECTURE.md §0 D15 and §10 R5):

* The type is decided by **content** (magic bytes + package structure), never by the file
  extension alone. A mismatch between extension and content is rejected.
* OOXML: reject macro-enabled packages (``.docm``/``.pptm`` content types or any
  ``vbaProject.bin``), encrypted entries, path traversal, too many entries, too much
  decompressed data, and suspicious compression ratios (zip bombs).
* Legacy/encrypted OLE files (``.doc``/``.ppt`` or password-protected OOXML) are rejected
  with a clear message.
* PDF: reject encrypted files. Active content (JavaScript, launch actions, embedded files)
  is **reported as a warning**, never executed. AKSHARA never runs it.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Literal

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

DocumentKind = Literal["docx", "pdf", "pptx"]

_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_ZIP_MAGIC = b"PK\x03\x04"
_PDF_MAGIC = b"%PDF-"

_CT_NS = "{http://schemas.openxmlformats.org/package/2006/content-types}"

_MAIN_CONTENT_TYPES: dict[str, DocumentKind] = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml": "docx",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml": "docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml": "pptx",
    "application/vnd.openxmlformats-officedocument.presentationml.slideshow.main+xml": "pptx",
}

_MACRO_CONTENT_TYPES = {
    "application/vnd.ms-word.document.macroEnabled.main+xml",
    "application/vnd.ms-word.template.macroEnabledTemplate.main+xml",
    "application/vnd.ms-powerpoint.presentation.macroEnabled.main+xml",
    "application/vnd.ms-powerpoint.slideshow.macroEnabled.main+xml",
    "application/vnd.ms-office.vbaProject",
}

EXTENSIONS: dict[str, DocumentKind] = {".docx": "docx", ".pdf": "pdf", ".pptx": "pptx"}

MIME_TYPES: dict[DocumentKind, str] = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "pdf": "application/pdf",
}

# PDF name tokens that indicate *active* content. PDF names may hex-escape characters
# (/J#61vaScript), so names are normalised before matching. Trigger keys such as /OpenAction
# or /AA are deliberately not flagged on their own: ordinary PDFs use them to set the opening
# view. What matters is the action *type* they could invoke, which is listed here.
_PDF_ACTIVE_NAMES = {
    b"/JavaScript": "javascript",
    b"/JS": "javascript",
    b"/Launch": "launch_action",
    b"/EmbeddedFile": "embedded_file",
    b"/RichMedia": "rich_media",
    b"/XFA": "xfa_form",
    b"/SubmitForm": "submit_form",
    b"/ImportData": "import_data",
    b"/GoToE": "embedded_goto",
}
_PDF_NAME_RE = re.compile(rb"/[A-Za-z0-9#]+")
_PDF_HEX_ESCAPE_RE = re.compile(rb"#([0-9A-Fa-f]{2})")


@dataclass(frozen=True)
class SafetyLimits:
    max_bytes: int
    max_uncompressed_bytes: int
    max_entries: int
    max_compression_ratio: int


@dataclass
class FileInspection:
    kind: DocumentKind
    mime_type: str
    size_bytes: int
    warnings: list[str] = field(default_factory=list)


class FileRejected(Exception):
    """The file must not be accepted. ``code`` is stable and safe to show to users."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def kind_from_filename(filename: str) -> DocumentKind:
    suffix = PurePosixPath(filename.replace("\\", "/")).suffix.lower()
    if suffix in {".docm", ".pptm", ".dotm", ".potm", ".ppsm"}:
        raise FileRejected(
            "MACRO_ENABLED",
            "Macro-enabled documents are not accepted. Save the file as .docx or .pptx.",
        )
    if suffix in {".doc", ".ppt"}:
        raise FileRejected(
            "LEGACY_FORMAT",
            "Legacy Office formats are not supported. Save the file as .docx or .pptx.",
        )
    kind = EXTENSIONS.get(suffix)
    if kind is None:
        raise FileRejected(
            "UNSUPPORTED_EXTENSION", "Only .docx, .pdf and .pptx files are supported."
        )
    return kind


def inspect_file(path: Path, filename: str, limits: SafetyLimits) -> FileInspection:
    expected = kind_from_filename(filename)
    size = path.stat().st_size
    if size == 0:
        raise FileRejected("EMPTY_FILE", "The file is empty.")
    if size > limits.max_bytes:
        raise FileRejected(
            "FILE_TOO_LARGE",
            f"The file is larger than the {limits.max_bytes // (1024 * 1024)} MB limit.",
        )

    with path.open("rb") as fh:
        head = fh.read(1024)

    if head.startswith(_OLE_MAGIC):
        raise FileRejected(
            "ENCRYPTED_OR_LEGACY",
            "This looks like a password-protected or legacy Office file. "
            "Remove the password or save it as .docx/.pptx and try again.",
        )

    if head.startswith(_ZIP_MAGIC):
        detected = _inspect_ooxml(path, limits)
        warnings: list[str] = []
    elif _PDF_MAGIC in head:
        detected = "pdf"
        warnings = _inspect_pdf(path)
    else:
        raise FileRejected(
            "UNRECOGNISED_CONTENT", "The file content is not a valid DOCX, PDF or PPTX document."
        )

    if detected != expected:
        raise FileRejected(
            "EXTENSION_MISMATCH",
            f"The file is named .{expected} but its content is {detected.upper()}.",
        )
    return FileInspection(
        kind=detected, mime_type=MIME_TYPES[detected], size_bytes=size, warnings=warnings
    )


def _inspect_ooxml(path: Path, limits: SafetyLimits) -> DocumentKind:
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise FileRejected("CORRUPT_PACKAGE", "The document package is damaged.") from exc

    with zf:
        infos = zf.infolist()
        if len(infos) > limits.max_entries:
            raise FileRejected("TOO_MANY_PARTS", "The document contains too many internal parts.")

        total = 0
        names: set[str] = set()
        for info in infos:
            name = info.filename
            parts = PurePosixPath(name).parts
            if name.startswith(("/", "\\")) or ".." in parts or "\\" in name or ":" in name:
                raise FileRejected("UNSAFE_PATH", "The document package contains unsafe paths.")
            if info.flag_bits & 0x1:
                raise FileRejected("ENCRYPTED_PART", "Encrypted document parts are not supported.")
            total += info.file_size
            if total > limits.max_uncompressed_bytes:
                raise FileRejected(
                    "DECOMPRESSION_LIMIT", "The document expands to more data than allowed."
                )
            if info.file_size > 1024 * 1024 and info.file_size > limits.max_compression_ratio * max(
                info.compress_size, 1
            ):
                raise FileRejected(
                    "COMPRESSION_RATIO", "The document has a suspicious compression ratio."
                )
            names.add(name.lower())

        if any(n.endswith("vbaproject.bin") for n in names):
            raise FileRejected(
                "MACRO_ENABLED",
                "The document contains macros. Macro-enabled documents are not accepted.",
            )
        if "[content_types].xml" not in names:
            raise FileRejected("NOT_OOXML", "The file is a ZIP archive, not an Office document.")

        ct_name = next(i.filename for i in infos if i.filename.lower() == "[content_types].xml")
        ct_info = zf.getinfo(ct_name)
        if ct_info.file_size > 5 * 1024 * 1024:
            raise FileRejected("CORRUPT_PACKAGE", "The document package is damaged.")
        try:
            root = SafeET.fromstring(zf.read(ct_name))
        except (DefusedXmlException, SafeET.ParseError) as exc:
            raise FileRejected("CORRUPT_PACKAGE", "The document package is damaged.") from exc

    content_types = {
        el.get("ContentType", "")
        for el in root.iter()
        if el.tag in (f"{_CT_NS}Override", f"{_CT_NS}Default")
    }
    if content_types & _MACRO_CONTENT_TYPES:
        raise FileRejected(
            "MACRO_ENABLED",
            "The document is macro-enabled. Save it as .docx or .pptx without macros.",
        )
    kinds = {_MAIN_CONTENT_TYPES[ct] for ct in content_types if ct in _MAIN_CONTENT_TYPES}
    if len(kinds) != 1:
        raise FileRejected(
            "UNSUPPORTED_PACKAGE", "The Office package is not a Word or PowerPoint document."
        )
    return kinds.pop()


def _normalise_pdf_name(name: bytes) -> bytes:
    return _PDF_HEX_ESCAPE_RE.sub(lambda m: bytes([int(m.group(1), 16)]), name)


def _inspect_pdf(path: Path) -> list[str]:
    """Byte-level scan. Does not parse or render; Phase 2 parses with PyMuPDF in a worker."""
    found: set[str] = set()
    encrypted = False
    tail = b""
    chunk_size = 1024 * 1024
    with path.open("rb") as fh:
        while chunk := fh.read(chunk_size):
            window = tail + chunk
            for raw in _PDF_NAME_RE.findall(window):
                name = _normalise_pdf_name(raw)
                if name == b"/Encrypt":
                    encrypted = True
                elif name in _PDF_ACTIVE_NAMES:
                    found.add(_PDF_ACTIVE_NAMES[name])
            tail = window[-64:]
    if encrypted:
        raise FileRejected(
            "ENCRYPTED_PDF", "Password-protected PDFs are not supported. Remove the password first."
        )
    return [f"pdf_active_content:{name}" for name in sorted(found)]
