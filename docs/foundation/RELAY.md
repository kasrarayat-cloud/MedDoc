# FOUNDATION — the relay ledger

**This ledger is the contract between sessions.** `SPEC.md` says what to build;
`DISCOVERY.md` says what is true today; this says what order, with what proof.

---

## GATE 0 — the war room reviews DISCOVERY

**No build item below may start until this gate clears.** Phase 0 produced five
decisions the war room owns, not the implementer:

| # | Decision | Where |
|---|---|---|
| 0.1 | Fate of the 12 `MEDDOC_PRO`-only accounts — four carry the operator's own name | SPEC §4.1, DISCOVERY §A.5 |
| 0.2 | Grant `TRANSCRIBE_MD` to the cross-app-redirect users, or delete them | SPEC §4.2 |
| 0.3 | "One active note template" — per-doctor or per-practice | SPEC §4.3, DISCOVERY §B.9 |
| 0.4 | The micro-unit denominator and the `× 1.5` rounding rule | SPEC §4.4 |
| 0.5 | Is Resend billed at all? It is a subscription, not a meter | DISCOVERY §D.4 |

Two items are **not** decisions and should be scheduled regardless of the
review's outcome, because they are live defects this pass surfaced:

- **`audit_logs` fails OPEN into `clinic_main`.** 65 production rows are
  misattributed today. → item **T2**.
- **The Deepgram rate is ~3.4× the vendor's published number**, and the
  record shows the correct value was considered and discarded. → item **B3**.

And one item is not a decision but a **security posture question** the owner
should see before the deletion phase: pro.quillmd.com is a publicly-reachable,
PHI-capable write path into the production clinical database, with every table
it touches currently empty (DISCOVERY §A.2). It can be shut off long before it
is deleted.

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

### T2 — close the audit fail-open
`lib/audit.ts:293-294` — `?? 'clinic_main'` becomes a refusal or an explicit
`null`, never a silent write into the largest shared practice. Backfill
`practiceIdSnapshot` on the 38 rows that predate it. The 6 unrecoverable rows
stay unrecoverable and are named in the migration.
**Gate:** the 65 misattributed rows are enumerated before and after (F3); a new
audit write with no session practice is proven not to land in `clinic_main`;
`audit_logs` is named as an S4c exclusion in the same commit that writes the
fail-closed rule.
**Independent of T1** — schedule it first if the war room is slow.

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
| **Phase 0** | ✅ **DONE 2026-08-04** | *(this PR)* | *(cited on merge)* | `SPEC.md` + `DISCOVERY.md` + `RELAY.md`. READ-ONLY on prod: no schema change, no deletion, no billing code, no row written. 28 agents, 5 areas, **7 claims corrected** (6 DRIFTED, 1 REFUTED) — all recorded in DISCOVERY as corrected. Vendor prices verified live against four vendors' own pages, dated. |
| GATE 0 | ⏸ **WAITING** | — | — | War room reviews DISCOVERY. Five decisions, listed above. |
| T1 … A6 | ⏸ not started | — | — | Blocked on GATE 0. |

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
