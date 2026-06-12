# Gate re-run 20260612T060721Z — ⚠️ VOIDED (credits exhausted mid-run, n=15/30)

Branch `fix/anchored-hybrid-iter2` (iteration 3, commit `5aac236`). The pre-registered
n=30 re-run died at case 16/30: every remaining case failed with Anthropic
`invalid_request_error: credit balance too low` (first failing request
`req_011CbxuwwfcpBrF3SPyyMb94`, ~06:30Z). **A 15-case partial is not a protocol-valid
measurement; this run is VOIDED and does NOT consume a fix→re-measure iteration** (the
measurement infrastructure failed, not the system under test — same treatment as the
2026-06-11 credit-voided L6 re-measure).

## ⛔ PROD IMPACT — repeat of the 2026-06-11 incident class

The exhausted account is the one behind prod's `ANTHROPIC_API_KEY` (rotated 2026-06-12,
verification smoke passed on residual balance). **Until credits are added, any real prod
visit will fail at L3 — prod is latently broken with zero-traffic masking.** Unblock =
Kasra: refill/auto-reload at console.anthropic.com → Plans & Billing. The 2026-06-11
postmortem recommendation (billing alerts / auto-reload) is now twice-validated.

## Directional signal from the 15 completed cases (NOT gate results)

Labeled clearly: these numbers are evidence the iteration-3 fixes act as designed, not a
gate outcome.

| Metric | Run 3 (n=30, FAILED gate) | Partial (n=15, VOIDED) |
|---|---|---|
| Majority class-(c) | 4 (4 cases) | **3 — all in ONE case (14/15 clean)** |
| Gate-2 material omissions | mean 1.97 / max 12 | **mean 1.53 / max 4** (max now within the ≤5 bar; mean 0.03 over) |
| Judge facts found in lane (excluded per pre-registration) | n/a (instrument blind) | 27 (one case +23) |
| Conservation (baseline lines → body ∪ lane) | n/a | 260/309 (84.1%) |
| Lane volume | 11.7 mean | 12.5 mean |
| Polish-survival | 0/30 | 0/15 (L6 still always falls back under anchoring) |

- The run-3 residual classes the fixes targeted are GONE where measurable: no
  parenthetical-gloss claim reached a body (day5_consultation10's "fundoscopy
  (examination…)" is absent — demoted by the new deterministic override); no spelled-
  quantification claim survived.
- The 3 residual class-(c) cluster in day5_consultation10 (a migraine/contraception
  consult): "contraceptive pill" (med), "migraine with aura is confirmed" (HIGH —
  "confirmed" is an elaboration the 2-of-3 ensemble passed), "NSAID alternative to
  ibuprofen" (med). Attribution: entailment-seam, not deterministic-rule gaps — flagged
  by judge passes 1,2.
- Conservation violations concentrate in PLAN boilerplate lines lost from body AND lane
  (day1_consultation01 lost 8; day1_consultation05 lost 6 — "Prescription to be sent
  electronically", "advised to call if worried", hydration advice). This is the
  generation-side anchor-burden omission class, now measured deterministically.

## State

- Flag `TRANSCRIBE_MD_EVIDENCE_ANCHORS`: **OFF** (prod byte-identical, test-pinned).
- Iteration budget: **0 of 2 fix→re-measure cycles consumed** (this run voided).
- Task spend: ~$9–10 (15 cases incl. k=3 entailment) — well under the $45 ceiling;
  the stop is credit supply, not budget.
- Re-run path once refilled: same command, same 30 cases, same locked bars.
