# AI Pipeline Fix-Pack 2 — Status (2026-05-10)

> Resolution of the 16 open Q1 findings and the Quick-win Q2 bundle
> from `docs/ai-pipeline-audit-phase-1-2026-05-05/findings/10-recommendations.md`.

## Triage outcome

The fix-pack 2 audit was scoped to "land trivially fixable items
as one or more PRs; defer items needing design judgement." Triage
of the 15 Q1 findings + 8 Q2 quick-wins revealed:

- **5 Q2 quick-wins were ALREADY DONE** in production code by the
  time this fix-pack was scoped (commits between Phase 1 audit
  date 2026-05-05 and triage date 2026-05-10).
- **2 items shipped in this fix-pack** as one PR.
- **8 Q1 findings DEFERRED** — require design / clinical /
  architecture judgement and should land as their own focused PRs.
- **5 items remain open** but were not in this fix-pack's scope
  (Q0 #5 deferred per §26.6; Q1 #11/12/13 need product UX
  discussion; Q1 #14 needs schema design).

## What shipped in this fix-pack

| Item | Where | Scope |
|---|---|---|
| **Q1 #9** — Restore OB-GYN to specialty catalog | `packages/shared/src/specialties.ts` | Add `{ id: 'ob-gyn', label: 'OB-GYN', templateId: 'ob-gyn' }`. Remap legacy `'OB-Gyn'` / `'Obstetrics & Gynecology'` strings from `'unspecified'` → `'ob-gyn'`. The `SPECIALTY_GUIDANCE` entries already exist (lines 64 + 70) — this PR is purely catalog-side. |
| **Q1 #18** — L2 speaker-classification prompt-injection wrap | `apps/transcribe-md/src/worker/layers/02-speaker-roles.ts` | Pattern-copy `wrapAsData` + `delimiterSystemSuffix` + `PIPELINE_REJECTED_INJECTION_DELIMITER` audit-on-detection from L3. Closes the delimiter-injection risk on the speaker-content user prompt. |

Single PR; both changes mechanical and additive. Code Quality
Auditor pass: BLOCK 0 / WARN 0 / NIT 0 (TOKEN-* N/A — no styling;
COMP-* N/A — server-only worker code; SCHEMA-001 N/A — adds
`logAudit` call alongside an existing prompt path that was
read-only at the model boundary; LAYOUT-* / SCOPE-* N/A; A11Y-*
N/A — no UI).

## Already-done items (verified in source — not re-shipped)

| Item | Status check | Where |
|---|---|---|
| Q2 §08.1 (= Q1 #17) — L2 temperature 0.1 | Already at `temperature: 0` (stricter than recommendation) | `apps/transcribe-md/src/worker/layers/02-speaker-roles.ts:153` |
| Q2 §08.2 — L5 temperature 0.2 → 0.1 | Already at `0.1` | `apps/transcribe-md/src/worker/layers/05-self-critique.ts:174` |
| Q2 §08.3 / §01.11 — L7d temperature 0.3 → 0.1 | Already at `0.1` (L7d referrals); L7e patient-summary at `0.3` is a separate item not in fix-pack scope | `apps/transcribe-md/src/worker/layers/07d-referrals.ts:89` |
| Q2 §01.9 — L1b passes `MEDICATION_KEYTERMS` | Already passing `CLINICAL_KEYTERMS` (intentional broader set) | `apps/transcribe-md/src/worker/layers/01b-transcribe-dictation.ts:88` |
| Q2 §06.7 — RxAction enum gains `switch`/`hold`/`restart` | Already added; comment at line 34 explicitly says "Q2 fix-pack §06.7" | `apps/transcribe-md/src/worker/layers/07c-rx-drafting.ts:40-51` |

## Deferred (each needs its own focused PR)

### Need clinical judgement

| Item | Why deferred |
|---|---|
| **Q1 #6** — L4 SOAP gen zero-shot → few-shot | Picking the 2 anchor examples requires clinical input on what "good SOAP" looks like for primary-care vs psychiatry vs urgent-care. Worth doing alongside an eval suite. |
| **Q1 #7** — L5 critique 3 → ~30 red-flag scenarios | Building the chief-complaint → red-flag-questions table is clinical curation. Needs input from a doctor reviewer. |
| **Q1 #10** — ICD-10 + CPT allowlists family-medicine biased | Hand-curating ~150 codes for cardiology / psychiatry / pediatrics needs clinical judgement. |

### Need product UX decision

| Item | Why deferred |
|---|---|
| **Q1 #11** — Single-speaker audio mode mismatch | What does the doctor see when L2 detects 1 speaker on a `audio_conversation` upload? Modal? Auto-reprocess? UX decision. |
| **Q1 #12** — 3+ speakers attribution weak | Display rules + prompt change. UX decision (do we show "[caregiver]" attribution in the SOAP?). |
| **Q1 #13** — Code-switching (bilingual) language detection | Deepgram `language: 'multi'` enabled; what then? Display flag? Doctor-confirmation modal? UX decision. |
| **Q1 #20** — Anthropic SDK refusal events not detected | Detecting `stop_reason === 'refusal'` is mechanical; the actionable banner shape is UX decision. |

### Need architecture decision

| Item | Why deferred |
|---|---|
| **Q1 #8** — L3 entity prompt specialty-blind | Specialty extensions to the entity schema cross-cut multiple layers. Schema design needs to align with #14 (conflict / negation). |
| **Q1 #14** — Conflict / negation handling in L3 (superseded + polarity) | Schema additions ripple into L4/L5/L6 readers. Plan as a single layer-3-and-downstream PR. |
| **Q1 #15** — L3 + L7c don't see patient context | Threading patient relation through worker requires deciding what "patient context" includes (DOB, weight, allergies, last visit). Architecture decision. |
| **Q1 #16** — L6 polish doesn't see entities + transcript | Adding entities + transcript to L6 input changes the prompt-cache hit characteristics (more tokens = different cache key). Architecture decision around cache strategy. |
| **Q1 #19** — L4 + L6 free-form output structural validator | The validator's "what counts as valid SOAP structure" is a contract decision (do we require both Subjective + Objective + Assessment + Plan headings? What about partial visits?). |
| **Q2 §06.6** — L7a/L7b confidence < 0.4 → drop with audit | The drop policy is operationally significant — a doctor reviewing dropped codes needs a UI surface. Architecture + UX. |
| **Q2 §06.3** — L3 schema `.min(1)` on every business-critical string | Adding `.min(1)` retro-actively will break in-flight visits with empty strings. Migration shape needs design. |
| **Q2 §06.4** — L5 schema `.min(1)` on description + suggested_fix | Same shape as Q2 §06.3. |

## Out of scope for this fix-pack

| Item | Reason |
|---|---|
| Q0 #5 — Psychiatry structured PHQ-9/GAD-7/MSE/safety extraction | Deferred per audit §26.6 to Phase 2 (after eval suite). |

## Post-fix-pack-2 recommended sequence

1. **Phase 2 eval suite** (per §26.8 recommendation) — unblocks
   most Q1 items by making refactors safe.
2. **Schema design pass** for items #8 / #14 / Q2 §06.3 / Q2 §06.4
   — single PR landing the schema additions across L3 / L5
   together to avoid back-and-forth.
3. **L4 + L5 prompt expansion** (#6, #7) — clinical-input-gated;
   pair with eval suite.
4. **UX decisions track** (#11, #12, #13, #20) — needs Kasra +
   pilot doctor feedback.
5. **Architecture track** (#15, #16, Q2 §06.6) — frame as
   "patient-context plumbing" PR + "cache-key strategy" PR.

## Audit trail

- Source: `docs/ai-pipeline-audit-phase-1-2026-05-05/findings/10-recommendations.md`
- Pre-existing fix history: `docs/POST_MERGE_TODO.md §26`
  (Fix-Pack 1 — SA1-SA4) shipped via PRs #125-#128.
- This fix-pack: 1 PR (open as of 2026-05-10).
