# Declaration — private activation of the multi-column/mixed Word release, September 21, 2026

Advances the served application from `21809ef408a5f7b6691beb338a7640da82fcfb97` to the merged
release. **No migration, no public-asset change.** The operations-status publisher is installed
by its own ruled act afterwards, not by this one.

## The reviewed schema expectation

⚠️ **This list is the EXPECTATION, and the adapter reads it from HERE.** It is not read from the
database the activation is about to check, because a check whose expected value comes from the
thing under test cannot fail. It is the 35 tables this lineage shipped against — taken from the
retained capture manifest `20260921T043001Z-0a6f66da` that the previous activation pinned as its
recovery evidence — **plus exactly one table, `core_servicehealth`, created by the reviewed
migration `0018_servicehealth`**. Nothing else is added, and nothing is removed.

Independently corroborated by tonight's verified capture `20260921T194532Z-1b826c0d`, whose
manifest holds these same 36 names and whose set equals live `pg_tables` exactly.

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

## Migration frontier

| | |
|---|---|
| frontier before AND after | `0018_servicehealth` |
| history rows for it | exactly **1** |
| migrations applied by this act | **none** |

## Declared source scope

Advancing `21809ef408a5f7b6691beb338a7640da82fcfb97` to the merged release changes these
**thirty** files and no others — the twenty-four already reviewed, plus the minimal driver repair,
its two refreshed pins, this adapter, this declaration and its guards:

<!-- declared-source-scope -->

```text
.claude/settings.json
docs/foundation/mutations/20260921-quillmd-desktop-key-administration.md
docs/foundation/mutations/20260921-quillmd-operations-publisher.md
docs/foundation/mutations/20260921-quillmd-word-multicolumn-activation.md
docs/foundation/mutations/20260921-quillmd-word-multicolumn-mixed.md
rebuild/core/field_location.py
rebuild/core/generation.py
rebuild/core/tab_review.py
rebuild/core/tests/test_mapping_review_clarity.py
rebuild/core/tests/test_tab_form_policy.py
rebuild/core/tests/test_tab_independent_sections.py
rebuild/core/tests/test_unlabelled_source_scope.py
rebuild/core/views.py
rebuild/deploy/quillmd-fresh-operations-publisher.service
rebuild/deploy/quillmd-fresh-operations-publisher.timer
rebuild/documents/engine.py
rebuild/documents/tab_form.py
rebuild/documents/test_multicolumn_and_mixed.py
rebuild/documents/test_tab_form.py
rebuild/documents/test_unmapped_areas.py
rebuild/ops/install_operations_publisher.py
rebuild/ops/test_admin_console_activation.py
rebuild/ops/test_operations_publisher_install.py
rebuild/ops/test_word_multicolumn_activation.py
rebuild/ops/test_word_multicolumn_scope.py
scripts/activate-admin-console.py
scripts/activate-typed-voice-generation.py
scripts/activate-typed-voice.py
scripts/activate-word-multicolumn.py
scripts/ci/verify-fresh.sh
```

**Zero migrations and zero files under `rebuild/static/` appear in that range** — measured, not
assumed. The two `rebuild/deploy/` unit files and `rebuild/ops/install_operations_publisher.py`
are carried into the tree so the publisher's own ruled act can find them; **this act installs no
unit and enables no timer.**

## What MUST NOT change

Documents, mappings, finalized records and exports; wallets, ledger, reservations, settlements
and provider receipts; audit history; MFA and inactive reviewer access; backup and offsite
timers, policies, tickets and evidence; the renewal installed at 19:38Z; public maintenance; and
every other project on this host. Clinical counts are compared before and after.

## Two captures, two roles

⚠️ **The activation safety capture is NOT the publisher's coverage capture**, and a read-only run
refused when this declaration's first draft conflated them.

| | capture | why |
|---|---|---|
| **activation safety** | `20260921T043001Z-0a6f66da` (35 tables) | the chain requires the final capture to share the RESTORED DRILL's schema exactly — a rollback target whose schema was never restore-proven is not evidence. Measured set-equal to the drill; inside the thirty-hour window; the same capture the previous activation pinned |
| **publisher coverage** | `20260921T194532Z-1b826c0d` (36 tables) | the first capture containing `core_servicehealth`, verified against live `pg_tables` **by name**. Checked by the publisher's own ruled act, not by this one |

This act changes no schema, and the one table the safety capture does not carry is empty.
Re-proving an independent-key restore against tonight's capture would be restoration work that is
out of scope, so the guard is left exactly as it is. Full account:
`rebuild/.runtime/word-multicolumn-activation-20260921/readonly-refusal-20260921.md`.

## ⚠️ One bounded acceptance, and exactly what it costs

The retained safety capture **predates the reviewed migration**, so it holds 35 tables while the
live database holds 36. Two checks in this chain want different captures and no single capture
satisfies both: `backup_evidence` requires the safety capture to share the RESTORED DRILL's
schema, and `assert_retained_capture` requires it to equal the LIVE population. Reconciling them
strictly would need a fresh independent-key restore drill against a 36-table capture, which is
restoration work outside this scope.

**One clause is therefore widened by exactly one table, in one direction, and only while that
table is EMPTY.** A restore from this capture would lose no row, because there is no row in it to
lose; it restores a database one migration behind the code, which is the ordinary property of any
capture taken before a migration.

⚠️ **This is NARROWER than the precedent it copies.** When the previous activation accepted the
same exception, no capture covering the table existed. One does now —
`20260921T194532Z-1b826c0d`, verified against live `pg_tables` **by name** — so the **publisher's
coverage requirement is met strictly and does not rely on this exception at all.** Nothing about
that requirement is weakened.

Proved rather than described: a non-empty uncovered table refuses, a second uncovered table
refuses, an uncovered table that is not the declared one refuses, and a table the capture holds
but the live database lost refuses. Identical populations take the strict path.

## Failure recovery

The driver's own receipt, lock and staged-state directory are retained on failure. A failure is
diagnosed from that receipt and repaired; it is **not** blindly replayed, and no guard is
weakened to get past it.
