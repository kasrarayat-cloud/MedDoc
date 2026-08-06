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

### ✅ T1 — the multi-seat fixture — DONE 2026-08-05

**Gate met by DEMONSTRATION.** T1's own wording: *"a filter test that FAILS when
the practice predicate is removed — demonstrated by mutation, not asserted.
Without the red, T1 is not done."* Three mutations, each red:

    M1  remove the practice predicate  → THE GATE reds
    M2  point the fixture tag at nothing → the non-vacuity guard reds
    M3  scope patients to a missing slug → the native-column path reds

Clean run 4/4 green. Fixture: `t1-alpha` **2 members / 6 visits**, `t1-beta`
**1 member / 3 visits**, both with patients, templates and a SIGNED/READY mix.
`scripts/seed-t1-multiseat.ts` (fail-closed via `assertNonProdDatabase`, and it
THROWS if either side lands empty), wired into `e2e.yml` after the guarded seed.
Gate: `tests/e2e/scenarios/31-practice-isolation.spec.ts`.

#### ⚠️ WHAT MEASUREMENT CHANGED ABOUT THIS ITEM

**The "Practice entity + personal-practice backfill" half was ALREADY SHIPPED.**
Measured against production: 196 users, **0 without a practice**, 197 practices,
**178 of them personal** and named `solo-<hash>-<hash>` — an automated
personal-practice path already exists. Nothing to design; nothing to backfill.
Recorded so it is not built twice.

**But the multi-seat half was NOT, and the reason is the whole point of T1.**
Three multi-member practices already existed — `main-clinic` (11 members),
`qa-audit` (5), `test-clinic-b` (2) — and every one has **ZERO visits, ZERO
templates**. A filter test over an empty practice cannot go red: drop the
predicate and the answer does not change, because there was nothing to leak.
That is why T1 blocks everything below it, and it is a structural instance of the
vacuity trap — an assertion about a set whose size was never established.

**The gate is written to be BREAKABLE.** `scopedVisits()` takes the predicate as
an argument, and the gate runs it twice — scoped and unscoped — asserting the two
answers DIFFER, and that the difference is exactly beta's row count. A test that
only asserted "alpha's rows come back" would pass on a query that filters nothing.

#### TWO FACTS FOR T3, MEASURED HERE

- **`transcribe_visits` has NO practice column.** A practice scope is a JOIN
  through `users` today. T3's job.
- **`transcribe_md_patients` IS already `practiceId`-scoped natively.** So the
  two clinical tables sit on **different tenancy models right now**. The gate
  exercises both deliberately, so the native-column path is not left untested
  until T3 changes the other one.

#### CARRIED

**16 orphaned practices with zero members**, left behind by deleted users
(`solo-*` slugs). Harmless, not blocking, not cleaned — recorded so a future
count of "practices" is not mistaken for a count of tenants.

---

### T1 (original wording) — the multi-seat fixture
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

### ✅ T3 — `practiceId` on `transcribe_visits` — DONE 2026-08-05

#### THE DERIVATION, STATED: `patient.practiceId`. NOT `user.practiceId`.

Both agreed on all 26 production rows when this was written — measured
2026-08-05: **26 visits, 26 agree, 0 disagree, 0 nulls, 0 visits without a
patient.** Nothing in the database kept them agreeing, which is exactly why the
choice had to be made rather than inherited from whichever join was handy.

**Why the patient wins.** A note belongs to the practice that owns the CHART. A
locum from practice B seeing a patient of practice A creates a note in **A**;
deriving from the author would file it in B and split that patient's history
across tenants — silently, and irreversibly by the time anyone noticed.

**And structurally:** `transcribe_md_patients.practiceId` is already the tenancy
anchor. Deriving from the patient keeps **one** source of truth. Deriving from
the user creates a **second, independent** one, and two sources that nothing
reconciles is precisely the drift this column exists to end.

#### ⚠️ THE CONSTRAINT IS A COMPOSITE FK, NOT A TRIGGER

    transcribe_visits(patientId, practiceId) → transcribe_md_patients(id, practiceId)

A trigger can be disabled, skipped by a bulk load, or dropped in a restore. A
composite FK makes the bad row **unrepresentable**: there is no `(id, practiceId)`
pair to point at, so the storage layer refuses it and application code has
nothing to route around. It required adding `@@unique([id, practiceId])` to the
patient model — redundant for uniqueness (`id` is the PK), required for
referenceability, and noted in the schema so a tidy-up cannot remove it without
removing the guarantee.

#### GATE — MET, AND PROVEN BY ATTEMPT

    cross-practice INSERT   → ERROR: violates transcribe_visits_patientId_practiceId_fkey
    same INSERT, correct    → INSERT 0 1

⚠️ **The positive control is what makes the refusal mean anything.** "The insert
failed" proves nothing alone — a typo'd column, a missing user, a dropped table
all fail too. Only the pair shows the constraint rejects the wrong TENANT
specifically.

Backfill: **58 visits on QA, 0 null, 0 mismatch**, counted after; the migration
itself `RAISE EXCEPTION`s if any row is still NULL before `SET NOT NULL`, so a
half-run migration cannot report success. Column is `NOT NULL`. Scoping index
added.

Repeatable gate: `tests/e2e/scenarios/32-visit-practice-constraint.spec.ts`,
**mutation-proven** — dropping the FK reds 2 of its 4 tests.

⚠️ **NOT YET APPLIED TO PRODUCTION.** The migration lands with the next
`deploy-prod.sh`, which runs `prisma migrate deploy` and asserts afterwards. The
26 prod rows will backfill from the same derivation; the abort guard is what
makes that safe to do unattended.

---

### T3 (original wording) — `practiceId` on `transcribe_visits`, with a stated derivation
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

### ⏸ T4 — createdBy / signedBy — **PARTIAL 2026-08-06. Blocked as a DEPENDENCY.**

**T4-a LANDED** (PR #529, merge `ee6aabfb`, deployed 2026-08-06). Both columns,
both derivations stated in the migration header, the author fallback DECLARED as
a fallback, server-side `signedBy` in the sign statement, and the CHECK.

Production backfill verified: **26 visits · createdBy null 0 · differs 0 ·
signed 16 · unattributed 0**, and all **16 signedBy came from the 1:1 audit
rows** (`matches_audit 16 / differs 0`) — the fallback never fired, exactly as
the header predicted. `transcribe_visits_signed_requires_signer` is live.

#### ⚠️ THE POSITIVE GATE IS BLOCKED ON T5+T6. IT IS NOT A MISSING TEST.

> **"the positive gate is blocked on T5+T6; it is not a missing test."**

`src/app/api/visits/[id]/sign/route.ts:208`:

    if (!visit || visit.userId !== userId) return apiError('not found', 404);

The sign route is **owner-only**. A second member signing a visit the owner
created receives a 404. There is exactly one authorization check and no
practice-scoped path anywhere: visit access is `userId`-scoped throughout, and
`practiceId` appears in those routes only to gate PATIENT FK changes.

So T4's gate — *"a non-owner member signs and signedBy ≠ userId"* — is
**structurally unpassable today**. That is the gate working as designed: its own
wording says *"a solo-practice run cannot pass this gate (F1)."* It was written
to stay red until multi-seat access exists.

Building it inside T4 would mean implementing T5's accessor and T6's role model
under T4's name. **T4 CLOSES WHEN T6 LANDS** and a second CLINICIAN signs through
the real role-gated route, proven three ways: on the wire, in the database, and
in the audit chain where `VISIT_SIGNED` names the second member.

#### Schema drift — enumerated, and two items were MINE

| Drift item | Class | Disposition |
|---|---|---|
| `note_templates_one_system_default` | PARTIAL unique | **inexpressible in Prisma** — documented in place |
| `note_templates_one_active_per_doctor_encounter` | PARTIAL unique, `NULLS NOT DISTINCT` | **inexpressible** — documented, with a DO-NOT-FIX warning |
| `transcribe_md_patients_name_trgm_idx` | GIN/expression | already documented (`schema:1700`) |
| `transcribe_visits_practiceId_idx` | plain | **mine, T3** — now declared |
| `transcribe_visits_signedBy_idx` | plain | **mine, T4** — now declared |

⚠️ **THE PRESCRIBED FIX WOULD HAVE BROKEN PRODUCTION, and the war room ratified
the correction.** The instruction was to *"declare the `@@unique` Postgres
already enforces"*. Postgres does not enforce that. It enforces a PARTIAL unique
`WHERE status='active' AND doctorId IS NOT NULL`, with `NULLS NOT DISTINCT` —
Prisma expresses neither. `@@unique([doctorId, encounterType])` would be a FULL
unique, strictly stronger, and production **already holds 1 doctor+encounterType
group with more than one row** across all statuses (0 among active). It would
fail to apply or start rejecting legitimate inactive history.

**Consequence, recorded so nobody re-opens it:** there is no compound unique
Prisma can see, so `noteTemplate.upsert` on that pair is impossible. Seeds use
find-then-create. That is the only available shape, not an unfinished workaround.

**Standing expectation, now canon:** the drift enumeration reports
**UNDECLARED-PLAIN = 0**. Partial and expression indexes are the only permitted
residue, each documented in place.

---

### ✅ T5 — the one practice-scoped accessor — **CLOSED 2026-08-06**

`src/lib/practice-scope.ts`. It takes the practice as an argument and does not
read the session, as specified. It returns a **PREDICATE, not a wrapped query**:
a wrapper owning the whole query has to re-expose every Prisma option its callers
use, and the first one it fails to expose gets worked around with a raw call —
the exact leak it exists to close.

**Gate MET, and then some.** The specified mutation (a raw
`prisma.transcribeVisit.findMany` outside the accessor) reds it. So does an
unscoped `doctorEditPattern` read — see the ⚠️ below. So does routing
`visitScope` through the author (`user: { practiceId }`), an undeclared system
read, a cast that manufactures a brand, and a stripper that mistakes code for a
comment. Each was proven and restored.

#### THE LEDGER — the ratchet, and the number that closed it

Every step lowered **in the same commit as the code that earned it**, so the
number in the guard and the number in the codebase never disagreed.

| | count | what happened |
|---|---|---|
| accessor lands | **81** | the guard BEFORE the adoption, deliberately |
| declaration | **78** | `PERSONAL_SCOPE` — reads whose SUBJECT is the user |
| tranche 1a | **60** | by-id API routes. **No authorization change.** |
| tranche 1b | **22** | `transcribe_visits` finished; reads widened to the practice |
| tranche 2 | **10** | `note_templates` **RULED doctor-scoped — not migrated** |
| tranche 3 | **0** | `transcribe_md_patients` |
| **the flip** | **wall** | its own commit, `2e69a967` |

**What the zero means, narrowly:** every request-context read of a clinical model
either carries the accessor's predicate or sits in a bucket declared BY FILE AND
COUNT and checked in both directions — SYSTEM 18, PERSONAL 3, DOCTOR 12,
SYSTEM_DEFAULT 1, COMMENT 1. It does **not** mean the app is free of tenancy
bugs. It means there is no longer a clinical read that nobody has looked at.

**The ratchet was not deleted at zero.** `MAX_UNSCOPED_REQUEST_READS` stays, at
0, with the assertion unchanged — the same line that said "do not grow" now says
"do not exist". A fresh check that reports zero on its first run has proved
nothing; this one has been running and falling since the first commit.

#### ⚠️ THE GUARD WAS NOT WATCHING `doctor_edit_patterns` — the table this spec named

The spec said, in as many words, that the guard must catch it: *"the table a
source grep is most likely to miss and the one that leaks whole notes."* It was
absent from `CLINICAL_MODELS` through all three tranches, so **the wall reached
zero having never looked at it.**

Nothing would have surfaced it. Both reads are correct, no test failed, no sweep
complained — the guard was telling the truth about a smaller question than it
appeared to answer. Found by re-reading the item's own acceptance criteria before
writing this row, not by any check. **"The gate passed" is not "the gate covered
what was asked."** Fixed in `6a36ab84`; zero holds with the table in scope.

#### ⚠️ TRANCHE 2 IS A RULING, NOT A MIGRATION — and it wants a war-room nod

`note_templates` stay **doctor-scoped**. A template is the doctor's own note
FORMAT, not clinical data about a patient; widening it would put a colleague's
formats in your template picker and list them as yours in Settings.

And there is **no tenancy hole to close**: `doctorId = session.user.id` is
STRICTLY NARROWER than a practice predicate, so no cross-practice template read
is reachable. Migrating them would WIDEN them. All 12 sites were traced to the
session before being declared.

This is consistent with **T7**, which already carves `note_templates` out as
"the platform-global carve-out". If the intent was that templates also become
practice-uniform — a clinic with one house format — that is a **product change
with UI consequences**, its own item, not a scoping change.

#### The E2E pair, proven red on the pre-change build

`tests/e2e/scenarios/34-practice-uniform-read.spec.ts`. `31-practice-isolation`
proves the COLUMN isolates by running two SQL queries; it is structurally blind
to whether the APP uses that column, and a route still filtering on `userId`
leaves it completely green. So 34 drives a browser through a real session:

- **NEW** — alpha-2 opens a visit authored by alpha-1 → the note renders.
- **UNCHANGED** — beta-1 opens the same visit → refused.
- **NOT WIDENED** — the personal data export stays author-scoped.

The first alone passes on a route that dropped tenancy entirely, and **fails
open**. The second alone passes on the pre-T5 code. Only the pair separates "the
wall moved to the practice boundary" from "the wall is gone".

⚠️ **The QA stack was running an image built 2026-08-05 — genuinely pre-T5** — so
rather than mutate source to manufacture a red, the pair ran against THAT image:
NEW ✘ ("alpha-2 got a not-found for a colleague's visit"), UNCHANGED ✓, NOT
WIDENED ✓. Then 3/3 against a build of this branch. The transition is
attributable to the code and nothing else.

#### Branded ids — the closing hardening

`PracticeId` / `UserId`, minted only at `getSession()`. `loadVisitExportData`'s
second parameter was renamed `userId` → `practiceId` in tranche 1b and **nine
call sites kept passing a user id**, silent through `tsc`, because both are
`string`. It is now `Argument of type 'UserId' is not assignable to parameter of
type 'PracticeId'`.

The **argument-shape source guard is RETIRED with a note in place** — the type
checker carries that guarantee on every call now, and a source rule duplicating
the type checker is noise. Replaced, not deleted, by a **cast ban**: a brand
cannot see `userId as PracticeId`, so casts are confined to the session boundary
and to the runtime guard's own forced-value proof.

The runtime `requirePractice` **stays**: `{ practiceId: undefined }` is `{}` to
Prisma — **every tenant** — and that is the one failure here that is silent and
WIDER. A brand stops honest callers, not an `as any`.

### ▶ T6 — roles, and the sign gate that refuses — **OPEN, next**
OWNER / CLINICIAN / TECH. The sign gate is server-side and fail-closed: an
unrecognised or absent role refuses.
**Gate:** a TECH member's `POST /sign` is **refused by the route** — proven with
a direct request, not by a hidden button — and the refusal writes an audit row.
This is the R1 lesson: a gate nothing enforces is one path away from not
existing.

**Scope, as ruled 2026-08-06 — four things, not one:**

1. **The roles model**, and **invites carrying practice + role**.
2. **The sign gate refusing TECH by name**, server-side. Named, not 404'd:
   "you may not sign" and "this does not exist" are different facts and a
   clinician deserves the true one (§4.1a).
3. ⚠️ **REMOVE THE AUTHOR CONJUNCTS — this is T6's, by ruling §4.1c.** T5 widened
   READS and deliberately left every ACTION carrying `userId: session.user.id`
   beside its new practice predicate, because with no role column consulted at a
   write path the alternatives were to widen writes with nothing distinguishing
   a TECH from a CLINICIAN, or to ship nothing. **The conjunct is a placeholder
   standing exactly where the role check goes.** The list is not kept by memory:
   it is every write path carrying `userId: session.user.id` **beside** a
   `visitScope`/`visitByIdScope` call, which is greppable precisely because the
   two appear together.

   Why this is written down rather than discovered: a later reader finding a
   practice-scoped read next to an author-scoped write concludes the write was
   MISSED, widens it, and arrives at §4.1a's end state with none of §4.1a's
   refusals. **A conservatism nobody recorded is indistinguishable from an
   oversight, and gets "fixed".**
4. **T4's positive gate finally runs through the real route** — a non-owner
   member signs and `signedBy ≠ createdBy` — flipping **T4 PARTIAL → CLOSED**.
   The T1 fixture gains roles here, so its second member is a CLINICIAN, which
   is what makes that gate passable at all.

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

### ✅ TEAMS EXIT GATE — ALL FOUR ROWS RULED, 2026-08-05

Written before any migration runs, which is the point of the gate.

#### 1. `worker.ts:983` read-after-write — ⚠️ RACE CONFIRMED BY CONSTRUCTION

Phase 0 left this UNSURE and said so. It is no longer unsure, and the answer did
not need a reproduction:

    packages/ai/src/log.ts:33
      export function logAiCall(input: AiCallLogInput): void {
        void prisma.aiCall.create({ … }).catch(…);
      }

The function returns `void` **synchronously** and discards the promise. There is
no flush, no drain, no queue — `grep` for one across `log.ts`/`index.ts` returns
nothing, so a caller has no way to wait for outstanding writes. `worker.ts:983`
then does `prisma.aiCall.findMany({ where: { visitId } })` and sums.

**There is no happens-before edge between the last write and that read.** So the
question was never "can it race" — by construction it can. Asking for a
reproduction would have been asking how OFTEN, which is a different question and
a much weaker one: a race that reproduces rarely is still a race.

**Impact today: none that matters.** The code's own comment is correct — "the
cost number is observability, not load-bearing for correctness" — and the L7
fan-out takes seconds, so all but the last writer have almost certainly landed.

⚠️ **IT STOPS BEING OBSERVABILITY WHEN BILLING LANDS.** B6 makes this number the
input to `charge = cost_micro × 3 / 2`. An undercounting sum then becomes an
undercharge — silent, unbounded, and invisible because the number still looks
plausible. **VERDICT: accepted for now, ASSIGNED to BILLING B1/B4**, which must
either await the writes or accumulate the cost in memory rather than re-reading
the table it just wrote. Not deferred silently; deferred to the item where it
first matters.

#### 2. `practiceIdSnapshot` backfill — ✅ DONE

⚠️ **THE COUNT WAS 44, NOT 38.** DISCOVERY §B.8's 38 was the *resolvable*
subset; six more rows have no practice on their user either and cannot be
backfilled from anything.

**Applied:** 38 rows, one transaction, guarded — expected count pinned inside the
transaction, `GET DIAGNOSTICS ROW_COUNT` compared to it, and a post-check that
zero remain, with `RAISE EXCEPTION` on either mismatch. Total row count
unchanged at 10500. All 38 belonged to a single **QA Audit Practice**, not a
clinician's.

⚠️ **WHY THIS IS NOT A BREACH OF APPEND-ONLY, stated because it looks like one.**
The rule protects what a row SAYS HAPPENED — action, actor, time, target.
`practiceIdSnapshot` is none of those: it is a denormalised copy of `practiceId`,
which the row **already carries**, added by S4c so the value survives the FK
being detached at deletion. Copying it from the row's own authoritative field
asserts nothing new and changes no claim.

Contrast with the audit-attribution repair of 2026-08-04, where the stored
`practiceId` was itself WRONG (`?? 'clinic_main'`): fixing that in place would
have changed what the row claimed, so correction records were the only honest
route. **The test is whether the edit changes a claim, not whether it changes a
byte.**

The 6 unresolvable rows are left NULL. Inventing a tenant for them would be the
breach this paragraph rules out.

#### 3. `audit_logs` as an S4c exclusion — ⏭ CARRIED AS A REQUIREMENT ON T5/T7

Nothing to do yet: the fail-closed "no clinical row without `practiceId`" rule
does not exist. **The requirement is recorded here so the commit that writes it
cannot omit it** — `audit_logs` must be named BY NAME as an exclusion, with the
S4c reasoning cited inline, because a future tidy-up that "fixes" the nullable
`practiceId` re-breaks account deletion: the deletion path depends on the FK
being SET NULL while `practiceIdSnapshot` preserves the tenant
(`delete-account/route.ts:126-134`).

#### 4. The 12 `MEDDOC_PRO`-only accounts — ✅ VETO LAPSED, OWNER CONFIRMED 2026-08-05

**The owner was asked and answered in writing before this row was written.**
Verdict: *lapsed — deactivate all 12.* GATE 0's ruling stands: excluded from
backfill, login disabled, rows retained, **no deletion**.

⚠️ **SPEC §4.1 IS IMPRECISE AND IS CORRECTED HERE.** It says "Four of the twelve
are on `@meddoc.com` carrying the operator's own name." Measured, **three** are —
`kash@`, `kasra@`, `kas@meddoc.com`. The likely fourth, `doctor@meddoc.local`, is
on a **different domain** and carries a **different person's name**, "Dr.
Bakhtiar Moussazadeh". That distinction was surfaced to the owner before the
question was put, because deactivating your own test accounts and deactivating
one bearing a named clinician are not the same decision.

Also measured: **all 12 own zero clinical rows**, so deactivation costs nothing
clinically and remains reversible — which is what made the window meaningful.

**T7 may now exclude these rows.** The veto is closed.

---

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
