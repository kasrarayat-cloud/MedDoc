# Declaration — private activation of the candidate-review release, September 21, 2026

Advances the served application from the multi-column/mixed Word release. **No migration, no
public-asset change, no schema change of any kind.** The change is confined to what a clinician is
SHOWN when the scope validator holds an answer, and to how an acceptance is recorded.

## The reviewed schema expectation

⚠️ **The adapter reads this list from HERE, never from the database it is about to check.** A check
whose expected value comes from the thing under test cannot fail.

This release carries **no migration**, so the expectation is the previous activation's reviewed
36-table set, **carried over byte-for-byte** — the 35 tables of the lineage plus `core_servicehealth`
from migration `0018_servicehealth`. It is reproduced in full rather than referenced, because a
declaration that points at another file's list is one edit away from declaring something nobody read.

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

The full set of tracked files that differ between the served release and the tree being installed.
The adapter refuses any drift outside it.

<!-- declared-source-scope -->

```text
docs/foundation/mutations/20260921-quillmd-candidate-review-activation.md
docs/foundation/specs/field-specific-correction-handling.md
rebuild/core/generation.py
rebuild/core/tests/test_candidate_suggestion.py
rebuild/core/views.py
rebuild/templates/encounter_detail.html
scripts/activate-candidate-review.py
```

## The recovery evidence, and an exception that is REMOVED rather than broadened

⚠️ **The previous activation carried a bounded exception and it has expired. That is recorded here
because a guard that refuses is evidence, not an obstacle.** That activation accepted a 35-table
safety capture which did not cover `core_servicehealth`, bounded explicitly to *only while that
table is EMPTY* — a restore from it would then lose no row. The operations publisher has since
written one row, so this release's read-only pass refused:

    RuntimeError: The table the retained capture does not cover is no longer empty.

The refusal was correct. It is **not** worked around, and the exception is **not** widened.

Instead the prerequisite is met strictly, through the existing authorized LOCAL procedure — no
offsite restore, no B2 allowance, no provider call, no new key:

| step | result |
|---|---|
| `backup_restore.py backup` | `20260922T024158Z-8d231f14` — **36 tables**, 226,080 rows, 64 files, `source_commit` `eb37c784` = the running release |
| `backup_restore.py restore-check` | `restore-88da076936d4dc98` — isolated and networkless: `all_table_hashes_match` and `all_file_hashes_match` true, `provider_actions` 0, `network` none, `published_ports` 0, `workers_started` 0, `provider_credentials_copied` false, container not retained, financial invariants all zero |
| `compose-backup-restore-proof.py` | `backup-restore-20260922T024158Z-8d231f14.json`, 65 objects, 65 plaintext checked, validator passed |

Because that capture's table population equals the live population exactly, **the driver's own
`assert_retained_capture` passes unmodified and this adapter overrides it with nothing.** The
safety capture and the restore drill are now the same run, so the schema-equality clause holds by
identity rather than by coincidence. The historical activators' own constants are untouched; the
two values are set on the modules for this run only, because their receipts depend on them.

⚠️ **The compose step refused once before this, and that refusal is also recorded**: paired with
the older 36-table capture `20260921T194532Z-1b826c0d`, it asserted the live `/health/` release
against the capture's `source_commit` and found `eb37c784` against `21809ef4`. A stale capture
cannot be dressed in current health evidence. The fresh capture is what makes the pairing honest.

## What must change, and what must not

**MUST change:** the running image's source, and nothing else about the deployment.

**MUST NOT change**, and each is asserted by the adapter before it acts:

| quantity | declared value |
|---|---|
| tables | 36, exactly the set above |
| applied migrations | unchanged; head stays `0018_servicehealth` |
| encounters | 29 |
| finalized encounters | 17 |
| ledger entries | 47 |
| usage rows | 29 |
| service-health rows | 1 |
| cost-reconciliation rows | 0 (the driver asserts this) |
| static assets | identical to the completed receipt of the release now serving |
| stored documents, balances, audit history, MFA | untouched |

⚠️ **THE CLINICAL COUNTS ARE IN THIS TABLE DELIBERATELY.** An activation that moves an encounter,
a finalized document or a signature count has done something nobody asked for, and the only way to
know is to have written the numbers down while they were still true. They were read read-only from
`quillmd_fresh` before this declaration was committed.

## What this release does NOT do

- It does not change `text`, `status` or `evidence` for any answer. Proven across 896 synthetic
  cases against the installed release, with a positive control showing the comparison flags 44
  cases when the code *is* changed.
- It does not change `INHERITED_SCOPE`, `INLINE_CORRECTION`, `UNSCOPED_NEGATIVE_HEADING` or
  `QUOTED_SOURCE`. Proven against the installed release's own source.
- It does not relax finalization. A held answer still refuses to finalize until a clinician decides.
- It does not repair the trailing-correction defect recorded in
  `docs/foundation/specs/field-specific-correction-handling.md` §3. That gap is narrowed, not closed.
- It makes **no provider call**. The §1e allowance is spent and is not re-spent by this activation.
