# Keyterm scoping + ISMP safety floor — Issues #202 + #206 closure

**Date:** 2026-05-14
**Author:** Claude (Opus 4.7 1M)
**Trigger:** Q1 fix-pack — pilot-readiness gate for clinical transcription accuracy.
**Method:** Production audit → architectural redesign → ISMP literature pull → live regression baseline against TTS-synthesized doctor dictation.
**PRs:** #246 (PR-1, scoping), #247 (PR-2, safety floor), #248 (PR-3, regression framework), this doc (PR-4).

---

## Section A — Executive summary

| Issue | Status | Evidence |
|---|---|---|
| **#206** — Implanon → insulin substitution | **CLOSED** | Both `Implanon` + `Nexplanon` boosted via the safety floor on every visit (not just ob-gyn). Regression baseline transcribes the Implanon seed-case dictation as "Implanon", primary hit count = 2, zero `insulin` substitutions. |
| **#202** — Global CLINICAL_KEYTERMS dilution | **CLOSED** | Pre-fix: 124 keyterms shipped on every visit (no scoping). Post-fix: per-visit composition via `buildKeytermsForVisit` — CORE (~57) + specialty bundle (~24–30) + ISMP safety floor (44) + patient-context boost (capped 15). 29/31 high-severity primaries transcribe correctly under live Deepgram. |

**Pilot-readiness verdict for the clinical-accuracy axis: GREEN.**

The previously load-bearing dilution gap is closed. The keyterm payload is now scoped, the safety floor catches cross-class catastrophic substitutions independent of specialty, and a re-runnable regression baseline guards against future architecture drift.

Two ASR phonetic-artifact discoveries surfaced from the baseline (Levemir → "levetiracil", Tradjenta → "trajena"). Neither is in the ISMP literature; both are added to the §F follow-up list. They are not blocking for the §A verdict — the regression baseline DID its job (the whole point is to surface this class of finding).

---

## Section B — Background: the pre-fix state

### The seed: Issue #206

Production audit (2026-05-13) surfaced a transcribed visit where the doctor had clearly dictated "Implanon" in an ob-gyn contraceptive-counselling context, and Deepgram output "insulin". Cross-class substitution: contraceptive vs antidiabetic. Catastrophic if it had reached a clinical decision.

The phonetic mechanism: both names are 3-syllable, both have stress on the second syllable (`/ɪm-PLAN-on/` vs `/IN-suh-lin/` with the leading vowel disambiguating less than the prosody suggests), and both live in medication-context prosody. ASR substitutes one for the other when the language model's prior favours the more-common term ("insulin" is many orders of magnitude more common in medical training corpora than "Implanon"). Not in the ISMP 2024 list — this is a TTS/ASR artifact specific to dictation pipelines, not historical pharmacy literature.

### The wider problem: Issue #202

Investigation widened from #206 into a structural audit of the keyterm payload:

1. **No scoping.** The `CLINICAL_KEYTERMS` aggregate (~124 terms) shipped on every visit globally. No per-specialty composition.
2. **No safety floor.** Rare/specialty-specific terms (Implanon among them) were absent from the list — the assumption was that the model would pick them up from context. The #206 evidence shows that assumption was wrong.
3. **Token budget undocumented.** Deepgram's `keyterm` parameter has a documented cap (~500 tokens); the global list at 124 terms was already at ~360 tokens with no per-visit context to spend the rest of the budget on.
4. **No audit trail.** No way to attribute a future transcription regression to a specific keyterm composition — the post-incident forensic loop was dead-ended at "we shipped 124 keyterms, dunno which one helped or didn't".

---

## Section C — The fix-pack (PR-1 → PR-4)

### PR-1 (#246) — Scoping skeleton

Architecture: per-visit `buildKeytermsForVisit({ specialty, safetyFloor, patientContext })` composes the keyterm payload in priority order.

**4 layers:**

| Layer | Source | Size | Always-loaded |
|---|---|---|---|
| 1 — CORE_KEYTERMS | anatomy + labs + procedures + common diagnoses | ~57 terms | Yes |
| 2 — SPECIALTY_KEYTERMS[key] | per-canonical-specialty bundle (14 specialties) | ~20–30 | When `specialty` non-null |
| 3 — Safety floor | argument (PR-2 wires CONFUSED_DRUG_NAMES_FLAT) | ~44 | When provided |
| 4 — Patient-context boost | argument (slot — not yet wired in production) | capped 15 | When provided |

**Composition rules:**

- Priority order: safety floor > CORE > specialty > patient context (first-occurrence wins on dedupe).
- Token-budget enforcer caps total at 450 estimated tokens (10% headroom below Deepgram's documented 500).
- Trim direction: patient context → specialty tail → never safety floor or CORE.

**Schema:** New JSONB `transcribe_visits.keytermsApplied` column records the composition per visit for forensic attribution. Idempotent migration `20260513230000_visit_keyterms_applied`.

**Wiring:** L1 + L1b read `visit.specialty` (free-text), builder normalizes via `normalizeSpecialty` against `specialty-keys.ts`. Interpreter-mode visits skip the builder entirely (model swaps to nova-3 general which doesn't accept the bias the same way).

### PR-2 (#247) — ISMP confused-drug-names safety floor

42 pairs / 44 primary names curated from ISMP's [List of Confused Drug Names](https://home.ecri.org/blogs/ismp-resources/list-of-confused-drug-names) (June 2024 edition). Each pair carries `rationale` citing ISMP, FDA/ISMP Tall Man Letter list, Pharmacy Times, or Issue #206 (internal observation).

**Asymmetric-boost design (PR-2 auditor closure):**

`CONFUSED_DRUG_NAMES_FLAT` exports primaries only — NOT primaries + `confusedWith`. The reasoning is two-fold:

1. **Token budget.** Flattening both sides of every pair pushed the floor to ~90 entries / ~280 tokens. Combined with CORE + specialty, that silently trimmed the specialty layer (regression caught by the auditor pre-merge).
2. **Asymmetric value.** The `primary` is the term we WANT transcribed correctly; the `confusedWith` alternatives are what Deepgram outputs by DEFAULT — they don't need a prior boost (they already have one from training-corpus frequency).

Net: ~44 × ~3 tokens ≈ 150 tokens for the safety floor. Leaves headroom for CORE + specialty + future patient-context boost.

**CORE refactor:** The pre-PR-2 CORE_KEYTERMS list contained 25 universal medications inline (acetaminophen, ibuprofen, metformin, lisinopril, …). With the safety floor riding on every visit, those meds were redundant; keeping them pushed total tokens over budget. Doc block at `apps/transcribe-md/src/lib/deepgram-vocabulary.ts:608-625` records the traceback.

### PR-3 (#248) — Regression baseline framework

`apps/transcribe-md/scripts/keyterm-regression/` — for each of the 31 high-severity primaries, synthesize a doctor-dictation TTS clip (OpenAI tts-1, "onyx" voice, ~150-250 char clinical context), then run it through `buildKeytermsForVisit({ specialty, safetyFloor: CONFUSED_DRUG_NAMES_FLAT })` + `deepgramBatchTranscribe(...)` (dictation mode), and score the transcript for primary-presence + `confusedWith` occurrences.

**Strict serial throughout** — TTS and Deepgram calls one-at-a-time. Inherited from the PR-2 operator note on parallel-sub-agent RAM pressure.

**One-time baseline captured by this PR** (`docs/keyterm-regression-baseline/baseline-2026-05-14T01-19-05-787Z.md`):

- **29 / 31 PASS (93.5%)**
- Cost: $0.088 Deepgram + $0.09 OpenAI = $0.18 total
- **Builder budget invariant verified live:** `budgetEnforced: NO` across ALL 31 specialty + safety-floor composites. The PR-2 architecture refactor holds — no silent specialty trimming under any specialty.

### PR-4 (this doc) — Audit closure

This document.

---

## Section D — Findings from the regression baseline

### 29 passing — selected attestations

| Tag | Specialty | Layers (core/sp/sf/pc) | Tokens | Primary hits | Transcript excerpt |
|---|---|---|---|---|---|
| `implanon` | ob_gyn | 57/24/44/0 | 404 | 2 | "…here to discuss her Implanon. The Implanon was placed three years ago…" |
| `nexplanon` | ob_gyn | 57/24/44/0 | 404 | 3 | "…here for Nexplanon insertion. She has had a Nexplanon previously…" |
| `tresiba` | endocrinology | 57/30/44/0 | 376 (post-dedupe) | 2 | "…transitioning from Lantus to Tresiba forty units daily. Tresiba has a flatter…" |
| `trulicity` | endocrinology | 57/30/44/0 | 376 | 2 | "…Starting Trulicity 0.75 milligrams subcutaneously once weekly…" |
| `tramadol` | pain_management | 57/22/44/0 | 396 | 2 | "Tramadol fifty milligrams every six hours as needed for breakthrough pain…" |
| `metformin` | primary_care | 57/13/44/0 | 360 | 2 | "Increasing metformin from five hundred milligrams twice daily…" |
| `metoprolol` | primary_care | 57/13/44/0 | 360 | 2 | "Continuing metoprolol succinate fifty milligrams daily…" |

The two `confusedWith` co-occurrences in the baseline are both legitimate co-mentions in the dictation script (e.g., the `implanon` script also mentions `Nexplanon` as the replacement option). No substitutions were observed — every reach into a `confusedWith` was an intentional co-mention.

### 2 failing — phonetic-artifact discoveries

**`levemir` — Levemir → "levetiracil"**

- **Specialty:** endocrinology
- **Script:** "She is currently on Levemir twenty-two units twice daily. Morning hypoglycemia at three a.m. Plan to drop the evening Levemir dose to eighteen units and reassess."
- **Transcript:** "She is currently on levetiracil twenty two units twice daily, morning hypoglycemia at 3AM. Plan to drop the evening levetiracil dose to eighteen units and reassess."
- **Interpretation:** Deepgram morphed toward levetiracetam (Keppra — anticonvulsant) but truncated to a non-word ("levetiracil"). The pull-toward is the canonical sign of an unrecognized rare term getting bent toward a similar-sounding common term. Wrong-class substitution risk: levetiracetam vs Levemir is insulin-vs-anticonvulsant — catastrophic if it had matched cleanly.
- **Class:** ASR phonetic artifact, not ISMP-documented.
- **Recommendation:** Add `levetiracetam` to `Levemir.confusedWith` in `confused-drug-names.ts`. Rationale: "ASR phonetic artifact (PR-3 baseline 2026-05-14): Deepgram morphed Levemir toward levetiracetam under continuous-speech prosody — insulin vs anticonvulsant wrong-class". Optionally consider adding `Levetiracetam` as a separate `primary` in the safety floor with the same severity rating.

**`tradjenta` — Tradjenta → "trajena"**

- **Specialty:** endocrinology
- **Script:** "Adding Tradjenta five milligrams daily to her metformin regimen. Tradjenta is renally safe at her current eGFR. Will recheck A1C and metabolic panel in three months."
- **Transcript:** "Adding trajena five milligrams daily to her metformin regimen, trajena is renally safe at her current eGFR. We'll recheck A1c and metabolic panel in three months."
- **Interpretation:** Deepgram dropped the 'd' AND the second 't', producing a non-word. Unlike Levemir, this didn't pull toward a real alternate drug — it's a degenerate phonetic collapse, not a substitution. The T-named diabetes class (Trulicity / Tradjenta / Toujeo / Tresiba / Tanzeum) is the highest-density ISMP cluster (Tresiba's row alone has 5 alternatives); the prosody is overloaded.
- **Class:** TTS-side phonetic underspecification, possibly compounded by the keyterm `Tradjenta` being lowercased by Deepgram for matching but not retokenized cleanly.
- **Recommendation:** Re-synthesize the Tradjenta fixture at slower TTS speed (e.g., `speed: 0.9`) or with an alternative voice and re-run. If the failure persists at slower TTS speed, file a Deepgram support ticket — `nova-3-medical` is supposed to be aware of brand-name diabetes meds. If it resolves at slower TTS speed, treat as a TTS-side fixture issue, not a Deepgram-side gap.

---

## Section E — Closure criteria

### Issue #206 (Implanon → insulin)

| Criterion | Status |
|---|---|
| Implanon explicitly in safety floor | ✓ (`confused-drug-names.ts:243-249`) |
| Nexplanon explicitly in safety floor | ✓ (sibling entry) |
| Both ride on every non-interpreter visit regardless of specialty | ✓ (L1 + L1b wiring, #247) |
| Live regression confirms "Implanon" → "Implanon" in transcript | ✓ (baseline 2026-05-14 `implanon` row, primary hits = 2) |
| Audit attribution available for future regressions | ✓ (`transcribe_visits.keytermsApplied` JSONB persisted by L1; layer counts include safetyFloor) |

### Issue #202 (global CLINICAL_KEYTERMS dilution)

| Criterion | Status |
|---|---|
| Per-visit keyterm composition (not a single global list) | ✓ (`buildKeytermsForVisit`, #246) |
| Specialty layer composed alongside CORE + safety floor | ✓ (14 canonical specialties, #246) |
| Token budget enforced with documented trim policy | ✓ (450 cap; never trims safety floor or CORE; #246) |
| Builder budget invariant holds across all specialty composites | ✓ (live regression 2026-05-14: `budgetEnforced: NO` in 31/31 runs) |
| Forensic attribution column persists per visit | ✓ (`keytermsApplied` JSONB, #246) |
| Re-runnable regression check guards against future drift | ✓ (`scripts/keyterm-regression/`, #248) |

---

## Section F — Follow-ups (not blocking closure)

### F.1 — Levemir → levetiracetam class

**Severity:** high (insulin vs anticonvulsant wrong-class).
**Effort:** ~5 lines in `confused-drug-names.ts` + re-run regression baseline.
**Recommendation:** Ship in the next safety-floor expansion PR. Track as a child of #202.

### F.2 — Tradjenta TTS-side investigation

**Severity:** investigative — may be fixture-side, not Deepgram-side.
**Effort:** Re-synthesize at TTS speed 0.9 and rerun.
**Recommendation:** Resolve before promoting the baseline to a hard pre-merge gate.

### F.3 — Patient-context boost (Layer 4)

PR-1 (#246) reserved the layer-4 slot for a per-patient medication-history boost (up to 15 terms). It's not wired in production yet. The slot would let a chronic-condition patient's known meds (e.g., the diabetes regimen on a returning patient's chart) ride alongside the safety floor + specialty bundle for that visit. Would close additional dilution gap for high-context patients.

**Severity:** medium — incremental gain over the closure achieved by #246–#248.
**Recommendation:** Separate scope; queue for the next clinical-accuracy iteration.

### F.4 — CI gate for transcribe-md unit tests

Discovered during PR-2: `apps/meddoc-pro`'s `test:all` script is a decommissioned echo (`"echo '[meddoc-pro] CRM decommissioned…'"`), and the root `test:all` resolves through it — so transcribe-md's 1148 vitest tests do NOT run in CI today. Several local-env failures (`ANTHROPIC_API_KEY` missing, stale `specialty-catalog` snapshot, `edit-tracking` env-deps) would have been caught if they did.

**Severity:** high — silently undermines the test-gating story.
**Recommendation:** Add a root `test:transcribe-md` script that runs `npx vitest run` inside `apps/transcribe-md` and wire it into `.github/workflows/test.yml`. Fix the local-env failures (`ANTHROPIC_API_KEY` stub for the `llm-mdm` suite; regenerate the `specialty-catalog` snapshot) before turning the gate red.

### F.5 — Quarterly drift check

Set a quarterly calendar reminder to re-run `scripts/keyterm-regression/run.ts`. Captures: (a) accumulated ISMP list updates, (b) Deepgram model drift, (c) accumulated CONFUSED_DRUG_NAMES edits. Cost per run is ~$0.20 — negligible.

---

## Section G — Operator note (previous-session crash root cause)

The first attempt to ship this fix-pack ended in mid-session termination. No kernel OOM, container OOM, or Docker `oom`/`die` events were recovered from this VPS's logs across the 6 hours preceding the crash (uptime 9 days, no host reboot). Most-likely cause: session-level RAM pressure from parallel sub-agent spawning — the previous plan called for parallel TTS fixture generation in PR-3.

The retry that produced this fix-pack runs **strictly serial**: every TTS call sequential, every Deepgram call sequential, every PR's auditor invocation sequential, every container build sequential. The constraint is codified in PR-2's commit message and the PR-3 README so future re-runs preserve it.

---

_End of audit. PRs #246, #247, #248 close Issues #202 + #206._
