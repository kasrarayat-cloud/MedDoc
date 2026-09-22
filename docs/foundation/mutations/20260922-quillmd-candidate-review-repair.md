# Declaration — forward repair of the candidate-review activation, September 22, 2026

The 2026-09-21 activation of `5b2576c5` **stopped partway**. This declaration covers the forward
repair the stopped act's own `rollback_policy` prefers. **No migration, no schema change, no
public-asset change.**

## What the stopped act actually did, measured

| step | state |
|---|---|
| source install | **DONE** — the shared tree is at `5b2576c5` and the new code is loaded |
| static install | **DONE** — `before == after == 37` entries, still byte-equal to the pinned receipt |
| environment replace | **NOT DONE** — current `.env` sha256 equals `environment_before_sha256` and equals the retained `prior-environment.env` |
| completion receipt | **NOT WRITTEN** |
| data / schema | **UNTOUCHED** — `migration_performed: false`, `provider_calls: 0` |

So the application serves the NEW code under the OLD release label. That is not cosmetic: the
release marker is what the next activation's baseline check reads, so it must be corrected rather
than left.

## Why it stopped, and it was the guard working

⚠️ **THE OPERATIONS PUBLISHER WROTE DURING THE ACT.** `quillmd-fresh-operations-publisher.timer`
runs `OnUnitActiveSec=5min`. It recomputed `core_servicehealth` at **05:23:08.077792Z** and
published at **05:23:08.106330Z**, inside the activation window `05:22:32Z → 05:23:15Z`. The
`unchanged(baseline, snapshot(...))` invariant then refused, because it cannot distinguish a
routine publish from corruption — and it should not try to.

**Nothing was wrong with the release.** The refusal is a race with a five-minute timer.

⚠️ **AND TIMING IS NOT THE FIX. IT WAS PROPOSED AND REJECTED.** Launching just after an observed
publish shortens the window; it excludes nothing. Two writers with no shared mechanism race for as
long as they both exist, and a race lost rarely is still lost on the night it matters.

**The repair is a shared exclusion mechanism**, `rebuild/ops/activation_exclusion.py`, used by the
activation and by every publisher write path:

| requirement | mechanism |
|---|---|
| shared exclusion | one `flock` both sides take — kernel-held against a descriptor, so a dead holder releases it and there is no stale-lock class |
| drain in flight | the activation acquires **blocking with a bounded wait**; acquisition cannot complete until a publication releases |
| held through checks and receipt | the adapter wraps the entire act and releases in a `finally`, so a FAILED act frees it exactly as a successful one does |
| recompute, never stale | the publisher **collects inside the lock**; a deferred tick collects nothing, so it cannot publish a pre-activation picture under a current timestamp |
| truthful monitoring | every deferral is appended to `publication-deferrals.jsonl`; the `ServiceHealth` row is left strictly alone so its own staleness check keeps working |
| no manufactured health | a deferred tick writes nothing and asserts nothing |

⚠️ **AND FOR THIS ONE ACT THE EXCLUSION IS ONE-SIDED, WHICH IS SAID HERE RATHER THAN GLOSSED.** The
installed publisher is not yet lock-aware — this repair is what installs the lock-aware one. So
the adapter additionally **stops the publisher timer for the act and restores it in a `finally`**,
on success or failure alike, recording both transitions. Stopping a timer does not stop a run
already in flight, so a bounded drain waits for any live `publish_operations_status` before the
lock is taken. The timer is never disabled, and the deferral stays visible: the row keeps its own
freshness check, so a longer gap reads as stale rather than as a green.

## The tree and the configured release have diverged

⚠️ **THIS IS THE PARTIAL STATE, STATED AS TWO FACTS RATHER THAN ONE.** The stopped act installed
the source, so the shared tree is at `5b2576c5`; it never replaced the environment, so the
application is still **configured as** and **serves** `eb37c784`. The driver reads these for
different purposes — `BASELINE` for the shared-tree assertion and the diff range, `RUNNING_RELEASE`
for `updated_environment` and the live-health checks — and a normal activation may collapse them
because normally they agree.

The divergence shows up in **two** places, and both are pinned to the serving release: the
environment check, and the completed static transition whose assets are the ones actually
installed. The second surfaced only after the first was fixed — a reminder that one conflation
found is not the class enumerated.

Collapsing them here made the first read-only pass refuse with *"Unexpected configured release"*.
That refusal was correct: it noticed the very divergence this repair exists to close. The adapter
now pins them separately, and the configured value is taken from the application's **own**
`/health/` output — `rebuild/.env` is not read by any route.

## The reviewed schema expectation

Unchanged from the stopped act, reproduced in full rather than referenced.

<!-- declared-schema -->

```text
auth_group
auth_group_permissions
auth_permission
core_auditevent
core_code
core_codeset
core_codesuggestion
core_costreconciliation
core_department
core_encounter
core_invitation
core_job
core_ledgerentry
core_loginattempt
core_membership
core_organization
core_patient
core_payment
core_platformcost
core_providerreceipt
core_refund
core_reservation
core_servicehealth
core_template
core_templateversion
core_usage
core_user
core_user_groups
core_user_user_permissions
core_verification
core_wallet
core_webhookevent
django_content_type
django_migrations
django_session
otp_totp_totpdevice
```

## The declared source scope

<!-- declared-source-scope -->

```text
docs/foundation/mutations/20260922-quillmd-candidate-review-repair.md
rebuild/core/management/commands/publish_operations_status.py
rebuild/core/tests/test_option_c_acceptance.py
rebuild/core/tests/test_publication_exclusion.py
rebuild/ops/activation_exclusion.py
rebuild/ops/backup_alerts.py
rebuild/ops/test_activation_exclusion.py
scripts/activate-candidate-review-repair.py
```

⚠️ **THIS LIST DRIFTED ONCE AND THE ADAPTER'S OWN CHECK CAUGHT IT.** Two files —
`rebuild/ops/backup_alerts.py`, which carries the independent recovery hook, and
`rebuild/core/tests/test_option_c_acceptance.py` — entered the range after the first version of
this declaration was written. A declaration that names a smaller range than the tree it ships is
not a smaller promise; it is a false one, and the activation refuses rather than accepting it.

## What must change, and what must not

**MUST change:** the release setting in the environment, and the running services restarted onto it.

**MUST NOT change**, each asserted before the act:

| quantity | declared value |
|---|---|
| tables | 36, exactly the set above |
| applied migrations | unchanged; head stays `0018_servicehealth` |
| encounters | 29 |
| finalized encounters | 17 |
| ledger entries | 47 |
| usage rows | 29 |
| service-health ROWS | 1 — ⚠️ the row's CONTENT is expected to move, because the publisher owns it |
| static assets | the 37 entries already installed, unchanged |
| documents, balances, audit history, MFA, synthetic-only | untouched |

## Demonstrated before deployment, not asserted

| demonstration | result |
|---|---|
| forced publisher overlap | a publish attempt inside a held act is refused, **with a positive control** so the refusal cannot be the mechanism being broken |
| failure cleanup | an act that raises inside the hold releases exclusion, and publication resumes |
| dead holder | cannot wedge publication — the reason the mechanism is `flock` and not a lock file whose liveness must be reasoned about |
| bounded drain | refuses rather than hangs; an unbounded wait is its own outage |
| guarded data during the interval | a real `publish_operations_status` tick forced inside a held window leaves the row byte-identical |
| resumption | the next tick publishes fresh, and recomputes |
| deferral recorded | every deferral appended, never silent |

**No provider call and no repeat B2 drill.** The qualified recovery proof
`f2df7c56486b5d09de254ee7ab69c30697ca2b6487b84b700fe06c7fa7f49d0f` is reused unchanged; this is a
synchronization repair and needs neither.
