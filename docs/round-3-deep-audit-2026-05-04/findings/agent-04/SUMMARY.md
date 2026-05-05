# Agent 04 — Input Validation, Injection & Prompt Injection · Summary

## Severity counts
**P0: 0 · P1: 2 · P2: 3 · P3: 1 · Total: 6**

## Top 3 findings
1. **P1-001 prompt injection across all worker layers** — `apps/transcribe-md/src/worker/layers/{02..07e}` concatenate user text (transcript, dictation, typed notes, `chiefComplaint`, patient name) into Anthropic user messages with no delimiter wrapping; L4 (SOAP draft) and L6 (polish) have no Zod gate, so injected instructions can directly alter the SOAP a doctor signs. Bounded from P0 only because the email-destination pin in `/api/visits/[id]/export/email` blocks PHI exfil and there's no markdown renderer.
2. **P1-002 audio uploads trust Content-Type header** — `/api/visits/[id]/upload` and `/dictation/upload` allow-list MIME headers but never magic-byte-sniff. Bytes labelled `audio/wav` are stored in MinIO with attacker-claimed `audioMimeType` and exported back via `inferAudioExt`.
3. **P2-001 password Zod fields lack `.max()`** — login/signup/reset/change-password/change-email/delete-account all have `password: z.string().min(N)` with no upper bound; bcryptjs.compare runs on up to ~1MB plaintext including the unauthenticated dummy-hash timing equalizer in `actions/auth.ts:173,248`.

## Other findings
- **P2-002** Search query params unbounded
- **P2-003** ID fields lack uuid/cuid format validation
- **P3-001** Stack field on client errors could bloat logs

## Coverage
All 262 Zod usages enumerated across 46 files; both file-upload routes (only two exist) reviewed; all `dangerouslySetInnerHTML` (zero hits); the single `$queryRawUnsafe` (`admin/users/_lib/users-data.ts`) audited and confirmed parameter-safe; all 18 RegExp usages reviewed (no user-controlled regex); all `JSON.parse` (10 hits, all bounded); SSRF surface (every `fetch(`) reviewed — only env-derived or static URLs; CORS confirmed default same-origin; ReDoS — no catastrophic backtracking.

## Positives
1. Audio routes have content-length checks, MIME allow-lists, rate limits; filename sanitisation in `lib/minio.ts:197-202` is correct.
2. Email-destination guard (`/api/visits/[id]/export/email/route.ts:61-87` and `/sign/route.ts:104-133`) hard-pins to session email — load-bearing primitive that keeps prompt injection out of P0.
3. No `dangerouslySetInnerHTML`, no markdown renderer (`react-markdown`/`marked`/`dompurify`/`sanitize-html` absent from package.json AND code) anywhere in `apps/` or `packages/`.
4. The lone `$queryRawUnsafe` is correctly parameter-bound; non-bound pieces draw from closed enum allowlists (`parseStatus`/`parseRole`/`parseProduct`).
5. Anti-enumeration 404 pattern is uniform across `/api/visits/[id]/*` and `/api/patients/[id]/*`.

## Cross-domain hooks
- **Agent 02**: confirm `/sign` clipboard formats can't be coerced to re-route email exfil; P1-001 severity tracks the email-destination pin.
- **Agent 03**: P1-002 attacker-chosen MIME stored in MinIO depends on bucket-serve policy.
- **Agent 06**: "no markdown renderer" positive must hold; if `react-markdown` is added later for SOAP, P1-001 escalates to stored-XSS via injection.
- **Agent 09**: P2-001 bcrypt-DoS and P2-002 search-string DB CPU are rate-limit-amplified.
