# Backup alerts: interrupted round 3 recovered

2026-09-27. **Prepared locally; not installed or merged.** This report closes the
unfinished regression pins and documentation from the interrupted alert repair.
It does not establish delivered alerts, a current backup, admission to offsite
storage, outside-host outage detection, or real-patient readiness.

## Recovered state and retained evidence

- Worktree: `/opt/meddoc-pro/.worktrees/v1-ops`; branch: `v1/alert-escalation`.
- Recovered HEAD: `8a3a5bb20885d23562d717262911b02e296a6275`.
- The only unfinished tracked changes were `rebuild/ops/test_backup_alerts.py`
  and `docs/rebuild/operational-alerts.md`. Both were preserved and inspected.
- The previous agent was `a5bd35097110dd210`, in the execution log at
  `/home/claude/.claude/projects/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/subagents/agent-a5bd35097110dd210.jsonl`.
- Its scratch remains at
  `/tmp/claude-1000/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/scratchpad/v1/repair-alerts3/`.
  This continuation's logs and separate mutation copy are under `astra-recovery/`.
- The original mutation process had completed before recovery. No alert writer,
  mutation process or alert test was still running. The original source and its
  scratch copy matched for all three mutated implementation files; no restoration
  or interrupted provider operation needed repetition.
- The lead's preflight report was
  `docs/preflight-reports/preflight-20260927T161904Z.md` (disk warning; work permitted).

Raw completed mutation results, the new focused mutation result, the operations
suite output and exact skip explanations are retained in
[alerts-round3-evidence-20260927](alerts-round3-evidence-20260927/manifest.json).
That manifest records original locations and SHA256 hashes. The original logs,
including the surviving mutation, were retained without rewriting them.

## Repairs and verification

These implementation commits already existed on the recovered branch:

| Finding | Reproduction and completed repair |
|---|---|
| R3-1: a healthy restart notice suppressed a later backup failure | RED `20e6fa17`; repair `9724d444` compares severity and always reports the backup condition. |
| R3-2: a dead check's pending notice was hidden while another check ran | RED `f8dc3ed0`; repair `fa128aea` locks records currently in flight, retains uncertainty after process death, and publishes staleness/unreadable-state context to the admin page. |
| R3-3: quiet conditions lost the required restart notice | Regression pin `145a70a4`. |
| R3-4: rollback/forward history could suppress a later escalation | Regression pin `eac8d28b` checks the previous release's notice time. |
| R3-5: FIFO lock/status files could block status reads | RED `7c06dc4c`; repair `644bedfd`; no-follow/nonblocking regression pins `8a3a5bb2`. |
| R3-6 and remaining guards | Recovered tests pin malformed marker keys/reasons, invalid versus missing records, unexpected I/O labels, unsafe locks, failed-write cleanup, same-size concurrent writes, final-write mark release, and heartbeat severity. |

The original final mutation batch had **28 killed and 1 surviving out of 29**.
The survivor, R1f, removed the second severity check after heartbeat evidence
raised the condition. Claude then extended the heartbeat test in the worktree,
after the original scratch snapshot, and reached its usage limit. This explains
why the completed old batch still reported that survivor.

This continuation reran **only R1f** with that last extension on a new scratch
copy: the unmodified focused test passed; the mutation failed because it held
`external_monitor_unconfirmed` behind a prior healthy restart notice. Application
was asserted and restoration was checked with SHA256. Implementation hash before
and after: `138bd702d4b6cc0f096ea78be09f2fcee87a409343d99fb18ff1a5b9e8c34aef`.
The original 28 kills remain valid; the separate repaired result closes R1f.

The required operations suite was then run once:

```text
.venv/bin/python -B -m unittest discover -s ops -p 'test_*.py'
Ran 1018 tests in 54.247s
OK (skipped=2)
```

**1016 passed; 2 skipped.** The two skips are the pre-existing multicolumn Word
candidate scope comparisons: that candidate is already merged, so those checks
do not reinterpret its old scope against this later branch. Their exact reasons
were confirmed with those two checks only. They are not Word compatibility
acceptance and provide no custom-form success claim.

The unchanged publisher/admin page `PublishedOperationsCarryTheirStaleness`
2-test evidence was reused from the original batch: four separate mutations
removing either published field or either visible message were killed. Their
unmutated baselines each passed. These are database-free `SimpleTestCase` checks.
The database-backed console/publication suite was not rerun; its test database
was stopped and no service was started.

`git diff --check` passed and the configured pre-commit/pre-push hooks were present,
executable and parsed. The operational documentation now describes the measured
restart crash window through the relevant fsyncs and its residual behavior.
Tests used synthetic fixtures and mocked email/provider/host mutation boundaries.
The installer failure-shaped output in the suite log comes from the existing
mocked installer test; it is not an installation receipt or actual host action.

## Exact next action and remaining operational gates

The containing commit is the continuation tip; obtain its full SHA with
`git log -1 --format=%H -- docs/rebuild/v1/alerts-round3-recovery-20260927.md`.
No push, merge, deployment, activation, live lock change, provider request,
notification, purchase, or credential change occurred in this continuation.
No test or mutation process remains pending.

Next, the lead should review this completed branch together with the actual
installed operations revision and existing declaration. Any integration and
installation must follow the repository's normal gates and preserve all current
state/receipts. Do not infer the installed revision from this branch's HEAD, clear
an unexplained lock, retry an uncertain send, or run the old single-use alert test.

Still required independently:

- Reconcile the actual installed backup-alert, publisher and offsite failures
  against current journals, retained attempts and the exact installed sources.
  This local test result neither resolves nor reclassifies those live failures.
- Preserve the existing accepted email and its receipt. Establish actual provider
  delivery and human inbox confirmation using eligible evidence/access. The older
  runbook records a delivery lookup refused with HTTP 401; that historical fact
  does not authorize another send or establish current delivery.
- Establish outside-host missing-heartbeat detection and delivery on an authorized
  endpoint, using the isolated-check qualification described in the runbook.
- Reconcile current backup-admission policy, account-audit observations, ticket
  spend and reservations before any offsite traffic. A fresh authenticated
  observation or a separately reviewed covered production backup design is needed;
  extending an old 24-hour lease is not renewal. Previously consumed/expired
  tickets and reservations remain preserved and provide no new budget.
- Complete these operational gates on the approved production target before
  admitting real patient data. Existing historical restore evidence can be reused
  where still applicable; a healthy status row is not a completed backup.
