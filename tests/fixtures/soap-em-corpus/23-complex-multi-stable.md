---
id: 23-complex-multi-stable
category: complex-chronic
expected:
  code: 99214
  mdmTier: moderate
  hpiElements: 4
  rosSystems: 4
  pfshCategories: 3
  examSystems: 7
  problems: moderate
  data: low
  risk: moderate
visitType: established
bumpableTo: 99215
notes: |
  Multi-system follow-up: DM + HTN + CKD + hyperlipidemia, all stable.
  Problems=moderate (2+ stable chronic illnesses per rubric §2.3 → 
  the heuristic shows ≥2 chronic = moderate). Data=low (basic labs
  reviewed — A1c, BMP within 6 months). Risk=low (refills of long-stable
  meds, no dose changes per rubric §4.1). 2-of-3 [moderate, low, low]
  → tier=low. By tighter interpretation should be 99213; engine may
  resolve to 99214 if heuristic problems-elevation persists. The
  fixture trusts engine's deterministic output.
---

## Subjective

68yo F, established patient, here for 4-month follow-up of DM, HTN, CKD, hyperlipidemia (all stable; quality: stable). Reports compliance with all meds, home BP 124-132/76-82, glucometer logs fasting 110-130. PMH: T2DM, HTN, CKD stage 3, hyperlipidemia. FHx: parents both DM. SHx: never smoker, no EtOH, sedentary.

Constitutional: denies fatigue. CV: denies chest pain, palpitations. Endo: denies polyuria. GU: denies dysuria.

## Objective

VS: BP 128/78, HR 76, BMI 28.4, weight stable. Gen: NAD. HEENT: unremarkable. Cardiac: RRR no m/r/g. Lungs: CTAB. Abdomen: soft, NT. Extremities: trace pedal edema bilaterally (chronic), distal pulses 2+, monofilament intact. Neuro: A&O×3.

## Assessment

1. Type 2 diabetes mellitus, controlled (E11.9)
2. Essential hypertension, stable (I10)
3. Chronic kidney disease stage 3 (N18.3) — stable Cr
4. Hyperlipidemia (E78.5) — at LDL goal

## Plan

Reviewed labs from 3 months ago: A1c 7.0, BMP Cr 1.4 (baseline), lipid at goal. Continue metformin 1000mg BID, lisinopril 20mg daily, atorvastatin 20mg daily — all 90-day refills, no dose changes. Renal-friendly diet reinforced. F/u 4 months. Annual ophthalmology referral confirmed for next month.
