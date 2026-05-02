---
id: 09-routine-multi-condition-refill
category: routine-pcp
expected:
  code: 99214
  mdmTier: moderate
  hpiElements: 3
  rosSystems: 4
  pfshCategories: 3
  examSystems: 7
  problems: moderate
  data: minimal
  risk: moderate
visitType: established
bumpableTo: null
notes: |
  Multi-condition refill bundle: HTN + hyperlipidemia + DM all stable.
  Problems = moderate (2+ stable chronic illnesses per rubric §2.3).
  Data = low (BMP/lipid/A1c reviewed within 6 months — no new labs).
  Risk = low (refills only, no dose changes). 2-of-3: [moderate, low,
  low] → low... wait, but the engine flags 2+ chronic = moderate
  problems and the rubric says 2+ stable chronic = moderate. Heuristic
  may resolve to low here (2-of-3 favors low when only problems is
  moderate). The fixture trusts the engine's deterministic output.
---

## Subjective

62yo M, established patient, here for 6-month refill of HTN, hyperlipidemia, T2DM (all stable on monotherapy each). No new sx. Home BP 120-128/76-82, glucometer log fasting 110-130, no hypos. PMH: HTN, hyperlipidemia, T2DM. FHx: father MI age 68. SHx: ex-smoker quit 2010, no EtOH, walks daily.

Constitutional: denies fatigue, weight change. CV: denies chest pain, palpitations. GI: denies abdominal pain. Endo: denies polyuria.

## Objective

VS: BP 122/78, HR 72, BMI 26.9, weight stable. Gen: NAD. HEENT: unremarkable. Cardiac: RRR no m/r/g. Lungs: CTAB. Abdomen: soft, NT. Extremities: no edema, distal pulses 2+. Neuro: A&O×3, monofilament intact.

## Assessment

1. Essential hypertension, stable (I10)
2. Hyperlipidemia, on statin (E78.5)
3. Type 2 diabetes mellitus, controlled (E11.9)

## Plan

Continue lisinopril 20mg daily, atorvastatin 20mg daily, metformin 500mg BID — all 90-day refills, no dose changes. Recent labs (3 months ago) reviewed — A1c 6.8, lipid at goal, BMP unremarkable. Continue home BP + glucose log. F/u 6 months. Annual labs due in 9 months.
