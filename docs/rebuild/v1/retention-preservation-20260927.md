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

## September 28 independent refutation and lifecycle repair

Independent reviewer tested frozen4dc254:10 of13 controls passed; three demonstrated failures remain in the sealed report (`retention-independent-refutation-20260927.md` in the custody branch). Releasing a hold before the first cleanup lost an unregistered file; a held prior Job row survived while its former input file was deleted; the restore verifier omitted that archived reference and could report success. Root independently reproduced the first ten controls, including both deletion failures:8PASS/2RED. Initial root replay attempts failed before any test action (incorrect settings-module name, then the wrong environment-variable name); their logs12/13 remain, and successful reproduction is14.

The repair considers applicable historical holds as well as active ones, and follows all immutable prior input/result/original/export paths even after the current row changes. Release alone never authorizes destruction. Actual upload and normalization preparation now record an immutable creation boundary **before bytes exist**, serialized with hold release. That record enumerates releases already committed at creation, so routine new files after release remain eligible for transient cleanup. This avoids trusting filesystem timestamps or clock ordering. Unknown older/unattributed files remain conservatively protected; no backfilled birth time is invented. No database migration or historical record was changed by this repair.

The production restore verifier includes all four archived file-path families and their recorded hashes, as well as registered preserved files. Missing/conflicting/changed prior evidence cannot become a green restore report. The installed legacy verifier remains unchanged.

Focused results:22 preservation tests PASS1.988s; exact first-ten independent controls now10PASS/0RED;11 pure restore checks PASS0.843s, including missing/changed/exact bytes for every archived path family. Logs15–17 and private root-refutation-red/green retain both outcomes. Broader affected upload, security, readiness and exact catalog checks are recorded separately in18. No provider requests, installed mutations, cleanup of old evidence or new deletion authority. The preservation slice still needs final independent closure before integration; the remaining disposition/deletion engineering above remains open.


### Historical scope correction (second independent finding)

Frozen09487 passed18 of19 independent controls; case18 still lost held bytes after a released encounter was reassigned to a different patient through the database. Root independently reproduced the exact application upload/audit/reaper sequence (`19-root-scope-red.log`), preserving the wrong first outcome. No exposed clinical transfer route was found by the bounded source review.

Forward migration0026 keeps protected scope identifiers fixed after release, including held descendants when an ancestor patient/department/template would move. Ordinary values can still be corrected; released holds stop capturing new prior values. Release is not a clinical transfer or disposition instruction. This intentionally does not provide a patient-transfer workflow. Earlier migration0025 and all historical rows are unchanged. The exact restore contract still expects39 guards, with the replacement function's new hash pinned from the reviewed migration; its helper now reads forward replacement functions in migration order.

Focused proof:28 PostgreSQL preservation/catalog/empty-install historical reversal tests PASS10.525s;11 pure restore checks PASS0.846s. The new cases exercise post-release reassignment refusal plus allowed ordinary correction and cleanup preservation, ancestor moves, and preservation of patient identity under an active encounter hold. Both preservation migrations refuse reversal when evidence exists; the final focused assertion is recorded separately. Prior99/107 failures, all independent REDs and every repaired outcome remain retained. Final independent closure is still required; no launch or disposition-completion claim.
