# Ordinary notes recovery result — 2026-09-27

This closes the interrupted notes repair stream as a local engineering change. It does not close V1, generic ordinary-note qualification, WM narrative integration, broad Word compatibility or live Sonnet 5 verification.

## Recovered and preserved

- Worktree `/opt/meddoc-pro/.worktrees/v1-notes`, branch `v1/ordinary-notes`; recovered HEAD `d346f7c0f8721b91399030eeb40d9cac728df019`, with 44 uncommitted mutation regression lines. No other active writer or notes test was found. Lead preflight `preflight-20260927T161904Z.md` permitted continuation with yellow disk capacity only; no destructive cleanup performed.
- Prior Claude work, draft PR #1287, logs and scratch were preserved. The interrupted batch F had finished; source SHA matched its saved original. Its restore was not repeated. One apparent mutation kill was a syntax error; the invalid attempt is retained and a compiling CJK mutant now fails the intended assertion.
- Prior scratch remains at `/tmp/claude-1000/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/scratchpad/v1/notes-repair3`. Durable selected evidence and original paths/SHA-256 are in `evidence/manifest.json`. Synthetic test PostgreSQL port 55706; no provider calls, spend, external messages, deployment, campaign, holdout, push or merge by this stream.

## Changes and their limits

Recovered R3 commits already repaired quadratic parsing, abbreviation/inner-sentence loss, overly broad plain-value acceptance, minus-sign/instruction handling and unsupported run-on adoption. Original uncommitted pins were committed with additional failing cases in `00dcc969`.

`af948a44` conservatively preserves whole-note evidence for ordinary v3 generation. Existing spoken self-correction markers hold automatic answers across blank paragraphs; a consent answer cannot be adopted while other note units remain outside its evidence. The same governance applies to generation, review, save and finalization, including old drafts. An over-limit source-unit count remains reviewable but held. These guards do not infer consent or correction content.

It also permits complete unlabelled paragraphs for bounded general narrative fields. Independent refutation found two defects in the first implementation: `Lt knee` and `Allergies` could accept wrong-topic paragraphs, and deduplication could silently drop a repeated instruction. Both first failures remain in evidence. RED regression commit `20e15f76` precedes repaired source `6ea775b6683afe4aa0b56b73bc0582d9ce72380d`.

The final paragraph relaxation is confined to exact normalized names: History, History of present illness, HPI, Reason for visit, Plan, Treatment plan, Management plan; only text/long-text, one unique destination, complete selected paragraph, no labelled units and no competing owner qualify. Existing context/shape/type guards remain. Partial, duplicated/side-specific destinations, option questions and reordered output remain governed. Source order and repeated occurrences are retained, including final Word export. The provider still selects relevance among these general fields; the allowlist is not a proof of live semantic relevance or universal ordinary-note completion.

## Finite verification

| Evidence | Candidate and result |
|---|---|
| Baseline required core | Recovered `d346f7c0` + preserved pins: 1,263 tests, 9 skips, 463.772 s, OK |
| Initial repair RED | 5 of 7 new tests failed before implementation |
| Initial shared regression | `af948a44`: 1,275 core tests, 9 skips, 461.620 s, OK; 108 explicit document tests, 52.071 s, OK |
| Final changed-path regression | `6ea775b6` source: 134 ordinary-note and worker/review/finalize/export tests, 45.080 s, OK |
| Mutation proofs | Prior R3 61 distinct final mutations accounted for, including replaced invalid FD proof; 11 new compiling initial-repair mutations killed; two final changed guards independently removed and killed by concrete wrong-destination/data-loss assertions; source restored after each |
| Legacy identity | Unchanged 30-case tab/WM/legacy request, price, fixture and validated-output digest `083b6fca176780ea999f827beae2285273e8706c80a18910def636fbb42a8c9b` on final source |
| Performance | Existing bounded stress probes: 49,900 punctuation stops 0.29 s vs 100.35 s before; 20k stops across three fields 0.05 s vs 22.16 s; 999 Q1 segments 0.05 s vs 6.61 s. These are local observations, not production latency |
| Independent finished-diff refutation | Alerts recovery agent reran unchanged exact probes against `6ea775b6`: wrong Lt-knee/allergy cases conflict with blank answer; repeated-dose Plan retains all three occurrences/offsets and passes unchanged-text finalization governance. NOTHING ELSE FOUND within those bounded claims |

Broad suites belong to their actual earlier candidate; they were not relabelled as final-tree runs. The later source delta is the narrow destination gate and occurrence retention covered by final changed-path checks and fresh refutation. All provider responses in these checks are mocked selections. Export checks inspect actual exported Word bytes/hash but are not native Word desktop acceptance or the 60-file corpus.

## Usefulness and remaining blockers

Retained first-pass subsets are unchanged: five-note module subset supports 1/12 answers, holds 11/12 (92%); ten ordinary-note refuter cases support 5/77, hold 72/77 (94%). A measurement invocation initially used the wrong environment selector and ran the combined 89-answer set twice; those outputs are preserved under explicit `all-*` names, and the corrected GROUP=test/r1 invocations preserve their original denominators. The newer bounded HPI/plan positives and worker-to-export cases are separate regressions, not an improved estimate for either first-pass subset. Holding almost every answer is not a useful completed V1 workflow.

Remaining semantic probes include `Allergies: none. Plan: avoid penicillin.`, `Diabetes: yes. Diagnosis: prediabetes.`, and `Allergies: penicillin, rather amoxicillin.`. The last retains the entire correction phrase rather than interpreting it. These are disclosed limitations, not proven clinical correctness. Generic v3 ordinary-note/model quality remains unqualified; the repaired context guards do not establish it. Long unpunctuated runs may still be held. No mandatory relabelling workaround is proposed.

WM ordinary-note integration is **required V1 work**, not a future patch or permission blocker. See `narrative-disposition.md` for the precise missing path and coupled C#/Python evidence. The preserved draft is not merged wholesale. Required integration will use a new isolated worktree after a confirmed base includes cleared notes and review repairs, adapt requests/limits/accounting to Sonnet 5, retain existing fixtures/proofs and obtain independent refutation. No old campaign grant is reusable by assumption.

Actual installed application/model remain outside this branch's authority; no installed revision, served model, hosting agreement, clinical admission or launch claim is made. Lead recovery owns their current proof and the consolidated V1 blocker list.
