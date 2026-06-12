# Gate instrument validity note — 2026-06-12T06:45:00Z (pre-registered BEFORE the re-run)

Branch `fix/anchored-hybrid-iter2`. This note is committed BEFORE any gate tokens are spent,
in the same spirit as the protocol (`stabilized-protocol-20260611T201252Z.md`) and its
addendum (`stabilized-protocol-addendum-20260611T230650Z.md`). **The rubric, the judge
prompts for Gate 1, and both pre-registered bars are UNCHANGED.** What changes is (a) the
system under test (verifier iteration 3) and (b) one demonstrably broken clause of the
Gate-2 instrument, fixed to match its own pre-registered definition.

## The instrument defect (run-3 forensics, day2_consultation05)

The addendum defines: *"material omission := transcript-supported fact in the BASELINE
final note absent from the new body AND not in the lane; lane-capture doesn't count as
omission."* Run 3 (`primock57-fullchain-fabrication-20260612T014805Z.json`) shows the
single-pass completeness judge violating the lane clause it was instructed to apply:

- Judge omission **"Patient lives with his wife"** — lane item 4 (shown to the judge,
  numbered): **"- Lives with his wife."** (verbatim).
- Judge omission **"Patient is a non-smoker"** — lane item: **"- Smoking: Non-smoker."**
- Judge omission **"Allergy to penicillin"** — lane item: **"- Penicillin (reaction not
  stated)."** under section *Drug Allergies*.
- Judge omission **"Aspirin 75 mg once daily, self-initiated…"** — lane item: **"- Aspirin
  75 mg once a day (patient-initiated based on something read on the Internet…)"**.

9 of that case's 12 judged "omissions" were in the lane it was shown. The case scored
max=12 against the ≤5 bar; the run-3 Gate-2 FAIL (mean 1.97 / max 12) is therefore partly
an instrument artifact. (The remaining 3 — e.g. the patient's occupation, the TIA-urgency
remark — are genuine and remain countable.)

## The fix (instrument, not rubric)

`scripts/eval/conservation-matcher.ts` (unit-tested on the verbatim run-3 fixtures above):

1. **Deterministic lane clause** — the judge keeps deciding transcript support and body
   absence (unchanged prompt); each judged fact is then checked against the lane
   DETERMINISTICALLY (content-token coverage ≥0.5 with prefix-5 equivalence, section label
   included, hard digit veto — "Aspirin 300 mg" can never be captured by a 75 mg item).
   Lane-captured facts are reported but NOT counted, exactly as pre-registered.
2. **Conservation check (new, diagnostic)** — every content line of the flag-off baseline
   note must appear in the new body ∪ lane (same matcher; judge-free). Reported per case;
   catches silent loss regardless of judge behavior. Not a gate — the gates are the two
   pre-registered bars, unmoved.

## System-under-test changes measured by this re-run (iteration 3)

- k=3 ensembled entailment (base / elaboration-hunter / clinical-skeptic lenses), majority
  ≥2-of-3 to survive; errored pass votes not-entailed; ≥2 errored passes → verifier_failed.
- New deterministic overrides: spelled quantification under the digits rule
  ("two glasses per week"), parenthetical-gloss support requirement.
- Entailment prompt: elaboration/gloss/quantification/site-transfer/causal-attribution
  rejection rules (abstract classes; no eval-case text embedded).

## Bounds (unchanged from the GOAL)

Bars: majority class-(c)=0 AND completeness mean ≤1.5 / max ≤5. Up to 2 fix→re-measure
cycles inside this task, the rubric never moves, then STOP with per-case attribution.
Budget ceiling $45; ≈$15–25 per run expected (k=3 raises entailment cost) — STOP before
exceeding.
