# Sonnet 5 model check — PASSED (QA worker), 2026-09-29

Stage `model_check` of campaign `quillmd-v1-sonnet5-staged-40` (authority
`quillmd-v1-sonnet5-staged-40-call_9fkOp2kqbQ28e17HqXgHFlzk`), run once through `scripts/run-ruled-mutation.sh` with
the committed declaration (`01ff8c7d`, committed 2026-09-28T23:29:58Z; act 2026-09-29T00:56:43–00:57:04Z). Runner
`ops/sonnet5_qa.py` at `231183b3` (clean, detached worktree) on candidate code `8e3dcfd0`.

**What this proves: the candidate's real views and real worker function (`core.jobs.run_one`) in an isolated QA
process, with its own synthetic database and state directory.** It is QA-worker evidence. The installed release
`dedac162`, its worker, configuration and database were not touched, and nothing here is evidence about them.

## The single attempt

| row | declared | observed |
|---|---|---|
| model / profile | `claude-sonnet-5`, thinking disabled, effort medium, 8,000 output, 120 s | request body: model `claude-sonnet-5`, `max_tokens` 8000, `thinking {type: disabled}`, `output_config` {effort, format}; no temperature |
| pricing version | `configured-v1:8975b158…` | same (checked before admission) |
| admission | maximum × 1.1 fits $5.00 stage / $40 total | maximum $0.104896, bound $0.1153856; hold $0.157344 (= 1.5 × maximum) |
| served model | `claude-sonnet-5` | `claude-sonnet-5` |
| stop reason | `end_turn` | `end_turn`; content `["text"]` |
| output share | < 70% of 8,000 | 118 tokens (1.5%); thinking tokens 0 |
| geography | unset; `us` metered is a stop | `global` |
| provider ids | retained | request `req_011CfWpbvUpWa7eEj1zrJ4Kt`, message `msg_011CfWpbwtQsMKgMLksaWRXd` |
| provider cost (configured rates × reported usage) | — | 840 input × $2/M + 118 output × $10/M = **$0.00286** |
| settlement | 1.5 × actual, reservation settled | receipt and usage actual $0.00286; charged $0.00429; reservation `settled` |
| billing audit | clean | `all_checks_pass: true` |
| retained evidence | request capture, raw result, records, adopted vs reviewed answers, export, manifest | all present; the transcript and every retained file carry no key-shaped string |

## Raw model output, validator decision, review — kept separately

- **Raw model output:** for each field the exact quote from its own line (`History`, `Findings`, `Plan`), `conflict: false`.
- **Validator decision (adoption):** all three `supported`; each text equals the documented value; each evidence span
  lies on the question's own line and contains the answer.
- **Review:** saved unchanged, each answer marked reviewed by the synthetic QA doctor; finalized.
- **Authenticated export:** each answer cell's full text (all descendants) equals the reviewed answer, one paragraph,
  no hidden runs, content controls or nested tables; export sha256 equals the finalized record's `ab6570ff…`.

The stricter checks refutation round 2 found the runtime verdict could miss (evidence belonging to another question,
block wrappers in an answer cell, an unlistable directory in the leak scan) were applied by hand to the retained
evidence and all hold. The runtime check of the review page's own content is known to be vacuous (the page always
shows the notes); the review save, finalization and export are what prove that step.

## Campaign ledger after the check

| stage | limit | exposure | remaining | decision |
|---|---|---|---|---|
| model_check | $5.00 (≤ 10 requests) | $0.00286 (1 request) | $4.99714 | **passed** |
| mapping | $25.00 | $0 | $25.00 | may start (prerequisite met) |
| ordinary_notes | $10.00 | $0 | $10.00 | may start (prerequisite met) |
| **total** | **$40.00** | **$0.00286** | **$39.99714** | |

These are configured-rate figures over provider-reported usage. The provider's own charge is read by the owner from
the provider console and recorded separately.

## What it does not prove

Clinical usefulness beyond a three-line explicit note, mapping of real forms, ordinary-note behaviour, native Word
acceptance, the installed worker, or any agreement coverage. Those are the later stages and the external gates.
