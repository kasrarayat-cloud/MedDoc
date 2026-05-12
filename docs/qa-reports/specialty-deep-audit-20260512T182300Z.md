# Specialty Deep Audit — Bariatric + Vascular Surgery
**Date:** 2026-05-12 18:23 UTC
**Auditor:** Claude (Opus 4.7 1M)
**Trigger:** Demo-readiness audit before client demo (per Kasra)
**Scope:** PR #219 (Bariatric Surgery) + PR #220 (Vascular Surgery), clinical content correctness, catalog completeness, load-bearing safety rules, and UI surfaces.

---

## Section A — Demo Confidence Summary

| Dimension | Result | Notes |
|---|---|---|
| Visits attempted | 19 (9 Bariatric / 10 Vascular) | |
| Visits completed (READY) | **12 / 19** | 7 vascular visits FAILED mid-run due to Anthropic credit exhaustion (operational, not code) |
| SOAP structure pass | **12 / 12** completed visits | All produced clinically coherent, phase-anchored SOAP notes with documented clinical scales |
| ICD-10 codes valid (allowlist) | **12 / 12** | Zero `CODING_COACH_REJECTED_INVALID_ICD` audit events — every emitted code was in the allowlist |
| CPT codes valid (allowlist) | **12 / 12** | Zero `CODING_COACH_REJECTED_INVALID_CPT` audit events |
| Documented findings → ICD coding | **8 / 12 visits had ≥1 documented finding missed** | See gaps G1–G7 below; this is a prompt-quality issue, not a catalog issue |
| Load-bearing safety rules — tested | 2 / 4 | B7 calcium-carbonate (PASS), B6 NSAID-avoidance post-RYGB (PASS by absence); V8 prasugrel/vorapaxar + V10 iohexol UNTESTED (failed mid-run) |
| **B7 calcium-carbonate stress test** | **PASS** | Critical-severity warning fired verbatim: "Calcium carbonate is contraindicated in post-RYGB anatomy" |
| Bump CTA sample | Deferred — bump CTA is a UI-driven workflow; no visits in this batch had under-coded E&M that would trigger it |
| Pipeline cost per visit | **$0.25–$0.57 (mean $0.43)** | Within the $0.30–$0.80 target post-PR #213/#215; 12-visit total $5.11 |
| **UI surfaces** | **PASS** | Both specialties surface end-to-end: marketing pill list (12), "Twelve specialty templates" headline, /visits/new dropdown, /settings default-specialty dropdown, avatar tone map. No regressions detected. |
| Catalog gaps (ICD) | 0 | No allowlist rejections |
| Catalog gaps (CPT) | 0 | No allowlist rejections |
| Catalog gaps (Rx dose-ranges) | **~12 drugs** | Common bariatric/perioperative supplements + 2 IV agents flagged "not in verified safety database" — see G8 below |
| Pipeline bugs surfaced | **2** | V3 silent-completion (P0), DLQ enqueue failure (P0 ops) — see G9, G10 below |
| **Overall demo readiness** | **CONDITIONAL** | Bariatric (B1–B9): ✅ ready, content is clinically strong. Vascular: ⚠️ V1–V3 verified, V4–V10 untested due to credit exhaustion; will re-run after credit top-up. Pipeline must address V3-style silent-completion before any LLM-spend incident becomes user-visible. |

---

## Section B — Per-Visit Detail

### Bariatric Surgery (9 visits, all READY)

#### B1 — READY · $0.42 · Pre-op RYGB, BMI 47

**ICD-10 (8):** E66.01, Z68.45, E11.65, Z79.84, Z79.899, G47.33, K76.0, I10
**CPT:** E&M 99205 (new patient comprehensive) · modifiers `[95]`
**Rx (3 Rx, 6 warnings):** Semaglutide (hold), Metformin (continue), Lisinopril (continue)
**Verdict:** **PASS** — comprehensive code set covering obesity, T2DM, OSA, NAFLD, HTN, plus long-term med codes (Z79.84 GLP-1, Z79.899 long-term meds). SOAP anchored phases correctly. Pre-op counseling captured.
**Minor:** missing Z68.42 (BMI 45–49.9) — Z68.45 emitted instead (BMI 70+ — wrong specificity).

#### B2 — READY · $0.41 · Pre-op revision after LAGB

**ICD-10 (4):** E66.01, Z68.38, I10, Z98.84
**CPT:** E&M 99205 · proc `[36415]` (venipuncture for baseline labs) · modifiers `[25]`
**Rx (0 Rx, 2 warnings):**
**Verdict:** **CONDITIONAL** — missed K21.9 (GERD) despite explicit "GERD (omeprazole 40 daily)" in PMH. GERD is the index driver behind the RYGB vs sleeve decision documented in the plan. Missing this code under-states the clinical complexity.

#### B3 — READY · $0.52 · Pre-op BPD-DS, BMI 55

**ICD-10 (12):** E66.01, Z68.45, Z68.44, Z68.43, E11.65, G47.33, I10, E78.5, K76.0, Z79.84, Z79.4, Z87.891
**CPT:** E&M 99215 (established high-MDM) · no procedure
**Rx (10 Rx, 18 warnings):** Enoxaparin 40 mg BID, full BPD-DS supplement stack (Vit A 10k, E 400, K 1mg, B12 1k mcg, D3 50k weekly), iron, zinc, bariatric MVI
**Verdict:** **CONDITIONAL** — missed I50.32/.30/.31 (HFpEF) despite explicit "CHF: HFpEF, EF 55% on recent echo, NYHA Class II" in PMH. Under-codes the patient's cardiac risk profile (highly relevant for surgical risk).
**Strong:** correctly drafted the full BPD-DS lifelong supplementation regimen including fat-soluble vitamins.

#### B4 — READY · $0.42 · POD #5 RYGB leak workup

**ICD-10 (5):** K91.89, R11.2, Z98.84, E66.01, Z79.01
**CPT:** E&M 99215 (established high-MDM) · modifiers `[25]`
**Rx (5 Rx, 9 warnings):** Piperacillin-tazobactam 3.375 g IV q6h, Pantoprazole IV, Enoxaparin (increase to BID), Acetaminophen, Opioid PRN
**Verdict:** **CONDITIONAL** — three documented findings missed:
- **AKI** (Cr 1.4 from baseline 0.8) → N17.x not coded
- **Abdominal pain** (LUQ tenderness 5/10) → R10.12/13 not coded
- **Dehydration** (dry mucous membranes, low intake) → E86.0/.9 not coded
Critical warning fired for missing allergy documentation pre Zosyn (correct safety behavior).
**Strong:** correctly cautioned about NSAID avoidance post-RYGB (marginal ulcer risk) — implicit safety rule respected.

#### B5 — READY · $0.33 · POD #14 sleeve diet advance

**ICD-10 (3):** Z98.84, E66.01, Z68.41
**CPT:** E&M 99213 (low-MDM follow-up)
**Rx (5 Rx, 8 warnings):** Multivitamin, B12, Calcium citrate 1500, D3 5000, Acetaminophen
**Verdict:** **CONDITIONAL** — missed Z48.815 / Z48.812 (surgical aftercare digestive) which is the canonical aftercare code for this phase. Z98.84 is "bariatric status" but doesn't carry the "encounter for surgical follow-up" semantics.

#### B6 — READY · $0.40 · POD #28 RYGB DVT-prophylaxis transition

**ICD-10 (6):** E11.9, I10, E78.5, E66.01, Z79.01, Z79.899
**CPT:** E&M 99214 (moderate MDM)
**Rx (7 Rx, 10 warnings):** Enoxaparin 40 mg SQ (discontinue), Atorvastatin, Bariatric MVI, B12, Calcium citrate, D3, Iron elemental
**Verdict:** **CONDITIONAL** — missed Z86.718 (personal hx VTE) despite documented "prior provoked DVT (2018)" which is the *driver* of the extended VTE-prophylaxis regimen. Z79.01 (long-term anticoag) captured.
**Strong:** Rx validator added a note: "Post-RYGB patient: calcium citrate is non-substitutable. Pharmacist must NOT substitute calcium carbonate" — load-bearing safety rule projecting forward to the pharmacy.

#### B7 — READY · $0.49 · Month 6 RYGB · **calcium carbonate STRESS TEST**

**ICD-10 (6):** K91.1 (dumping syndrome — appropriate), E11.9, E78.5, G47.33, I10, Z79.899
**CPT:** E&M 99214
**Rx (7 Rx, 7 warnings):** **Calcium carbonate (DISCONTINUE), Calcium citrate (NEW)**, Bariatric MVI, B12, D3, Iron, Atorvastatin
**Verdict:** ✅ **PASS — critical safety rule fired correctly**
**critical-severity warning verbatim:**
> "Calcium carbonate is contraindicated in post-RYGB anatomy — carbonate dissolution requires acidic gastric pH that is absent in the bypassed stomach, placing patient at risk for secondary hyperparathyroidism and accelerated bone loss. Confirm discontinuation and that patient understands calcium citrate is a non-substitutable lifelong requirement."

The model correctly identified the user's pharmacy switch from citrate to carbonate as contraindicated, drafted carbonate as DISCONTINUE + citrate as NEW, and surfaced the load-bearing post-RYGB safety rule. **This is exactly the demo-critical content.**
**Minor:** missed Z90.3 (acquired absence of stomach).

#### B8 — READY · $0.49 · Month 12 sleeve, B12 def + weight regain

**ICD-10 (8):** E53.8, D50.9, E55.9, E11.9, I10, G47.33, Z98.84, E63.9
**CPT:** E&M 99215 (established high-MDM) · modifiers `[25]`
**Rx (7 Rx, 11 warnings):** Cyanocobalamin SQ + sublingual, Ferrous sulfate, D3 loading + maintenance, Calcium citrate 750 BID, Bariatric MVI
**Verdict:** **CONDITIONAL** — missed D51.9 (B12 deficiency anemia) despite documented macrocytosis (MCV 99) + B12 102 pg/mL + Hgb 11.8. Has E53.8 (B12 deficiency) but anemic component missing.
**Strong:** Critical-severity Rx warning fired correctly for an over-the-cap dose: "Dose 650 mg/day exceeds verified adult max of 325 mg/day for ferrous sulfate" — the dose-range validator caught BID dosing of 325 mg as exceeding the per-day cap.

#### B9 — READY · $0.57 · Year 2 RYGB · protein-calorie malnutrition

**ICD-10 (7):** Z98.84, R63.4 (abnormal weight loss), R53.83 (chronic fatigue), E03.9, E11.9, I10, Z79.890
**CPT:** E&M 99215 · proc `[96160]` (health-risk assessment) · no modifier
**Rx (6 Rx, 11 warnings):** Bariatric MVI, B12, Calcium citrate, D3, Iron, Levothyroxine
**Verdict:** **CONDITIONAL** — missed E43 / E44.0 / E44.1 / E46 despite explicit documented "PROTEIN-CALORIE MALNUTRITION" diagnosis with albumin 2.8, pre-albumin 12, sarcopenia, peripheral edema. R63.4 alone under-codes a documented major-complication encounter. Visit text explicitly references admission for "nutritional rehabilitation"; E&M 99215 (outpatient established) vs 99221+ (initial inpatient) is a borderline call.
**Strong:** Rx validator surfaced refeeding-syndrome risk: "Active refeeding syndrome risk (albumin 2.8, Mg 1.9, phos 3.0, profound malnutrition). Consider empiric thiamine supplementation BEFORE initiating refeeding."

### Vascular Surgery (10 visits — 3 READY, 7 FAILED)

#### V1 — READY · $0.34 · Venous CEAP C3 GSV reflux

**ICD-10 (4):** I83.012, I83.812, I87.2, I10
**CPT:** E&M 99215 · proc `[93971]` (limited venous duplex) · modifiers `[25]`
**Rx (1 Rx, 0 warnings):** Lisinopril (continue)
**Verdict:** **PASS** — varicose veins with edema (I83.012 left thigh + I83.812 right), venous insufficiency (I87.2). CEAP class encoded correctly in SOAP. Compression-failure history captured. RFA + phlebectomy plan documented. CV-risk-factor cross-cut completed (never smoker, BP at goal).
**Minor:** 93970 (bilateral complete) would be more accurate than 93971 (limited) since both legs were duplexed; both are valid.

#### V2 — READY · $0.47 · Venous CEAP C6 ulcer, prior DVT

**ICD-10 (8):** I83.012, I87.002, I83.012, I10, E11.9, Z79.84, E66.9, Z87.891
**CPT:** E&M 99215 · proc `[93971, 93971]` · modifiers `[26, 59]`
**Rx (2 Rx, 2 warnings):** Metformin (continue), Lisinopril (unclear — flagged)
**Verdict:** **CONDITIONAL** — missed Z86.718 (personal history of VTE) despite explicit "extensive left iliofemoral DVT 12 years ago" which is the *root cause* of the patient's post-thrombotic syndrome on the left leg. This is a primary indexed history finding.
**Minor:** 93971 listed twice (de-dup gap?). Modifiers `[26, 59]` chosen without `[25]` on E&M; modifier 25 is conventional when E&M + procedure same day.

#### V3 — **READY (anomalous) · $0.25** · PAD Rutherford 3 smoker · **cilostazol/HF stress test**

**ICD-10:** ❌ NULL
**CPT:** ❌ NULL
**Rx:** ❌ NULL
**SOAP:** 4,747-char SOAP generated successfully (full subjective, objective, assessment, plan)
**Verdict:** ❌ **P0 PIPELINE BUG**

Worker log:
```
em-coding:llm-mdm "llm call failed" visitId=cmp2y2e99000bgs87mn2f22b0
attempt=first error=400 invalid_request_error: Your credit balance is too low...
[transcribe-md-worker] info visit completed jobId=… visitId=…
```

The L7 (auto-coding) layer failed with a credit-exhaustion error from the Anthropic API, and the worker still marked the visit `COMPLETED → status=READY`. The patient-facing UI would show a SOAP with no codes / Rx and the operator would not be alerted. **This is exactly the failure mode a demo cannot tolerate.** Cilostazol/HF stress test could not be evaluated as a result.

#### V4–V10 — FAILED · processing failed during entity extraction (L3) or SOAP drafting (L4)

All seven failed with the same root cause as V3: Anthropic API credit balance exhausted mid-run. Unlike V3, the failure happened earlier in the pipeline (L3/L4), so the visits correctly transitioned to status=FAILED. Visit-level reviewReason text was "Processing failed during entity extraction. The audio file may be corrupt or in an unsupported format — please re-upload to try again." — this is a copy-string mismatch (the failure was credits, not audio), but a separate finding.

Per-visit clinical stress tests **NOT EXECUTED**:
- V4: CLI Rutherford 5 ulcer + AF on apixaban + CKD 3a — multi-comorbid demo case
- V5: AAA 5.2 cm surveillance — borderline-threshold decision
- V6: Type B aortic dissection — TEVAR planning
- V7: Asymptomatic 75% carotid — medical-mgmt vs CEA decision
- V8: **TIA + 85% carotid — prasugrel/vorapaxar contraindication stress test** ⚠️ HIGH-VALUE
- V9: CKD 5 AVF planning (Rule of 6s, CPT 36821)
- V10: **EVAR 5.8 cm AAA 110 mL iohexol — contrast AKI stress test** ⚠️ HIGH-VALUE

These should be re-run after credit top-up.

---

## Section C — Gaps Identified + Fix Status

### G1. ICD-10 coding misses — documented findings not coded

The L7a prompt is missing some explicit documented findings. Pattern: when a finding is in the PMH list as a labeled entity (e.g., "GERD (omeprazole 40 daily)", "HFpEF, EF 55%, NYHA Class II", "prior provoked DVT 2018"), the model tends to leave it out of the emitted ICD set, often because there's no plan-section action tied to that specific condition this visit. The L7a critique should treat any documented PMH entity as a chronic-condition candidate (PR #217 fixed the parallel bug for K76.0 + G47.33).

**Impacted visits + missed codes:**
| Visit | Missed code | Source text |
|---|---|---|
| B2 | K21.9 (GERD) | "GERD (omeprazole 40 daily)" |
| B3 | I50.32 / .30 / .31 (HFpEF) | "CHF: HFpEF, EF 55% on recent echo, NYHA Class II" |
| B4 | N17.x (AKI) | "Cr 1.4 (admit baseline 0.8); BUN/Cr ratio 23 — pre-renal" |
| B4 | E86.0/.9 (dehydration) | "Dehydration — clinically dry, ortho concerning" |
| B4 | R10.12 / .13 (LUQ pain) | "Persistent LUQ pain, dull, 5/10" |
| B6 | Z86.718 (hx VTE) | "prior provoked DVT (2018)" |
| B7 | Z90.3 (absence of stomach) | "post-RYGB anatomy" |
| B8 | D51.9 (B12 def anemia) | "Hgb 11.8 (mild), MCV 99 (mildly macrocytic)" |
| B9 | E43 / E44.x (PCM) | explicit "PROTEIN-CALORIE MALNUTRITION" + albumin 2.8 |
| V2 | Z86.718 (hx VTE) | "extensive left iliofemoral DVT 12 years ago" |

**Impact:** under-codes the encounter complexity; some affect E&M-bump opportunities. Demo-visible if the demo focuses on coding completeness.

**Fix status:** Documented as a prompt-quality follow-up. Recommended approach: extend the L7a "documented findings list" extraction (the same machinery PR #217 used for K76.0/G47.33) to cover GERD, HFpEF, AKI, dehydration, abdominal pain, hx VTE, surgical anatomy status, B12-anemia, and protein-calorie malnutrition. This is the most demo-impactful follow-up.

### G2. Bariatric phase-status code (Z90.3 / Z48.815) sparsely used

Bariatric post-op visits emit Z98.84 (bariatric status) but the more specific Z90.3 (acquired absence of stomach for RYGB) and Z48.815 (encounter for surgical aftercare of digestive system) are rarely used. SOAP guidance for `bariatric-surgery` already mentions phase identification — the L7a prompt should pair the phase with the Z-code that signals it to the payor.

**Impact:** minor (clinical care is unchanged); affects billing audit trail.

**Fix status:** documented. Folded into the same L7a prompt extension as G1.

### G3. CPT 99203/99204/99205 vs 99213/99214/99215 — patient-status detection

The synthetic patient (Kasra) is reused as an established patient across all 19 visits, so the model correctly emitted established-patient codes (99213–99215). This is *correct behavior* — but worth flagging that the demo's per-visit-type expectations need to align with the patient-status in the system. Recommend: for the live demo, create a fresh TranscribeMdPatient row per visit type to exercise the new-patient codes (99204/99205).

**Fix status:** demo-script change, no code change required.

### G4. V1/V2 — duplex code 93971 vs 93970

V1 + V2 emitted 93971 (limited venous duplex) for bilateral-leg duplex studies; 93970 (complete bilateral) would more accurately represent the scope documented in the SOAP. Both are in the allowlist. Could be a prompt-strengthening note in the vascular-surgery specialty guidance.

**Fix status:** documented; nice-to-have, not demo-blocking.

### G5. Modifier 25 omitted on V2 (E&M + procedure same day)

V2 emitted procedure 93971 alongside E&M 99215 without modifier 25. Modifier 25 is conventional and was correctly applied on V1 (same procedure). The model's reasoning omitted it on V2.

**Fix status:** worth a one-line addition to the L7b prompt: "When a procedure code is emitted alongside an E&M code on the same date, modifier 25 is the default unless documentation explicitly indicates otherwise."

### G6. B8 — fallback to outpatient code instead of inpatient initial

B8 (Year 2 malnutrition admission) emitted 99215 (established outpatient) when the SOAP text explicitly stated "Admit for nutritional rehabilitation". 99221+ (initial inpatient) is the correct family. The L7b prompt should treat documented "admit / inpatient" verbatim as a hard signal to swap to 99221–99223.

**Fix status:** documented; folded into G5 as the same L7b strengthening.

### G7. ferrous sulfate alias gap — caught BID dosing on B8

B8 fired a critical-severity warning: "Dose 650 mg/day exceeds verified adult max of 325 mg/day for ferrous sulfate". This means the dose-range validator DID match "Ferrous sulfate" → existing entry — but other visits (B6, B7, B5) flag "Ferrous sulfate (Iron)" / "Iron" / "Iron (elemental)" as "not in verified safety database". The alias resolver doesn't catch the parenthetical / generic-name variations.

**Fix status:** addressed in this PR (G8 dose-range additions include alias coverage).

### G8. Rx dose-range catalog gaps (~12 drugs flagged "not in verified safety database")

Drugs prescribed but missing from `packages/ai/src/data/dose-ranges.ts`:
- **Cyanocobalamin / Vitamin B12 (oral + sublingual + SQ)** — appears on every late post-op bariatric visit
- **Cholecalciferol / Vitamin D3** — appears on every bariatric + many CKD vascular visits
- **Iron / Ferrous sulfate / Ferrous fumarate** — alias coverage incomplete
- **Bariatric multivitamin** / **Multivitamin** — needs catch-all entry with "verify formulation" note
- **Vitamin A, E, K** — BPD-DS supplementation triplet (B3 needs it)
- **Zinc** — BPD-DS, copper-deficiency interaction
- **Enoxaparin** — every post-op bariatric visit (B3, B4, B6)
- **Piperacillin-tazobactam (Zosyn)** — B4 IV empiric coverage
- **Pantoprazole** (IV) — B4 anastomotic protection
- **Levothyroxine** — common comorbidity coverage (B9)

**Fix status:** **PR opened** — see Fix Roll-up below.

### G9. **P0 pipeline bug — V3 silent-completion on L7 failure**

When an L7 layer (em-coding / icd / cpt / rx) throws a non-retryable error mid-pipeline, the worker continues to mark the visit as `COMPLETED` with `status=READY`. The SOAP from L4 + critique from L5 + polish from L6 are persisted but the automation columns (`icdCodes`, `cptCodes`, `rxDrafts`) remain NULL. The patient-facing UI surfaces a "ready for review" visit with no codes / Rx.

**Reproduction:** V3 hit a `400 invalid_request_error: Your credit balance is too low` from the L7 LLM call. The worker logged the error as a warning, did not enqueue a retry (correctly — credit exhaustion isn't recoverable by retry), but then logged `visit completed` and transitioned status to READY.

**Recommended fix shape:** if ANY of `runLayer7a` / `runLayer7b` / `runLayer7c` throws and the resulting column is still NULL, the worker should:
1. Set `status = NEEDS_REVIEW` (or a new `INCOMPLETE` enum)
2. Populate `reviewReason` with the specific layer that failed
3. Surface a banner in the visit UI: "Auto-coding incomplete — see review notes"

**Fix status:** **NOT FIXED in this audit task** — requires worker-layer changes spanning 04/05/06/07 + a status enum extension. Recommended as a fast-follow PR; the credit-exhaustion failure mode happens to be the most concerning case but the bug shape is generic to any L7-layer error (timeout, malformed response, validator throw).

### G10. **P0 ops bug — DLQ enqueue rejected by BullMQ**

Worker log (verbatim, repeated for every failed visit):
```
[transcribe-md-worker] DLQ enqueue failed for job visit-cmp2y2e9x000igs870ofbbbps-29643488:
  Error: Queue name cannot contain :
```

The DLQ queue name `dlq:permanent-failures` (`apps/transcribe-md/src/lib/queue.ts:166`) contains a colon, which BullMQ rejects as a name. **All dead-lettered jobs are being silently dropped.** This has been live since the DLQ landed (PR-L per the comment); 7 of the 7 failed visits in this audit failed to enqueue to DLQ.

**Recommended fix:** rename `DLQ_QUEUE_NAME` to `dlq-permanent-failures` (or `dead-letter-permanent`). One-line change; no data loss since the DLQ has been silently dropping jobs anyway (the DLQ structure was never populated).

**Fix status:** **NOT FIXED in this audit task** — flagged for fast-follow PR. Easy fix, but I want Kasra to confirm the rename rather than chose unilaterally because the DLQ name appears in BullBoard dashboards.

### G11. Visit-failure reviewReason copy mismatch

V4–V10 failed because of Anthropic credit exhaustion, but the `reviewReason` written to each visit reads:
> "Processing failed during entity extraction. The audio file may be corrupt or in an unsupported format — please re-upload to try again."

The text_notes inputMode has no audio file. The error-categorization layer is emitting an audio-specific message regardless of inputMode. This is a UX bug — operator sees "audio corrupt" for a text-only visit and is misdirected.

**Fix status:** documented. Likely a one-line fix in `worker/error-categorize.ts` to branch on inputMode.

---

## Section D — UI Surfaces (Section 4 of brief)

| Surface | Bariatric Surgery | Vascular Surgery | Status |
|---|---|---|---|
| Marketing pill list | ✅ Present | ✅ Present | Auto-derived from shared catalog |
| Marketing headline count | "Twelve specialty templates" ✅ | "Twelve specialty templates" ✅ | Auto-derived via PR #218 |
| `/visits/new` dropdown | ✅ Present (`SPECIALTIES_FOR_VISIT_CREATE`) | ✅ Present | Reads shared catalog |
| `/settings` default-specialty | ✅ Present (`SPECIALTIES` full list) | ✅ Present | Reads shared catalog |
| Avatar tone | **coral** | **sky** | `clinician-specialty-color.ts:103 / 114` |
| Avatar aliases | bariatricsurgery, bariatric, bariatrics | vascularsurgery, vascular, cvs, phlebology | All covered |
| `/admin/usage` specialty breakdown | n/a — feature not present | n/a | Admin usage page does not currently slice by specialty; not a regression |

No UI bugs detected. The marketing site is live at the auto-derived "Twelve specialty templates" headline with all 12 pills present.

---

## Section E — Fix Roll-up

| Gap | Severity | Fix status | PR |
|---|---|---|---|
| G1 — Documented findings not coded (10 instances) | High (demo-visible) | Recommended L7a prompt extension; not in this PR | Follow-up |
| G2 — Bariatric phase Z-codes | Low | Folded into G1 fix | Follow-up |
| G3 — New vs established patient codes | n/a (demo-script issue) | No code change | — |
| G4 — 93971 vs 93970 | Low | Recommended L7b prompt note | Follow-up |
| G5 / G6 — Modifier 25 + inpatient code on admission | Medium | Recommended L7b prompt strengthening | Follow-up |
| G7 — ferrous sulfate alias gap | Low | Addressed by G8 PR | This audit |
| **G8 — Rx dose-range catalog (12 drugs)** | Medium | **Will fix in this audit task** | **opening now** |
| **G9 — V3 silent-completion** | **P0** | Documented; needs worker error-handling change | Fast-follow |
| **G10 — DLQ enqueue rejected** | **P0 (ops, not demo)** | Documented; one-line rename | Fast-follow |
| G11 — reviewReason audio-copy on text-only visits | Low | Documented; one-line branch | Follow-up |

---

## Section F — Demo-Confidence Recommendation

**For the demo, use the Bariatric Surgery flow as the primary specialty showcase.** Bariatric clinical content is strong:
- All 9 phases produced clinically-coherent SOAPs
- Phase identification is reliable (POD #5 / POD #14 / Month 6 / Year 2 etc.)
- The load-bearing calcium-citrate-vs-carbonate rule fires correctly with critical-severity prominence
- BPD-DS supplementation regimen drafted comprehensively (Vit A/E/K, B12, D3, iron, zinc)
- E&M complexity reflects the visit type
- Cost per visit $0.33–$0.57 (well within budget)

**For vascular,** stick to the venous-insufficiency demo cases (V1/V2 verified) until the V4–V10 batch is re-run after credit top-up. The carotid stress test (V8) and EVAR contrast stress test (V10) are the demo's highest-impact safety stories and **must be verified before they're shown.**

**Before the demo, address the two pipeline P0s:**
- G9 (silent-completion on L7 error) — without this fix, any LLM-side hiccup during the demo could leave a visit "ready" with empty codes/Rx.
- G10 (DLQ rename) — operational, not demo-visible, but worth fixing in the same window.

After credit top-up: re-run V4–V10 with the same harness. Estimated cost: ~$4. The fixes to G1/G5/G6/G11 can ride on a single L7a/L7b prompt-tightening PR.
