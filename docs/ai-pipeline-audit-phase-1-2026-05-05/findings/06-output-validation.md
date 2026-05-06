# Finding 06 — Output validation

For every model call, this finding examines the parsing pipeline:
schema, retry semantics, silent coercions, and where stricter
validation would catch more errors earlier.

---

## Validation surface map

| Layer | Schema | Retry on schema-fail | Allowlist filter | Other backstop |
|---|---|---|---|---|
| L2 | SpeakerMap | Yes (modelClient) | — | confidence < 0.7 → needsReview |
| L3 | ExtractedEntities (deeply nested) | Yes (2x) | — | — |
| L4 | None — plain text | No | — | — |
| L5 | CritiqueReport | Yes | — | — |
| L6 | None — plain text | No | — | — |
| L7a | IcdResult | Yes | ICD allowlist | — |
| L7b | CptResult | Yes | CPT allowlist + modifier set | — |
| L7c | RxResult | Yes | **none today** (validateRxDose not wired) | — |
| L7d | ReferralsResult | Yes | — | — |
| L7e | PatientSummaryResult | Yes | — | Flesch-Kincaid grade flag |

---

## 06.1 — `validateRxDose` is shipped but never called from production code

**Severity:** Q0 (safety-critical)
**Layer affected:** L7c
**Quality dimension:** safety

### What's happening today

`packages/ai/src/data/dose-ranges-validator.ts` exports
`validateRxDose`. The function is wired into:
- `packages/ai/src/index.ts` (re-export)
- `apps/transcribe-md/src/lib/__tests__/dose-range.test.ts` (tests)
- `docs/LAUNCH_CHECKLIST.md` (mentioned)

**Verified via:**

```
grep -rln "validateRxDose" /opt/meddoc-pro/ --include='*.ts' \
  | grep -v node_modules | grep -v _design-references
→
apps/transcribe-md/src/lib/__tests__/dose-range.test.ts
docs/LAUNCH_CHECKLIST.md
packages/ai/src/index.ts
packages/ai/src/data/dose-ranges-validator.ts
```

The L7c layer (`07c-rx-drafting.ts`) does NOT call it. The Rx
output goes straight from the model into the DB.

### Why this is a quality issue

Round 3 PR-D (audit finding A06-P0-004 partial) shipped the
deterministic dose validator as a "fail-closed safety floor."
The point of the validator is: even if Sonnet's training data
is wrong about a drug's dose, the deterministic check fires
when an out-of-range dose is emitted. Today, that floor is
inert in the production pipeline.

The fail-closed semantics described in the file's comment
header (lines 16-18 of dose-ranges-validator.ts) — "fail-closed
by design" — is true of the validator function but NOT true
of the pipeline because the pipeline doesn't call the
validator.

A doctor relying on the L7c warnings for safety is getting
ONLY the model's training-time pharmacology — no deterministic
backstop fires.

### Recommended fix

Wire `validateRxDose` into L7c after the model output. Two-step:

1. Pull patient context (DOB + weightKg + allergies array) into
   the L7c call. Today the worker doesn't pass these to L7c;
   needs an addition to `Layer7cInput` and a Prisma fetch in
   the worker.

2. After the model returns the `RxResult`, iterate
   `result.prescriptions` and call `validateRxDose` per drug.
   Append validator-emitted warnings to `result.warnings`.
   Emit corresponding audit rows
   (`RX_DOSE_EXCEEDS_VERIFIED_RANGE`,
   `RX_CONTRAINDICATION_MATCH`,
   `RX_DRUG_NOT_IN_VERIFIED_DATABASE`,
   `RX_COMPLEX_DOSING_VERIFY_INDIVIDUALLY`).

The validator already knows how to convert mg/dose × frequency
into mg/day — but the model output uses `strength` ("20 mg")
+ `sig` ("Take 1 tab BID") rather than mg/day directly. Add a
small parser that handles common sigs:
- "1 tab daily" / "1 tablet QD" / "1x/day"
- "1 tab BID" / "twice daily" / "Q12H"
- "1 tab TID" / "every 8 hours"
- "1 tab QID" / "four times daily"
- "PRN" → flag with `complex_dosing_verify_individually`
  (PRN dosing has variable mg/day)

For unparseable sigs, call validateRxDose with `doseMgPerDay:
null` — the validator still runs the contraindication +
complex-dosing checks, just skips the numeric range check.

### Estimated PR scope
**Medium** — patient-context plumbing + sig parser + validator integration + audit emit. Single PR. Consider as the highest-priority fix in the audit.

---

## 06.2 — L4 + L6 have NO output validation (free-form markdown)

**Severity:** Q1
**Layer affected:** L4 / L6
**Quality dimension:** consistency

### What's happening today

`04-generate-soap.ts:123-134` — `modelClient.completeText` (no
schema). The output is whatever the model returns; the only
verification is a `text.trim()` join.

`06-polish.ts:74-87` — same.

If the model produces:
- Empty text — saved as `soapDraft = ""` and the pipeline
  continues
- Non-markdown plain text — saved as-is
- A "preamble" the prompt told it not to include — saved as-is
- A SOAP missing required sections — saved as-is

L5 critique is the only downstream check. It catches some
issues but not all (e.g., empty SOAP would land an "everything
missing" critique but not a hard reject).

### Why this is a quality issue

A failed SOAP draft (empty, malformed, prefixed with
"Sure, here is a SOAP note: ...") still moves through the
pipeline. The doctor sees a broken draft that may or may not
get cleaned up by L6.

### Headroom

Add a structural validator for SOAP output that checks:
- Non-empty
- Contains `## Subjective`, `## Objective`, `## Assessment`,
  `## Plan` markdown headings
- No "Sure, here" / "I'd be happy" / "Here is" preamble
- No "Let me know if" / "I hope this helps" postscript
- Length is plausible (not <100 chars, not >50000)

If the output fails the structural check, retry once with the
specific failure communicated to the model.

### Recommended fix

Add `validateSoapStructure()` in
`apps/transcribe-md/src/worker/layers/soap-validator.ts`:

```typescript
export interface SoapValidationResult {
  ok: boolean;
  errors: string[];
}

export function validateSoapStructure(text: string): SoapValidationResult {
  const errors: string[] = [];
  if (!text || text.trim().length < 100) {
    errors.push('SOAP draft is empty or too short');
  }
  for (const heading of ['## Subjective', '## Objective', '## Assessment', '## Plan']) {
    if (!text.includes(heading)) errors.push(`Missing required heading: ${heading}`);
  }
  if (/^(?:sure|here(?:'s| is)|i'?d be happy|let me|i'?ll)/i.test(text.trim())) {
    errors.push('SOAP draft starts with conversational preamble');
  }
  return { ok: errors.length === 0, errors };
}
```

L4 calls this; on failure, retries once with errors injected
into the user message ("Your previous draft failed: <errors>.
Regenerate following the structure exactly.").

Same for L6 polish.

### Estimated PR scope
**Small** — single validator file + L4/L6 integration.

---

## 06.3 — L3 schema accepts empty strings as valid for required fields

**Severity:** Q1
**Layer affected:** L3
**Quality dimension:** accuracy

### What's happening today

`03-extract-entities.ts:71-79`:

```typescript
chief_complaint: z
  .object({
    statement: z.string(),     // <-- accepts ""
    evidence_quote: z.string().min(1),
    speaker: z.string().optional(),
    timestamp: z.number().nonnegative().optional(),
  })
  .nullable(),
```

`statement` has no `.min(1)` constraint. If the model emits
`{statement: "", evidence_quote: "patient reports headache"}`
the schema accepts it and L4 sees an empty chief complaint.

Similar issues:
- `medications[].name: z.string()` — no min length, accepts ""
- `allergies[].substance: z.string()` — no min length
- `family_history[].relation: z.string()` and `condition: z.string()` — no min length

### Why this is a quality issue

Model occasionally emits placeholder values for required fields
(common when it's been told "OMIT IT if you can't cite
evidence" but doesn't quite). An empty `chief_complaint.statement`
shouldn't validate; it should fail and trigger a retry with
"the chief_complaint must have a non-empty statement".

### Recommended fix

Add `.min(1)` to every business-critical string field:

```typescript
chief_complaint: z
  .object({
    statement: z.string().min(1),  // <-- was z.string()
    ...
  })
  .nullable(),

medications: z.array(z.object({
  name: z.string().min(1),  // <-- was z.string()
  ...
})).default([]),

allergies: z.array(z.object({
  substance: z.string().min(1),
  ...
})).default([]),

family_history: z.array(z.object({
  relation: z.string().min(1),
  condition: z.string().min(1),
  ...
})).default([]),

ros: z.array(z.object({
  system: z.string().min(1),
  finding: z.string().min(1),
  ...
})).default([]),

exam_findings: z.array(z.object({
  system: z.string().min(1),
  finding: z.string().min(1),
  ...
})).default([]),
```

Same pattern for `tests_mentioned`, `assessment_discussed`,
`plan_discussed`, social_history sub-fields.

### Estimated PR scope
**Trivial** — schema-only edit.

---

## 06.4 — L5 critique schema allows empty `description` and `suggested_fix`

**Severity:** Q2
**Layer affected:** L5
**Quality dimension:** completeness

### What's happening today

`05-self-critique.ts:22-27`:

```typescript
export const CritiqueIssue = z.object({
  severity: z.enum(['critical', 'major', 'minor']),
  location: z.string(),       // no min
  description: z.string(),    // no min
  suggested_fix: z.string(),  // no min
});
```

A critique issue could land with `description: ""`, which gives
L6's polish prompt no useful information.

Worse: `isStructurallyFixable` (line 160) reads `issue.description.toLowerCase()`
to decide if the issue is fixable. An empty description gets
treated as "fixable" (no red-flag keywords match) and L6 tries
to apply a fix it has no description for.

### Recommended fix

Add `.min(1)` constraints:

```typescript
export const CritiqueIssue = z.object({
  severity: z.enum(['critical', 'major', 'minor']),
  location: z.string().min(1),
  description: z.string().min(8),  // arbitrary low floor; "missing" is 7 chars
  suggested_fix: z.string().min(1),
});
```

Plus: `isStructurallyFixable` should defensively treat missing
description as `false` (not fixable → preserves the SOAP as-is).

### Estimated PR scope
**Trivial**.

---

## 06.5 — Anthropic SDK refusal / content-moderation events are not specifically handled

**Severity:** Q2
**Layer affected:** model-client / anthropic.ts
**Quality dimension:** robustness, observability

### What's happening today

`anthropic.ts:171-186` — the catch block logs whatever error
the Anthropic SDK throws as `errorCode: err.name.toUpperCase()`.

There's no specific detection for Anthropic refusals. When
Anthropic's content moderation refuses a generation (rare but
possible — e.g., a transcript that triggers self-harm content
guards), the response is typically a stop_reason of `'refusal'`
or a structured refusal in the content array.

### Why this is a quality issue

Refusal handling in the current code: would arrive as a TextBlock
with the refusal text, which fails JSON parsing → SCHEMA_FAIL,
gets retried (which won't help — content moderation is
deterministic). After 2 retries, propagates up. The doctor
sees a generic "processing failed" rather than "Anthropic
declined this content; please review manually".

This is most likely to fire on:
- Visits with detailed self-harm discussion (psychiatry
  specifically)
- Visits with violent-injury detail
- Visits where the patient describes drug-use scenarios in
  detail

### Recommended fix

Detect refusal via stop_reason check after the Anthropic call:

```typescript
// In anthropicComplete, after the messages.create call:
if (response.stop_reason === 'refusal') {
  logAiCall({
    ...args,
    provider: 'anthropic',
    promptHash,
    latencyMs,
    inputTokens: response.usage.input_tokens,
    outputTokens: response.usage.output_tokens,
    success: false,
    errorCode: 'ANTHROPIC_REFUSAL',
    errorDetails: capErrorDetails(text),
  });
  const err = new Error('ANTHROPIC_REFUSAL') as Error;
  throw err;
}
```

Plus: the worker's `error-categorize.ts` should treat
`ANTHROPIC_REFUSAL` as `permanent` (no retry — content
moderation is deterministic), and the `buildUserFacingFailureReason`
should map it to something doctor-actionable:

> "Our AI declined to process this content. The visit may
>  contain material that triggers our provider's safety guards
>  (e.g., detailed descriptions of self-harm or violence).
>  You can write the SOAP manually for this visit."

### Estimated PR scope
**Small** — anthropic.ts refusal detection + error-categorize update + worker reason mapping.

---

## 06.6 — L7a/L7b confidence has no minimum-confidence threshold for inclusion

**Severity:** Q2
**Layer affected:** L7a (and analogous in L7b)
**Quality dimension:** safety, billing

### What's happening today

`07a-icd-coding.ts:23-25`:

```typescript
confidence: z.number().min(0).max(1),
```

No floor. The model can emit `confidence: 0.05` and the schema
accepts it. The UI displays it as red (per the prompt
documentation, <0.5 maps to red), but the code is still in
the doctor's suggested list.

### Why this is a quality issue

A code with confidence 0.05 is the model saying "I can barely
justify this." Including it as a suggestion creates noise:
- Doctor has to dismiss it manually
- Risk of accepting it accidentally (if the UI's confidence
  rendering isn't instantly attention-grabbing)
- Audit/billing exposure if a low-confidence code is signed

### Recommended fix

Filter the schema's accepted output to confidence ≥ a
threshold. Two options:

**Option A** — schema-level filter (preserves all confidences):
```typescript
confidence: z.number().min(0.3).max(1)  // floor at 0.3
```
Any code with confidence <0.3 fails schema → retry.

**Option B** — post-filter in L7a:
```typescript
const MIN_CONFIDENCE_FOR_SUGGEST = 0.4;
const lowConfidenceDropped = result.codes.filter(c => c.confidence < MIN_CONFIDENCE_FOR_SUGGEST);
const suggestable = result.codes.filter(c => c.confidence >= MIN_CONFIDENCE_FOR_SUGGEST);

if (lowConfidenceDropped.length > 0) {
  void logAudit({
    action: 'CODING_LOW_CONFIDENCE_DROPPED',
    ...
  });
}
```

**Recommend Option B** — keeps the prompt's confidence ladder
intact (the model still emits low-confidence speculative codes
when it sees them) but filters the doctor-facing output.

### Estimated PR scope
**Small** — L7a + L7b post-filter; new audit action enum value.

---

## 06.7 — L7c RxAction enum doesn't include all common Rx scenarios

**Severity:** Q3
**Layer affected:** L7c
**Quality dimension:** completeness

### What's happening today

`07c-rx-drafting.ts:16-23`:

```typescript
export const RxAction = z.enum([
  'new', 'continue', 'increase', 'decrease', 'discontinue', 'unclear',
]);
```

No values for:
- `'switch'` — replacing one drug with another
- `'hold'` — temporarily pausing without discontinuing (peri-op,
  during illness)
- `'restart'` — resuming a previously held drug

### Why this is a quality issue

The model has to map "switch from atenolol to metoprolol" into
two actions: `discontinue` atenolol + `new` metoprolol. That's
correct but loses the "switch" semantic. The doctor's review
view treats them as separate decisions when they're one.

### Recommended fix

Add the actions and update the prompt:

```typescript
export const RxAction = z.enum([
  'new', 'continue', 'switch', 'increase', 'decrease',
  'hold', 'restart', 'discontinue', 'unclear',
]);
```

Schema for `switch`: include a `replaced_drug` field
identifying what's being switched out. Schema for `hold`:
include a `hold_until` field if specified ("hold until Tuesday
surgery"). Schema for `restart`: ground in entities so the
prior drug is identifiable.

### Estimated PR scope
**Small** — schema + prompt update; UI changes can wait.

---

## 06.8 — `entities.ros[].finding` is a string but should distinguish negative from positive

This is the same as Finding 02.9 (negation handling) — listed
here for cross-reference.

---

## 06.9 — JSON-mode is not enforced via Anthropic SDK; fence-stripping is the workaround

**Severity:** Q3
**Layer affected:** packages/ai/anthropic.ts
**Quality dimension:** robustness

### What's happening today

`anthropic.ts:86-89`:

```typescript
const unfenced = text
  .replace(/^```(?:json)?\s*/i, '')
  .replace(/```$/, '')
  .trim();
```

Claude sometimes wraps JSON in markdown fences despite the
prompt saying "no fences." The fence-stripping is a defensive
workaround.

The Anthropic SDK now supports a structured `tool_use`
contract that's more reliable than free-text JSON: the model
must emit a tool call with parameters matching a JSON schema.
Combined with `tool_choice` forcing, this eliminates the
fence-and-prose-around-JSON failure mode.

### Why this is a quality issue

The retry-on-schema-fail loop handles the worst cases. But
~5% per-call schema-fail rate (per the model-client comment)
costs latency + tokens. Tool-use mode would drop this to
near-zero.

### Recommended fix

Migrate JSON-output layers (L2, L3, L5, L7a-e) from
free-text JSON to tool-use mode:

```typescript
const response = await client.messages.create({
  model: args.model,
  max_tokens: args.maxTokens ?? 4096,
  system: args.system,
  messages: [{ role: 'user', content: userContent }],
  tools: [{
    name: 'submit_result',
    description: 'Submit the structured result',
    input_schema: zodToJsonSchema(args.schema),
  }],
  tool_choice: { type: 'tool', name: 'submit_result' },
});
```

Then read the result from `response.content[0].input` (the
`tool_use` block's `input` field).

### Estimated PR scope
**Medium** — affects every JSON-output layer + the model-client. But the change is centralized in `anthropicComplete` — the layers don't touch it. Single PR.

This is the highest-impact reliability improvement after the
dose-validator wiring (Finding 06.1).
