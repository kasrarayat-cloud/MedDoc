# Continuation pointer — Word and recovery milestone, 2026-09-17

**Preserve the new implementation and all new data. No reset, migration from the
old app, broad cleanup or public promotion is authorized by this continuation.**

Latest owner decisions: complete Word support including WM IOV first; scanned
forms later. Reuse preserved Resend with a verified sender and established
owner-controlled recipient. Engineering owns routine choices; no technical
option menus. CPT stays planned and disabled until licensing is verified.

Read `/opt/meddoc-pro/rebuild/.runtime/CHECKPOINT-LATEST.md` for the actual
running release, protected evidence and next action. This operational checkpoint
is append-only; its latest milestone supersedes historical sections. Never print
its linked account credentials, provider payloads, secrets or recovery keys.

## Verified running baseline before this Word PR

Release `688837471efb8b11c57a89e76d585e0ba352e937` (PR1181) runs all three
private services as dedicated `quillmd-app`, UID996/GID988, no extra groups or
capabilities. Active new-system state is `/var/lib/quillmd/{files,mail,proofs}`.
The original new-system operator storage remains preserved and inactive.
Actual same-PID denial and positive controls close the former direct file/socket
test gap without weakening AppArmor or host protections. Eight real private
browser checks passed for authentication/MFA, recovery, invitations, upload,
export and tenant isolation; email used the private outbox.

The post-cutover encrypted backup restored33tables,75,248rows and22referenced
files with matching hashes and invariants. This is a same-VPS restoration;
it does not establish offsite recovery or independent key custody.

## This milestone's implementation

The qualified MIT Word SDK handles the accepted WM IOV original with28 content
controls,90 answer locations and14 independently reviewed prewritten statements
and identity requirements. Versioned statement alternatives cover positive,
absent, no-prior-treatment and asymptomatic cases. The actual authenticated
clinician replaces the preprinted signer only after review. Source evidence,
side/row binding, conflicts, missing values and displayed-wording proofs gate
export; a changed statement must be displayed before its review can be accepted.

Local verification:262 tests pass with no skips (158application,27document/native,
77operations);12standard browser and9WM browser checks pass. The WM browser
exercises all five clinical scenarios, desktop/mobile accessibility, source
correction, conflict refusal and department/organization isolation. SDKqualification
90checks and independentclinical refutation12checks passed before release.
The final runtime passed47 checks with identical Word package parts; three
builds from different Git heads produced identical192-file runtimes. Five
locked NuGet packages were positively inventoried with zero published advisory
findings. Final manifest SHA256: `2a2ab5e1ba63e041dfd087e7f2c205999ccf8ff6bc41f9409cfd1d99e4537680`.
These are pre-activation results; the private checkpoint records actual deployment.

Exact merge67e632e4 subsequently failed its WM browser check before review.
Its old failure report did not record the precise assertion, so it does not
by itself prove the cause. A deterministic regression independently reproduced
a real display race: a worker could commit during Word resolution, after the
answer snapshot but before lazy job/code queries. Two tests failed before the
repair and pass afterward for generation and voice adoption. The view now reads
the encounter, jobs and codes under a short encounter-row lock, released before
Word processing; the current page stays consistent and the next GET shows the
completed result. Browser failures now record the exact stage and source line.
The repaired descendant requires its own PR/CI citation before activation.


The runtime is pinned, reproducibly built and isolated before document parsing;
network/process execution and outside-file access are denied. A shared bounded
processing slot limits concurrent native helpers. Original uploads stay unchanged.
Formatting qualification uses private evaluation rendering with watermarks and
font substitutions; product DOCX exports use MIT FOSS editing and contain no
evaluation watermark. Native Word acceptance is still required before promising
identical appearance in that application. No SDK purchase is requested.

The Word schema adds only three empty JSON columns to existing records. The
one-shot `scripts/activate-word-beta.py` requires the exact merged PR citation,
verified restore proof, exact build-input/runtime hashes, stopped services,
unchanged old database columns/rows/files/mail, retained report hashes, and
actual post-start identity/interface checks. Do not run an old activator again.
Private activation evidence, not this prepared description, determines what is live.

Encrypted B2 offsite transport and download-only recovery are implemented and
fixture-tested. An approved destination/scoped key and separately held recovery
key are still absent; no remote transfer or offsite restoration is claimed.
See `wm-iov-qualification.md`, `sdk-boundary.md`, `offsite-backup.md`,
`security-readiness.md` and `owner-actions.md` for exact scope and dependencies.

## External release gates

- Stripe sandbox restricted key and matching forwarding webhook secret, delivered
  securely; actual checkout, retries, exactly-once credits and refunds remain unverified.
- One established owner-controlled recipient for real Resend invitation/recovery
  delivery and usable private links. No suitable verified inbox was found.
- Approved offsite bucket/prefix/scoped credentials plus a separate vault key copy.
- Authentic provider billing/invoice evidence. Configured1.5×arithmetic passes;
  it is not provider-reconciled cost. Two historical missing receipts remain exceptions.
- CPT rights/content, independent tester access/window, and patient-data agreements
  and processing controls before their respective features/release stages.

Public app/admin routes remain maintenance503; real patient data remains disabled.
Private review addresses remain localhost9130/9131 through SSH forwarding.

---

# QuillMD fresh rebuild — durable checkpoint

Updated 2026-09-17. The owner's latest decision is **NO MIGRATION**. No old users, patients, documents, templates, balances or history are imported. Do not revive old migration/backfill/compatibility plans from historical documentation.

## Where work lives

The implementation is merged in [PR #1173](https://github.com/kasrarayat-cloud/MedDoc/pull/1173), merge `61879a61f56eaf85e8e8f764f748355abbc53906`. Shared `/opt/meddoc-pro` stays on main; the running application is **/opt/meddoc-pro/rebuild**. Marketing remains `apps/marketing` plus `packages/shared`. Future feature work belongs in an isolated worktree.

Private doctor: **http://127.0.0.1:9130**. Private administrator: **http://127.0.0.1:9131**. Use SSH forwarding. Individual login is required; administrators also require TOTP. Synthetic account passwords and administrator enrollment are in `/opt/meddoc-pro/rebuild/.runtime/private-access.json` (0600), never Git. Three `quillmd-fresh-{doctor,admin,worker}` systemd units are active and enabled under user claude. No reboot was performed or claimed as tested.

Fresh PostgreSQL: `quillmd-fresh-postgres`, loopback port 55438, volume `quillmd_fresh_pg`, database `quillmd_fresh`, independent random credentials. It has no connection to the old meddoc database. Its restart policy is unless-stopped. Private originals/exports and provider receipts live in `rebuild/.runtime/files`; preserve all new runtime data across code updates.

Public marketing/www return 200, app/admin return deliberate 503 maintenance, retired pro returns 410. No public route reaches the preview. DNS, certificates, nginx and shared container IDs/images/mounts were preserved. The main tree is clean of tracked changes.

Required checks are **Fresh application tests**, **Marketing build**, **Private browser and accessibility**, and **TruffleHog (verified-only, diff-scan)**. Other branch-protection settings are unchanged. Exact implementation merge citation: CI **35203116442**, secrets-scan **35203116365**, both first-attempt success. The browser/application/marketing jobs all passed remotely.

Activation completed at **09:13:12 UTC**, with auditable repairs for the host systemd PID namespace and Docker's stale file-bind inode after git checkout. Caddy received exact tracked shared-tree config bytes through stdin without recreating ingress. See `activation-judged.md`. Durable private evidence: `/opt/meddoc-pro/rebuild/.runtime/activation-result.json`, `activated-browser-verification.json`, `voice-speech-verification.json` and `activation-artifacts-cleanup-result.json`. Initial failed activation is retained honestly in the deployment log; do not blindly rerun the one-time activation command against an existing runtime.

## Implemented and exercised

- Individual verified accounts, invitations, personal organizations and departments, role checks, inactive-account revocation, password hashing, CSRF, throttled login, and administrator TOTP. Invitation acceptance grants the same single personal $10 welcome credit as direct verified registration.
- Original DOCX/AcroForm PDF storage, hashes, immutable mapping versions, department patients, typed/voice inputs, evidence/missing/conflict review, editing, finalized immutable encounter, original-format export and authorized downloads. The source original remains byte-identical. Unsupported structures and PDF overflow fail explicitly.
- Isolated parsing subprocess with Landlock, seccomp, CPU/memory/file/time limits and no network. Malicious archive/PDF/document constructs are refused. No unsandboxed fallback.
- Worker queue with durable receipts, conservative provider retry policy, stale-job reconciliation, request idempotency, immutable pricing/payer snapshot and authorization recheck after provider completion. Signed, expiring usage quotes preserve the displayed maximum and rates.
- PostgreSQL-locked reservations, personal promotional and paid balances, organization payers, exact1.5×defined-cost settlement, append-only ledger/usage/audit triggers, provider units/rates and user/department/org/payer attribution. No automatic top-up or live Stripe charging.
- Coding tab with effective dated ICD-10-CM/CPT token suggestions, source support and clinician acceptance. Source edits invalidate accepted suggestions. Official April2026 ICD-10-CM full set: **74,719 codes**. CPT requires valid licensed content and entitlement.
- Admin console for accounts/permissions, activity, queue, provider receipts/costs/charges, grants/balances/ledger, payments/refunds, reconciliation and audits.

## Integration truth table

| Integration | State and evidence |
| --- | --- |
| DOCX and AcroForm PDF | Real local libraries and kernel sandbox; exercised Word/PDF fill, original preservation, export and refusal cases. Advanced Word controls and scanned/flat PDF require a commercial SDK/OCR path, currently explicitly unsupported. |
| Anthropic | Live existing account, Sonnet4.6; normal queue receipt and settlement verified on synthetic notes. See live-provider-verification.json. |
| Deepgram | Live medical transcription API. A 6.43-second locally synthesized speech sample preserved wrist pain, no-fracture negation and follow-up; 11 queue/receipt/billing assertions passed. This is one sample, not general clinical accuracy validation. |
| OpenAI | Adapter exists; available key returned401. Optional replacement credential needed only to use this provider. |
| Stripe | Test checkout, signed webhook, duplicate/refund/reconciliation logic implemented; synthetic signed-event tests pass. No actual Stripe test checkout has completed; test key and webhook secret still needed. Live mode disabled. |
| ICD-10-CM | Real official CMS/CDC terminology loaded, source hash and effective dates recorded. April2026 set expires September30; refresh before October clinical use. |
| CPT | No licensed content loaded or simulated as licensed. Licensed feed/license identifier/expiry required. |
| Email | Optional Resend adapter implemented; 12 mocked tests pass. Read-only API check recognized the existing key as send-only, which cannot list domains. File outbox remains default; no message was sent. Confirm the sender domain in the dashboard and choose a reachable HTTPS origin before delivery testing. |
| AI fixture mode | Deterministic source extraction, clearly labeled, zero provider cost. Used in tests/CI; not claimed as live AI. |

## Verification and repaired findings

At this checkpoint, **70 Django/PostgreSQL tests**, **14 document tests**, and **12 browser checks** passed. Browser checks include create→generate→source review→finalize→DOCX download, responsive layouts, access exclusion and Axe accessibility. After activation, **11 additional real browser checks** passed: upload a new original under systemd sandboxing, mapping v2, live Anthropic evidence generation, review/finalization/export, original questions and complete answers, and separate administrator MFA/receipt visibility. Actual cost $0.003270 × 1.5 = $0.004905; the disclosed reservation was $0.1912635. This includes12 mocked optional-email checks; no real account email was sent.

The clinical refutation pass found and repaired negation/uncertainty/family-history substring loss, repeated-label conflict omission, inherited multiline scope, revoked-user cached permission, payer drift, duplicate transcription charges, missing receipt on output-storage failure, coding acceptance stale after voice changes, and quote/rate drift. Concrete regressions cover concurrent reservation/settlement, duplicate grants, repeated jobs/payment events, cross-department/org APIs/search/files/exports/jobs, malicious uploads/prompt injection, administrator MFA and finalization immutability.

Marketing production build passed and marketing remains HTTP200. Python lockfile audit and production npm audit reported zero known vulnerabilities. Security test scope is recorded in `pentest-scope.md`; this is internal authorized testing, not independent certification. Browser accessibility observations are bounded to exercised routes, not an assertion of universal conformance.

## Old resources removed and protected

Completed exact retirement evidence: `retirement-result.json` and `obsolete-image-cleanup-result.json`.

Removed: old app/admin/CRM source;10 old application/sidecar/QA containers;3 dedicated QA volumes;40 old application tables/types;79 objects in2 dedicated old buckets;old Redis DB0 application keys after writers stopped;85 unused dedicated application images carrying104 pinned tags. Old backup scheduler stopped/disabled. Image cleanup observed30,351,110,144 bytes recovered (~28.3GiB), root disk81% used after cleanup.

Preserved: marketing and its **7 waitlist entries** with DB-internal digest comparison; shared PostgreSQL/Redis/MinIO/Caddy/nginx; useful service credentials; DNS/certificates; encrypted mounts; other VPS projects and all unrelated container/image identities. Mixed old backups and ambiguous unlabeled resources remain untouched because ownership is shared/unclear. No archive was required or created, and no global pruning ran. 38 additional dedicated sidecar/backfill/QA/deployment files and one old nightly QA cron line were then removed; exact manifests, declarations and results are recorded separately. The cron installer now contains only preserved monitoring jobs. A further **7,431 pinned old build/artifact paths** were removed after main advanced. One differing service-credential copy was preserved at `/opt/meddoc-pro/.retained-service-credentials/.env.old-standalone` (0600 in a 0700 directory); root .env was unchanged. Shared root node_modules remains because two other worktrees link to it; do not replace it with npm ci until those consumers are resolved.

## External decisions and continuation

1. Provide Stripe **test** secret key and webhook signing secret through the private environment; use Stripe CLI forwarding or an explicitly authenticated staging endpoint. Exercise checkout, payment/refund events and reconciliation before allowing live payments.
2. Provide a properly licensed CPT dataset/feed with distribution entitlement, license ID and expiry. No subscription purchase is authorized by implementation alone.
3. Choose/license an evaluated Word/PDF SDK for advanced arbitrary customer forms. Assess original-format fidelity on authorized synthetic examples before promising support. See document-sdk-evaluation.md.
4. Confirm the billable-cost definition against provider account invoices/discounts/promotional credits, tax/refund policy and payment disclosures. Published token/audio rates are configured and versioned; account invoice reconciliation is not yet established.
5. Verify patient-data agreements, provider processing terms/regions/retention, access recovery, encryption and least-privilege database credentials, backup/restore and operational controls. The new database is currently a synthetic development database, not a qualified patient-data store. **SYNTHETIC_ONLY remains hard-gated.** Do not add real patient data on the basis of passing tests.
6. Before public promotion: HTTPS routing for the two hostnames, secure-cookie deployment, external email delivery, credential rotation/recovery, suitable monitoring and independent authorized penetration testing. Do not expose private ports or reuse marketing's datastore as the new application datastore.

Useful commands: `rebuild/README.md` for local tests; `scripts/check-cotenants.sh` for declared public statuses; `scripts/check-citation.sh <fullsha>` for actual CI citation. The three fresh systemd units in `rebuild/deploy` provide supervised private processes after activation. Database data and private originals/exports must be preserved across fresh-app code updates; the owner's deletion authorization concerned the verified old system.

## 2026-09-17 late — fresh live Word run through the repaired mapper

Release `8f8a6763b80d345e432074df64b907c2db50be2a` remains the running private
release. A second synthetic WM IOV encounter (`066488ba-d87d-48a7-9559-c868fd04a737`,
job `8d43fadb-3b52-4133-a7b5-44e423413823`, `absent` scenario) was generated by
exactly one live Anthropic request through the deployed mapper: 90 of 90
answers supported and evidence-bound with **zero clinician corrections**
(the previous encounter needed 90 edits before PR1185). It was reviewed,
finalized and exported through the normal interface; the independent read-only
verifier passed 42/42; the whole-ledger billing audit passes on 12 usage rows;
a new encrypted backup and isolated restore proof were taken afterwards.
Private evidence and the exact paths are listed in `rebuild/.runtime/CHECKPOINT-LATEST.md`
(0600). Native Microsoft Word acceptance stays pending: see
`word-acceptance-checklist.md`. Release requirements are consolidated in
`patient-data-release-requirements.md`; verified gap: the fresh database volume
and `/var/lib/quillmd` are not on an encrypted volume. The phased live runner is
tracked as `rebuild/wm-live-fresh.mjs`; the tunnel-only reviewer access script is
`scripts/ops/reviewer-tunnel-access.sh`.

## 2026-09-18 — billing policy activated, running release 19d46ad3

PR #1188 (billing policy: discount basis in the pricing fingerprint,
`CostReconciliation`/`PlatformCost`, appended ledger kinds `reconciliation` and
`absorbed`, automatic absorption of unadopted provider cost, administrator
console actions, migration `0012_billing_policy`, guarded activator) passed four
independent refutation rounds. The declared activation of `d2e45b53` stopped, by
design, after the migration because Django's post-migrate bookkeeping (two
content-type rows, eight permission rows) was not in the guard's expectation; the
scoped, declared resume (PRs #1189/#1190) proved that partial state and finished
the code-only steps. **Permanent main and the three private services run
`19d46ad3d51a3d8b548b4b53073f91664ca30946`**, synthetic-only. Console check,
billing audit (12 rows, all checks pass, 0 reconciled, 0 platform costs) and a
fresh encrypted backup with isolated restore were taken afterwards. Exact
private evidence paths: `rebuild/.runtime/CHECKPOINT-LATEST.md`. Provider cost
reconciliation still needs authentic provider evidence; Stripe, Resend delivery,
offsite restoration, CPT, independent testing and at-rest encryption of the fresh
data paths remain open gates (`owner-actions.md`,
`patient-data-release-requirements.md`).


## 2026-09-18 — billing boundary and storage encryption live, running release 3eac783a

**Permanent main and the three private services run
`3eac783a55b6b771016da258ab2b57e0a06bdb38`**, synthetic-only, public routes in
maintenance.

- **Billing boundary (PR #1192).** Declined output stays charged, and unusable
  output is absorbed. A queued request cancels free, and a request failing before
  any provider call releases its hold. Additional requests are disclosed.
  Output is delivered only for charged requests. Retries are charged once, and
  the audit covers cancelled and ended jobs. Three refutation rounds
  confirmed 21 findings (17, 4, then none). All are fixed, and every code finding
  has a regression test. No schema change.
- **Storage encryption (PRs #1193, #1194, declared act).** The fresh database,
  WAL, files, mail, proofs and service temp files now sit on a LUKS2 volume.
  Attempt 1 stopped safely at its first host step and reverted in 17 seconds.
  Attempt 2 completed and was judged 29 of 29. The key file is still on the host,
  so protection against disk-level access needs the owner steps in
  `owner-actions.md` §5.
- **After the act.** The billing audit passes (12 usage rows), the post-act
  encrypted backup restores with no decrypted files written (75,457 rows,
  identical to before), and the console check passes 4 of 4.

Remaining owner actions, stated once with exact locations: `owner-actions.md`.
Private evidence paths: `rebuild/.runtime/CHECKPOINT-LATEST.md`.


## 2026-09-18 — binding recording limit live, plaintext copies removed, running release 5f673a3b

**Permanent main and the three private services run
`5f673a3b2cc5c99d68f08f34fba43b4883403583`**, synthetic-only, public routes in
maintenance.

- **Binding recording charge limit (PR #1197, declared activation of
  migration 0013).** Before any paid request, a recording is measured the way a
  decoder plays it, and its exact limit is held. Above the displayed limit
  ($0.30, which fits 45:34 at the configured rate), nothing is sent until the
  doctor picks a shorter segment or approves a priced higher limit. The charge
  never exceeds the limit; anything above is absorbed and recorded separately.
  A missing portion of more than 2 s is marked in the notes and the download.
  Four refutation rounds confirmed 20, 6, 6 and 3 findings, all fixed. The
  activation was judged 18/18: only the pinned schema changed and no row moved.
  The billing audit passes, the console check passes 4/4, and the post-act
  backup restores with the capped invariant at zero.
- **Plaintext copies removed (PR #1196, declared act).** Removal came after
  proof that every active path is on the encrypted volume, both key slots
  open, a fresh encrypted backup equals the live database table for table, and
  closing and reopening the volume is fail-closed and recovers. Nine
  directories (2,722 files) were shredded, judged 20/20. The storage act's
  rollback now targets the reap merge.
- **Not done here:** recovery after a host reboot (a shared host), independent
  custody of the recovery keys (no vault is connected), native Word acceptance
  (Windows), and the external integrations. See `owner-actions.md` for exact
  locations.

Private evidence paths: `rebuild/.runtime/CHECKPOINT-LATEST.md`.


## 2026-09-18 — verification and repair pass: legacy inventory, length bounds, restore cause, key custody, ICD-10-CM FY2027

A focused pass over five named items. The rebuild was not restarted, no broad
review campaign was run, and no historical record was deleted to make an earlier
report read consistently.

**The running release and revisions were verified first**, not assumed: HEAD and
both HTTP surfaces reported `5f673a3b2cc5c99d68f08f34fba43b4883403583`, and
`origin/main` was `1ed50b93` (PR #1198, documentation only).

- **Legacy inventory, with the correction** —
  `docs/rebuild/legacy-inventory.md`. The 2026-09-17 sentence claiming the
  rebuild kept "all of the original application's remnants" is **wrong**, and so
  is reading the earlier reports as "the old system is gone". The original
  application's source, images and cron entry are verified absent; three of its
  data services still run; and one of them holds **7 real waitlist rows
  (email and name, 2026-08-02 to 2026-09-05)** that are business records, not
  remnants. No cleanup was executed: the previously authorized source/cron
  cleanup is already complete, and everything still on disk is either preserved
  deliberately or an owner decision about data deletion.
- **Recording length: charging and disclosure separated.** An MP3 fixture
  measured 2.412 s against ffmpeg's 6.717 s because frames hidden in trailing
  tags were bounded but never counted. Measurement now returns
  `Bounds(confirmed, measured)`; the charge limit is held against `measured`
  and the incomplete-output marker reads `confirmed`, so no number rounded up
  for billing can describe a transcript as complete. Tag-resident frames are
  counted, and beyond eight stray headers the file is refused with a re-export
  instruction. **Residual, stated rather than claimed away:** up to eight stray
  headers remain bounded but unconfirmed, which `confirmed` excludes.
- **The first failed restore was diagnosed, not retried.** The docker journal
  showed the isolated container created at `11:09:07.24Z` and removed at
  `11:09:09.31Z` — too fast for the dump, so the failure was inside
  `pg_restore`. Cause: the PostgreSQL entrypoint's temporary initialisation
  server answers `pg_isready` before the real server exists.
  `restore_ready()` now requires the init-complete marker, `pg_isready` and a
  `SELECT 1` returning 1; failures record the stage and exception class, never
  raw stderr.
- **Encryption mapped scenario by scenario** —
  `docs/rebuild/storage-encryption.md`. Every key, backup, swap and log
  location is listed with its filesystem. The honest statement is now explicit:
  **a whole-host image containing `/etc/quillmd` is not protected**, the backup
  key sits two directories from the ciphertext it opens, and swap
  (4,190,184 KB of 4,194,300 KB in use) and the 3.22 GB journal are
  unencrypted host-level storage.
- **Key custody and Word retrieval rewritten** — `owner-actions.md` §1 and §2.
  The procedure was verified on dummy values first (trailing newline, no
  newline, padded), and the two secrets are published as SHA-256 checksums of
  their trimmed values so the owner can confirm a correct copy without either
  value being displayed. The Word archive command names its destination and
  compares the checksum and byte count before unpacking; the archive was
  re-verified on the host. **A correction:** the backup key file is 45 bytes —
  a 44-character Fernet key plus a newline the tool strips — so a value stored
  with that newline attached will not open a backup. An earlier note saying it
  had no trailing newline was wrong.
- **`.env` is not read, and now does not need to be.**
  `manage.py configuration_status` reports each credential as absent, present,
  or present with a recognised or unrecognised shape, and its tests assert that
  no configured secret can appear in its output.
- **ICD-10-CM FY2027, and the defect that made it urgent.** The release was
  selected by `timezone.localdate()` — the date the note is coded on, not the
  date of the visit. With only FY2026-April loaded (effective to 2026-09-30),
  coding would have returned **zero suggestions with no error from 1 October**,
  twelve days out. `Encounter.service_date` now carries the date of service or
  discharge, migration 0014 backfills existing encounters from the date they
  were recorded, and `applicable_releases(encounter)` is the single rule both
  the suggestion and acceptance paths read. FY2027 (74,879 codes) is verified and
  declared for import beside FY2026-April (74,719), neither replacing nor
  rewriting it. CPT stays disabled.

### The first activation attempt was REFUSED by the database, 2026-09-18T15:37:47Z

PR #1199 merged as `475a5925` with a full citation, and the declared activation then failed inside migration 0014:
`encounter_scope`, a trigger on `core_encounter`, refuses **any** update to a finalized document, and six of the
eleven encounters are finalized. The migration rolled back whole — no column, no history row, 11 encounters
unchanged — and the activator failed closed with the three services stopped.

**No test had a finalized encounter in it.** Every fixture was a draft, so the migration was proved against a
universe the guard had no reason to refuse. That is the same shape as a control that passes vacuously, and it is
why the retry ships a `TransactionTestCase` carrying a finalized document.

Permanent main was advanced to `475a5925` before the migration ran and stays there; the retry is declared at
`docs/foundation/mutations/20260918-quillmd-service-date-retry.md` and re-baselines onto it.

### What reached the running system, 2026-09-18

**Running release `5f8050df5e79c0d7948185850914f1c161fcbc1f`**, both surfaces
synthetic-only, public routes in maintenance.

Three declared acts ran, each judged row by row against numbers written down
before it:

| act | declaration | judged |
| --- | --- | --- |
| migration 0014 and the release advance | `20260918-quillmd-service-date-retry.md` | **14 of 14** |
| ICD-10-CM FY2027 | `20260918-quillmd-icd10cm-fy2027.md` | jointly **31 of 31** |
| ICD-10-CM FY2026-October | `20260918-quillmd-icd10cm-fy2026-october.md` | with the above |

- **The date of service is recorded and it selects the release.** All 11
  encounters carry a `service_date`, each the UTC date of its own `created_at`
  (`2026-09-17=11`), the six finalized ones included. Nothing else moved: 35
  tables, 3 patients, 12 jobs, 0 suggestions, 361 audit events, and every row
  fingerprint identical with the new column removed.
- **`encounter_scope` is back on and still refuses.** The migration suspends it
  for its backfill statement only. Recorded `O` before and after, and a live
  probe still raises *"Finalized document is immutable"* on a finalized row.
- **Three contiguous ICD-10-CM releases, 224,317 codes.** FY2026-October
  (2025-10-01→2026-03-31, 74,719), FY2026-April (2026-04-01→2026-09-30, 74,719,
  byte-identical and untouched) and FY2027 (2026-10-01→2027-09-30, 74,879).
  Boundary read-back: 30 September selects FY2026-April, 1 October selects
  FY2027, and dates before 2025-10-01 or after 2027-09-30 select nothing and say
  so. **The 1 October defect is closed.** CPT remains disabled — 0 releases, no
  licence.
- **Post-checks.** `audit_billing --maintenance-storage` passes every check; its
  two `durable_receipt_gaps` are the pre-existing live Anthropic and Deepgram
  calls awaiting the owner's cost evidence (`owner-actions.md` §7), and are not
  gated. A fresh encrypted backup (`20260918T161229Z-2ee211a0`, 35 tables,
  225,079 rows, 28 files) restored **first time** — no retry — with every table
  and file hash matching, zero decrypted files written, on tmpfs without swap.
  `manage.py configuration_status` answers on the live release.

⚠️ **It took four attempts, and the refusals are the record worth keeping.** The
first was refused by the database (the finalized-document guard); the second and
third by the activator's own preflight (a leftover assertion, then the tree HEAD
and the running release having come apart when the first attempt died between
them); the fourth by a dead process's lock, which was inspected and set aside
rather than deleted. **None of them touched data.** The private service was down
for about 35 minutes across that sequence, and no attempt was made to shorten it
by starting the services on a release whose schema was not there yet.

**Still open, unchanged by this pass:** recovery after a host reboot,
independent key custody, native Word acceptance, the external integrations, the
owner's provider cost evidence, and the owner decision on the legacy data
services holding the seven waitlist rows.

## 2026-09-18 — integrity and cleanup milestone

**Running release `5f8050df5e79c0d7948185850914f1c161fcbc1f` on all three surfaces**, synthetic-only,
public routes in maintenance. Verified, not assumed: the doctor and admin surfaces answer that release
over HTTP, and the **worker** — which has no HTTP surface — is covered by the activation's own identity
proof bound to pid 322901, still the live process. Repository `23c05d4f`, two documentation commits
ahead of the running release, no runtime file differing.

### The four checks that passed without exercising their conditions

Recorded in full at `docs/rebuild/checks-that-passed-without-looking.md`: each check, its intended
guarantee, the missing input, and whether a release shipped on it. One did — the migration proof, whose
every fixture encounter was a draft, so `encounter_scope` was never reached; PR #1199 merged as
`475a5925` on the strength of it and the activation then failed against the live database.

`rebuild/exercised.py` turns the precondition into a declared, failing assertion. Every repair is
proved twice: remove the required input and the check reports MISSING COVERAGE; restore the original
defect and it FAILS. A fifth was found in passing — eight live document tests skipped on a predicate
naming two of three required variables, which meant they RAN and FAILED on a partly-configured host.

### Finalized documents: unchanged, proved against pre-change evidence

Backup `20260918T114002Z-bba650ad` (11:40Z, commit `5f673a3b`, before the migration) was restored into
an isolated networkless container and compared with live:

- **11 encounters both sides**, none added or removed, and **0 rows whose content differs** once the
  declared `service_date` column is excluded;
- across the **6 finalized** encounters, all **14 clinical fields identical** — notes, answers,
  template_review, status, revision, finalized_at/by, export_path, **export_sha256**, and the scope keys;
- exported-document hash set identical;
- the only audit action that moved is `terminology.import`, 1 → 3: the two declared imports. No logins,
  no views, no coding, no encounter mutations.

The declared metadata change is the only difference. **This distinguishes metadata from content:** a
column was added and filled; nothing a clinician wrote was touched.

### The migration exercised on real draft AND finalized data

In a second isolated database loaded from the same pre-change backup, the **actual** migration was run:
5 draft + 6 finalized all filled, 0 nulls, 0 disagreeing with their own `created_at`. Then:

- legitimate draft edits (notes, answers, service_date) **succeed**;
- all six prohibited changes to a finalized document **fail**, including the new `service_date` — so
  the added metadata is immutable there too;
- **the counterexample on real data:** with the guard active the backfill aborts entirely, **0 rows
  filled**, which is exactly why the production migration died.

The guard is not weakened: `encounter_scope` reads `O` before and after, and a live probe still raises
*"Finalized document is immutable"*.

### Legacy working copies

Ten removed (2.2 GB), nine kept, each with a named reason —
`docs/rebuild/legacy-inventory.md`. Every removed worktree was clean, inactive, and held only commits
reachable from a named `origin` branch; `git worktree remove` deleted no commits and no branches, which
was verified branch by branch afterwards. **No running service uses original application code or
data.** The seven marketing waitlist records and their storage are untouched.

⚠️ `find -newermt '-24 hours'` is rejected by this host's **bfs** and returns a vacuous zero for every
directory. Every activity figure was re-taken with an absolute cutoff; one worktree that looked dormant
had thousands of files written that day.

### Audio judged against what is actually submitted

`docs/rebuild/audio-submission.md`. The recording is POSTed verbatim, so the submitted payload is the
file, and `core/media.py` probes it with ffprobe under explicit stream selection and bounded resources.
The charge ceiling, the duration estimate and the completeness assessment are three separate numbers.
Coverage is judged against the submission; where the payload does not determine what a decoder
processes, the answer is **UNKNOWN**, disclosed with its reason.

A matching duration is **not** proof that every spoken word was transcribed, and the silent case is the
absence of a claim rather than a statement of completeness.

### Session hygiene

The two shells were identified and stopped, both mine, both waiting on conditions that could never
occur: one polling for a marker in a file that had already exited, one an `until ! pgrep -f …` whose
own command line matched the pattern. The agent session, the three application services and other
sessions' work were left alone.

**Still pending, unchanged by this milestone:** the documented encryption limitations (a whole-host
image containing `/etc/quillmd` is not protected), independent key custody, native Word acceptance, and
the unavailable external integrations. No host reboot and no shared-host security change was made.
