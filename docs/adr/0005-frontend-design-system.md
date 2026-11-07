# ADR 0005 — Frontend stack and "Ink & Gold leaf" theme with React Bits

Status: accepted (Phase 1)

**Decision.** React 19 + TypeScript + Vite + Tailwind CSS 4, TanStack Query for server
state, React Router. API types are generated from the backend's OpenAPI schema. The visual
language is a dark "ink" canvas with paper-white text, indigo for interaction and manuscript
gold for emphasis; Source Serif 4 for display type (documents), Inter for UI, JetBrains Mono
for hashes and metadata. Fonts are self-hosted (no third-party font requests).

Motion comes from a few vendored [React Bits](https://reactbits.dev) components chosen to
match the product's meaning, not decoration for its own sake:

| Component | Where | Why |
|---|---|---|
| Threads | Sign-in hero | Flowing lines, the metaphor of text and documents |
| BlurText | Page headlines | Blur → sharp: "bringing clarity" |
| DecryptedText | Tagline, unbuilt-module pages | Decoding documents |
| ShinyText | Wordmark | A gold-leaf glint on the name |
| SpotlightCard | Quick actions | Focus on what you can do |
| CountUp | Library statistics | Real numbers from the API |
| StatusMark | Upload progress | Real per-file progress, done or failed |

All of them honour `prefers-reduced-motion`. They depend only on `motion`. They are kept
unmodified in `src/components/reactbits/` with their MIT + Commons Clause licence (allowed
inside an application; the components themselves may not be resold or redistributed alone).
Pages are code-split so the WebGL sign-in hero loads only on the auth screens.

**Honesty rule.** Modules that are not built are shown as locked with their phase number,
driven by `/api/v1/capabilities`; they never show placeholder results.
