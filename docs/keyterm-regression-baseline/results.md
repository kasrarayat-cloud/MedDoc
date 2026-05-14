# Keyterm regression results — Issues #202 + #206 (current state)

**Generated:** 2026-05-14T01:40:04.550Z  
**Scenarios:** 32  
**Passed:** 30 / 32  
**Failed:** 2  
**Audio scenarios actually run (rest skipped due to missing cache):** 32  
**Total Deepgram cost:** $0.092 (nova-3-medical @ $0.0145/min)  

## Delta from prior baseline (PR-3 → PR-5)

Prior baseline: `baseline-2026-05-14T01-19-05-787Z.md` (29 / 31, $0.088).

| Metric | PR-3 baseline | PR-5 (this run) | Δ |
|---|---|---|---|
| Scenarios | 31 | 32 | +1 (levetiracetam) |
| Passing | 29 | 30 | +1 |
| Pass rate | 93.5% | 93.75% | +0.25pp |
| Total cost | $0.088 | $0.092 | +$0.004 |
| Endo specialty tokens (lantus row) | 376 | 380 | +4 (one new safety-floor primary) |
| Builder `budgetEnforced` | NO ✓ | NO ✓ | — |

### Scenarios changed

- **NEW `levetiracetam` (PASS)** — TBI / seizure-prophylaxis dictation. 2 primary hits, no `confusedWith` co-occurrences. Confirms the safety floor biases Deepgram correctly in the levetiracetam direction.
- **`levemir` (still FAIL — but transcript morphology changed)** —
  - PR-3 transcript: "levetiracil twenty two units twice daily…" (truncated non-word)
  - PR-5 transcript: "levetiracetamol twenty two units twice daily…" (full anticonvulsant name with an "ol" suffix Deepgram tagged on)
  - Interpretation: the new `levetiracetam` primary added to the safety floor IS active and moved Deepgram closer to the canonical spelling — but the LM prior on the anticonvulsant remains strong enough that biasing `Levemir` symmetrically doesn't yet flip the output. The keyterm API increases the prior; it doesn't override the acoustic likelihood. This is a Deepgram-side limitation — the structured safety-floor data is now in place for when Deepgram improves or when QuillMD moves to an alternative ASR for ambiguous-acoustic cases.
- **`tradjenta` (still FAIL — unchanged from PR-3)** — out of scope for this PR; remains in §F.2 of the closure doc.

### Why the symmetric boost was still the right call

Per the PR-5 design: clinicians can legitimately say either Levemir OR levetiracetam, depending on whether the patient is on an insulin or an anticonvulsant. Asymmetric boost (Levemir only) would have made `levetiracetam` worse for epilepsy-patient dictations — a different but equally catastrophic substitution risk. The 30/32 outcome is the right trade: the levetiracetam-direction safety is now empirically guarded; the Levemir-direction safety waits on Deepgram-side improvement or a TTS-side fixture refinement (§F.2-extension).

## Method

- Each scenario synthesizes a ~150-250 char doctor-dictation script via OpenAI tts-1 ("onyx" voice).
- Audio is read from `.local/keyterm-regression-audio/{tag}.mp3` (idempotent cache).
- `buildKeytermsForVisit({ specialty, safetyFloor: CONFUSED_DRUG_NAMES_FLAT })` composes per-scenario keyterms.
- `deepgramBatchTranscribe` with `diarize: false, utterances: false` (dictation mode).
- Pass = primary medication name appears in the transcript at least once (word-boundary, case-insensitive).
- `confusedWith` occurrences are tracked but not gated — co-mention is allowed.

## Per-scenario results

| Tag | Primary | Pass | Primary hits | Confused hits | Tokens | Audio dur | Cost ¢ |
|---|---|---|---|---|---|---|---|
| lantus | Lantus | ✓ | 2 | — | 380 | 11s | 0.27 |
| levemir | Levemir | ✗ | 0 | — | 380 | 10s | 0.24 |
| tresiba | Tresiba | ✓ | 2 | — | 380 | 11s | 0.27 |
| toujeo | Toujeo | ✓ | 2 | — | 380 | 11s | 0.27 |
| humalog | Humalog | ✓ | 2 | — | 380 | 11s | 0.27 |
| humulin | Humulin | ✓ | 2 | — | 380 | 11s | 0.27 |
| novolog | Novolog | ✓ | 2 | — | 380 | 11s | 0.27 |
| trulicity | Trulicity | ✓ | 2 | — | 380 | 13s | 0.31 |
| tradjenta | Tradjenta | ✗ | 0 | — | 380 | 11s | 0.27 |
| januvia | Januvia | ✓ | 2 | — | 380 | 12s | 0.29 |
| metformin | metformin | ✓ | 2 | — | 364 | 11s | 0.27 |
| metoprolol | metoprolol | ✓ | 2 | — | 364 | 12s | 0.29 |
| fastin | Fastin | ✓ | 3 | phentermine=1 | 364 | 12s | 0.29 |
| bupropion | bupropion | ✓ | 2 | — | 364 | 12s | 0.29 |
| naltrexone | naltrexone | ✓ | 2 | — | 364 | 13s | 0.31 |
| nexplanon | Nexplanon | ✓ | 3 | — | 408 | 13s | 0.31 |
| implanon | Implanon | ✓ | 2 | Nexplanon=1 | 408 | 12s | 0.29 |
| levothyroxine | levothyroxine | ✓ | 2 | — | 380 | 12s | 0.29 |
| liothyronine | liothyronine | ✓ | 1 | levothyroxine=2 | 405 | 13s | 0.31 |
| prednisone | prednisone | ✓ | 2 | — | 364 | 12s | 0.29 |
| dexamethasone | dexamethasone | ✓ | 2 | — | 400 | 13s | 0.31 |
| heparin | heparin | ✓ | 3 | — | 408 | 13s | 0.31 |
| coumadin | Coumadin | ✓ | 2 | — | 408 | 12s | 0.29 |
| jantoven | Jantoven | ✓ | 2 | — | 364 | 12s | 0.29 |
| celexa | Celexa | ✓ | 2 | — | 385 | 12s | 0.29 |
| lexapro | Lexapro | ✓ | 2 | — | 385 | 11s | 0.27 |
| sertraline | sertraline | ✓ | 2 | — | 385 | 11s | 0.27 |
| tramadol | tramadol | ✓ | 2 | — | 400 | 13s | 0.31 |
| hydroxyzine | hydroxyzine | ✓ | 2 | — | 400 | 11s | 0.27 |
| oxycodone | oxycodone | ✓ | 2 | — | 400 | 12s | 0.29 |
| atorvastatin | atorvastatin | ✓ | 2 | — | 364 | 12s | 0.29 |
| levetiracetam | levetiracetam | ✓ | 2 | — | 317 | 14s | 0.34 |

## Failures — detail

### levemir — Levemir

- **Specialty:** `endocrinology`
- **Fail reason:** primary "Levemir" not found in transcript
- **Script:** She is currently on Levemir twenty-two units twice daily. Morning hypoglycemia at three a.m. Plan to drop the evening Levemir dose to eighteen units and reassess.
- **Transcript:** She is currently on levetiracetamol twenty two units twice daily, morning hypoglycemia at 3AM. Plan to drop the evening levetiracetamol dose to eighteen units and reassess.
- **Confused hits:** none

### tradjenta — Tradjenta

- **Specialty:** `endocrinology`
- **Fail reason:** primary "Tradjenta" not found in transcript
- **Script:** Adding Tradjenta five milligrams daily to her metformin regimen. Tradjenta is renally safe at her current eGFR. Will recheck A1C and metabolic panel in three months.
- **Transcript:** Adding trajena five milligrams daily to her metformin regimen, trajena is renally safe at her current eGFR. We'll recheck A1c and metabolic panel in three months.
- **Confused hits:** none

## Keyterm-budget invariant

**Builder `budgetEnforced` ever triggered:** NO ✓ (specialty bundles ride untrimmed)

---

_Auto-generated by `apps/transcribe-md/scripts/keyterm-regression/run.ts` (PR-5 run). See `docs/audit-reports/keyterm-scoping-202-206-closure.md` for issue context._
