# Adversarial pass over the integrated V1 candidate — 2026-09-28

The mandatory refutation pass over the finished candidate `bf8f7b78` (`v1/release-integration`, draft PR #1291),
run after the three interrupted repairs (D31 selection limits, D31 contradiction handling, D10 coded columns) were
finished, refuted twice, repaired and integrated. Seven read-only lenses, each on its own throwaway database, and an
independent verifier that reproduced every HIGH/MEDIUM finding before it was counted. Full machine output:
`rebuild/.runtime/v1-full-release-20260928/adversarial-pass-bf8f7b78/result.json`
(sha256 `016263a9…5447`); the interrupted-repair rounds: `inflight-repairs-result.json` (sha256 `df21aa3b…3e0f`).

State at the pass: CI run 36437449939 on `bf8f7b78` passed all six jobs; locally documents 454, ops 1,181 (2 skipped)
and core 2,290 (31 skipped) passed. Installed release `dedac162`, synthetic-only, unchanged.

## Default-path identity with the installed release — clean

Every new V1 capability is behind a default-off setting (`QUILLMD_WORD_ENGINE=legacy`; mapping assistance, WM
narrative, history context, generation batches and field relations off). Measured against `dedac162` under default
settings, the candidate is byte-identical on every checked path: provider request bodies (28 end-to-end cases on the
colonoscopy tab form, the WM IOV form, legacy Word and PDF forms, plus 1,510 fuzzed notes), `pricing_version`,
`maximum_cost` and holds, adopted answers, the review page's answer values, and every legacy Word/PDF export member.
All 40 development originals give identical legacy inspect/fill results.

The differences found are deliberate and recorded: request profile and evidence-contract keys in job/quote config;
new receipt facts (inference geography, stop reason); US-only inference settling at 1.1x when metered; split cache-write
pricing (unreachable on the default path); refusal of quotes whose price or mode changed; refusal of generation over
clinician decisions; unchanged notes saves no longer clearing answers; the recorded `&` WM review blocker.

**Promotion precondition found by this lens:** live-mode identity holds only if production's `QUILLMD_AI_MODEL` is
spelled exactly as one of the listed legacy models (the docs name `claude-sonnet-4-6`). Any other spelling is now
refused before a request is built (deny by default). Confirm with `configuration_status` before any promotion; do not
read the environment file.

## Findings, verified

| Lens | Result | Verified serious findings | Default path? |
|---|---|---|---|
| Default-path identity | nothing found | — | yes |
| D31 selection limits, round 3 | 12 findings | 6 HIGH, 3 MEDIUM (one downgraded) | no — v3 engine |
| D10 coded columns, round 3 | 6 findings | 1 HIGH, 2 MEDIUM | no — v3 engine |
| Contradiction veto, round 3 | 18 findings | 8 HIGH, 7 MEDIUM | no — field-relations flag |
| Money after the merges | 2 findings | 1 MEDIUM (batches flag), 1 downgraded to LOW | partly |
| Retention triggers vs flows | 3 findings | 1 MEDIUM (deadlock → 500) | **yes** |
| Migrations | 2 findings | 1 MEDIUM (0021 reverse deletes append-only rows), 1 downgraded to LOW (code rollback onto the new schema breaks upload) | **yes** (deploy/rollback) |

Every original finding, input and verifier reproduction is in `result.json`; nothing was relabelled to improve a count.

## What follows

- Five isolated repair streams run from `bf8f7b78`: retention lock order, migration and rollback safety, batch money,
  a structural fail-closed selection-cardinality rule for the v3 engine, and the D10 round-3 defects. Each repair is
  reproduced first, then refuted independently before it can join the candidate.
- **The contradiction veto (field-relations path) is not converging: 9, 6 and 8 HIGH in three rounds.** It stays off.
  No further investment until a bounded live Sonnet 5 qualification is possible; enabling the flag requires further
  refutation rounds and that qualification. Its open cases are recorded, not closed.
- Selection cardinality on the v3 engine is also not converging on word lists (7, 4, 6 HIGH); the next round replaces
  the approach with a structural rule that allows several answers only on explicit positive local evidence.
- None of this changes the Word compatibility gate (B-W1): still unmet, still measured only by historical proxies.
