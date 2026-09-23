# Declaration — install the self-service doctor pilot release, September 23, 2026

A code-only release. **No migration, no schema change, no unit change, no provider call, no
backup, restore, readback or renewal act, no ledger reservation, and no change to any credential,
policy, mode or identity.** One public asset source changes: `rebuild/static/app.js`.

## Why this exists

The pilot task (owner, 2026-09-23): a self-service synthetic doctor must be able to find the
document workflow, choose the qualified WM IOV form, understand where notes and voice go, and
finish a fictional document, with honest instructions and without weakening any safeguard.
PR #1282 carries:

1. **Navigation, instructions and errors.** An empty workspace points to a supported form and to
   Patients; the only department is preselected; the upload page explains supported and refused forms
   before an upload; an engine refusal gains a next step keyed on the engine's own refusal text, and an
   encrypted Office file or old `.doc` is named as such; a new document without a patient links to
   Patients; the WM IOV form page lists its prewritten statements and the answers each wording needs;
   signature rows name the exact account name.
2. **A clinical attribution defect.** On ordinary forms *I reviewed this answer* rendered
   pre-ticked from another clinician's review, so a second clinician's plain Save re-stamped every
   review, the signature included, to themselves; a carried-forward "Leave blank — reviewed" row did
   the same. The box now reflects only the reader's own review, as the qualified Word branch already
   did; a carried blank keeps the review actually posted; a removed review is recorded in the existing
   `encounter.answers_saved` audit event (`withdrawn_reviews`, no schema change).
3. **Voice.** CSP `media-src 'self' blob:` so the recording preview plays (it was blocked);
   the voice quote lasts 1800 s so a slow dictation is not discarded (generation keeps 600 s), and a
   change made elsewhere is named as the reason; browser size check, auto-stop notice,
   empty-transcript and clean-up guidance; MPEG frame-sync check aligned with `core/audio.py`.
4. **The one-click suggestion gate withholds more, never less.** It withholds in every case it did
   before, and also under a denial line that ends in a colon (any colon width, invisible trailing
   characters ignored) or points at other lines (`ROS: negative for the following:`, `Pertinent
   negatives:`, `Patient denies the following`), reading each line both as written and with invisible
   characters removed. Answer statuses on question/answer tables, placeholders, fillable PDFs and the
   WM IOV form are exactly the installed release's; on underlined-Tab forms a heading ending in a
   fullwidth colon or an invisible character now counts as the ASCII one already did. No prompt or
   model change.
5. **Answer line breaks.** Answers are stored with plain line breaks instead of the browser's CRLF, so a
   two-line answer can finalize on a fillable PDF and no longer doubles its break in a Word table
   cell. The PDF character refusal names the question by the doctor's label and names the
   character (the document engine's one change: that message and its label source).
6. The rewritten doctor guide.

The range also carries PRs #1280 and #1281 (merged, never installed): the publisher verifier and
its script, the offsite renewal test, and documentation. None of the seven allocation-pinned
offsite control sources changes.

## Bounded change

| what | exactly |
|---|---|
| release marker | `d9660e34f9d3217369212ffc7d0d8302d4ad568c` → the target, replaced by the driver, never by hand |
| source | fast-forward only, to the exact reviewed target |
| files changed | the source scope below, plus this declaration and its adapter |
| systemd units | **none** |
| public assets | recollected by the driver: only `app.js`, its hashed and compressed forms and `staticfiles.json` may change; every other entry identical |
| services | doctor, admin and worker restarted onto the new release by the driver |
| timing | the act runs outside 04:25–05:15Z so it cannot overlap the local capture or the offsite run |

**MUST change:** the served `/health/` release on doctor and admin equals the target; the doctor
site's `Content-Security-Policy` carries `media-src 'self' blob:`; the upload page shows the
supported-forms list. Each checked read-only after the act.

## MUST NOT change, each asserted before and after the act

Baseline read-only at 2026-09-23T00:52:23Z (`.runtime/doctor-pilot-install-20260923/pre-install-snapshot.json`).

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
.claude/settings.json
docs/rebuild/b2-renewal-desktop-handoff.md
docs/rebuild/offsite-renewal-operations-20260920.md
docs/rebuild/pilot-doctor-guide.md
rebuild/core/forms.py
rebuild/core/generation.py
rebuild/core/middleware.py
rebuild/core/tests/test_candidate_suggestion.py
rebuild/core/tests/test_doctor_pilot_self_service.py
rebuild/core/tests/test_tab_form_workflow.py
rebuild/core/views.py
rebuild/documents/engine.py
rebuild/ops/publisher_verification.py
rebuild/ops/test_offsite_renewal_integration.py
rebuild/ops/test_publisher_verification.py
rebuild/static/app.js
rebuild/templates/dashboard.html
rebuild/templates/encounter_detail.html
rebuild/templates/encounter_form.html
rebuild/templates/encounter_input.html
rebuild/templates/login.html
rebuild/templates/template_detail.html
rebuild/templates/template_upload.html
scripts/activate-pilot-blank-install.py
scripts/verify-publisher-run.py
```

## Rollback

Stop on failure; retain current data, schema, configuration and prior source. The driver retains
the prior source archive, the prior environment and the prior static inventory. A failed act
leaves release `d9660e34` serving.

**No provider call. No B2 call. No restore drill. No new capture.** The retained capture
`20260922T043002Z-7d766ca1` and the independent-key restore proof
`f2df7c56486b5d09de254ee7ab69c30697ca2b6487b84b700fe06c7fa7f49d0f` are reused unchanged.
