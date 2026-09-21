# Declaration — combined admin console + doctor/form private activation, September 21, 2026

Two reviewed candidates are installed together in **one** activation. Tab 1's doctor/form work
(PR #1252) is already merged and deliberately uninstalled; this branch (PR #1251) adds the
administration console. Both change a public static asset, and the public-static transition is
the riskiest path in this system — it failed twice earlier today, once because the collector
requested `shell` through the database-role wrapper and was correctly refused, once because a
restrictive inherited umask masked the staging directory from 0755 to 0700. **Running that
transition once instead of twice is the whole reason these are combined.**

The owner delegated this routine integration decision. No product question is reopened here.

## Measured prerequisites

- Shared repository `main` and served doctor/admin/worker are **not** the same revision, and
  that is expected: at the time this is written `main` is
  `06d095b2ce9a73f3764eed733319117e1ad456c8` (PR #1252) while the served release is
  **`e66d84abbb4cda663dc4489d175c71d477572fca`**. The baseline this activation moves *from* is
  the served release, read from the running surfaces rather than from `main`. The **target** is
  the merge commit of PR #1251, which contains `06d095b2` — so this one act installs both
  candidates, and the served release advances by two merges rather than one.
- The activator refuses any target that is not a merged pull request's own merge commit on
  `main`, and refuses to run from anywhere but the clean reviewed worktree.
- Stop if a concurrent source or release change requires inspection.
- Recovery point, read from QuillMD's own receipts and **not** inherited from a prior report:
  local encrypted capture of `quillmd_fresh` **complete 2026-09-21T04:31:03Z**
  (run `20260921T043001Z-0a6f66da`), offsite transfer **complete 2026-09-21T05:00:15Z** with a
  **verified remote readback** whose `manifest_cipher_sha256` matches the upload's own
  (`ac714b19…`). No offsite restore is repeated and no key is rotated by this act.
- `meddoc-pro-postgres-backup-1` is the **legacy** Next.js `meddoc` sidecar
  (`POSTGRES_HOST=postgres`, `POSTGRES_USER=meddoc`) and is unrelated to QuillMD's data. It stays
  stopped; reviving a retired unit is not part of this activation.

## Bounded change

Application code, templates, one new additive migration and **both** public static assets.
No dependency, SDK, service-unit, privilege, billing-policy, backup-policy or provider change.
No provider, payment, email, backup, B2 or renewal call is made by the activator.

The diff also carries the act's own two files — `scripts/activate-admin-console.py` and its
guards in `rebuild/ops/test_admin_console_activation.py`. They are named here because the
activator's allowlist is exhaustive: a path that is not declared refuses the activation, so the
instrument has to declare itself.

### The one door

    bash scripts/run-ruled-mutation.sh --declaration docs/foundation/mutations/20260921-quillmd-admin-console-integration.md \
      -- .venv/bin/python scripts/activate-admin-console.py --target <merge-sha> \
         --backup-report <retained restore proof> --result <receipt> --execute

`activate-admin-console.py` is a thin adapter: it pins `scripts/activate-typed-voice.py` by
sha256, which already owns the public-asset transition, and adds exactly two things — the
declared migration, and a preservation comparison that tolerates that migration and nothing
else. **Default is read-only**; `--execute` is opt-in. Fifteen mutations of its guards were
each applied and each caught before this was written.

Two honesty repairs are made to the inherited receipt, because the inherited act is code-only
and this one is not: `migration_performed` reports what actually happened rather than the
inherited constant `False`, and the inherited claim
`existing_schema_indexes_constraints_catalog_unchanged` is replaced by the narrower
`…_apart_from_declared_new_table`. A receipt that overstates preservation is worse than none.

### Schema — the expected delta, written before the act

`core/migrations/0018_servicehealth.py`, applied through the `migrator` role. It is purely
additive:

| must change | exactly |
|---|---|
| tables | **35 → 36** — one new table `core_servicehealth`, and nothing else |
| columns | **+11**, all on `core_servicehealth` (`id, created_at, key, condition, severity, healthy, action, payload, computed_at, published_at, expected_interval_seconds`) |
| indexes | one new `core_servicehealth_key_…_like`, plus the unique key constraint |
| `django_migrations` | **+1 row**, `core / 0018_servicehealth` |

| must NOT change | |
|---|---|
| every other table's row fingerprint | identical |
| `core_wallet.balance` / `.reserved` sums | identical |
| `core_ledgerentry` sum and row count | identical |
| `core_usage` charged/actual sums | identical |
| clinical counts — encounters, patients, templates, finalized exports | identical |
| every existing column, constraint and index | identical |

This was proved before the act on an isolated copy brought to the exact state production is in
(0017, 35 tables): applying 0018 moved tables 35 → 36 and columns 276 → 287, the only row-count
changes were the new empty table and the `django_migrations` record, and the money totals were
byte-identical. **A difference outside that table is the finding**, whatever explanation is
available afterwards.

### Static — both assets move, and every old one is retained

`rebuild/static/app.js` (Tab 1) and `rebuild/static/app.css` (this branch). Collect into a new
stage, verify canonical paths, exact source-to-hash binding, compressed variants, operator
ownership and modes (0755 directories / 0644 files, enforced against the caller's private
umask), **retain every previously hashed asset so pages already open keep working**, and publish
`staticfiles.json` last. Do not apply a blanket `chmod`, do not weaken the shell allowlist, and
do not make the private runtime world-readable to satisfy a static check.

### Bookkeeping and audit — what is expected to move

The activation itself creates no financial rows. Expected new audit rows are only those the
activator and post-activation checks generate (`admin.*` reads if the console is exercised).
**No `core_job`, `core_usage`, `core_reservation`, `core_ledgerentry`, `core_payment` or
`core_refund` row may be created, changed or deleted.** `core_servicehealth` is expected to be
**empty** immediately after the migration; it is populated later by the publisher, which is a
separate act with its own scope.

### Services

`quillmd-fresh-doctor`, `quillmd-fresh-admin`, `quillmd-fresh-worker` restart onto the target.
Both surfaces must afterwards report the target release and `synthetic-only`, and the worker
must genuinely have restarted rather than merely been signalled.

## Preservation required

Clinical records, originals, versioned mappings, finalized exports, financial entries and
balances, audit history, runtime secrets, backup and restore evidence, and every unrelated
service and co-tenant. Public maintenance, synthetic-only operation, administrator MFA and
inactive independent-reviewer access all remain as they are.

⚠️ **Serialized template fields and versioned mappings are not touched.** `validate_mapping`
compares a stored mapping against a fresh inspection with exact equality, so an incidental new
key in a field dictionary breaks exports for templates already uploaded. Neither branch adds a
key to a stored mapping dictionary; location hints and display metadata stay out of it.

## What this declaration does not authorize

No provider call, no live Stripe transaction, no backup-account audit, no subscription, no real
patient processing, no public launch, and no relabelling of configured costs as reconciled
invoices. Native Word appearance and the owner's own microphone test remain open for human
acceptance and are not simulated.
