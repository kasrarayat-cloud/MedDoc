# Declaration — bounded private typed and voice SOAP verification

Date: 2026-09-20. Owner authorizes this milestone in the active session.

## Scope before the act

The actual existing private synthetic application is served from `/opt/meddoc-pro/rebuild`, release `928897f4e934f1912855f96662617c6d0d9df629`, through protected `https://app.quillmd.com:9443`. No deployment is proposed. This declaration may run from its isolated documentation worktree using absolute paths to the unchanged existing application and protected runtime browser helpers; no compose or hosting command runs from that worktree.

The library has no custom SOAP template. Upload one engineering-created blank DOCX, expressly labelled synthetic and not doctor supplied, then review/save mapping version2 through the normal application. The original fixture is `synthetic-custom-soap-20260920.docx`, SHA256 `ed297f82b5a7357b144537ee5f78490f5efffbcc7146fc07f0699a1c7a7ee204`, 37843bytes, with8 blank answer cells across Subjective, Objective, Assessment and Plan. Use existing synthetic owner2247e403-a830-4807-9a34-6903b95a0f50, patient716c0c55-abad-420a-9c71-07fac3acd991 and X-ray department46a5abdd-36f1-41f0-968f-8c09c39d9daa.

Create exactly two encounters with the same frozen synthetic left-ankle scenario. One uses typed notes. The other records locally synthesized speech using actual browser MediaRecorder, submits it through the application to Deepgram, reviews/corrects the transcript through the notes form, then generates. Retain raw transcript, raw Anthropic responses and clinician corrections separately. The declared maximum is THREE actual provider requests: two Anthropic generations and one Deepgram transcription, with SUM of displayed authorized charge ceilings at most USD1. No automatic retry or extra request after uncertain completion. Preserve all failed-attempt evidence and incurred costs; a further provider request requires its own concrete qualification before execution.

Review and finalize these two encounters through normal application permissions, source/review validations and CSRF protections. Attempting finalization with the documented unresolved pain-score conflict must refuse; then resolve only that score by clinician edit, retain both original source lines, review all8 inputs and finalize/export. Allergies and vital signs are unspecified and stay blank/missing with the template's visible legend. Assessment and plan are solely those explicitly supplied in the frozen synthetic script. No clinician inference, real patient data, SQL finalization or forged provider receipt.

## Baseline captured before any application mutation

Protected runtime directory: `rebuild/.runtime/soap-verification-20260920`.

- `protected-rows-before.json`: 2026-09-20T05:21:11Z,97751bytes, SHA256 `714f12c01d1ba4ad9ce3b0fd5cb055f2ead7b910eddac009dbc12324673b9361`.
- `billing-before.json`: 2026-09-20T05:20:27Z,14196bytes, SHA256 `bbd1c5c5341f7e43543dac26704c3c166603d6dcdf106db2b763052d57231523`.
- Existing counts:11Users/1MFA/2Organizations/3Departments/10Memberships/8Invitations/3Patients/11Templates/18MappingVersions/14Encounters/14Jobs/12Reservations/14Usage/11Receipts/27Ledger/22Wallets/3Payments/2Refunds/7WebhookEvents/611AuditEvents. No pending jobs.

## Required changes and preservation

Exactly1template,2mappingversions and2encounters added. Successful bounded workflow adds3jobs,3receipts,3usage settlements and at most3 new reservations, each one charged exactly1.5 times its applicable recorded cost. Original ledger/usage/receipt/payment/refund/webhook/history rows stay immutable. Only the acting synthetic account's authorized payer wallet balance/reserved fields move by the exact recorded reservations and charges; no paid top-up or welcome grant. Existing users' authentication counters/last_login may change only for normal scope-control logins. Existing clinical documents, source files, final hashes and mapping records stay unchanged. Audit history grows from normal application actions. All count claims must be checked against actual outcomes, not assumed on submission.

Demonstrate same-department access and different-department/organization denial for both new encounters, files, exports, source/template and provider results, using existing synthetic account credentials. Verify ledger settlement stability using job-specific read-only evidence and harmless repeated downloads/reviews; do not rerun settled jobs merely to assert idempotency. Focused isolated regression coverage can verify concurrent/repeated settlement independently and must not be called actual provider execution.

## Gates and cleanup

No changes to public443 maintenance, private authentication/TLS, existing secrets, administrator MFA, service identities, reviewer restrictions, synthetic-only policy or patient-data gate. No emails, Stripe requests, Word milestone repeats, purchases or shared resource cleanup. New exports receive structural checks and any available separately labelled local rendering; new native Microsoft Word acceptance remains pending unless actually performed. Scope is this8field synthetic SOAP form, not arbitrary/scanned forms.

Preserve both exports, original, source scenario, raw provider results, expected-versus-actual report, costs and failed attempts in protected runtime evidence with file hashes/sizes. Normally sign out only helper-created browser sessions and remove only their temporary copied cookies/profile after qualification. Keep all new clinical/audit/provider/billing records. Update the continuation checkpoint. No owner decision is required for routine execution within this declared scope.
