# Continuation pointer — private beta verification, 2026-09-17

**Preserve this new implementation and all of its data. No further reset or old-application cleanup is needed.**

The continuation adds expiring password recovery with administrator MFA, verification resend, invitation revocation, explicit provider HTTP/resource identifiers and configured pricing fingerprints, durable Stripe test-event state and refund safeguards, organization-owner top-ups, encrypted backup/isolated restore tooling, and separately privileged database roles with service secret isolation. See `private-beta-qualification.md`, `account-recovery.md`, `billing-provenance-verification.md`, `backup-restore.md` and `security-readiness.md` for bounded evidence and remaining gates.

Local final verification before this PR: **112 Django/PostgreSQL tests**, **26 document/backup tests**, **19 form qualification cases**, **13 extended fixture browser checks**, **17 restored-database role assertions**. A four-case adversarial provider-deduplication counterexample was independently reproduced on the prior test schema; migration0010 repairs all four. These local results do not alone establish activation.

The reviewed updater `scripts/update-private-beta.py` requires exact merge-commit CI, the committed mutation declaration, a verified new-system restore report, stopped private services, unchanged database/file hashes and unchanged shared containers/public statuses. It writes the actual release result to `rebuild/.runtime/private-beta-activation.json`. Role activation and final live synthetic tests are recorded separately.

**Read `/opt/meddoc-pro/rebuild/.runtime/CHECKPOINT-LATEST.md` if present for the final running release, post-activation evidence and exact next steps.** It is a protected operational checkpoint; never publish its linked credentials or provider payloads. Health on ports9130/9131 reports the release captured when each process starts. The earlier checkpoint below is historical baseline only.

External dependencies remain: Stripe test key/webhook secret; a controlled email inbox, current sender-domain verification and reachable authenticated HTTPS origin; provider invoice/usage exports and account discounts/credit treatment. These were requested without printing secrets. CPT remains unavailable until licensed usage rights and dated content are verified. Additional Word SDK/OCR licensing is optional pending the exact forms required; WM IOV's28 content controls are currently unsupported. Independent penetration testing and patient-data agreements/controls remain release gates. Public doctor/admin maintenance stays in force.

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
