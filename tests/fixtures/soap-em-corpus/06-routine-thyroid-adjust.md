---
id: 06-routine-thyroid-adjust
category: routine-pcp
expected:
  code: 99213
  mdmTier: low
  hpiElements: 4
  rosSystems: 3
  pfshCategories: 3
  examSystems: 5
  problems: low
  data: low
  risk: minimal
visitType: established
bumpableTo: null
notes: |
  Hypothyroidism follow-up w/ TSH-driven dose adjustment.
  Problems = low (1 stable chronic). Data = low (TSH reviewed in office).
  Risk = moderate (Rx dose-change is "increase" → Rx-mgmt floor; rubric
  §4.1 explicit). 2-of-3 sorted [moderate, low, low] → tier=low → 99213
  by deterministic; the LLM judge may upgrade to moderate when "uncertain
  prognosis" reasoning is added. We keep this fixture at the heuristic
  result for stability.
---

## Subjective

48yo F, hypothyroidism × 3 yrs, here for 3-month TSH check (location: thyroid; quality: stable; duration: 3 yrs h/o; timing: chronic). Reports mild fatigue past 4 weeks; no weight change, no cold intolerance, no constipation. PMH: hypothyroidism. FHx: mother hypothyroid. SHx: never smoker, occasional EtOH. Constitutional: mild fatigue. Endo: denies polyuria, heat intolerance.

## Objective

VS: BP 118/74, HR 72, T 98.4°F, weight stable. Gen: NAD. HEENT: thyroid not enlarged, no nodules. Cardiac: RRR no m/r/g. Skin: dry but not flaky. Neuro: A&O×3, reflexes 2+ symmetric.

## Assessment

1. Hypothyroidism, suboptimally controlled today (E03.9)

## Plan

TSH ordered — drawn today (8.4, elevated from 4.2 last visit). Increased levothyroxine to 88mcg daily from 75mcg. F/u TSH in 8 weeks. Continue calcium-iron separation by 4 hr from levo. Patient education re fatigue improvement timeline.
