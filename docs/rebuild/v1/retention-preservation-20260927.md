# Retention preservation implementation — September 27 continuation

Prepared in isolated `v1/retention-enforcement`, based on reviewed4caa. **Not installed, not a complete disposition/deletion system.**

## Implemented behavior

- MFA-protected administration page and CSRF-protected API register immutable holds for a patient, document, department, organization or all clinical data. Stable request keys reject conflicting reuse. Metadata carries scope IDs and authority-document hashes, never clinical prose.
- A second active verified administrator records an append-only release with its own authority reference. Hash shape and account authorization do not establish authenticity of the underlying legal instruction; authorized custodians retain the actual documents.
- PostgreSQL preserves exact prior clinical row values before held patient/document/template/job/department/terminology-proposal updates or deletions. Clinician correction continues; prior values remain protected. Scope moves cannot detach held records. Finalized encounters reject DELETE as well as their existing UPDATE protection.
- Existing transient upload/submission cleanup now checks preservation under a shared transaction lock. Known encounter cleanup uses the encounter lock in enqueue order. Unattributed files are conservatively retained while any hold is active. Durable job/receipt/original/export references are never transient cleanup candidates.
- Held files receive immutable storage-key/hash/size/hold records; both files and prior row evidence survive release. No file is counted as removed unless it was actually removed. Database/file inspection failure preserves the bytes without overriding a completed provider result or exposing an error's contents.
- New database evidence is append-only and protected from TRUNCATE. Migration reversal refuses while any hold/release/preserved record/file exists. An empty installation can reverse; an admitted preservation installation needs a forward repair.
- The production restore verifier checks all39 exact triggers and13 pinned function bodies and now includes preserved files. The installed legacy backup reader remains byte-identical. This verifier still cannot prove reconciliation with a hold recorded after a backup's timestamp.

## Focused evidence and failures retained

Private artifacts: `rebuild/.runtime/retention-preservation-20260927/` in this worktree.

| Evidence | Actual result |
|---|---|
| First preservation controls |15 PASS1.490s, real isolated PostgreSQL55707 |
| First related run |99 discovered,2 failures/3 errors retained. One nonexistent test-module name; migration-reversal dependency caused remaining failure cascade. Not a green run. |
| Isolated schema recovery |`04-isolated-schema-recovery.json`: preservation tables empty; exact prior/new migration SQL repaired only test_quillmd_ci,34→39 triggers. No installed schema/data change. |
| Dependency repair proof |19 PASS10.404s: preservation, exact PostgreSQL catalog, all three historical0020 reversal cases |
| Final related checks |107 tests,106 passed/one instrument error: the CSRF check assumed Django's default cookie name; app uses a configured name. Corrected to settings.CSRF_COOKIE_NAME; the exact affected test then PASS0.247s. |
| Pure restore checker |10 PASS0.659s; migration/body identity, missing/extra/replaced/disabled trigger controls retained |
| Schema |No migration drift, Django system check clean |
| Actual authenticated forms |MFA session, CSRF rejection/acceptance, required scope confirmation, registered state and PHI-free page responses tested; no bypass |
| Render |Actual authenticated HTML rendered in Chromium offline at1440/390, both document widths equal viewport; two forms/seven visible labels. Screenshots inspected. This is not a public deployment/browser-server or native Word proof. |

One edit-instrument count assertion expected14 numeric tokens but found13 and stopped before writing that file; the corrected exact13 edit is recorded separately. No result is attributed to the aborted edit.

## Still required for B-L6

Owner/counsel: authoritative retention schedule/start events, custody/hold procedures, actual provider/copy lifecycle terms. No period has been invented and no production deletion is authorized.

Engineering: authenticated disposition request/approval, scoped tombstones and idempotent deletion executor, complete reference and financial/job reconciliation, external-copy/backup expiry reconciliation, and a restore-admission procedure that reapplies instructions newer than the recovered database. Independent refutation and integration are required for this preservation slice. Holds do not make these remaining tasks disappear.

All new checks are synthetic/offline. Historical mappings, finalized documents, original export hashes, balances, receipts and provider records were not rewritten. No installed service, activation lock, agreement, purchase or provider request changed.
