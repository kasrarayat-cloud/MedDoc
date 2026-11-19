# CPT Studio Gemini migration: the usage ledger

This ledger continues from the recorded history (DECISIONS D183, the owner's funding authority of 2026-11-12). Nothing in
it is credited back or reset. An estimate is labelled as one, and an unknown stays unknown.

**Prices** (the trial's pricing record, read 2026-11-09; Standard tier):

| Period | Input (per 1M tokens) | Output (per 1M tokens, thinking included) |
|---|---|---|
| Through 2026-11-30 | $2 | $10 |
| From 2026-12-01 | $4 | $20 |

Unless a row says otherwise, a cost is an ESTIMATE: the provider-reported token usage priced at these rates. Google's bill
is the authority.

## 1. Gemini sends recorded by the harness ledgers (history, as recorded)

| Batch | When | Requests | Outcomes | Estimated USD | Source |
|---|---|---|---|---|---|
| trial, attempt 1 | 2026-11-09 05:49Z | 7 | 7 refused, 429 before billing; 0 billable tokens | 0 | gemini-trial/archive/attempt1-20261109T0549Z/ledger.jsonl |
| trial | 2026-11-09 | 14 | 7 refused (429); 7 answered | 0.1848 | gemini-trial/out/ledger.jsonl, eval/usage-cost.json (14,542 in, 15,573 out) |
| FRESH-1 probe | 2026-11-10 08:18Z | 1 | 1 answered | 0.0432 | fresh-out/probe/ledger.jsonl |
| FRESH-1 A, B, C | 2026-11-10 | 179 | 179 answered | 11.5494 | fresh-out/{A,B,C}/ledger.jsonl |
| FRESH-2 A, B, C | 2026-11-10 | 179 | 179 answered | 12.1686 | fresh2-out/{A,B,C}/ledger.jsonl |
| S17 cap probe | 2026-11-10 15:21Z | 1 | 1 answered | 0.0476 | s17/capprobe-152129/ledger.jsonl |
| **recorded total** | | **381** | **367 answered, 14 refused** | **23.99** | |

The frozen directories (fresh-frozen, fresh2-frozen) are byte copies of these ledgers and are not counted twice.

## 2. Gemini sends with no harness ledger (unknown, kept as unknown)

- **g1 run 1** (12 documents, test instance, 2026-11-10).
  - Usage was recorded only on the provider runs of its test database, which has since been removed.
  - Cost: unknown.
- **g1 runs 2 and 3** (2026-11-10, about 13:58Z).
  - Each interpreted 1 of 12 documents. Then 23 sends were refused by the project's monthly spending cap (429 with no
    quota detail; D39). Both runs are void.
  - The two interpreted sends: cost unknown.
  - The 23 refused sends: billable tokens unknown (presumed none; not verified).
- **The S17 test-instance walks** (walk-smoke1, walk-smoke2, walk-final1, walk-final1-gi10).
  - Their evidence files do not record whether they sent to Gemini, or at what cost.
  - Cost: unknown.
- **Month to date at the cap stop** (2026-11-10 13:56Z): about $26. That was the session's estimate at the time; Google's own
  figure is unknown.
- **The earlier cap, kept as history.**
  - The owner raised the cap to about $300 on 2026-11-11 (owner-cap-20261111-verbatim.md).
  - On 2026-11-12 the owner superseded it as a ceiling on the session's sends (owner-funding-20261112-verbatim.md).
  - The Google project's own spending cap remains the owner's setting.

## 3. Corti, Astra and Fable

- **History:** the migration's test walks recorded their usage on provider runs in test databases that have since been
  removed. It is not compiled here: unknown.
- **From 2026-11-12:** each run's provider-reported usage stays on its ProviderRun, the operator report sums it, and each walk
  batch appends its totals here.

## 4. Development agents

Claude subagents, counted in tokens as the workflow tool reports them. The session does not measure a dollar cost for
them; it depends on the account's plan.

| Session | Period | Workflow or agent tasks | Subagent tokens |
|---|---|---|---|
| 30a58364 | 2026-11-09 to 2026-11-11 | 56 | 196,006,525 |
| 68197eb1 | 2026-11-11 to 2026-11-12 06:55Z | 16 | 76,963,699 |

The lead sessions' own tokens are not included.

## 5. From 2026-11-12, appended per batch (D183)

Each batch's cost guard is about twice its modelled cost. A guard stops a runaway loop; it is not a ceiling on the work.

| When | Batch | Label | Requests (pass 1 / pass 2) | Provider-reported tokens (in / out) | Estimated USD | Guard | Outcome |
|---|---|---|---|---|---|---|---|

**Development agents from 2026-11-12:**

| When | Workflow | Subagent tokens |
|---|---|---|
| 2026-11-12 06:25Z- | wf_79871e65-763, build waves 1-2 | pending |
