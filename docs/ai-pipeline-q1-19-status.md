# Q1 #19 Status — L4 + L6 + L7a/b/c structural validators

**Source:** Phase 1 audit recommendation #19 (deferred during Fix-Pack 2,
2026-05-10).
**Triage date:** 2026-05-10.

## What the recommendation said

> L4 + L6 free-form output has no structural validator. Add
> `validateSoapStructure` — checks for required headings, non-empty,
> no preamble. Single retry on structural failure.

## What the 2026-05-10 baseline shadow audit revealed

`tm_cpt_coding`, `tm_entities`, `tm_rx_drafting`, `tm_icd_coding` had
22-49% schema/JSON-parse failure rates in production. **Triaging the
actual failure messages (not just retry-counter rollups) revealed the
root causes are different from what #19 originally hypothesized:**

| Layer | Pre-fix-pack failure rate | Pulled from `errorDetails` |
|---|---|---|
| `tm_cpt_coding` (L7b) | 50/103 | Model writes prose into the `em.reasoning.risk` enum field (e.g. *"Low — prescription NSAID initiated; however..."* instead of just `"low"`). |
| `tm_entities` (L3) | 15/68 | Model returns bare string for `social_history.<field>` instead of the `{value, evidence_quote}` object shape — even with the T-M23.B prompt guidance. |
| `tm_rx_drafting` (L7c) | 16/69 | Model returns `null` for `warnings[].rx_drug` when the warning is general (no specific drug attribution). Schema required `.min(1)`. |
| `tm_icd_coding` (L7a) | 18/69 | `JSON_PARSE_FAIL` — model emits multi-block responses (one ```json block, then prose self-correction, then another ```json block). The parser stops at the first block. |

`#19`'s "L4 + L6 free-form output validator" framing was a
hypothesis. The actual failures are concentrated in **schema strictness
vs. model output drift** at L3 / L7a / L7b / L7c — different layers,
different remediation.

## What ships in this PR

Schema-side fixes for the three SCHEMA_FAIL clusters that surfaced.
None of these are prompt changes; the prompts already guide the model
toward the desired shape, and the schemas are now monotone-permissive
where the model's edge-case outputs make clinical sense.

| Fix | File | Approach |
|---|---|---|
| **`em.reasoning.risk`** prose extraction | `apps/transcribe-md/src/worker/layers/07b-cpt-coding.ts` | `z.preprocess` extracts the first `\b(minimal\|low\|moderate\|high)\b` token in the string before strict-enum validation. |
| **`warnings[].rx_drug`** null coercion | `apps/transcribe-md/src/worker/layers/07c-rx-drafting.ts` | `z.preprocess` maps `null` → `"General"` (the documented general-warning bucket) before `.min(1)` validation. Wire shape stays `string` so downstream consumers (pdf-generator, docx-generator, ehr-formatters, rx-tab) don't need null-handling. |
| **`social_history.<field>`** string-to-object lift | `apps/transcribe-md/src/worker/layers/03-extract-entities.ts` | New `liftStringToFact<K>()` helper wraps `factWithEvidence(K)` with a preprocess: a bare string is lifted to `{[key]: value, evidence_quote: value}`. Lossy but monotone — the field stays in the SOAP draft instead of failing the whole call. |

Expected post-fix failure rate (back-of-envelope, rerun shadow audit
to confirm):

- `tm_cpt_coding` SCHEMA_FAIL: ~47 → ~0 (prose-in-enum is the only pattern observed)
- `tm_rx_drafting` SCHEMA_FAIL: ~15 → ~0 (null is the only `rx_drug` pattern observed)
- `tm_entities` SCHEMA_FAIL: ~15 → expected drop, but other shape mismatches may still exist; rerun for fresh triage

## What does NOT ship — deferred to Q1 #19.B

### `tm_icd_coding` JSON_PARSE_FAIL multi-block output (18/69)

Root cause is different — the model emits **multiple** ```json blocks
in one response (often a first attempt, prose self-correction "I need
to correct myself…", then a corrected attempt). The current parser
takes the first block; the second is dropped.

Fix shape: change the JSON-extraction in `packages/ai/src/anthropic.ts`
(or wherever the model client unwraps fenced blocks) to take the **last**
```json block — the model's self-corrected attempt — instead of the
first. This is a model-client-level change, larger blast radius.

Defer rationale: warrants a focused PR with a prompt-cache hit-rate
delta check (multi-block output may correlate with cache misses;
forcing single-block output via prompt may reduce both failure rate
AND per-call cost).

### Q1 #19 original framing — "validateSoapStructure for L4 / L6"

The L4 + L6 free-form output's structural validator hasn't been
needed by the production failure data: the 0% ERROR rate on `tm_polish`
and the 6/60 generic ERROR on `tm_soap_draft` (which tracks back to
network/HTTP errors per the retry classifier, not structural issues)
suggest L4/L6 output is shaped reasonably without an explicit
validator.

Defer rationale: build the validator if a future shadow-audit run shows
real L4/L6 structure breakage. Until then, no signal demands the work.

### Q2 §06.6 — L7a/L7b confidence < 0.4 drop with audit

The recommendation calls for low-confidence ICD/CPT codes to be dropped
with an audit row. The current `confidence` field exists on the schema
(per fix-pack 1 PR #128) but the drop policy isn't wired. Operationally
significant — the doctor's review-pane needs to surface dropped codes.

Defer rationale: needs UX design (where does the dropped-code surface
go?). UX-track follow-up.

## Test plan

- [ ] Re-run `tm_cpt_coding` against the 50 prior failure inputs (replay
      from `errorDetails`); verify SCHEMA_FAIL drops to ~0.
- [ ] Re-run `tm_rx_drafting` against the 15 prior failures; same.
- [ ] Re-run `tm_entities` against the 15 prior failures; expect
      partial drop (the explicit string-shortcut pattern is fixed; other
      shapes may still trigger).
- [ ] Confirm wire-shape of `RxWarning.rx_drug` post-coerce: downstream
      consumers (`pdf-generator.ts:415`, `docx-generator.ts:206`,
      `ehr-formatters.ts:122`, `rx-tab.tsx:143`) all read `w.rx_drug`
      as a string; coercion to "General" preserves that contract.
- [ ] Confirm `em.reasoning.risk` enum value is correct after extract
      (e.g. `"Low — ..."` → `"low"`).

## Followup refs

- 2026-05-10 baseline shadow audit:
  `docs/agent-shadow-runs/ai-pipeline/20260510T200534Z.md`.
- Fix-pack 2 deferred-items grid:
  `docs/ai-pipeline-fix-pack-2-status.md`.
- Phase 1 audit recommendations:
  `docs/ai-pipeline-audit-phase-1-2026-05-05/findings/10-recommendations.md`.
