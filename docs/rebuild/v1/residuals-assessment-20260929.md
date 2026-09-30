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

## Second refutation (RR2): five findings reproduced and repaired

A second refutation of this assessment and of its repairs (RS-1..RS-5, RA-LOW-1 on `d5367521`) verified five findings.
Each was first reproduced as a failing test on `d5367521` (tests added, no application change), then repaired in the
app's idiom, then mutation-proved. Environment as above, except the throwaway test database `quillmd_qa_resid3_t1` and
a `sitecustomize` that refuses every non-loopback connection and name lookup; providers, Stripe and email were fakes
(the mapping provider client is a mock; invitation delivery is replaced). The installed application, its database and
the campaign's runtime state were not touched. No environment file was read.

| | Severity | RED on `d5367521` | Change | Proof |
|---|---|---|---|---|
| **RR2-ACC-1** address longer than the username column | MEDIUM | 151–254 characters passed every form; `/register/` and both acceptances answered 500, `bootstrap_first_admin` raised `DataError` (varchar(150)); the department door issued an invitation at 151; 255–320 passed both invitation forms and department issuance raised `DataError` (varchar(254)) (the clinic door at 300 was not measured: that failure aborted the test's transaction) | `forms.account_email` refuses an address longer than every column it is written to (150, derived from the model fields): a form error, no account, the invitation row unchanged | 4 tests RED → GREEN, 2 boundary controls (150 still issued, accepted, registered, bootstrapped); 3 mutants killed |
| **RR2-M1** mapping handler overwrote a committed adoption | MEDIUM | adoption COMMIT answer lost after it committed: `('failed', 'platform_failure: …')`, charge reversed, new mapping version left on the template; the handler's own first statement failing raised `OperationalError` out of `run_one`, job left `running` | `mapping_jobs.end_failed_job`: `core.jobs.end_failed_job`'s guard (decided and written under the job row lock; a committed outcome never overwritten; an in-doubt settlement COMMIT held with its key); the handler's own `DatabaseError` holds the job, as `core.jobs.run_one` | 4 tests RED → GREEN (2 of them RED only on the message, below), 2 controls; 6 mutants killed |
| **RR2-ACC-2** quoted local part | LOW | `"sam"@…` and `"s\am"@…` each created another account beside `sam@…` at `/register/`, and `"sam"@…` one at a department invitation (the clinic subtest then met that account, so the clinic door was not measured on its own); both invitation forms accepted it and the department door issued it; `bootstrap_first_admin` created it | `forms.account_email` refuses a quoted local part ("Enter the email address without quotation marks.") | 5 tests RED → GREEN; 1 mutant killed |
| **RR2-ACC-3** one invitation accepted twice at once | LOW | the second request answered a bare 404 (department `[404, 200]`, clinic `[200, 404]`) | under the invitation's row lock, an already accepted invitation answers with the sign-in page and "This invitation has already been accepted: the account for this email address exists. Sign in to continue."; it wrote nothing | 2 tests RED → GREEN; 2 mutants killed |
| **RR2-L1** charged mapping output not downloadable | LOW | its requester got 404 from `/jobs/<id>/result/` | `job_result` scopes a mapping job by its template's department, under the generation rule (an active member of the job's department; charged outcomes only); the mapping page links it | 1 test RED → GREEN, 1 control; 4 mutants killed |

### RR2-ACC-1 — an address longer than the account columns

The address is the account's username (`register`, `invite_accept` and `clinic_invitations.accept` set
`username = email`), a 150-character column; `User.email`, `Invitation.email` and `ClinicInvitation.email` hold 254,
and Django's form `EmailField` admits 320. `account_email` — the one rule every door that chooses an address already
applies (registration and both acceptances through `RegisterForm`, both issuances, `bootstrap_first_admin`) — now
refuses an address longer than `ACCOUNT_EMAIL_MAX_LENGTH`, the minimum of those four model fields (150), with "Enter an
email address of at most 150 characters." Measured after stripping, as stored.

Tests (`test_account_email_rule.AccountEmailBounds`, `FirstAdministratorEmailRule`): every form at 151, 254, 300 and 320
(RegisterForm beyond 254 is refused by Django's own `max_length` first); `/register/` at 151 and 254 answers 200 with the
form error and no account; an invitation stored before the bound (department and clinic, 151 and 254) answers 200 with
the form error, creates no account or organization, and its row is unchanged field for field; issuance through `/team/`
and `/console/clinic-invitations/` at 151 and 300 answers 200 with the form error and stores no invitation; the first
administrator's long address is the command's own `first_admin_email` refusal, not a `DataError`. Controls: exactly 150
characters is issued by both doors, accepted into an account whose username is 150 characters, registered, and
bootstrapped. Mutants: no bound (M1), the bound taken from the email column, 254 (M2), off by one (M3, killed by the
controls).

### RR2-M1 — the mapping handler decides under the job row lock

`core.mapping_jobs.run_one`'s handler read `Usage.exists()` without the job's lock and wrote the job afterwards. When the
adoption's COMMIT answer is lost after it committed, the adoption transaction still holds the job row (its UPDATE) until
it ends; the unlocked read saw the committed usage, decided "known, not declined", and its later UPDATE waited for the
row and then overwrote `succeeded` with `failed`/`platform_failure`, and `absorb_failed_job` reversed the charge of a
mapping version the template now carries.

Reproduced with the same deterministic harness as RS-1 (`test_settlement_outcome_unknown.CommitAnswerLost`: the COMMIT
goes out, its answer never arrives, the transaction stays open on its server connection holding its locks until another
backend waits for one of them, then is committed or rolled back), in live mapping mode with a mocked provider client:
`test_mapping_outcome_unknown.py`.

The repair is `core.jobs.end_failed_job`'s guard, as the finding asked, in `mapping_jobs.end_failed_job`: the handler
first takes the job's row lock (which waits for an in-flight transaction), returns with `job.error_after_commit` audited
when a committed transaction already ended the job, and otherwise decides from the committed usage and writes the state,
the release or absorption and the `mapping.<state>` audit in one transaction. The connection that carries settlement's
COMMIT is kept, and an in-doubt settlement (`jobs.commit_in_doubt`) asserts nothing: `reconciliation` with "The
settlement outcome of this request is unknown; …", its request key kept, nothing released or absorbed. As in
`core.jobs.run_one`, the handler first repairs a connection broken outside a transaction, and a `DatabaseError` from the
handler's own reads or writes holds the job ("The outcome of this request could not be recorded; …") instead of leaving
it `running`. Error strings, the absorption-failure hold (RS-3) and the audit actions are unchanged.

| Test | RED on `d5367521` | GREEN |
|---|---|---|
| adoption committed, answer lost | `('failed', 'platform_failure: Mapping output could not be adopted.')`, charge reversed | `succeeded`, deliverable, 2 mapping versions, usage debits standing, no absorption or platform cost, `mapping.review_ready` kept, `job.error_after_commit` (`state=succeeded`, `OperationalError`) |
| adoption did not commit, answer lost (control) | pass | `failed`/`platform_failure:`, key freed, 1 version, wallets as before the request, platform cost = usage cost |
| settlement committed, answer lost | **RED at its first assertion, on the message**: already `reconciliation` with its key, reading "Provider outcome or settlement is uncertain; reconcile before retrying."; its later assertions were not reached on `d5367521` | `reconciliation`, "The settlement outcome of this request is unknown; …", key kept, holds settled, nothing absorbed, never retried, the same request not bought twice |
| settlement did not commit, answer lost | **RED at its first assertion, on the message**, as above | the same, holds still held, no usage |
| the handler's first statement loses the connection | `OperationalError` out of `run_one`, job `running` | `reconciliation`, "The outcome of this request could not be recorded; …", key kept, charge left for the administrator |
| unusable output, nothing lost (control) | pass | `failed`/`platform_failure:`, absorbed, `mapping.failed` |

The settlement rows are recorded as what they are: on `d5367521` the unlocked read preceded the in-flight commit, so the
mapping handler already held an in-doubt settlement (by luck of its wording, not by rule). They pin the RS-1 rule on the
mapping path: a handler that merely took the lock would read a landed settlement as known and absorb it (mutants M9 and
M10 do exactly that and are killed). Mutants: no state check under the lock (M7), no lock (M8), in-doubt branch removed
(M9), doubt never computed (M10), doubt never cleared after settlement, so a lost adoption answer is read as a settlement
(M11), handler failure re-raised (M12).

### RR2-ACC-2 — a quoted local part

Django's `EmailValidator` accepts a quoted local part (`"sam"@…`, with `\`-escapes inside the quotes). It names the
mailbox `sam@…` (RFC 5321) and is a different string to the unique index, the `iexact` lookup and every view comparison.
`account_email` now refuses it: a `"` can occur only in a quoted local part (the validator admits it nowhere else). It is
refused, not unquoted, for the rule's existing reason: nothing is rewritten into a different address, because the stored
address is where the account's mail goes. Tests (`QuotedLocalPart`, the first-administrator test): `/register/` beside an
existing `sam@…` (three spellings), both acceptances of an invitation stored with a quoted address (no account, the row
unchanged), both forms, both issuance views, and `bootstrap_first_admin`. Mutant M4 (the check removed) killed.

### RR2-ACC-3 — one invitation accepted twice at once

Two submissions of the same invitation (two tabs, or a double submit that `data-submit-once` did not stop) both pass the
unlocked lookup and the form (no account yet) and wait for the invitation's row lock; the first accepts it and creates
the account, and the second found `accepted_at` set and raised `Http404`. Reproduced deterministically:
`test_invitation_account_race.OneInvitationAcceptedTwiceAtOnce` holds both requests at a barrier right before the row
lock. Now, under the lock, an accepted invitation answers with a redirect to the sign-in page and the message; the
request wrote nothing. Expired or revoked (clinic) still answer 404. Asserted: both requests end on `/login/`, exactly one
carries the message, one account (one welcome entry and one `credit.welcome`), one membership (clinic: one organization),
one acceptance audit. Mutants M5 and M6 (each view back to `Http404`) killed.

### RR2-L1 — a charged mapping job's stored output

`job_result` filtered on `encounter__department`, which a mapping job (no encounter) never matches. Decision: the same
access rule as a generation's output, not a new one: an active member of the job's department (for a mapping job, its
template's department), charged outcomes only (`jobs.deliverable`: a success or a `not_adopted` decline), integrity
checked, `job.result_download` audited with the job's department. The mapping assistance page links it for a deliverable
operation ("Download provider result"). The mapping page itself stays limited to owners, clinicians and managers; the
download follows the generation rule because the output concerns a blank form (no patient data) and the template, its
original and every mapping version are already readable by every member of the department. Tests: the requester
downloads (sha256 equal to the stored result), the audit row, the page link, a department colleague (employee) 200, a
member of a sibling department 404, a deactivated membership 404; control: an absorbed (uncharged) mapping failure's
stored output is 404 and not linked. Mutants: the old query (M13), any department (M14), uncharged output delivered
(M15), no link (M16).

### Test runs (RR2)

| Run | Result |
|---|---|
| RED (`rr2-red.txt`): the new tests on `d5367521` with no application change | 21 new tests: 16 fail as described (27 failures and 3 errors counting subtests), the 5 controls pass; the RR2-L1 test re-run after moving its download assertion first: `404 != 200` |
| GREEN (`rr2-green.txt`): `test_money_closeout`, `test_account_email_rule`, `test_invitation_account_race`, `test_mapping_outcome_unknown`, `test_mapping_assistance` | 96 of 96 |
| Mutation (`rr2_mutate.py`, `rr2-mutation.json`, `rr2-mutation-run.txt`) | unmutated baseline of every label set first (23, 2, 6, 2 tests, all OK); 16 of 16 mutants killed; every anchor asserted to occur once, every application read back, every restore verified by sha256 (and the six changed files re-hashed against a record taken before the batch: all OK) |
| 27 affected modules (`rr2-modules.txt`: every module that drives registration, invitations, the console invitation, the first administrator, `job_result`, the mapping worker or settlement) | 422 of 422 |
| **`core.tests`, the whole core suite, once** (`rr2-core-suite.txt`, 30 min 50 s) | 2,426 run, 31 skipped, **0 failures** (2,405 before this change, plus the 21 new tests) |
| `manage.py check` | no issues |

One pre-existing test-isolation dependency was found and is not changed here: run without `test_money_closeout` loaded
first, `test_mapping_assistance.MappingAssistance.test_no_provider_credential_is_not_processed_and_releases_the_hold`
fails (`rr2-green-first.txt`), identically with `d5367521`'s `mapping_jobs.py` restored (sha256 verified before and after).
`test_money_closeout.REAL_ANTHROPIC` is captured when that module is first imported; imported lazily inside the test,
after `MappingAssistance.setUp` has patched `anthropic.Anthropic` to refuse, it captures the refusing mock, and the
positive control's SDK construction fails before submission. The full suite loads `test_money_closeout` first and passes.

### Remaining limits (RR2)

- **Rows stored before the rule.** An account created earlier with a quoted local part (if any exists) is not matched to
  its unquoted twin by the existing-account lookup; an invitation issued earlier to a quoted or over-long address cannot
  be accepted (a clear form error) and stays pending until it expires or is revoked. Whether such rows exist in
  production was not measured (this session may not read it); an operator can count them with
  `SELECT count(*) FROM core_user WHERE email LIKE '%"%' OR length(email) > 150` and the same over `core_invitation` and
  `core_clinicinvitation`.
- **RR2-ACC-3 is the simultaneous case only.** A used invitation link opened or submitted afterwards still answers 404
  from the unlocked lookup, as before; only a request that passed that lookup while the invitation was unused gets the
  new answer.
- **RR2-M1** leaves the mapping worker's wording and billing classification as they were; only where and when it decides
  changed. An unreachable database still leaves the job to the stale sweep, as for generation.
- **RR2-L1**: the download rule is deliberately the generation rule; if mapping output should follow the mapping page's
  stricter roles instead, that is a product decision, recorded here rather than made silently.
- The pre-flight health check in `AGENTS.md` was not run by this session: it needs `docker`, which this task's rules
  forbid; the tests ran one at a time against the QA PostgreSQL only.

Evidence: `residuals-evidence-20260929/rr2-*` and `rr2_mutate.py`. Tests: `rebuild/core/tests/test_account_email_rule.py`
(`AccountEmailBounds`, `QuotedLocalPart`, two first-administrator tests), `rebuild/core/tests/test_invitation_account_race.py`
(`OneInvitationAcceptedTwiceAtOnce`), `rebuild/core/tests/test_mapping_outcome_unknown.py`, and two tests in
`rebuild/core/tests/test_mapping_assistance.py`.

## Amendment, 2026-09-29 — re-runnability of the committed mutation proofs (appended)

`residuals-evidence-20260929/rs_mutate.py` and `rr2_mutate.py` name runners in the session scratchpad that no longer
exist (`pyenv/run-tests.sh`, shredded at 09:42Z; `rr2repair/run-tests.sh`, removed by its own agent at 03:49Z). They
are not re-runnable as committed. Reconstructed runners are in `docs/rebuild/v1/cleanup-incidents-20260929/
reconstructed/`. The assessment's cited evidence files themselves are committed and hash-checked.

## Appended 2026-09-30 — the RS-1 to RS-5 section, RECONSTRUCTED (not the original text)

> ⚠️ **RECONSTRUCTED FROM SESSION TRANSCRIPTS. This is not text that was committed on 2026-09-29, and it was not
> re-verified against the code when it was placed here.** `docs/rebuild/cost-definition.md` cites this assessment for
> RS-1 and RS-3, and the RR2 section above names "its repairs (RS-1..RS-5, RA-LOW-1 on `d5367521`)", but the section
> that defines them was never committed to this file: `d5367521` changed 15 lines of it
> (`cleanup-incidents-20260929/evidence-reliance.json`). Its working copy was lost in the scratch shredding of
> 2026-09-29 (event 2, `cleanup-incidents-20260929.md`) and was rebuilt from the writing agent's transcript: one write
> and three edits, 2026-09-29T01:51:51Z to 02:21:35Z, named line by line in
> `cleanup-incidents-20260929/reconstructed/RECONSTRUCTED-event2__report-section.txt.source.json`. Lines 22 to 69 of the
> rebuilt text were checked against the agent's own view of its file at 02:21:37Z (48 of 48 lines equal); the rest is the
> replayed write and edits, unchecked by any view.
>
> **What follows, between the two markers, is byte-identical to
> `cleanup-incidents-20260929/reconstructed/RECONSTRUCTED-event2__report-section.txt`** (18,628 bytes, sha256
> `bf7013690848c291dcb589707a92dcf653a3b296fd0aae281b85a95d4d70b86e`). It is placed here so that the citations resolve to this assessment.
>
> **Where it disagrees with the sections above, they govern:** they were committed, and the RR2 section is the later
> refutation. In particular, its "Remaining limits" says the mapping worker's handler still writes without the job-lock
> guard; RR2-M1 above repaired that. Its evidence files are committed in `residuals-evidence-20260929/` (`rs-red.txt`,
> `rs-green.txt`, `rs1-probe.txt`, `rs1_probe.py`, `rs-mutation.json`, `rs-mutation-run.txt`, `rs_mutate.py`,
> `rs-modules.txt`, `rs-core-suite.txt`, `rs_sitecustomize.py`); the amendment above says why `rs_mutate.py` is not
> re-runnable as committed.

<!-- BEGIN RECONSTRUCTED TEXT: cleanup-incidents-20260929/reconstructed/RECONSTRUCTED-event2__report-section.txt, sha256 bf7013690848c291dcb589707a92dcf653a3b296fd0aae281b85a95d4d70b86e -->
## Refutation of this assessment: RS-1 to RS-5 and RA-LOW-1, repaired (2026-09-29)

A refutation of this assessment on `61c5cc8f` found one MEDIUM and three LOW defects in how the worker records a failure
whose end it cannot see (RS-1, RS-2, RS-3, RS-5), a LOW counting error in this report (RS-4), and a LOW pre-existing account
defect (RA-LOW-1). Every one of them was reproduced first as a failing test on `61c5cc8f`, then repaired, and every new
guard was mutation-proven with sha256-verified restores. Environment as above, except for a fresh throwaway database
`quillmd_qa_resid2_t1` and a `sitecustomize` that refuses every non-loopback connection and name lookup. Providers,
Stripe and email were fakes. The installed application, its database and the campaign root were not touched, and no
environment file was read.

### Summary

| | Reproduced on `61c5cc8f` | Change | Proof |
|---|---|---|---|
| **RS-1** (MEDIUM) settle()'s COMMIT answer lost | **Yes.** The job said "… nothing is charged until it is resolved" while the −0.15 debit, the usage row and the settled hold of that very commit existed | An in-doubt settlement is held with a neutral message and nothing released, absorbed or freed. The handler writes under the job lock and never overwrites a committed outcome. The resolution decides from the committed rows | 5 tests (3 RED), 4 mutants killed |
| **RS-2** (LOW) the handler's own failure | **Yes, two shapes.** OperationalError out of `run_one` with the job left `running` (and charged, when settlement had committed) | The connection is repaired before the handler reads. A handler read or write that fails holds the job | 2 tests (2 RED), 2 mutants killed |
| **RS-3** (LOW, money) a reversal that fails | **Yes.** `failed`, still charged, key freed; the same request queued, held and sent again | Failed state and absorption in one transaction. If the absorption fails, the job is held with its key and charge. `mapping_jobs` repaired the same way | 3 tests (3 RED), 2 mutants killed |
| **RS-4** (LOW) report numbers | Yes: 654 "ordinary" scenarios | Report corrected above: 632 ordinary, 13 vacuous, 619 exercised, 22 not ordinary | the evidence rows, recounted |
| **RS-5** (LOW) fixture message | **Yes.** "Generation failed validation." for a settlement the database refused | Named as a platform database error. Key freed only when no charge can exist | 3 tests (2 RED; one is the in-doubt fixture settlement), 1 mutant killed (and RS1-M1) |
| **RA-LOW-1** (LOW) two accounts for one address | **Yes, at every door.** `ſam@…` created beside `sam@…`, and `sam@…` beside a stored `ſam@…` | One rule, `core.forms.account_email`, at every door that chooses an account's address | 12 tests (9 RED), 6 mutants killed |

### RS-1 — a settlement whose COMMIT answer is lost

**Reproduction.** `core/tests/test_settlement_outcome_unknown.py`, `CommitAnswerLost`. The worker's COMMIT for
`settle()` goes out and its answer is lost. The test replaces Django's `_commit`: an OperationalError comes out of
Django's `commit()`, the rollback that follows fails, and Django drops the connection, as for a connection that died.
Meanwhile the transaction stays open on its own server connection, holding its row locks, as a COMMIT in flight does. A
finisher thread commits it (`landed`) or rolls it back, and only after another backend waits for one of its locks. So
the handler acts while the commit is genuinely in flight. On `61c5cc8f` (`rs1-probe.txt`), the job read
`reconciliation`, "Provider completed, but settlement needs administrator reconciliation; nothing is charged until it is
resolved.". At that moment the usage row existed, the ledger carried the −0.150 usage debit, and the job's
reservation was `settled`. The handler had waited for the in-flight commit and then recorded a claim the commit had
just made false.

**Repair (`core/jobs.py`).**

- `commit_in_doubt(error, carrier)` is structural, in the same idiom as `never_transmitted`. It returns true when the
  exception passed through Django's own `BaseDatabaseWrapper.commit`, checked by code-object identity, **and** `carrier`
  is gone. `carrier` is the connection that sent the COMMIT, recorded just before `settle()`. Django drops a connection
  whose post-commit rollback fails, and reconnects at once inside `atomic`'s exit (`set_autocommit(True)`). So "no
  connection" proves nothing, and the first version, which tested that, never fired: a probe showed a fresh `IDLE`
  connection in the handler. The identity of the connection is what distinguishes the cases.
  - A COMMIT the server answered with an error, such as a deferred foreign-key violation, rolled back on a connection
    that survived to say so. That outcome is established, and the job still reads "nothing is charged".
  - A statement that failed before the COMMIT never reached one, so it cannot commit. That outcome is established too.
- **An in-doubt settlement asserts nothing.** The job goes to `reconciliation` with "The settlement outcome of this
  request is unknown; an administrator must reconcile it.". Nothing is released or absorbed, and the request key is
  held. The audit event is `job.reconciliation` with `billing=uncertain`.
- **The handler now decides and writes under the job's row lock** (`end_failed_job`), and never overwrites an outcome
  that a committed transaction recorded. Found in the same class: the **adoption's** COMMIT answer lost after the
  adoption committed. On `61c5cc8f` the committed success was overwritten as `failed` / `platform_failure`, and the
  charge of an output already adopted into the document was reversed. Now the job stays `succeeded` and charged, and a
  `job.error_after_commit` audit event records the error beside the outcome.
- **The resolution reads what committed.** `admin_resolve_job` already locks the job row, and so waits for any
  in-flight transaction on it. It then reads `Usage` and resolves from it. The tests prove both directions, for both
  form outcomes:
  - **Landed:** the settled branch reverses the charge exactly once. Wallets end as they were before the request,
    no hold is released (`usage.release` never written), and the platform cost equals the usage cost.
  - **Not landed:** the holds are released, and the receipt's cost is absorbed with `receipt:<id>` evidence.
  - `audit_billing` passes with nothing unresolved in both.
- **Stated plainly:** under PostgreSQL the job-row lock alone would have established the outcome. `settle()` takes that
  lock first and holds it until its transaction ends; mutant RS1-M1 shows the lock-first handler then records the
  committed charge and absorbs it. The worker does not rely on that argument, as the refutation required. The cost is
  availability: the document stays pending until an administrator resolves the job.
- **R-B (1) above still holds for the shapes it tested.** Its "after COMMIT" row raises after `settle()` has
  returned on a live connection. That is an established commit, still absorbed as a platform failure (the test is
  unchanged and green). The lost-answer shape is the one this section adds.

### RS-2 — the handler's own failure

- **Connection repair before the handler reads.** `usable_connection()` does what a request boundary does
  (`close_if_unusable_or_obsolete`) before the handler reads; the worker has no request boundary. RED on `61c5cc8f`:
  the server ended the connection at the worker's autocommit write of the result path. Every later statement then
  failed, with OperationalError "the connection is closed" out of `run_one` and the job left `running`. Now the
  handler reconnects and records what is established: settlement never ran, so the job is held with its receipt and
  "nothing is charged".
- **A handler read or write that fails** (DatabaseError) holds the job on a fresh connection, asserting nothing: "The
  outcome of this request could not be recorded; an administrator must reconcile it.". RED on `61c5cc8f`: settlement
  committed, the output was unusable, and the server ended the connection at the handler's first statement. The result
  was OperationalError out of `run_one`, with the job `running` and the charge standing until the stale sweep. Now:
  `reconciliation`, key held, charge standing. The resolution absorbs it, and wallets end as before the request.
- **Unchanged when nothing is possible.** An unreachable database also defeats the hold, so the exception leaves
  `run_one` as before and the stale sweep holds the job. `test_an_unreachable_database_after_the_termination_waits_for_the_stale_sweep`
  is still green.

### RS-3 — a reversal that fails

- **One transaction.** The failed state and the absorption are now one transaction. If the absorption fails, nothing
  of that transaction stands. The job is held in `reconciliation` with its request key and its charge, with "The output
  could not be adopted, and its charge could not be reversed automatically; an administrator must reconcile it.",
  `usage.absorb_failed` audited and `billing=platform_failure`. The settled branch of the resolution absorbs it.
- **Real database refusal.** The test raises 40P01 at the absorption's ledger insert. RED on `61c5cc8f`: `failed`,
  charged, key freed, and a re-request queued a new job. Now a re-request of the same revision returns the held job
  (`reused`): no new job, no new hold, no provider call.
- **Tests that pinned the old behaviour, updated.**
  - `test_billing_policy.test_failed_reversal_never_stops_the_worker_and_is_flagged_by_the_audit` asserted `failed`
    and a direct `absorb_failed_job` as the repair. It is now `…_holds_the_job_with_its_key`, and repairs through the
    console.
  - `RefutationRegressions.failed_unabsorbed_job` manufactured its fixture through the old defect. It now asserts the
    held job, then writes the pre-repair row explicitly; those four tests are about the absorption's netting, which is
    unchanged.
- **`core/mapping_jobs.py`** had the identical shape (behind a default-off flag). It is repaired the same way through
  the shared `hold_for_reconciliation(action='mapping.reconciliation')`, with one test, RED then GREEN. The batch
  worker's `stop()` already absorbs inside its own transaction and never frees a consumed key.

### RS-5 — fixture (synthetic) mode

- **Messages.** A validation refusal still reads "Generation failed validation.". Any other failure is named: "Generation
  failed: a platform database error (OperationalError) stopped it before its output was adopted. Synthetic generation
  carries no charge; the held funds were released.".
- **Request key.** The key is freed only when no charge can exist: nothing settled, and synthetic cost is zero. An
  in-doubt settlement in fixture mode is held like any other, with its key kept.

### RS-4 — the report's counts

The counts are corrected in the R-B (2) sections, table and limits above.

- **Recount from `settle-interleavings-rows.json`:** 670 = 632 over the 33 ordinary operations + 22 second-settlement +
  16 control.
- **The stale sweep's 13 scenarios are vacuous.** `mark_stale` selects jobs running for more than five minutes, and J
  had just started, so every one of the 13 has 0 lock-taking statements.
- **What remains:** the ordinary evidence is 619 scenarios over 32 operations. The 654 figure is "all scenarios outside
  the control".
- **History:** `61c5cc8f`'s commit message still says "654 scenarios against 34 operations"; this report is the
  correction.

### RA-LOW-1 — one rule for an account's email address

**The defect.** The rules that compare addresses disagree outside ASCII:

- The unique index is `lower(email)`.
- Every lookup is `email__iexact`, which is PostgreSQL `UPPER()`.
- The views compare with `str.lower()`, and the email allowlist with `str.casefold()`.

`lower('ſ')` is `ſ` but `upper('ſ')` is `S`. So `ſam@…` passed the index beside `sam@…`, and both answered the same
sign-in lookup. Django's `EmailValidator` admits exactly four non-ASCII local-part letters: ſ, ı, İ and the Kelvin sign
U+212A. It admits them only because `re.IGNORECASE` folds them onto its ASCII class; every other non-ASCII local part
(ß, fullwidth letters) was already refused.

**Decision, from the code.**

- **What the rule is.** An account address is ASCII, stripped and lowercased: the only set on which all four
  comparisons agree.
- **The Kelvin sign.** ASCII is checked on the address as typed, because `str.lower()` itself folds the Kelvin sign
  onto `k`.
- **An address the lookup already answers is refused.** This covers a stored pre-rule `ſam@…`, which the lower() index
  cannot see.
- **Nothing is folded into a different address.** NFKC or casefold would rewrite `ſ` as `s`, and the stored address is
  where the account's mail goes.
- **Internationalized domains** are entered in their `xn--` form. IDNA conversion was rejected: Python's codec is
  IDNA 2003 and maps `ß` to `ss`, which is another domain.

**Doors.** The rule is applied at registration and both invitation acceptances (`RegisterForm`), at both invitation
issuances (`InvitationForm`, `ClinicInvitationForm`), and when the first administrator is created
(`bootstrap_first_admin create`). Ordinary addresses behave as before; the tests cover mixed case, invitation creation
and clinic creation.

### Test runs

| Run | Result |
|---|---|
| RED: every new or changed test on the sources of `61c5cc8f` (`rs-red.txt`) | 49 run: the 25 new or changed tests, plus `test_money_closeout`'s 24, included only so that the mapping test imports in full-suite order. **19 of the 25 fail** (29 failures counting subtests, 2 errors). The 6 that pass are the narrowness and ordinary-case controls, green before and after. `test_money_closeout` 24 of 24 |
| GREEN: the same 49 (`rs-green.txt`) | 49 of 49 OK |
| Mutation (`rs-mutation.json`, `rs-mutation-run.txt`); unmutated baselines first (23, 1, 12 tests OK) | **15 of 15 killed**. 13 were killed by assertion failures. RS2-M4 and RS2-M5 were killed by the old behaviour itself, OperationalError out of `run_one`. Every anchor occurred once, every application was read back, and every restore was compared by sha256 |
| Targeted modules: jobs, billing, invitations, admin resolution and the residual tests, 29 modules (`rs-modules.txt`) | 540 run, 4 failures: `RefutationRegressions`' fixture relied on the RS-3 defect (fixture rewritten above); `test_billing_policy` then 33 of 33 |
| **`core.tests`, the whole core suite, on the final tree** (`rs-core-suite.txt`) (29 min 43 s, one run) | **2,405 run, 31 skipped, 0 failures**. That is 24 more tests than the earlier run's 2,381. The earlier run's one timing failure (`test_round_13_…`, 5.12 s against 5.0 s) did not recur |
| `manage.py check` | no issues |

Mutants:

| Mutant | Killed by |
|---|---|
| RS1-M1 in-doubt settlement treated as established | landed and not-landed (both outcomes), fixture in-doubt: 5 |
| RS1-M2 a COMMIT the server refused counted as in doubt (connection identity ignored) | server-refused commit (new), `test_generation_held_for_reconciliation_at_every_stage` (commit stage) |
| RS1-M3 a statement error counted as in doubt (commit frame ignored) | `test_a_connection_terminated_during_settlement_is_held_for_reconciliation` |
| RS2-M4 the handler's failure re-raised instead of held | the handler's first statement losing the connection |
| RS2-M5 no connection repair before the handler reads | the connection lost at the autocommit result-path write |
| RS1-M6 no committed-state guard under the job lock | the adoption that committed before its answer was lost |
| RS3-M7 a failed reversal swallowed, failed state kept (the old handler) | both RS-3 tests |
| RS5-M8 every fixture failure called a validation failure | the fixture database error |
| RS3-M9 mapping worker: the old handler | the mapping RS-3 test |
| RA-M10 non-ASCII addresses accepted | 16 tests or subtests |
| RA-M11 lowercased before the ASCII check (the Kelvin sign) | the Kelvin subtests |
| RA-M12 no refusal of an address the lookup already answers | register, department and clinic tests for a stored `ſam@` |
| RA-M13 / RA-M14 department and clinic invitations issued without the rule | the issuance test (5 subtests each) |
| RA-M15 first administrator created without the rule | 3 subtests |

### Remaining limits

- **Where the lost answer is simulated.** It is simulated at the Django connection layer (Django's `_commit`). The server
  side is real: the transaction stays open holding its locks and is then committed or rolled back. A real network
  partition, or a proxy between the worker and PostgreSQL, was not exercised.
- **Held when it could be known.** An in-doubt settlement is held even though the job-lock read could establish it, so
  the document waits for an administrator.
- **The mapping worker (default-off)** received only the RS-3 repair. Its uncertain message was already neutral, but its
  handler still writes without the job-lock guard, so an adoption whose COMMIT answer is lost could still be
  overwritten there.
- **RA-LOW-1 changes no existing row.**
  - Production was not inspected, which this session may not do. A pre-rule non-ASCII account, if one exists, keeps
    signing in by the same lookup. A pre-rule invitation to a non-ASCII address can no longer create an account; issue
    a new one to the ASCII address.
  - Whether production holds such an account, or a pair of accounts one lookup answers, needs an operator query
    (count of `core_user` rows whose email is not ASCII, and of `upper(email)` duplicates).
- **The ASCII rule is a product decision taken from the code:** an internationalized domain must be typed in its
  `xn--` form. It is recorded for the owner.

### Evidence

`docs/rebuild/v1/residuals-evidence-20260929/`:

- `rs-red.txt` and `rs-green.txt`
- `rs1-probe.txt` (with the probe `rs1_probe.py`)
- `rs-mutation.json`, `rs-mutation-run.txt` and the runner `rs_mutate.py`
- `rs-modules.txt` and `rs-core-suite.txt`
- `rs_sitecustomize.py` (the socket guard)

Tests:

- `rebuild/core/tests/test_settlement_outcome_unknown.py`
- `rebuild/core/tests/test_account_email_rule.py`
- one test in `test_mapping_assistance.py`
- the updated test and fixture in `test_billing_policy.py`

After the mutation batch, only comments in `core/forms.py`, a docstring and an unused import in the new test file, and the `RefutationRegressions` fixture changed. The core suite ran on that final tree, and its source hashes are recorded in `rs-core-suite.txt`. `docs/rebuild/cost-definition.md` states the new rules.
<!-- END RECONSTRUCTED TEXT -->
