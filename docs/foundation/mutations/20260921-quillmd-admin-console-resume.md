# Declaration — forward repair of the stopped admin-console activation, September 21, 2026

The combined activation of `1f8d7d9d124243f78bd17449e60339f313a2e1c5` **stopped at its own
preservation comparison**, at stage `advance_stopped_source_ff_only`, and left the three private
services stopped. This declaration covers finishing exactly the work that remains. It is written
**before** that work and after a full inspection of what the stopped act left behind.

## What the first attempt found, and why it was right to stop

> **A `CreateModel` migration is not only a table.**

`docs/foundation/mutations/20260921-quillmd-admin-console-integration.md` declared the schema
delta as one new table, its eleven columns, its own constraints and indexes, and **one**
`django_migrations` row. That was incomplete. Django's `post_migrate` also writes the new model's
`ContentType` and its four default permissions, so the true delta is **five rows wider**:

| table | before | after | what |
|---|---|---|---|
| `django_content_type` | 31 | **32** | `core.servicehealth` |
| `auth_permission` | 124 | **128** | `add_/change_/delete_/view_servicehealth` |

⚠️ **The earlier isolated migration proof asserted the opposite** — *"the only row-count changes
were the new empty table and the `django_migrations` record"*. That claim was wrong. It is
corrected here rather than quietly dropped, because the proof is cited in the integration
declaration and a reader would otherwise inherit it.

**Nothing about this is a defect in the migration.** The rows are standard, required, and were
verified to be exactly the model's own: one ContentType, exactly the four default codenames, and
**zero** permissions bound to that ContentType beyond them. The defect was in the DECLARATION,
and the comparison that refused is the control that caught it. This is §2.5 working: a difference
that is not in the declaration is the finding.

## The state this repair starts from, measured

- shared source advanced to `1f8d7d9d…` and clean; `origin/main` will be this repair's target
- migration `0018_servicehealth` **applied**, frontier `0018`, 36 tables, the new table **empty**
- clinical and financial state unmoved: encounters 28, finalized 16, jobs 28 (0 draining),
  usage 28, ledger 46 rows summing 115.607024439350, wallet balance 115.607024439350,
  reserved 0, templates 14
- **no public asset moved, no release stamp changed, no service started** — the failed receipt
  carries no `static_transition`, and its state directory holds no `static-stage`
- the three private services are **stopped**, which is the failure policy, not an incident
- the original activation lock is present, names the failed target, and its process is gone

## Bounded change

`git diff 1f8d7d9d… <target>` must be **exactly three paths**: `scripts/activate-admin-console.py`,
`rebuild/ops/test_admin_console_activation.py`, and this declaration. The activator refuses any
other. No application code, template, migration, dependency, service unit, privilege or policy
changes in this repair.

### The remaining work, and only this

1. the public-asset transition — `app.css` and `app.js` together, every previously hashed asset
   retained, `staticfiles.json` published last;
2. the release stamp in `.env`, that line and no other;
3. start the three private services and verify the exact release.

**The migration is NOT replayed.** The resume asserts it is already applied, that its history row
is unique, that the new table is still empty, and that its bookkeeping is exactly the one
ContentType and four permissions — then leaves it alone.

### Expected delta of THIS act

| must change | exactly |
|---|---|
| public assets | new hashed `app.css` and `app.js` (+ `.gz`), `staticfiles.json` republished, **every older hashed asset retained** |
| `.env` | the release stamp line only |
| services | `quillmd-fresh-doctor`, `-admin`, `-worker` restarted onto the target |

| must NOT change | |
|---|---|
| every table's row fingerprint, outside the already-applied declared delta | identical |
| wallet, ledger, usage, clinical counts | identical |
| schema, constraints, indexes, triggers, functions | identical |
| `core_servicehealth` | still **empty** — it is populated later, by a separate act |
| storage, mail, unit files, shared configuration, co-tenants | identical |

## Preservation required

Clinical records, originals, versioned mappings, finalized exports, financial entries and
balances, audit history, runtime secrets, backup and restore evidence, the retained failure
receipt and its rollback state, and every unrelated service and co-tenant. Public maintenance,
synthetic-only operation, administrator MFA and inactive independent-reviewer access remain as
they are. The serialized mapping contract is untouched.

## What this declaration does not authorize

No provider call, no live Stripe transaction, no backup, restore, readback, renewal or
backup-account audit, no subscription, no real patient processing, no public launch, and no
relabelling of configured costs as reconciled invoices. No key is rotated. The failed receipt and
its preserved evidence are retained, not deleted.
