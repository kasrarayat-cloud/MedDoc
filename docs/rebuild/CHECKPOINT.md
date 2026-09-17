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
