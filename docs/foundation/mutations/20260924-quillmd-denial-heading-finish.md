# Declaration — install the finished denial-heading repair, September 24, 2026

A code-only release. **No migration, no schema change, no unit change, no static asset change, no
provider call, no backup, restore, readback or renewal act, no ledger reservation, and no change to
any credential, policy, mode or identity.** No Word adapter (C#) source changes, so the installed
Word runtime is untouched.

It installs everything from the serving release `02c29f99` to the target: PR #1284 (merged as
`2d900862`, never installed; its declaration `20260923-quillmd-denial-heading-install.md` is kept
unchanged as the record of that plan) and the finish PR (`fix/denial-heading-finish`).

## Why this exists

The clinical-context milestone (owner, 2026-09-23), finished:

1. **PR #1284's repair.** A heading (a line that visibly ends in a colon), a sentence ending on a
   forward pointer, and a correction govern the answers they introduce: each is a decision for the
   clinician, never pre-filled and never offered for one click, with the candidate kept beside the
   lines that govern it; the page, save and finalization apply the same reader, recomputed from the
   notes. The qualified Word form's wording/answer conflicts name the statement, its wording and
   the answers.
2. **The older-form case, followed through.** The pilot guide documented that on question/answer
   tables, placeholders, fillable PDFs and the WM IOV form a heading that is itself a form question
   could return the denied finding ready. Reproduced with stored mappings from real uploads: tables,
   placeholders and fillable PDFs hold it through finalization and export (tests added for the PDF
   and placeholder forms). **The qualified WM IOV form did not**: labelled lines never governed there,
   so `Right tributary row 11: anatomical location: none of the following:` left
   `Left GSV at the SFJ: reflux time (ms): 700 ms` and `Right impression: reflux or absence: reflux
   positive.` READY on both `02c29f99` and `2d900862`. Now a question whose own value ends in a
   colon governs the answers after it (forward only); a prewritten statement's approved wording
   (`… By:`) and an unanswered question do not, and words inside a value are still not read there.
3. **The surviving mutant M184 is separated**: a correction after a period and Word's namespaced
   markup (`…polyp.<o:p> Correction: …`) is read; without that alternative the whole line came back
   ready.
4. **The governing heading is on the review page** when it lies far from the answer: a family-history
   heading twenty lines above, and a denial heading beyond a full window of sub-headings (the rest are
   counted), each asserted on the rendered page.

Read-only count at 2026-09-23T22:37:43Z, judged by the target's own page and finalization readers:
29 encounters (9 draft, 3 review, 17 finalized), 3 non-finalized with answers (51 answers, none on
the qualified Word form); **0** newly shown held and **0** refused at finalization.

## Bounded change

| what | exactly |
|---|---|
| release marker | `02c29f991e50327525ebc6b4498f5cde08f78bbb` → the target, replaced by the driver, never by hand |
| source | fast-forward only, to the exact reviewed target |
| files changed | the source scope below, plus this declaration and its adapter |
| systemd units | **none** |
| public assets | recollected by the driver; **no** entry may change (no static source is in the range) |
| services | doctor, admin and worker restarted onto the new release by the driver |
| timing | outside 04:25–05:15Z, so it cannot overlap the local capture or the offsite run, and before 2026-09-24T10:25Z, inside the retained capture's 30-hour window |

**MUST change:** the served `/health/` release on doctor and admin equals the target; the notes
form's aside states the heading and sentence rule. Each checked read-only after the act.

## MUST NOT change, each asserted before and after the act

Baseline read-only at 2026-09-23T22:37:23Z (`.runtime/denial-heading-install-20260923/pre-declaration-snapshot-20260923T223723Z.json`);
identical to the 20:17:40Z snapshot except `core_servicehealth` content, which the publisher rewrites.

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
docs/foundation/mutations/20260923-quillmd-denial-heading-install.md
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

## Recovery evidence

**No provider call. No B2 call. No restore drill. No new capture.** Two retained, already-qualified
records, in the shape the business-readiness, admin-console and Word-multicolumn activations used
(a later authenticated capture of the same mechanism beside an earlier independent-key restore):

| record | identity |
|---|---|
| retained capture (the 30-hour window applies to it) | `20260923T043000Z-2031049f`, the scheduled 04:30Z capture: complete, 36 tables, 226,167 rows, 64 files, source `d9660e34`, manifest ciphertext `a6617fd69f4f7da84f6f4c40a52bec53b32dc9cc77300736caaa66052ad3c987`; offsite `20260923T050000Z-fe49b5e8` authenticated with a ciphertext-sha256 readback of all 66 objects (18,516,232 B) |
| independent-key restore proof | `20260922T043002Z-7d766ca1`, restored with the vault-returned key on 2026-09-22 (result `f2df7c56486b5d09de254ee7ab69c30697ca2b6487b84b700fe06c7fa7f49d0f`, manifest ciphertext `c3c4994fa4b50c51e75197e2ba57f8e2427daaf5929539c01498548da2083011`) |

The driver authenticates both with the operating key, requires the same database container, table
set and invariants, and refuses a capture older than 30 hours. Nothing is widened, re-dated or
re-run.

## Rollback

Stop on failure; retain current data, schema, configuration and prior source. The driver retains
the prior source archive, the prior environment and the prior static inventory. A failed act
leaves release `02c29f99` serving.

## Review and owner decisions

PR #1284: fifteen rounds of adversarial refutation, mutation proofs and the retained-response
replay; the owner's 2026-09-23 decisions (ship after a pre-merge round with no HIGH on plausible
clinical text; crafted-input cost edges and the listed reading limits documented) stand. The finish
PR's clinical change (the qualified-form value heading) gets its own refutation pass over the
finished diff before merge, and mutation proofs for each of its conditions.
