# Residuals R-A and R-B — evidenced assessment (2026-09-29)

The final default-path refutation on `d9fa3249` (`candidate-adversarial-pass-20260928.md`, "Final default-path
refutation") left two recorded residuals that its lock-order lens called "no ordinary trigger found":

- **R-A** — two different still-valid invitations for one not-yet-registered address, accepted at the same instant,
  answer HTTP 500 (an `IntegrityError` on the account insert).
- **R-B** — `core.jobs.run_one` turns a `DatabaseError` raised from `settle()` into reconciliation.

The owner asked for an evidenced assessment rather than a dismissal. This document is that assessment, on candidate
`8e3dcfd0` (`fix/v1-residuals`). **Outcome: R-A is reproduced deterministically and repaired; R-B is safe, and no
ordinary trigger was found by enumeration or by a two-party interleaving search over every lock-statement prefix; the administrator's
resolution of R-B's state had a LOW accounting defect, repaired.**

Environment: the QA PostgreSQL 16.15 at `127.0.0.1:55731` (`read committed`, `deadlock_timeout` 1 s, no
`lock_timeout` or `statement_timeout`), a throwaway test database `quillmd_qa_resid_t1`, `python -B`, `TMPDIR=/tmp`, and
a `sitecustomize` that refuses every non-loopback socket; one test run at a time on that database. Providers, Stripe and
email were fakes; nothing left the host.
The installed application and its database were not touched. No environment file was read.

## Summary

| | Reproduced | Decision | Change | Proof |
|---|---|---|---|---|
| **R-A** invitation race | **Yes, deterministically** (barrier before the account insert): 4 of 4 races answered `[302, 500]`, `IntegrityError` on `core_user_username_key` — two department invitations, two clinic invitations, one of each, and two `/register/` submissions | The later request gets the answer the same request gets a moment later: 200, "this email already has an account, sign in", its invitation unused and still valid; one account; audit rows untouched | `invite_accept`, `clinic_invitations.accept`, `register` catch the `IntegrityError` only when the account now exists (`forms.account_created_meanwhile`); any other `IntegrityError` still raises | 7 tests (4 RED → GREEN), 8 of 8 repeated runs green, 4 of 4 mutants killed, restores verified by sha256 |
| **R-B** (1) safe? | Injected as real PostgreSQL errors at settle's first statement, after its money writes, at its last statement, at COMMIT, after COMMIT, and a killed connection | **Reconciliation is the safe outcome**: hold kept, nothing charged, receipt kept, nothing adopted or delivered, no retry | none | 5 tests green on the unmodified code; 2 of 2 mutants of the handler killed |
| **R-B** (2) ordinary trigger? | **No.** Lock/constraint enumeration below, and a two-party search over every lock-statement prefix of either side: 632 scenarios against 33 ordinary operations, of which the stale sweep's 13 were vacuous (it found no job to sweep and took no lock), so 619 scenarios over 32 operations exercised a lock interplay; plus 22 for a second settlement one worker cannot produce (not ordinary) and 16 for the positive control. 0 failures outside the control | Recorded as evidenced; no code change | none | `residuals-evidence-20260929/`; the positive control deadlocks exactly where predicted |
| **R-B** (3) resolution correct? | **Defect (LOW, admin-only accounting).** A receipt-backed job resolved as `release_no_cost` recorded "no provider cost evidenced" and no platform cost; `absorb_platform_failure` recorded the typed amount | The durable receipt is authoritative, as the batch resolution and the settled branch already treat it | `admin_resolve_job`: receipt branch | 2 tests RED → GREEN; 1 mutant killed |

## R-A — two invitations for one new address

### Reproduction

`core/tests/test_invitation_account_race.py`. Each request runs on its own thread and database connection; an
execute wrapper holds each at a `threading.Barrier(2)` immediately before its `INSERT INTO "core_user"`, so both have
passed `RegisterForm`'s unique-email check (it reads committed rows) and both are inside their transaction, holding
their own invitation's row lock, when the inserts are released together. PostgreSQL makes the later insert wait on the
unique index for the earlier transaction and raises `unique_violation` when it commits. The outcome therefore does not
depend on timing: exactly one request wins.

RED on `8e3dcfd0` (`ra-red`): every race answered `[302, 500]` with
`IntegrityError('duplicate key value violates unique constraint "core_user_username_key"')` — two department
invitations, two clinic invitations, one department and one clinic invitation, and two `/register/` submissions of one
address (open mode; real mode answers 404 there). The transaction of the 500 rolled back whole, so there was one
account and no orphaned row, as the lens recorded: the defect is the 500, and a 500 that says nothing about whether
the invitation was used.

How ordinary is it? The window runs from the loser's unique check to the winner's commit, and includes the winner's
password hashing (Argon2) and welcome credit; it was not timed here. The same person must hold two invitations for the same new
address (a department and a clinic invitation, or two departments) and submit both in that window — rare, but a
normal user action, not an attack. The same form double-submitted is already serialized by the invitation row lock
(the lens measured 404 for the second) and by `data-submit-once`.

### Decision

The sequential case is the specification. Accepting the second invitation after the first committed already answers
200 and shows "This email already has an account. Sign in to accept the invitation", because an unauthenticated form
may not attach an invitation to an existing account: that would let possession of a token substitute for the
account's password. So the concurrent loser gets the same handled answer, plus one sentence that says what happened:
"An account for this email address was created a moment ago. This invitation has not been used: sign in, then open it
again to accept it." Signing in and reopening the invitation joins the account the first acceptance created, through
the existing-account path. No second account can exist (three unique indexes). The loser's transaction rolled back
whole: nothing it wrote survives, and nothing anyone else wrote is touched (every pre-existing audit row id is still
present; only the winner's acceptance audit rows are added).

Rejected: joining the loser to the winner's account on the spot. It would attach a department to an account on the
strength of a second token without the account's password, and silently drop the password the loser typed.

### Change

- `core/forms.py`: `account_created_meanwhile(email)` and the two messages, next to `RegisterForm`, with the reasoning.
- `core/views.py` `invite_accept` and `core/clinic_invitations.py` `accept`: `try: with transaction.atomic(): … except
  IntegrityError:` — re-raised unless the request was creating an account (`existing` is None) **and** the account now
  exists; otherwise the message is added and the page renders as the sequential case does (the app's idiom: `patients`
  catches its unique-reference race the same way).
- `core/views.py` `register`: the same, with a form error "An account with this email address already exists."

### Proof

- GREEN (`ra-green`): 7 of 7. The three invitation races each assert: exactly one 302 and one 200 carrying the refusal;
  one account, verified, with two wallets and exactly one welcome ledger entry and `credit.welcome` audit; the winner's
  invitation accepted with one acceptance audit; the loser's invitation unused, with no acceptance audit, no
  organization, department or membership; every pre-existing audit row still present; then signing in and posting the
  loser's invitation joins the same account (one account, still one welcome entry). The registration race asserts one
  account, one verification, one `account.register` audit and one verification email.
- Narrowness: an unrelated `IntegrityError` on the new-account path (injected at `welcome_credit`, or at the
  `account.register` audit) still answers 500 with no account and the invitation unused.
- Stability (`ra-green-repeat`): the two race classes run 8 times in a row, 8 of 8 OK.
- Mutation (`ra-mutation`; each anchor asserted to occur once, application asserted, restore compared by sha256):

| Mutant | Killed by |
|---|---|
| RA-M1 `invite_accept` handler reduced to `raise` | two department invitations |
| RA-M2 clinic `accept` handler reduced to `raise` | two clinic invitations |
| RA-M3 `register` handler reduced to `raise` | two registrations |
| RA-M4 `account_created_meanwhile` always true (swallow every `IntegrityError`) | all three narrowness tests |

### Every other account-creation path

Account rows are created in exactly three views (`register`, `invite_accept`, `clinic_invitations.accept`) and two
management commands (`bootstrap_first_admin`, the seed commands; operator-run, not views). All three views are covered
above. The other `DatabaseError` shapes on the new-account path were checked by reading the lock sequence: the
transaction holds its invitation row, its own uncommitted rows, and at commit takes `FOR KEY SHARE` on the invitation's
department (department invitation) or only its own new rows (clinic invitation). No ordinary transaction holds a
department or organization `FOR UPDATE` (payer change and holds use `FOR NO KEY UPDATE`; see the R-B enumeration), so a
new-account acceptance can wait but cannot be in a cycle; it is not caught and would still be a 500 if the database
itself failed. The existing-account paths were already raced by the lens (about 600 acceptances, 0 errors) and by
`test_retention_flow_locks` (RF-R1). Verification (`verify`), recovery and verification resend create no account.

## R-B — a `DatabaseError` from `settle()`

### (1) Is reconciliation the safe outcome? Yes.

`run_one` runs the provider call, commits the durable `ProviderReceipt` in its own transaction, writes the result file,
then calls `settle()` (one outermost transaction) and only after it the adoption transaction. When `settle()` raises,
its transaction is rolled back whole, so `Usage` does not exist (`known=False`), the provider returned
(`unsent=False`), and a live job goes to `reconciliation` with "Provider completed, but settlement needs administrator
reconciliation; nothing is charged until it is resolved." No release, no absorption, no adoption: the hold stays on the
customer's balance until an administrator resolves the job, the platform absorbs the provider cost at that point, and
the stored output is not delivered (`deliverable()` is only a success or a user-declined success). The request key is
not freed, so the same request cannot be bought twice meanwhile, and the worker never retries it. The cost of this
safety is availability, not money: the document counts the held job as pending, so it cannot be regenerated until an
administrator resolves the job.

`core/tests/test_settlement_database_error.py` makes **the database** fail settlement (SQLSTATE 40P01 raised by the
server through `RAISE`, the error a deadlock victim receives; a real foreign-key violation for COMMIT):

| Where | Outcome asserted |
|---|---|
| settle's first statement (the job row lock) | `reconciliation`, "Provider completed …"; wallets, reservations (still `held`), ledger, usage and platform-cost counts and the document's answers, notes, status, revision and review state byte-identical to before settlement; receipt present; no usage, ledger or platform cost for the job; not deliverable; audit `job.reconciliation` with `billing=uncertain`; no `usage.settle`/`job.succeeded`; `audit_billing` passes and lists the job as unresolved and its receipt as unsettled; the provider is never called again |
| the usage insert, after the wallet updates, ledger debit and reservation updates of the same transaction | the same (the money writes rolled back with it) |
| its last statement (the `usage.settle` audit) | the same |
| COMMIT (a deferred foreign-key violation) | the same, `error_class=IntegrityError` |
| a transcription, at the usage insert | the same; the notes are not appended |
| after COMMIT (settlement committed, the error surfaced afterwards) | `failed` with `platform_failure:`, the charge reversed by absorption (wallets exactly as before the request), platform cost = the usage's cost, nothing adopted |
| the connection terminated mid-settlement (`pg_terminate_backend`), server reachable | Django closes the broken connection when its rollback fails and the handler reconnects: the same `reconciliation` outcome as above |
| the same, server unreachable for the handler's next query | the handler cannot read the usage table, so the exception leaves `run_one` (the worker exits; systemd `Restart=on-failure` restarts it) with the job `running` and everything untouched; the stale sweep then moves it to `reconciliation` with the hold kept |

All seven green on the unmodified settlement code (`rb-green`; the first connection-loss hypothesis — that the exception
always leaves `run_one` — was wrong and is recorded as two observed shapes). Mutants of the handler (`rb-mutation`):
treating a provider-completed settlement failure as "not processed" (hold released, RB-M2; 6 failures) and swallowing
the settlement error so the output is adopted (RB-M3; 7 failures, including the after-commit case, which would then
stay charged) are both killed, so the tests would catch the tempting wrong repairs.

### (2) Is there an ordinary trigger? None found.

**Enumeration.** `settle(J)` on the running job J of user U in department D of organization O, with holds on U's
promotional wallet P and its payer's paid wallet W, executes 11 lock-taking statements in one transaction:

| Step | settle takes | Other ordinary writers of those rows | Why no cycle or constraint failure |
|---|---|---|---|
| 1 | J `FOR UPDATE OF self` | `cancel` and `admin_resolve_job` (lock J first, then refuse a running job), `absorb_failed_job` (J first, refuses non-failed), `mark_stale` (the same single worker process, between jobs), `reconcile_usage` (needs J's usage row, which does not exist yet) | settle holds nothing when it waits here (fresh transaction), so a wait here cannot close a cycle |
| 2 | the preservation lock (`LOCK_KEY`) | every preserved clinical write (encounter, patient, template, department, job, code updates; encounter, hold and tombstone inserts), `reserve`/`release`/`settle`/`absorb_failed_job` of other jobs, holds, disposition, payer change | a holder would have to wait for J; every locker of a running job takes J before `LOCK_KEY` (step 1 list) |
| 3–4 | J's reservations and P, W `FOR UPDATE`, in wallet id order | `reserve`, `release`, `settle`, `absorb_failed_job` of other jobs (job → `LOCK_KEY` → wallets by pk); `welcome_credit` (account `NO KEY` → P; nothing after); `credit_payment`, `reconcile_refund` (payment → W; nothing after); `reconcile_usage`, `apply_pending_reconciliations` (job → row → W; nothing after) | no ordinary transaction takes `LOCK_KEY`, a job it does not already hold, or a lower-pk wallet after holding a wallet (the batch closeout locks child jobs after `release()`, but only under its batch row, and batches are off by default); every multi-wallet locker uses pk order |
| 5–9 | `UPDATE` P and W; `INSERT` ledger `usage:J:<wallet>` for each debited wallet; `UPDATE` both reservations | `CHECK wallet_never_overspent`; unique ledger key | the check holds by invariant: `reserved` equals the held reservations (every writer changes both under the wallet lock) and every debit other than settlement first checks `balance − reserved`; settlement subtracts at most each reservation from both. `usage:J:*` is written only by `settle(J)` under J's lock |
| 10 | `INSERT` usage | one per job | only `settle(J)`, under J's lock, after its existence check |
| — | `INSERT` platform cost when over the limit | one `absorbed_over_limit` per job | only `settle(J)`; the resolution's `absorbed_failure` is a different partial index and runs only on a job in reconciliation |
| 11 | `INSERT` audit `usage.settle` | — | no unique or trigger |
| COMMIT | deferred foreign-key checks: `FOR KEY SHARE` on J, P, W, U, D, O | `FOR UPDATE` on U: `admin_account`, `admin_revoke_sessions`, `admin_mfa_reset`, recovery completion, `verification_resend` (unverified accounts only), `bootstrap_first_admin` (command). D, O: nobody (payer change and holds use `FOR NO KEY UPDATE`; `UPDATE`s change no key) | none of the account lockers waits for `LOCK_KEY`, a job or a money row afterwards: settle can wait, never deadlock |

Other `DatabaseError` sources inside settle: numeric overflow needs a provider cost above about 6.7 × 10^11 USD (the
receipt insert fails first at 10^12) — a provider anomaly; serialization failures do not exist at `read committed`;
no lock or statement timeout is configured in the repository's database settings, service units or the QA server. The
refusals settle raises itself (`SandboxFundsRefused`, no held limit, precision) are `ValidationError`s and take the same
reconciliation branch. What remains is infrastructure: a lost connection, a restart, a full disk, an operator's
`pg_cancel_backend`, or a timeout an operator adds to the server. Those are exactly the cases (1) proves safe.

**Targeted concurrent reproduction.** `residuals-evidence-20260929/settle_interleavings.py`, run on the QA PostgreSQL.
The worker's settlement of J (holds on P and W, called as `run_one` calls it) is raced against one ordinary operation of
another actor on the same rows, each on its own thread and connection. Every lock-taking statement of either side is a
pause point: the paused side stops right after its k-th such statement holding everything so far, the other runs
until it finishes or waits for a lock (read from `pg_locks`), then the paused side resumes; k runs until the paused
side finishes without reaching it, in both directions. For two parties whose statements do not depend on timing, this
visits every prefix at which one side holds locks while the other runs, which is where any two-party cycle or
constraint conflict must appear. A failure is looked for everywhere it could hide: a `DatabaseError` raised by any
statement of either side even if caught later, an exception out of either side, an HTTP 5xx, the application's own
failure audits (`usage.reconciliation_apply_failed`, `usage.absorb_failed`), an error logged by a robust on-commit
callback, settlement not completed, any wallet of the scenario not equal to its ledger and held reservations, and the
server's own `pg_stat_database.deadlocks`.

**Result: 670 scenarios in 232.0 s: 632 for the 33 ordinary operations, 22 for a second settlement (not an ordinary operation: the worker is one process, so two settlements never run at once) and 16 for the control. Zero failures of any kind in the 654 scenarios outside the control**: no `DatabaseError` from any statement on either side, no exception, no HTTP 5xx, no failure audit, no logged error, no hang, every settlement completed and every wallet reconciled. The server's deadlock counter rose by exactly 2 during the run — the control's two. **What the 632 ordinary scenarios exercised:** 619 of them, over 32 operations, raced a lock-taking operation against settlement. The stale sweep's 13 did not: `mark_stale` selects only jobs that have been running for more than five minutes, J had just been started, so in every one of the 13 the sweep found nothing, executed no lock-taking statement and never met settlement. They are vacuous and are not evidence about the sweep. Settlement ran 11 lock-taking statements; in the pending-charge scenarios its thread also ran the on-commit application of the payer's pending charge (13 or 18 statements), which was raced the same way.

| Other operation | Scenarios | Other side waited | Answers | Failures |
|---|---|---|---|---|
| doctor requests a generation on another document (enqueue → `reserve`) | 26 | 16 | 302 | 0 |
| doctor requests a generation on the running document (refused: pending) | 17 | 0 | 302 | 0 |
| doctor cancels another queued job (`release`) | 24 | 19 | 302 | 0 |
| doctor cancels the running job (409) | 15 | 12 | 409 | 0 |
| administrator resolves another held job, no receipt (`release`) | 24 | 18 | 302 | 0 |
| administrator resolves another held job with a receipt (the new branch) | 25 | 19 | 302 | 0 |
| administrator resolves the running job (409) | 15 | 12 | 409 | 0 |
| worker absorbs another failed, settled job | 21 | 17 | returned | 0 |
| administrator cost reconciliation, additional charge (debits W) | 20 | 14 | 302 | 0 |
| administrator cost reconciliation, credit back | 20 | 14 | 302 | 0 |
| pending reconciliation charge applied (what a top-up runs after commit) | 27 | 23 | returned | 0 |
| Stripe webhook credits a top-up to W (`credit_payment`) | 20 | 14 | returned | 0 |
| Stripe webhook records a refund from W | 21 | 15 | returned | 0 |
| doctor starts a personal top-up checkout (Stripe patched) | 21 | 9 | 302 | 0 |
| the account accepts a department invitation (`welcome_credit`) | 21 | 12 | 302 | 0 |
| the account accepts a clinic invitation | 23 | 12 | 302 | 0 |
| administrator suspends the account (`User` FOR UPDATE) | 17 | 3 | 302 | 0 |
| administrator signs the account out everywhere | 17 | 3 | 302 | 0 |
| administrator resets the account's authenticator | 18 | 4 | 302 | 0 |
| the account completes password recovery (`User` FOR UPDATE) | 17 | 3 | 302 | 0 |
| the account signs in | 22 | 0 | 302 | 0 |
| the owner deactivates the account's membership | 17 | 0 | 302 | 0 |
| the owner creates a department | 18 | 0 | 302 | 0 |
| payer change on D (granted role; off in production) | 18 | 13 | 302 | 0 |
| doctor saves notes on another document (preservation lock) | 20 | 15 | 302 | 0 |
| doctor saves notes on the running document (409) | 15 | 0 | 409 | 0 |
| preservation hold on O | 17 | 13 | returned | 0 |
| preservation hold on D | 17 | 13 | returned | 0 |
| preservation hold on the patient | 17 | 13 | returned | 0 |
| preservation hold on the running document | 17 | 13 | returned | 0 |
| global preservation hold | 16 | 13 | returned | 0 |
| second custodian releases a hold | 16 | 13 | returned | 0 |
| the stale sweep — **vacuous**: no job had run for five minutes, so it found nothing and took no lock (0 lock-taking statements in all 13) | 13 | 0 | returned | 0 |
| **all 33 ordinary operations** | **632** (619 excluding the vacuous stale sweep) | | | **0** |
| a second settlement for the same payer (not ordinary: one worker) | 22 | 18 | returned | 0 |
| **all scenarios outside the control** | **654** | | | **0** |

**Positive control.** A synthetic transaction that locks W and then the preservation lock — the order the global lock
order forbids — must deadlock with settlement, and did, in exactly the two predicted interleavings (2 of its 16 scenarios, SQLSTATE 40P01, both counted by the server): with settlement paused holding J and the preservation lock, the control took W and waited for the preservation lock, and settlement's wallet lock closed the cycle (the control was the victim); with the control paused holding W, settlement took J and the preservation lock and waited for W, and the control's preservation lock closed it (**settlement was the victim — this is what R-B looks like when it happens**). The instrument sees the failure class it is looking for, and no ordinary operation has that shape.

Held by the search, beyond the zero: several operations **waited** for the paused settlement (and settlement for them)
and completed after it — generation requests (the reservation), cancellation and resolution of other jobs, absorption,
cost reconciliation, pending charges, top-up and refund webhooks, invitation acceptance (the welcome credit), the
account screens, recovery, the payer change, notes saves and every hold scope — which is the lock order doing its job.

### (3) Is the administrator's resolution correct for this state? It was not quite; repaired.

The customer side was already right: `admin_resolve_job` releases the holds, frees the request key, charges nothing,
and the output is never delivered. But R-B's state is a job with a durable `ProviderReceipt` and no `Usage` row: QuillMD
already holds the provider's own metering of a completed request. The resolution ignored it:

- `release_no_cost` recorded `job.error` "Resolved by administrator: no provider cost evidenced." and **no platform
  cost**, contradicting the append-only receipt; `audit_billing` still passed (only batch parts are checked for a
  receipt accounted for), so the platform-cost totals silently understated what QuillMD paid.
- `absorb_platform_failure` recorded whatever amount was typed (asserted with 0.05 against a receipt of 0.1).

The batch resolution (`batch_jobs.resolve_view`) and this view's own settled branch ("whatever the form carried")
already treat the durable record as authoritative, so this is a gap in one branch, not a policy question. Severity LOW:
administrator-only, never a customer charge or a clinical effect, but a false statement in an append-only record.

Repair (`core/views.py` `admin_resolve_job`): when the job is neither settled nor synthetic and a non-simulated receipt
exists, the resolution records `PlatformCost(kind='absorbed_failure', amount=receipt.actual_cost,
evidence_reference='receipt:<id> <note>')` whatever the form carried, and says so in `job.error`. Uncertain jobs without
a receipt (the existing `test_billing_policy` resolution tests) are unchanged. `docs/rebuild/cost-definition.md` states
the rule. Tests (`ResolvingASettlementHeldByADatabaseError`): both outcomes, after a real settle-time database error,
assert holds released, wallets exactly as before the request, no usage or ledger movement, document untouched, not
deliverable, platform cost = the receipt's cost with `receipt:<id>` evidence, `audit_billing` passing with nothing
unresolved. RED on `8e3dcfd0` (`rb-red-resolution`, taken when the test file held its first four tests:
`PlatformCost.DoesNotExist`; `0.05 != 0.1`), GREEN after; mutant
RB-M1 (the receipt ignored again) killed by both.

## Test runs

| Run | Result |
|---|---|
| `core.tests.test_invitation_account_race` | 7 of 7 (RED first: 4 failures on `8e3dcfd0`) |
| `core.tests.test_settlement_database_error` | 7 of 7 (RED first: the 2 resolution tests on `8e3dcfd0`) |
| `test_v1_invite_only`, `test_retention_flow_locks`, `test_worker_financial_reliability`, before any change | 63 of 63 |
| the interleaving search (`settle_interleavings`) | OK: 670 scenarios (632 ordinary, 13 of them vacuous; 22 second settlement; 16 control), control deadlocked as predicted, 0 failures outside the control |
| **`core.tests`, the whole core suite, after the changes** (29 min 43 s, one run) | 2,381 run, 31 skipped, **1 failure**: `test_wm_narrative.ReviewCost.test_round_13_a_whole_leg_unexamined_is_read_once_per_sentence`, a wall-clock bound (5.12 s against 5.0 s) on WM narrative computation this change does not touch, on a shared host under load; it passed 3 of 3 isolated re-runs (whole test 4.56–4.94 s). Recorded as a pre-existing tight timing bound, not a result of this change (`core-suite.txt`) |
| `manage.py check` | no issues |

## Remaining limits

- **Three or more parties** are not enumerated by the interleaving search; the lens's randomized stress (five runs,
  mixed doctors, worker, administrators and webhooks) covered mixes, with 0 deadlocks.
- **The stale sweep was not raced against settlement.** Its 13 scenarios are vacuous (the sweep found no job running for
  five minutes). What keeps it from meeting settlement is structural, not searched: the worker runs `mark_stale` and
  `run_one` in one process, one after the other. The second settlement's 22 scenarios are likewise not an ordinary
  operation. The ordinary evidence is 619 scenarios over 32 operations.
- **Operations not in the search**: voice uploads (their `reserve()` is the generation request's), disposition
  execution (refuses any document with a job, so it cannot touch a running job's rows), generation batches and mapping
  jobs (default-off flags; separate settlement callers), and the production server's own configuration, which this
  session may not read. If an operator ever sets `lock_timeout` or `statement_timeout` on the production database, an
  ordinary lock wait becomes a `DatabaseError`: settlement would then reach R-B under contention — safely, by (1).
- **R-B remains reachable by infrastructure**, by design: reconciliation is the conservative answer, and resolution is
  now consistent with the receipt. The console form still offers both outcomes for a receipt-backed job; the typed
  amount is ignored for it and `job.error` says which evidence was used. The screen copy was not changed.
- **R-A**: a database failure other than the unique race (a lost connection, an operator cancel) on the account-creation
  path is still a 500; no ordinary trigger was found by reading its lock sequence. `/register/` exists only in open
  (synthetic) mode.

## Evidence

`docs/rebuild/v1/residuals-evidence-20260929/`: the interleaving search (`settle_interleavings.py`), its summary
(`settle-interleavings-summary.json`), every scenario row (`settle-interleavings-rows.json`) and its run
(`settle-interleavings-run.txt`); the RED and GREEN test transcripts (`ra-red`, `ra-green`, `ra-green-repeat`,
`rb-red-resolution`, `rb-green`), the mutation runs (`ra-mutation`, `rb-mutation`) and the core suite (`core-suite.txt`).
To rerun the search: the Django test runner with this directory on `PYTHONPATH`, label `settle_interleavings`,
`RESID_EXPLORER_OUTPUT=<file>`, against a throwaway database (about four minutes). Tests: `rebuild/core/tests/test_invitation_account_race.py`,
`rebuild/core/tests/test_settlement_database_error.py`.
