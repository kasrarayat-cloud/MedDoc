# Evidence — WM narrative rounds 18–19 qualification and the offline campaign validation (PR #1287)

Preserved from the qualifying session's scratch on 2026-09-27 ~00:35Z, before any scratch cleanup.

**Location:** `/opt/meddoc-pro/rebuild/.runtime/wm-narrative-qualification-20260926/` — the operator's evidence store
(gitignored, directory 0700, files 0600, readable by no service account). 1,460 files, 29 MB.

**Integrity:** `SHA256SUMS` inside it lists every file; the copy was verified identical, file for file, to the scratch
source before this record was written. sha256 of `SHA256SUMS`:
`f493fac1ca21486027224797a3fdb116239be3bffd8260b5317ea9f2441db7ff`.

**What it holds** (everything synthetic; no provider request was made by any of it):

| path | what |
| --- | --- |
| `campaign/full7/`, `campaign/full8/` | the complete offline campaign validations on `11912b0c` and `72283bc5` (18 of 18 scenarios each; 323 checks on `72283bc5`): per scenario the ledger, captured requests, mock responses, replay files, replay manifest, scores, stage verdict and report, the synthetic database's exported records, and the mock's own log of what it received |
| `campaign/full1..6/`, `campaign/try1..3/` | `validation.json` summaries and logs of the earlier runs; their detailed files were shredded on 2026-09-26 (recorded in that session's report) |
| `findings/`, `fp/` | round 18's review findings and verdicts; round 19's focused-pass findings and verdicts |
| `mutresults*.json`, `mutbatch*.out`, `mutlogs/`, `mutants18.py`, `mutants19.py`, `mutrun.py`, `mutbatch.py` | the mutation proofs (round 18: 46 mutants; round 19: 22) and their harness |
| `perf/` | the interleaved fresh-process samples behind the 5 s guard's reconciliation |
| `fuzz20*.json`, `fuzz20.py` | the round-19 self-check's window fuzz (62,088 answers, 0 differences from `f01107aa`) |
| `runall*.txt`, `battery18*.txt`, `bench-*.txt`, `dead-*.txt`, `cost19.txt`, `suites*.txt`, `suite-*.log` | row-diffs against `f01107aa`, batteries, dead-end sweeps, cost shapes, full-suite logs |
| `declaration-stage1-DRAFT.md` | the Stage 1 declaration draft (uncommitted until the owner's authorization is recorded) |

Not copied: per-run transient state directories and commit-message drafts (their text is in git).
