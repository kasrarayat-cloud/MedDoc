# Finding 09 — Error handling

For each error class — 429, 500, schema fail, JSON fail,
content-moderation refusal, timeout — what does the pipeline
do today and where are the gaps.

---

## Current error-handling map

| Error class | Detection | Action | Doctor sees |
|---|---|---|---|
| 429 rate limit (Anthropic) | SDK throws | Worker catch → BullMQ retry (default 3 attempts with backoff) | "Try retrying this visit" |
| 5xx provider error | SDK throws | Worker catch → BullMQ retry, OR `provider_down` path if 3+ fails in 60s | "Provider temporarily unavailable" |
| 4xx (non-429) | SDK throws | Worker catch → marks `permanent` → fail-fast | Generic |
| Invalid JSON output | `JSON.parse` throws in `anthropicComplete` | Re-throw → modelClient retries up to 2x with retry-context | "Try retrying" if final |
| Schema fail (Zod) | `safeParse` returns `{success: false}` | Re-throw → modelClient retries up to 2x | Same |
| Content-moderation refusal | **No specific detection** — see Finding 06.5 | Falls into JSON-parse-fail or schema-fail path → wasted retries | Generic |
| Timeout | `withTimeout` 15min hard cap in worker | Worker catch | "Try retrying" |
| Hung Anthropic stream | Same — withTimeout | Same | Same |
| Pipeline reject (PR-D guards) | `PipelineRejectError` | Mapped to `permanent`, fail-fast | Specific actionable message |

Generally well-handled. Key gaps are:

---

## 09.1 — Content-moderation refusals are not categorized; waste retries

**Severity:** Q1
**Layer affected:** packages/ai/anthropic.ts → worker.ts
**Quality dimension:** robustness, doctor-experience

(Already documented in Finding 06.5 — listed here for the
error-handling audit.)

### Recommended fix

Detect `response.stop_reason === 'refusal'`, throw with
errorCode='ANTHROPIC_REFUSAL', map to `permanent` in
`error-categorize.ts`, surface a doctor-actionable
`reviewReason` in `buildUserFacingFailureReason` in
`worker.ts:888-925`.

---

## 09.2 — Per-attempt partial-result preservation is good but L5+L6 chain has a gap

**Severity:** Q2
**Layer affected:** worker.ts orchestration
**Quality dimension:** robustness

### What's happening today

`worker.ts:308-310, 661-680` — T-M13 layer-skip checkpointing.
Each layer's output is persisted; on retry the worker reads
the prior state and skips completed layers.

This is correct for L1-L4 + L7. For L5 + L6, the chain is:
- L5 produces `critique`
- L6 produces `soapFinal`

If L5 succeeds and L6 fails, retry skips L5 and re-runs L6.
✓ Good.

If L4 produces `soapDraft`, L5 succeeds, then L6 starts and
fails partway through... actually L6 either succeeds in
producing soapFinal or doesn't (binary). The skip check is
`isLayerComplete(resumeState, 'L6')` which checks
`soapFinal !== null`. ✓ Good.

### Where there might be a subtle gap

If L5 succeeds with `safe_to_sign_without_review = true` and
L6 is short-circuited (no fixable issues, soapFinal =
soapDraft), then `soapL6Original` is set. ✓ Good.

If the doctor edits the SOAP after sign, `soapFinal` gets
overwritten but `soapL6Original` is preserved (`06-polish.ts:111`
explains this).

But: if L6 model call fails AFTER the prisma update lands
(unlikely — the update is the last thing before return), we
could have `soapFinal` set but the layer-status reporting
`failed`. The skip-check would then read soapFinal as
"complete" on next retry and not re-run L6 even though it
errored. **Edge case** — the current ordering is:

```typescript
// 06-polish.ts:101-117
await prisma.transcribeVisit.update({...});  // sets soapFinal
return { soapFinal, needsReview, reviewReason, unfixable };
```

The update lands BEFORE the return, but the update's success
implies the layer's success — the await would throw if the
update failed.

### Verdict

Actually correct as-implemented. No real gap. Move on.

---

## 09.3 — Worker timeout is 15min hard cap — fine, but per-layer breakdown would help observability

**Severity:** Q3
**Layer affected:** worker.ts
**Quality dimension:** observability

### What's happening today

`worker.ts:95-98` — `JOB_TIMEOUT_MS = 15min`. The whole
pipeline (L1 through L7 fan-out) must complete in 15 min.

When the timeout fires, we know the visit failed but not which
layer was running. `currentLayer` gets passed to the Sentry tag
(per Round 3 PR-H) so Sentry shows the layer.

### Why this is a (very low) quality issue

Per-layer timing is captured in `latencyMs` per AiCall row.
That's the data for "which layer was slow." So the
observability is fine via SQL aggregation.

### Recommended fix

No change. Document in worker.ts that per-layer timing comes
from `AiCall.latencyMs`.

---

## 09.4 — Schema-fail retry context appends previous output + zod errors — appropriate

**Severity:** Q3 (positive observation)
**Layer affected:** model-client.ts
**Quality dimension:** robustness

### What's happening today

`model-client.ts:89-93`:

```typescript
const rawOutput = (err as Error & { rawOutput?: string }).rawOutput;
const zodErrors = (err as Error & { zodErrors?: unknown }).zodErrors;
retryContext = zodErrors
  ? `${rawOutput ?? ''}\n\nZod errors:\n${JSON.stringify(zodErrors, null, 2)}`
  : `Previous response failed to parse: ${err.message}`;
```

Previous output + structured Zod errors are passed back to the
model. This is the canonical "fix your output" pattern and
works well.

### Worth amplifying

Per Finding 06.9: tool-use mode would mostly eliminate the
retry-on-schema-fail path. But until that migration, this
pattern is the right pattern.

---

## 09.5 — Layer-7 fan-out is `Promise.allSettled` — single L7 failure doesn't fail the visit

**Severity:** Q3 (positive observation)
**Layer affected:** worker.ts:681
**Quality dimension:** robustness

### What's happening today

`worker.ts:681`:

```typescript
const results = await Promise.allSettled(toRun.map((t) => t.run()));
```

If L7a succeeds and L7c fails, the visit still completes with
ICD codes but no Rx drafts. The failed-layer column gets
nulled (`worker.ts:741`) and `confidenceScores[t.key] =
{ status: 'failed', reason: ... }`.

Doctor sees the visit READY with partial automation outputs.

### Why this is right

L7 layers are independent. A coding failure shouldn't deny
the doctor the SOAP they need. A patient-summary failure
shouldn't deny them the codes.

`needsReview` doesn't auto-fire for L7 failures (the
confidenceScores tells the UI to show a "this layer failed"
banner per-layer). That's appropriate.

### Worth amplifying

This is the right pattern. Calling it out so future changes
don't "fix" it by promoting L7 failures into visit failures.

---

## 09.6 — `notifyAdminOnFailure` is best-effort — appropriate

**Severity:** Q3 (positive observation)
**Layer affected:** worker.ts:847-871
**Quality dimension:** robustness

### What's happening today

`worker.ts:847-871` — admin notification on visit failure
swallows all errors internally:

```typescript
void prisma.user.findUnique(...).then(u =>
  notifyAdminOnFailure({...})
).catch((notifyErr: unknown) => {
  console.error(...);
});
```

A misconfigured Resend account doesn't mask the underlying
pipeline error. ✓ Good.

### Worth amplifying

This is the right pattern. Sentry capture happens BEFORE the
notify attempt (line 785), so Sentry sees the failure
regardless of email delivery.

---

## 09.7 — Categorize-error has a `provider_down` heuristic; works for the pipeline

**Severity:** Q3 (positive observation)
**Layer affected:** worker/error-categorize.ts
**Quality dimension:** robustness

### What's happening today

`error-categorize.ts:31-42` — tracks per-provider 5xx
counts in a 60s window. After 3 hits, the provider is
marked "down" and the doctor sees a more specific
`reviewReason`.

In-memory ring per worker process. Not Redis-backed. For
single-worker concurrency (CONCURRENCY=2 today), accurate.

### Worth amplifying

If we ever go multi-worker, this needs to move to Redis.
Until then, in-memory is fine. The comment in the file
already calls this out.
