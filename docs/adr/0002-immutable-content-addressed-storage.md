# ADR 0002 — Immutable, content-addressed originals

Status: accepted (Phase 1)

**Decision.** Files are stored by SHA-256 and written once. Immutability is enforced at
three layers: the `BlobStorage` interface has no delete/overwrite operation; stored files are
read-only and created with an atomic hard-link that cannot replace an existing file; and
PostgreSQL triggers reject any `UPDATE`/`DELETE` on `blobs` and any change to a version's
`source_blob`. Deleting a document is a soft delete; its original stays in storage.

**Consequences.** Identical uploads share one blob. A future retention/purge policy must be a
separate, audited administrative operation (it will need to lift the trigger deliberately).
