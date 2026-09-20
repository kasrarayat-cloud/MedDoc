# Private beta operations milestone — 2026-09-20

**Integration record, before activation.** Candidate repairs below have focused
evidence. Exact merged CI, private activation, installed backup timer and served
browser verification are pending until the lead appends their results. Source
inspection and isolated tests are not execution evidence for the running build.

Authoritative continuation: `/opt/meddoc-pro/rebuild/.runtime/CHECKPOINT-LATEST.md`.
This record supplements historical reports; it does not rewrite them. The current
system is the preserved rebuild. There is no migration, restart of the rebuild,
broad cleanup, public promotion or real patient data in this task.

## Baseline and evidence vocabulary

At 08:13 UTC, repository main was
`db5f54524a2b3bbda4eaa28a46612e9523966697`. Doctor/admin health separately reported
`928897f4e934f1912855f96662617c6d0d9df629`; each service startup proof, including
worker, matched its actual systemd PID and that release. The existing difference
was documentation, not an unverified application deployment.

All evidence paths below are relative to `/opt/meddoc-pro/rebuild/.runtime/`.
The current protected evidence directory is `overnight-completion-20260920/`.

- **Complete within stated scope:** demonstrated result, including its limits.
- **Defective in served baseline; candidate repaired:** reproduced failure and
  focused green check, awaiting actual activation and affected served checks.
- **Unverified/deferred:** required interaction or execution has not occurred.
- **External dependency:** necessary authorized access or evidence is absent.

## Compact requirement-to-evidence checklist

| Requirement | Current status and evidence |
| --- | --- |
| Separate doctor/admin, authentication and administrator MFA | Prior private implementation complete. Current health/PID/release checks: `overnight-completion-20260920/recovery-revisions-before.json`. Normal preview sign-in replaces browser Basic authentication. New admin finance views retain staff/MFA and clinical membership gates; candidate checks below. |
| Invitation, recovery, individual accounts and welcome credit | Completed milestone retained: `email-verification-20260920/invitation-recovery-closeout-20260920.md`. Original invite accepted/reuse refused; exactly one $10 grant; password reset invalidates required sessions and preserves unrelated/admin sessions. Owner confirmed recovery inbox receipt and new-password login. Send-only provider telemetry limit remains stated; no email campaign repeated. |
| Word upload, versioned mapping, evidence, review and export | Prior complete WM IOV workflow and native Word acceptance retained: verified 20260919 package, Word 365 Version 2608 Build 20326.20144, five documents / 43 pages, unchanged original hashes. Partial exports have two answered mapped inputs and 88 missing, with separate statement/signature replacements. No repeat of this acceptance. |
| Custom typed and voice SOAP | Complete bounded typed and recorded synthetic-speech workflows: `soap-verification-20260920/expected-versus-actual.md` and `quillmd-soap-review-20260920.zip`. Two genuine exports/hash matches, correct S/O/A/P, negations/missing/conflict review and exactly-once charges. Machine speech is not human dictation. New SOAP native Word appearance remains deferred; no claim about arbitrary/scanned forms. |
| Natural human dictation | Deferred by owner availability. Preserve encounter `0211ea6d-a705-4232-81c1-1eb027d9e774` and `human-dictation-20260920/preparation-summary.md`. No synthetic substitute or provider call. |
| Department/organization isolation and finance confidentiality | Prior API/file/export/job negative evidence retained. Current candidate regression adds financial staff without clinical membership, own-user versus foreign billing and hidden other-payer balances. `admin-evidence-final.json/.log`: nine isolated tests pass. No separate finance membership role was invented. |
| Practical administration and charge explanation | Served baseline truncated accounts/history and lacked a complete individual-charge drill-down. Candidate adds bounded searchable pagination, matching usage totals, full audit navigation and `/console/jobs/<uuid>/` plus permitted `/billing/jobs/<uuid>/` evidence views. Provider identifiers/quantities/rate snapshot, 1.5× charge, holds, promo/paid movements and balances remain distinct. Actual candidate/served browser execution pending. |
| Accepted usage billing and concurrency | Existing policy in `cost-definition.md` retained: exact 1.5× defined cost within authorized limit, excess absorbed, personal promo first, fixed payer, no undisclosed card charge. Reproduced wallet/job lock inversion repaired with after-commit payer-scoped pending reconciliation. `worker-financial-focused-green.json/.log`:31 focused tests pass, including rollback and interruption fixtures. Crash after commit/before callback can leave durable pending reconciliation for later authorized processing. |
| Immutable financial/provider evidence | QuerySet update/delete bypass of model-only reconciliation guard reproduced in isolated DB. Candidate migration 0015 freezes every reconciliation field except valid ledger status; no old row rewritten. Actual-host trigger installation must be recorded at activation. Two historical missing receipts remain exceptions; no fabricated evidence. |
| Stripe sandbox | Complete actual sandbox campaign retained: `stripe-payment-20260920/acceptance.json` and `final-ledger.json`. Funding, decline, duplicate delivery, controlled retry, out-of-order handling and refunds passed. Controlled redelivery does not claim Stripe's automatic retry schedule. No live payments or repeat campaign. |
| Provider cost reconciliation | External dependency: designated `provider-evidence/` absent. Captured provider quantities priced at immutable configured rates are not invoice-reconciled cost. SOAP batch cost $0.0151115 / charge $0.02266725 remains valid configured arithmetic. Fixture reconciliation checks exercise validation, duplicate protection, proportional credits and append-only adjustments without authentic provider invoices. |
| Lost/stale clinical edits | Stale mapping POST silently superseded newer labels: candidate now requires current mapping UUID, refuses409, retains submitted labels and shows feedback. Existing encounter revision/source protections also pass focused checks. No clinical generation prompt changed. |
| Invitations after revocation | Inactive employee invitation previously consumed the invite while leaving membership revoked. Candidate409 leaves membership, invite and welcome grant unchanged; no unauthorized reactivation. |
| Malicious uploads/parser confinement | UTF16/32DTD and renamed declared active content reproduced with harmless fixtures. Candidate inspects parsed DTD and content/relationship types.21 Django plus 8 actual isolated parser checks pass; no executable macro, exploit network request or exfiltration occurred. Sandbox ownership/Landlock/seccomp protections retained. |
| ICD-10-CM and CPT | Existing explainable code-token suggestions remain source-supported and service-date/version aware. Three contiguous loaded ICD-10-CM releases cover 2025-10-01 through 2027-09-30; old September2026-refresh warning is superseded by recorded FY2027 import. CPT stays disabled: zero licensed releases, rights/content not verified. |
| Local encryption and recovery | New actual backup/restore `20260920T081236Z-04a49ff8`/`c965470cd3de6157`:35 tables, 225,581 rows, 42 files, all hashes/invariants match, 8 triggers, network none, tmpfs/no swap, zero decrypted files/providers/workers; owned container removed. `backup-attempt-01.json`/`restore-attempt-01.json`. Local live data encrypted; keys still colocated. |
| Local backup schedule/failure visibility | Omission confirmed: no QuillMD timer. Candidate daily 04:30 UTC service wraps existing backup with locking, limits and redacted immutable attempts/status.12 fixture checks plus independent reproduced-finding retest pass; invalid-lock failure cannot remain green behind old success. Installation and one actual service capture pending. Local status/journal is not external alert delivery. No retention deletion. |
| Offsite/key custody | External dependency: `backup-secrets/b2-offsite.json` absent; no approved remote upload/restore. Existing adapter validation and handoff retained. Independent recovery-key custody remains unverified. No purchase or credential creation. |
| Independent security testing | Reviewer host qualification is completed evidence, access remains inactive. This task's internal review is not independent penetration testing. Reviewer identity/key/window/contact and engagement still required. |
| Public/real-patient release | Not approved. Public app/admin maintenance, synthetic-only gate, administrator MFA and inactive reviewer access remain required. Patient-data agreements/regions/retention and independent review remain open. |

## Current findings and verification boundaries

Detailed current reports:

- `overnight-completion-20260920/security-clinical-review.md` and preserved red
  upload/mapping/invitation evidence;21 Django / 8 parser green checks.
- `overnight-completion-20260920/worker-financial-review.md`, initial failed race
  and evidence-mutation checks,31 focused green checks and independent refutation.
- `overnight-completion-20260920/admin-evidence-final.json`, nine isolated tests,
  and `admin-independent-refutation.json`. Earlier fixture failures remain.
- `overnight-completion-20260920/recovery-review.md`, inventory/revision proof,
  actual restore,12 scheduler fixture checks, original lock-status refutation and
  `scheduled-backup-lock-status-refutation-retest.json`.

The original data/financial baseline is `baseline.json`. Final comparison must
explain every expected new audit/session row, preserve original records and
balances, and keep SOAP artifacts/human draft unchanged. No new live provider,
Stripe or email call is needed to verify these repairs.

## Consolidated external dependencies

1. **Offsite and custody:** approved private B2 bucket/prefix and restricted key
   securely installed in `.runtime/backup-secrets/b2-offsite.json` (claude, 0600),
   using `offsite-backup.md`; separately held recovery keys/custodian evidence.
2. **Authentic provider costs:** account usage/cost/invoice evidence, applicable
   rates/discounts/credits and accepted allocation in `.runtime/provider-evidence/`
   (0700), transferred through protected access. Ordinary request keys do not
   grant this reporting evidence.
3. **Independent review:** engaged tester, public key, approved UTC window and
   emergency contact through the existing `pentest-scope.md` handoff; access must
   remain inactive until that scoped engagement is approved.
4. **Licensed/clinical release:** legitimate CPT entitlement/content/usage rights;
   patient-data agreements and processing/retention controls. No automatic
   contracts or purchases. Human dictation and new SOAP desktop Word appearance
   await actual owner/workstation interaction, separately from prior acceptance.
5. **Operations ownership:** independent recovery custody and approved external
   failure-alert route/receiver acknowledgement remain unverified. Local status
   is available preparation; no unsolicited notification is authorized here.

No secrets belong in chat, Git or reports. These are release dependencies, not a
new technical option menu. Follow [incident and recovery instructions](private-beta-incident-recovery.md).

## Activation closeout — pending lead evidence

Append exact PR/head/merge CI citations, repository versus all three served
revisions, declaration/rollback result, actual migration and service/timer state,
served browser outcomes, preservation comparison and remaining limits here.
Until that evidence exists, candidate repairs and prepared units are not claimed
as running. Public release remains refused by the unmet gates above.

### Supplemental coding and reconciliation checks before activation

`overnight-completion-20260920/provider-reconciliation-and-coding-review.md`
records actual read-only state: zero provider-cost reconciliations, two historical
real receipt gaps, three loaded ICD-10-CM releases and zero CPT content. Ordinary
request keys do not provide invoice evidence. The established process is manual
MFA-protected per-usage reconciliation entry, not an automated invoice importer or
a claim of independently verified invoice authenticity. Eleven invalid amount/
evidence inputs add no adjustment; existing duplicate, proportional credit and
append-only adjustment coverage is reused. Twenty-three focused checks pass.

Synthetic stored CPT descriptors exposed an additional licence-display defect:
absent, expired or different-feed entitlement could still show old suggestions.
The candidate hides those descriptors while retaining historical rows and accepted
decisions; ICD suggestions remain visible. Current matching entitlement retains
the existing service-date and acceptance checks. No genuine licensed CPT content
exists on this deployment. Root supplemental finished-diff refutation found no
concrete counterexample; this is fixture/source evidence, not live CPT acceptance.

Required private-browser CI now includes administrator MFA, no clinical patient
scope for financial administration, charge-page and audit accessibility, and an
honest empty-filter state. Actual CI and served outcomes remain to be appended.
