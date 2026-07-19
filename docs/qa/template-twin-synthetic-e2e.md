# Template Twin synthetic infrastructure E2E

When executed successfully, this gate is designed to prove the safe-alpha
vertical slice against the repository’s throwaway QA infrastructure. It is not
a production, HIPAA, provider, Word, or LibreOffice attestation.

**Historical execution status:** `PASS` on 2026-07-15 — one Playwright scenario
completed in 24.9 seconds against freshly migrated disposable QA PostgreSQL,
the real Redis/worker boundary, and versioned/object-lock-capable QA MinIO. That
run applied the then-current 70 migrations and removed the Compose stack and
volumes afterward. It predates the ordinary-placeholder, custom-scalar, and
static-asset compatibility work and must not be cited as current-branch proof.
The final compatibility SHA requires a fresh isolated run. CI, desktop Word,
and LibreOffice evidence remain separate gates.

## Infrastructure the scenario is designed to exercise

- Next.js route handlers and cookie-backed physician authorization
- the global fail-closed switch plus the default-off practice rollout flag,
  including a disabled upload attempt
- QA PostgreSQL with deployed Prisma migrations and tenant constraints
- Redis/BullMQ plus the real TranscribeMD worker boundary
- the shared model/transcription client with a dedicated synthetic-only mock
- the dedicated private, versioned/object-lock-capable QA Template Twin MinIO
  bucket and the explicit synthetic-only readiness exception
- deterministic DOCX compilation, resolution, validation, exact rendering,
  independent output readback, and static-region verification
- physician correction, SOAP edit invalidation, worker regeneration, signing,
  and Original Template DOCX download
- sign-time stream hashing with no destination selected
- adversarial removal of the exact pinned QA object version, which must leave
  the visit unsigned even if a key could have another latest version

The in-memory DOCX has four clinically meaningful fields: native text, an
exact-option native dropdown, a native checkbox, and a text control inside a
fixed table. It also has a static title, header, footer, and Word placeholder
metadata. Every string and account is explicitly synthetic; accounts use only
`@synthetic.test`.

## Mock boundary

`MOCK_TEMPLATE_TWIN_E2E=true` does nothing by itself. The evidence-bearing
fixture is returned only when the shared `MOCK_AI_CALLS` switch is also exactly
`true` and `DATABASE_URL` parses to a database whose name has a `qa`, `test`,
or `synthetic` segment. Otherwise the existing empty generic entity fixture is
used. No provider network call is made by this project.

## Deliberate release gates outside this test

- opening and visual comparison in desktop Word and LibreOffice
- Word repair-dialog detection and pagination/layout review
- real provider behavior or model quality
- production bucket encryption, object-lock, backup, restore, and IAM evidence
- real PHI, real physician templates, and production migrations
- unbounded or non-scalar custom concepts, plus complex/repeating/rich-text
  structures that safe-alpha certification blocks; the historical scenario
  does not prove the newer physician-certified scalar custom-concept path

The test must not be cited as evidence that Template Twin is real-PHI-ready.
QA readiness verifies the local bucket's private policy plus
versioning/object-lock capability and requires separate named exceptions for
each remaining local-only gap. Those exceptions report `productionReady:
false`; they do not attest production encryption, TLS, IAM,
lifecycle/retention, backup, restore, or legal-hold controls.
