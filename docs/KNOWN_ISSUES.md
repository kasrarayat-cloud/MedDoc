# Known Issues

Living list of things the operator should know about but that are not
worth interrupting a milestone for. Each entry has a trigger, an
owner, and an escalation path. Remove entries once they're resolved.

---

## KI-1 — L3 `tm_entities` SCHEMA_FAIL rate on dense-entity specialties

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

---
