# Retention and deletion readiness — operator preparation

**Status: read-only inventory implemented; policy unset; purge unavailable. B-L6 remains open.**
This is engineering preparation, not a legal retention schedule or authority to destroy records.
No retention duration is selected by this package. The owner/counsel must identify applicable
requirements and authoritative start events; unsupported events need additional engineering.
No production records were queried to prepare or verify this package.

## What exists and what is missing

The application has protected relationships, append-only financial/audit/receipt/mapping records,
immutable mapping confirmations and a finalized encounter UPDATE guard. It offers access,
correction, finalization, export, suspension, invitation revocation and session revocation.
It has no patient/account deletion route, durable legal-hold registry/enforcement, deletion-request
workflow, clinical tombstone mechanism or general purge operation. The finalized encounter guard
in migration 0003 applies to INSERT/UPDATE; it is not a blanket DELETE guard. Do not infer a complete
deletion policy or workflow from existing database constraints.

Existing worker cleanup is narrower and must remain in the inventory:

- `core/jobs.py:reap_abandoned_voice_uploads` removes unapproved over-limit audio whose quote
  exceeded the existing 2,400-second approval window, within the bounded audit-query window,
  only when no Job references that upload. This existing operational lifetime is not a newly
  selected medical-record retention duration.
- `reap_stray_submissions` removes stale normalized provider-submission artifacts after that
  window. Normalized artifacts are otherwise removed in a `finally` path.
- Failed/unclaimed uploads and exports have failure cleanup. New clinical code suggestions
  replace prior suggestions. MFA reset removes old authenticator devices; account/session
  revocation is access control, not patient data deletion.

None of those cleanup paths is called or changed by this readiness tool. Their interaction with
future legal holds must be designed and verified before a retention/deletion workflow is admitted.

## Exact source and route inventory

Counts are per database row or reference row. A referenced file is not necessarily present, unique,
or hash-correct. The tool never lists directories, opens recordings/templates/receipts/exports,
reads row bodies into Python, contacts providers or restores a backup.

| Data class | Current storage/source | Access/processing route and retention dependency |
|---|---|---|
| Account, organization, department, membership | User, Organization, Department, Membership; account-linked Django group/permission associations | login/recovery, team, admin account/membership/session controls; offboarding and access revocation differ from deletion |
| Invitation/recovery identity | Invitation, ClinicInvitation, Verification; expiring token hashes; recovery tokens derived from account state | invite/verify/recovery email; no patient details permitted in messages; email account retention remains external |
| Security state | Session, TOTPDevice, LoginAttempt; account session version | MFA and session/recovery controls; expired session/token cleanup and hold policy need explicit ownership |
| Patient identity | Patient names/references and department FK | patients UI/API, encounter creation; a patient's creation timestamp is not asserted to be the legal retention anchor |
| Original template | Template original path/hash; private original upload | template upload/original/review; a supposed blank upload can contain clinical data and must be classified accordingly |
| Mapping/provenance | TemplateVersion fields/review/backend/corrections/assistance; MappingConfirmation | immutable mapping review/history; mapping Jobs share the ledger and may retain blank-form provider output |
| Draft clinical record | Encounter notes, answers, template_review, service date and revision | typed/dictated notes, review/correction, coding, save; no general deletion route |
| Finalized clinical record and export | finalized Encounter and private export path/hash | finalization/download; preserve clinical meaning, immutable evidence, original export hashes and downstream copies |
| Job/request evidence | Job immutable config/pricing/scope, state, request/provider identifiers | generation/transcription/mapping queues; running/unknown/reconciliation states and held funds must be resolved before future disposition |
| Original recordings | Job.input_path references in private audio storage | upload, voice approval and Deepgram processing; approved originals differ from transient normalized submissions |
| Provider response/transcript | Job.result_path and historical ProviderReceipt.result_path reference rows, hashes; private receipts | raw generation/transcription/mapping receipts, reviewed transcript adoption and job-result access; both reference columns counted separately, not claimed as unique files |
| Clinical terminology proposals | CodeSuggestion explanation/evidence and accepted code references | coding review/acceptance; suggestion replacement already exists; immutable final record remains separate |
| Financial evidence | Wallet, LedgerEntry, Reservation, Usage, Payment, WebhookEvent, Refund, ProviderReceipt, CostReconciliation, PlatformCost | wallet/live billing, Stripe webhook, audit/reconciliation; references and receipts cannot be deleted or rewritten by this package |
| Audit and operational state | AuditEvent details; ServiceHealth reports | admin audit/services, incident evidence; identifiers in audit are never emitted by this tool |
| Terminology reference | CodeSet, Code | licensed/source release identity and historical code meaning; no purge proposal |

The code catalog covers all concrete core models and separately counts sessions/MFA. Framework
permission/group join rows follow account/access-control dependencies and are not claimed as an
independent purge inventory. A future new model must be assigned explicitly; the catalog test fails
when a concrete core model is absent.

## Routes outside aggregate database coverage

All remain **unverified** in this report, even if a policy file declares them ready for review.

| Route/copy | Required reconciliation before any future deletion plan |
|---|---|
| Private state volume | original/audio/receipt/export files, unreferenced files, crash residue and hashes; this command does not establish their existence or count |
| RDS automated/PITR backup | actual restoration windows and configured lifecycle; current hosting package's 35-day assumption is not counsel approval |
| AWS Backup RDS and EBS | actual recovery points, cross-account copies, vault/Object Lock constraints, restoration consistency and expiry evidence |
| Legacy encrypted local/offsite sets | existing synthetic host copies, manifests, leases, remote versions and custody; never erase them as a shortcut to launch or policy recovery |
| Anthropic and Deepgram | exact account agreements/settings, geography/features, processing and retained copies; advertising or model access does not verify account policy |
| Invitation/recovery email | provider records, mailboxes and security links; patient information stays out of ordinary messages |
| Stripe | payment/event/invoice metadata and provider records; patient information stays out of metadata |
| Host/SSM/security logging | operator/session/access/security records, backup-account log copies and custodians; no patient transcripts in routine logs |
| Downloaded exports | clinic/recipient/device/print custody; server deletion cannot prove downstream erasure |
| Legal holds | a complete, maintained hold register, authority, scope, coverage, expiry/release process and restoration reapplication; none is implemented by a declaration file |

## Policy format and command

Files:

- `rebuild/ops/retention/policy.unset.json`: complete catalog, every class unresolved, every duration null.
- `rebuild/ops/retention/policy.schema.json`: generated closed JSON schema; runtime validation also
  rejects incomplete/unknown/duplicate members, arbitrary anchors, booleans as days and invalid combinations.
- `core/retention_readiness.py`: explicit catalog, strict validator and COUNT-only implementation.
- `manage.py retention_readiness`: local operator command with no execution/delete switch.

A `review_window` requires an explicitly chosen supported timestamp, positive whole-day review
window and a schedule-document hash reference. The hash is only a reference: no signature, legal
review or authorization is inferred from it. The 365,000-day numeric ceiling is an implementation
bound, not a recommended period. Calendar-year/minor-age/last-treatment or other legal start events
are not silently converted to `created_at`; unsupported events require implementation and review.
`preserve` means this tool does not propose removal; it does not assert indefinite legal retention.
Protected financial/audit/original/mapping/final-export classes cannot receive a review-window rule
in this version. Their actual legal schedules still belong in the authoritative schedule.

From the selected **isolated, authorized** environment, first validate without a database query:

```bash
cd /path/to/selected/release/rebuild
.venv/bin/python manage.py retention_readiness --policy ops/retention/policy.unset.json --validate-only
```

For an authorized operator's aggregate inventory, after selecting the intended environment and
protecting the resulting operational report:

```bash
umask 077
.venv/bin/python manage.py retention_readiness --policy /secure/review-policy.json > /secure/retention-review.json
```

Preparation used only the isolated synthetic database on port 55702. No production inventory was
run. The full command starts its own PostgreSQL `REPEATABLE READ, READ ONLY` transaction before
any count, verifies read-only status, bounds statement/lock waits and refuses nested transactions
or non-PostgreSQL execution. It returns no partial report when a query/policy is invalid. Exceptions
are fixed labels; no paths, SQL, policy values or record details are echoed.

Output contains fixed class names, counts, policy hash, report time and fixed blocker codes. It does
not contain record IDs, names, paths, notes, answers, transcripts or row contents. Review-window
counts are **not deletion eligibility**. Missing anchors are reported separately. External copies,
policy authority and file integrity are not verified. Even a fully declared policy always returns:

```json
{"status":"blocked","purge_available":false,"policy_authority_verified":false,"deletion_eligibility_assessed":false}
```

A successful process exit means the inventory/validation command ran; it does not mean a retention
policy, purge operation or launch is approved. Do not use exit code zero as a readiness gate.

## Remaining B-L6 work and handoff

**External decisions/evidence:** owner/counsel-approved schedule and start events, hold authority and
custodians, downstream/provider/backup account terms and lifecycle evidence, clinic export custody,
data-request/breach procedures and responsibilities. This document offers no legal period recommendation.

**Engineering still required:** durable hold registration/enforcement across cleanup/clinical/file
and restored-backup paths; authenticated disposition-request/approval workflow; tombstone design;
reference-graph and active-job/financial checks; separately reviewed idempotent file/row disposition;
immutable ledger/audit/finalized export evidence; backup expiry reconciliation and prevention of
restoring disposed content into service; replay/failure/partial-outcome proof and audit records.
No purge function is implemented or authorized here. These are engineering blockers alongside the
external policy work, not an external-only delay. No launch date or V1 completion is claimed.

Only after the actual schedule, scope and hold/copy handling are concrete can that separate
engineering implementation and approval be defined. Do not bypass existing constraints or delete
clinical rows/files to make this readiness report appear complete.
