# Re-certification decision rule — 2026-06-13T00:38:00Z (pre-registered BEFORE tokens)

Branch `fix/anchored-live-followups`. ONE n=30 run under the locked protocol
(`stabilized-protocol-20260611T201252Z.md` + addendum `…230650Z.md`), same rubric, same
judge prompts, same 30 cases, NO iterations. Purpose: the deployed configuration must stay
the measured configuration after the polarity-alignment precision fix (the #311 smoke's
lisinopril misfire — 31/104 of the final gate run's negation_mismatch demotions were the
same incidental-span-negation class).

## System under test (delta vs the certified configuration of run `…T183517Z`)

- `04b-anchor-verify.ts` polarity alignment: a POSITIVE claim demotes on a span negation
  ONLY when the negation targets the claim's content (4-token window, prefix-5). Invented
  denials (negative claim, positive span) and true polarity flips demote unchanged.
- Nothing else in the verifier/prompt path changes. (The E/M-confirm feature and boot
  guard in this branch do not touch the eval path.)

## Decision rule (committed before tokens; the AMBER state is unchanged either way)

- **KEEP the precision fix iff BOTH:**
  1. Gate-1 residuals stay **within the certified band: majority class-(c) ≤ 4, zero
     unanimous (3/3), zero medium-or-higher severity**;
  2. Gate-2 completeness **passes** (mean ≤ 1.5 AND max ≤ 5, judge-unavailable = 0).
- **Otherwise ROLL BACK Phase 1**: revert the verifier polarity commit, redeploy, the
  certified configuration is restored, and the re-certification failure is reported with
  per-case attribution.
- Either way: the reconciliation entry + diligence paragraph are updated to describe the
  configuration ACTUALLY RUNNING in prod, and the Gate-2 / conservation / lane-volume
  numbers are refreshed from this run (the fix should help completeness — measured, not
  assumed).

## Bounds

One run only. Rubric, bars, and judges untouched. Budget ≈$18–20 (ceiling $30 for the
task); balance ≥$25 confirmed by Kasra before launch (standing rule).
