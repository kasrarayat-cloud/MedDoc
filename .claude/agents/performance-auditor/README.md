# Performance Auditor

> **Status: SHADOW MODE** (active, advisory-only) at file creation in
> `agent/performance-auditor-v1`. Runs on demand against production
> telemetry; findings route to
> `docs/agent-shadow-runs/performance/<UTC>.md` (advisory) instead of
> a production-blocking path. Findings do NOT block any merge,
> deploy, or operator action — they're advisory until graduation.
> Trigger phrase: **"Run the performance shadow audit"**. See
> `SKILL.md` and `skills/activation-criteria.md`.

An agent that audits QuillMD's runtime performance posture: pipeline
round-trip time, BullMQ queue depth + DLQ accumulation, Prisma N+1
patterns at PR time, route TTFB on the high-traffic visit pages,
client bundle-size delta. Read-only against the live database +
Redis + Next.js build artifacts.

## Why a separate agent (not part of the other four)

QuillMD already has four agents:

- **`qa-interaction-auditor`** (active v3.3) — walks UI surfaces;
  catches click-class bugs.
- **`ai-pipeline-auditor`** (shadow) — audits AI pipeline drift in
  cost/quality/coverage/model-assignment.
- **`hipaa-compliance-auditor`** (shadow) — compliance posture
  drift across §164.308 / §164.310 / §164.312.
- **`code-quality-auditor`** (active v1.1) — pattern drift at PR
  time across token / component / schema / pipeline / boundary /
  layout / scope / a11y rules.

None of them catch **performance drift** — is the SOAP pipeline
suddenly p95'ing 2.3× longer than baseline? Are jobs piling up in
the BullMQ queue without enough workers? Did a new visit-list
query introduce N+1 behaviour? Did a webpack import balloon the
visit-page bundle past the 250 KB Linear-V1 budget? Performance
lives at a different layer than UI behavior, AI quality, compliance
posture, or pattern drift, so a separate agent is the right shape.

The five agents form a circle: front-end behaviour, AI pipeline
drift, compliance posture, source-code patterns, runtime
performance.

## Scope

**In scope:**

- **Pipeline RTT** — per-visit end-to-end time from upload to
  `status=READY`. Read from `transcribe_visits.uploadedAt` →
  `processedAt` (or equivalent terminal timestamp).
- **BullMQ queue depth + DLQ** — `bull:transcribe-md:waiting`,
  `bull:transcribe-md:active`, `bull:transcribe-md:delayed`,
  `bull:transcribe-md-dlq:waiting` Redis sets.
- **Prisma N+1 on diff** — static check against the diff for
  patterns like `forEach(... await prisma.x.findUnique ...)` or
  similar in-loop query shapes.
- **Route TTFB** — Server-side render time for `/visits`,
  `/visits/[id]`, `/visits/[id]/record`. Measured via per-route
  `X-Response-Time` headers (already emitted by `withApiHandler`)
  read from `audit_logs` if the timing is recorded there, or via
  a dedicated lightweight measurement bucket.
- **Bundle size delta** — Compares the Next.js build output's
  `app-build-manifest.json` size for the three high-traffic visit
  routes against a prior baseline; flags increases beyond a
  configured threshold.

**Out of scope:**

- AI pipeline cost (owned by ai-pipeline-auditor)
- UI a11y / behaviour (owned by qa-interaction-auditor)
- Compliance posture (owned by hipaa-compliance-auditor)
- Pattern drift in source code (owned by code-quality-auditor;
  except: Prisma N+1 on diff overlaps mildly with code-quality —
  see CHARTERS.md for the seam)
- Production infrastructure (CPU, RAM, disk on the VPS) — that's
  operator-owned via existing monitoring dashboards.

## How I run

Read-only. Never writes. Never reads PHI content. The audit reads:

- Structured columns of `transcribe_visits` (timestamps + counts
  only; never `transcript`, `soapDraft`, `soapFinal`).
- `audit_logs` for response-time markers if present.
- Redis SETs for queue / DLQ depth (key counts only; payloads are
  not deserialized).
- The Next.js build manifest for bundle-size comparison.

## Companion docs

- [`SKILL.md`](SKILL.md) — skill registration; trigger phrase;
  output contract.
- [`skills/activation-criteria.md`](skills/activation-criteria.md)
  — shadow mode + graduation criteria.
- [`skills/data-sources.md`](skills/data-sources.md) — exact tables
  / Redis keys / files read.
- [`skills/finding-classes.md`](skills/finding-classes.md) —
  severity taxonomy.
- [`skills/methodology.md`](skills/methodology.md) — phase-by-phase
  audit algorithm.
