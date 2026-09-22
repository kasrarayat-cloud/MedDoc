# Declaration — install the invited-pilot doctor-navigation repair, September 22, 2026

A code-only release. **No migration, no schema change, no unit change, no public-asset content
change, no provider call, no backup, restore, readback or renewal, and no change to any
credential, policy, mode or identity.**

## Why this exists

The 2026-09-22 invited-pilot readiness walkthrough (authenticated, GET-only on the installed
release; mutating flows on an isolated QA stack with fixture generation) found three
doctor-facing defects that stop or mislead a doctor completing the supported workflow:

1. **"Use this form" selected nothing.** Both the form page and the library link to
   `/encounters/new/?template=<id>`, but the view ignored the parameter, so the doctor landed on
   an empty list of every mapping version of every form (25 on the installed release, superseded
   versions included). Now the chosen form's CURRENT mapping version is preselected, taken from
   the form's own scoped queryset.
2. **A refused finalization did not say which question was at fault.** "A clinician must review
   every field" and "Resolve every conflict by editing the answer" named no question, on forms
   of up to 100 fields, and the second omitted the explicit "Accept this suggestion" route. Now
   both name the questions in form order (bounded to twelve), and the conflict message names both
   routes. The gate itself is unchanged: a randomized equivalence check of 200,000 states found
   the old and new predicates refuse in exactly the same states.
3. **A refused document edit was a bare text page with no way back** (for example a save from a
   second tab: `409 This document changed. Reload before editing.`). Now it renders inside the
   workspace, says nothing was saved, and links back to the document. Every refusal still
   returns before any write, with the same status code.

## Bounded change

| what | exactly |
|---|---|
| release marker | `3b8cfb9a2ab4d3ce22cce438f61fce64f012748a` → the target, replaced by the driver, never by hand |
| source | fast-forward only, to the exact reviewed target |
| files changed | the three below, plus this declaration and its adapter |
| systemd units | **none** |
| public assets | recollected by the driver; no static source changes, so the inventory must come back identical (37 entries) |
| services | doctor, admin and worker restarted onto the new release by the driver |

**MUST change:** served `/health/` release on doctor and admin equals the target; the new
template exists on the served path; `GET /encounters/new/?template=<id>` preselects that form's
current mapping (checked read-only after the act).

## MUST NOT change, each asserted before the act

| quantity | declared value |
|---|---|
| tables | 36, exactly the set below |
| applied migrations | unchanged; head stays `0018_servicehealth` |
| encounters | 29 (17 finalized) |
| patients | 4 |
| jobs | 29 |
| ledger entries | 47 |
| payments | 3 |
| usage rows | 29 |
| service-health ROWS | 1 — the row's content moves; the count does not |
| installed public assets | 37 entries, unchanged in name and digest |
| every systemd unit, override and enablement link | identical — this release installs none |
| documents, balances, audit history, MFA, synthetic-only, public maintenance | untouched |

⚠️ `core_auditevent`, `django_session` and `core_user.last_login` are expected to move from
ordinary sign-ins and are named rather than omitted.

<!-- declared-schema -->
```
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

<!-- declared-source-scope -->
```
rebuild/core/views.py
rebuild/templates/document_refusal.html
rebuild/core/tests/test_pilot_navigation.py
```

## Rollback

Stop on failure; retain current data, schema, configuration and prior source. The driver retains
the prior source archive, the prior environment and the prior static inventory. The change is
presentation and preselection only; a failed act leaves the installed release serving.

**No provider call. No B2 call. No restore drill. No new capture.** The retained capture
`20260922T043002Z-7d766ca1` and the independent-key restore proof
`f2df7c56486b5d09de254ee7ab69c30697ca2b6487b84b700fe06c7fa7f49d0f` are reused unchanged.
