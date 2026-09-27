# Payment round-5 recovery

2026-09-27. Local preparation on `v1/blockers`, recovered from clean
`cc68963848950700ad8d0265335107ef2dbf2c7e` in
`/opt/meddoc-pro/.worktrees/v1-blockers`. This is not live payment or deployment
evidence. No Stripe, Anthropic, Deepgram or other billable provider operation was
performed.

## Recovery and scope

The interrupted agent `a6ec2d2982b9f1af6` had inspected the findings and created
the isolated, migrated `r5_probe` database on the existing synthetic test
PostgreSQL container `v1-blockers-pg` (localhost port 55702). No source edits had
begun. Recovery confirmed its final probe transaction had rolled back: no probe
role or persistent replication settings remained. The probe database was retained.

The test configuration remains the existing protected
`.../scratchpad/v1/env/blockers-testenv.sh`; it was sourced without printing its
contents. Exactly one test process at a time used this agent's database. Evidence
and the scratch-only mutation harness remain at
`/tmp/claude-1000/-opt-meddoc-pro/64d93580-8414-4553-b17d-ed04b0550ae1/scratchpad/v1/blockers-repair5/astra-recovery/`.
The lead's earlier preflight permitted work with a disk warning.

R5-1, R5-3 and R5-4 were **test gaps in the recovered code**. In particular,
`apply_additional_debit` already checked and audited sandbox refusal before its
available-balance check. That behavior was preserved; no money movement logic
needed repair.

## Finished changes and claims for review

- R5-1: a synthetic live-mode top-up of $10 followed by a $1 provider settlement
  and reconciliation to $1.80 applies the additional $1.20 charge, leaving $7.30.
  The test prevents a guard from refusing all real-mode reconciliation.
- R5-3: a department paid by its organization, with sandbox-funded paid money and
  a wholly promotional hold, is refused by the worker before a provider request
  after switching to real mode. No usage/receipt is created; the hold is released
  and the refusal audited.
- R5-4: both initial and subsequent reconciliation attempts against a
  sandbox-funded wallet with no available money are audited. They remain pending
  and debit nothing.
- R5-2: the read-only admission check compares each required full trigger
  definition, enabled state, function schema/name/signature and pinned SHA256 of
  its installed body. It rejects unexpected row or statement triggers on the three guarded
  tables, except PostgreSQL's internal foreign-key constraint triggers. Those
  internal triggers were inspected; no additional Django row triggers were found.
- The same check requires `session_replication_role=origin` in the current
  connection and in the effective role/database catalog default. Precedence is
  role+database, role, database, then all roles/databases. A default for another
  role is ignored. A check made after `SET ROLE` still examines the active runtime
  role's defaults, since PostgreSQL does not apply them at `SET ROLE`.
- Output contains fixed labels and counts, not unexpected trigger names, function
  source, payment identifiers or values. The command remains in a `READ ONLY`
  transaction and does not call a provider. This is point-in-time evidence; an
  owner able to change both database and checker can defeat it.
- Documentation now states that an earlier `0020` can reverse/reapply only while
  it has no live records. If it has recorded live payments/events, its reverse
  refuses and a separately reviewed forward migration is required. No migration
  SQL or recorded payment history was changed here.

## Verification

The added 11-test R5 module first ran against the recovered implementation:
20 assertions failed across the catalog counterexamples; the three financial
cases passed. After the repair, the focused R5, payment evidence and real-mode
payments modules passed **70 tests**. The first focused run exposed one old
upgrade-test expectation: the stricter check also identifies its old body bytes
and extra obsolete trigger. That expectation was corrected; the original failed
run remains in evidence.

Ten bounded mutations were applied only to a separate `billing.py` copy:

| Mutation | Result |
|---|---|
| Refuse all real-mode reconciliations, including live-funded money | Killed |
| Omit the organization payer from worker wallet discovery | Killed |
| Check available balance before auditing sandbox refusal | Killed |
| Ignore the full trigger definition | Killed |
| Ignore the function schema | Killed |
| Ignore the function body hash | Killed |
| Ignore unexpected row triggers | Killed |
| Ignore the current replication mode | Killed |
| Ignore persistent replication defaults | Killed |
| Inspect the login identity rather than active runtime role after `SET ROLE` | Killed |

The complete R5 module passed against the unmutated copy before these probes.
Every mutation asserted application and failed a meaningful assertion; every
restore checked SHA256. The worktree source was never mutated by that harness.
Billing source SHA256 for those ten mutations and the full core run:
`130b4a666d1effe0f15d6e4de2a7898234a7a7eb097b3a0607778a2b4f461f85`.
All five pinned function hashes were also independently compared with the exact
string constants in migration source and matched.

The one required `manage.py test core.tests --noinput` run completed with exit 0:
**1,328 tests in 458.312 seconds, nine skips**. Its log is retained as
`payment-r5-evidence-20260927/core-suite.txt`. It tested the source hash above,
before the independent statement-trigger finding below; it was not rerun.

The independent Word reviewer then demonstrated an unexpected `AFTER INSERT FOR
EACH STATEMENT` security-definer trigger that temporarily sets replication to
`replica`, changes a sandbox payment's `livemode` to true, and restores `origin`.
The prior check returned no problems. Both this author and the lead independently
reproduced that result in fully rolled-back synthetic schemas. The first local
copy attempt failed before the probe ran; that failed attempt is retained too.

The finished check also rejects unexpected statement triggers. The new regression
test failed on the prior code for all six table/timing combinations, then passed
on the repair. The three focused modules now pass **71 tests in 13.997 seconds**.
A separate scratch-only mutation removing statement-trigger detection was killed
by those six assertions, and its restore and unchanged worktree hash were checked.
The exact transactional exploit now reports
`unexpected_statement_triggers:core_payment` before and after the deliberate SQL
insert. It still demonstrates that a privileged installed hook can relabel a row;
the repaired admission checker refuses that database, rather than claiming to
prevent an arbitrary owner's SQL. All probe objects were rolled back.

Billing source SHA256 for the statement repair and mutation:
`e051850e39ef2d0096eadd9151c47e80e58a754c2b7e1405d43396416f119987`.
The ten earlier mutation proofs are reused for unchanged checks; only the added
statement-trigger check received a new mutation. Every evidence file and its hash
is listed in `payment-r5-evidence-20260927/manifest.json`.

The final diagnostic sentence was then clarified to name both row and statement
triggers. Its focused six-case statement-trigger regression passed again (one
test, 0.088 seconds); this wording-only source hash is
`b0d580ec55fb0c7e56552b88b74a9ffc05c0a2b45eae01832ed9893c9fd20995`.

The independent reviewer repeated the original transactional probe against the
statement repair and confirmed the refusal before the insert. The finding is
closed; no additional demonstrated finding remained in that bounded review.
Its retained log is `payment-statement-repair-verified.log` in the evidence folder.

## Deployment and next action

No push, merge, activation, live database write, service restart, lock clearing,
provider call, email or purchase occurred. The installed application remains a
separate identity that this branch does not prove or change. The new checks are
not evidence of live Stripe acceptance or production runtime-role configuration.

Next: the lead can review and integrate this completed local repair into its exact candidate.
Keep all prior payment records, account agreements, spending grants, reservations
and deployment gates. Any live-payment qualification needs the existing eligible
authority and actual production account configuration.
