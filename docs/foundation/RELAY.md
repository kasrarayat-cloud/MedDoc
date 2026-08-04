# FOUNDATION — the relay ledger

**This ledger is the contract between sessions.** `SPEC.md` says what to build;
`DISCOVERY.md` says what is true today; this says what order, with what proof.

---

## GATE 0 — ✅ CLEARED 2026-08-04

All five decisions are made and are recorded **verbatim in `SPEC.md` §4**.
Summary only — SPEC is the contract:

| # | Decision | Ruling | Where |
|---|---|---|---|
| 0.1 | The 12 `MEDDOC_PRO`-only accounts | Excluded from backfill, **deactivated**, rows retained, no deletion. **Owner veto window open until the TEAMS migration runs** | SPEC §4.1 |
| 0.2 | Cross-app redirect users | Classify **by where clinical data lives**, not by entitlement | SPEC §4.2 |
| 0.3 | Note templates | **PER-DOCTOR in v1** — the existing unique index stays. Practice-shared library is post-TEAMS, flag-gated | SPEC §4.3 |
| 0.4 | Money | Integer **micro-dollars**; `cost_micro × 3 / 2` in integer math, half-up at the micro-dollar; **cent rounding at display only** | SPEC §4.4 |
| 0.5 | Resend | **Not metered.** Only per-run vendors produce `UsageEvent`s. Price table gains **PROVENANCE** per rate | SPEC §4.5 |

### The security block that jumped the queue — ✅ DONE 2026-08-04

Three items were ruled to precede every build item. All three shipped in one
change; see the ledger row.

1. **pro.quillmd.com is OFFLINE.** 410 at the edge on every path, container
   stopped. The capability died; the **code** deletion is still item **A6**.
   Credentials were shared, not separable — container-stop is the control, and
   least-privilege per-app Postgres roles move into **TEAMS-phase hygiene** as
   a named item (today there is exactly one login role and it is SUPERUSER).
2. **The Stripe SDK is out of the clinical worker.** Root cause was not
   standalone tracing; the worker ships the whole workspace-root
   `node_modules`. Seven further CRM-only packages still ride along and are
   named in DISCOVERY §E.2 so **A6** can check them off rather than hope.
3. **Audit attribution fails closed.** No fallback practice; unresolvable means
   `NULL` + an `UNATTRIBUTED` tombstone + a loud error. The 64 wrong rows are
   repaired by **APPENDING** corrections — never by editing, because an audit
   trail that can be rewritten is not one.

⚠️ **The count was 64, not 65.** DISCOVERY's original figure included one
`USER_GRANTED_SUPER_ADMIN` row that is *correct* — `grant-admin/route.ts`
deliberately files the event under the **target's** practice, not the actor's.
Corrected in place. A repair driven by the original query would have damaged a
correct row, which is the general lesson: **a cross-tenant admin action has two
defensible tenants, and a checker that knows one of them manufactures
findings.**

### Still standing from Phase 0

- **The Deepgram rate is ~3.4× the vendor's published number.** Deliberately
  **NOT** patched now (SPEC §4.5): no billing math exists to be wrong yet, and
  re-basing the constant would silently move a year of historical `ai_calls`
  comparisons. → corrected by the price table in **B3**.
- **`worker.ts:983` read-after-write** — carried as a named open item on the
  TEAMS gate, not dropped.

---

## Rules

The Rounds relay's rules apply verbatim and are not restated here — read
`docs/rounds/RELAY.md` §Rules first. In particular: **1** (one item per session,
taken to its gate), **2a** (merge-commit CI cited by SHA and run id; local
results never close an item), **2b** (no push mid-run), **2c** (no evidence
before the event), and **7** (say what would make the check fail, then make it
fail) with its corollaries.

Four rules are specific to this program.

**F1. A tenant test that has never seen two seats has proved nothing.**
193 of 196 users are alone in their practice, and **no practice with more than
one user holds any clinical data at all** (DISCOVERY §B.10). A `practiceId`
filter passes vacuously against that population. **T1 exists to remove this
excuse, and no item after T1 may cite a gate that ran only against a solo
practice.**

**F2. A billing number is not proved by a green test. It is proved against the
vendor's own page, with a URL and a date.**
Every rate in the price table carries both. The Deepgram error (DISCOVERY §D.2)
survived a deliberate reconciliation *because both sides of it were internal*.

**F3. READ-ONLY on production stays the default.** Any item that writes to
production data is a **deliberate transactional act** — abort-on-mismatch
guard, audit row, stated row count before and after — never a side effect of a
migration or a check. The house precedent is the imaging-E/M artifact purge.

**F4. The billing writer must be incapable of running outside production, and
"incapable" needs two conditions** — the code gate *and* credentials that are
not real. `scripts/check-qa-mock-posture.sh` reads the **running containers**,
not the compose file, for exactly this reason. A `${STRIPE_SECRET_KEY:-…}` in
`docker-compose.qa.yml` is a bug until proven otherwise.

---

## Phase TEAMS

Dependency order. Each item is one session, taken to its gate.

### T1 — the multi-seat fixture
Build a QA practice with **≥2 members and real clinical data** (visits,
deliveries, edit patterns, templates), and a second practice to be excluded
from.
**Gate:** a filter test that **fails** when the practice predicate is removed —
demonstrated by mutation, not asserted. Without the red, T1 is not done.
**Blocks:** every item below.

### T2 — close the audit fail-open — 🟩 **DONE 2026-08-04** (code) / ⏸ repair pending
The code half shipped ahead of TEAMS as part of the security block:
`?? 'clinic_main'` is gone, `signOut` threads the practice by traversal,
`gate-audit-attribution-failclosed` is proven red against four mutations, and
`AUDIT_ATTRIBUTION_CORRECTED` shipped **with its Prisma migration**.

**Still to run, deliberately not run yet:**
`npx tsx scripts/repair-audit-attribution.ts --apply` against production. It is
read-only by default and it **never updates or deletes** — it appends one
correction per wrong row. Holding it until the migration is applied to prod
(the enum label must exist first, or every insert is rejected — silently, per
`535d30d9`).

Still owed in TEAMS proper: backfill `practiceIdSnapshot` on the 38 rows that
predate the column, and name `audit_logs` as an S4c exclusion in the same
commit that writes the fail-closed rule.

### T3 — `practiceId` on `transcribe_visits`, with a stated derivation
Column added nullable, backfilled, then `NOT NULL`. **Write down which
derivation path was used** (`user.practiceId` or `patient.practiceId`) — they
agree on all 26 rows today and nothing in the database keeps them agreeing
(DISCOVERY §B.5).
**Gate:** `assert-migrations-applied.sh` green; 26/26 backfilled with 0
mismatches, counted before and after; a DB-level constraint or trigger that
makes a cross-practice visit impossible, proven by attempting one.

### T4 — `createdBy` / `signedBy`
Columns added; `POST /api/visits/[id]/sign` records the actual signer.
**Gate:** on the T1 fixture, a **non-owner member signs a visit and `signedBy`
≠ `userId`.** A solo-practice run cannot pass this gate (F1). Reconcile the
three disagreeing signer records (36 / 16 / 16, DISCOVERY §B.7) or state in the
ledger why they still disagree.

### T5 — the one practice-scoped accessor, and the guard that keeps it one
Every clinical read/write moves behind it. It takes the practice as an
argument; it does not read the session.
**Gate:** **mutation** — add a raw `prisma.transcribeVisit.findMany` outside the
accessor, watch the guard redden, restore. The guard must also catch
`doctor_edit_patterns` (DISCOVERY §B.4), which is the table a source grep is
most likely to miss and the one that leaks whole notes.

### T6 — roles, and the sign gate that refuses
OWNER / CLINICIAN / TECH. The sign gate is server-side and fail-closed: an
unrecognised or absent role refuses.
**Gate:** a TECH member's `POST /sign` is **refused by the route** — proven with
a direct request, not by a hidden button — and the refusal writes an audit row.
This is the R1 lesson: a gate nothing enforces is one path away from not
existing.

### T7 — the remaining tables gain `practiceId`
`visit_deliveries`, `doctor_edit_patterns`, `rx_warning_overrides`, the four
unscoped `template_twin_*` tables, `account_deletions`, and `note_templates`
with the platform-global carve-out.
**Gate:** the fail-closed rule ("no clinical row without `practiceId`") lands
with its **two named exclusions** — `audit_logs` (S4c, cited) and
`api_usage_events` (271 NULL rows, telemetry). Zero-row tables constrained now
(DISCOVERY §B.3). ⚠ Template Twin's ingest is load-bearing on every `.docx`
upload — that write path is exercised, not assumed.

### ⚠️ TEAMS EXIT GATE — carried open items that must be RESOLVED OR RESTATED

TEAMS is not closed while any of these is silently unaddressed. Each is a
question somebody already asked and nobody has answered; closing the phase
without a written verdict on each is how they become invisible.

| Carried item | What closing it looks like |
|---|---|
| **`worker.ts:983` read-after-write** — the per-visit cost sum reads `ai_calls` in the same tick-chain that wrote it. Phase 0 left this **UNSURE** and said so rather than guessing; the L7 fan-out takes seconds so earlier writes have almost certainly landed, but the last-writer case was never proved either way and was not reproduced. | Either a reproduction (or a proof it cannot race), **or** a written statement that it is accepted-unproven and why. Not silence. |
| **`practiceIdSnapshot` backfill** — 38 rows predate the S4c column (DISCOVERY §B.8). | Cheap, separate, non-blocking. Do it or say why not. |
| **`audit_logs` named as an S4c exclusion** in the same commit that writes the fail-closed "no clinical row without practiceId" rule. | Named by name, with the S4c reasoning cited, so a future tidy-up cannot "fix" it and re-break account deletion. |
| **The 12 `MEDDOC_PRO`-only accounts** — GATE 0 ruled *excluded + deactivated, rows retained*, with an **owner veto window open until the TEAMS migration runs** (SPEC §4.1). | Confirm the veto has lapsed **before** excluding them. Four of the twelve carry the operator's own name. |

### T8 — invites carry practice + role
**Gate:** a code minted for `(practice, CLINICIAN)` produces a member of that
practice with that role, and one minted for a practice that no longer exists
refuses. Audit row per issuance.

---

## Phase BILLING

Depends on TEAMS: the wallet is per-practice.

### B1 — capture the vendor request id
Deepgram first — it is **already parsed and discarded**
(`deepgram-batch.ts:108-115`, read at `:342`), so it is the cheapest fix in the
program. Then Anthropic's `response._request_id`, which is read nowhere.
**Gate:** every success row carries a **vendor** id, not a `randomUUID()`;
a replayed write is deduped; the schema comment that already claims this
becomes true.

### B2 — wire the failure paths into the durable table
Close DISCOVERY §C.3: the five Anthropic failure branches and both Deepgram
failure branches write `api_usage_events`, and the Deepgram failure rows carry
`audioSeconds`.
**Gate:** force a `SCHEMA_FAIL` and a Deepgram timeout on QA and prove a usage
row exists for each. Then settle the durability inversion (§C.4) — state in the
ledger which table is the billing source and what stops it being deleted.

### B3 — the versioned price table
Seeded from DISCOVERY §D, every rate with its URL and read-date.
**Three corrections land here**: the Deepgram rate (~3.4× over), the **two**
Anthropic cache-write classes (1.25× and 2×, currently collapsed into one), and
three Deepgram rates rather than one (`nova-3-medical` pre-recorded, `nova-3`
pre-recorded, `nova-3` streaming) with the row recording which ran.
**Gate:** re-pricing a historical row **does not change it** — the snapshot is
proven by changing a rate and re-running. Per F2, each rate cites a page.
⚠ Sonnet 5's introductory rate expires **2026-08-31**; the table is versioned by
date, not by model name.

### B4 — `UsageEvent` per stage
All twelve Anthropic layers **including L4b, L6b and the `llm-mdm` judge**,
which are invisible to a `worker.ts` call-site scan (DISCOVERY §C.1). Fix the
unit labels: `COALESCE(audioDurationSec, dictationDurationSec)`, real model
name instead of the hardcoded `'nova-3-medical'`, real operation instead of
`'transcribe_realtime'`.
**Gate:** one full QA pipeline run produces one event per stage, **counted
against the enumerated stage list**, not eyeballed. The audio path must be
exercised on QA — it is unexercised in production (all 26 visits are
`text_notes`), so production cannot be the proof.

### B5 — money
Integer micro-unit; append-only `LedgerEntry` with `balanceAfter`; practice
wallet.
**Gate:** append-only enforced at the **database**, not by convention — an
`UPDATE` and a `DELETE` are both attempted and both refused.
`balanceAfter` consistency proven across a generated sequence.

### B6 — `charge = cost × 1.5`, and the prod-only writer
**Gate:** the writer **refuses on the live QA stack**, demonstrated, not
asserted (F4). `STRIPE_SECRET_KEY` is added to
`scripts/check-qa-mock-posture.sh` `KEYS` in the same commit, and the QA compose
entry does **not** use `${STRIPE_SECRET_KEY:-…}`. Rounding rule stated and
tested at the boundary.

### B7 — Stripe Checkout + webhook
Hosted Checkout only — it avoids the publishable key and its build-arg inlining
trap entirely (DISCOVERY §E.7). `$10` promo bucket as a separate ledger bucket.
**Gate:** signature verification is the **first statement** in the handler;
`req.text()` before anything, never `req.json()`; tests use
`generateTestHeaderString` with no network and no Stripe account. The
`ADMIN_*`/`CHECKOUT_*` audit labels ship as a **Prisma enum migration** — a TS
union edit alone is silently discarded (`535d30d9`). The webhook passes
`userId` and `practiceId` explicitly; it has no session.
**Forbidden in metadata:** visit ids, patient ids, and anything reachable from
`BillingEvent` (DISCOVERY §E.5).

### B8 — fail-closed block + system-fault auto-credit
Insufficient balance blocks the work; **if the balance cannot be read, it also
blocks.** System faults credit back via DLQ classification.
**Gate:** both directions proven — a zero balance blocks, and a DLQ'd system
fault credits. This makes `/admin/queues` load-bearing for money; A2 must land
before or with this.

### B9 — monthly reconciliation
Our ledger against the vendors' invoices, line by line — which is what B1
exists for.
**Gate:** one real month reconciles, and the report **names its own
discrepancies** rather than rounding them away.

---

## Phase ADMIN

Legacy deletion is last, deliberately.

### A1 — platform ADMIN flag + `ADMIN_*` audit actions
**Gate:** every new label exists in the **Postgres enum** (migration), and one
of each is written and read back. A label that only exists in TypeScript is the
known silent failure.

### A2 — ops
Queues/DLQ absorbed **with a navigation entry** — it has none today and is the
one page an operator cannot find (DISCOVERY §A.3). Standing checks surfaced.
Audit viewer.
**Gate:** the existing `26-admin-superadmin.spec.ts` still passes; a DLQ entry
is visible to an operator who did not type the URL.

### A3 — business
Practices/members, invite issuance UI, usage + revenue, price-table editor.
**Gate:** the price-table editor writes a **new version**, never mutates an old
one — proven by re-pricing a historical row and watching it not move (B3's
gate, re-run through the UI).

### A4 — the ZERO-clinical-content guard
**Gate:** a source-level guard, negative-controlled — render a patient name in
an admin component and watch it redden, then restore. Without the red it is a
comment.

### A5 — legacy rewire
The four blockers, in DISCOVERY §A.7's order: root `package.json` scripts → CI
`test` job → the `auth.ts:229` cross-app redirect (with decision 0.1/0.2
applied) → the nightly smoke assertions.
**Gate:** CI green with **no job silently vacuous** — the retired `test` job is
retired *with a note*, not deleted quietly, and the expected check set is
re-read and restated in the ledger.

### A6 — legacy deletion
`apps/meddoc-pro/`, the compose service, the Caddy block, the nginx
`server_name` entry, the DNS record.
**Preconditions, all three:** A5 merged; a **traffic window longer than 23
hours** (DISCOVERY §A.6) or a 410 canary on `/login` that nobody trips; and
`POST_MERGE_TODO` §21 amended — the 2026-05-04 decommission was a recorded
decision with a written reversal procedure, and deleting is a change to that
decision, not a cleanup.
**Gate:** co-tenant HTTP status unchanged; `app.quillmd.com` and
`admin.quillmd.com` unchanged; the rollback tag table in
`docs/DEPLOYMENT_RUNBOOK.md` §3 states what a rollback can and cannot restore
once the app leaves `main`.

---

## Invariants re-checked every item

- `bash scripts/assert-migrations-applied.sh` — after any migration, and before
  reading a deploy's own success message as proof.
- `bash scripts/check-qa-mock-posture.sh` — every item that touches a vendor key.
- `bash scripts/check-imaging-em-artifacts.sh`, `check-minio-encrypted-mount.sh`,
  `check-pg-encrypted-mount.sh` — the standing set.
- Close-out hygiene per AGENTS.md: shred, **check exit codes**, escalate, *then*
  remove.
- Branch cadence: branch from `main`, merge back on green, retire the branch.

---

## Ledger

| Item | Status | Merge SHA | CI run | Notes |
|---|---|---|---|---|
| **SECURITY BLOCK** | 🟩 **LIVE IN PRODUCTION 2026-08-04** | **`a0b8775f`** (PR #518) | `CI` · `e2e` · `secrets-scan` all `completed/success`; tree identity proven — branch head `7a038e27` and merge `a0b8775f` share tree `1f3c68e1` | **A.1** pro.quillmd.com **410 on every path, GET and POST**, container `exited (143)`; app/admin/quillmd/www/staging unchanged, 5 co-tenant hostnames unchanged incl. their 3 pre-existing failures, 16 non-meddoc containers untouched. ⚠️ *"disable only its own vhost"* was impossible — one file carries all five hostnames, and `sites-enabled/dealhunter` (`server_name … _;`, first in the glob) is the de-facto default, so an **unnamed** host falls through to a **co-tenant**. Explicit 410 block; `:80` keeps the name so ACME still answers (verified 404-on-probe, not 301/410). ⚠️ Found a **shadow vhost being loaded** — `quillmd.bak-20260725`, a regular file in `sites-enabled/`, carrying the **pre-S2 spoofable `X-Forwarded-For`**, inert only by glob order; removing the name from the live file would have **promoted it**. Evicted. Credentials **shared, not separable**: `DATABASE_URL` byte-identical across three containers, and Postgres has **one** login role, SUPERUSER — container-stop **is** the control; least-privilege roles → TEAMS hygiene. **A.2** Stripe out of the worker; root cause is `Dockerfile.worker:62` copying the whole workspace-root `node_modules`, **not** standalone tracing; 9 of 28 CRM deps ride along, 7 named for A6; lockfile 1187→1185, **sharp intact 28→28**. **A.3** fail-open closed; **71 corrections APPENDED** (65+6), originals **still 65 and still wrong**, total 10153→10224 (+71 exactly), 71/71 `targetId`s resolve. Deploy log `deploy-20260804T034655Z.log`; rollback tags **`:pre-secblock-20260804`** cut against RUNNING ids `cdfa16cc599b` / `1526b97cf960` / `2d05d22572ba`. Post-deploy verifier PASS with positive controls on every zero. |
| **Phase 0** | ✅ **DONE 2026-08-04** | **`c36eeda1`** (PR #517) | `CI` · `e2e` · `secrets-scan` all `completed/success` | `SPEC.md` + `DISCOVERY.md` + `RELAY.md`. READ-ONLY on prod: no schema change, no deletion, no billing code, no row written. 28 agents, 5 areas, **7 claims corrected** (6 DRIFTED, 1 REFUTED) — all recorded in DISCOVERY as corrected. Vendor prices verified live against four vendors' own pages, dated. |
| GATE 0 | ✅ **CLEARED 2026-08-04** | — | — | Five rulings, recorded verbatim in `SPEC.md` §4. |
| **T2** (code half) | 🟩 **LIVE 2026-08-04** | `a0b8775f` | see SECURITY BLOCK | Fail-closed + traversal + guard + migration + the append-only repair, **applied to prod**. Still owed in TEAMS proper: `practiceIdSnapshot` backfill on the 38 pre-column rows, and naming `audit_logs` as an S4c exclusion in the commit that writes the fail-closed rule. |
| T1, T3 … A6 | ⏸ not started | — | — | GATE 0 is clear; **F-ret closes first** per the owner's sequence. |

---

## What Phase 0 found that nobody asked about

Two things outrank the framing they were found under. Both were found by
measurement, not by looking for them.

1. **pro.quillmd.com is a live, publicly-reachable, PHI-capable write path into
   the production clinical database** — one shared `DATABASE_URL`, writes to
   `patients` / `documents` / `medications` / `allergies` / `appointments`,
   gated by an RBAC role rather than a platform entitlement, with no owner, no
   CI and no audits *by its own README*. Every table it touches is empty, so
   this is a capability and not a breach — but it does not need to wait for
   phase ADMIN to be switched off. (DISCOVERY §A.2)

2. **The Stripe SDK already ships inside the live clinical worker container.**
   `stripe@22.0.2` and `@stripe/stripe-js@9.2.0` are present in
   `meddoc-pro-transcribe-md-worker-1` — declared by a decommissioned app,
   imported by nothing, excluded from the web image by standalone tracing and
   **not** excluded from the worker. A real supply-chain surface today.
   (DISCOVERY §E.2)

Neither is a build item. Both are decisions the owner can take this week.

## Found on the way past — 2026-08-04, during F-ret.1

Neither of these belongs to F-ret and neither was looked for. They are written
here because a finding that lives only in a session transcript is not a finding:
the next sweep cannot see it, and an unanswered question decays into "probably
fine" through nothing but repetition. That is exactly how the May audit PDF sat
tracked and unlisted for eleven weeks.

### 1. `em-coding:llm-mdm` does not honour `MOCK_AI_CALLS`

The `e2e` job's app logs carry real Anthropic requests:

```
scope: em-coding:llm-mdm   error: 401 {"type":"authentication_error",
                                       "message":"invalid x-api-key"}
```

They failed only because CI's key is a dummy — which is the second condition
working exactly as AGENTS.md says it must: *"`MOCK_AI_CALLS=true` stops calls
only while every code path honours the flag; dummy credentials are what survives
a code regression."* This is a code path that does not honour it.

**Nothing leaked and no balance was burned here.** The concern is the same shape
as the 298 real Anthropic calls the QA stack made on 2026-07-28 — a stack whose
header promised it could reach nothing. `scripts/check-qa-mock-posture.sh` reads
the running containers' env; it cannot see a code path that ignores what it
finds there.

**Located, not just observed.** `src/lib/em-coding/llm-mdm.ts` contains **no
reference to `MOCK_AI_CALLS` at all** — it constructs its client and calls, and
logs the vendor's refusal at `:500`. Sibling paths do check the flag
(`src/worker/layers/04b-anchor-verify.ts`,
`src/actions/preview-note-template.ts`), so this is one path that was missed,
not a convention nobody follows.

**The verification that matters is not the compose file.** `docker-compose.qa.yml`
hardcodes `MOCK_AI_CALLS: "true"` for both app and worker (`:211`, `:308`) — and
the calls happened anyway. That is the whole point: reading config proves
nothing about a path that never reads it. `scripts/check-qa-mock-posture.sh`
inspects the running containers' env, so it would report this stack GREEN while
it was calling a vendor.

**Not yet established:** how many other vendor-calling paths skip the flag. The
sweep is cheap and has an obvious shape — enumerate every construction of an
Anthropic/OpenAI/Deepgram client under `src/`, subtract the ones with a mock
branch, and report the count **with a positive control**, or the zero means
nothing.

### 2. `a11y-ci` never runs on `main`

`.github/workflows/a11y.yml` triggers on `pull_request` **only**. The other
three required workflows (`CI`, `e2e`, `secrets-scan`) all carry
`push: [main]` as well.

So the axe-core sweep validates the PR head and **never the merge result**.
Anything reaching `main` by another path — a direct push, or a merge whose
outcome differs from the head that was tested — is structurally invisible to it.
It reads as coverage and there is a route it cannot see, which is the two-month
gate defect in miniature for the third time this program.

Found while citing #525's merge commit `c150b600` across all four workflows by
name: three could be cited and the fourth could not, because it does not run
there. Quoting its PR-head green next to a merge SHA would have been precisely
the substitution the citation rule exists to prevent.

**The fix is one line** — add `push: [main]` to `a11y.yml`. It is *not* applied
here because it adds a ~4.5-minute job to every push to `main`, which is a
cadence decision for the owner rather than a correctness one. State a verdict
either way; do not leave it as a third silent gap.
