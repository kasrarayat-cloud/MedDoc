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
