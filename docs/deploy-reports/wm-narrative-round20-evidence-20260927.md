# Evidence — WM narrative round 20: the independent pass over round 19 and its repairs (PR #1287)

Preserved from the session's scratch on 2026-09-27 ~02:20Z, before any scratch cleanup.

**Location:** `/opt/meddoc-pro/rebuild/.runtime/wm-narrative-round20-20260927/` — the operator's evidence store
(gitignored, directory 0700, files 0600, readable by no service account). 1,469 files, 21 MB.

**Integrity:** `SHA256SUMS` inside it lists every other file and was verified against the copy before this record was
written. sha256 of `SHA256SUMS`: `e827230d161e8c0b5328059ac731a3a279c5522897ceabfcffae5284ff0118d5`.

The rounds 18–19 evidence stays where `wm-narrative-offline-validation-evidence-20260926.md` records it; re-verified
2026-09-27 01:36Z: its `SHA256SUMS` still hashes to `f493fac1…` and every listed file checks.

**What it holds** (everything synthetic; no provider request was made by any of it):

| path | what |
| --- | --- |
| `review/` | the three lenses' prompts and findings (R, P, C), and every verifier's verdict (`verdicts.json`: 17 confirmed, 1 refuted) |
| `lens-probes/reader-and-page/`, `lens-probes/runner/` | the lenses' and verifiers' own probes and outputs (per-run state directories and throwaway database credential files not copied) |
| `runs/r20/` | the author's reproductions (`r20probe.py`, the cases files, `repro20.txt`), the old-code runs of the new tests, the cost timings, the targeted and full suite logs (`suite-*.log`, `suites.txt`), the page test logs, and the offline campaign validation `campaign-full9/` (22 of 22 scenarios, 356 checks, on `2e7453f3` — its ledgers, captured requests, responses, replays, manifests, scores, verdicts and exported records) |
| `runs/runall66.txt` | the row-for-row harness against `f01107aa` |
| `mutation/` | the 27 round-20 mutants, their driver, per-mutant logs and `mutresults-mutants20.json` |

Not copied: per-run transient state directories (the blank template the synthetic campaigns upload), throwaway
database credential files, and commit-message drafts (their text is in git).
