# Declaration — install the denial-heading repair, September 23, 2026

A code-only release. **No migration, no schema change, no unit change, no static asset change, no
provider call, no backup, restore, readback or renewal act, no ledger reservation, and no change to
any credential, policy, mode or identity.** No Word adapter (C#) source changes, so the installed
Word runtime is untouched.

## Why this exists

The clinical-context milestone (owner, 2026-09-23): a denial heading that is also a form question
(`Review of systems: negative for the following:` above `Symptoms: chest pain`) came back with the
denied finding SUPPORTED, pre-filled and finalizable on a review tick. This PR (`fix/denial-heading-governance`) carries:

1. **Headings govern the answers they introduce.** A line that visibly ends in a colon, a sentence
   that ends on a forward pointer (`following`, `below`, `as follows`, `the following <word>`), and
   a correction (`correction` where a line, value or sentence starts; failing closed except for
   listed treatments and targets) govern the answers after (or, for corrections and closing
   headings, before) them, by position in the note, judged at every place the selected text occurs
   for that question. A governed answer is a decision for the clinician: never pre-filled, never
   offered for one click, its candidate kept beside the lines that govern it (up to three governing
   spans per line, what changes meaning first). The qualified Word form: labelled lines never govern.
2. **Finalization, the page and save apply the same reader**, recomputed from the notes: a governed
   `supported` answer, an accepted governed suggestion, and a governed answer cleared to nothing
   cannot finalize without a decision; drafts from earlier releases are shown by the same rule; a
   page opened before this release cannot turn the pre-filled text into a decision; finalized
   records are never re-described. Read-only count at 2026-09-23T20:50:20Z, judged by this release's own
   page and finalization readers: 12 non-finalized encounters, 3 with answers (51 answers); **0** newly
   shown held and **0** refused at finalization.
3. **The qualified Word form's wording/answer conflicts name** the statement, its chosen wording and
   the answers involved, on the document page only (the flash message stays general).
4. The doctor guide and the notes-form aside describe the rules, the fixed vocabulary and its limits.

## Bounded change

| what | exactly |
|---|---|
| release marker | `02c29f991e50327525ebc6b4498f5cde08f78bbb` → the target, replaced by the driver, never by hand |
| source | fast-forward only, to the exact reviewed target |
| files changed | the source scope below, plus this declaration and its adapter |
| systemd units | **none** |
| public assets | recollected by the driver; **no** entry may change (no static source is in the range) |
| services | doctor, admin and worker restarted onto the new release by the driver |
| timing | the act runs outside 04:25–05:15Z so it cannot overlap the local capture or the offsite run |

**MUST change:** the served `/health/` release on doctor and admin equals the target; the notes
form's aside states the heading and sentence rule. Each checked read-only after the act.

## MUST NOT change, each asserted before and after the act

Baseline read-only at 2026-09-23T20:17:40Z (`.runtime/denial-heading-install-20260923/pre-declaration-snapshot-20260923T201740Z.json`);
identical to the 09:34:30Z snapshot except `core_servicehealth` content, which the publisher rewrites.

| quantity | declared value |
|---|---|
| tables | 36, exactly the set below |
| applied migrations | 36 rows; head stays `0018_servicehealth` |
| encounters | 29 (17 finalized) |
| patients | 4 |
| jobs | 29 |
| ledger entries | 47 |
| payments | 3 |
| usage rows | 29 |
| templates / template versions | 15 / 24 |
| organizations / memberships | 2 / 10 |
| service-health ROWS | 1; the row's content moves, the count does not |
| offsite `budget.json`, `renewal/*`, policy, allocation contract | byte-identical: this release reserves and renews nothing |
| the seven pinned offsite control sources | byte-identical |
| every systemd unit, override and enablement link | identical |
| documents, originals, exports, balances, audit history, MFA, synthetic-only, public maintenance | untouched |

⚠️ `core_auditevent`, `django_session`, `core_loginattempt`, `core_user.last_login` and
`otp_totp_totpdevice` (`last_used_at`, `last_t`) are expected to move from ordinary and
administrator sign-ins, and `core_servicehealth` content from the publisher. They are named
rather than omitted.

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
docs/rebuild/pilot-doctor-guide.md
rebuild/core/generation.py
rebuild/core/tests/test_candidate_suggestion.py
rebuild/core/tests/test_denial_heading_governance.py
rebuild/core/tests/test_wm_conflict_messages.py
rebuild/core/tests/test_wm_workflow.py
rebuild/core/views.py
rebuild/core/wm_conflicts.py
rebuild/templates/encounter_detail.html
rebuild/templates/encounter_form.html
```

## Rollback

Stop on failure; retain current data, schema, configuration and prior source. The driver retains
the prior source archive, the prior environment and the prior static inventory. A failed act
leaves release `02c29f99` serving.

**No provider call. No B2 call. No restore drill. No new capture.** The retained capture
`20260922T043002Z-7d766ca1` and the independent-key restore proof
`f2df7c56486b5d09de254ee7ab69c30697ca2b6487b84b700fe06c7fa7f49d0f` are reused unchanged.

## Review and owner decisions

Fifteen rounds of adversarial refutation (four read-only lenses each, the last round two lenses over
the final delta), mutation proofs on scratch copies, and the retained-response replay. The owner chose,
on 2026-09-23, to ship after a pre-merge round with no HIGH on plausible typed, dictated or pasted
clinical text, with crafted-input cost edges and the listed reading limits documented in the doctor
guide rather than chased further. The final round's cost findings (page, save and finalize up to about
3 s on crafted notes of tens of thousands of one-character lines; a realistic 600-line note is 1.7-2x
the installed release) are accepted on that basis.
