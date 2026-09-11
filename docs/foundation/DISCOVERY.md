# FOUNDATION — DISCOVERY

**Phase 0. Evidence over recall. READ-ONLY throughout — nothing in production
was modified, no schema changed, no row written or deleted.**

Run 2026-08-03 → 2026-08-04 (UTC). Twenty-eight agents across five areas, each
finding independently re-verified by a second agent that did not see the first
agent's reasoning. **Seven claims came back corrected** — six DRIFTED, one
REFUTED. Every one of those seven is recorded below *as corrected*, with the
original claim shown, because the corrections are the most useful part of this
document: they are the shape of the mistakes this area invites.

All row counts re-run by hand against production Postgres at 2026-08-04, not
carried from an agent's report.

| Table | Rows | | Table | Rows |
|---|---:|---|---|---:|
| `users` | 196 | | `audit_logs` | 10 114 |
| `practices` | 197 | | `ai_calls` | 1 097 |
| `transcribe_visits` | 26 | | `api_usage_events` | 1 288 |
| `transcribe_md_patients` | 15 | | `session_logs` | 835 |
| `note_templates` | 6 | | `billing_events` | **0** |
| `visit_deliveries` | 62 | | `patients` | **0** |
| `doctor_edit_patterns` | 16 | | `documents` | **0** |
| `rx_warning_overrides` | **0** | | `medications` / `allergies` / `appointments` | **0** |
| `account_deletions` | **0** | | `_prisma_migrations` | 84 |

---

## A. Admin census

### A.1 There are two admin surfaces and they are not peers

`apps/meddoc-pro` is a **whole second Next.js 16 application** — a clinical CRM
with 15 pages and 12 API routes, including a patient chart, a scheduler, a
document editor, voice intake, and its own `/system-admin` area. It was
formally decommissioned on 2026-05-04 (`README.md:1`,
`docs/POST_MERGE_TODO.md` §21). The container is still built, still running,
and still publicly served at **pro.quillmd.com, which returns 200**.

`apps/transcribe-md/src/app/admin/**` is the current surface: 6 pages, 29 API
routes, uniformly gated.

### A.2 The finding that outranks its framing — **ACTIONED 2026-08-04**

> ## ✅ pro.quillmd.com IS OFFLINE. The capability died 2026-08-04 01:45 UTC.
>
> Owner ruling: **the capability dies today; the code deletion stays scheduled
> last** (item A6). What was done, and what it cost:
>
> | | Before | After |
> |---|---|---|
> | `https://pro.quillmd.com/` | 200 | **410** |
> | `/login` `/register` `/dashboard` `/system-admin` | 200 | **410** |
> | `/api/health` `/api/patients` (GET **and** POST) | 200 | **410** |
> | `meddoc-pro` container | Up 5 days (healthy) | **exited (143)** |
> | app · admin · quillmd · www · staging | 307 · 404 · 200 · 200 · 200 | **unchanged** |
> | 5 co-tenant hostnames | 3 up, 3 pre-existing failures | **unchanged, same 3** |
> | 16 non-meddoc containers | running | **untouched** |
>
> **⚠️ "DISABLE ONLY ITS OWN VHOST" WAS NOT POSSIBLE — THERE IS NO PER-HOST
> VHOST.** One `sites-available/quillmd` file carries all five QuillMD
> hostnames on a single `server_name` line. And deleting the name is **not**
> the same as taking the host down: `sites-enabled/dealhunter` declares
> `server_name 5.231.107.93 _;` and, being first in the `sites-enabled/*` glob,
> is the de-facto default server for these listeners. **An unnamed
> pro.quillmd.com would have fallen through to a co-tenant.** So the change is
> an explicit `server` block that answers 410 — the hostname is *terminated*,
> not merely unlisted.
>
> `pro.quillmd.com` deliberately **stays** on the `:80` server_name: the shared
> Let's Encrypt cert covers it, so the ACME challenge path must keep answering
> or renewal breaks for **every** QuillMD hostname. Verified after the change —
> `/.well-known/acme-challenge/<probe>` returns 404 (served, token absent),
> not 301 or 410.
>
> **⚠️ AND IT FOUND A SHADOW VHOST THAT WAS BEING LOADED.**
> `sites-enabled/quillmd.bak-20260725` was a **regular file, not a symlink**,
> inside `sites-enabled/` — and nginx's include is `sites-enabled/*` with no
> extension filter, so it was parsed on every start. It declared the same five
> hostnames, producing **22 `conflicting server name … ignored` warnings**, and
> it carried the **pre-S2 `X-Forwarded-For $proxy_add_x_forwarded_for`** — the
> spoofable form that the 2026-07-25 client-IP fix replaced.
>
> It was inert *only because of glob order*: `quillmd` sorts before
> `quillmd.bak-…`, so nginx kept the first block and ignored the second. Which
> means removing `pro.quillmd.com` from the live file would have **promoted the
> shadow block's copy of it to the winner** and silently reverted the client-IP
> fix for that host. It has been moved to `/etc/nginx/vhost-backups/`. The 22
> warnings are gone; `nginx -t` now emits only the two pre-existing co-tenant
> `protocol options redefined` warnings.
>
> **CREDENTIALS: SHARED, NOT SEPARABLE.** `DATABASE_URL` is **byte-identical**
> across `meddoc-pro`, `transcribe-md` and the worker (compared by sha256, not
> by eye). And there is exactly **one** login role in Postgres — `meddoc`, and
> it is **SUPERUSER**. So there was nothing to revoke: a per-app credential does
> not exist to be withdrawn, and revoking the shared one would take production
> down. **Container-stop is the control.** Credential separation — a
> least-privilege role per app — lands in **TEAMS-phase hygiene**, and it is a
> new role plus a grant audit, not a config edit.
>
> Worth recording, because it is the real blast radius: the container took
> `env_file: - .env`, so it also held `ANTHROPIC_API_KEY`, `DEEPGRAM_API_KEY`,
> `OPENAI_API_KEY`, `RESEND_API_KEY`, `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD`,
> `MINIO_KMS_SECRET_KEY`, `AUTH_SECRET` and `SCRIBE_SERVICE_TOKEN` — the entire
> production secret set. **No rotation is being triggered by this change**, and
> that is a judgement, not an oversight: these are the same keys the live app
> uses, `.env` is mode `0600`, and nothing indicates disclosure. The finding is
> about blast radius, not about a leak.
>
> **Restore procedure** is written into the nginx block itself and into
> `docs/DEPLOYMENT_RUNBOOK.md` §3.5.

### A.2 (original finding, as measured)

The brief asked for a census. The census produced one fact that is not a
tidiness item:

> **pro.quillmd.com is a live, publicly-reachable, PHI-capable write path into
> the production clinical database, with no owner, no CI, and no audits — by
> its own README.**

- It shares **one** database with transcribe-md. Identical `DATABASE_URL` at
  `docker-compose.yml:133` (meddoc-pro) and `:625` (transcribe-md); the worker
  (`:410`) and db-migrate (`:719`) carry the same string. There is exactly one
  schema in the repo.
- It reads *and writes* clinical tables via `@meddoc/db`:
  `grep -rhoP "prisma\.\w+" apps/meddoc-pro/src | sort | uniq -c` →
  25 `prisma.user`, 11 `prisma.patient`, 9 `prisma.sessionLog`,
  7 `prisma.medication`, 7 `prisma.document`, 7 `prisma.appointment`,
  6 `prisma.allergy`, 5 `prisma.auditLog`.
- Its `/system-admin` gate is `session.user.role !== 'ADMIN' && !== 'SUPER_ADMIN'`
  → `redirect('/dashboard')`. That is an **RBAC role, not a platform
  entitlement**, and a redirect *confirms the route exists*. Contrast the
  current surface, which uses `notFound()` precisely so it does not.

**Mitigating, and stated plainly: every table it touches is empty.**
`patients`, `documents`, `medications`, `allergies`, `appointments` — all 0.
That is the whole set, counted, not a sample. So the exposure is a capability,
not a breach.

### A.3 What is load-bearing in the current surface

`/admin/queues` is the **only read path for the BullMQ dead-letter queue
anywhere in the repo.** `grep -rln "getDlqQueue|DLQ_QUEUE_NAME"` returns
exactly two non-test files: `src/lib/queue.ts` (the definition) and that page.
`worker.ts:1652` writes to the DLQ unconditionally.

Cost of losing it: the DLQ keeps filling and becomes write-only — a visit that
exhausts its three attempts fails permanently with no operator-visible record
of why, leaving `redis-cli` against a BullMQ-internal key layout as the only
recourse. It is named as the alerting path in `docs/BAA_CHECKLIST.md:183`.

Two further facts about it:

- **It has no navigation entry.** `AdminNav.client.tsx:22-26` lists five items;
  queues is not one. The one page worth calling load-bearing is the one page an
  operator cannot find.
- **Deleting it would red a required CI check.**
  `tests/e2e/scenarios/26-admin-superadmin.spec.ts:104-126` asserts it renders
  200 for a SUPER_ADMIN, in the default chromium project.

BILLING §2.4 makes this page load-bearing for *money* too — system-fault
auto-credit classifies off the DLQ.

### A.4 The current admin gate has no hole

`apps/transcribe-md/src/app/admin/layout.tsx`: SUPER_ADMIN with JWT-then-DB
fallback (`:52-63`) → `notFound()` not redirect (`:65-67`, with the comment
"so the existence of /admin isn't revealed"); MFA enrolment gate on a fresh DB
read (`:77-86`); 12-hour session-freshness ceiling; audit row on entry.

All **29** admin API routes wrap in `adminApi` — checked per-file, not
sampled. Four additionally re-check SUPER_ADMIN explicitly.

`admin.quillmd.com` is a strict path allowlist that 404s everything else
(`Caddyfile:158-246`), on the same container as the clinician app. It needs no
work in any deletion plan.

### A.5 CORRECTION — "all 15 MEDDOC_PRO users are synthetic" is wrong

> Original claim: *"No real user holds the MEDDOC_PRO entitlement. All 15 are
> synthetic, and the only recent logins are the QA harness."* → **DRIFTED.**

Every number reproduces exactly: `TRANSCRIBE_MD|183`, `MEDDOC_PRO|15`,
`SUPER_ADMIN|3`; domains `test.dev|7`, `meddoc.com|4`, `quillmd.local|3`,
`meddoc.local|1`; 12 hold `MEDDOC_PRO` and nothing else; exactly 3 have a login
inside 90 days, all `quillmd.local`, all 2026-08-03, all QA-harness-shaped.

The **characterisation** is wrong. Re-run by hand:

```
ash@meddoc.com    MEDDOC_PRO,TRANSCRIBE_MD,SUPER_ADMIN  ADMIN   logged-in  2026-04-12
kash@meddoc.com   MEDDOC_PRO                            DOCTOR  logged-in  2026-04-12
kasra@meddoc.com  MEDDOC_PRO                            DOCTOR  logged-in  2026-04-12
kas@meddoc.com    MEDDOC_PRO                            DOCTOR  logged-in  2026-04-13
```

Four accounts carrying the operator's own name, created on the first two days
of the project, all with a real login. Whether they are "real users" is an
**owner decision**, not something a domain string settles.

And the method matters more than the conclusion: inferring "synthetic" from a
`.dev`/`.local` domain is exactly the shortcut this project has already ruled
inadmissible — the launch-readiness rulings established that three files were
non-PHI **by ownership, never by their names**.

### A.6 CORRECTION — the traffic window is 23 hours, not a week

> Original claim: *"pro.quillmd.com gets real inbound traffic, but it is
> scanners and one headless QA walker."* → **DRIFTED** (conclusion holds,
> boundary was overstated).

The headline survives re-verification and was strengthened: `/system-admin` → 0
requests across **all** hosts; `/dashboard*` on pro → exactly 28, of which 26
are `?_rsc=` prefetches and 2 are bare hits from one IP at 03:02:34 and
03:02:37 on 2026-08-03, `Referer: https://pro.quillmd.com/login`; and
`SELECT max("createdAt") FROM session_logs` → `2026-08-03 03:02:36.94+00`, an
exact match to the second bare hit. The rest is scanners
(`/.env`, `/.git/config`, `/aws.env`, `//xmlrpc.php`).

**But Caddy's logs only reach back ~23 hours**, not the 168 the brief implied.
The agent said so rather than letting the window pass unstated. **A 23-hour
window is not a basis for retiring a public hostname.** Before deletion:
either a week of logs, or a 410/redirect canary on `/login` first.

### A.7 Deletion plan — DRAFTED, NOT EXECUTED

**MUST STAY.** `packages/*` (the CRM depends on them, not the reverse —
`apps/meddoc-pro/Dockerfile:14-17`); all 6 pages + 29 API routes under
`apps/transcribe-md/src/app/admin/**`; the `admin.quillmd.com` Caddy block;
`/admin/queues` and its E2E scenario.

**REWIRE FIRST, in this order.** Each of these breaks CI or a user-facing flow
if sequenced wrong:

1. Rewrite the **13 root `package.json` scripts** (`package.json:11-25`) that
   route `dev`/`build`/`start`/`lint`/`test:*`/`seed:*`/`eval:*` through
   `-w meddoc-pro`. `npm run build` at the repo root currently builds the CRM.
   ⚠️ **CORRECTED 2026-09-09 — the count is now TWELVE.** `test:all` was
   decoupled ahead of the rest because it is the only one any workflow reaches
   (`.github/workflows/test.yml`, the REQUIRED `test` job). The other twelve are
   local-only and are enumerated with their reasons in
   `gate-dmp-a-workspace-coupling.test.ts`, which reds if a thirteenth appears
   or if one of the twelve is fixed without its row being removed.
2. Delete or repoint the CI `test` job (`.github/workflows/test.yml:41-114`).
   It is **already vacuous** — it runs `npm run test:all`, which resolves to an
   `echo` in the decommissioned workspace, and `test.yml:269` says so in its own
   comment. The real unit gate is the separate `unit` job at `:285`.
   ⚠️ **CORRECTED 2026-09-09 — the vacuity STANDS, the mechanism changed.** The
   echo now lives at the repo ROOT: root `test:all` no longer delegates to the
   retired workspace. The reason it could not wait for the delete-or-repoint
   decision is that the delegation made the step exit 1 the moment
   DELETE-MEDDOC-PRO ran (`npm error No workspaces found: --workspace=meddoc-pro`,
   measured) — and `test` is a REQUIRED context, so that is not a red main, it is
   every PR unmergeable. **Deleting or repointing the job is still owed.**
3. Remove the pro.quillmd.com branch from
   `apps/transcribe-md/src/actions/auth.ts:227-241`, **and** decide the fate of
   the 12 `MEDDOC_PRO`-only accounts (SPEC §4.1). Doing the first without the
   second leaves a login error whose only remedy is a dead link.
4. Retire the nightly assertions that pro.quillmd.com returns 200 —
   `.github/workflows/nightly-tests.yml:56`,
   `tests/automated/smoke/health.sh:23-24`,
   `tests/automated/monitoring/uptime-check.sh:32`, and the 12-cell
   `tests/automated/e2e/product-separation.spec.ts`. These three files are the
   only thing currently keeping the CRM "in use".
5. (Unrelated, cheapest fix in the area) give `/admin/queues` a nav entry.

**COULD GO, once the above lands.** `apps/meddoc-pro/` (~150 files); the
compose service (`docker-compose.yml:92-150`); the `pro.quillmd.com` Caddy
block (`:249-272`); `pro.quillmd.com` from the host nginx `server_name` line;
the DNS A-record. Optionally the `MEDDOC_PRO` enum value and the orphan
accounts — **that is a migration and a separate decision.**

**Note on scope beyond the repo:** routing lives in three places, two of them
outside git — the Caddyfile, `/etc/nginx/sites-enabled/*`, and DNS.

**Note on precedent:** the 2026-05-04 decommission was a recorded decision with
a written reversal procedure. It deliberately stopped short of deletion.
Deleting is a *change to that decision* and belongs in `POST_MERGE_TODO` §21 as
one, not executed as a cleanup.

### A.8 Loose end

`Caddyfile:258-264` defends `/api/internal/*` on pro.quillmd.com with a
comment describing a scribe → meddoc-pro service-to-service integration.
`ls apps/meddoc-pro/src/app/api/` has no `internal` directory. Harmless as a
rule; misleading as documentation.

---

## B. Data-model facts

### B.1 The ownership chain, exactly

- **User → Visit**: `transcribe_visits.userId` → `users.id`, `onDelete: Cascade`
  (`schema.prisma:1682-1683`).
- **Practice → Patient**: `transcribe_md_patients.practiceId` → `practices.id`,
  `onDelete: Cascade` (`:1611-1612`).
- **Visit → Patient**: `transcribe_visits.patientId`, `onDelete: Restrict`
  (`:1689-1690`).

Two separate chains that meet only at the visit row — **and the visit row
stores neither practice.** A visit's tenant is only ever derived. There is no
column on which a fail-closed constraint could be placed.

### B.2 Fourteen tables already carry `practiceId`

`ai_calls`, `allergies`, `api_usage`, `api_usage_events`, `audit_logs`,
`billing_events`, `medications`, `patients`, `session_logs`, `tasks`,
`template_twin_fill_manifests`, `template_twin_source_artifacts`,
`transcribe_md_patients`, `users`.

`transcribe_visits` is not one of them. The already-scoped set is almost
entirely the dormant CRM half plus telemetry; **the live clinical write path is
the unscoped half.**

### B.3 The tables that would gain `practiceId`

| Table | Rows | Current owner column(s) |
|---|---:|---|
| `transcribe_visits` | 26 | `userId` + `patientId`, no practice |
| `visit_deliveries` | 62 | `visitId` only |
| `doctor_edit_patterns` | 16 | `visitId` (unique) + `doctorId` |
| `note_templates` | 6 | `doctorId`, **nullable** |
| `rx_warning_overrides` | 0 | `visitId` + `overriddenBy` (nullable) |
| `template_twin_compiled_versions` | 0 | `sourceArtifactId` + `noteTemplateId` |
| `template_twin_field_definitions` | 0 | `compiledVersionId` |
| `template_twin_semantic_mappings` | 0 | `fieldDefinitionId` |
| `template_twin_certifications` | 0 | `compiledVersionId` |
| `account_deletions` | 0 | `userId`, **no FK by design** |

Small in rows, wide in tables. **The zero-row tables are free to constrain now
— this is the cheapest window this will ever have.**

⚠ Template Twin is PARKED but its ingest code is load-bearing on every `.docx`
upload (AGENTS.md). Adding a required column there changes a live write path.

### B.4 `doctor_edit_patterns` is the highest-PHI-density unscoped table

`schema.prisma:2082-2089` — `originalSoap String @db.Text` and
`editedSoap String @db.Text`, i.e. **two full copies of the note text**, with
the comment "Frozen copy of soapL6Original at sign time. Never updated." 16
rows, no `practiceId`, tenant reachable only via `doctorId → users.practiceId`.

A practice-scoped query layer that forgets this table leaks whole notes, not
metadata.

### B.5 The backfill is unambiguous today — and only today

```sql
SELECT count(*) FROM transcribe_visits v
JOIN users u ON u.id = v."userId"
JOIN transcribe_md_patients p ON p.id = v."patientId"
WHERE u."practiceId" <> p."practiceId";   -- → 0
```

Both derivation paths give the same answer for all 26 visits. **Pick one and
write down which**, because nothing in the database keeps them agreeing: the
two FKs are independent, there is no composite FK and no CHECK. The only guard
is app-side and covers only the PATCH path
(`api/visits/[id]/route.ts:245-253` → 400 `INVALID_PATIENT`); the create path
(`actions/visits.ts:198-213`) writes `userId` and `patientId` and no practice.

### B.6 The product bug the migration exists to fix

Visit access control today is **user-equality, not practice-membership**:
`api/visits/[id]/sign/route.ts:207` — `if (!visit || visit.userId !== userId) return 404`.
Compare `lib/patients-query.ts:60/92/126`, which filter
`WHERE p."practiceId" = ${practiceId}`.

So a colleague in the same practice **can see the patient and cannot open the
visit.** Blast radius: 61 call sites match
`transcribeVisit.findMany|findFirst|findUnique` in `src` excluding tests.
Changing the ownership predicate is not a one-line change.

### B.7 Attribution is thinner than it looks

`transcribe_visits` has `signedAt` (`:1913`) and **no `signedBy`**, and no
`createdBy`/`createdById` anywhere on the table. Today "who signed" is answered
by `userId` — the *owner*, not a recorded signer.

Three records currently answer "who signed", and they disagree in coverage:

- `audit_logs` where `action = 'VISIT_SIGNED'` → **36** rows, 36 distinct
  targets, 0 with a null `userId`.
- `transcribe_visits` where `signedAt IS NOT NULL` → **16**.
- `doctor_edit_patterns` → **16**.

Of the 36 audited signings, only 16 targets still exist as visit rows. **The
audit table is the only durable signer record**; anything built on
`transcribe_visits` alone loses 20 signings of history.

### B.8 `audit_logs.practiceId` can never be fail-closed — and its values are not trustworthy

Two separate facts, both load-bearing.

**Nullable by design.** `schema.prisma:1117-1126` — *"S4c — NULLABLE + SetNull.
An audit row must outlive the practice it describes."* 6 rows are NULL and
their tenant is unrecoverable because `practiceIdSnapshot` is NULL too (all 6
are worker-emitted `EM_LEVEL_CHANGED` with no session). **This table must be
excluded by name from any "no clinical row without practiceId" rule, with the
S4c reasoning cited** — otherwise someone will "fix" it and re-break account
deletion, which is what S4c exists to prevent.

**Fail-open fallback.** `lib/audit.ts:293-294`, as it stood:

```ts
const practiceId = input.practiceId ?? sessionPracticeId ?? 'clinic_main';
```

The fallback failed *open, into the largest shared practice* — the exact
opposite of what a tenant boundary should do on unknown input. If
practice-scoped audit views had shipped as specced, 64 solo doctors' logout
events would have appeared in Main Clinic's feed.

> ### ✅ CLOSED 2026-08-04 — and the number was **64, not 65**
>
> **Self-correction, recorded rather than quietly fixed.** This section first
> said 65 misattributed rows, "64 `LOGOUT`, 1 `USER_GRANTED_SUPER_ADMIN`". The
> `USER_GRANTED_SUPER_ADMIN` row is **correct**, and the query that produced
> the 65 was wrong.
>
> That query asked `a."practiceId" <> actor."practiceId"`, i.e. it assumed an
> audit row's practice should always be the *actor's*. It should not.
> `api/admin/users/[id]/grant-admin/route.ts:82` deliberately passes
> `practiceId: user.practiceId` — the **target's** practice — because the event
> belongs to the tenant being changed, not to the admin doing the changing.
> Verified on the row itself: `practiceId = clinic_main` and
> `target_practice = clinic_main` agree.
>
> **A repair driven by the naive query would have "corrected" a correct row.**
> The lesson generalises past this row: a cross-tenant admin action has two
> defensible tenants, and a checker that knows about only one of them
> manufactures findings.
>
> **The fix**, all in one change:
> - `lib/audit.ts` — the fallback is gone. The resolution now ends in `null`,
>   the row is written `practiceId = NULL` with
>   `practiceIdSnapshot = 'UNATTRIBUTED'` (the FK column cannot hold a sentinel
>   without inventing a `Practice` row), and it is reported at **error** level,
>   because an unattributable write is a defect in the *caller*.
> - `lib/nextauth.ts` — the `signOut` event now resolves the practice **by
>   traversal** (one primary-key lookup) before writing `LOGOUT`. `auth()`
>   cannot run there; that is why the fallback was reached at all.
> - `gate-audit-attribution-failclosed` — a guard proven red against four
>   mutations, including the literal pre-fix line.
> - `AUDIT_ATTRIBUTION_CORRECTED` — a new `AuditAction`, **with its Prisma
>   migration**, because a TS-only label is discarded silently.
> - `scripts/repair-audit-attribution.ts` — read-only by default. **It never
>   updates and never deletes.** `audit_logs` is append-only, so the 64 wrong
>   rows stay wrong and a correction row is *appended* per original, pointing
>   at it via `targetId`. The six unattributable pre-S4c rows get correction
>   rows too, carrying `determinable: false` — stated, not guessed.

A further 38 rows have a `practiceId` but a NULL `practiceIdSnapshot` — they
predate migration `20260725040000_s4c_deletable_account_audit_preserving`. A
snapshot backfill is cheap, separate and non-blocking.

`api_usage_events` has **271 of 1 288** rows with a NULL `practiceId`, same
SetNull posture — a second named exclusion. (`ai_calls` has 0 of 1 097.)

### B.9 `note_templates` cannot take a blanket NOT NULL

2 of 6 rows are platform-global with `doctorId = NULL`:
`tmpl_system_default_soap` (isSystemDefault=true) and `tmpl_ultrasound_report`
(**isSystemDefault=false**). Note the second one: a global row that is *not*
the system default, which a naive "NULL doctorId ⇒ system default" rule
mis-handles.

And the uniqueness backstop is keyed on doctor:
`note_templates_one_active_per_doctor_encounter … ("doctorId","encounterType") NULLS NOT DISTINCT WHERE status='active' AND "doctorId" IS NOT NULL`.
Adding `practiceId` without touching this index leaves "one active template"
meaning per-doctor. If the intent is a shared practice format, **this index is
the thing that silently keeps it per-doctor.** (SPEC §4.3)

### B.10 The population makes vacuous tests very easy to write

197 practices, 196 users, 196 with a non-null `practiceId`. Signup mints a
synthetic 1:1 practice (`actions/auth.ts:493-501`). **Only three practices have
more than one user** — `clinic_main` (11), `qa-practice-audit` (5),
`clinic_test_b` (2). **Only two practices hold any TranscribeMD patients at
all**, both solo; `clinic_main`, with its 11 users, holds none.

So practice-scoping is currently indistinguishable from user-scoping for 193 of
196 users. **Any test that a `practiceId` filter "works" passes vacuously
unless it runs against a multi-seat practice with clinical data — and no such
practice exists anywhere in production.** This is the fixture-monoculture
failure mode this project has already hit once (the imaging-E/M bug, where an
all-primary-care fixture set is why CI could not see it).

16 practices have zero users — orphans left when QA accounts were deleted;
signup creates user+practice in one transaction, deletion removes only the
user. Harmless today (none hold clinical rows), but **"practices" is not a
usable proxy for "customers".**

### B.11 CORRECTION — "reversing a recorded decision" overstates the comment

> Original claim: *"The schema states the non-scoping as intentional design, not
> oversight — so the migration is reversing a recorded decision, not fixing a
> bug."* → **DRIFTED.**

The quote at `schema.prisma:1564-1566` is verbatim accurate and the descriptive
half holds. The operative half does not, on three counts:

1. It truncates the sentence. Lines 1566-1567 continue *"so tenant scoping still
   works if we ever reuse Practice-aware code paths"* — the note **reserves**
   the practice-aware path rather than forbidding it.
2. Its premise has lapsed. The rationale holds only *"for solo users [where] the
   Practice is a synthetic 1:1 container"*. Live: 3 multi-seat practices.
3. It is a shell-era note never revisited. `git log -L 1564,1567` returns
   exactly one commit — `6b79e9cf` (2026-04-18), *"T-M2: TranscribeMD Solo app
   skeleton"*.

So: not a decision being reversed. A conditional note whose condition expired.

### B.12 Baseline

84 migrations applied; 38 base tables; `schema.prisma` is 2 848 lines. Earliest
practice migration `20260412234252_add_multi_tenancy`; most recent overall
`20260802220000_sign_blocked_no_attestation`. No orphan risk in current data:
visits owned by soft-deleted or inactive users → 0; orphan deliveries → 0;
edit-patterns whose doctor ≠ visit owner → 0.

⚠ `pg_stat_user_tables.n_live_tup` is stale on this database (reports
`practices|3`). Every count in this document is a real `count(*)`.

---

## C. Usage-capture facts

**The billing meter can only bill what is captured.** This section is what is
captured, and what is thrown away.

### C.1 The pipeline, and where it is enumerated from

Eight ordered stages plus an E/M judge, per `worker.ts` call sites:

| Stage | File | Vendor | Notes |
|---|---|---|---|
| L1 | `01-transcribe.ts` | Deepgram | audio_upload only |
| L1b | `01b-transcribe-dictation.ts` | Deepgram | voice_dictation only |
| L2 | `02-speaker-roles.ts` | Anthropic sonnet-4-6 | audio_upload only |
| L3 | `03-extract-entities.ts` | Anthropic | |
| L4 | `04-generate-soap.ts` | Anthropic opus-4-8 | |
| **L4b** | `04b-anchor-verify.ts` | Anthropic sonnet-4-6 | **nested inside L4** |
| L5 | `05-self-critique.ts` | Anthropic opus-4-8 | |
| L6 | `06-polish.ts` | Anthropic sonnet-4-6 | |
| **L6b** | `06b-polish-fidelity-gate.ts` | Anthropic sonnet-4-6 | **nested inside L6** |
| L7a–e | `07a-icd` / `07b-cpt` / `07c-rx` / `07d-referrals` / `07e-patient-summary` | Anthropic | parallel fan-out |
| judge | `lib/em-coding/llm-mdm.ts` | Anthropic sonnet-4-6 | **bypasses `modelClient`** |

**L4b and L6b are not invoked from `worker.ts`.** A meter that enumerates
stages by scanning worker call sites misses two Anthropic-billing layers — and
`tm_anchor_entailment` (222 events) is the **highest-volume Anthropic operation
in production.**

`llm-mdm.ts` is a second, independent Anthropic integration. Any meter change
made only in `packages/ai/src/anthropic.ts` will miss it.

### C.2 There are already two persistence lanes

- `ai_calls` (`AiCall`, via `logAiCall`) — 1 097 rows.
- `api_usage_events` (`ApiUsageEvent`, via `logApiUsage`) — 1 288 rows.
- plus a per-visit `transcribe_visits.processingCostCents` rollup and a full
  pricing dispatcher at `packages/ai/src/pricing.ts`.

This is not a greenfield meter. It is a meter with two known holes.

### C.3 HOLE 1 — failed-but-billed calls never reach the durable table

`logApiUsage` has exactly two call sites (`anthropic.ts:433` and `:580`), both
immediately after a `success: true` block. The five failure branches
(`:233` AI_REFUSAL, `:264` JSON_PARSE_FAIL, `:324` AI_REFUSAL, `:349`
JSON_PARSE_FAIL, `:383` SCHEMA_FAIL) each **extract and price real usage**, write
it to `ai_calls`, and then drop it.

Re-run by hand:

```sql
SELECT count(*), sum("inputTokens"), sum("outputTokens"), sum("costUsdCents")
FROM ai_calls WHERE success = false AND "inputTokens" > 0;
--  44 | 146474 | 52231 | 153
```

**44 real, vendor-billed calls worth ~$1.53** exist in one table and not the
other — ~4% of all Anthropic calls, concentrated in `tm_entities` (18) and
`tm_rx_drafting` (13).

The same applies to Deepgram (`deepgram-batch.ts:293`, `:318`), and there it
**contradicts the module's own written contract**, `api-usage.ts:4-8`:

> *"Called from each provider wrapper AFTER the call completes — successful or
> failed (failed calls often still cost money: a Deepgram socket that ran for
> 30s before erroring is still 30s of billed audio)."*

Worse for Deepgram: the failure rows carry no `audioSeconds`, so the lost
amount is **not recoverable after the fact.**

### C.4 HOLE 2 — durability is inverted

`ai_calls` — the table that *does* hold the failed-call tokens — is
hard-deleted in three paths: `api/visits/[id]/delete/route.ts:85` and `:142`,
`worker/cleanup/stale-visits.ts:72`, `api/settings/delete-account/route.ts:188`.
`api_usage_events` is deleted nowhere. FK rules agree: `ai_calls.practiceId` is
RESTRICT; `api_usage_events` is SET NULL.

So: **choosing `ai_calls` as the billing ledger means a doctor deleting a visit
erases their own bill. Choosing `api_usage_events` means silently under-billing
every failed-but-charged call. Neither table is currently a correct billing
source on its own.**

`transcribe_visits.processingCostCents` is computed by summing the perishable
table (`worker.ts:983-991`), is reset to null on each new input, and counts all
retry attempts. Its own comment concedes the status: *"the cost number is
observability, not load-bearing for correctness."* **Do not promote it.**

### C.5 Attribution gaps

`ai_calls` has **no `userId` column** at all — per-doctor attribution is
impossible from it, even though `AiLogContext` carries one
(`types.ts:64-73`). `api_usage_events` has one, NULL on 51 of 1 067 Anthropic
rows (~5%) and on all 219 `resend` rows. `model-client.ts:151-154` records that
this class of bug already bit once.

### C.6 No vendor request-id is captured anywhere, for any vendor

**This is the biggest single gap against SPEC §2.2, which requires idempotency
on the vendor request id.**

- `grep -rn "_request_id"` across `packages/` and `apps/transcribe-md/src/` →
  **zero hits.** Anthropic's `response._request_id` is never read. The only
  `request-id` reads are on the *error* path (`anthropic.ts:108-115`), and they
  land in an `errorDetails` string, not a usage row.
- Deepgram **does** return one and the response type already declares it —
  `deepgram-batch.ts:108-115` has `request_id?: string` in
  `DeepgramBatchResponse.metadata`. Only `duration` and `detected_language` are
  read out. **This is the cheapest fix in the whole area:** the field is
  already typed and already in hand at `:342`.
- `ApiUsageEvent.requestId` is filled with a local `randomUUID()`
  (`api-usage.ts:160/179/247`) and no caller ever passes one — 1 288 of 1 288
  distinct by construction, **despite a schema comment claiming otherwise.**

Consequence: the table cannot dedupe a replayed write, cannot be reconciled
line-by-line against a vendor invoice, and cannot correlate the several usage
events produced by one user action.

### C.7 Units: what the vendor actually reports

- **Anthropic tokens** — all four fields read on every call
  (`anthropic.ts:55-62`), both cache fields coalesced to 0. Vendor-reported.
- **Deepgram audio seconds** — `raw.metadata?.duration` (`deepgram-batch.ts:342`).
  **Vendor-reported, not computed.** Good.
- **Whisper** — `response.duration` (`whisper-batch.ts:248`). Vendor-reported.

But the Deepgram usage row **hardcodes** its own provenance:
`api-usage.ts:162,168` writes `operation: 'transcribe_realtime'` and
`modelName: 'nova-3-medical'` for **every** Deepgram event — even though this
is the batch endpoint, and interpreter mode swaps the model to `nova-3`
(`01-transcribe.ts:158`, `01b:130`). The true model survives only in
`metadata->>'model'`. So provider/model attribution in `api_usage_events` is a
**literal, not an observation**, and a future price split between nova-3 and
nova-3-medical cannot be applied retroactively.

**Dictation duration is written to a different column than audio-upload
duration** — `audioDurationSec` (`01-transcribe.ts:289`) vs
`dictationDurationSec` (`01b:229`). Any billable-minutes query must
`COALESCE` both. This **cannot currently be caught in production**: all 26 prod
visits are `text_notes` (`text_notes|SIGNED|16`, `text_notes|READY|10`), 26/26
with NULL `audioDurationSec` and zero rows carrying `dictationDurationSec`.
**The entire audio billing path is unexercised in production.**

### C.8 Prompt caching is one call site

Only the E/M MDM judge sets `cache_control` (`lib/em-coding/llm-mdm.ts:394`,
`cacheControl: 'ephemeral'`), and it calls the SDK directly. Neither
`messages.create` in `anthropic.ts` sets it. Production confirms: `judge` is
the only operation with non-zero cache columns.

Cache-aware pricing exists and is correct (`api-usage.ts:57-59`, 0.10× / 1.25×),
exercised by one operation.

Latent: `completeText` returns only `{text, inputTokens, outputTokens}`
(`anthropic.ts:597-601`) — it hands cache tokens to the DB but **not to its
caller**, despite `model-client.ts:131-137` documenting the opposite intent.
Nil impact today; a silent under-count the day caching is enabled on L4/L6.

### C.9 Both writers are fire-and-forget

`logAiCall` is `void prisma.aiCall.create(...)` (`log.ts:33-34`); `logApiUsage`
defers into `setImmediate` and swallows failures to `console.warn`
(`api-usage.ts:105-136`), per its own stated design. **Defensible for
observability, wrong for a billing meter** — a Postgres blip silently loses
revenue with a console warning.

Recorded honestly: the agent flagged a possible read-after-write race at
`worker.ts:983` (the cost sum reads `ai_calls` in the same tick-chain that
wrote it) and **said it did not prove it either way and did not attempt to
reproduce it.** It stays UNSURE.

### C.10 CORRECTION — "nothing on the Anthropic token surface is dropped"

> Original claim: *"Anthropic usage is read in FULL — all four token fields …
> Nothing on the Anthropic token surface is dropped at extraction time."*
> → **DRIFTED.**

The cited code is verbatim correct. The generalisation is not. In the pinned
SDK (`@anthropic-ai/sdk@0.85.0`), `Usage` declares **eight** fields, not four.
Four are dropped, two of them billing-bearing:

- `cache_creation: CacheCreation | null` — the `{ephemeral_1h, ephemeral_5m}`
  TTL breakdown that distinguishes the **1.25× and 2× cache-write classes**.
- `server_tool_use: ServerToolUsage | null` — `web_fetch_requests` /
  `web_search_requests`, **billed per request**.
- plus `inference_geo` and `service_tier`, the latter billing-relevant.

Current impact is **nil, checked not assumed** — the only `cache_control` in
the tree is the single judge call site. But SPEC §2.2 says *vendor-reported
units*, and a 1-hour cache write is priced at 2× while a 5-minute one is 1.25×.
**Collapsing both into one `cacheCreationInputTokens` integer is an
under-charge that turns on the day someone sets a 1h TTL.**

### C.11 CORRECTION — the env-override count

> Original claim: *"6 of 12 layers read an env override."* → **DRIFTED.**

It is **seven**: `03:28`, `04:46`, `04b:45`, `05:31`, `06:31`, `06b:54`,
`07c:32`, all reading `TRANSCRIBE_MD_CLINICAL_MODEL`. The claim said six while
its own evidence list enumerated all seven. Denominator 12 is correct. (Files
live at `apps/transcribe-md/src/worker/layers/`.)

The operative point stands and matters: **one env var silently repoints seven
layers, including both Opus ones.** The rate must come from the `modelName`
recorded on the row at call time — which `buildAnthropicUsage(..., modelName, ...)`
already does correctly.

---

## D. Vendor price verification

Fetched **2026-08-04** from the vendors' own pages. These are the **price-table
seed**. Every row carries its URL and the date it was read, because a rate card
without a date is a guess with a decimal point.

### D.1 Anthropic — https://platform.claude.com/docs/en/docs/about-claude/pricing (read 2026-08-04)

| Model | Input /MTok | 5m cache write | 1h cache write | Cache read | Output /MTok |
|---|---|---|---|---|---|
| Claude Opus 5 | $5 | $6.25 | $10 | $0.50 | $25 |
| **Claude Opus 4.8** | **$5** | $6.25 | $10 | $0.50 | **$25** |
| Claude Opus 4.7 | $5 | $6.25 | $10 | $0.50 | $25 |
| Claude Sonnet 5 (**through 2026-08-31**) | $2 | $2.50 | $4 | $0.20 | $10 |
| Claude Sonnet 5 (from 2026-09-01) | $3 | $3.75 | $6 | $0.30 | $15 |
| **Claude Sonnet 4.6** | **$3** | $3.75 | $6 | $0.30 | **$15** |
| Claude Haiku 4.5 | $1 | $1.25 | $2 | $0.10 | $5 |

Multipliers, stated by the vendor: **5-minute cache write 1.25×, 1-hour cache
write 2×, cache read 0.1×**, and they stack with batch and data-residency
modifiers. Batch API is a flat **50% discount**. `inference_geo: "us"` is a
**1.1×** multiplier on *all* categories for 4.6-and-later models.

**Verdict against the code:** `packages/ai/src/pricing.ts` opus $5/$25 and
sonnet $3/$15 and haiku $1/$5 — **all correct as of today.**

**Two gaps, both against SPEC §2.2:**

- The code models cache writes with a **single 1.25× multiplier**
  (`pricing.ts:claudeCostCents`). The vendor has **two** write classes, 1.25×
  and 2×. Correct today only because the one caching call site uses ephemeral
  5m. See §C.10.
- **Sonnet 5's introductory rate expires 2026-08-31** ($2/$10 → $3/$15). If
  anything is ever repointed at Sonnet 5 via `TRANSCRIBE_MD_CLINICAL_MODEL`,
  the price table must be *versioned by date*, not by model name. This is a
  live example of exactly why SPEC §2.2 requires a versioned snapshot.

### D.2 Deepgram — https://deepgram.com/pricing (read 2026-08-04)

| Model | PAYG streaming | PAYG pre-recorded | Growth streaming | Growth pre-recorded |
|---|---|---|---|---|
| Flux English | $0.0065/min | $0.0077/min | $0.0057 | $0.0065 |
| Flux Multilingual | $0.0078/min | — | $0.0068 | — |
| **Nova-3 Monolingual** | $0.0048/min | **$0.0077/min** | $0.0042 | $0.0065 |
| Nova-3 Multilingual | $0.0058/min | $0.0092/min | $0.0050 | $0.0078 |

**⚠ `nova-3-medical` does not appear on Deepgram's pricing page at all.** That
is the model this system sends by default (`deepgram-batch.ts:23`,
`DEFAULT_BATCH_MODEL = 'nova-3-medical'`).

The only price Deepgram publishes for it is in the launch announcement,
https://deepgram.com/learn/introducing-nova-3-medical-speech-to-text-api
(read 2026-08-04): **"$0.0043 per minute of pre-recorded audio"** — pre-recorded
only, and the page shows "Updated" with **no date**.

**Verdict against the code: our rate is wrong, and the record shows we picked
the wrong side of a known disagreement.**

`api-usage.ts:36-43` records that the two surfaces once disagreed — *"Previously
this duplicated the value and disagreed with pricing.ts ($0.0043 vs $0.0145)"* —
and resolved it by unifying **on $0.0145**. The discarded number, $0.0043, is
the one Deepgram publishes. At **$0.0145/min the default is ~3.4× the vendor's
stated rate.** With `charge = cost × 1.5`, that error propagates straight into
what a doctor is billed.

Impact today is zero (all 26 prod visits are `text_notes`; §C.7) — which is
exactly why nobody caught it, and exactly why it must be fixed **before** audio
billing turns on rather than after.

Second-order: since the code *also* mislabels the model on interpreter-mode
calls (§C.7), a corrected table needs **three** rates —
`nova-3-medical` pre-recorded, `nova-3` pre-recorded, `nova-3` streaming — and
the row must record which one actually ran.

### D.3 OpenAI — https://developers.openai.com/api/docs/pricing (read 2026-08-04)

| Item | Price |
|---|---|
| `whisper` | **$0.006 / minute** |
| `gpt-transcribe` | $0.0045 / minute |
| `gpt-4o-transcribe` | $0.006 / minute |
| `text-embedding-3-small` | **$0.02 / 1M tokens** |
| `gpt-5.6-sol` | $5.00 in / $30.00 out per 1M |
| `gpt-5.6-terra` | $2.00 in / $12.00 out per 1M |
| `gpt-5.6-luna` | $0.20 in / $1.20 out per 1M |

**Verdict against the code:** `PRICING.whisper = 0.006` — correct.
`DEFAULT_OPENAI_EMBED_SMALL_CENTS_PER_M = 2` (= $0.02/M) — correct.

⚠️ **CORRECTION, 2026-08-10 (B3) — THAT VERDICT CHECKED ONE OF TWO SURFACES,
AND THE OTHER ONE IS WRONG BY 6.5×.** The embedding rate lives in two places and
they disagree:

| surface | rate | |
|---|---|---|
| `pricing.ts:170` `DEFAULT_OPENAI_EMBED_SMALL_CENTS_PER_M = 2` | **$0.02 / 1M** | correct, and the one this section checked |
| `api-usage.ts:66` `openai_embedding: 0.13` | **$0.13 / 1M** | **unsourced — matches no figure OpenAI publishes** |

`api-usage.ts:369-370` uses its own constant, so an `api_usage_events` embed row
would be priced at 6.5× the published rate — **and ruling 78(b) makes
`api_usage_events` the billing source**, so the durable side is the wrong side.

**This is the same shape as the Deepgram finding three paragraphs above**
(§D.2: two surfaces disagreed, `$0.0043` vs `$0.0145`, and the code unified on
the wrong one). The reason it was missed here is that a verdict was written
against the constant somebody happened to look at, and *"correct"* is a claim
about a rate, not about a file.

**Impact today is exactly zero, and the reason is itself a finding:** the embed
usage builder has **no caller** — `logEmbedUsage` / `operation: 'embed'` appears
only at its own definition. Measured on production: **0** rows in
`api_usage_events` with `operation='embed'`, against **37**
`text-embedding-3-small` rows in `ai_calls`. So embeds are metered in the
observability table and **not in the billing table at all**, which is a B4
coverage gap independent of the rate.

Corrected in the price table (`20260810011500_b3_price_table`, $0.02/M with the
published URL and read-date). **Neither in-code constant is patched** — SPEC
§4.5, the same reasoning that leaves the Deepgram default alone.

⚠ **No price exists in the code for any OpenAI *chat* model.** Per the standing
rule, OpenAI is Doc Editor + CRM only and the clinical pipeline is all
Anthropic — so this is correctly out of the clinical meter. But if Doc Editor
usage is ever billed, its models are unpriced today and
`claudeCostCents`-style dispatch returns 0 for unknown models rather than
erroring, i.e. **it would silently bill nothing.**

### D.4 Resend — https://resend.com/pricing (read 2026-08-04)

Free: 3 000 emails/month, capped at 100/day, no overage.
Pro $20 → 50 000; Pro $35 → 100 000; Scale $90 → 100 000; $160 → 200 000;
$350 → 500 000; $650 → 1 000 000; $825 → 1 500 000; $1 150 → 2 500 000.
Overage $0.90 → $0.46 per 1 000, decreasing by tier. Enterprise above 3M.

**Not per-call priced.** Resend is a **subscription**, not a meter, so it
cannot be charged as `cost × 1.5` per event. It is 219 rows in `api_usage_events`
today, every one with a NULL `userId` (§C.5). **It belongs in the monthly
reconciliation report as a fixed cost, not in `UsageEvent`.** That is a SPEC
decision the war room should confirm.

### D.5 Boundary of this section

Four vendors checked: Anthropic, Deepgram, OpenAI, Resend. Every figure above
came from the vendor's own page today, not from search snippets or from memory
— **except** the Nova-3 Medical figure, which comes from Deepgram's own
announcement post because their pricing page does not list the model, and that
post carries no date. That one number is flagged rather than trusted, and
confirming it is a **question for Deepgram**, not for another sweep.

---

## E. Stripe feasibility on this stack

Stack as installed: **Next.js 16.2.11**, App Router, React 19.2.4,
`next-auth@5.0.0-beta.32`, 71 `route.ts` handlers, 22 `'use server'` files.

### E.1 Greenfield, confirmed by broad negative

`git grep -rinE "import .*stripe|require\(.*stripe|loadStripe|new Stripe|Stripe\("`
across `apps/`, `packages/`, `scripts/` → **zero lines**. No `STRIPE` in any of
the 12 `.env*` files on disk (including untracked `.env`, `backups/.env.*`), no
`STRIPE` in any compose file or script. No payment/billing/checkout route
directory exists.

There is a **UI placeholder already designed for it**: `settings/page.tsx:895-905`
— *"Billing is handled for you during the pilot. When self-serve billing opens,
this is where it will live."* beside a permanently `disabled` button.

⚠ And a **public claim that is currently untrue**:
`apps/meddoc-pro/src/app/pricing/page.tsx:38` — *"All payments are processed
securely through Stripe."* Line 30 of the same page carries a HIPAA/BAA claim
that the pre-pilot BAA status contradicts. Both live on pro.quillmd.com today.

### E.2 CORRECTION — the Stripe SDK DOES ship in a production container

> Original claim: *"The only Stripe footprint is two UNUSED dependencies in the
> legacy `apps/meddoc-pro` app. They are installed at the repo root but do not
> reach the running production image."* → **REFUTED.**

> ## ✅ REMOVED 2026-08-04
>
> **Root cause, and it is not "standalone tracing".** The worker does not use
> standalone tracing at all. `apps/transcribe-md/Dockerfile.worker:62` is
> `COPY --from=prod-deps /app/node_modules ./node_modules` — the **entire**
> workspace-root tree from `npm ci --omit=dev`. Because every app's
> `package.json` is copied in first so the workspace graph resolves (line 39,
> and the header explains why: the ioredis regression), that `npm ci` installs
> the CRM's dependencies too, hoists them to the root, and the whole thing is
> copied wholesale into the runner. The web app escapes because *its* runner
> copies `.next/standalone` — node-file-trace output, only what is imported.
>
> **The class is bigger than Stripe, and is quantified rather than waved at:**
> 9 of the CRM's 28 production dependencies are unique to it and therefore ship
> in the clinical worker for no reason — `@auth/prisma-adapter`,
> `@hookform/resolvers`, `@stripe/stripe-js`, `file-saver`, `pdf-parse`, `pg`,
> `react-hook-form`, `stripe`, `zustand`. **Only the two Stripe entries are
> removed here**, per the ruling; the other seven disappear when
> `apps/meddoc-pro` is deleted in item **A6**, and they are named so that is a
> checked outcome rather than a hoped-for one.
>
> **The fix:** both entries deleted from `apps/meddoc-pro/package.json`.
> Lockfile diff is exactly two removals, nothing added
> (1187 → 1185 packages), and the **sharp subtree is intact at 28 entries
> before and after** — the known `npm update` splice trap, checked with a
> positive control rather than assumed.

Sentence one holds — `apps/meddoc-pro/package.json:29,46` are the only Stripe
entries repo-wide and nothing imports them. Sentence two checked **one** of four
production containers. Re-run by hand, 2026-08-04:

```
meddoc-pro-transcribe-md-worker-1 : /app/node_modules/stripe        ✅ present
                                    /app/node_modules/@stripe       ✅ present
meddoc-pro-transcribe-md-1        : both                            ❌ absent
```

`stripe@22.0.2` (17.9 MB) and `@stripe/stripe-js@9.2.0` sit inside the **live
clinical worker** — the container that processes patient audio. Next's
standalone tracing excluded them from the web app; the worker image is built
differently and does not.

So they are a **real supply-chain surface today**, not a lockfile curiosity.
(SPEC §4.5.)

### E.3 Webhooks — the Pages Router wrinkle does not apply, and the real trap is narrower

Next's own bundled docs, `node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/route.md:597`:

> *"Notably, unlike API Routes with the Pages Router, you do not need to use
> `bodyParser` to use any additional configuration."*

and the "### Webhooks" example at `:566` is literally `await request.text()`.
No `export const config = { api: { bodyParser: false } }` is needed **or
supported**. Any guidance carried over from Pages Router memory is wrong here.

**Proven in-repo, not docs-only:** `api/visits/[id]/upload/route.ts:174` and
`api/visits/[id]/dictation/upload/route.ts:140` both call
`Buffer.from(await req.arrayBuffer())` with no body config.

**The actual trap is byte-identity.** A Web `Request` body is a single-use
stream, and `JSON.stringify(await req.json())` is *not* byte-identical to what
Stripe signed (key order, whitespace, unicode escaping). The house convention
across 10+ routes is `await req.json()`. **A Stripe webhook must deliberately
break that convention and call `req.text()` first.** It fails as an opaque
signature error, not a parse error — which is why it is worth writing down.

The installed SDK offers both `constructEvent` (sync) and `constructEventAsync`
(`Webhooks.d.ts:31-34`); sync works given `runtime = 'nodejs'`, which every
route already sets. **`generateTestHeaderString` ships too — webhook tests can
run in Vitest with no network and no Stripe account.**

### E.4 Ingress and auth

`proxy.ts:21-26` matches only `/dashboard/:path*`, `/visits/:path*`,
`/settings/:path*` — so `/api/stripe/webhook` is **unauthenticated by default**,
which is correct (the signature *is* the auth) and requires no middleware
exclusion. `Caddyfile:116-124` passes all of `app.quillmd.com` through with no
path gating.

It also means the route is exposed the moment it exists: **the signature check
must be the first statement, before any parsing or DB access.** A
defence-in-depth precedent exists if wanted — `Caddyfile:250-266`,
`@internal path /api/internal/*` → `respond 404`.

`withApiHandler` (`lib/api-error.ts:80-95`) forwards `req` untouched, so a
webhook can keep house style at no cost to signature verification.

### E.5 What must not go into Stripe metadata

**Safe:** `Practice.id`, `User.id`. The paying party is the doctor, not a
patient, so no PHI reaches Stripe and Stripe stays outside the BAA perimeter.
Caveat worth stating: at 197 practices ≈ 196 users, a practice id is
effectively a clinician identity — **personal data, but not PHI.**

**Forbidden:** visit ids and patient ids. `transcribe_visits` carries
`patientName` and `patientSummary` as columns, so a visit id dereferences to a
named patient in one hop. **This rules out per-visit metered billing tagged
with a visit id.** If usage billing is wanted, aggregate from
`api_usage_events` keyed by practice.

**And the loaded gun:** `BillingEvent` (`schema.prisma:1373-1382`) sounds like
an invoice and is a **clinical claims record with a required `patientId`** and
`icd10Items`/`cptItems` JSON. An implementer told "put the invoice id in
metadata" who greps for `billing` lands on a table whose primary key
dereferences to a named patient. It has 0 rows, which makes the trap **quieter,
not smaller.**

### E.6 Two stack-specific landmines

1. **`logAudit` is fire-and-forget against a Postgres enum.** `AuditAction` has
   136 values; a label added only to the TypeScript union is rejected by the
   insert and the rejection is discarded. **This exact bug shipped** — commit
   `535d30d9`. Any `CHECKOUT_COMPLETED` / `SUBSCRIPTION_CANCELED` action needs a
   Prisma migration, not a TS edit. Also: `logAudit` calls `auth()` internally
   (`lib/audit.ts:279-283`), which is request-scoped — **a webhook has no
   session and must pass `userId` and `practiceId` explicitly.**
2. **`scripts/check-qa-mock-posture.sh:38-40` has a hardcoded key list** —
   `ANTHROPIC_API_KEY DEEPGRAM_API_KEY OPENAI_API_KEY RESEND_API_KEY`. It would
   be **blind to a live Stripe key.** `STRIPE_SECRET_KEY` joins that list in the
   same change, and the QA compose entry must **not** use
   `${STRIPE_SECRET_KEY:-sk_test_…}` — that syntax inherits the production value
   whenever `.env` sets it. The guard's own header predicts exactly this failure.

### E.7 Env plumbing

A **secret** key follows a well-worn path: plain compose `environment:`
passthrough (`docker-compose.yml:417-418`), sourced from root `.env`
(`-rw-------`, gitignored). Two lines.

A **publishable** key does not: `NEXT_PUBLIC_*` goes through **build args**, and
per AGENTS.md the verification is to grep the built chunk — *a `NEXT_PUBLIC_*`
read that survives at runtime means it was not inlined.*
**Hosted Stripe Checkout (redirect) avoids the publishable key entirely** and is
therefore the cheaper as well as the safer shape.

---

## F. What this pass did not establish

Stated so the war room is not misled by silence:

1. **A traffic window long enough to retire pro.quillmd.com.** 23 hours, not a
   week. (§A.6)
2. **Whether Deepgram's `$0.0043/min` for nova-3-medical is current.** Their
   pricing page omits the model; the announcement post is undated. (§D.2)
3. **Whether the `worker.ts:983` cost-sum read-after-write races.** Explicitly
   left UNSURE rather than guessed. (§C.9)
4. **Anything about multi-seat behaviour under load.** There is no multi-seat
   practice with clinical data in production to observe. (§B.10)
5. **Nothing was executed.** No schema change, no deletion, no billing code, no
   row written. The deletion plan in §A.7 is a draft.
