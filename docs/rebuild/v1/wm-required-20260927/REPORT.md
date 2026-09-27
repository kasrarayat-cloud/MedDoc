# Required WM ordinary narrative integration — 2026-09-27

## State and scope

Selected code `7ebf5059edd283d63be1b3437329b2d4b9b07af2` plus repair `edd02753c0816e3eb1d0955cfd6a3494f401bb93` in `/opt/meddoc-pro/.worktrees/v1-wm-integration`, branch `v1/wm-required-repairs`, selects required work from preserved draft `4396c801` onto reviewed combined V1 base `39e8f6b9b0978d0025fa2e0d0aa9149b34b3f8d9`. The source draft and its execution/financial evidence remain untouched. This is prepared code; no application installation, flag activation, production write or provider call occurred.

The selected path accepts ordinary WM narratives, proposes answers and statement wording from source units, shows held/uncertain answers for correction, preserves editor/reviewer identities, prevents generation from replacing human decisions, and carries source evidence through finalization into the original Word form. The paired C# adapter and Python digest were selected together. Shared v3 ordinary-note, repeated-label, control, finalization and review-warning repairs were kept as unions. Campaign, activation and historical cleanup tools were excluded.

WM remains one adapter and one independently authored blank template. This integration is required V1 work; it supplies no success claim for the separate 60-template compatibility target. The WM flag remains disabled by default pending release gates. Generic ordinary-note block B-G1 remains open; this port does not turn prior 92%/94% held subsets into success.

## Sonnet 5 preparation

Narrative requests use the common `claude-sonnet-5` profile and request builder. The profile supplies disabled/medium thinking/effort by default, an 8,000-token output cap and 120-second timeout; adaptive requests use their explicit 16,000-token profile. Reservations include the actual serialized narrative payload, instructions, schema, framing allowance, profile output cap and applicable US multiplier. Common settlement retains metered region, cache reads/writes, thinking, stop reason and historical accounting. No historical record was rewritten.

Response text blocks are selected by type. Refusal, incomplete output and a different response model cannot be adopted. Preparation errors are classified unsent before client construction; exceptions after submission remain uncertain and are not retried automatically. Six focused mocked profile/replay tests passed. Independent root probes confirmed split text blocks after thinking, refusal/max-token/wrong-model handling and the before/after-send boundary. These are synthetic protocol proofs; they are not an actual Sonnet 5 response or served-worker identity proof.

## Finite evidence

| Check | Candidate result | Limit |
|---|---|---|
| Focused Sonnet and replay | 6 tests, 0.841s, pass | Mocked response/client, zero network |
| WM narrative, Sonnet profile/settlement, WM review | 273 tests, 194.987s, pass | Retained finite synthetic regression and performance checks |
| Known benchmark | Byte identical to preserved draft | Known note cases on one WM form; misses/holds retained below |
| Actual-engine workflow plus shared review/v3 paths | 276 tests, 457.874s; 275 passed, one real integration failure retained | Explicit operator qualification, not production identity or native Word desktop |
| Repaired cleared-answer workflow and review guards | 80 tests, 67.013s, pass | Exact failed actual-engine case plus changed shared guard tests; unaffected cases reused |
| Independent root Sonnet/union refutation | Nothing found in bounded claims | Script/result retained; no provider |
| Independent Word/source/provenance refutation | Nothing found in original bounded claims and final tiny repair delta | Repeated identical sentences under RIGHT/LEFT resolve to correct offsets and remain stable on save; opposite-side citation refuses |

All 17 retained engine source inputs match this selected tree. Reused build manifest `2a1e4477144207bed04d3f3d38cb3b276cdaf7e450ef7d622f1ee63cd4e0d756`, proof `9ded38e9e3f0c6271ce2551ef8adaaa8fbb83ecde7b7bfb0d836365b55c0dbca`; runtime verification passed. C# adapter SHA `883273448d427245e2026efa17ce4c7e38deff354834ae014a3659918a192441` matches the Python pin. Existing runtime was reused without build, activation, lock mutation or spending. No new native Microsoft Word desktop acceptance was performed.

The first benchmark invocation failed during Python module loading before Django setup; its log is preserved. The corrected invocation initialized Django and completed. Output from this candidate and draft is identical: SHA `b4f6707f4d4e6ee13546f1f2afc62c83a24f69922ae037145a2c9c861edf5ce5`.

## Demonstrated integration failure and repair

The combined 276-test run found one missed union condition: the shared `clinician_decided` helper lacked the draft's `edited_by` check. A WM employee could deliberately clear a supported answer, which is stored as `status=missing` with its editor, then a crafted generation request replaced that blank. The existing actual-engine Round 18 test caught this. The failed run and exact failing views snapshot remain in evidence.

The repair treats the saved editor as a human decision in the regeneration guard and as an edit in the clearing audit count. A new regression distinguishes an untouched missing field from a deliberately cleared answer and checks that the employee's edit is never counted as a clinician review. Its initial RED result is retained. The existing actual-engine failing case and all affected review-guard checks passed: 80 tests in 67.013s. The unaffected passing cases from the original run are reused; no blanket full-suite rerun is claimed. No parser, C# adapter, model request or benchmark output changed. The independent Word refuter reread the finished repair at `edd02753` and found no demonstrated defect in its bounded provenance, regeneration and disjoint audit-count claims; that report is retained.

## Known benchmark results, without reclassifying failures

| Selection fixture | Note cases | Correct supported / missing / hold | Other answer results | Statements correct / missed |
|---|---:|---|---|---|
| Careful | 23 | 338 / 1,719 / 7 | 6 expected decisions shown missing | 161 / 2 |
| Weak | 23 | 330 / 1,707 / 7 | 6 decisions shown missing; 12 held where blank expected; 5 held wrong candidate; 3 missed | 157 / 6 |
| Historical file named heldout | 12 | 254 / 789 / 14 | 6 decisions shown missing; 17 unnecessary holds | 83 / 10 |

No wrong *supported* output occurred in these retained selection fixtures. The careful subset has zero unnecessary holds, while the other results above remain. An answer shown missing where ambiguity should be shown as a decision is not an automatic success. These are now known regression cases, including the file historically named `heldout`; none is an unseen qualification cohort. They are not independent Word documents and are excluded from the custom-Word compatibility denominator. Full per-case findings remain in `evidence/known-benchmark-report.txt`.

## Remaining product and evidence limits

The retained design explicitly describes conservative holds for side after a value, unpunctuated mixed-side narratives, incomplete row/level/vein or prior-study context, and some date expressions. These deterministic guards cannot guarantee semantic correctness when no detectable contradiction exists. Literal cell sequences that the engine rewrites (`&p`, `&l`, `&m`, `&b`, `&&`) remain visible refusals; the narrative path allows explicit clinician correction. The legacy labelled path's instructions do not replace the promised ordinary-note workflow.

Generic notes still have the documented residual semantics and original hold-rate evidence in `../notes-recovery-20260927/REPORT.md`: cross-field medication/allergy context, diabetes versus prediabetes, and unrecognized correction wording require further bounded repair/qualification. This WM integration does not close B-G1 or establish useful automatic coverage for all custom forms.

Actual Sonnet 5 behavior on the eligible endpoint, installed worker/model identity, broad Word corpus/render/native-control acceptance, real human dictation, hosting/account agreements and production operations remain separate release gates. No launch readiness or date is inferred from these offline results.

## Recovery

Local scratch and run wrappers remain in `rebuild/.runtime/wm-required-20260927`. The private synthetic environment is outside git; no credential file is copied into evidence. The isolated test DB is port 55706 and must have one test writer at a time. See `CHECKPOINT.md` for active-process and next-action state. Failures must be retained before repair; no source reset, holdout retuning or fresh provider/campaign attempt is authorized by this report.
