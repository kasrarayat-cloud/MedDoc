# QuillMD fresh rebuild — durable checkpoint

Updated 2026-09-17. The owner's latest decision is **NO MIGRATION**. No old users, patients, documents, templates, balances or history are imported. Do not revive old migration/backfill/compatibility plans from historical documentation.

## Where work lives

Implementation branch: `feat/quillmd-fresh-start`, isolated tree `/opt/meddoc-pro/.worktrees/quillmd-fresh`. Shared deployment tree stays `/opt/meddoc-pro` on main. Fresh code is `rebuild/`; marketing is `apps/marketing` plus `packages/shared`.

Private doctor listener: **127.0.0.1:9130**. Private administrator listener: **127.0.0.1:9131**. Use SSH forwarding; no public preview ingress. Login is required and administrator TOTP is enforced. Synthetic passwords/bootstrap MFA enrollment live in `rebuild/.runtime/private-access.json` (0600), never Git. The file is initially under the isolated tree and moves with the new runtime to the shared tree during declared activation.

Fresh PostgreSQL: container `quillmd-fresh-postgres`, loopback55438, named volume `quillmd_fresh_pg`, database `quillmd_fresh`. Its own random credentials are in the private new environment, and its Docker resource labels declare fresh ownership. It has no connection to the old `meddoc` database. All data in this app is synthetic. Django migrations here only create the fresh schema.

The implementation PR replaces obsolete workflow contexts with **Fresh application tests**, **Marketing build**, **Private browser and accessibility**, and **TruffleHog (verified-only, diff-scan)**. Required workflow citation is CI plus secrets-scan. Legacy tests named for the removed application cannot certify this build.

At checkpoint commit, public maintenance reload and process relocation await exact merge-commit CI. Their committed declaration is `docs/foundation/mutations/20260917-quillmd-private-activation.md`; local execution evidence, final commit/PR identifiers and current process paths are recorded durably in `/opt/meddoc-pro/rebuild/.runtime/activation-result.json` after completion. Check that evidence before assuming activation happened. Do not use old deploy-prod.sh for this Python application.

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
| Deepgram | Live medical transcription API; bounded synthetic one-second silence accepted and metered. Speech/clinical accuracy has not been established by that smoke. |
| OpenAI | Adapter exists; available key returned401. Optional replacement credential needed only to use this provider. |
| Stripe | Test checkout, signed webhook, duplicate/refund/reconciliation logic implemented; synthetic signed-event tests pass. No actual Stripe test checkout has completed; test key and webhook secret still needed. Live mode disabled. |
| ICD-10-CM | Real official CMS/CDC terminology loaded, source hash and effective dates recorded. April2026 set expires September30; refresh before October clinical use. |
| CPT | No licensed content loaded or simulated as licensed. Licensed feed/license identifier/expiry required. |
| Email | Optional Resend adapter implemented;12 mocked tests pass. Protected file outbox remains default; no message was sent. Existing credentials can be reused only after sender/domain/origin verification. See email-delivery.md. |
| AI fixture mode | Deterministic source extraction, clearly labeled, zero provider cost. Used in tests/CI; not claimed as live AI. |

## Verification and repaired findings

At this checkpoint, **70 Django/PostgreSQL tests**, **14 document tests**, and **12 browser checks** passed. Browser checks include create→generate→source review→finalize→DOCX download, responsive layouts, access exclusion and Axe accessibility. This includes12 mocked optional-email checks; no real account email was sent.

The clinical refutation pass found and repaired negation/uncertainty/family-history substring loss, repeated-label conflict omission, inherited multiline scope, revoked-user cached permission, payer drift, duplicate transcription charges, missing receipt on output-storage failure, coding acceptance stale after voice changes, and quote/rate drift. Concrete regressions cover concurrent reservation/settlement, duplicate grants, repeated jobs/payment events, cross-department/org APIs/search/files/exports/jobs, malicious uploads/prompt injection, administrator MFA and finalization immutability.

Marketing production build passed and marketing remains HTTP200. Python lockfile audit and production npm audit reported zero known vulnerabilities. Security test scope is recorded in `pentest-scope.md`; this is internal authorized testing, not independent certification. Browser accessibility observations are bounded to exercised routes, not an assertion of universal conformance.

## Old resources removed and protected

Completed exact retirement evidence: `retirement-result.json` and `obsolete-image-cleanup-result.json`.

Removed: old app/admin/CRM source;10 old application/sidecar/QA containers;3 dedicated QA volumes;40 old application tables/types;79 objects in2 dedicated old buckets;old Redis DB0 application keys after writers stopped;85 unused dedicated application images carrying104 pinned tags. Old backup scheduler stopped/disabled. Image cleanup observed30,351,110,144 bytes recovered (~28.3GiB), root disk81% used after cleanup.

Preserved: marketing and its **7 waitlist entries** with DB-internal digest comparison; shared PostgreSQL/Redis/MinIO/Caddy/nginx; useful service credentials; DNS/certificates; encrypted mounts; other VPS projects and all unrelated container/image identities. Mixed old backups and ambiguous unlabeled resources remain untouched because ownership is shared/unclear. No archive was required or created, and no global pruning ran. 38 additional dedicated sidecar/backfill/QA/deployment files and one old nightly QA cron line were then removed; exact manifests, declarations and results are recorded separately. The cron installer now contains only preserved monitoring jobs.

## External decisions and continuation

1. Provide Stripe **test** secret key and webhook signing secret through the private environment; use Stripe CLI forwarding or an explicitly authenticated staging endpoint. Exercise checkout, payment/refund events and reconciliation before allowing live payments.
2. Provide a properly licensed CPT dataset/feed with distribution entitlement, license ID and expiry. No subscription purchase is authorized by implementation alone.
3. Choose/license an evaluated Word/PDF SDK for advanced arbitrary customer forms. Assess original-format fidelity on authorized synthetic examples before promising support. See document-sdk-evaluation.md.
4. Confirm the billable-cost definition against provider account invoices/discounts/promotional credits, tax/refund policy and payment disclosures. Published token/audio rates are configured and versioned; account invoice reconciliation is not yet established.
5. Verify patient-data agreements, provider processing terms/regions/retention, access recovery, backup/restore and operational controls. **SYNTHETIC_ONLY remains hard-gated.** Do not add real patient data on the basis of passing tests.
6. Before public promotion: HTTPS routing for the two hostnames, secure-cookie deployment, external email delivery, credential rotation/recovery, suitable monitoring and independent authorized penetration testing. Do not expose private ports or reuse marketing's datastore as the new application datastore.

Useful commands: `rebuild/README.md` for local tests; `scripts/check-cotenants.sh` for declared public statuses; `scripts/check-citation.sh <fullsha>` for actual CI citation. The three fresh systemd units in `rebuild/deploy` provide supervised private processes after activation. Database data and private originals/exports must be preserved across fresh-app code updates; the owner's deletion authorization concerned the verified old system.
