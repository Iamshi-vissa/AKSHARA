"""What the running build can actually do.

The frontend uses this to show unbuilt modules as unavailable instead of faking them
(engineering rule: never build a fake working interface). Update this list as each phase is
verified.
"""

from __future__ import annotations

from app.schemas.system import Capability

CAPABILITIES: list[Capability] = [
    Capability(
        key="upload",
        label="Secure upload & library",
        available=True,
        phase=1,
        note="DOCX, PDF and PPTX with content-based validation.",
    ),
    Capability(
        key="versions",
        label="Immutable originals & versions",
        available=True,
        phase=1,
        note="Originals are stored once and never overwritten.",
    ),
    Capability(
        key="preview",
        label="Document parsing & preview",
        available=False,
        phase=2,
        note="Canonical document model and page rendering.",
    ),
    Capability(
        key="inspect",
        label="Inspect document",
        available=False,
        phase=3,
        note="Structural and formatting defects with severity levels.",
    ),
    Capability(
        key="standards",
        label="Apply standard (UDSE)",
        available=False,
        phase=4,
        note="IEEE, APA, MLA and custom rule profiles.",
    ),
    Capability(
        key="edit",
        label="Edit & auto-correct",
        available=False,
        phase=5,
        note="Tracked, approval-gated changes.",
    ),
    Capability(
        key="create",
        label="Create document",
        available=False,
        phase=6,
        note="Outline-first generation with DOCX/PDF export.",
    ),
    Capability(
        key="presentations",
        label="Generate presentation",
        available=False,
        phase=7,
        note="Themed PPTX with slide validation.",
    ),
    Capability(
        key="visual",
        label="Visual quality",
        available=False,
        phase=8,
        note="Render-based layout defect detection.",
    ),
    Capability(
        key="research",
        label="References & research",
        available=False,
        phase=9,
        note="Verified citations, never fabricated.",
    ),
]
