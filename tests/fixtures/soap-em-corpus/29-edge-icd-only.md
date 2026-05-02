---
id: 29-edge-icd-only
category: edge-case
expected:
  code: 99213
  mdmTier: low
  hpiElements: 0
  rosSystems: 0
  pfshCategories: 0
  examSystems: 1
  problems: low
  data: minimal
  risk: low
visitType: established
bumpableTo: 99214
notes: |
  Tests fallback behavior with minimal MDM-relevant prose.
  ICD codes present (1 chronic) so problems=low (1 stable chronic).
  Data=minimal. Risk=low (refill of long-stable med). 2-of-3 [low,
  low, minimal] → low → 99213.
---

## Subjective

[not documented]

## Objective

VS: BP 124/78. Gen: NAD.

## Assessment

1. Essential hypertension, stable (I10)

## Plan

Continue lisinopril 10mg daily — refill 90 days, no change.
