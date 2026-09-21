# Declaration — install the operations-status publisher, September 21, 2026

Two new systemd units and one scheduled publication. **No application restart, no migration, no
schema change, no provider call, no backup, restore, readback or renewal, and no change to any
existing service, privilege, credential or policy.**

## Why this exists, and why it is not a view

⚠️ **THE WEB PROCESS STRUCTURALLY CANNOT READ THE BACKUP STATE, AND THE OBVIOUS FIX IS A FALSE
RED.** `deploy/quillmd-fresh-admin.service` carries
`InaccessiblePaths=… /opt/meddoc-pro/rebuild/.runtime`, so the runtime tree is outside the admin
surface's mount namespace; the state directories are additionally mode 0700 owned by a different
identity with no shared group. A console view that read `.runtime/backup-alerts/status.json`
would report *unavailable* on a host whose backups are perfectly healthy — **and a panel that is
wrong when things are fine is one somebody stops reading, which is how a false red becomes a
false green on the night it matters.**

**The identities stay disjoint. Nothing is granted to the web process.** The publisher runs as
the operations identity — the same `claude` that `quillmd-fresh-backup-alerts.service` already
uses — calls the existing aggregator, and writes the already-redacted report into
`core_servicehealth`, a table the web process can read. No path is opened, no mode widened, no
privilege granted, and `.runtime` stays masked exactly as it is.

## Bounded change

| what | exactly |
|---|---|
| new files in `/etc/systemd/system` | **two**: `quillmd-fresh-operations-publisher.service` and `.timer`, root-owned, 0644, byte-identical to their reviewed sources in `rebuild/deploy/` |
| new enablement link | **one**: `timers.target.wants/quillmd-fresh-operations-publisher.timer` |
| rows written | `core_servicehealth`, key `backup`, **one row**, created or refreshed |
| schedule | 5-minute timer, 3-minute boot delay, matching the existing alert check |

| must NOT change | |
|---|---|
| every other systemd unit, override and enablement link | identical |
| `quillmd-fresh-doctor`, `-admin`, `-worker`, `-database` | still **active**, same MainPID |
| protected configuration (`.env`, db-role secrets) | identical uid, mode and hash |
| every table other than `core_servicehealth` | untouched |
| wallets, ledger, usage, jobs, receipts, reservations, clinical records, audit history | untouched |
| backup and offsite timers, policies, tickets and evidence | untouched |

## The act, and its one door

    bash scripts/run-ruled-mutation.sh --declaration docs/foundation/mutations/20260921-quillmd-operations-publisher.md \
      -- .venv/bin/python rebuild/ops/install_operations_publisher.py --expected-commit <sha> --action install --execute
    # then, separately:
      … --action activate --execute

**Default is read-only**; `--execute` is opt-in, and `install` is separate from `activate` so the
units land before anything runs. The host actions happen only inside the pinned, network-less
root helper against a byte-verified source set, exactly as the backup and alert installations do.
`--action disable` is the rollback: it removes this timer's enablement and nothing else.

## What proves it worked

The helper proves the units installed, resolved and enabled. **The publication is proved
separately, from the operator side, through the application's own model** — a `ServiceHealth` row
for key `backup` whose `published_at` moved, is under fifteen minutes old, carries an expected
interval at or above the schema floor, and whose payload names no clinical field. A row that did
not move is not a publication, and the check says so.

## What this declaration does not authorize

No provider call, no email, no live Stripe transaction, no backup, restore, readback, renewal or
backup-account audit, no subscription, no real patient processing, no public launch, no new
credential, and no change to billing policy. Public maintenance, synthetic-only operation,
administrator MFA and inactive independent-reviewer access all remain as they are.
