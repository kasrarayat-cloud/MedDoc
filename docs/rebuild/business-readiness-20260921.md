# Business-readiness verification — September 21, 2026

This milestone preserves the private rebuilt application and prepares an inactive
first paid release. It adds two bounded repairs; it does not authorize production
payments, public ingress, patient data, provider calls or a second billing platform.
The exact merged/installed revision and CI receipt are recorded in
`rebuild/.runtime/business-readiness-20260921/FINAL-REPORT.md` and the durable
checkpoint after activation. Starting repository/operations were
`ab4d3659e43c5591477017d9685a7e3d50f8c59b`, application
`97597c2972072821a27f4ce840775c07fca48a63`.

## Authentic costs and supported reconciliation

The protected read-only expected-usage manifest covers September17 at
08:26:13.354870UTC through September21 at00:49:28.179094UTC. It contains nine
Anthropic operations ($0.155370000000 configured cost; $0.233055000000 original
charge) and six Deepgram operations ($0.004890900700 configured cost;
$0.007336351050 original charge). Two simulated usage rows are excluded. The
ledger has no cost reconciliations or unsettled/unproven provider operations in
this export. Two historical missing-receipt exceptions remain. No clinical
content, patient identifiers or credential values are included.

The protected provider-evidence directory was empty. Saved September17 access
reports contain refused Anthropic cost and Deepgram request/billing reads, not
actual costs. No denied credential was retried. The desktop's login-page state
is owner-reported and does not establish authenticated export availability or
shared filesystem access. Exact provider account/workspace/project IDs were not
recorded in local receipts or nonsecret configuration; the package supplies the
request/resource identifiers so the desktop need not reconstruct the ledger.
A historical model resource ID is not relabelled as an HTTP request ID.

The exact-decimal preview preserves estimates and customer caps; unavailable
actuals/differences are null, never zero. No authentic evidence was imported and
no live adjustment was applied. Obtain original owner-authenticated scoped usage,
cost reports and issued invoices where available with account/period/currency/
retrieval provenance. Shared-account aggregate costs remain aggregate unless an
existing approved allocation supports more detail. Card top-ups, subscription
fees, taxes and provider credits are not inferred as per-request costs. Current
rate arithmetic is not invoice reconciliation.

The existing importer is a manual MFA-protected per-usage form. No bulk format is
implemented or claimed. Preserve original bytes in the protected evidence store,
validate regular single-link0600 files under0700, hash and record provenance, and
review the actual format before parsing. Reject malformed, ambiguous, unsupported
or partial evidence; inspect archive paths before any extraction. A hash binds
bytes, not authenticity. The private `DESKTOP-BILLING-HANDOFF.md` contains the
intake/correlation/preview steps and the minimum desktop action. A local path is
not proof of delivery to the desktop.

The one-to-one append-only reconciliation writer refuses duplicate, overlapping
or corrected second entries without mutation. Its existing credit/cap/pending-fund
rules remain intact; no live card charge/refund follows. Do not silently upgrade
a provider report into a later invoice or overwrite history. A later correction
requires a specific reviewed append-only evolution, not a second mock batch.

## Demonstrated repairs

**Evidence classification.** Previously any reconciliation with a reference/hash
was reported as invoice reconciled, including a usage export, while summary text
could still claim none were reconciled. Explicit immutable evidence kind now
separates provider reports, invoices and unclassified prior records across the
writer, audit and finance views. The form requires a choice; the migration adds
only the classification column/check and leaves financial amounts unchanged.
Example: a verified usage-cost export displays “Provider-reported actual · not
invoice reconciled”; an old unspecified reference remains “invoice status
unknown.” Administrator classification is not automated provider authentication.

**Payment namespace.** The existing signed sandbox webhook rejected live events
but accepted unsupported Connect/account or organization-context namespaces
before recording/settlement. A shared validator now refuses those fields at both
HTTP ingress and durable event recording, before any event ID can be consumed or
funds credited. Ordinary own-account events may omit both fields; the endpoint
credential provisioning binds its owner. Example: a validly signed foreign
Connect event returns400 and leaves funds/event history unchanged; the legitimate
own-account event with the same ID can still settle exactly once. This is not an
arbitrary unsigned attacker bypass or a claim of production qualification.

Focused PostgreSQL tests and a separate internal reviewer cover both changes.
The original reproductions and harness failures/corrections are retained in the
protected review folders. Existing tenant/MFA/clinical/Word/payment acceptance
proofs are reused where unchanged, not replayed as new campaigns. Required CI
and installed preservation/behavior checks are recorded separately at close-out.

## Clean paid-release preparation

An actual empty disposable PostgreSQL initialization produced no users, patients,
wallets, payments, grants or other core data; no private seed/import was run. One
existing registration→verification test proves exactly one $10 personal
promotional grant and $0 purchased funds. These are isolated fixtures with no
provider/email/live-database writes.

Current hard gates deliberately keep the application synthetic and sandbox-only;
its launcher/role tools pin the private namespace. Payment tables do not partition
live/test mode internally. Production therefore requires a separate empty
DB/encrypted state and a reviewed fixed target profile with account/mode/origin
binding. A credential swap cannot safely promote this private database. The
[production checklist](production-activation-checklist-20260921.md) and
[payment contract](production-payments-checklist-20260921.md) give exact resource
names, restricted capabilities/events, verified-owner/MFA bootstrap, acceptance,
pause and rollback. They are inactive preparation, not installed production.

Preserve supported DOCX/AcroForm templates, typed notes, supported transcription
with correction/review, original-format export, isolation and explainable enabled
coding. Do not advertise arbitrary/scanned forms or CPT. Original Word acceptance
and sandbox payment lifecycle remain complete; natural dictation/new SOAP Word,
authentic costs, live payment setup/acceptance, independent engagement,
outside-host notification coverage and patient-data permissions remain distinct.

## Protected artifact locations

- `rebuild/.runtime/business-readiness-20260921/expected-usage-manifest.json`
- `rebuild/.runtime/business-readiness-20260921/exact-decimal-preview.json`
- `rebuild/.runtime/business-readiness-20260921/quillmd-billing-correlation-20260921.zip`
- `rebuild/.runtime/business-readiness-20260921/billing-handoff-index.json`
- `rebuild/.runtime/business-readiness-20260921/reconciliation-review/ASSESSMENT.md`
- `rebuild/.runtime/business-readiness-20260921/payments-review/REVIEW.md`
- `rebuild/.runtime/business-readiness-20260921/production-review/REVIEW.md`
- `rebuild/.runtime/business-readiness-20260921/FINAL-REPORT.md`

These nonpublic operational artifacts include financial correlation identifiers;
keep their protected storage. No new external billing, backup, alert or review
credential/integration was created. The separate backup timer, audit ticket,
policy, historical reservations and independent restore proof remain preserved.
