# ADR 0003 — Self-hosted auth with rotating refresh tokens

Status: accepted (Phase 1)

**Decision.** Argon2id password hashes. 15-minute JWT access tokens kept in browser memory
only. Opaque refresh tokens (only their SHA-256 is stored) in an httpOnly, SameSite=Strict
cookie scoped to `/api/v1/auth`. Every refresh rotates the token; replaying a rotated token
revokes the whole login family. Login and registration are rate-limited (Redis). Resources
owned by another user return 404.

**Consequences.** No third-party account is needed to run AKSHARA. OIDC/SSO can be added
later behind the same service. The browser stores only a non-secret "has signed in" hint in
localStorage, used to avoid a pointless session probe on first visit.
