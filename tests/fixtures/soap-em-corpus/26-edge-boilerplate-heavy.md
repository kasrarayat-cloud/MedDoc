---
id: 26-edge-boilerplate-heavy
category: edge-case
expected:
  code: 99213
  mdmTier: low
  hpiElements: 3
  rosSystems: 5
  pfshCategories: 2
  examSystems: 6
  problems: low
  data: minimal
  risk: low
visitType: established
bumpableTo: null
notes: |
  Tests engine resistance to ROS template-padding. 14-system "all negative"
  ROS doesn't inflate problem count; engine should still compute LOW MDM
  based on actual problem (1 stable chronic) + minimal data + low risk
  (refill, no dose change). Boilerplate-heavy notes are common in EHRs;
  engine should NOT auto-bump on inflated counts.
---

## Subjective

40yo F, established patient, here for 3-month HTN follow-up. BP at home 118-128/74-82. No new symptoms (location: n/a; duration: stable on lisinopril × 18 mo).

ROS (template, all reviewed): Constitutional: denies fever, chills, weight change, fatigue. Eyes: denies vision changes, eye pain, drainage. ENT/Mouth: denies sore throat, ear pain, nasal congestion, oral lesions. CV: denies chest pain, palpitations, dyspnea, edema. Resp: denies cough, SOB, wheezing, hemoptysis. GI: denies nausea, vomiting, abdominal pain, change in bowel habits. GU: denies dysuria, frequency, hematuria. MSK: denies joint pain, stiffness, swelling. Skin: denies rash, lesions, pruritus. Neuro: denies headache, dizziness, weakness, paresthesias. Psych: denies depression, anxiety, suicidal ideation. Endo: denies polyuria, polydipsia, heat/cold intolerance. Heme: denies easy bruising, bleeding. Allergic: denies seasonal symptoms today.

PMH: HTN. NKDA. Tobacco: never. EtOH: 1-2 drinks/wk.

## Objective

VS: BP 122/76, HR 72, RR 14, T 98.4°F, weight stable. Gen: well-appearing. HEENT: unremarkable. Cardiac: RRR no m/r/g. Lungs: CTAB. Abdomen: soft, NT. Extremities: no edema.

## Assessment

1. Essential hypertension, stable (I10)

## Plan

Continue lisinopril 10mg daily — refill 90 days. Continue home BP log. F/u in 6 months. Routine BMP within 1 year, due now → ordered at lab today (patient will go to lab).
