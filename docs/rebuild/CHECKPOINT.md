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

At this checkpoint, **70 Django/PostgreSQL tests**, **14 document tests**, and **12 browser checks** passed. Browser checks include create→generate→source review→finalize→DOCX download, responsive layouts, access exclusion and Axe accessibility. After activation, **11 additional real browser checks** passed: upload a new original under systemd sandboxing, mapping v2, live Anthropic evidence generation, review/finalization/export, original questions and complete answers, and separate administrator MFA/receipt visibility. Configured-rate cost $0.003270 × 1.5 = $0.004905; the disclosed reservation was $0.1912635. (Configured-rate cost means provider-reported units priced at the recorded rates. No provider invoice has been reconciled, so it is not an actual billed amount.) This includes12 mocked optional-email checks; no real account email was sent.

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

## 2026-09-18 — deterministic audio submission, running release cd428f70

**Running release `cd428f7062d3d624787d927c41130692017d5a84` on all three surfaces**, synthetic-only,
public routes in maintenance.

**Three revisions, and they are three different facts:**

| | |
| --- | --- |
| running revision before | `5f8050df5e79c0d7948185850914f1c161fcbc1f` |
| code revision merged and never deployed | `8de5dd491de78b4e628364096c50ed68b161ef19` |
| running revision after | `cd428f7062d3d624787d927c41130692017d5a84` |
| documentation-only ahead of the running revision | this entry's own commit, and nothing else |

Two changes shipped together and **both were judged**: the integrity-and-cleanup milestone that merged
as `8de5dd49` and was never activated, and deterministic audio submission. The declaration named the
full range from the RUNNING release rather than from the tree, because *"I deployed `main`" is not the
same claim as "I judged what I deployed"*.

Verified, not assumed: the doctor and admin surfaces answer `cd428f70` over HTTP, and the **worker** —
which has no HTTP surface — was identified by **four** facts, because a PID is reused and one read in
one place and checked in another describes whatever holds it now:

| | |
| --- | --- |
| systemd's record of the start | `Fri 2026-09-18 21:26:38 UTC` (was `16:09:21`) |
| the kernel's record of that PID's start | `2026-09-18T21:26:37.34Z` |
| the command | `/opt/meddoc-pro/rebuild/.venv/bin/python /opt/meddoc-pro/rebuild/manage.py worker` |
| the service cgroup | `0::/system.slice/quillmd-fresh-worker.service` |

⚠️ **The first version of that check asserted the wrong command** — `service_launcher.py --surface
worker` — because the launcher EXECS the surface and replaces itself. It was caught by running the
check against the live host rather than only reading it, and by narrowing a too-wide `except` that had
reported the mismatch as NOT EXERCISED.

### The declared delta was EMPTY, which is stricter than a migration's

No migration ships here, so nothing had an excuse available. Judged and matched: 35 tables, every
column, constraint and index, **every table's row fingerprint**, the private files and mail
inventories, the compiled Word runtime, the retained reports and the protected containers — all
byte-identical across the act. `provider_calls: 0`. The only things that changed are the release line
(one occurrence, line count unchanged, recorded by sha256 of the file before and after) and the three
process identities.

### Post-checks

`audit_billing --maintenance-storage` → `all_checks_pass: true`, exit 0. Its two `durable_receipt_gaps`
are the same pre-existing live Anthropic and Deepgram calls awaiting the owner's cost evidence
(`owner-actions.md` §7) recorded in the previous milestone — and provably untouched here, since every
row fingerprint is identical across the act and the act made no provider call. Doctor and admin
surfaces gated (302, not 500); `/admin/` gated. Co-tenants at their expected statuses, three distinct
codes so the probe discriminates. `configuration_status` on the live release reports both media tools
resolved, `SYNTHETIC_ONLY: True`, `STRIPE_LIVE_ENABLED: False`.

**The deployed modules were exercised directly** — imported from `/opt/meddoc-pro/rebuild`, the tree
the services load — with no database write and no provider call: a one-track WebM remuxed 27,776 →
27,686 bytes, and a two-track WebM was refused before any remux. The live constants read back as
budget 25 s, address space 768 MB, tolerance 0.1 s.

⚠️ **What was NOT exercised, named rather than implied:** the HTTP upload → worker → provider path end
to end. That needs an authenticated synthetic account and a paid provider call, and the full clinical
walk belongs on QA against a byte-identical build. No real clinical record was touched.

### A new runtime dependency, and it fails silently

`ffmpeg` joins `ffprobe`. Without either the application still works and degrades honestly — every
recording is submitted exactly as uploaded, unnormalised — which is the hardest kind of absence to
notice. The activation refuses without both, and `configuration_status` names each.

### Ten defects, seven in the same direction

Four refutation lenses over the finished diff found nine; the checks written for them found a tenth.
Seven refused, charged for, or silently narrowed a recording that was made correctly — including a
multi-track refusal that **failed open above 64 tracks** (a 65-track file created a job, held $0.06,
made a provider request and charged $0.0525), an in-limit MP3 refused as "Recording too large" because
our own remux crossed a limit the upload sat on, and loss before the request that was invisible by
construction. Full account: `docs/rebuild/audio-submission.md`.

**The most serious finding was about the evidence, not the code.** With ffmpeg removed from `PATH`, 32
of 34 submission tests skipped and the suite reported `OK` — and the one test written to assert the
dependency skipped itself on exactly that condition. Absent is now a skip on a machine that never
promised the tool and a **failure** where something installed it on purpose.

### Two gates refused, and both were right

⚠️ **CI refused the first push.** Three tests rendered a page and resolved a static asset through the
manifest storage; they passed locally only because this worktree's `staticfiles` is a symlink into the
shared tree. Reproduced by moving the symlink aside — 393 tests, the same count CI ran.

⚠️ **The ruled-mutation gate refused the activation outright**, reporting `tracked: no`. The
declaration ships in the very commit it activates, and the activator advanced `main` **itself**, after
the gate had already run — so the declaration existed only in a worktree the gate cannot see. *An
activation whose declaration is invisible to its own gate is a gate that cannot fire, and nothing would
have said so except the refusal.* Fixed by ordering (PR #1205): `main` carries the declaration, the
tree is fast-forwarded, and the preflight now fails on the same condition rather than leaving it to
surface with the act already staged. The declaration's commit stands at `2026-09-18T20:50:35Z` and the
act started at `21:26:11Z` — a bracket the gate printed itself.

**Still pending, unchanged by this milestone:** native Word acceptance (the package is unchanged at
227,269 bytes, `B270C982…F03A72` — re-verified on the host, not regenerated), independent key custody,
the documented encryption limitations (a whole-host image containing `/etc/quillmd` is not protected),
and the unavailable external integrations. No host reboot and no shared-host security change was made.
The seven marketing waitlist records are untouched — counted at 7, values not read. They live in the
LEGACY `meddoc` database, a different container from the one this act fingerprinted, so they were never
in this deploy's blast radius; the count is reported because it was asked for, not because anything
here could have moved it.

## 2026-09-19 — recording stops safely when processing fails, running release 6d73c5e9026d974053365468101c2f7921544c6c

**Running release `6d73c5e9026d974053365468101c2f7921544c6c` on all three surfaces**, synthetic-only, public routes in maintenance.

| | |
| --- | --- |
| running revision before | `cd428f7062d3d624787d927c41130692017d5a84` |
| code revision before the fast-forward | `d45d9f72216132934b99e0c1fa426d1bc4fb532f` |
| running revision after | `6d73c5e9026d974053365468101c2f7921544c6c` |
| documentation-only ahead | this entry's own commit |

### The repaired failure paths

The audio path used to **fall back to submitting the original upload** whenever ffmpeg processing
failed. That is removed. It had been reasoned as *"never worse than the behaviour before normalisation
existed"*, and the reasoning was wrong in a way that sounds conservative: **a step that silently stops
running is worse than one that fails.** The provider received bytes nobody had measured, decided for
itself what to decode, and the doctor was charged for the result — with the only trace a detail string
on a usage row.

Every failure now stops before the provider. `NoProviderRequest` is the stop: `run_one` classifies it
`unsent`, writes the failure and **releases the hold in one transaction**, so nothing is charged and
the reservation is released exactly once.

| class | cause | retryable |
| --- | --- | --- |
| `missing` | the upload is gone from storage — the platform's failure, not the file's | no |
| `unavailable` | ffmpeg or ffprobe missing or unrunnable | yes |
| `too_slow` | the 45 s preparation budget or a decode deadline was spent | yes |
| `unreadable` | unmeasurable, ambiguous, or a length that does not decode | no |
| `too_large` | the prepared payload exceeds the submission limit | no |

The doctor sees a fixed sentence per class, never the technical reason: `failure_reason()` renders a
`NoProviderRequest`'s message verbatim into the doctor's error *and* into `audit_billing`'s export, and
ffmpeg quotes the storage path it was handed. The detail is recorded once, scrubbed of paths, on a
`voice.submission_refused` row.

### Two new refusals, both before any charge

- **A WAV holding more than one `data` chunk.** It gives three answers about its own length: the
  parser's floor says 1 s, its ceiling says 10 s, and ffmpeg plays 9 s because it reaches the *last*
  chunk — reverse them and it plays 1 s. Refused in `enqueue`, before the job row and the hold.
- **An artifact that does not decode.** `-c:a copy` moves frames without decoding them and exits 0 on a
  container no decoder can use, after which ffprobe reports what the container *declares*. The artifact
  is decoded and the decoded length compared with the declared one, tolerance 0.25 s against a measured
  worst real divergence of 0.040 s.

### Six defects the refutation pass found, all in this change

The most serious: **a failed audit write could strand the money it exists to return.** `refuse()` put a
`SELECT` and an `INSERT` on every failure path, landing right after up to 45 s of subprocess work. If it
raised, the job went to `reconciliation` rather than `unsent` — hold never released, `request_key` never
freed so the encounter refused every later recording, and `audit_billing`'s hold policy only inspects
succeeded/failed/cancelled jobs, so `all_checks_pass` stayed **true over stranded funds**. The audit
write is now best-effort.

Also: ffprobe missing was reported as the doctor's file being broken and marked non-retryable; a
recording the platform had *lost* was reported as one to re-export (an existing regression test pinned
that and was red — suites had been picked by name rather than by what the change touched); the decode
deadline could not fire on a child that produced nothing; the 25 s budget had been sized for a remux
alone; and `configuration_status` — edited in this very change — still promised a degraded-but-working
submission path that no longer exists.

**No false rejection introduced:** 16 of 17 legitimate recordings pass unrefused, across stereo, VBR,
ID3, 8 kHz, 24-bit, float, u8, silence, 0.2 s, 2 min, live-shaped WebM and espeak output. The
seventeenth is Vorbis, refused by the *pre-existing* Opus-only parser.

### Repository integrity after the scratch cleanup

Read-only: `git fsck --strict` exits 0 with 558 lines, **all `dangling`** — zero missing, broken,
corrupt, unreadable or invalid — and all 466 refs resolve. The objects shredded in the previous
session's close-out were under `/tmp/.../scratchpad/`, in three throwaway clones, never under
`/opt/meddoc-pro`. No further cleanup was performed and the dangling objects were left alone.

### A process failure worth keeping

Both refutation lenses were authorised to mutate repository files and restore them **while the same
files were being edited**. Their restore is to a snapshot, so concurrent edits were reverted silently —
twice, with no error, surfacing only as an `ImportError`. One lens was stopped mid-run. Recorded in
`AGENTS.md`: *a mutation proof asserts its own restoration as well as its own application*, and no agent
gets write access to a file its author is editing.

**Still pending, unchanged:** native Word acceptance (package unchanged at 227,269 bytes,
`B270C982…F03A72`), independent key custody, the documented encryption limitations, and the unavailable
external integrations. No host reboot and no shared-host security change.

### The end-to-end demonstration, through the application

One locally synthesized six-second sample (`espeak-ng`), uploaded over authenticated HTTP by a synthetic
account, transcribed by the real provider, displayed and downloadable. **Its expected records and
charges were declared and committed before it ran**
(`docs/foundation/mutations/20260918-quillmd-endtoend-demonstration.md`).

| | |
| --- | --- |
| release under test | `6d73c5e9026d974053365468101c2f7921544c6c`, confirmed by the harness itself |
| job | `00959751-1eb5-486c-9f71-4b079f6a5cc4`, `succeeded` |
| provider | `deepgram:nova-3-medical`, **`simulated=false`** |
| provider request id | `01a0b715-ae33-7473-83b5-6410239d98f4`, identical on Job, Usage and ProviderReceipt |
| submitted artifact | 280,414 bytes, sha256 `c577f95c…a8a20d2d5`, 1 audio stream, container `wav` |
| **`submission_source`** | **`normalised`** — the repaired path ran; nothing fell back |
| declared vs decoded | 6.357596 s vs **6.358 s** — the new decode verification ran and agreed |
| provider-reported | 6.3575625 s |
| configured-rate cost (`actual_cost`) → charged | $0.000455625300 → $0.000683437950, exactly 1.5× |
| reservations | **1, `settled`** — settled exactly once |

The same run also exercised a real Anthropic generation ($0.00291 → $0.004365, paid from personal
promotional credit), finalization and the Word export. Reservations peaked at **$0.49098** against the
harness's USD 1 ceiling; this run charged **$0.0050484380** in total and no row was simulated.

Every declared quantity matched with one exception, stated rather than smoothed: **`users` did not
grow.** The invitation check is the one that failed, so the user it would have created was never made.

⚠️ **THE ONE FAILING CHECK, AND ITS DEPENDENCY NAMED.** *"Private invitation, single welcome grant, and
password recovery work after deployment"* failed after 11 passing checks. Diagnosed: the harness's
helper runs as the operator account, and the check reads the service's private email outbox
(`/var/lib/quillmd/mail`) to extract the invitation and recovery links. That directory is owned by
`quillmd-app` and the operator account cannot read it — `PermissionError [Errno 13]`, reproduced
directly. **This is the OS isolation working as designed, not a defect in the release**: the activation
proved the mail inventory and the installed unit files byte-identical across the act, and nothing in
this change touches email or storage permissions. It is unrelated to the recording path, and it is left
as a known limit of running that particular check against the live services rather than a fixture.

**Post-checks on the new release.** `audit_billing --maintenance-storage` → `all_checks_pass: true`,
exit 0, the same two pre-existing owner-pending receipt gaps. Doctor, admin and `/console/` gated
(302). Co-tenants at expected statuses across three distinct codes. The operator screen now answers the
question that used to be unanswerable from the operator's side: **`DEEPGRAM_API_KEY: present`,
`ANTHROPIC_API_KEY: present`**, both media tools resolved, `SYNTHETIC_ONLY: True`.

## 2026-09-19 — the account checks' access method, repaired rather than worked around

**The revision under test is `6d73c5e9026d974053365468101c2f7921544c6c`**, read from `/health/` on both
surfaces (doctor `9130`, admin `9131`) rather than taken from the brief. The recording milestone is
accepted as complete on its retained evidence and was not re-run: no recording, no generation, no
provider contact of any kind in this work.

### What was failing, and what the repair is

The twelfth check of the release harness failed with `PermissionError` because its helper ran as the
OPERATOR account against `/var/lib/quillmd/mail`. **That was the OS isolation working**, and it is
preserved exactly: nothing here changes a directory mode, a group, an ACL or a unit file, nothing takes
sudo, nothing exposes a token endpoint, and MFA is exercised rather than relaxed.

`rebuild/ops/private_mail.py` reads the outbox through the existing confined reader in
`ops/private_storage` — a container running as the SERVICE identity, no network, read-only bind of one
approved root, all capabilities dropped. It is a NARROWING of the docker-socket privilege the operator
account already holds, not a new boundary around it, and it is described that way.

### ⚠️ THE FIRST DESIGN WAS WRONG, AND A REFUTATION PASS PROVED IT WITH REAL BYTES

It selected messages by FILENAME TIMESTAMP and regexed the whole file. Two library facts break that, and
neither is this application's choice:

- `django/core/mail/backends/filebased.py` names each file `%Y%m%d-%H%M%S-<abs(id(self))>.log`, and
  `abs(id(self))` is a recycled CPython address — **measured constant across 4000 sequential backend
  instances**. The only real entropy in that name is one second.
- `core/email_backend.py` opens it `O_APPEND|O_CREAT`, so a name collision APPENDS.

Three sends in one second produced ONE file holding THREE records for THREE recipients, and a first-match
regex over those bytes **returned a different account's raw token**. Selection is now at RECORD level —
split on Django's 79-dash separator, parse each record's `To:`, take the single record addressed to this
run's unique synthetic address, refuse on two — and the run is identified by a before/after `inventory()`
diff rather than by a clock, because a changed sha256 catches the append-collision that a timestamp window
cannot see at all.

⚠️ **AND THE SAME BROKEN READER WAS LIVE IN THREE OTHER HARNESSES.** The repair had landed in a new module
while `verify-private-release.mjs`, `identity-browser.mjs` and `private-beta-browser.mjs` kept their own
copies — including the one whose check had already failed. Each navigates to what it returns, so a wrong
token means consuming a stranger's invitation or resetting a stranger's password. All four now call the
one reader.

### What is true about the confinement, said plainly

`private_storage.read_file` is all-or-nothing: there is no predicate and no partial read. So the narrowing
is at MATCHING level, and READING is narrowed only to the files this run changed. A file the run changed
can hold somebody else's record, and that record's bytes reach this process. The module says so in its own
docstring rather than claiming otherwise, and the mitigation is named as a DETECTION, not a prevention: a
record addressed outside `@synthetic.quillmd.invalid` makes the read refuse, so the run stops instead of
continuing quietly. On this synthetic-only host no such address exists; the guard is for the day one does.

The route and the token are the same string (`core/email_delivery.py` builds `{origin}/{route}/{token}/`),
so it is navigated to and never logged, never written to a report, never passed in argv, and never an
operand of an assertion. Reports carry `describe()` — found, kind, token length — plus counts.

### Two gates that had quietly stopped measuring anything

- **A spent activator's range test was pinned to `HEAD`.** `test_every_path_this_branch_changes_was_declared`
  compared `RUNNING_RELEASE..HEAD` against the activator's `ALLOWED` set. That is the right question only
  while the branch is unshipped; once it lands, `HEAD` keeps moving and the test starts asking whether
  everything since the last deploy is in a spent activator's allow-list. It had been **red on `main`** since
  the recording repair merged, and CI never said so because `actions/checkout` is shallow and the
  range-availability guard turns that into a skip. Both activators now record `SHIPPED` and the range is
  measured to it. The pin itself is cross-checked three ways — trunk first-parent merge commit, the previous
  activation's `SHIPPED` matching this one's `RUNNING_RELEASE`, and the deploy checkpoint's own
  `running revision before`/`after` rows — because a refutation pass measured that an unconstrained pin
  admits a later merge and stays green.
- **⚠️ `load_activator()` COULD EXECUTE A STALE COMPILED COPY, AND IT DID.** `spec_from_file_location` +
  `exec_module` is a SourceFileLoader, which serves `__pycache__` whenever the cached source mtime AND size
  still match. A mutation proof restores both — same size, same one-second mtime — so the run AFTER the
  restore can execute the version from BEFORE it. Measured here: `after mutate, default: ORIGINAL` while the
  file on disk said `MUTATED`, and `sys.dont_write_bytecode = True` does not help because it only stops
  WRITING. **It cost a wrong answer in this session**: a proof that a wrong `SHIPPED` fails its test reported
  a failure produced by a stale activator. All twelve loaders in `ops/` now go through
  `ops/source_module.load`, which compiles the text and takes no cache; its positive control demonstrates the
  standard loader still going stale, and pins `sys.dont_write_bytecode` because every activator sets it at
  import and would otherwise silently disarm the control depending on test order.

### Cost language, corrected

Provider-reported usage priced at the configured rates is **configured-rate cost** throughout. It is not
invoice-reconciled actual cost, and no provider invoice has been reconciled. `docs/rebuild/cost-definition.md`
already framed it correctly; `CHECKPOINT.md`, `activation-judged.md`, `design.md` and `verification.md` did
not, and the evidence GENERATORS (`verify_live`, `verify-private-release.mjs`, `private-beta-browser.mjs`)
now emit a `cost_basis` field so a corrected document cannot be silently overwritten by the next run.
Existing evidence files are retained as produced and are NOT amended. The database column keeps its name.

### Money-return coverage, confirmed and one gap closed

Nineteen money-return / reservation-release paths were enumerated against the deployed code and sixteen were
already covered — the strongest being `assert_stopped_cleanly` in `test_audio_submission.py`, a literal
exactly-once assertion that counts `usage.release` audit rows against reservation count and refuses to pass
vacuously. The deployed release's `core/jobs.py`, `core/billing.py`, `audit_billing.py` and the billing/audio
test files are byte-identical to what is running, so those results are reused rather than re-run.

**One real gap is now closed**: `core/jobs.py`'s opening membership guard — access revoked BETWEEN enqueue
and processing — had no test anywhere. Every existing revocation test revokes during or after the provider
call, which is the `not_adopted` branch and deliberately KEEPS the charge. A regression that swapped the two
was invisible to the whole suite. Proved by mutation: removing `release(job)` from that branch turns the new
test red (`['held'] != ['released']`), and the file was restored with a matching sha256.

**Two gaps remain open and are named rather than closed**: the `UNREADABLE` refusal kind (nine raise sites in
`core/media.py`) and `AMBIGUOUS` are covered only by unit tests that never call `run_one()`, so no reservation
is created and no release is exercised for either. `AMBIGUOUS` is mitigated — enqueue refuses multi-track
payloads before any hold — and `UNREADABLE` is not.

### One residual, measured rather than assumed

`private_storage._execute` streams the file's raw bytes on the confined container's STDOUT, so the
token exists on the daemon's logging path for the life of that container. Measured here:
`docker info --format '{{.LoggingDriver}}'` is **`json-file`** and there is no `/etc/docker/daemon.json`,
and the helper runs `docker run --rm`, so the container's log file is removed with the container and
nothing persists in a system log. ⚠️ **A daemon switched to `journald` or `syslog` would reopen this**,
and the remedy is one flag — `--log-driver=none` on that `docker run`. Not changed here: `private_storage`
is the sanctioned reader and altering it is a larger decision than a harness repair. Recorded so the next
reader does not have to re-derive it, and so a logging-driver change is understood to be a security
change.

### `main` is ahead of the deployed release, and by what

Nothing here is deployed and nothing needed to be: the changes are a test harness, tests and documentation.
`main` will carry one non-runtime application change the deployed release does not — `verify_live`'s
`cost_basis` field, a management command — plus the corrected documents, the new `ops/` modules and the test
repairs. Recorded here so the next deploy's §2.5 declaration names its full payload rather than only its own.

### The first run of the repaired checks, and the assertion that stopped it

**`05:01:54Z → 05:02:06Z`, release `6d73c5e9026d974053365468101c2f7921544c6c`.** Four checks passed —
including *"Invitation acceptance creates the user and its department membership"*, **the one that failed
on 2026-09-19 with `PermissionError`**. The repaired mail access did its job: the reader answered before
anything was sent (7 files), the invitation was located from **1 changed path, 1 record for this run, 0
for anybody else, 0 outside the synthetic domain**, and the token was **43 characters** — exactly
`secrets.token_urlsafe(32)`.

The fifth check stopped on an `AssertionError`. ⚠️ **THE APPLICATION DID NOTHING WRONG; THE ASSERTION WAS
WRONG, AND IT IS WORTH RECORDING BECAUSE OF *WHERE* IT FAILS:**

> `str()` on a `Decimal` uses SCIENTIFIC notation once the exponent is negative and the value is zero. A
> promotional wallet with nothing reserved stringifies as **`0E-12`**, not `0.000000000000`. Measured:
> `str(Decimal('0.000000000000')) == '0E-12'`; `format(…, 'f') == '0.000000000000'`.

**It fails ONLY at zero — which is the value a money assertion most needs to check**: nothing reserved,
nothing charged, nothing outstanding. Every non-zero amount compares correctly, which is exactly why it
read fine in review and survived three refutation passes. Fixed at the source, `format(value, 'f')` on the
Python side of every money field, in all three harnesses that emit one — not by loosening the comparison,
which would have removed the check instead of repairing it.

**The partial act is judged row by row, before anything else ran**, at
`docs/foundation/mutations/20260919-quillmd-account-checks-run2.md`. Every MUST-NOT-CHANGE row held —
jobs 14, usage 14, receipts 11, reservations 12/0, charge and cost totals identical to the digit,
departments 3, patients 3, encounters 12, **provider calls 0**. Every MUST-CHANGE row the completed checks
were responsible for matched exactly: users 8→9, promotional wallets 8→9, welcome entries 8→9, memberships
7→8 in the inviting doctor's own department, promotional balance **+10 exactly**, and five new audit rows
that are all account/auth/email actions with no billing action among them. Three rows are short, and all
three are the same fact — the run stopped — recorded against the check that never executed rather than
explained away.

## 2026-09-19 — the private invitation and password-recovery checks PASS

**8 of 8, `complete: true`, `05:12:48Z → 05:13:34Z`, against release
`6d73c5e9026d974053365468101c2f7921544c6c`** — read from `/health/` on both surfaces and recorded as the
measured value, not as the argument that was passed in. Evidence:
`rebuild/.runtime/private-accounts-verification-run2.json` (0600). The earlier failed run's file is
retained unmodified beside it.

| check | result |
|---|---|
| Both permanent services serve the exact revision under test | ✅ |
| The confined outbox reader answers before anything is sent | ✅ 8 files |
| Doctor signs in and creates a departmental invitation | ✅ department selected by id, not by the label two departments share |
| Invitation acceptance creates the user and its department membership | ✅ — **the check that failed with `PermissionError`** |
| Exactly one $10 welcome credit, and a retried acceptance does not issue a second | ✅ |
| Cross-department access remains denied to the invited employee | ✅ |
| Password recovery succeeds, invalidates the existing session, and its link is one-time | ✅ |
| Administrator MFA remains enforced and a replayed code is refused | ✅ |

### Judged against the declaration, every row

`docs/foundation/mutations/20260919-quillmd-account-checks-run2.md`, committed `05:06:36Z` — provably
before the act started at `05:12:48Z`.

**MUST CHANGE — all matched:** users 9 → **10**; promotional wallets 9 → **10**; welcome ledger entries
9 → **10**; active memberships 8 → **9**, in the inviting doctor's own department; invitations / accepted
5 / 4 → **7 / 6**; promotional balance 89.782275898950 → **99.782275898950**, exactly +10; TOTP `last_t`
59657718 → **59659827**; outbox files 8 → **11**, exactly the two invitations and one recovery message
declared; sessions 55 → **61**; the new account's password replaced by recovery.

**MUST NOT CHANGE — all held:** jobs **14**, usage rows **14**, provider receipts **11**, reservations
**12 / 0 held**, total charged **0.217724101050**, total configured-rate cost **0.145149400700**, paid
balance **0**, departments **3**, patients **3**, encounters **12**, provider calls **0**. The first run's
account is untouched — balance 10, reserved 0, one welcome entry, one invitation, one membership.

**The audit rows were read, not assumed.** 22 rows since the act began: `auth.login` ×7,
`auth.login_failed` ×3, `email.outbox` ×3, `department.invite` ×2, `department.invitation_accepted` ×2,
`auth.recovery_requested`, `auth.password_recovered`, `credit.welcome`, `api.encounter_read`,
`admin.dashboard`. **The only billing-family action in the whole set is the single `credit.welcome`** — no
`usage.*`, no `job.*`, no payment, refund or reconciliation. The three `auth.login_failed` rows are the
negative evidence: the administrator's empty second factor, the replayed code, and the old password after
recovery.

### What the checks actually proved, and what they do not

- **Exactly one welcome credit, proved against a real second grant attempt.** The account holds **two
  invitations, both accepted**, and **one** welcome ledger entry of `$10.000000000000` in **one** wallet,
  with **one** membership. A GET on the spent link is also refused (404) — but that is the LINK, not the
  grant, and on its own it would pass against a build that funded the wallet twice.
- **Cross-department denial, proved over HTTP by a real foreign reader.** The Ultrasound clinician is
  refused an X-ray encounter (**404**) on the exact URL the invited employee reads successfully (**200**),
  so the denial cannot be a broken route. The employee sees 1 of 3 patients and 0 departments outside
  their own.
- **Recovery is complete**: the pre-existing session was bounced to `/login/`, the old password stopped
  working, the new one worked, and the link was refused on reuse.
- **Administrator MFA is enforced and single-use**: a correct password with no second factor does not sign
  in, and the same code replayed in a second context is refused. ⚠️ The check also asserts the refusal was
  NOT a rate-limit page, because a sign-in refused before the authenticator is consulted would otherwise be
  recorded as a replay refusal it never earned.
- ⚠️ **What this does NOT show.** `QUILLMD_EMAIL_MODE` is `file`. Reading the private outbox demonstrates
  that the APPLICATION composed and handed off the message. It says nothing about whether a message would
  arrive in a real mailbox, and nothing here may be reported as if it did. **A controlled real recipient is
  still an owner action.**
- The mail access recorded itself at each step: three routes located, each from **1 changed path, 1 record
  for this run, 0 for anybody else, 0 addressed outside the synthetic domain**; invitation tokens 43
  characters (`secrets.token_urlsafe(32)`), recovery token 88. No token appears in the report, the log or
  any assertion.

## 2026-09-19 — the three named engineering gaps, closed

**Application revision under test: `6d73c5e9026d974053365468101c2f7921544c6c`**, read from `/health/` on
both surfaces. **Harness revision: `58a8dc37` and later** — the two are deliberately reported separately,
because the harnesses have been ahead of the deployed application since `cb39b6a2`. Nothing in this work
is deployed and nothing needed to be: only tests, operations modules and harnesses changed.

### 1 · The outbox readers: which remained affected, and what was added

**Measured, not assumed: none remained affected.** Every file that reads the outbox or matches an account
link — `verify-private-accounts.mjs`, `verify-private-release.mjs`, `identity-browser.mjs`,
`private-beta-browser.mjs` — routes through `ops/private_mail`. No file globs the outbox, reads it with
`read_text()`, or takes a first regex match. `email-delivery-verify.py` matches only rendered page text
and is not an outbox reader.

**What was still missing was the message IDENTIFIER, and it is now bound.** Selection and binding answer
different questions:

- selection — `ops/private_mail` — asks *was this written TO me, in a file this run changed*;
- binding — `ops/account_mail`, new — asks *is this the message this run CAUSED*.

A stale invitation to the same address, a superseded record, or a token lifted from another account's
message and delivered to ours all answer the FIRST question correctly. Only the second refuses them, and
a failed binding is a refusal, never a fallback to the next candidate.

The bindings are exact and leak nothing. An invitation token is bound by `sha256(token) ==
Invitation.token_hash` — the application already stores `digest(raw)` on the row, so it is an identity
check against the record and a hash is not a credential. A recovery token is bound by its `uidb64`
segment decoding to the user's own primary key AND `default_token_generator.check_token`, which is the
application's own verifier.

⚠️ **THE BINDING IS ONE MODULE BECAUSE THE ORIGINAL DEFECT WAS ONE READER, COPIED.** Pasting the
application-side predicate into four inline Python snippets would have rebuilt the same trap one layer up.
All four harnesses call `account_mail.locate`, and each asserts `token_bound` is exactly `true` — a run
with no binding records `null`, which must not read as bound.

Proved by thirteen new tests and a read-only control against the live database: five of the six invited
addresses on this host would REFUSE a binding because every invitation they hold is accepted, and the one
open invitation binds — so the check discriminates rather than always refusing.

### 2 · UNREADABLE and AMBIGUOUS, exercised where the money is

Both kinds previously had unit-level evidence only. Every test called `probe_submission`,
`plan_normalisation` or `normalise_submission` directly; none called `run_one()`, so no reservation was
created and no release was exercised. The assertions proved the classifier and said nothing about the
money.

⚠️ **AND MEASURING CORRECTED THE PLAN TWICE, WHICH IS WHY IT IS WORTH RECORDING.** The first version of
these tests assumed an unreadable upload reaches the worker holding a reservation. It does not. Two shapes
were tried and both are refused at the HTTP entry point, before anything is held:

- an unprobeable payload — *"The length of this recording could not be determined (unsupported format),
  so its charge cannot be confirmed. Nothing was sent."*
- a `.webm` carrying Vorbis rather than Opus — *"(WebM audio that is not Opus)"*.

`core/audio.py` parses the container itself, and a recording it cannot measure cannot have a charge limit
confirmed. That is the stronger outcome and it is now proved for both, with no job, no reservation, no
charge and no provider call.

⚠️ **THE PAIRING IS ITSELF A FINDING, AND IT IS NOW ASSERTED RATHER THAN IMPLIED.** Two readers answer
"what audio can this product carry": the pricing gate in `core/audio.py` and the remux table in
`core/media.plan_normalisation`. Today the pricing gate is the STRICTER of the two, which makes the remux
table's "no lossless remux is defined" branch defence in depth rather than a path an upload reaches. That
can stop being true in either direction — a codec added to the table that pricing still refuses becomes
dead code; a codec pricing starts accepting that the table lacks makes the table the only guard, holding a
reservation when it fires. A test now pins the pair so a change to either side has to face it.

**What genuinely reaches the worker with a hold outstanding** is a recording that was fine when priced and
is not fine when read — the stored bytes change between enqueue and processing. That is the same
operational class the `MISSING` kind exists for, whose own regression test uses exactly that device. Both
kinds are now exercised through `run_one()` with the full proof set:

- no provider request, and no provider receipt;
- the reservation released EXACTLY once — one `usage.release` audit row per reservation, never two;
- nothing charged, nothing still reserved, balances back to their starting values, `audit_report()`
  green with no unresolved jobs;
- the job in its terminal `failed` state, naming the cause to the doctor, and not inviting a retry for a
  cause re-sending the same bytes cannot fix;
- **the encounter still usable** — the notes still edit and a new recording still queues afterwards;
- **replaying the failure handling cannot release twice** — `release()` is called twice more and no
  reservation, audit row or balance moves.

`AMBIGUOUS` past the hold keeps its reachability condition written into the test: `enqueue` refuses a
multi-track payload before any hold, so this branch is reached only when the stream count is unknown at
enqueue and known at processing, which a probe timeout on a loaded shared host produces. It is exercised
because the branch releases money, not to raise a number.

### 3 · ⚠️ AND THE GREEN AUDIT IS NOW PROVED NON-VACUOUS

Every test above ends by asserting `all_checks_pass`. That means something only if a red audit is
reachable, so a stranded reservation is planted deliberately in an isolated fixture — a job that ended
while its hold is still held, which is exactly what a half-applied refusal leaves behind. The audit finds
it: `ended_jobs_hold_no_funds` goes false, the job id is named, and `audit_billing` exits non-zero so a
scheduled run cannot pass over it. Releasing the hold turns it green again, and a wallet counter that
drifts from its held rows — the shape a double release leaves — is caught by a second, independent
invariant.

### 4 · The activator range test and the stale import cache

**Both were already repaired; both are now confirmed against the exact current source, with the bytecode
caches deleted first so a stale one cannot be what makes them pass.** 46 tests green.

The falsifiability proofs were re-run in a **disposable `git worktree`, one writer, reaped immediately** —
not in the working tree, which is the shape that let a stale cache answer for a restored file. Each
mutation asserted its application by reading the file back, its restoration by sha256, and the sandbox's
cleanliness by `git status` rather than by the script's own bookkeeping. All six wrong-constant shapes are
caught, including the one an earlier refutation pass measured as passing — a `SHIPPED` naming a later merge
— which the checkpoint cross-reference now closes.

**The stale-cache repair was proved under its exact trigger**: a mutation of the same byte length with the
mtime restored. The standard loader read `6d73c5e9026d` — the value from BEFORE the mutation, the defect —
while `ops/source_module.load` read `000000000000`, the file as it actually stood. Restoration verified by
sha256 and by git.

### Verification

`bash scripts/ci/verify-fresh.sh python` against a disposable database: **417** application tests
(8 skipped — the Word runtime helper is not built locally; CI builds it), **27** document tests, **260**
operations tests. Exit 0.

### Nothing here is deployed

Only tests, operations modules and harnesses changed; no runtime application file was touched, so no
deployment was warranted and none was performed. The served revision remains
`6d73c5e9026d974053365468101c2f7921544c6c`, and `main` continues to carry one non-runtime application
change ahead of it — `verify_live`'s `cost_basis` field, a management command.

## 2026-09-19 — the confined mail helper: the logging claim was WRONG, and the helper is hardened

**Application revision: `6d73c5e9026d974053365468101c2f7921544c6c`**, read from `/health/` on both
surfaces. **Repository/harness revision: `56b02381` before this change.** Nothing is deployed: only the
operations helper, tests and documentation changed.

### ⚠️ THE EARLIER REPORT WAS WRONG, AND MEASURING IS WHAT SHOWED IT

That report said raw file bytes on container stdout were *"harmless under `json-file` with `--rm`"*. They
were not. Measured on this host:

    docker info --format '{{.LoggingDriver}}'        -> json-file
    attached `docker run --rm`, default driver:
      docker logs <running container>                -> the canary, 1 occurrence
      docker inspect --format '{{.LogPath}}'         -> /var/lib/docker/containers/<id>/<id>-json.log
      the client's own pipe                          -> the canary, 1 occurrence

**Attachment does not bypass the logging driver, and `--rm` does not prevent the recording** — it deletes
the file when the container exits. The reasoning in that report confused *the log is removed afterwards*
with *the log is never written*, which are different facts.

**And the helper really did write sensitive content there.** `_helper_main`'s `read` branch writes the
complete file to stdout, so every mail read put an outbox file — tokens included — into that container's
json log for the container's lifetime.

### Scope of the actual exposure, assessed rather than assumed

- **What:** complete outbox file bytes, including raw invitation and recovery tokens, for the lifetime of
  each helper container (sub-second).
- **Where:** `/var/lib/docker/containers/<id>/<id>-json.log`, root-owned. No network exposure.
- **Now:** every helper ran with `--rm`, so each log was deleted with its container. No `python:3-slim`
  container remains on this host, and the operator account cannot read `/var/lib/docker/containers`
  directly (`Permission denied`).
- **Who could have read it:** root, or a holder of the Docker socket — which is the operator account, and
  that account already has strictly greater access by the same socket (`docker run -u 0:0` reads the whole
  host, the outbox included). ⚠️ **That bounds the harm; it does not make the recording acceptable.**
- **Which tokens:** the eleven `email.outbox` events on record. Every invitation among them is
  **accepted**, so its link is already refused by `invite_accept`'s `accepted_at__isnull=True` filter —
  demonstrated live on 2026-09-19 when a consumed link answered 404. Every recovery token among them is
  spent by its own completed password change, because Django derives the token from the password hash.
  **No affected token is still redeemable.**
- **One live invitation exists and is NOT in the affected set.** `release-1789778057188`, created
  `09-19 00:34`, unaccepted, expires `09-26`. Its message was written at `00:34:17` by
  `verify-private-release.mjs`, which at that revision still used the **operator-account** glob reader —
  the one that fails with `PermissionError` on the outbox, which is exactly why that check failed and is
  recorded as failed in `beta-deployed-browser-verification.json`. Its token therefore never entered a
  helper container. It is left intact rather than revoked, because revoking data that is not demonstrated
  affected is a mutation nobody asked for; it is flagged here so the decision is visible.

### The hardening: two narrow changes

**1 · Selection and binding moved INSIDE the helper.** A new `select` action reads the named files with
the same verified per-file read as `read` — same ownership, mode and stat re-checks — then splits records
on Django's 79-dash separator, matches the exact recipient, applies the purpose pattern, and checks the
record binding. It returns **one route plus counts**. Unrelated records are counted and dropped on the
service side.

⚠️ **THE PREVIOUS ARRANGEMENT REJECTED THEM ONE ADDRESS SPACE TOO LATE.** `read_file` is all-or-nothing by
construction, so finding one message meant exporting every message sharing the file into the operator
process and rejecting the unrelated ones afterwards. Under the append-collision the callers exist to
handle, that exported file can hold somebody else's live token.

The binding crosses as a **value, not a callable**: `sha256(token)` against `Invitation.token_hash` for an
invitation, and the `uidb64` prefix for a recovery token. A digest is not a credential and identifies the
record exactly. `check_token` is the one check that cannot go in — it needs the secret key and the user's
password hash, and the helper has no database and no network — so it runs last, on a token that has
**already** satisfied the in-container binding.

**2 · Every invocation passes `--log-driver=none`.** Measured, both arms, with a token-shaped canary:

    default driver   LogPath present   canary in `docker logs` = 1   client pipe = 1
    --log-driver=none  LogPath EMPTY   canary in `docker logs` = 0   client pipe = 1

The functional channel is unaffected; the logged copy is gone. **The shared Docker daemon is not
reconfigured**, no unrelated service restarts, outbox permissions are unchanged, no token endpoint is
added and no sudo is granted. Every prior control is retained and asserted by test: `--rm`,
`--pull=never`, `--network=none`, `--read-only`, `--cap-drop=ALL`, `no-new-privileges`, the read-only
bind, and the service `uid:gid` (996:988). Criteria travel on **stdin**, never argv.

### The matcher is no longer duplicated

`private_mail` had its own copy of the record matcher; it now delegates, and re-exports the record
separator and synthetic domain from `private_storage` rather than restating them. The selection tests
moved with the matcher into `ops/test_confined_select.py` — one implementation, one test home.

### Verified, success and failure paths, with dummy tokens and an unrelated-message canary

All tokens below are dummies. Every path returns counts and a reason; **no unrelated value appears in any
returned result**:

    our own record alone, bound                 found=True   leaked=none
    our record sharing a file with another      found=True   leaked=none
    a stranger token delivered to our address   found=False  reason=token_not_bound
    two records for our address                 found=False  reason=more_than_one_record
    no record for us                            found=False  reason=no_record_for_this_run
    a NON-synthetic canary shares the file      found=False  reason=outside_synthetic

⚠️ **The canary is the one that matters**: a live-shaped token for a non-synthetic address. The previous
design exported its complete bytes into the operator process; the hardened design counts it and stops,
and the result carries no trace of it — asserted by rendering the whole result and searching it.

**Live, through the real container:** `select_message` read the three newest real outbox files and
returned `{records_for_this_run: 0, records_for_others: 3, records_outside_synthetic: 0, found: False,
reason: 'no_record_for_this_run', route: ''}` — counts and a reason, no content, no token. The real argv
was captured and carries `--log-driver=none` with every other control intact.

**Falsifiability, proved in a disposable worktree, one writer, reaped immediately** — each mutation
asserted its application by reading back, its restoration by `sha256`, and cleanliness by `git status`:

    the logging control removed                    caught
    the matcher dropped from the shipped helper    caught
    the invitation binding disabled                caught
    the non-synthetic canary guard disabled        caught
    token_bound always reported true               caught

### Verification

`bash scripts/ci/verify-fresh.sh python`: **417** application tests (8 skipped — the Word runtime helper is
not built locally; CI builds it), **27** document tests, **270** operations tests. Exit 0. Only checks
affected by this change were re-run beyond that gate; no broad audit and no real-provider campaign.

## 2026-09-19 — the three Word findings: reproduced, two repaired, one honestly unfinished

**Application revision: `6d73c5e9026d974053365468101c2f7921544c6c`** (unchanged; nothing was deployed).
**Repository revision: `3f50bb82` and later.** The review package's artifacts are from release `8f8a6763`,
and `rebuild/documents/` is **byte-identical** between `8f8a6763` and `HEAD` — so the exporter that
produced them is the exporter running today, and all three findings reproduce by code identity rather than
by re-running an unchanged path.

### 1 · Table pagination — CONFIRMED and REPAIRED

Measured on the original and on both real exports: the measurement table carries **no `tblHeader`, no
`cantSplit`, no `keepNext`**, and the title paragraph above it has none either. The safeguards were absent
in the template and the exporter faithfully preserved that absence.

`rebuild/documents/layout.py` adds them to the EXPORT on its way out, at the single seam every DOCX export
passes through, **before** the caller hashes the file — so the uploaded original keeps its own bytes and
`export_sha256` describes what is actually stored.

⚠️ **A REPEATING HEADER ROW IS DELIBERATELY NOT USED, AND A TEST PINS THAT DECISION.** Word repeats a
`<w:tblHeader/>` row *verbatim*, and this table holds TWO sections — `** Right Leg **` at row 0 and
`** Left Leg **` at row 14. Repeating row 0 would print `** Right Leg **` above the LEFT leg's
measurements: a caption that is wrong about which limb the numbers describe. OOXML also cannot make a
repeated heading read "(continued)" on later pages only. Continuation is handled by keeping each heading on
the page where its own measurements begin, which is checkable on the page.

Heading rows are found **by content** — the columns beyond the first repeat the table's own captions —
matching rows 0 and 14 and no measurement row, because a filled measurement cell holds a number. Measured:
2 heading rows, `cantSplit` on all 28 rows, `keepNext` 1 → 8, **not one visible character changed**,
paragraph/control/row/cell counts unchanged, every other zip member byte-identical.

### 2 and 3 · The two fixtures are misnamed at their SOURCE — generation, not packaging

- **`all-blanks.docx` fills every template blank** — all 52 measurements, 6 locations, 4 demographics, and
  the qualification's own checks say exactly that. It was shipped labelled *"every answer reviewed as
  missing"*, its precise opposite. Re-measured with a corrected `w:t` regex: **28 of 28 controls filled**.
- **`long-answer.docx` inserts a 19,931-character BODY PARAGRAPH** via `review.ParentNode.InsertBefore`,
  and the check asserts it in `non_control_text` — outside every mapped control. Longest mapped answer:
  **89 characters**. Two new checks assert both facts so the fixture cannot be mistaken again.

⚠️ **THE REGEX I FIRST MEASURED WITH WAS WRONG AND I CAUGHT IT MID-TASK.** `<w:t[^>]*>` also matches
`<w:tcW>`, so the first pass reported "27 filled, 1 placeholder" and inflated paragraph lengths. Every
number in this entry was re-taken with `<w:t(?:\s[^>]*)?>`.

### Checklist corrections, each verified before editing

- **No font defect, and none should be raised.** The owner confirmed the ORIGINAL Word dropdown yields the
  same Aptos 12-point answer as the export. The Liberation Serif / DejaVu Sans note applied only to a Linux
  evaluation render with no Aptos installed.
- **"headers and media byte-identical" was false for headers.** `header1.xml` 4,188 → 3,435 bytes,
  `header2.xml` 4,205 → 3,451, both `.rels` differ. The media half is true and kept.
- **All 52 measurement rows** claimed the unit was *"printed by the original cell"*. Cells hold bare
  numbers (`2.25`, `501`); the unit is printed **once in the column heading**.

A new section **F2** covers the pagination rows and states what is deliberately not done.

### ⚠️ A CLAIM I MADE AND WITHDREW

PR #1214 asserted that CI exercises the real WM IOV export path. **It does not.** `ops/sdk_sandbox` refuses
a Word processor owned by the calling account, and on the engineering host **and** on the CI runner the
account running the tests owns the runtime — all 8 `test_wm_workflow` tests skip in both, and the CI log of
that very run says so. **The layout repair is verified STRUCTURALLY** — against the real original and real
exports, byte for byte — **and has not been through a live `fill_template` call anywhere.**

### The genuine missing-answer and long-answer documents are NOT delivered

Six attempts through the deployed application, each judged against the declaration before the next. The
first three were harness defects and are recorded in the commits that fixed them: a missing CSRF token; a
CSRF cookie whose name this deployment changes per surface (`quillmd_doctor_csrf`); a revision read from
the first of three `[name=revision]` inputs, with the 14 `claim_reviewed_*` boxes omitted.

⚠️ **THE REMAINING THREE WERE NOT THE HARNESS. THEY WERE THE CLINICAL REVIEW MODEL, BEHAVING CORRECTLY.**

- `save_answers` runs each prewritten statement through `source_quote_evidence`, which demands a COMPLETE
  SOURCE LINE from the notes for that exact label. A statement nobody can point at in the notes has not
  been reviewed, the review is recorded `complete=False`, and the finalization helper refuses it.
- Each statement variant declares `required_control_keys` and `empty_control_keys`. Choosing
  `not_documented` by name left `claim_9` and `claim_39` — which do not offer it — on defaults that
  REQUIRE a filled control, and the resolver said so: *"The chosen answers and prewritten statement
  alternatives conflict."*

Reading the second of those as a form problem three times was mine, not the application's. **Zero documents
were finalized.** Judged against the declaration: encounters 12 → **14**, which is the declared end state
but reached as two missing-answer drafts rather than one of each kind; **finalized stayed 7 and exports
stayed 7**. Every MUST-NOT-CHANGE row held exactly — jobs 14, usage 14, receipts 11, charged
`0.217724101050`, cost `0.145149400700`, reservations 12/0, patients 3, templates 11, users 10,
promotional balance `99.782275898950`, **provider calls 0**. The two encounters are left in `review`, not
deleted, and are flagged here.

### The new package

`rebuild/.runtime/word-review-package/quillmd-word-review-20260919.zip` — **315,232 bytes**, sha256
`d88b397d8468453c5b3c406635a2538aba0a0819eec60c6909cf0aa798cfc66c`, 10 files, built by the tracked
`scripts/build-word-review-package.py`, which GENERATES nothing and refuses if a BEFORE/AFTER pair comes
out identical or carries no safeguards.

It ships each real export **twice — before and after the repair** — because the repair changes no visible
character and only Word can show the difference. Independently verified on the archive: `cantSplit` 0 → 28,
`keepNext` 1 → 8, `tblHeader` 0, visible text identical, no other zip member changed. The two SDK fixtures
travel under names that say what they are.

⚠️ **The repair is MERGED AND TESTED BUT NOT DEPLOYED**, so files 03 and 05 are what the exporter *will*
emit, not what the running service would hand a doctor today.

### Verification, and what kind it is

417 application tests (8 skipped — the Word runtime ownership above), **41** document tests including 14
new layout tests, **270** operations tests. Exit 0.

⚠️ **THESE ARE STRUCTURAL TESTS. They prove what the file says, not what Word draws.** Native Word
acceptance is **OPEN** and stays open until the pairs in the new package are opened in Microsoft Word.

## 2026-09-19 — genuine Word candidate execution, private activation pending

This entry supersedes the earlier claim that matching exporter source was execution
proof. At the start of this milestone, repository main was
`ae6c48bf493a5232ae5016e1086c8e3c6d1e396e`; actual doctor/admin health independently
reported `6d73c5e9026d974053365468101c2f7921544c6c`, synthetic-only. Public app/admin
still answered maintenance503. No application provider configuration changed.

The processor prerequisite was resolved using trusted UID996/GID988 against the
existing operator-owned installed SDK, with default AppArmor, no application
capabilities, NoNewPrivs/seccomp and ordinary ownership checks. Eight actual Word
integration tests ran twice (baseline and finished runtime candidate): **8/8,
zero skips**. Final candidate execution was at
`7f3b5313e775c1f43bc7ac0b7998ac86ef256e0e`; evidence is
`.runtime/word-identity-verification-20260919/final-eight-tests-7f3b5313.json` in
the permanent rebuild. CI now requires these tests and installs the processor
outside runner-writable ancestors; missing prerequisites fail instead of skip.

The previous pagination repair protected only the first row after a heading.
A concrete long mapped-location diagnostic lost limb/unit context on continuation
pages. The repair now partitions the qualified28-row table into original Right
and Left14-row sections, with each section's own repeating heading and units.
Only six long free-text location rows may flow; numeric rows remain together.
One empty separator paragraph is added. All original visible text, questions,
rows, cells and controls remain in order; unrelated tables are left unchanged.
18 focused layout checks and15 independent preservation/counterexample checks passed.

An isolated localhost9142 candidate with its own synthetic DB/state completed the
actual browser workflow on its first attempt: upload unchanged original, create
synthetic drafts, demonstrate all90-answers-missing finalization refusal, edit source,
review every field and statement, finalize and download. The valid partial case
has88 empty mapped answers; the long case has90 supported answers, a14,444-character
mapped patient name and six mapped location answers each over4,400characters.
Every assertion, INCLUDING not-documented variants, has its complete explicit
synthetic source line; no clinical gate was bypassed. Neither case needed a provider
request or direct database mutation. Both downloaded hashes match recorded hashes.

Candidate artifacts:
`.worktrees/word-export-verification/rebuild/.runtime/word-export-verification/candidate-attempt1/`.
Actual downloads independently passed all90 mapped-answer checks,28 original
controls/options,28 rows,2 correct limb tables and missing-value preservation.
Packager checks initially misread the original placeholder option and assumed a
missing control contained placeholder text; actual XML proved empty content with
original options intact. Those verifier errors were repaired. Positive checks and
six deliberate in-memory wrong-limb/unit/answer counterexamples passed without
changing the genuine files.

This is candidate evidence, not deployment. Follow the new committed activation
and subsequent two-draft verification declarations. Preserve both previous failed
live review drafts and reuse them; do not replay AI generation. The new archive
builder only copies independently verified genuine downloads and never repairs
or manufactures them. Native Microsoft Word acceptance remains pending; Linux
rendering is separately labelled evaluation evidence. The final deployed revision,
served exports, archive and all evidence paths will be recorded in the append-only
private `.runtime/CHECKPOINT-LATEST.md` after the declared acts actually complete.

## 2026-09-19 — owner workstation native Word acceptance (additive)

The owner completed native Microsoft Word appearance acceptance of
`quillmd-word-review-20260919-verified.zip` (220764 bytes,
SHA256 `2bd478ee88c1dc26f96171bcef22de9c1680c9ef279f985c1a828c7827405b01`):
Word365 Version2608 Build20326.20144, five documents,43 rendered pages,
preserved long answers and controls, no demonstrated rendering defect, unchanged
original hashes. See `native-word-acceptance-20260919.md` for per-file hashes and
precise evidence scope. This owner attestation closes native appearance acceptance;
it is not an agent-operated Word test or public-launch approval.

Independent read-only checks confirm ZIP integrity, all5 document sizes/hashes,
and all8 checksum-list members. Candidate7f3b5313 and actual served dc4eb42c
remain distinct execution records. Historical archive/manifest/checklist, failed
attempts, milestone report and evidence index were preserved without rewriting.
Their old “pending” status is superseded by this dated addendum.

Partial exports have exactly2 answered mapped inputs (patient name and exam side)
and88 missing inputs, plus14 separate reviewed statement/identity replacements.
The additional exam-type text has an exact recorded source quotation and
claim_9/exam_choice approval. Clinician text uses the authenticated synthetic
finalizer through reviewed trusted identity claims; the signed timestamp is server
metadata. No unsupported additional answer was demonstrated; no clinical output
or finalization record was changed. Private provenance/acceptance evidence is
linked from the append-only `.runtime/CHECKPOINT-LATEST.md`.

Authorized configuration inspection identified no Stripe sandbox pairing/test key,
controlled owner recipient, approved B2 destination/key, or authentic provider
billing evidence. Reusable Resend sender/key exist, but DNS and credential presence
alone do not prove current provider sender verification. The sole currently needed
owner email input is a controlled recipient; engineering owns sender verification
and delivery tests. `owner-actions.md` now starts with the current dependency
list while preserving the historical body verbatim.

Next supported engineering work is isolated qualification/repair of the prepared
independent-reviewer SSH access. No reviewer grant, shared SSH configuration change,
provider call, app restart, data reset, or public activation is part of this update.
Doctor/admin continue to report dc4eb42c, synthetic-only; public app/admin remain
maintenance503. CPT, provider reconciliation, offsite recovery, independent testing
and patient-data agreements remain separately gated.

### Reviewer access qualification completed (same update)

The actual isolated OpenSSH fixture reproduced reverse TCP forwarding despite the
old key's permitopen restrictions. Shared-account grant now refuses; prepare emits
a dedicated-account Match policy and SSH expiry without granting access. Repairs
also cover sole-key removal, concurrent removals, audit availability before
mutation, exactly-one-key validation and unreadable status. Lead independently
reproduced audit-order/concurrent/status counterexamples and reran all20 focused
checks successfully with no skips. CI now explicitly runs this SSH qualification.

Evidence: `.runtime/reviewer-access-qualification-20260919/report.json`, SHA256
`1c0cb2b1181e313ca91d8a7cc3b646b27ed3e2947a656363547e33b5eb253278`,
and its test log. The original helper and failed harness/refutation evidence are
preserved. No host SSH policy, actual reviewer key or application data changed.

The isolated fixture is unprivileged; it cannot establish a Unix-forwarding
positive control, because the legacy setup also refuses it. Actual dedicated
account/effective-host-policy testing and scheduled termination of established
connections remain activation prerequisites. Key removal and expiry alone do not
terminate existing tunnels. This is internal preparation, not independent testing.
`pentest-scope.md` has the additive correction and exact activation steps.

## 2026-09-19 — Stripe sandbox readiness and reporting repair

Read stripe-readiness-20260919.md and the updated external-verification-runbook.md.
Protected application Stripe key/signing secret remain absent; CLI1.51.0 is
unpaired. The unchanged runner executed its dry run against served dc4eb42c:
both doctor loopback names passed, actual receiver503, exit1 before login/checkout;
0checkouts and0Stripe calls. Preserve the original private attempt JSON.

Two offline counterexamples demonstrated full-success reporting with required
cases skipped or unverified. The repaired runner requires CLI before checkout,
tracks attempted submission, and returns incomplete/exit2 until real delivery,
retry and order evidence exists.8 focused outcome tests and5 credential tests
passed without database/provider access; actual changed final block independently
returned incomplete for the original counterexample. No application billing policy
or welcome-credit change. These are isolated tests, not sandbox event evidence.

The sole current owner action is sandbox pairing plus a restricted Checkout
Sessions Write key in protected rebuild/.env; engineering obtains the listener
secret and performs integration verification. All other inputs are deferred in
one checklist. Word acceptance and reviewer-host qualification remain complete.
No external reviewer access, public activation, app restart or real patient data.
Repository/tooling and served revision are distinct; final exact CI/merge and
private evidence paths will be appended to .runtime/CHECKPOINT-LATEST.md.
