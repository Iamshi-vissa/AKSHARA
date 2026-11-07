# ADR 0004 — Content-based upload safety gate

Status: accepted (Phase 1)

**Decision.** `core/filesafety.py` decides the type from content (magic bytes, OOXML content
types), never from the extension alone. It rejects macro-enabled packages, encrypted or legacy
OLE files, encrypted PDFs, ZIP path traversal, too many parts, excessive decompressed size and
suspicious compression ratios; XML is parsed with `defusedxml`. PDFs with active content
(JavaScript, launch, embedded files, form-submit...) are accepted but flagged; nothing is ever
executed. Trigger keys such as `/OpenAction` are not flagged on their own, because ordinary
PDFs use them to set the opening view (found while testing real LibreOffice output).

**Consequences.** The gate reads bytes only. Deep parsing happens in sandboxed workers from
Phase 2. Limits are configurable (`AKSHARA_MAX_*`).
