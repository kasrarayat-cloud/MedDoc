# QuillMD — Full-App Deep Audit

**Run:** 2026-07-24 · master audit → triaged report → safe surgery
**Scope:** `apps/transcribe-md` (live app) + `apps/marketing` + `packages/*` + worker + infra
**Out of scope:** `apps/meddoc-pro` (decommissioned CRM), co-tenants (LeatherERP, voiceassist*, openclaw)
**Preflight gate:** 🟢 GO — `docs/preflight-reports/preflight-20260724T180527Z.md`

---

## Executive summary

| | count |
|---|---|
| **Findings raised** | **98** (88 sub-agent + 10 lead-verified) |
| Effective **P0** | **0** (one P0 was raised and downgraded to P1 on adversarial verification) |
| Effective **P1** | **19** |
| Effective **P2** | **46** |
| Effective **P3** | **23** |
| **Fixed this run** | **2 PRs open, 0 merged** — see *Why nothing merged* below |
| **Held for Kasra** | **20** (product decisions, frozen-adjacent, needs root, or debatable) |
| **Known-open reconfirmed** | **9** (not re-litigated) |
| Frozen-surface findings (report-only) | 3 |

### The six things that actually matter

1. **The GitHub repo is PUBLIC.** `kasrarayat-cloud/MedDoc` → `"visibility":"PUBLIC"`. Anonymous, unauthenticated fetches succeed *right now*:
   `WM IOV Template.docx` → **200, 52 884 B** (your pilot customer's proprietary venous-duplex form, including `INTERPRETING PHYSICIAN: Maged S. Mikhail, MD, RPVI, RVT`), `docker-compose.yml` → **200, 33 295 B**, `Caddyfile` → **200, 11 581 B**.
   **No patient PHI and no credentials** — every form field is the Word placeholder `Choose an item.`, `.env` is not tracked (only `.env.example`), and TruffleHog gates verified secrets. So this is a **customer-asset + provider-identity + infrastructure-topology** exposure, not a PHI breach. It also *compounds* item 2: the public `Caddyfile` tells anyone exactly where the unauthenticated `/_preview/` endpoint is. **[W4-hygiene]**

2. **`app.quillmd.com/_preview/` is a live, unauthenticated public directory listing** on the production clinical host — 138 screenshots of every authenticated screen including all six SUPER_ADMIN dashboards, plus bulk ZIPs. **No PHI** (verified: captured against the QA stack with synthetic seed data), but it is free reconnaissance on the admin surface and the Caddyfile comment already calls it temporary. One-line removal — held only because the design-review window it serves opened *today*. **[LEAD-7]**

3. **Every per-IP rate limit collapses to one constant IP.** Caddy `header_up X-Forwarded-For {remote_host}` *overwrites* the chain nginx preserved, so `clientIpFromHeaders` returns the proxy for everyone. Prod proof: `SELECT "ipAddress", count(*) FROM audit_logs` over 45 days returns **one row — `172.19.0.1`, 2 300 rows**. Login is therefore capped at 10/hour *platform-wide*, and `audit_logs.ipAddress` cannot attribute any PHI access. **[W1-authz]**

4. **PHI leaves the building unaudited.** Full-account export, per-patient export ZIP (both include raw audio + signed PDFs), and the three "Copy" buttons all move PHI with **zero audit rows**. Separately, `ACCOUNT_DELETED` can never be written (FK violation, swallowed) and "Delete my account" is **deterministically broken** — `audit_logs.practiceId` is `ON DELETE RESTRICT`. And the **PHI-export volume-spike detector has been dead in prod since 2026-04-26** — `action LIKE 'EXPORT_%'` on a Postgres enum throws 42883 (**965 occurrences** in 81 days of prod DB logs) and is swallowed by `.catch(() => [])`, so `/admin/security` renders "no threats" instead of an error. **[W3-audit, W3-data]**

5. **The audit harness was the least trustworthy thing in the repo.** Its 2026-07-24 sweep reported **30/30 walkers OK while emitting 14 Postgres errors**; its DB probes read **production** unconditionally; its app target defaulted to **production**; and its fixture file goes stale silently. All fixed and verified this run (PR #394). **[LEAD-1/2/6]**

6. **The "React-19 save-button quirk" was a misdiagnosis.** The button fires, React's handler runs, the server action runs. On mobile the button is simply **covered** by the fixed bottom nav (`z-index: 40` over a `sticky` bar with none) — only the top 8 px of a 66 px CTA was exposed, so **a doctor could not save their note format on a phone at all**. Fixed and verified (PR #395). **[LEAD-5/8]**

**Dated deadline:** TLS renewal is scheduled and healthy, but `/etc/letsencrypt/renewal-hooks/deploy/` is **empty** and `certbot.service` has no `--deploy-hook`, so nginx (a host service holding the cert in memory since Jul 22) will never pick up a renewed cert. The current cert expires **2026-09-01T15:14:44Z**. This becomes a P0 outage on that date. Needs root — I have no sudo. **[W4-infra]**

### Why nothing merged

`npm audit (high+critical gate)` **fails on `main` today**, independent of this run: a newly-published advisory puts `postcss ≤8.5.17` (GHSA-r28c-9q8g-f849) at HIGH, and all 5 highs trace to it through `next`. PR #394 touches only test tooling and still fails the gate, which proves it is pre-existing.

I attempted the fix (override `next.postcss` → `^8.5.23`; it worked) and **reverted it**, because the same re-resolve deleted the entire `sharp` subtree. Root cause now precisely characterised: `overrides.sharp = ^0.35.0` **cannot satisfy** `next.optionalDependencies.sharp = ^0.34.5` — disjoint ranges, and because sharp is *optional* npm drops it silently instead of erroring. Trading a postcss HIGH against losing Next's native image library is a judgement call, not a mechanical fix.

Per the standing rule (*gate overrides require an immediate debt-payment task*) I did **not** override the gate and did **not** merge. Both PRs sit green on the other checks. Working tree restored and verified byte-identical to `main`. **[LEAD-10]**

---

## Method & coverage

Four waves, ≤3 concurrent sub-agents throughout, with a resource pre-flight before each wave (the box has OOMed historically; it never dropped below 20 Gi available).

Every sub-agent finding at P0/P1 went through an **adversarial verification pass** whose instruction was to *refute*. That pass earned its keep:

- It **downgraded the sole P0 → P1** with reasoning (availability + attribution defect, not tenant crossover / PHI disclosure / auth bypass; the limiter fails *closed*).
- It **caught a fabricated citation**: a finding cited "all 7 specs in `tests/automated/e2e/*.spec.ts`" — that directory contains no Playwright specs at all. The conclusion survived on other evidence; the citation did not.
- It **refuted a central claim outright**: the "sign-out silently fails" finding missed a redundant revoke in the next-auth `events.signOut` handler that also logs and writes a LOGOUT row. Downgraded P1 → P3.
- Net: 8 P0/P1 findings verified, **all survived**, 6 downgraded.

### What was checked and came back CLEAN (real results)

- **Cross-tenant isolation — verified empirically, not by reading code.** I created a second practice + doctor + patient + visit on the QA stack with a secret marker in the note, then probed from the *first* tenant's authenticated session: `/api/visits/<other>/export/docx`, `/export/pdf`, `/progress`, `/em-score`, `/patients/<other>` → all **404, zero marker leakage**. `/visits/<other>` returns a soft-404 page ("This visit doesn't exist or you don't have access to it") — content correct. Test tenant removed afterwards; QA back to baseline.
- **Full clinical lifecycle end-to-end on QA**: created a real text visit → pipeline ran `QUEUED → DRAFTING → CRITIQUING → POLISHING → AUTOMATING → READY` → review → sign → export. Audit trail complete and correct: `VISIT_CREATED → VIEWED_VISIT ×n → VISIT_SIGNED → EXPORT_PDF_DOWNLOADED`.
- **Rx critical gate fires**: on the `criticalRx` fixture, *Sign & Send* is `disabled` with a "Resolve the critical interaction to sign →" CTA.
- **Export surfaces**: 8 combinations (4 visits × docx/pdf) all HTTP 200 with correct content types, sizes and filenames.
- **Mobile 390 px**: zero horizontal overflow on dashboard and the visit-review page; only the intentional 1×1 skip-link is a sub-44 px tap target.
- **Console**: clean across every page walked — the only recurring error is a missing `/favicon.ico` (P3).
- **30/30 walkers** pass after the fixture repair (the run began with the fixtures stale — see LEAD-1).
- **BullMQ**: prod queue depths all zero; no stuck ACTIVE jobs, no DLQ accumulation.
- **Migrations**: no failed or rolled-back rows on prod. Exactly one migration pending (see below).
- **Prod containers**: 9/9 healthy, zero restarts, no OOM in 24 h.

---

## Findings

Severity shown is the **effective** severity after verification; `⤶` marks a downgrade from what the finding agent originally claimed.

Sources: **W1** = Wave 1 (code & routes), **W3** = Wave 3 (pipeline & data), **W4** = Wave 4 (infra & hygiene), **LEAD** = lead-agent direct.

| # | Sev | Src | Area | Finding | Location | Frz | Mech |
|---|-----|-----|------|---------|----------|-----|------|
| 1 | P1 ⤶P0 | W1 | rate-limiting / ingress | Every per-IP rate-limit bucket collapses to one constant proxy IP — login/signup/password-reset are globally cap | `Caddyfile:103 (app.quillmd.com block) + ~/lib/rate-limit…` |  |  |
| 2 | P1 | W3 | admin-security-detectors | PHI-export volume-spike detector (Detector 4) has been dead in production since 2026-04-26 — `action LIKE 'EXPOR | `~/app/admin/_lib/dashboard-data.ts:608 and :905` |  | y |
| 3 | P1 | W3 | dev tooling / prod data  | Eval/regression scripts load the production .env and write to the production database, bypassing the fail-closed | `apps/transcribe-md/scripts/keyterm-regression/_boot.ts:9…` |  |  |
| 4 | P1 | W3 | audit-coverage / PHI exp | Full-account PHI export (every visit + audio bytes + signed PDFs) writes zero audit rows | `~/app/api/settings/export-data/route.ts:53-241` |  |  |
| 5 | P1 | W3 | audit-coverage / PHI exp | Per-patient PHI export ZIP (patient.json + all visits + raw audio + signed PDFs) writes zero audit rows | `~/app/api/patients/[id]/export/route.ts:42-223` |  |  |
| 6 | P1 | W3 | audit-coverage / PHI exp | "Copy" buttons put the whole signed note on the OS clipboard client-side, bypassing the audited clipboard export | `~/app/visits/[id]/soap/SoapBody.tsx:67` |  |  |
| 7 | P1 | W3 | audit-coverage / account | ACCOUNT_DELETED audit row can never be written — the insert always violates a foreign key and the failure is swa | `~/app/api/settings/delete-account/route.ts:164-172` |  |  |
| 8 | P1 | W3 | audit-coverage / admin a | Admin-surface requests execute the admin data layer but produce no audit row when the gate rejects — ADMIN_* log | `~/app/admin/layout.tsx:113 (emit) vs src/app/admin/threa…` |  |  |
| 9 | P1 | W3 | audit-review / threat de | PHI-export volume-spike detector is permanently dead in prod — enum `LIKE` throws 42883 and the `.catch(() => [] | `~/app/admin/_lib/dashboard-data.ts:608 and :905` |  | y |
| 10 | P1 | W3 | db-integrity/account-del | "Delete my account" is deterministically broken: audit_logs.practiceId is ON DELETE RESTRICT and is never cleare | `~/app/api/settings/delete-account/route.ts:124-144` |  |  |
| 11 | P1 | W3 | db-integrity/retention | Expired-trash purge aborts the ENTIRE nightly batch on any visit that has an Rx-warning override (FK RESTRICT),  | `~/worker/cleanup/stale-visits.ts:70-79` |  | y |
| 12 | P1 | W3 | db-integrity/clinical-re | Deleting a note template silently NULLs noteTemplateId on already-SIGNED visits (FK SET NULL) with no guard and  | `~/actions/note-template-lifecycle.ts:276-283` |  |  |
| 13 | P1 | W3 | object-storage/retention | Three separate purge paths name the T-M12 MinIO orphan sweep as their compensating control, but T-M12 is disable | `~/worker/cleanup/stale-visits.ts:87-89` |  |  |
| 14 | P1 | W4 | infra/tls | Certbot renewal has no nginx reload hook — prod TLS will serve an EXPIRED cert from 2026-09-01 | `/etc/letsencrypt/renewal-hooks/deploy/ (empty) + /usr/li…` |  |  |
| 15 | P1 | W4 | hygiene/confidentiality | Pilot customer's proprietary clinical form + named interpreting physician are published in a PUBLIC GitHub repo | `WM IOV Template.docx (tracked, commit 9b10def, on origin…` |  |  |
| 16 | P1 | W4 | dependencies / CI gate d | The required "npm audit (high+critical gate)" check is RED on main right now — 5 HIGH, all rooted in postcss 8.5 | `package.json:41 (overrides.next.postcss) + .github/workf…` |  | y |
| 17 | P1 | W4 | test coverage — GOAL 8-1 | PDF-native cert carry-forward has zero tests, and the ONE state the suite does exercise is "it threw and was swa | `~/lib/pdf-native/carry-forward.ts (no test file exists) …` |  |  |
| 18 | P1 | W4 | doc-drift / deploy-verif | Runbook's production verify matrix points at ports prod no longer owns — :9020 is now the isolated QA stack | `docs/DEPLOYMENT_RUNBOOK.md:99-105,362,569 + README.md:89…` |  | y |
| 19 | P1 | W4 | doc-drift / env config | TRANSCRIBE_MD_EVIDENCE_ANCHORS is live-ON in prod and documented in zero operational config — a deploy from the  | `~/worker/evidence-anchors-flag.ts:9 (flag) vs .env.produ…` |  | y |
| 20 | P2 ⤶P1 | W1 | worker / note generation | Template resolution failure silently reverts a custom-template doctor to system-default SOAP | `~/worker.ts:617-624` |  | y |
| 21 | P2 ⤶P1 | W1 | E/M coding / logging | Patient clinical narrative written verbatim to container logs on MDM parse failure | `~/lib/em-coding/llm-mdm.ts:491-495` |  | y |
| 22 | P2 ⤶P1 | W1 | native PDF export / cert | PDF-native "finish setup" discards the real error — doctor retries forever, operator gets nothing | `~/actions/certify-pdf-template.ts:86-88` |  | y |
| 23 | P2 | W1 | export path (native DOCX | Native-DOCX fallback to styled export records no reason — the PDF route's fix was never mirrored here | `~/app/api/visits/[id]/export/docx/route.ts:53-59, 76-88` |  | y |
| 24 | P2 | W1 | worker / watchdog observ | Stuck-visit watchdog only heartbeats when it rescues — a healthy watchdog is indistinguishable from a dead one | `~/worker.ts:1376-1387` |  | y |
| 25 | P2 | W1 | worker / L7 automation | Swallowed column-clear failure pins a failed L7 layer as "complete" on every subsequent retry | `~/worker.ts:948` |  | y |
| 26 | P2 | W1 | native PDF export / stor | MinIO outage is reported to operators as "orphaned certificate" — the watchdog misreads its own signal | `~/lib/pdf-native/store.ts:32-42` |  | y |
| 27 | P2 | W1 | worker / watchdog config | Malformed STUCK_VISIT_THRESHOLD_MS silently disables the last-resort stuck-visit watchdog | `~/worker/cleanup/stuck-visit-watchdog.ts:44-47` |  | y |
| 28 | P2 | W1 | export path (email deliv | Emailed PDF is always the styled document — a native-export doctor gets a different artifact by email than by do | `~/app/api/visits/[id]/export/email/route.ts:101` |  |  |
| 29 | P2 | W1 | auth / login UX | Infrastructure failure during sign-in is presented to the user as "Invalid email or password" | `~/actions/auth.ts:302-322` |  | y |
| 30 | P2 | W1 | native export / logging | Fill-engine error messages logged unredacted, breaking the house redactPhi rule at the one call site that skips  | `~/lib/template-twin/native-export.ts:153-159` |  | y |
| 31 | P2 ⤶P1 | W1 | stale flags / CI coverag | Required E2E gate builds the app with NEXT_PUBLIC_SKIN_BETA=false — the entire production UI has zero E2E covera | `.github/workflows/e2e.yml:73 (and docker-compose.yml:479)` |  |  |
| 32 | P2 | W1 | stale flags / PHI retent | MinIO orphan-object reaper is permanently disabled in prod — orphaned patient audio is retained indefinitely wit | `docker-compose.yml:418 (worker env) → ~/worker.ts:136,13…` |  |  |
| 33 | P2 | W1 | orphan routes | MFA enrollment/disable page is in code but absent from site-map.md and has no walker — an unaudited security sur | `~/app/settings/security/mfa/page.tsx:34 (route /settings…` |  | y |
| 34 | P2 | W1 | root litter / build hygi | .dockerignore misses ~4.7 GB of the repo root — every image build ships secrets/, .local/datasets, landing-monol | `.dockerignore (whole file) → apps/transcribe-md/Dockerfi…` |  | y |
| 35 | P2 | W1 | dead code / decommission | Root npm scripts all target the decommissioned CRM — `npm run test:all` is a no-op echo and `npm run build` buil | `package.json:9-22` |  | y |
| 36 | P2 ⤶P1 | W1 | cost / abuse control | POST /api/visits/[id]/em-score takes 50 KB of caller-supplied text and makes an uncached paid Anthropic call per | `~/app/api/visits/[id]/em-score/route.ts:47-107` |  | y |
| 37 | P2 ⤶P1 | W1 | cost / abuse control | No server action in the app has any rate limiting, and previewNoteTemplateAction issues a claude-opus-4-8 call w | `~/actions/preview-note-template.ts:64-131` |  |  |
| 38 | P2 | W1 | auth hardening | All three /api/mfa/* endpoints have no rate limit — the MFA disable route verifies a 6-digit TOTP with unlimited | `~/app/api/mfa/disable/route.ts:44-58` |  | y |
| 39 | P2 | W1 | audit / HIPAA | audit_logs.ipAddress records the reverse proxy for 100% of rows — the §164.312(b) trail cannot attribute any PHI | `~/lib/audit.ts:215-218` | Y |  |
| 40 | P2 | W1 | cost / abuse control | POST /api/visits/[id]/export/email re-renders and re-sends a full PHI-bearing PDF on every call with no rate lim | `~/app/api/visits/[id]/export/email/route.ts:35-43` |  | y |
| 41 | P2 | W3 | worker observability / B | A permanently-failed visit produces zero proactive signal in production: Sentry DSN is unset (all capture calls  | `~/worker-sentry.ts:14-31; ~/worker.ts:1608-1652; ~/app/a…` |  |  |
| 42 | P2 | W3 | worker cleanup crons / s | A visit left in QUEUED with its input already stored (enqueue failed / job dropped) is covered by NEITHER sweep  | `~/worker/cleanup/stuck-visit-watchdog.ts:54-61,80-88; ~/…` |  |  |
| 43 | P2 | W3 | audit-coverage / PHI exp | Sign-and-send email and EHR-clipboard deliveries write only a visit_deliveries row, never an audit_logs row | `~/app/api/visits/[id]/sign/route.ts:459 and :470` | Y | y |
| 44 | P2 | W3 | audit-coverage / PHI ing | Text-mode clinical input (the only input mode prod actually uses) is audited on rejection but not on success | `~/app/api/visits/[id]/text/route.ts:109-121` |  | y |
| 45 | P2 | W3 | audit-coverage / PHI rea | Patient-roster search and pagination in the live C3 skin read PHI through unaudited server actions | `~/actions/patients.ts:55 (searchPatientsAction) and :24 …` |  | y |
| 46 | P2 | W3 | audit-coverage / templat | Live note-template activation, deletion and PDF-native certification are unaudited, while the dormant Template-T | `~/actions/note-template-lifecycle.ts:197,246,276 and src…` |  |  |
| 47 | P2 | W3 | audit-integrity / multi- | LOGOUT rows are non-deterministically attributed to the 'clinic_main' sentinel practice — practice-scoped audit  | `~/lib/nextauth.ts:376` | Y | y |
| 48 | P2 | W3 | object-storage/orphans | transcribe-md-template-artifacts has no garbage collection at all — 3 of 4 prod objects are already orphans, and | `~/lib/pdf-native/store.ts:11` |  |  |
| 49 | P2 | W3 | db-performance/index | The patient-name trigram index is unusable by the app's query shape — every patient search is a full sequential  | `~/actions/patients.ts:71` |  | y |
| 50 | P2 | W3 | db-performance/index | The "Ready to sign" inbox has no supporting index: the plan bitmap-scans the GLOBAL status index across every te | `~/components/dashboard/dashboard-c3.tsx:80-99` |  | y |
| 51 | P2 | W3 | db-performance/index | Patients list orders by updatedAt but no index carries it — every page load and every cursor page top-N sorts th | `~/app/patients/page.tsx:71-95` |  | y |
| 52 | P2 | W3 | soft-delete-consistency | The export/clipboard/email loader is the only visit read path with no deletedAt/archivedAt gate — a trashed visi | `~/lib/visit-export-server.ts:43-68` |  | y |
| 53 | P2 | W4 | infra/backups | Backups work, but two of the three obvious verification paths are dead and silently lie about it | `root crontab line 6 + /var/log/meddoc-backup.log + backu…` |  |  |
| 54 | P2 | W4 | infra/logging | Four prod containers have no log-size cap and there is no daemon-level default to catch them | `docker-compose.yml:17 (postgres), :137 (redis), :183 (mi…` |  | y |
| 55 | P2 | W4 | hygiene/repo | 226 untracked+unignored entries at repo root on a PUBLIC repo; .gitignore has no screenshot pattern | ` (repo root) + .gitignore` |  | y |
| 56 | P2 | W4 | test coverage — form-onl | The PDF half of form-only export is a %PDF-magic-bytes smoke test — the entire chrome-strip the feature exists f | `apps/transcribe-md/tests/worker/generators.test.ts:350-356` |  | y |
| 57 | P2 | W4 | CI | The required status check named "test" runs zero tests and cannot go red on code | `.github/workflows/test.yml:98-99 + apps/meddoc-pro/packa…` |  | y |
| 58 | P2 | W4 | CI / test integrity | The required axe-core gate fails OPEN: a seeding error silently converts 8 of its 24 tests into skips and the wo | `apps/transcribe-md/tests/e2e/a11y.spec.ts:265-270 and :2…` |  | y |
| 59 | P2 | W4 | test coverage / a11y fix | The a11y route labelled "visit-detail-signed" never renders a signed visit — the fixture writes status 'READY' | `apps/transcribe-md/tests/e2e/helpers/seedVisitStates.ts:…` |  | y |
| 60 | P2 | W4 | test coverage — GOAL 8-1 | Four of the eight pdf-native modules, the certify server action, and the PDF export route have no tests — includ | `~/lib/pdf-native/export.ts, certify.ts, store.ts; ~/acti…` |  |  |
| 61 | P2 | W4 | doc-drift / QA coverage | site-map.md claims to be the COMPLETE route inventory but omits /settings/security/mfa — a security-critical sur | `.claude/agents/qa-interaction-auditor/skills/site-map.md…` |  |  |
| 62 | P2 | W4 | doc-drift / public claim | Placeholder pricing tiers the code says must not be published are publicly live and contradict the homepage's fl | `apps/marketing/src/app/pricing/pricing-tiers.tsx:19-66 (…` |  |  |
| 63 | P2 | W4 | doc-drift / ops runbook | The daily-monitoring handoff gives a HIPAA baseline that no longer matches prod, so the routine produces a perma | `KASRA_HANDOFF.md:9,11,73,82` |  |  |
| 64 | P2 | W4 | maintainability / false- | Every root npm script (lint, build, test:unit, test:e2e, test:all) targets the decommissioned meddoc-pro CRM, so | `package.json:10-24` |  | y |
| 65 | P2 | W4 | doc-drift / env config | Documented browser-side Sentry DSNs can never reach the client bundle — no Dockerfile ARG and no compose build.a | `.env.production.example:275-287 vs apps/transcribe-md/Do…` |  | y |
| 66 | P3 ⤶P1 | W1 | auth / session revocatio | "Sign out" and "Sign out all devices" report success when the DB session revoke fails | `~/actions/session.ts:14-17, 29` |  | y |
| 67 | P3 | W1 | dead code / unreferenced | Seven unreferenced components left over from the Phase-5→C3 redesign | `~/components/ (7 files, 644 LOC)` |  | y |
| 68 | P3 | W1 | dead code / orphan modul | Three lib modules (250 LOC) have zero importers anywhere in the repo | `~/lib/clinician-specialty-color.ts, src/lib/template-twi…` |  | y |
| 69 | P3 | W1 | stale flags / dead branc | NEXT_PUBLIC_SKIN_BETA OFF branch (~1971 LOC of pre-C3 UI) has not run in production since 2026-06-15 | `~/config/skin-beta.ts:21 and its 13 call sites` |  |  |
| 70 | P3 | W1 | orphan routes | Seven API routes have no caller anywhere in the repo | `~/app/api/admin/* and src/app/api/visits/[id]/progress/r…` |  |  |
| 71 | P3 | W1 | stub packages | packages/types is dead for all in-scope code and its export map points at a file deleted 3 commits into the repo | `packages/types/package.json:10 and packages/types/src/` |  | y |
| 72 | P3 | W1 | unused exports | Seven exported functions/constants in src/lib have zero references, including their own file | `~/lib/ (7 symbols across 6 files)` |  | y |
| 73 | P3 | W1 | root litter | Repo root holds 157 untracked screenshots, 12 tracked one-off smoke scripts, 5 untracked infra backups and 2 tra | `/opt/meddoc-pro (repo root)` |  |  |
| 74 | P3 | W1 | information disclosure | Unauthenticated /api/health echoes raw dependency error strings and the build version to any internet caller | `~/app/api/health/route.ts:77,95,115` |  | y |
| 75 | P3 | W3 | ingress / TLS | Caddy retries Let's Encrypt (staging CA) certificate renewal for all 5 quillmd.com hostnames every ~6 hours and  | `prod container meddoc-pro-caddy-1 (ACME renewal loop); C…` |  |  |
| 76 | P3 | W3 | worker cleanup crons — d | stuck-visit-watchdog's header comments are factually wrong about both the job timeout and its QUEUED coverage —  | `~/worker/cleanup/stuck-visit-watchdog.ts:15-27,38-41 vs …` |  | y |
| 77 | P3 | W3 | audit-coverage / MFA | No MFA lifecycle event has ever been recorded on prod, including for the one account that is MFA-enrolled | `~/app/api/mfa/verify-enrollment/route.ts:126-138` |  |  |
| 78 | P3 | W3 | audit-coverage / dead en | 41 of 116 prod AuditAction values have ever been written; several are unreachable logging paths rather than mere | `packages/db/prisma/schema.prisma:59-370 (AuditAction) vs…` |  |  |
| 79 | P3 | W3 | soft-delete-consistency | Dashboard "Signed this week" counts trashed visits — the only stat in either dashboard missing deletedAt: null | `~/components/dashboard/dashboard-c3.tsx:106` |  | y |
| 80 | P3 | W3 | db-observability | Prod Postgres has no pg_stat_statements — there is no query-level observability going into the pilot | `docker-compose.yml (postgres service config)` |  |  |
| 81 | P3 | W4 | infra/disk | ~32.8GB safely reclaimable without touching a single image (so every pre-* rollback tag and co-tenant image is p | `host /dev/sda2 + docker storage` |  |  |
| 82 | P3 | W4 | infra/host | A co-tenant service is crash-looping every ~5s and is the dominant consumer of the shared /var/log budget | `/var/log/syslog on host crimson-mink-43222 (co-tenant op…` |  |  |
| 83 | P3 | W4 | dependencies / supply ch | The production image ships @auth/core 0.41.2 (HIGH, CVSS 7.5) next to the patched 0.41.3; no import path reaches | `package.json:5-8 (workspaces) — vulnerable copy observed…` |  |  |
| 84 | P3 | W4 | doc-drift | README architecture section carries six independently-false statements about the live stack | `README.md:19,22,24,34-35,48,61,96-104,140-146` |  | y |
| 85 | P3 | W4 | stale TODO — safe to clo | Schema TODO claims the AccountDeletion purge sweeper is unimplemented, but it shipped in T-M18.2 — the comment i | `packages/db/prisma/schema.prisma:790-796 (added 2026-04-…` |  | y |
| 86 | P3 | W4 | stale TODO — safe to clo | rate-limit TODO(later) waits on a convergence signal that can never arrive — meddoc-pro is decommissioned | `~/lib/rate-limit.ts:22-24 (added 2026-04-20, >3 months)` |  | y |
| 87 | P3 | W4 | deferred control — conve | Per-practice audio retention override is documented in the schema but never honored by the sweep — currently ben | `~/worker/cleanup/retention-sweep.ts:21-28 (added 2026-04…` |  |  |
| 88 | P3 | W4 | doc-drift / env config | Six operational env vars are read by production code and documented in no config template or runbook | `.env.production.example (absent) vs ~/worker.ts:180-183,…` |  | y |


---

## Surgery plan

### (A) Fixed this run

| PR | Title | Status |
|----|-------|--------|
| [#394](https://github.com/kasrarayat-cloud/MedDoc/pull/394) | `fix(qa-harness): stop the audit harness reporting false green` | open · **5/6 green**, only `npm audit` red (pre-existing on main) |
| [#395](https://github.com/kasrarayat-cloud/MedDoc/pull/395) | `fix(settings): the note-format Save button is unclickable on mobile` | open · **4/6 green + E2E running**, only `npm audit` red (pre-existing) |

**PR #394 — QA harness integrity** (LEAD-1, LEAD-2, LEAD-6). Test tooling only; no product code.
- DB probes no longer hardcode the prod container/database; they resolve from `QA_AUDITOR_DB_*`, default to the isolated QA stack, and refuse `meddoc` without explicit opt-in.
- App target default inverted from `https://app.quillmd.com` to `http://localhost:9020`; a prod hostname now throws (mirrors `db-guard.ts`'s fail-closed discipline, which the walker fleet had never inherited).
- SQL is passed as a properly escaped argument — the old double-quoted shell string was **eating the quotes around camelCase identifiers**, which is why psql answered `column "updatedat" does not exist`. The doubled `LIMIT 5 LIMIT 1` syntax error is fixed too.
- Probe failures are recorded, emitted as `db-probe-error`, and **fail the walker** — enforced in the single `emit()` choke point so future walkers inherit it automatically.
- Stale fixtures fail closed: the fixture id is verified against the target DB before use.
- **Verified:** healthy run → `ok=true`, 0 probe errors (was 2 swallowed); broken DB → `ok=false`, 20 errors surfaced; prod app URL → refuses; prod DB name → refuses; explicit opt-in → honored.

**PR #395 — mobile Save button** (LEAD-5, LEAD-8). CSS + one `className` + one error-message branch.
- Sticky action bar lifted above the fixed mobile nav using the pattern `.qm-c3-rev2-signbar` already uses (same breakpoint, same `60px + env(safe-area-inset-bottom)` offset).
- Toast surfaces made click-through (controls inside toasts still clickable) — sonner's container carries no `pointer-events: none`, so a visible toast was a live hit target at `z-index: 999999999` in the same corner as the CTA.
- `friendlyValidationError` no longer tells a clinician to "review" `id`, a field they cannot see or correct.
- **Verified:** 390×844 before → `saveHittable: false`; after → `true`. Desktop unaffected. 18/18 unit tests pass, incl. 2 new.

### (B) Held for Kasra — triage menu

Numbered for the surgery session. Each is either a product decision, frozen-adjacent, or one where the "right" behaviour is genuinely debatable.

1. **Is the GitHub repo meant to be PUBLIC?** This gates several others, so it is first. Verified anonymously: the pilot customer's `WM IOV Template.docx` (with a named interpreting physician), `docker-compose.yml` and `Caddyfile` are all fetchable by anyone. No PHI, no credentials, `.env` not tracked. Decide: (a) flip the repo private — simplest, reverses everything at once; or (b) keep it public and `git rm --cached` the customer assets **plus** a history rewrite or GitHub cache purge, since `git rm` alone leaves the blob fetchable by SHA. Do **not** delete the working-tree copy of the IOV template — it is live test input for the IOV stack. Worth confirming the customer consented to publication.
2. **TLS: add the certbot deploy hook before 2026-09-01.** Renewal is scheduled and active, but `/etc/letsencrypt/renewal-hooks/deploy/` is empty and `certbot.service` has no `--deploy-hook`, so nginx keeps serving the cached cert. `/etc/letsencrypt/archive/quillmd.com/` holds exactly one generation — the renewal path has never been exercised. Fix is a 2-line root script + `certbot renew --dry-run`. **Needs root; I have no sudo.** Same gap on `staging.quillmd.com`. Becomes a P0 outage on the expiry date.
3. **Remove the public `/_preview/` directory listing from production?** One-line Caddyfile delete + drop the volume mount + `restart caddy`. Held only because the redesign capture it serves is dated *today*, so the review window may still be open. Non-PHI, but it publishes every admin dashboard's layout — and item 1 means the Caddyfile advertising the path is itself public. *Say the word and it's a 60-second change.*
4. **npm-audit gate debt (postcss vs sharp).** Pick: reconcile the sharp override with next's range · bump next · or a dated, documented allowlist. **Blocks all merges until resolved** — including PRs #394/#395.
5. **Rate-limit / client-IP restoration.** Requires BOTH a Caddy change (append instead of overwrite XFF) AND trusted-proxy resolution in `rate-limit.ts` — element 0 becomes client-controlled the moment Caddy stops overwriting it, so doing only half makes the limiter *spoofable*. Touches shared ingress (co-tenants), and the `audit_logs.ipAddress` half lands in **frozen** `audit.ts`.
6. **Eval/regression scripts write to the PRODUCTION database.** `scripts/keyterm-regression/_boot.ts` hard-loads `/opt/meddoc-pro/.env`; six scripts skip `@meddoc/db/guard`. Prod Postgres logs show **199 FK-violating INSERTs** into `ai_calls`/`api_usage_events`, one synthetic practice (`iov_smoke_practice`) that *was* created and later failed to delete, and ~200 `canceling authentication due to timeout` on the same dates (prod connection exhaustion). The FK constraint is the only thing that stopped most of these writes.
7. **Two active catch-all templates → non-deterministic note generation.** You have *both* "Operative Note" and "Primary Care Chronic Disease Follow-up" active with `encounterType = NULL`. `selectTemplate` uses a bare `.find()` over a `findMany` with **no `orderBy`**, so which template writes your note depends on Postgres row order — and can flip when you edit either one. Determinism is mechanical; *which* should win is your call (most-recent? explicit default? forbid two catch-alls?).
8. **"Delete my account" is deterministically broken** (`audit_logs.practiceId` is `ON DELETE RESTRICT`, never cleared before `tx.practice.delete()`), and the `ACCOUNT_DELETED` audit row can never be written for the same reason. The FK is *correct* — audit logs must outlive the user — so the bug is the hard-delete. Needs a decision on practice retention/anonymisation.
9. **Unaudited PHI egress**: full-account export, per-patient export ZIP (both include raw audio + signed PDFs), and the three client-side "Copy" buttons. Decide what to log and whether clipboard copies should round-trip through the audited route.
10. **PHI-export volume-spike detector dead since 2026-04-26** — `action LIKE 'EXPORT_%'` on a Postgres enum throws 42883 (965 occurrences in 81 days), swallowed by `.catch(() => [])`. The one-character fix (`action::text LIKE`) is mechanical; the decision is whether detector failures should ever fail open silently.
11. **Note-template deletion silently NULLs `noteTemplateId` on already-SIGNED visits** (FK `SET NULL`, no guard, no audit). **13 of 15 prod visits are already in this state** — the provenance link from a signed note to the template that produced it is gone. Refuse deletion, or soft-retire?
12. **Trash purge aborts the whole nightly batch** on any visit with an Rx-warning override (FK RESTRICT), silently retaining trashed PHI forever.
13. **The MinIO orphan sweep is cited as the compensating control by three purge paths but is disabled AND dry-run in prod.** Either enable it for real (dry-run a week, review, then arm) or stop citing it as a control.
14. **Apply the pending migration `20260722063000_template_twin_native_docx`?** Additive-only and reversible per its own header, but it is a schema change for a feature you have not activated. Prod has **zero** `template_twin_*` tables while the deployed Prisma client knows all 7 — dormant and safe today (flag-gated *before* every query, verified), but the feature cannot work if flipped and would fail *invisibly*.
15. **Deploy-process gap behind #14:** prod's `db-migrate` is profile-gated (`profiles: ["migrations"]`), so `docker compose up -d` never migrates. Code and schema can diverge silently on any deploy. Recommend surfacing drift on `/api/health` rather than auto-applying on boot.
16. **`NEXT_PUBLIC_SKIN_BETA=false` in the E2E CI build** — CI exercises the *other* skin from the one prod serves (verified empirically: the prod container serves `qm-c3-auth` from a baked constant the CI image cannot reach). Not "zero E2E coverage" — server actions, APIs, worker, auth and the gates are shared — but the C3 presentation + client-interaction layer is uncovered.
17. **Rate limiting on LLM-bearing surfaces** (`em-score`, `apply-additions`, `previewNoteTemplateAction`). Authenticated + ownership-gated, so insider abuse only, but no global spend cap exists and the Anthropic balance is shared. A naive limiter on `em-score` is a UX-regression risk (CodingRail auto-calls it on debounced edits) — needs a considered shape.
18. **Admin gate rejections are unaudited** — the admin data layer executes, then `notFound()` fires with no row. `ADMIN_*` logging has been silent since 2026-05-12.
19. **PHI written verbatim to container logs** on MDM parse failure (`llm-mdm.ts`), violating the repo's own caller-must-redact contract. Verified *not* reaching a third party (no live Sentry DSN), so it is a minimum-necessary / PHI-footprint issue rather than a disclosure.
20. **CI gates that cannot go red**: the required check named `test` runs zero tests; the axe-core gate fails *open* (a seeding error silently converts 8 of its 24 tests into skips). Both are mechanical, but "what should a green check mean" is worth one sentence from you.

**Frozen-surface findings — report-only, no fix attempted:**
- `audit.ts:215-218` — `ipAddress` records the proxy for 100 % of rows (§164.312(b) attribution). Consequence of item 2; the fix lands in frozen code.
- `audit.ts` — LOGOUT rows non-deterministically attributed to the `clinic_main` sentinel practice.
- Sign-and-send email / EHR-clipboard deliveries write a `visit_deliveries` row but no audit row.

### (C) Known-open — reconfirmed, not re-litigated

Sonographer per-visit picker · narrative-only docx · PDF AcroForm field fill · single-parse collapse · carry-forward raw-bytes limitation · template-id rotation → CTA-once workflow · Whisper fallback inactive · dormant `ai-pipeline-auditor` (activation gate unmet — **not** activated) · `hipaa-auditor` phases 2/3 dormant.

Also explicitly **not** findings: `admin.quillmd.com` → 404 unauthenticated (deliberate `adminApi()` 404-gate); prod MinIO occasionally reporting UNHEALTHY (lost `mc` alias, service fine).

---

## Production state

**Untouched.** No deploy, no migration, no restart, no config change, no data write. All prod interaction was read-only: `SELECT`s, `docker logs`, `docker inspect`, container `env`, and unauthenticated GETs to public endpoints.

- 9/9 containers healthy, 0 restarts, no OOM in 24 h
- App + worker: `T-M19.1`, up 16 h
- Schema: 67 of 68 migrations applied (one pending — item 4 above)
- Rollback tags intact; the preflight's blanket image prune was **declined** precisely to preserve them (and a co-tenant image)
- Co-tenants untouched: `pro.quillmd.com` 200, `quillmd.com` 200, `app.quillmd.com` 307, `admin.quillmd.com` 404 (expected)

**No rollback tag was cut and no deploy was run** — deliberately. Phase B's plan ended in one prod deploy, but that is only meaningful if fixes merged; with zero merges a deploy would rebuild byte-identical code and burn a rollback tag for nothing. When #394/#395 do land, cut `:pre-audit-20260724` first, then deploy.

## QA stack state

Left running and healthy on `:9020`. Fixtures re-seeded (they were stale at run start). Net additions: one signed text visit created during the lifecycle test. The cross-tenant probe fixtures were removed — practices back to 1, users 2.

## Box health

Disk 67 % (96 G free) · RAM 20 Gi available of 31 Gi · load ~1.5 · swap 1.7 G of 4 G · no OOM. Docker: 42.8 GB images (33.7 GB reclaimable — deliberately not pruned, see preflight).
