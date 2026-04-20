# Known Issues

Living list of things the operator should know about but that are not
worth interrupting a milestone for. Each entry has a trigger, an
owner, and an escalation path. Remove entries once they're resolved.

> **Validation note (2026-04-20):** T-M17.1 pipeline resilience + T-M17.2
> patient model were validated end-to-end on the live VPS against real
> production-shape data. A single visit (Kasra, Primary Care, 16:05 UTC)
> hit three retryable Claude failures — one SCHEMA_FAIL on `tm_entities`,
> one SCHEMA_FAIL on `tm_rx_drafting`, one JSON_PARSE_FAIL on
> `tm_icd_coding` — and the T-M17.1 two-retry loop caught all three
> without surfacing a user-visible failure. All three failed rows
> persisted `errorDetails` to `ai_calls` as designed. T-M17.2 patient
> linkage verified at 18/18 visits post-deploy.

---

## KI-1 — L3 `tm_entities` SCHEMA_FAIL rate on dense-entity specialties <sub>RESOLVED 2026-04-20</sub>

**First observed:** 2026-04-20 (T-M16.4 post-deploy; visit
`cmo7brsct000101pepxco9u4w`, Cardiology).

**Pattern:** across the first 16 production visits, `tm_entities` (layer
`03-extract-entities.ts`) produced 6 `SCHEMA_FAIL` events, all on
Cardiology visits (4 distinct Cardiology visits, 10 total
`tm_entities` calls → 60% per-call failure rate for that cohort). The
other 12 visits (Orthopedics + Internal Medicine) produced zero
`tm_entities` schema failures.

**Mode:** Zod reports `expected: 'string', code: 'invalid_type',
message: 'Invalid input: expected string, received undefined'` on a
nested required string (typically a list-item field like
`medications[i].name` or an `evidence_quote`). The prompt is
specialty-agnostic, so this is model-output variance — not a
cardiology-specific template issue. Cardiology audio tends to produce
denser entity graphs (cardiac ROS + multiple meds + family history),
which plausibly amplifies the failure rate.

**Mitigation shipped (T-M17.1, 2026-04-20):**
- `packages/ai/src/model-client.ts` retry count raised from 1 → 2,
  and the retry branch now also covers `JSON_PARSE_FAIL` (which showed
  the same drop-rate pattern on `tm_icd_coding`).
- `ai_calls.errorDetails` TEXT column added; `anthropicComplete` writes
  the raw model response (capped at ~10 KB) on `SCHEMA_FAIL` /
  `JSON_PARSE_FAIL` rows so future incidents can be root-caused from
  `psql` without relying on the worker log buffer.

**How to check if the mitigation is working:**
```sql
SELECT
  DATE_TRUNC('day', "createdAt") AS day,
  COUNT(*) FILTER (WHERE success = false AND "errorCode" = 'SCHEMA_FAIL') AS schema_fails,
  COUNT(*) AS total_calls,
  ROUND(100.0 * COUNT(*) FILTER (WHERE success = false AND "errorCode" = 'SCHEMA_FAIL') / NULLIF(COUNT(*), 0), 2) AS fail_pct
FROM ai_calls
WHERE purpose = 'tm_entities' AND "createdAt" > NOW() - INTERVAL '30 days'
GROUP BY 1 ORDER BY 1 DESC;
```
Target: `fail_pct < 1%` per day after T-M17.1. At 1-2 retries the
*per-call* SCHEMA_FAIL rate won't change — what should change is the
rate at which a whole layer call bubbles up as failed (i.e., the rate
at which BullMQ sees a job FAIL), which is a downstream effect of
exhausting retries. Look at `transcribe_visits.status = 'FAILED'` or
`reviewReason LIKE 'SCHEMA_FAIL%'` as the user-facing outcome metric.

**Escalation — T-M17.2 tool_use refactor:**
If SCHEMA_FAIL *still* causes user-visible "processing failed" events
after T-M17.1 is live for a week across ≥50 visits, escalate to
T-M17.2: move `03-extract-entities.ts` (and the L7a-e automation
layers) from prompt-and-parse-JSON to the Anthropic `tool_use` API.
`tool_use` forces the model to emit arguments conforming to a JSON
Schema at the decoder level — near-zero JSON-parse or missing-field
failures in practice. This is a larger refactor (touches 6+ layer
files + the modelClient abstraction), hence deferred as its own
milestone.

**Resolution (2026-04-20, same day):** T-M17.1 mitigation cleared
the user-visible failure rate on the very next incident — a
Cardiology-shape visit on 2026-04-20 16:05 UTC hit three
independent retryable failures across three different layers
(`tm_entities` SCHEMA_FAIL, `tm_rx_drafting` SCHEMA_FAIL,
`tm_icd_coding` JSON_PARSE_FAIL), all succeeded on the second
attempt, and the visit reached `status=READY` instead of FAILED.
`ai_calls.errorDetails` captured the raw model output for all
three (858 B / 5310 B / 2275 B, well under the 10 KB cap),
giving us the first on-disk post-mortem material this class of
failure has ever left behind. Closing KI-1 until / unless the
rate climbs past 1%/day as measured by the SQL in the original
entry. Tool_use refactor is no longer on the near-term roadmap.

---

## KI-2 — Case-variant duplicate patients in legacy data

**First observed:** 2026-04-20 (T-M17.2 Phase 3 E2E verification).

**Pattern:** the T-M17.2 Phase 1 backfill deduped `TranscribeMdPatient`
rows by `LOWER(TRIM(patientName))` per practice, but did NOT merge
rows that were already distinct in the DB. Practice
`cmo5ye2nf000b01s3q0xlkaxb` currently has two rows — `Kasra` and
`kAsra` — that collide case-insensitively. They both have null DOB
so disambiguation from metadata alone is ambiguous.

**Runtime impact:** `createVisitAction.resolvePatient` uses Prisma's
case-insensitive equals, so the *next* visit named "Kasra" (any
case) will pick whichever row Prisma returns first. After that,
linkage is stable — but two different visits can end up on two
different patient records that should arguably have been one.

**Mitigation:** none in the current milestone. Safe for now at the
observed scale (1 duplicate across 13 patients).

**Escalation — T-M18+ "merge patients" UI:**
Add a doctor-facing "Merge into existing patient" action from the
patient detail page: pick a second patient, confirm, the server
re-FKs every `transcribe_visits.patientId` from source → target
and soft-deletes the source. A one-shot cleanup SQL in the
meantime is also viable if duplicates multiply before that ships.

---

## KI-3 — Abandoned QUEUED visits accumulate without cleanup

**First observed:** 2026-04-20 (T-M17.2 Phase 3 E2E verification —
Kash's visit `cmo7kj4o8…`).

**Pattern:** `/visits/new` creates a `TranscribeVisit` row in
`status=QUEUED` as soon as the doctor clicks a capture-mode tile.
If the doctor then walks away without uploading audio, starting a
dictation, or submitting text notes, the row sits in QUEUED
indefinitely — `audioKey`, `dictationAudioKey`, and `rawTextInput`
are all NULL, and the worker never picks it up because the
per-mode upload route is what enqueues the BullMQ job.

T-M16.4's stuck-job banners (10-min amber, 30-min red) render on
`/visits/[id]` only if the user is actually looking at the visit.
A user who never returns never sees them, and the row is invisible
to the dashboard's patient-centric view unless they click through.

**Runtime impact:** cosmetic — tiny row with all NULLs, zero audio
bytes, zero AI calls. No storage / compute / billing impact. Will
show up as a dangling "QUEUED" card if the doctor ever clicks
through on the linked patient.

**Mitigation:** none in the current milestone.

**Escalation — T-M18+ stuck-job cleanup sweep:**
Scheduled sweep similar to the T-M12 MinIO orphan cleanup: find
visits where `status=QUEUED AND audioKey IS NULL AND dictationAudioKey
IS NULL AND rawTextInput IS NULL AND createdAt < now() - interval
'24 hours'`; transition them to FAILED with reviewReason
`"Abandoned — no input within 24 hours"`. Or hard-delete — this
class of row is pure UI noise with nothing to recover.

---
