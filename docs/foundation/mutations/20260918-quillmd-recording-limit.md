# Private activation of the binding recording charge limit — 2026-09-18

Owner policy of 2026-09-18: the displayed maximum charge is a binding customer limit. This act ships it to the private service with migration
`core.0013_recording_charge_limit`, from the running release `3eac783a` to the cited merge. It runs through
`scripts/activate-recording-limit.py`, which the ruled-mutation runner invokes with this committed declaration.

## The tree this act ships

The act fast-forwards permanent main from `3eac783a` to the cited target and restarts the three private services on it. It declares every
change in that range:

1. **Documentation merged since `3eac783a`** (PR #1195): checkpoint, external verification runbook, owner actions, patient-data release
   requirements and storage-encryption notes.
2. **The plaintext recovery-and-reap act**: its script, tests and declaration. The storage act's rollback no longer requires the removed
   snapshot. These are operator scripts; nothing in them runs as part of this act.
3. **The binding recording charge limit** (`cost-definition.md`, "Recording charge limit"):
   - every recording's duration is measured in pure Python, as a decoder would play it, before any paid request, and unmeasurable input is
     refused with nothing sent;
   - the recording's exact charge limit is held before the request;
   - within the displayed limit it is processed at once. Above it, nothing is sent until the doctor chooses a shorter segment or approves a
     clearly priced higher limit (a signed approval, valid for 30 minutes);
   - the charge is 1.5 × cost, capped at the held limit. Anything above is absorbed as one `absorbed_over_limit` platform cost, and a later
     reconciliation records the excess as `over_limit_delta`;
   - usable transcripts are delivered with any missing portion marked. A transcript the notes cannot take is delivered for download and
     stays charged within the limit;
   - the payer's balance is never shown to the requester;
   - the worker removes over-limit uploads nobody approved within the window;
   - the backup/restore invariant, both verification runners, `audit_billing`, the billing page and the docs follow the capped rule.
4. **Guard maintenance**: the storage and billing activators' allow-list tests check the targets those acts migrated.

Not in the range, and refused by the activator if present: service units, the document sandbox, the service launcher, the storage helper
and the Python requirements. The compiled Word inputs must be identical.

## Expected delta, declared before the act

Database. Migration 0013 creates no model, so Django's post-migrate bookkeeping adds no content type and no permission. The whole delta:

- `core_costreconciliation.over_limit_delta`, `numeric(24,12)`, NOT NULL, no default. The table is empty, so no row gains a value.
- `core_platformcost.platform_cost_kind_known` is redefined to also admit `absorbed_over_limit`.
- `core_usage.exact_usage_multiplier` (`charged = 1.5 × cost`) is replaced by `usage_charge_at_most_multiplier`
  (`0 ≤ charged ≤ 1.5 × cost`, `cost ≥ 0`). All 12 existing usage rows are exactly 1.5 × cost, so they satisfy both.
- One partial unique index, `one_over_limit_absorption_per_job` on `core_platformcost(job_id)` where the kind is `absorbed_over_limit`.
- One `django_migrations` row, `core.0013_recording_charge_limit`.

The activator pins the migration file by SHA-256 and each changed definition as PostgreSQL 17 renders it. Before the act they were measured
live; after it, on a database migrated to 0013.

Must NOT change:

- every row of all 35 existing tables, compared by fingerprint before the migration, after it and after the services start;
- every other column, constraint and index;
- the private documents and mail outbox (inventory before and after);
- the Word runtime artifact and the protected containers;
- the retained reports and the installed unit files;
- the co-tenants' HTTP status.

The first worker loop runs the new upload reaper. No over-limit quote exists yet, so it removes nothing, and the file inventory proves it.
The environment file changes in exactly one line: the release identifier.

Provider requests: none. Jobs pending before or after: none.

## After the act

- Health on both private ports reports the target and `synthetic-only`; each service's same-PID identity proof names the target.
- `audit_billing` passes every check.
- The read-only console check passes. The doctor's encounter page states "Limit $0.30 per recording, which fits recordings up to" a length,
  and that limit and length equal what the running application's own quote computes.
- A fresh encrypted backup and plaintext-free restore check pass with every invariant zero, including the capped `usage_multiplier`.

## Failure handling

The act fails closed. On any failure after the services stop, they stay stopped and the result names the stage. The activator is never
re-run: a partial state is resumed only by a separate declared act. The migration runs in one transaction, so a failure inside it changes no
schema.

## How it runs

Only through `scripts/run-ruled-mutation.sh` with this committed declaration, from permanent main at `/opt/meddoc-pro`, running the reviewed
activator from a worktree at the target:

    activate-recording-limit.py --target <merge sha> \
        --backup-report rebuild/.runtime/restore-checks/backup-restore-<run>.json \
        --result /opt/meddoc-pro/rebuild/.runtime/recording-limit-activation-<label>.json --execute
