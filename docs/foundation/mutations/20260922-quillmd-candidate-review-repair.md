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

⚠️ **AND THE REPAIR MUST NOT RE-RUN INTO THE SAME RACE.** The act takes ~45 seconds; the window is
five minutes. This repair is launched immediately after an observed publish so the runway is
maximal, and the observed publish timestamp is recorded with the act. The timer is NOT disabled:
the sanctioned `systemd()` helper permits only start/stop of the three service units, and
disabling a monitoring timer to make an activation pass would be exactly the wrong trade.

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
scripts/activate-candidate-review-repair.py
```

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

**No provider call.** The §1e allowance is spent and is not re-spent here.
