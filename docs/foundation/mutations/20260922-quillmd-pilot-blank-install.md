# Declaration — install "Leave blank — reviewed" and the post-expiry renewal-administration door, September 22, 2026

A code-only release. **No migration, no schema change, no unit change, no public-asset content
change, no provider call, no backup, restore, readback or renewal act, no ledger reservation, and
no change to any credential, policy, mode or identity.**

## Why this exists — two owner-authorized decisions (2026-09-22)

1. **"Leave blank — reviewed".** On ordinary forms a generated conflict whose right answer is
   blank could not be finalized: an empty submit kept the status `conflict`. A clinician can now
   resolve an eligible answer by explicitly leaving it blank. The decision records actor, revision
   and time plus the status it resolved; the original conflict, candidate and evidence are kept; it
   is carried across saves and reopen, withdrawn only by an owner/clinician act, and exports as an
   empty answer area. Not offered for signature/identity questions or the qualified Word form.
   The finalize refusal now names the decision options instead of steering doctors to enter an
   answer or accept a suggestion to get past the gate.
   ⚠️ Found by the second refutation round and fixed here: a **whitespace-only answer is now stored as
   empty** on every field. Before, one space counted as an edit, so it could clear a generated
   conflict, or erase a left-blank decision without the authority check or audit a withdrawal needs.
2. **Post-expiry renewal-administration reservation (option B).** New module
   `rebuild/ops/offsite_renewal_administration.py`. ⚠️ It is deliberately NOT an edit of
   `offsite_operator.py` or `automatic_offsite.py`: the installed allocation contract pins the
   sha256 of seven control sources, and changing any of them would make every policy validation —
   including the historical one renewal depends on — refuse `policy_invalid`. **None of the seven
   changes in this release.** Installing the module reserves nothing; the reservation is a separate
   declared act (`20260922-quillmd-renewal-administration-reservation.md`).

## Bounded change

| what | exactly |
|---|---|
| release marker | `84fd9e8a1ee1ea0e099598a03a0ae99d68eb133b` → the target, replaced by the driver, never by hand |
| source | fast-forward only, to the exact reviewed target |
| files changed | the source scope below, plus this declaration and its adapter |
| systemd units | **none** |
| public assets | recollected by the driver; no static source changes, so the inventory must come back identical (37 entries) |
| services | doctor, admin and worker restarted onto the new release by the driver |

**MUST change:** served `/health/` release on doctor and admin equals the target; the encounter
page offers "Leave blank — reviewed" on an eligible open field (read-only check after the act).

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
| offsite `budget.json`, `renewal/*`, policy, allocation contract | byte-identical — this release reserves and renews nothing |
| the seven pinned offsite control sources | byte-identical |
| every systemd unit, override and enablement link | identical |
| documents, balances, audit history, MFA, synthetic-only, public maintenance | untouched |

⚠️ `core_auditevent`, `django_session`, `core_user.last_login` and `otp_totp_totpdevice`
(`last_used_at`, `last_t`) are expected to move from ordinary and administrator sign-ins and are
named rather than omitted.

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
rebuild/templates/encounter_detail.html
rebuild/core/tests/test_leave_blank_reviewed.py
rebuild/ops/offsite_renewal_administration.py
rebuild/ops/test_offsite_renewal_administration.py
.claude/settings.json
docs/foundation/mutations/20260922-quillmd-renewal-administration-reservation.md
docs/rebuild/pilot-doctor-guide.md
```

## Rollback

Stop on failure; retain current data, schema, configuration and prior source. The driver retains
the prior source archive, the prior environment and the prior static inventory. A failed act
leaves release `84fd9e8a` serving.

**No provider call. No B2 call. No restore drill. No new capture.** The retained capture
`20260922T043002Z-7d766ca1` and the independent-key restore proof
`f2df7c56486b5d09de254ee7ab69c30697ca2b6487b84b700fe06c7fa7f49d0f` are reused unchanged.
