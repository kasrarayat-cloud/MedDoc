# FOUNDATION — the relay ledger

**This ledger is the contract between sessions.** `SPEC.md` says what to build;
`DISCOVERY.md` says what is true today; this says what order, with what proof.

---

> ⚠️ **RULINGS INDEX: `docs/foundation/RULINGS.md`** — every war-room decision as
> one line with a pointer to its full text. **Grep it before deciding anything
> ruling-shaped.** New rulings append there in the same commit that records them.

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

### T2 — close the audit fail-open — ✅ **FULLY DONE 2026-08-04** (code AND repair)
The code half shipped ahead of TEAMS as part of the security block:
`?? 'clinic_main'` is gone, `signOut` threads the practice by traversal,
`gate-audit-attribution-failclosed` is proven red against four mutations, and
`AUDIT_ATTRIBUTION_CORRECTED` shipped **with its Prisma migration**.

⚠️ **THE REPAIR HAS ALREADY RUN. THIS SECTION SAID OTHERWISE FOR THREE DAYS AND
WAS WRONG — CORRECTED 2026-08-07 AGAINST THE DATABASE.**

It read *"Still to run, deliberately not run yet: `npx tsx
scripts/repair-audit-attribution.ts --apply`"*. Measured on production:

    AUDIT_ATTRIBUTION_CORRECTED rows ......... 71
    all written .............................. 2026-08-04
    distinct targetIds ....................... 71   (one per wrong row)
    originals still carrying 'clinic_main' ... 65   ← append-only honoured

Those figures match the SECURITY BLOCK ledger row exactly — *"71 corrections
APPENDED (65+6), originals still 65 and still wrong"*. **The repair ran the same
day this paragraph claimed it was being held**, as part of A.3; the section was
written before that and never updated.

⚠️ **AND THE COST OF BELIEVING IT WOULD HAVE BEEN REAL.** A session inheriting
"still to run" re-runs the script — and because it **appends** rather than
updates, a second run does not no-op. It writes **71 duplicate corrections**
against rows that are already corrected, permanently, into the one table whose
value is that it can be trusted. The append-only property that makes the repair
safe to run *once* is exactly what makes it unsafe to run *twice*.

> **A ledger row and a section that disagree are not a formatting problem. One
> of them is telling a future session to do something to production.** The
> database settles it; neither document does.

Still owed in TEAMS proper — **both since discharged**: the `practiceIdSnapshot`
backfill (done, see the exit gate §2) and naming `audit_logs` as an S4c
exclusion (done by **T7**, SPEC §1.5, which names all three exclusions with
their reasons).

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

### ✅ T4 — createdBy / signedBy — **CLOSED 2026-08-07**

**Both halves of the gate now run.**

- **NEGATIVE** — `33-visit-attribution.spec.ts`: a signature without a signer is
  refused by `transcribe_visits_signed_requires_signer`, with a positive control
  proving the constraint discriminates on signed-ness rather than rejecting
  every write. Landed 2026-08-06.
- **POSITIVE** — `35-sign-role-gate.spec.ts`: **a CLINICIAN signs a COLLEAGUE's
  unsigned visit through the real route, 200, and `signedBy ≠ createdBy`.**

⚠️ **THE POSITIVE HALF WAS BLOCKED FOR A REASON, AND THE REASON WAS DISCHARGED
RATHER THAN WAIVED.** T4 was declared PARTIAL on 2026-08-06 because proving
attribution needs a NON-AUTHOR to sign through the route — *"simulating it with
a direct UPDATE would prove the columns CAN differ and say nothing about whether
the ROUTE stamps the right person."* That required T5's practice-scoped read
(so the colleague can reach the visit at all) and T6's role model (so a
non-author is permitted to sign). Both landed; the gate passes.

Production could never have demonstrated it: all 16 signed visits have
signer == author, which is not evidence the attribution works — it is evidence
the data has never exercised it.

**Citation:** PR #533, merge `94ed44b7`, deployed from `main@00673b51` with a
full four-workflow citation (`CI` 31138836546 · `e2e` 31138836535 · `a11y-ci`
31138836556 · `secrets-scan` 31138836526).

### T4 (superseded) — the PARTIAL row

⚠️ **THE POSITIVE GATE NOW RUNS AND PASSES.** T6's fixture gave alpha-2 a
CLINICIAN role and `35-sign-role-gate.spec.ts` drives the REAL route: a
non-author signs a colleague's unsigned visit, 200, and `signedBy ≠ createdBy` —
which production's 26 visits could never have demonstrated, since signer equals
author in all 16 signed rows.

T4 stays PARTIAL in this ledger only until T6 lands on `main`; the blocker itself
is discharged. The original text follows.

### ⏸ T4 (original) — createdBy / signedBy — **PARTIAL 2026-08-06. Blocked as a DEPENDENCY.**

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

#### ✅ TRANCHE 2 EXECUTES GATE 0.3 — ratified 2026-08-06

`note_templates` stay **doctor-scoped**. A template is the doctor's own note
FORMAT, not clinical data about a patient; widening it would put a colleague's
formats in your template picker and list them as yours in Settings.

And there is **no tenancy hole to close**: `doctorId = session.user.id` is
STRICTLY NARROWER than a practice predicate, so no cross-practice template read
is reachable. Migrating them would WIDEN them. All 12 sites were traced to the
session before being declared.

⚠️ **AND IT WAS ALREADY THE STANDING RULING — I RE-DERIVED IT INSTEAD OF CITING
IT.** GATE 0.3 decided this on 2026-08-04, recorded verbatim at **SPEC §4.3**:
*"PER-DOCTOR in TEAMS v1 (solo behavior unchanged); practice-shared library
recorded as a post-TEAMS flag item."* The tranche-2 verdict is that ruling being
**executed**, not a new decision, and it reached the same answer by the same
reasoning — which is reassuring about the reasoning and says nothing good about
the process. **Read the standing rulings before deciding what a tranche should
do; a ruling that has to be rediscovered is a ruling that can be contradicted.**

Consistent with **T7**, which carves `note_templates` out as "the platform-global
carve-out", and with §4.3's own note that the unique index on
`("doctorId","encounterType")` stays as it is.

**The practice-shared template library remains the named post-TEAMS, flag-gated
item — never a T5 side effect.** A clinic with one house format is a product
change with UI consequences, and it arrives through that item or not at all.

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

#### ⚠️ IN PRODUCTION THE WIDENING IS A NO-OP, BY CONSTRUCTION — measured 2026-08-06

The reads widened from author to practice. **No production user's visible set
changes**, and that is a fact about the data, not a hope:

    visits in a practice with MORE THAN ONE member ........  0
    visits in a practice with at least one member .........  26   ← positive control
    total visits .........................................  26

The second line is the control and it is not decoration: a query that traverses
nothing returns 0 for every predicate you try, so the `> 1` zero means nothing
without a `> 0` that returns everything. It does.

Every practice holding clinical data is SOLO. The three multi-member practices —
`clinic_main` (11), `qa-practice-audit` (5), `clinic_test_b` (2) — hold **zero
visits between them**. So "the practice's day" and "my day" are the same set for
every real user today, and the change is only observable on the T1 fixture.

That is a good deploy posture and a bad test posture, and it is exactly why T1
exists: **a scoping test over an empty practice passes for free.** Production
could never have proven this either way.

#### ⚠️ CARRIED — a stale fixture flag in a LONG-LIVED worker container

Found 2026-08-06 while verifying T5 locally. The default `chromium` pack came
back **6 failed**, all one symptom: *"clicked Review & sign but the gate flow
never presented the attestation"*.

Not the code. **`MOCK_RX_WARNINGS=true` was still set on the WORKER**, left from
an earlier flag-gated run. The worker is what emits the Rx drafts, so every visit
it processed carried a critical Warfarin interaction and the gate flow opened at
Gate 1 instead of the attestation. The app container was clean; only the worker
was contaminated, because a rebuild had recreated `transcribe-md` and left
`transcribe-md-worker` up for two days.

Three things worth carrying:

- **A partial `up -d` leaves half the stack on the previous invocation's env.**
  The flags come from the shell at `up` time, so recreating one service and not
  the other is enough to split the stack's configuration.
- **`check-qa-mock-posture.sh` does NOT catch this.** It asks whether QA can
  reach a vendor — `MOCK_AI_CALLS` plus credentials — and correctly reported
  green throughout. A leftover *fixture* flag is a different failure: it silently
  changes what the pack is testing, which is the "packs certifying a
  configuration that is not production" class from F-ret.
- **The exit code lied, again.** The run was piped through `tail -40`, so `$?`
  was `tail`'s and read 0 while the summary said `6 failed`. Count the ✓/✘
  marks; never trust a piped exit status.

After recreating the worker without the flag: the same 7 specs pass, and the full
default pack is **74 passed · 0 failed · 1 skipped**, marks counted.

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

### 🟩 T5 ADOPTION IS LIVE IN PRODUCTION — 2026-08-07T00:26Z

**`main@74ca2ef2`** (PR #532). Full four-workflow citation on the MERGE COMMIT:

| Workflow | Run | Result |
|---|---|---|
| `CI` | `31132137862` | ✅ success |
| `e2e` | `31132137861` | ✅ success |
| `a11y-ci` | `31132137976` | ✅ success |
| `secrets-scan` | `31132137898` | ✅ success |

Deployed with `scripts/deploy-prod.sh`; log at
`docs/deploy-logs/deploy-20260807T002618Z.log`. Rollback tags
**`:pre-t5adopt-20260806`** cut against the RUNNING image ids
(`ef2845ffb584` / `2bda2b058f26`) and verified to resolve to them — not to a tag
string.

#### THE POST-DEPLOY CHECK WAS A COMPARISON, AND THE DIFF IS TWO LINES

A baseline was captured BEFORE the deploy so the check could be a diff rather
than an assertion in isolation. The entire difference:

    -  transcribe-md         sha256:ef2845ffb584…
    -  transcribe-md-worker  sha256:2bda2b058f26…
    +  transcribe-md         sha256:221106902 46a…
    +  transcribe-md-worker  sha256:133036c0a08a…

**Nothing else moved.** Containers 9/9 identical, migrations 87/87 identical,
co-tenants identical (307/410/404/200), and the clinical counts byte-identical:

    26 visits · 15 patients · 16 signed · 10 539 audit rows

That last line is the point of the exercise. A code-only deploy that changed a
clinical count would be the finding, and the only way to know is to have written
the numbers down first.

Standing checks green: imaging E/M invariant (0 of 15), migrations asserted
87 in repo / 87 applied, both encrypted mounts.

#### ⚠️ `/board` RETURNS 200 UNAUTHENTICATED — PRE-EXISTING, NOT THIS DEPLOY

Found while verifying: `/board` answers **200** to an unauthenticated request
where `/visits` and `/patients` answer **307**. Investigated rather than waved
past, because a 200 on a clinical route is the right thing to be alarmed by.

- **No data is exposed.** 0 hits for `patientName`, `chiefComplaint` or any
  cuid-shaped id; the body is a shell carrying "Sign in".
- **The redirect DOES fire** — `NEXT_REDIRECT` is present in the RSC payload.
  The page streams, so the shell flushes before the guard throws and Next can no
  longer send a 307; the client performs the redirect instead.
- ⚠️ **ATTRIBUTED, NOT ASSUMED.** The pre-deploy image was started from the
  rollback tag on the compose network and probed: **`/board` 200, `/visits` 307**
  — identical. This predates T5 adoption and is not a regression.

Carried as an open cosmetic/architectural item, not a security one.

### ⚠️ #531's MERGE-COMMIT CITATION IS 2 OF 4 — a PLATFORM limitation, stated

`main@3f656fb3` (PR #531, T5's accessor + guard):

| Workflow | Merge-commit result |
|---|---|
| `CI` | ✅ **success** — run `31118255254` (incl. `unit tests`, `test`, `npm audit`, `dev-dep advisories`) |
| `a11y-ci` | ✅ **success** — run `31118255287` |
| `e2e` | ⚠️ **NEVER DISPATCHED** — run `31118255417`, `queued` since 16:00 UTC |
| `secrets-scan` | ⚠️ **NEVER DISPATCHED** — run `31118255265`, `queued` since 16:00 UTC |

**The two are zombie runs from the GitHub incident of 2026-08-06** (status page:
partial → major outage, ~16:00–23:00 UTC). They cannot be recovered: `gh run
cancel` reports *"Cannot cancel a workflow run that is completed"* while the run
list still reports `queued`, and `gh run rerun` reports *"cannot be rerun; its
workflow file may be broken"*. They will not complete and cannot be replaced on
that SHA.

**A PR-head green is NOT substituted for them**, per the standing rule.

What IS true, stated narrowly:

- `CI` — which carries the unit suite — **passed on the merge commit itself**.
- #531 changed **three files: `practice-scope.ts` (a new module NO runtime path
  imported), its unit test, and SPEC prose.** There is no code path an E2E or a
  secret scan could exercise differently, because there is no code path at all.
- **#532's merge commit CONTAINS #531's changes** and gets a full four-workflow
  run. That is a stronger statement than re-running #531's would have been: the
  same code, verified on a later merge commit, by workflows that actually
  dispatched.

### 🟩 T6 IS LIVE IN PRODUCTION — 2026-08-07T02:24Z

PR #533 → merge `94ed44b7`. Deployed from **`main@00673b51`**, which carries the
merge plus two docs files, with a full four-workflow citation on **the commit
that actually deployed**:

| Workflow | Run |
|---|---|
| `CI` | ✅ `31138836546` |
| `e2e` | ✅ `31138836535` |
| `a11y-ci` | ✅ `31138836556` |
| `secrets-scan` | ✅ `31138836526` |

Log `docs/deploy-logs/deploy-20260807T022441Z.log`; rollback tags
**`:pre-t6roles-20260807`**, digest-verified against the running ids.

#### THE EXPECTED DELTA WAS DECLARED FIRST, AND THE DIFF MATCHES IT EXACTLY

Declared before running (runbook §2.5): migrations 87 → 89 · `users.practiceRole`
0 → 1 · both image ids change · **clinical counts UNCHANGED**. The diff:

    image ids     22110690246a → 92bda14187f9 · 133036c0a08a → 61e81fa0c962
    migrations    87 → 89
    practiceRole  0 → 1
    (nothing else)

26 visits · 15 patients · 16 signed · 196 users — identical. Containers 9/9,
co-tenants 307/410/404/200.

#### THE THREE-LAYER VERIFICATION — the lesson checking itself

| Layer | Result |
|---|---|
| backfill | **196 OWNER**, 0 underivable (active + practice + no role) |
| constraint | `users_active_member_has_practice_role` **live** |
| ⚠️ **`pg_enum`** | **`SIGN_BLOCKED_ROLE_NOT_PERMITTED` present** |

The third row is the whole point. `schema.prisma` and the TS union both passed
on 2026-08-06 while the database enum was empty, and the refusal fired correctly
with a 403 while its audit row silently did not. **The database is the only layer
whose answer counts**, so it is the one that gets asked.

#### PRODUCTION HOLDS NO TECH USER, AND THAT IS CORRECT

Zero CLINICIAN and zero TECH rows: every prod user is the OWNER of their own
solo practice, exactly as the backfill intends. So the **behavioural**
three-direction proof lives in CI/QA where the TECH seat exists, and prod gets
**structural verification only — no mutation, no synthetic sign.** A role gate
cannot be exercised against a population that has only one role, and inventing
one in production to watch it refuse would be editing a live account to make a
test feel complete.

### T6 (superseded) — the BUILT row

Built on `feat/teams-t6-roles`, stacked on T5. **Merges only on top of #532**, per
the standing sequence — nothing here reaches `main` before the base it assumes.

| | |
|---|---|
| **`PracticeRole`** | new enum on `users.practiceRole`; `UserRole` marked do-not-extend |
| **Backfill** | active + has a practice → OWNER. ⚠️ the ruling's premise was measured FALSE; see below |
| **Constraint** | `users_active_member_has_practice_role`, proven by attempt + positive control |
| **Bypass** | `canBypassTenantScope` DELETED; `tenantScope` returns a REQUIRED practiceId |
| **Sign gate** | two branches — cross-practice 404, in-practice wrong role 403 by name |
| **Conjuncts** | 23 removed, 1 kept and declared |
| **Fixture** | alpha-1 OWNER · alpha-2 CLINICIAN · **alpha-3 TECH (new seat)** · beta-1 OWNER |
| **Gates** | `35-sign-role-gate.spec.ts` — positive, negative, unchanged. All green |

#### ⚠️ THE BACKFILL RULING'S PREMISE WAS FALSE — 18 of 196

The ruling reads *"every active user today is the sole member of their personal
practice."* Measured on production:

    active 196 · sole member 178 · in a MULTI-MEMBER practice 18 · no practice 0

Main Clinic 11 · QA Audit Practice 5 · Test Clinic B 2. Taken literally those 18
derive NULL and trip the constraint — the migration aborts, correctly and
uselessly. **Stated rule: they take OWNER too, because a migration must not
DOWNGRADE anybody.** Every member can do everything today; deriving CLINICIAN or
TECH removes a capability on a hierarchy nobody stated, and the schema records no
designation to derive one from. All three hold ZERO visits and ZERO patients
(positive-controlled against the two that do hold data).

#### PRE-DEPLOY DRY-RUN AGAINST PRODUCTION — read-only, 2026-08-06

The migration's own predicates, evaluated against prod before it ever runs there:

    would become OWNER (active + has a practice) ....... 196
    stays NULL — deactivated ...........................   0
    stays NULL — no practice ...........................   0
    total users ........................................ 196

196 + 0 + 0 = 196, so **no row is underivable and the abort guard will not
fire**. Every production user takes OWNER of their own practice, which is what
the ruling intends and what the structure supports — with the 18 multi-member
rows covered by the stated no-downgrade rule rather than by the premise.

`SIGN_BLOCKED_ROLE_NOT_PERMITTED` is absent from prod's `AuditAction` enum (0),
so the second migration has work to do and is not a no-op.

#### ⚠️ THE AUDIT-ROW FAILURE, A THIRD TIME — and the narrower lesson

Adding `SIGN_BLOCKED_ROLE_NOT_PERMITTED`:

1. landed in `audit.ts` only — the schema anchor missed on indentation; caught by
   an occurrence assertion.
2. landed in `audit.ts` **and** `schema.prisma` — and still not in the DATABASE,
   because a Prisma enum **value** needs its own migration. `prisma validate`,
   `tsc` and 3192 unit tests all passed while the refusal fired correctly with a
   403 and its audit row silently did not.

The only thing that caught (2) was the E2E **reading the row back**. The app
logged `invalid input value for enum "AuditAction"` and swallowed it, because
`logAudit` is deliberately fire-and-forget so an audit failure cannot break a
clinical action.

> **A FIRE-AND-FORGET WRITER MEANS THE ONLY PROOF AN AUDIT ROW EXISTS IS A TEST
> THAT READS IT BACK.** Every gate that claims "and the refusal is audited" needs
> that assertion, or the claim is a comment.

#### ⚠️ PRODUCTION SIGNUP WOULD HAVE BROKEN — the T3 shape again

The CHECK makes a role required for an active member. `src/actions/auth.ts:502`
did not set one, so **every new signup would have failed on the first request
after deploy**, with a constraint error naming the CHECK rather than the missing
column. Swept all **9** user create/upsert sites by ORM method AND by raw SQL
(none); all 9 now set a role wherever they set a practice.

#### ⚠️ CARRIED OUT OF T6 — clinical WRITES are not accessor-scoped

SPEC §1.4 says *"every read **and write** of a clinical table goes through it"*.
T5's guard watched READS ONLY, so its ratchet reached zero over half the named
surface — the coverage-vs-criteria class, second instance in one day.

**Measured: 25 request-context clinical writes carry no practice predicate.**
**No leak is open** — every one is reached only after a practice-scoped read in
the same handler — but they lack a predicate of their OWN, the "borrowed
authorisation" shape T5 itself argued against, one refactor from being wrong.

A **write ratchet at 25** lands with T6 so the class cannot grow. Scoping the 25
is its own item, and it is not T6's. Two were fixed in T6 because they had no
practice predicate AND lost their author one (`rescore-em`'s updateManys would
have become id-only writes).

### T6 (original wording) — roles, and the sign gate that refuses
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
#### 📐 T6 RECONNAISSANCE — measured 2026-08-06, READ-ONLY, before any code

Measured the way T5's 101-site table was, and like that one it **changes the
build order**. Four findings; the first is a war-room question, not a session
one.

##### ⚠️ 1. THE ROLE ENUM ALREADY EXISTS, AND IT IS A DIFFERENT VOCABULARY

`UserRole` is **`DOCTOR / STAFF / ADMIN / SUPER_ADMIN`**. T6's spec says
**`OWNER / CLINICIAN / TECH`**. These are not the same axis: the existing enum
mixes a *clinical* distinction (DOCTOR vs STAFF) with a *platform-privilege* one
(ADMIN, SUPER_ADMIN — the latter explicitly documented as bypassing tenant
scoping).

    production   DOCTOR 190 · ADMIN 3 · SUPER_ADMIN 2 · STAFF 1   (196, all active)
    source       41 sites read UserRole / compare a role
    schema       @default(STAFF), indexed, on `users`

⚠️ **AND THIS IS A SPEC-vs-DISCOVERY CONFLICT, WHICH THE SPEC HEADER SAYS IS A
FINDING, NOT A TYPO.** SPEC §1.2 named the three roles in Phase 0 — *"Three
roles: OWNER, CLINICIAN, TECH"* — and DISCOVERY recorded the existing gate as
*"an RBAC role, not a platform entitlement"* (§132). **Neither document was ever
diffed against the other**, so the contract has said one vocabulary and the
database another since 2026-08-04, and the first person to notice is the one
who has to build against both. That is the watched-set / named-set class again,
one level up: at the DOCUMENT layer rather than inside a check.

**This is ruling-shaped and is NOT decided here.** Three options, with the
consequence of each:

| | what it means | cost |
|---|---|---|
| **MAP** onto the existing enum | DOCTOR→CLINICIAN, STAFF→TECH, ADMIN→OWNER | no migration; but SUPER_ADMIN has no TEAMS meaning and ADMIN currently means *practice-scoped platform admin*, not *practice owner* |
| **ADD** a second column | `practiceRole` beside `role` | two role systems to keep consistent — the shape that rots |
| **REPLACE** the enum | one vocabulary | a migration over 196 live rows and 41 read sites, and `SUPER_ADMIN`'s tenant-bypass must survive it |

⚠️ **`SUPER_ADMIN` bypasses tenant scoping by design.** Whatever is chosen must
say what happens to that bypass under a practice-role model, because T5 just made
every clinical read practice-scoped and 2 live accounts are documented as
crossing that boundary. That interaction is not optional to answer.

##### ⚠️ 2. §4.1c's STATED GREP IS INCOMPLETE — 24 SITES, NOT 5

§4.1c says the conjunct list "is every write path carrying `userId:
session.user.id` **beside** a `visitScope`/`visitByIdScope` call, which is
greppable precisely because the two appear together."

**That finds 5. There are 24.** The author gate has TWO shapes:

    IN-QUERY CONJUNCT   `...visitByIdScope(…), userId: session.user.id`      5
    POST-FETCH CHECK    `if (!visit || visit.userId !== userId) → 404`      19

I wrote that ruling, and it is **the same defect AGENTS.md already names: naming
a class is not enumerating it.** The defining predicate is *"every place
authorship gates an action"*, and it must be swept by BEHAVIOUR, not by the one
syntax I happened to picture. §4.1c is corrected accordingly — the count and both
shapes are now stated there.

⚠️ **The first sweep returned 25 and one was a FALSE POSITIVE — it matched my own
comment** in `visits/[id]/page.tsx` explaining that the check had been removed.
Re-run with comment stripping and positive controls in both directions (real
code matches, commented-out code does not): **24**.

##### 3. THERE IS NO MEMBERSHIP TABLE — one user, one practice

`User.practiceId` is a single FK. There is no join table, so "membership" is a
column, and a user cannot belong to two practices. **T6 does not need to build a
membership model**; it needs a role on the existing edge.

Signup creates practice + user together in one transaction
(`actions/auth.ts:493-502`, `name: 'Solo — …'`). That is the single write site
where a new member's practice and role are decided.

`InviteCode` today carries **neither practice nor role** — `codeHash`, `label`,
`maxUses`, `usedCount`, `expiresAt`, `revokedAt`. Consumed at
`lib/signup-invite.ts` (1 read + 1 transactional `updateMany`). **T8's "invites
carry practice + role" is therefore two nullable columns and one branch in the
signup transaction** — small, and it is the piece that makes a second seat
reachable without an operator writing SQL.

##### ⚠️ 4. THE T1 FIXTURE SEEDS EVERY MEMBER AS `STAFF`

`upsertMember` never sets `role`, so all three take the schema default.

    t1-alpha-1  STAFF      t1-alpha-2  STAFF      t1-beta-1  STAFF

**T4's positive gate — a non-owner member signs, `signedBy ≠ createdBy` — cannot
pass against this fixture even after T6 lands**, because under §4.1a a
non-clinical role is refused by name. The fixture must gain roles in the same
change as the gate, with alpha-2 a CLINICIAN, or T4 stays PARTIAL for a reason
that has nothing to do with T4.

##### The sign gate's insertion point

`src/app/api/visits/[id]/sign/route.ts:209` —
`if (!visit || visit.userId !== userId) return apiError('not found', 404);`

That single line is both the author conjunct §4.1c retires **and** the place the
role refusal goes. ⚠️ They are not interchangeable: the author check 404s (correct
for enumeration resistance), and §4.1a requires TECH to be **refused by name**,
not 404'd — *"you may not sign" and "this does not exist" are different facts and
a clinician deserves the true one.* So the replacement is two branches, not one:
practice-scope miss → 404; in-practice but wrong role → a named refusal with an
audit row.

##### PROPOSED BUILD ORDER, changed by the above

1. **The vocabulary ruling** — blocking, war-room. Nothing else can be built
   against a role model whose names are undecided.
2. Role on the user edge + the T1 fixture seeding roles (same change — see 4).
3. The sign gate: two branches, TECH refused by name, audit row.
4. T4's positive gate through the real route → **T4 PARTIAL → CLOSED**.
5. Author-conjunct removal across **24** sites, swept by behaviour (see 2).
6. T8's invite columns + the signup branch.

4. **T4's positive gate finally runs through the real route** — a non-owner
   member signs and `signedBy ≠ createdBy` — flipping **T4 PARTIAL → CLOSED**.
   The T1 fixture gains roles here, so its second member is a CLINICIAN, which
   is what makes that gate passable at all.

### ▶ T5-W — the write-scope debt — **ORDERED, immediately after T6 lands**

The 25 request-context clinical WRITES adopt the accessor **exactly as the reads
did**. This is T5's other half, not a polish item: SPEC §1.4 names *"every read
**and write** of a clinical table"*, and T5's guard watched reads only.

⚠️ **PRIORITY, RECORDED AS RULED: a cross-practice WRITE MUTATES ANOTHER
TENANT'S CHART.** A leaked read is a disclosure; a leaked write is a false entry
in someone else's medical record, and it is the kind of error that is discovered
by a clinician reading a note that says something they did not write. **This does
not linger behind BILLING.**

**No leak is open today** — every one of the 25 is reached only after a
practice-scoped read in the same handler. What they lack is a predicate of their
OWN: the "borrowed authorisation" shape T5 itself argued against, one refactor
from being wrong. The write ratchet at **25** ships with T6 so the class cannot
grow while this is outstanding.

The shape, mirroring T5 exactly:

1. **BY-TABLE TRANCHES.** `transcribe_visits` first, then `note_templates`, then
   `transcribe_md_patients` — same order, same reasoning.
2. **The ratchet is lowered in the SAME COMMIT as the code.** The number in the
   guard and the number in the codebase never disagree. 25 → 0.
3. **The flip to a wall is its own cited event**, as the read side's was.
4. **ATTEMPT-PROOFS IN BOTH DIRECTIONS**, per tranche: a cross-practice write is
   REFUSED, and a same-practice write SUCCEEDS. The second half is not optional —
   without it a predicate that matches nothing would pass the first.
5. **TRANSACTIONAL, per canon.** Every write a gate is supposed to refuse runs
   inside `BEGIN … ROLLBACK`, so the attempt is observable and never
   consequential — the rule earned on 2026-08-05 when a mutation proof nulled 21
   signers.

#### 📐 T5-W RECONNAISSANCE — measured 2026-08-07, READ-ONLY

    25 unscoped clinical writes
      by model   transcribeVisit 19 · noteTemplate 4 · transcribeMdPatient 2
      by method  update 18 · updateMany 6 · deleteMany 1

⚠️ **THE STRUCTURAL OBSTACLE, AND IT IS THE WRITE-SIDE TWIN OF T5's.** Eighteen
are `update({ where: { id } })`, and **Prisma's `update` requires a UNIQUE
where** — a `practiceId` conjunct cannot simply be added, exactly as `findUnique`
could not carry one on the read side. There the answer was `findUnique →
findFirst`. Here it is `update → updateMany`, which is **not a free swap**:
`updateMany` returns `{ count }` instead of the row.

So the 18 split, and the split decides the work:

| | count | treatment |
|---|---|---|
| `update`, return **discarded** | **15** | mechanical → `updateMany` + the predicate |
| `update`, return **USED** | **3** | `updateMany` + an explicit re-read, or keep `update` behind a verified-scoped read and say so |
| `updateMany` already | 6 | add the predicate; no shape change |
| `deleteMany` | 1 | add the predicate |

The three that use their row: `api/patients/[id]/route.ts:216`,
`api/visits/[id]/route.ts:313`, `actions/soap.ts:191` — all assign to `updated`
and read it afterwards.

⚠️ **PRE-AUTHORIZED 2026-08-07 — EITHER TREATMENT, PER SITE, DECLARED IN THE
COMMIT.** Each of the three may take:

- **`updateMany` + a re-read INSIDE THE SAME TRANSACTION** — the re-read must be
  transactional or it reintroduces the read-after-write window the `updateMany`
  was chosen to close, and `soap.ts` already carries an optimistic
  `soapVersion` guard whose whole purpose is that window; or
- **a STATED EXCEPTION** — keep `update`, with the reasoning in place: the write
  is preceded by a practice-scoped read of the same id in the same handler, and
  that fact is what authorises it.

The exception is legitimate and it is also exactly the "borrowed authorisation"
shape this unit exists to retire, so **an exception must say why the borrowing is
sound HERE**, not merely that it is convenient. Site by site, in the commit, not
as a blanket policy.

One write is not by id at all: `update-visit-header.ts:153` is a BULK
`updateMany` over `{ patientId, signedAt: null }` — a rename spreading across a
patient's unsigned visits. It has no id to be unique on and is the clearest case
for the accessor.

⚠️ **THE COUNT-0 TRAP GOVERNS ALL 25 — ruled 2026-08-07.** A scoped `updateMany`
whose predicate matches nothing returns `{ count: 0 }` — no error, no exception —
and several call sites already treat `count === 0` as *"a concurrent write won"*.
**A wrong predicate would therefore wear the benign-race costume**, and the
symptom is a save that silently does nothing on a chart the user can see.

> **EVERY converted site's attempt-proof includes the POSITIVE direction.** Not
> the refusing tranche's — every site's. A refusal-only proof is satisfied by a
> predicate that matches nothing, which is the failure it was meant to exclude.

This is the same defect family as a vacuous assertion, arriving through a
runtime API rather than a test: `{ count: 0 }` is a *successful call* that did
nothing.

### ✅ T5-W — the write-scope debt — **CLOSED 2026-08-07**

SPEC §1.4 names *"every read **and write** of a clinical table"*. T5's guard
watched reads only, so its wall reached zero over half the named surface — the
coverage-vs-criteria class, found by re-reading the criteria rather than by any
check.

#### THE LEDGER — each step lowered in the SAME COMMIT as the code

| | count | what happened |
|---|---|---|
| T5-W opens | **25** | the gap the read guard never watched |
| tranche 1a | **12** | 13 mechanical `update`→`updateMany` via `scopedUpdate` |
| classifier | **9** | doctor-scope LEARNED as a sanctioned narrower scope |
| return-row | **6** | the 3 sites take transactional re-reads |
| the rest | **0** | optimistic-concurrency sites + the last two template writes |
| **the flip** | **wall** | its own commit, `23b2168e` |

#### ⚠️ NO LEAK WAS EVER OPEN — the honest framing, recorded verbatim

> **Every one of the 25 was reached only after a practice-scoped read in the same
> handler. What they lacked was a predicate of their OWN: the borrowed
> authorisation T5 argued against, one refactor from being wrong. This unit
> removed the borrowing; it did not close an active hole, and the difference
> matters when someone reads this ledger later.**

#### ⚠️ DOCTOR-SCOPE IS A RULING, NOT A FOOTNOTE — recorded verbatim

> **Doctor-scoped writes count as SCOPED because `doctorId` is strictly narrower
> than a practice predicate — a ruling about what the scope MEANS (GATE 0.3), not
> a footnote excusing what the guard misses. `userId` is explicitly NOT accepted,
> with a control proving it, because that is ownership wearing tenancy's
> clothes.**

The zero is therefore genuine, with no carried-exception bucket holding the
residue. **A zero that needs a caveat is not a wall.**

#### THE WALL BITES — proof, recorded verbatim

> **A single unscoped `prisma.transcribeVisit.update({ where: { id }, … })`
> dropped into `src/lib/` reds it: `went UP (1 > 0)`. Removed; 15 passed. That is
> the mutation that matters at zero — every earlier tranche proved the ratchet
> could MOVE; this proves the wall can BITE, which is a different question and
> the only one still open once the number stops falling.**

#### What the tranches found

- **`update` → `updateMany` DELETES AN ERROR SIGNAL.** `update` throws P2025 on a
  miss; `updateMany` returns `{ count: 0 }`. `scopedUpdate()` restores it — a
  function, not a convention, because a convention here is a hand-kept list
  across thirteen sites. It takes the PREDICATE, not an id plus a practice: the
  three models do not share a scoping shape.
- **Two sites already HELD the tenant and did not apply it.**
  `em-coding/seed-baseline.ts` took `ctx.practiceId` and used it only for the
  audit row; `visits/[id]/page.tsx` had `sessionPracticeId` in scope and handed
  it to `computeEmScore` two lines above the unscoped write.
- **`certify.ts`'s unscoped fallback was DELETED, not scoped.** Its second branch
  wrote by id alone and was unreachable because every caller supplies `doctorId`
  — and **an unreachable unscoped write is one refactor from reachable.**
- **The bulk rename** (`update-visit-header.ts`) spreads across every unsigned
  visit for a patient, with no id to be unique on: the site where a missing
  predicate would have touched the most rows.
- **The POSITIVE half of the attempt-proof caught a bad fixture on first run** —
  `archive` refuses a non-signed visit. A refusal-only proof would have been
  green against that fixture, and would have stayed green if the predicate
  matched nothing at all.

### 🟩 F-TYPE + AUTH OBSERVABILITY ARE LIVE IN PRODUCTION — 2026-08-08T01:08Z

Deploy (c) from **`main@a2a0ee0c`** — #543 (F-TYPE) · #544 (auth observability)
· #545 (nanoid HIGH advisory) · #546 (BILLING recon). Code-only, no migration.
Full four-workflow citation on the deploying commit: `CI 31230015630` ·
`e2e 31230015647` · `a11y-ci 31230015621` · `secrets-scan 31230015622`. Log
`docs/deploy-logs/deploy-20260808T010802Z.log`; rollback
**`:pre-ftype-20260808`**, digest-verified against the running ids and
negative-controlled.

The whole diff was two image ids (`11791f54c3f8 → df8b00ba5a0e`,
`02d06a803137 → bfbf9c2497c1`) and two uptimes. Migrations 91 — **asserted, not
read off "no pending"**. Clinical **26 · 15 · 16 · 197**, users **196 / active
184**, co-tenants `307/404/200/200/410`, all four SNI issuers Caddy Local
Authority. Standing checks green.

#### ⚠️ THE WAR ROOM'S DECLARED PREMISE WAS FALSE, AND §2.5 IS WHAT CAUGHT IT

Recorded here as visibly as the `@@unique` premise was, because it is the same
class: **an instruction that was reasonable, specific, and wrong about the
system.**

The brief said to declare *"DATE OF PROCEDURE populates on newly generated notes
from this deploy forward."* Measured **before** running:

    template_twin_certifications      prod 0   ·   QA 10
    template_twin_compiled_versions   prod 0   ·   QA 45

`worker.ts`'s `visitDate` feeds **only** the Template Twin fill step, and
`template-twin-fill-step.ts:80` returns `skipped / not_certified_twin` before any
fill. Every production visit takes that branch, by the documented parked state —
there is no door in. **So the deploy changes no production document at all.** The
fix is LATENT until a twin is certified, which is a separate parked decision.

Declaring "the date now populates" and verifying it on QA would have produced a
green tick and a false sentence about the environment the declaration was about.
**Declaring first is what made the premise checkable at all** — after the fact,
"we verified it on QA" would have sounded like completion.

#### ⚠️ HOW TO READ `SESSION_FAILOPEN` — ENDORSED, AND BOTH INSTINCTS ARE WRONG

- **Seeing it is not a regression this deploy caused.** The fail-open behaviour is
  unchanged; it was previously SILENT. A line means it was already happening and
  nothing could see it.
- **Not seeing it proves nothing.** The first post-deploy window was **69
  seconds** with 0 lines — that means the database was healthy for 69 seconds.

> **The check reports a COUNT and its WINDOW. A zero is never reported as a
> result.** The grace-window ruling's retry budget is sized from the ACCUMULATED
> count, not from one quiet evening.

Positive-controlled: the same matcher finds `Ready in` in those logs, so the zero
is a real zero for that window and nothing wider.

### ✅ F-TYPE — type the shared Prisma client — **CLOSED 2026-08-07 · 42 → 0**

⚠️ **ONE PROOF REMAINS OPEN, AND IT IS NAMED RATHER THAN QUIETLY DROPPED.** The
DATE OF PROCEDURE fix is proven in the SHIPPED ARTIFACT with a negative control —
`createdAt: true` is present in the deployed worker and **absent from
`:pre-ftype-20260808`** — and the mechanism is traced end to end. What does not
yet exist is **a generated document showing the date**.

It cannot be produced in production (0 certifications, every visit short-circuits)
and it needs the by-hand twin flow on QA — upload → compile → fill → native
export. **OWED as its own bounded act**, run fresh: one document, the date
visible. This is the read-back canon applied to a document instead of a row, and
an artifact grep is not a substitute for it.

`packages/db/src/index.ts` is typed. `tsc -p apps/transcribe-md` reports **0
errors**; 3194 unit tests pass. **No `any`-casts, no `as unknown as`, no
`@ts-expect-error`** — verified by an adversarial pass over every diff.

#### 27 OF 42 WERE THREE DECISIONS, NOT 27 EDITS

| | n | the decision |
|---|---|---|
| `tx: typeof prisma` | **10 sites / 14 errors** | → `TransactionClient`, exported from `@meddoc/db` |
| `scopedUpdate`'s `model` param | **13 errors** | `{ where: unknown }` → **generic** |
| bare `null` into a Json column | **3** | → `Prisma.JsonNull`, measured on QA |

The middle one is worth stating: `unknown` is the TOP type, so under
`strictFunctionTypes` that parameter is CONTRAVARIANT and **no real Prisma
delegate is assignable to it**. The lazy fix is `args: any`, which restores the
silence everywhere. Making it generic instead means `where` and `data` are now
inferred from the delegate and **type-checked at all 13 call sites** — the
practice predicate and the update payload included.

#### ⚠️ TWO LATENT BUGS, BOTH INVISIBLE UNTIL THE CLIENT WAS TYPED

**1. `worker.ts` read a column it never selected — the DATE OF PROCEDURE was
always blank.** `visitDate: visit.createdAt` where the `findUnique` select never
requested `createdAt`. At runtime it was `undefined`; `visitDateToIso` returns
`null` for that on its first line; `withProcedureDateFact` is then a documented
no-op. **So every fill manifest the worker produced left the DATE OF PROCEDURE
control empty** — a feature written, wired, commented and never once fed. Nothing
threw, because every link in the chain is legitimately null-tolerant. The sibling
export paths (`visit-export-server.ts:148`, `pdf-native/export.ts:110`) pass a
real date, which is how we know the intent. Dormant in production today only
because the fill step short-circuits on `not_certified_twin`.

**2. `/patients` was the one clinical page with no `isActive` check.** Fixing the
three `PracticeId` brand errors there could not be done by casting — a brand is
minted only at `getSession()`, and `gate-practice-scope` bans the cast by name —
so the page now sources the practice from the mint point like every sibling
clinical page (`/board`, `/visits`, `/visits/[id]`, `/visits/new`,
`/visits/[id]/record`) already did. **That is a real authorization change, not a
type change**, and it is recorded as such: a deactivated user could previously
load the patient roster from this page. Every delta is fail-closed.

⚠️ **THE SECOND ONE WAS CAUGHT BY THE VERIFIER, NOT THE AUTHOR'S SUMMARY.** The
fix was reported as behaviour-changing, honestly — but its justification named
only legacy pre-T-M2 JWTs, while `validateSession()` also **fails open on DB
errors**, so the reachable set is wider than claimed. A behaviour change inside a
typing pass has to be named at its true width or it rides in as a type fix.

### F-TYPE (original wording) — type the shared Prisma client — **ORDERED: after TEAMS closes, BEFORE any BILLING build**

⚠️ **BILLING IS WALL-TO-WALL NEW PRISMA WRITES AND DOES NOT GET BUILT ON A
PLACEBO.** `packages/db/src/index.ts` declares `const prisma: any`, so **no
Prisma argument anywhere in this codebase is type-checked**. T7 proved the cost:
a change touching 15 write sites produced 2 tsc errors, and the one that mattered
(`logDelivery`, fire-and-forget) would have failed silently on every export.

#### 📐 RECONNAISSANCE — measured 2026-08-07, read-only

**The `any` is DELIBERATE, not accidental**, and that matters for the fix:

    const { PrismaClient } = require('@prisma/client') as { PrismaClient: any };

A CommonJS `require` with an explicit cast and two eslint-disables, carried in
by the monorepo refactor ("lifted verbatim from `apps/meddoc-pro/src/lib/db.ts`").
So F-TYPE's first job is finding **why** the `require` was needed — generated-client
resolution across the workspace boundary is the likely reason and must be
CONFIRMED, not assumed.

#### ✅ ANSWERED 2026-08-07 — THERE IS NO LIVE REASON. IT IS INHERITED.

The hypothesis was tested rather than reasoned about. A typed import placed
in-tree resolves and type-checks:

    import { PrismaClient } from '@prisma/client';
    c.transcribeVisit.create({ data: { __definitelyNotAField: 1 } })
    → error TS2353: … does not exist in type 'TranscribeVisitCreateInput'

**The positive control is the point**: the generated types are REAL, not a
permissive stub — a bogus field errors by name, while a legitimate
`findMany({ where: { practiceId } })` passes clean. CI already runs
`npm run db:generate` before every typecheck step (`test.yml:89`, `:302`, the
latter with a comment saying exactly why). So the `require` is a **legacy
artifact**, and the file's own header says so.

#### ⚠️ THE SURFACE WAS MEASURED WRONG — 42 ERRORS / 25 FILES, NOT 24 / ~12

Re-measured by typing the client and running `tsc -p apps/transcribe-md`:

    42 errors across 25 files
       patients/[id] 5 · worker.ts 3 · patients/page.tsx 3 · visits/[id] 3
       visits/[id]/delete 3 · patients/[id]/export 3 · stale-visits 2 · …

It also reaches **outside `apps/transcribe-md/src/`** — `packages/auth/src/user-session.ts`
and two `scripts/` files — which the original figure did not contemplate.

#### ⚠️ AND 42 ERRORS ARE NOT 42 DECISIONS. THE SHAPE DECIDES THE WORK.

| class | n | treatment |
|---|---|---|
| `$transaction(async (tx: typeof prisma) => …)` | **~16** | **ONE architectural fix** |
| `PracticeId` brand violations | 5 | READ EACH — possible real bugs |
| `StringFilter` reaching a scalar field | 4 | read each |
| bare `null` into a Json column | 3 | **likely real bugs** |
| misc (string→union, `string \| null`→`string`) | ~14 | annotations |

**The largest class is a single decision, and it is mis-diagnosed as sixteen.**
Typed, `typeof prisma` is the full `PrismaClient`, which is not assignable to
`Omit<PrismaClient, '$connect'|'$disconnect'|'$on'|'$use'|'$extends'>`. TypeScript
then falls back to the ARRAY overload of `$transaction` and infers `any[]` —
which is where *"'soapVersion' does not exist on type 'any[]'"* (`soap.ts:230`)
and *"'any[]' is not assignable to 'number'"* (`stale-visits.ts:78`) come from.
Those read like data-shape bugs and are not: **the runtime behaviour is already
correct.** ⚠️ **RULED: type the parameter as Prisma's own transaction-client
shape, everywhere, in ONE commit — never `typeof prisma`.**

⚠️ **THE `confidenceScores` NULL CLUSTER IS DECIDED ON QA, NOT BY REASONING.**
`worker.ts:332` and `:1094` write bare `null` to a Json column; Prisma's types
demand `Prisma.DbNull` (SQL NULL) or `Prisma.JsonNull` (JSON `null`), and the
two are different values with different query semantics. **Production data
cannot settle it** — measured, all 26 visits hold a real object, because the
reset at `:332` is always overwritten before processing ends, so there is no
surviving evidence of what a bare `null` lands as. Write it through the typed
client on QA and read back which of the two it produced, **then** choose. An
assumed answer here is a latent bug in either direction.

#### ✅ DETERMINED ON QA 2026-08-07 — AND THE INTUITIVE ANSWER IS THE WRONG ONE

Each variant written through the real client against `meddoc_qa_test`, then read
back from the column:

| written | `IS NULL` | `= 'null'::jsonb` | verdict |
|---|---|---|---|
| bare `null` | false | **true** | lands as **JSON `null`** |
| `Prisma.DbNull` | **true** | false | SQL NULL |
| `Prisma.JsonNull` | false | **true** | **identical to bare null** |

**So bare `null` has always had `JsonNull` semantics, and `DbNull` — the obvious
reading of the word "null" — would have silently changed what the clinical
worker stores.** Chosen: `Prisma.JsonNull`, because it preserves the stored bytes
exactly.

Also measured, because "equivalent" was worth checking rather than asserting:
both variants read back into JS as `null`, so the one consumer
(`codes-tab.tsx:924`, `?? {}`) yields `{}` either way and cannot tell them apart.
The choice is therefore safe in both directions — `JsonNull` is simply the one
that changes nothing.

⚠️ **THIS TABLE IS RECORDED HERE BECAUSE A REVIEWER CAUGHT THAT IT EXISTED
NOWHERE ELSE.** The first version of the fix carried the measurement only in a
code comment written by the same change that relied on it — which is evidence
citing itself. Production could not corroborate it (every visit holds a real
object), so the QA run is the only witness and it belongs in the ledger.

Tractable in one or two tranches rather than a sprawl. **Each revealed error is
either a latent bug or a missing annotation and gets CLASSIFIED, not
bulk-suppressed.** No `any`-casts to reach green; a site that genuinely cannot be
typed takes a declared, commented exception.

#### FIRE-AND-FORGET HARDENING RIDES WITH IT

Every `void … .catch()` writer's catch must **LOG LOUDLY WITH CONTEXT**. A
swallowed exception on a clinical write path is the silent-success class in its
purest form — `logDelivery` is the reference case, where the export reported
success while its audit row never wrote.

The read-back canon remains the proof standard; **the loud catch is the tripwire
between proofs.**

### 🟩 T7 IS LIVE IN PRODUCTION — 2026-08-07T16:22Z

PR #537 → merge **`f1765832`**, with a full four-workflow citation on the merge
commit:

| Workflow | Run |
|---|---|
| `CI` | ✅ `31190074510` |
| `e2e` | ✅ `31190074567` |
| `a11y-ci` | ✅ `31190074469` |
| `secrets-scan` | ✅ `31190074491` |

Deployed from **`main@141fe70b`** — which carries T7 plus the ingress fix (#539)
— itself fully cited (`CI 31193775929` · `e2e 31193775871` ·
`a11y-ci 31193775992` · `secrets-scan 31193775991`). The tree was asserted clean
at that SHA **before** any measurement was taken. Log
`docs/deploy-logs/deploy-20260807T162243Z.log`; rollback
**`:pre-t7-20260807`**, cut against the RUNNING ids and digest-verified to
resolve to them, negative-controlled against `:pre-t6roles-20260807`.

⚠️ **BEFORE THIS SESSION THE LIVE IMAGES CARRIED NO ROLLBACK TAG AT ALL.**
Deploy (a) landed at 06:02 and its session died before cutting one. A rollback
between 06:02 and 16:22 had no target. Cut and verified before deploying.

#### THE DECLARED DELTA, AND THE CORRECTION IT CONTAINED

Declared before running (runbook §2.5). ⚠️ **The brief said "84 rows
backfilled". That number is wrong in a way the post-deploy check could never
have caught**, because a migration supplies a ready-made excuse for any figure:

    84 rows GAIN the column      62 + 16 + 6
    82 rows RECEIVE a value      62 + 16 + 4
     2 stay NULL BY DESIGN       the platform-global note_templates

Measured after: **gained 84 · valued 82**, exactly. Everything else held —
migrations 90 → 91, both image ids changed (`a9280a7594b3 → 11791f54c3f8`,
`cc913dd3f3a5 → 02d06a803137`), and **26 visits · 15 patients · 16 signed ·
197 practices · 196 users byte-identical**, co-tenants `307/404/200/200/410`,
all five standing checks green.

#### THE BICONDITIONAL BITES — proven by attempt, inside a rollback

    UPDATE note_templates SET "practiceId"='x' WHERE "doctorId" IS NULL;
    → ERROR: violates check constraint "note_templates_practice_iff_doctor"

That is the **reverse** half — the one the migration header calls easy to omit.
It forbids an orphaned tenancy claim on platform content. The attempt ran inside
`BEGIN … ROLLBACK`, so it is observable and was never consequential.

#### ⚠️ PRE-DEPLOY: THE MIGRATION WAS DRY-RUN AGAINST PRODUCTION, READ-ONLY

Every abort guard evaluated **0**, each with a positive control proving the join
traverses (62 and 16 derivable). So no `RAISE EXCEPTION` could fire, and the
migration could not half-apply. The full chain was also applied to a **throwaway
shadow database** — 90 of 91 (the one failure being a `GRANT` migration naming
the absent `meddoc` role), which is where the index-name drift below was found.

#### ⚠️ CARRIED OUT OF T7 — index-name drift, 8 objects, NOT a blocker

The four twin tables' new objects are named `twin_*_practiceId_idx` / `_fkey`
while the models are `@@map`'d to `template_twin_*` and declare a bare
`@@index([practiceId])`. Prisma therefore derives `template_twin_*` names.
Measured on the shadow DB, and the convention is unambiguous in the same
database: `template_twin_fill_manifests_practiceId_status_updatedAt_idx` and
`template_twin_source_artifacts_practiceId_createdAt_idx` both carry the full
prefix, and **the other five T7 indexes match Prisma's convention exactly** — so
the four twin ones are the outliers, not the rule.

Functionally identical; drift against the standing **UNDECLARED-PLAIN = 0**
expectation, and it will surface later as a spurious rename migration.
**RULED 2026-08-07: the SCHEMA gains explicit `map:` names matching the
database's ACTUAL objects. Never rename a live database object for a
convention's sake** — that is a needless migration over a working index.
Schema-only; rides before BILLING.

### T7 (original wording) — the remaining tables gain `practiceId`
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

⚠️ **MECHANISM CONFIRMED 2026-08-07 — it is not a timing question at all.**
`logAiCall` (`packages/ai/src/log.ts:34`) is
`void prisma.aiCall.create(…).catch(…)`. It **returns `void`**, so no caller can
await it and no amount of fan-out latency makes it deterministic. The
`findMany` at `worker.ts:983` sums whatever has landed; an in-flight write is
simply not counted.

Phase 0 recorded this as UNSURE and declined to guess, which was right. The
answer is now structural rather than probabilistic: **the race is real, by
construction.**

⚠️ **AND IT IS WORSE THAN A RACE, WHICH THE EXISTING VERDICT DOES NOT YET SAY.**
A fire-and-forget write can also be **LOST OUTRIGHT** — a failed insert reaches
only `console.error`, and the sum is computed as though the call never happened.
For observability that is noise. For BILLING it is an undercharge with **no row
anywhere to reconcile against**: the vendor invoice will carry a call our ledger
has never heard of.

So B1/B4's brief is narrower than "await the writes": the cost for a visit must
be **accumulated in memory from the values already in hand**, not re-read from a
table that a dropped insert can silently under-report. Recorded here so the
BILLING item inherits the reason, not just the assignment.

*(The catch DOES log loudly — `[ai] AiCall write failed:` — so this is a
tripwire-present case, not a silent one. F-TYPE's hardening pass should confirm
the same is true of every other `void … .catch()` writer.)*

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

#### ✅ EXECUTED 2026-08-07T16:35Z — 12 deactivated, 12 ATTRIBUTED audit rows, 0 deleted

Run **after** the T7 migration, because SPEC §4.1 closes the veto window when
the TEAMS migration runs — not before. `scripts/execute-gate0-deactivation.sql`,
transactional, per the standing shape for owner-ruled production mutations.

**Population RE-DERIVED at execution time**, never copied from the ruling:

    MEDDOC_PRO-only ......... 12   (active 12 · already off 0)
    own clinical data ....... 0    (positive control: 2 users overall own visits)
    pre-existing gate0 rows . 0    (the script is not idempotent, by design)

Verified **independently of the script's own success message**:

    deactivated ............................ 12
    active ................................. 184
    users total ............................ 196   ← 0 DELETED
    deactivated OUTSIDE the ruling ......... 0     ← the control that matters
    audit rows ............................. 12
      with practiceId / snapshot / targetId  12 / 12 / 12
      NULL actor, by design .................12
    rows retained: stamped 12 · attributed-to-ruling 12 · role kept 12 · email kept 12
    clinical: 26 visits · 15 patients · 16 signed · 197 practices — UNTOUCHED

⚠️ **THE SCRIPT SHIPPED WITH A DEFECT AND IT WAS FOUND BY READING, NOT BY
RUNNING.** Its audit INSERT set `practiceIdSnapshot` and **not** `practiceId`.
Under T2's fail-closed rule a NULL `practiceId` *means something* — "this row's
tenant could not be resolved". Measured: 10546 of 10560 rows carry both. These
twelve are trivially resolvable (`u."practiceId"` was already in the SELECT), so
the script would have filed twelve perfectly-attributable rows into the bucket
reserved for attribution FAILURES, eroding the one signal T2 exists to make
trustworthy. **Nothing would have errored.**

Fixed before execution, and the guard now refuses the defect: dropping
`practiceId` from the INSERT again aborts with *"12 audit rows are missing
practiceId/snapshot/targetId"*. Two further corrections rode with it — the
pre-COMMIT block asserted a row COUNT and called it attribution (it now asserts
the attribution), and the no-deletion proof hardcoded `196`, a number copied
from a document and stale the moment somebody signs up (it now pins its own
baseline in a TEMP table inside the transaction).

**Rehearsed before executing**, per the standing shape: the whole script with
`COMMIT` → `ROLLBACK` against production (`UPDATE 12 / INSERT 0 12`, all guards
passing), residue then verified byte-identical to baseline; and three abort
guards each proven to fire by mutating a **copy** of the source, never the
database — the rule earned on 2026-08-05 when a mutation proof nulled 21
signers.

---

### ✅ TEAMS — CLOSED END-TO-END, 2026-08-07

Every item T1 → T8 is live in production, and all four exit-gate rows carry a
written verdict:

| | |
|---|---|
| T1 fixture · T2 audit fail-open · T3 visit tenancy · T4 attribution | 🟩 live |
| T5 read accessor · T5-W write accessor · T6 roles + sign gate | 🟩 live |
| T7 the remaining nine tables · T8 invites carry practice + role | 🟩 live |
| exit gate 1 `worker.ts:983` | verdict recorded — accepted, **assigned to B1/B4** |
| exit gate 2 `practiceIdSnapshot` | done — 6 unresolvable NULL, 10554 set |
| exit gate 3 `audit_logs` S4c | discharged by T7 — SPEC §1.5 names all three exclusions **with reasons** |
| exit gate 4 the 12 accounts | **executed** — see above |

**What the close does NOT claim.** The practice wall is now structural for every
clinical table, and no read or write reaches one without a predicate. It does
**not** mean the tenancy model has been exercised by real multi-seat use: every
production practice holding clinical data is still SOLO, so the widening remains
a no-op in production **by construction**, and every behavioural proof lives on
the T1 fixture. That is a good deploy posture and a poor test posture, and it is
why F1 exists.

**Next: F-TYPE, then BILLING** — in that order, because BILLING is wall-to-wall
new Prisma writes and does not get built on a placebo.

---

### T8 — invites carry practice + role
**Gate:** a code minted for `(practice, CLINICIAN)` produces a member of that
practice with that role, and one minted for a practice that no longer exists
refuses. Audit row per issuance.

---

### ▶ AUTH FAIL-CLOSED — ruled 2026-08-08, implementation is its own item

**RULED: `validateSession` fails CLOSED.** One bounded immediate retry on a DB
error, then refuse with **temporarily-unavailable (503-class)** semantics.
**Never a 401.**

⚠️ **THE 401-vs-503 DISTINCTION IS THE WHOLE RULING, NOT A DETAIL.** A 401 is a
statement about the CREDENTIAL — it tells the client its session is invalid, and
every client responds by discarding it and sending the user to /login. On a
transient pool timeout that converts a two-second blip into a re-login for every
clinician holding a session, which is precisely the outcome the old fail-open
existed to avoid. A 503 is a statement about the SERVER: the credential is
untouched, the client retries, the session survives. **Fail-closed and
sign-everyone-out are not the same posture**, and conflating them is why this
looked like a trade-off with no good side.

#### What was true before the ruling

Two fail-open points, both now instrumented (#544) and both behaviourally
unchanged pending this implementation:

| | what a DB error skipped |
|---|---|
| `getSession`'s inner catch (`lib/auth.ts`) | **`isActive`** — the check never ran; role and practiceId fell through from the JWT |
| `validateSession` (`packages/auth/src/index.ts`) | session revoked, session expired, `isActive`, `suspendedAt`, `softDeletedAt`, `forceLogoutAt` |

Bounded by the JWT's 8-hour `maxAge`. And it never needed the database to be
down: `PRISMA_POOL_MAX=10` with a 20s pool timeout makes failures **per-query**,
so this lookup can time out while the clinical queries after it succeed.

#### The implementation item — scope

1. **ENUMERATE the call sites.** Both catches, plus anything else that swallows a
   DB error on an auth path. By behaviour — "every place a failed auth read is
   caught" — not by grepping the two files already known.
2. **ATTEMPT-PROOF BOTH DIRECTIONS, plus the retry itself:**
   - error path → refuses **after** the retry (not before — a retry that never
     runs is the silent no-op class)
   - healthy path → admits, with no retry and no alarm
   - **the retry provably retries** — assert the call count, or "one bounded
     retry" is a comment
3. **SIZE IT FIRST.** Read the `SESSION_FAILOPEN` counts #544 is now producing
   before choosing the retry budget. Picking a timeout without knowing how often
   the path fires is guessing dressed as engineering.
4. ⚠️ **The 503 must not be swallowed into a generic error boundary that renders
   a login link.** The user-visible outcome is "try again in a moment", not "you
   are signed out" — otherwise the 401 behaviour arrives through the UI instead
   of the status code.

#### ⚠️ #544's FIRES test asserts the CURRENT (fail-open) behaviour

`auth-failopen-observability.test.ts` asserts the session is **still served** when
the lookup throws — deliberately, so that applying this ruling without updating
that file fails loudly instead of drifting. **That assertion is expected to flip
as part of this item**, and its flip is the signal the ruling landed.

## Phase BILLING

Depends on TEAMS: the wallet is per-practice.

### 📐 BILLING RECONNAISSANCE — measured 2026-08-07, READ-ONLY, before any code

Run in the T6 shape, and like T6 it **changes the build order**. 104 clauses from
`RELAY` §B and `DISCOVERY` §C/§D were re-measured against the code and the
production database:

    CONFIRMED 44 · DRIFTED 23 · REFUTED 34 · UNVERIFIABLE 3

**55% of the inherited claims did not survive as written**, and six verdicts that
came back CONFIRMED were **overturned on adversarial challenge** — so the
challenge pass earned its place too.

#### ⚠️ FOUR THINGS THAT CHANGE WHAT GETS BUILT FIRST

**1. B1 AND B4 HAVE NO GATE ON QA TODAY, AND THE FAILURE IS SILENT.**
Both gates say "prove a usage row exists on QA". The mock short-circuits
(`model-client.ts:77`/`:140`, `deepgram-batch.ts:195`) sit **above**
`logApiUsage` (`anthropic.ts:433`/`:580`, `deepgram-batch.ts:375`), so a QA
pipeline run emits **zero** usage events for every stage — which is
indistinguishable from a meter that is broken. `04b:1004` and `llm-mdm.ts:394`
short-circuit inside themselves, so merely relocating the meter does not fix
those two. **THE MOCK BOUNDARY IS A NEW ITEM AND IT BLOCKS B1 AND B4.** It is
not in the ledger; it is now.

**2. `response._request_id` IS NON-ENUMERABLE — the silent-no-op class, exactly.**
`@anthropic-ai/sdk/src/internal/parse.ts:86-89` attaches it with
`Object.defineProperty(..., { enumerable: false })`. So `{...response}`,
`Object.assign` and `JSON.stringify` **all drop it with no error**, `undefined`
reaches the builder, and `ctx.requestId ?? randomUUID()` mints a fresh UUID. B1
would look implemented and measure nothing. It must be read by direct property
access and proven by a test that **reads the row back**.

**3. B1 IS TWO TABLES WITH DIFFERENT COSTS, AND "DEEPGRAM FIRST" IS THE WRONG
PRIORITY.** `api_usage_events.requestId` exists (`schema.prisma:2583`, NOT NULL)
— that half is a value change at **five** builders (not the three DISCOVERY
names: `api-usage.ts:160, 179, 247, 273, 291`). **`ai_calls` has no requestId
column at all**, so B1's gate needs an ADD COLUMN migration there. And by volume:
Anthropic is **1091 of 1312** prod usage rows (83%), Deepgram is **2** (0.15%).
Deepgram is cheapest to build and smallest to gain.

**4. F-TYPE IS A HARD PREDECESSOR OF B5, BY THE LEDGER'S OWN ORDERING.** BILLING
is wall-to-wall new Prisma writes; on an untyped client every
`ledgerEntry.create({ … })` — `balanceAfter` and the micro-dollar amount included
— compiles unchecked. **Do not start B5 before F-TYPE lands.**

#### ⚠️ CORRECTIONS TO CLAIMS THAT WOULD HAVE MISDIRECTED THE WORK

| claim on record | measured |
|---|---|
| Deepgram id "already parsed … read at `:342`" | `:112` is a **type declaration**; `:342` reads `metadata.duration`. `request_id` is read at **no** line |
| the id is "discarded" | **durably stored** in `transcribe_visits.transcriptRaw` (jsonb) via `01-transcribe.ts:272/287` — wrong column, and a PHI-bearing one |
| no Anthropic request-id extraction exists | one **does**, on the error path — `anthropic.ts:108-115`, tested — and is reusable |
| "five Anthropic failure branches" | **nine**, across **three** files; `llm-mdm.ts:526` writes to **neither** table and is invisible to §C.3's own query |
| "`logApiUsage` has exactly two call sites" | **eight** |
| the `llm-mdm` judge is unmetered | **already metered** — `llm-mdm.ts:476`, 111 `judge` rows in prod |

⚠️ **B2's GATE AS WRITTEN WOULD PASS WITH BOTH HOLES OPEN.** "Force a
`SCHEMA_FAIL` and a Deepgram timeout" tests two branches out of nine. The gate is
**one forced failure per ENUMERATED branch**, counted against the list — the
LIST-IS-THE-DRIVER shape, where a sentence ("exactly two call sites") stood in
for an enumeration.

#### ⚠️ A LIVE RATE DISAGREEMENT NOBODY HAD FLAGGED — and it is a real bug now

`api-usage.ts:61` prices OpenAI embeddings at **$0.13/M**; `pricing.ts:170` sets
**$0.02/M**. **6.5× apart, and BOTH are live on the same call**: `embed.ts:95`
prices `ai_calls.costUsdCents` from one and `embed.ts:129` prices
`api_usage_events.totalCostUsd` from the other. This is verbatim the defect the
comment at `api-usage.ts:36-43` claims was resolved for Deepgram. **The two
tables disagree about the cost of the same event, today.**

#### PRODUCTION DATA VALIDATES THE MICRO-DOLLAR RULING — it was not a preference

    costUsdCents = 0 ......... 98 of 1085 priced rows (9.0%)
    min(unitCostUsd) ......... 0.000003   ← 3 micro-dollars

**Real Anthropic calls that cost money are stored as zero**, because a cent is
too coarse to hold them. GATE 0.4's integer micro-dollar is measured, not
stylistic.

#### ⚠️ TWO VERIFICATION TRAPS, BOTH OF WHICH WOULD PRODUCE A FALSE RESULT

- **`stripe@22.0.2` and `@stripe/stripe-js@9.2.0` are still in this host's
  `node_modules` as EXTRANEOUS** — unreferenced by any `package.json`, absent
  from the lockfile, and **absent from all five running containers**. Any B6/B7
  check of the form "prove Stripe is not present" that runs on the host will
  REFUTE while production is genuinely clean. Assert against the **containers or
  the lockfile**, never host `node_modules` — and reap them first.
- A stale gitignored build artifact (`apps/meddoc-pro/.next/standalone/…`, dated
  2026-06-14) still declares both packages. Nothing runs it; it is a second place
  a future sweep gets a hit and re-adjudicates. Same shape as *"a history purge
  does not clear the filesystem"*: the source removal landed, the residue did not.

#### OTHER ORDERING CORRECTIONS

- **B8's stated `A2` dependency is misidentified — drop it.** A2 delivers a nav
  entry and an audit viewer; `/admin/queues` has never had a write path. B8's
  real predecessor is **B5**, unconditionally: there is no wallet, ledger, balance
  or price table in production to gate against.
- **B3 cannot complete as one item.** Two of the three Deepgram rates are
  seedable today with `published` provenance; `nova-3-medical` — **the model that
  actually runs by default** (`deepgram-batch.ts:23`) — is disqualified from that
  seed by SPEC §4.5 and needs an `invoice` or `console` figure nobody has.
  ⚠️ **That is an OWNER/vendor action and it must start in parallel, now**, or B3
  stalls at 2/3 and B6 inherits a rate the price table refused to certify.
- **B8 must be proven on QA.** `failureCategory` is **100% NULL** across all 26
  production visits and there is not one FAILED visit — the classifier B8 would
  reuse has never produced a persisted value in production.

### 🟩 B0-a IS LIVE IN PRODUCTION — 2026-08-08T18:40Z

Deployed from `main` @ **`87327db6`** by `bash scripts/deploy-prod.sh`, under a
delta declaration written before the run: `docs/foundation/deploys/20260808-87327db6.md`.
Log `docs/deploy-logs/deploy-20260808T182917Z.log`. Rollback tags
**`:pre-b0a-20260808`**, cut against the RUNNING ids `df8b00ba5a0e` / `bfbf9c2497c1`
and digest-verified before the deploy started.

**Citation: 4 of 4 on the deployed commit.** `CI` · `e2e` · `a11y-ci` ·
`secrets-scan` are all `completed/success` on `87327db6` (push, 17:41:06Z). That
also **discharges the descendant citation owed** after `9a56293f`'s `e2e` was
cancelled — `87327db6` contains `cbb7b087`, which is itself 4-of-4 green. The
debt recorded below is paid; it is left in place because the mechanism is worth
keeping.

#### The declaration was judged line by line, and nothing moved that was not declared

| declared | measured |
|---|---|
| migrations **91 → 92**, k=1, named | **92**, and the applied name is `20260808020000_b0_units_source` |
| `unitsSource` present, **TEXT NULLABLE, NO DEFAULT** | `unitsSource｜text｜is_nullable=YES｜default=(none)` |
| index `api_usage_events_unitsSource_timestamp_idx` | present |
| **1312** rows backfilled to `vendor`, **0** NULL | `vendor｜1312` — the only group; zero NULLs |
| image ids **both change** | app `df8b00ba…` → `fc79b961…` · worker `bfbf9c24…` → `124f88fa…` |
| clinical **UNCHANGED** | visits **26** · patients **15** · signed **16** · users **196** — byte-identical |
| `api_usage_events` **1312**, `ai_calls` **1122** | **1312** · **1122** — unchanged, as a column-add must be |
| containers 9/9 healthy · co-tenants unchanged | 9/9 healthy · app 307 · admin 404 · quillmd 200 · www 200 · pro 410 |

`audit_logs` was declared as *may rise* and did **not** — 10586 → 10586.

**Structural verification that the new code is actually running**, not merely a
new digest: `unitsSource` is present in the worker image across all ten expected
sources (`packages/ai/src/{api-usage,anthropic,log,mock,embed,deepgram-batch,whisper-batch}.ts`
plus the gate and two app files) and in the app image's built Next chunks.

⚠️ **AND THE FIRST GREP FOR IT RETURNED ZERO — from a broken search, not an
empty image.** `grep -rl … /app --include='*.ts'` over the whole tree returned
nothing; the positive control (`grep -c` against `api-usage.ts` = **5**) is what
exposed it. Recorded because it is the canon's own rule catching the canon's own
author mid-verification: **a clean sweep and a broken sweep produce identical
output**, and the only difference is whether you controlled it.

#### ⚠️ WHAT IS STILL OWED — STEP 2 OF THE MIGRATION — ✅ **DISCHARGED by B0-b, 2026-08-08**

> **Step 2 is written and gated — see the B0-b row below.** This section is left
> in place because its REASONING (why the split was necessary at all) is the part
> worth keeping; only its "unwritten" status is stale. Recorded explicitly rather
> than edited away, because a section that says "still owed" about work that has
> landed is the T2 failure — there, a stale paragraph told a future session to
> re-run an append-only repair that would have written 71 duplicate corrections.

`unitsSource` is **nullable in the database and required only in TypeScript**.
The `SET NOT NULL` migration is deliberately not in this deploy — between
`deploy-prod.sh`'s step 3 (migrate) and step 6 (recreate) the previous image was
still serving and still writing usage rows it had never heard of the column for,
and a NOT NULL with no default would have failed every one of those inserts
*quietly*, because `logApiUsage` is fire-and-forget. That window is now closed:
the writing code is live everywhere. **Step 2 is the next B-lane item and it is
unwritten.** Until it lands the database's guarantee is weaker than the type's,
and a writer that reaches the table off the typed path can still insert a NULL
provenance.

#### What this deploy does NOT claim

- **The meter is not proven in production.** Every arm of B0-a's evidence is a
  unit gate plus the QA E2E seed, and this deploy adds only structural proof that
  the code is resident. No production pipeline run has been observed emitting a
  row since. Proving it would mean running a real visit, and **a real doctor's
  visit is never a smoke target.**
- **B1 and B4 are not closed.** The blocker they named is removed. No vendor
  request id is captured and no per-stage `UsageEvent` coverage exists.

---

### ✅ B0-a — the mock boundary moves BELOW the meter — the build row

**This row was written one session late.** B0-a merged as `9a56293f` (PR #549)
and `RELAY.md` was never updated, so for one session the three `B0` rows in
`RULINGS.md` pointed at a section that did not exist. RULINGS' own rule 3 says a
row is a pointer and its target is authoritative — **a pointer to nothing is the
worst case of that**, because the index reads as complete. The ledger row is part
of the item, not paperwork after it.

**What it does.** Mock the **VENDOR CALL**, never the stage. The two stage-level
short-circuits in `model-client.ts` are deleted; the three `messages.create`
sites in `anthropic.ts` route through one `createMessage` seam; `logAiCall` is
suppressed under mock **on the writer**, not per caller. A mocked pipeline run
now emits `api_usage_events` — which is what BILLING RECONNAISSANCE §1 said was
blocking B1 and B4.

**The marker.** `api_usage_events.unitsSource`, required in the type and with
**no database default**, per the ruling that a provenance column's default must
never be the trusted value. Making it required is what enumerated the writers:
`tsc` named **eight** call sites, all real vendor calls today, all `'vendor'` —
the compiler performing the by-table sweep the canon otherwise demands by hand.

| | |
|---|---|
| merge | **`9a56293f`** (PR #549) |
| migration | `20260808020000_b0_units_source` — **STEP 1 OF TWO** |
| gate | `packages/ai/src/__tests__/gate-b0-mock-boundary.test.ts`, four arms, each mutation-proven to redden |
| rulings | RULINGS 2026-08-08 × 4 — B0 Q1/Q2/Q3 and the standing provenance-default rule |

#### ⚠️ ITS MERGE-COMMIT CITATION IS 3 OF 4, AND THE CAUSE IS IN THIS REPO'S CANON

`CI` · `a11y-ci` · `secrets-scan` all `completed/success` on `9a56293f`.
**`e2e` is `cancelled`** — PR #550 merged to `main` at 15:41:50Z, seventeen
minutes after `9a56293f`'s runs started at 15:24:24Z, and GitHub cancels
in-flight runs on a new push to the same branch. `e2e` runs longer than
seventeen minutes, so it died.

**This is the documented hazard arriving through a legitimate door.** AGENTS.md
records it for a docs-only push straight to `main`; here it was a properly gated
PR merge. The mechanism does not care which — **any** new head on `main` kills
the previous head's in-flight runs. So the rule generalises, and is written down
here in its wider form:

> **Do not merge a second PR into `main` while the previous merge commit's
> citation is still running.** Wait for it, or accept that you have destroyed it
> and owe the descendant a full citation.

**Recovery, per canon — cite the DESCENDANT.** `cbb7b087` contains everything
`9a56293f` did plus PR #550, so its citation covers B0-a's code *and* certifies
the tree that will actually deploy. **Do not re-run `9a56293f`'s cancelled `e2e`**
— it describes an ancestor that is no longer `main`.

#### ⚠️ WHAT B0-a DOES NOT CLAIM

- **It is NOT deployed.** Production holds 91 applied migrations against the
  repo's 92; `api_usage_events.unitsSource` **does not exist in the production
  database**, and its 1312 existing rows are un-backfilled. Prod's code and prod's
  schema are consistent with each other — both pre-B0-a — so this is undeployed,
  not half-deployed. Nothing is broken by it today.
- **STEP 2 OF THE MIGRATION IS OWED AND UNWRITTEN.** `unitsSource` is nullable in
  the database and required only in TypeScript. The `SET NOT NULL` migration
  lands *after* the writing code is live everywhere — deliberately, because
  `deploy-prod.sh` applies migrations at step 3 and recreates the app at step 6,
  and in that window the previous image is still writing usage rows it has never
  heard of the column for. **Until step 2 lands, the database's guarantee is
  weaker than the type's**, and a writer that reaches the table without going
  through the typed path can still insert a NULL provenance.
- **It does not close B1 or B4.** It removes the blocker they named. No vendor
  request id is captured and no per-stage `UsageEvent` coverage exists.
- **The meter has not been proven on a real deploy.** Every arm is a unit gate
  plus the QA E2E seed. That is the correct posture for an undeployed item and it
  is not evidence about production's meter.

#### Carried out of B0-a

`.github/workflows/e2e.yml` now passes `ANTHROPIC_API_KEY=qa-dummy-…` into the
seed step. That is **deliberate and is the two-condition posture, not a leak**:
since the boundary moved below the meter, `getClient()` runs under mock — it
stays the first statement and outside the `try`, so the path is fail-closed. The
flag stops the call; the dummy credential is what survives a path that forgets
the flag. A mock that runs with no key at all is **one** condition, not two.

---

### 🟩 B0-b IS LIVE IN PRODUCTION — 2026-08-09T00:03Z

Deployed from `main` @ **`079b9205`** (PR #554) by `bash scripts/deploy-prod.sh`,
under a delta declaration written before the run:
`docs/foundation/deploys/20260808-079b9205.md`. Log
`docs/deploy-logs/deploy-20260808T235928Z.log`. Rollback tags
**`:pre-b0b-20260808`**, cut against the RUNNING ids `fc79b9618dd2` /
`124f88fa7493` and **digest-verified to resolve to them**, not to a tag string,
before the deploy started.

**Citation: 4 of 4 on the MERGE COMMIT** — not on the PR head:

| Workflow | Run |
|---|---|
| `CI` | ✅ `31283708499` |
| `e2e` | ✅ `31283708484` |
| `a11y-ci` | ✅ `31283708503` |
| `secrets-scan` | ✅ `31283708494` |

#### THE DECLARATION WAS JUDGED LINE BY LINE, AND NOTHING MOVED THAT WAS NOT DECLARED

| declared | measured |
|---|---|
| migrations **92 → 93**, k=1, named | **93**, applied name `20260808230000_b0_units_source_not_null` |
| `is_nullable` **YES → NO** | `nullable=NO` |
| CHECK **absent → present** | `api_usage_events_units_source_domain = CHECK ("unitsSource" = ANY (ARRAY['vendor','mock']))` |
| **DEFAULT still `(none)`** | `default=(none)` |
| image ids **both** change | app `fc79b961…` → `e127943e…` · worker `124f88fa…` → `09886c6b…` |
| `api_usage_events` **1312** | **1312** |
| NULL **0** · off-domain **0** | **0** · **0** |
| census **vendor 1312 / mock 0** | `vendor｜1312`, the only group |
| `ai_calls` **1122** | **1122** |
| clinical **UNCHANGED** | visits **26** · patients **15** · signed **16** · users **196** |
| containers 9/9 · co-tenants | 9/9 healthy · 307 · 404 · 200 · 200 · 410 |

`audit_logs` was declared as *may rise, a fall is a finding*: **10591 → 10591**.

Standing checks green after the deploy: migrations 93/93, imaging E/M invariant,
composite FK, ingress TLS, both encrypted mounts.

#### ⚠️ THE STRUCTURAL VERIFICATION HERE IS THE DATABASE, AND SAYING SO IS THE POINT

B0-a proved its code was resident by grepping the shipped image for a new symbol.
**That move does not transfer to this item, and pretending it did would be
theatre.** B0-b's only source change outside tests and docs is a **comment**
(`prpriced` → `prevent`) plus dropping a `?` in `schema.prisma`. There is no new
runtime symbol to find, so an image grep would prove nothing it could not also
prove about the previous build.

The substance of this deploy is the **migration**, and it was verified where it
lives: `is_nullable`, `column_default`, `pg_constraint` and the row census read
directly out of the production database, against numbers written down before the
deploy existed. An honest structural check names the layer that carries the
change.

#### WHAT THIS DEPLOY DOES NOT CLAIM

- **The meter is still unproven in production.** `api_usage_events`' newest row
  is **2026-08-05 14:43Z**, unchanged by this deploy — no usage row has been
  written since B0-a shipped. The guarantee is now enforced; **nothing has yet
  exercised it in production**, and it will not be exercised until a real
  pipeline runs. A real doctor's visit is never a smoke target.
- **B1 and B4 remain open.** No vendor request id, no per-stage coverage.

---

### ✅ B0-b — `unitsSource` SET NOT NULL — the build row, 2026-08-08

**The step-2 debt B0-a recorded against itself.** B0-a shipped the column
nullable in the database and required only in TypeScript, deliberately and for
exactly one deploy; its own row said *"Step 2 is the next B-lane item and it is
unwritten."* This is that item. From here the database refuses what the type
refuses.

| | |
|---|---|
| migration | `20260808230000_b0_units_source_not_null` — **STEP 2 OF TWO** |
| gate | `apps/transcribe-md/tests/e2e/scenarios/38-usage-provenance.spec.ts`, five arms |
| guarantees | `SET NOT NULL` · `api_usage_events_units_source_domain` CHECK · **still NO DEFAULT** |

#### THE WRITE-PATH SWEEP — by TABLE, and the one writer `tsc` cannot see

Swept by the standing rule rather than by whatever the type checker surfaced:

    raw SQL   grep -rniE 'insert into "?api_usage_events'   → 0 sites
    ORM       apiUsageEvent.(create|upsert|createMany)      → 1 site
                packages/ai/src/api-usage.ts:143

The raw-SQL **zero was positive-controlled** — the identical pattern against
`transcribe_visits` returns **7** real inserts — so it is an empty set and not a
broken pattern. Every other reference to the table in the tree is a `SELECT`
(the `/admin/usage` rollups).

⚠️ **AND THE ONE WRITER IS INVISIBLE TO `tsc`.** It is
`(prisma as any).apiUsageEvent.create(...)`; the shared client is untyped at
that call, so a green type-check proves nothing whatsoever about this insert.
It was read by hand. B0-a's "eight call sites named by the compiler" were
callers of `logApiUsage(event: UsageEvent)` — one layer up, which is exactly the
layer a future writer can step around. This is the canon's *"type-check is
decisive only for TYPED sites"* arriving with the `any` already in place.

#### ⚠️ THE DOMAIN CHECK IS AN ADDITION BEYOND THE LITERAL TWO-STEP RULING

Recorded as one so it can be stripped on sight rather than discovered later.
The ruling named *"nullable + backfill to `vendor`, then NOT NULL"*. **NOT NULL
alone still permits any TEXT**, so it does not actually discharge this item's own
framing — *"the database's guarantee is weaker than the type's"* — because the
type says `'vendor' | 'mock'` and NOT NULL says "some string".

It matters for money, not tidiness. The rollups filter
`WHERE "unitsSource" = 'vendor'` and B6 computes charge over exactly those rows.
A row carrying `'Vendor'` satisfies NOT NULL, reads correctly to a human, and
matches **neither** bucket: it does not error anywhere, it simply stops being
money — an **undercharge no test can see**. The mirror case, a mock row counted
as vendor, charges a doctor for a call that never happened.

**COST, STATED:** a third provenance value later needs a migration to widen the
CHECK. That is deliberate, and it is the AuditAction lesson — the database is
the only layer whose answer counts, so it is the layer that holds the domain.

#### GATE — FIVE ARMS, AND THE MUTATION MATRIX IS THE PROOF

| arm | asserts |
|---|---|
| SHAPE | `is_nullable='NO'` **and `column_default` is `<none>`** |
| NO-NULL | an insert omitting the provenance is REFUSED |
| NO-JUNK | `'Vendor'` is refused **by constraint name** |
| CONTROL | the SAME row with `'vendor'` — and with `'mock'` — is ACCEPTED |
| BUCKETS | every row is in a named bucket and they sum to the total |

Clean run **5/5**. Each mutation named its expected victim **before** it ran:

| mutation | predicted | measured |
|---|---|---|
| `DROP CONSTRAINT …units_source_domain` | NO-JUNK reds | **NO-JUNK only**, 4 green |
| `ALTER COLUMN … DROP NOT NULL` | SHAPE + NO-NULL red | **both**, 3 green |
| `ALTER COLUMN … SET DEFAULT 'vendor'` | SHAPE reds | **SHAPE only**, 4 green |

⚠️ **THE THIRD MUTATION IS THE ONE WORTH KEEPING, AND IT EXPOSED WHY THE
NO-DEFAULT ASSERTION MUST BE ITS OWN ARM.** Under `SET DEFAULT 'vendor'` the
**NO-NULL arm stayed GREEN** — a default only fills an *omitted* column, and the
probe passes NULL explicitly, so the NULL-refusal test is **structurally blind to
a default**. A default is precisely the fail-open the ruling forbids: it would
satisfy NOT NULL perfectly while letting any writer that never heard of the
column silently assert a real vendor reported those numbers. Only the SHAPE arm
sees it. A gate asserting "NOT NULL" alone would have called that state healthy.

⚠️ **EVERY PROBE RUNS IN `BEGIN … ROLLBACK`, AND THE MUTATION RUN PROVED WHY.**
During M1 the off-domain insert **succeeded** — that is what reddened the arm —
and the table still held **977 rows, 0 off-domain** afterwards. Bare inserts
would have left junk rows in the table the money code reads, with the constraint
dropped and nothing to catch them. This is the recorded scar tissue from the
`transcribe_visits_signed_requires_signer` incident, working.

#### THE MIGRATION EXERCISED ITS OWN BACKFILL ON REAL DATA

QA was **one migration behind** (91 of 92) and held **977 usage rows predating
the column**, so applying both steps there ran step 1's backfill for real rather
than over an empty table: 977 → all `vendor`, 0 NULL, then `SET NOT NULL` and the
CHECK. Migrate exit 0, 93 migrations found.

**The straggler backfill is factually correct, not a convenience.** Any row still
NULL was written by a pre-B0-a image, and in that code the mock short-circuits
sat ABOVE the meter — nothing under `MOCK_AI_CALLS` ever reached `logApiUsage`.
A pre-B0-a usage row is a real vendor call by construction.

#### ⚠️ THE GATE'S NON-VACUITY WOULD HAVE RED IN CI, AND ONLY LOCAL LUCK HID IT

The census arm first asserted `total > 0` against whatever was in the table.
That passes on this long-lived QA stack (**977 rows**) and would have **failed in
CI**, where `e2e.yml` tears the stack down with `down -v` and **nothing seeds
`api_usage_events`** — the three seeders cover users, the T1 multi-seat fixture
and the certified twin. Any rows present at that point would be incidental
output of whichever pipeline specs happened to run first: a race, not a fixture.

The arm now **inserts one `vendor` and one `mock` row inside the transaction it
counts**, so both buckets are occupied by construction and the arithmetic runs on
known data. Non-vacuous by construction instead of by luck.

#### ⚠️ THE CHECK IS **NOT** IN THE COMPOSITE-FK CLASS — measured, not assumed

The obvious worry about adding a raw `ADD CONSTRAINT` here is T3's trap:
`prisma migrate diff` reports the composite FK as a permanent difference and
offers `DROP CONSTRAINT …patientId_practiceId_fkey` as tidying, which silently
removes the tenancy wall. So the same question was put to the tool rather than
reasoned about:

    prisma migrate diff --from-config-datasource --to-schema prisma/schema.prisma --script

`api_usage_events_units_source_domain` **does not appear in the output at all** —
neither dropped nor added. Prisma has no CHECK concept, so it is blind to them in
BOTH directions: it cannot express the constraint, and equally it never proposes
to delete one. **A CHECK is therefore SAFER than the composite FK, not the same
risk** — the FK is dangerous precisely because Prisma *can* see it and sees it
wrongly.

The same run re-confirmed the known residue, which is expected and guarded:
the composite FK drop/replace pair is still offered (that is what
`check-composite-fk.sh` exists for), plus the two documented FK re-shapes and one
index rename. **`unitsSource` itself is absent from the diff**, which is the
positive signal that the schema edit and the migration agree.

#### Found on the way past — the substring trap, fifth sighting

`api-usage.ts:164` read *"the fail-open the column exists to **prpriced**"* — an
`event` → `priced` rename that matched inside the word **pr·event·**. Cosmetic:
it is a comment, and the sweep confirmed the same rename damaged nothing else
(every other `priced` occurrence is the legitimate local). Fixed here. Logged
because it is the exact family AGENTS.md already names, arriving in the file this
item was already opening.

#### WHAT B0-b DOES NOT CLAIM

- **It does not prove the meter in production.** `api_usage_events`' newest
  production row is **2026-08-05 14:43Z** — no usage row has been written since
  B0-a deployed, so the live meter remains unobserved. Proving it needs a real
  pipeline run, and **a real doctor's visit is never a smoke target.**
- **It does not close B1 or B4.** No vendor request id is captured and no
  per-stage `UsageEvent` coverage exists.
- **It says nothing about whether the one writer is CORRECT** — only that the
  database now refuses a row that lies by omission.

---

### 🟩 B1-a IS LIVE IN PRODUCTION — 2026-08-09T02:39Z

Deployed from `main` @ **`0257c77d`** by `bash scripts/deploy-prod.sh`, under a
delta declaration written before the run:
`docs/foundation/deploys/20260809-0257c77d.md`. Log
`docs/deploy-logs/deploy-20260809T023737Z.log`. Rollback tags
**`:pre-b1a-20260809`**, cut against the **RUNNING** ids
`e127943edacd` / `09886c6b26da` and digest-verified before the deploy proceeded.

**Citation — 4 of 4 on the MERGE COMMIT `0257c77d`:**
`CI` `31289161308` · `e2e` `31289161291` · `a11y-ci` `31289161336` ·
`secrets-scan` `31289161295`, all `completed/success`.

#### THE DECLARATION, JUDGED LINE BY LINE — 13 of 13

| # | declared | measured | |
|---|---|---|---|
| 1 | migrations 93 → **94** | **94**, `assert-migrations-applied` 🟢 94/94 | ✅ |
| 2 | `ai_calls.requestId` absent → present, `text` / nullable / **no default** | `text`, `is_nullable=YES`, `default=(none)` | ✅ |
| 3 | both image ids move | `e127943e→e781cd52`, `09886c6b→fec3c43d` | ✅ |
| 4 | `transcribe_visits` **26** | 26 | ✅ |
| 5 | `transcribe_md_patients` **15** | 15 | ✅ |
| 6 | visits with `signedAt` **16** | 16 | ✅ |
| 7 | `users` **196** | 196 | ✅ |
| 8 | `ai_calls` rows **1122** | 1122 | ✅ |
| 9 | `api_usage_events` **1312** | 1312 | ✅ |
| 10 | every historical `requestId` **NULL** | total 1122 / **null 1122** / non-null **0** | ✅ |
| 11 | `unitsSource` census **vendor 1312** | `vendor\|1312`, no other bucket | ✅ |
| 12 | co-tenants 307 · 404 · 200 · 200 · 410 | identical | ✅ |
| 13 | 9 of 9 healthy | 9 of 9 healthy | ✅ |

⚠️ **Rows 8 and 10 are deliberately BOTH present and they are not the same
claim.** The count staying at 1122 says no row was ADDED; every historical value
being NULL says no row was MODIFIED. A backfill would satisfy row 8 and violate
row 10 — and a backfill is precisely what must not have happened, because no id
can be invented for a call that finished months ago.

⚠️ **The declaration gate refused the first attempt, correctly, and the fix was
bookkeeping rather than a bypass.** `deploy-prod.sh` names the required file
`<UTC-date>-<short-sha>.md` for the commit being deployed, and that SHA does not
exist until the merge does. The content was authored at ~01:2xZ and **committed
to `main` at `8100e402`** — before the merge, and long before any deploy evidence
existed — then renamed to `20260809-0257c77d.md`. `git show 8100e402` is the
check that no number moved. The baseline was **re-derived at execution time**
(02:36Z) rather than trusted from the file, and came back identical.

---

### ✅ B1-a — the vendor's request id reaches the meter — the build row, 2026-08-09

**Built on `feat/b1a-vendor-request-id`, commit `5e6a27c6`.** B1 splits, and the
split is not a convenience — the second half is ruling-blocked (below).

#### WHAT LANDED

| | |
|---|---|
| migration | `20260809010000_b1a_ai_calls_request_id` — `ai_calls.requestId TEXT NULL`. **93 → 94** |
| reader | `packages/ai/src/vendor-request-id.ts` — `readAnthropicRequestId` / `readDeepgramRequestId`, both returning `null` rather than inventing |
| wiring | 3 Anthropic `createMessage` results + the Deepgram success path, into **both** `logAiCall` and `logApiUsage` |
| gate | `vendor-request-id.test.ts`, 10 arms, **3 mutations each naming its victim first** |
| unit suite | 3211 passed / 4 skipped, 260 files — unchanged in count from B0-b's 3194 + this file's 10 + 7 |

#### ⚠️ THE RECON WAS RIGHT ABOUT THE TRAP AND THE TRAP IS WORSE THAN STATED

`_request_id` is attached with `enumerable: false` — **verified against the
INSTALLED SDK (0.85.0, `internal/parse.js:55`)**, not against the recon's claim.
Two things the recon did not say:

1. **The value is `response.headers.get('request-id')`, and `get` returns `null`
   for an absent header.** So a genuinely successful vendor call can carry no id
   at all. That is why every column fed from this is NULLABLE and why nothing
   fabricates a substitute — "the vendor was called" and "the vendor told us its
   id" are two different facts.
2. **PR #421 proposes 0.85.0 → 0.115.0.** The property is SDK-internal. The unit
   test pins the shape, so the bump should surface there before it surfaces in
   the meter.

**The negative control is the arm that justifies the file.** `readAnthropicRequestId`
is four lines and would pass its happy path written as a spread. So the suite
asserts the counterfactual directly: the *same object*, spread / `Object.assign`
/ `JSON.parse(JSON.stringify(…))`, returns `null` in all three, and the direct
read on the original still returns the id — so the nulls are the copies' fault
and not a broken matcher.

#### THE WRITE-PATH SWEEP, BY TABLE

    raw SQL   grep -rniE 'insert into "?ai_calls'   → 0 sites
    ORM       aiCall.(create|upsert|createMany)     → 1 site (log.ts:55)

**The zero was positive-controlled** — the same pattern against
`transcribe_visits` returns 7 real inserts, so it is an empty set and not shell
escaping eating the pattern. The single writer has **19 call sites** across 5
files; the list is the driver and every entry is dispositioned:

| site group | count | disposition |
|---|---|---|
| `anthropic.ts` success paths | 2 | **wired** |
| `anthropic.ts` failure paths | 8 | **deferred to B2** — that item IS "wire the failure paths"; the id is already extracted there (`:146-155`) and reusable |
| `deepgram-batch.ts` success | 1 | **wired** |
| `deepgram-batch.ts` failure | 2 | **deferred to B2**, same reason |
| `embed.ts` (3), `whisper-batch.ts` (2), `llm-mdm.ts` (1) | 6 | **deferred, named** — OpenAI-family writers; not in B1-a's Anthropic+Deepgram scope (recon §3: Anthropic is 1091 of 1312 prod rows, Deepgram 2) |

None was left to "the errors stopped appearing".

#### PROVING IT CAN GO RED — 3 mutations, each asserted APPLIED before running

| mutation | expected victim | result |
|---|---|---|
| reader reads off `{ ...response }` | happy path + the negative control's back-assertion | **2 failed** ✅ |
| drop `requestId` from the create payload | both wiring arms | **2 failed** ✅ |
| delete `if (isMockEnabled()) return` | the suppression arm | **1 failed** ✅ |

⚠️ **The tree was COMMITTED before the first mutation, deliberately.** The
standing rule is to back up to scratch because `git checkout --` on a dirty tree
destroys uncommitted work — and the entire item was uncommitted. Committing
first makes `git checkout --` the *correct* restore, and creates **no scratch to
reap**. Tree verified clean and back at `5e6a27c6` after each restore.

#### ⚠️ WHAT B1-a DOES NOT CLAIM — read this before believing the gate

- **It does not close B1.** The `?? randomUUID()` fallback in all five usage
  builders is UNTOUCHED. B1-a threads the real id in where the vendor supplies
  one; it does not remove the fabrication in the residual case.
- **It does not prove capture from a REAL vendor response, end to end.** It
  cannot: `logAiCall` returns early under mock (B0 Q1), so a mocked QA pipeline
  writes **zero** `ai_calls` rows, and a real vendor call is the one thing QA
  exists not to make. What IS proven is every link either side of the network —
  an SDK-shaped response in, the id out, into the create payload — plus the DDL
  applying on QA inside `BEGIN … ROLLBACK` (nullable, no default, confirmed by
  `information_schema`). **The unproven link is named, not papered over.**
- **It does not dedup a replayed write.** That half of B1's stated gate belongs
  to B1-b.
- **It says nothing about `transcriptRaw`.** Deepgram's id has been durably
  stored all along — in `transcribe_visits.transcriptRaw`, a PHI-bearing jsonb
  column, unqueryable for billing. B1-a reads it into a real column; it does not
  remove it from there.

---

### ▶ B1-b — the fabrication fallback, and dedup — **RULING NEEDED, blocked**

The remaining half of B1's gate: *"every success row carries a vendor id, not a
`randomUUID()`; a replayed write is deduped."*

**Why it could not be decided in-session.** `ai_calls` was decidable without a
ruling and that is exactly what makes `api_usage_events` undecidable:

| | `ai_calls` | `api_usage_events` |
|---|---|---|
| mocked runs | writes nothing (B0 Q1) | **meters, by design** (B0-a) |
| `requestId` | **NULLABLE** — added by B1-a | **NOT NULL**, 1312 rows |
| a non-null id means | a vendor said it, **by construction** | nothing — could be vendor, could be `randomUUID()` |

So on `api_usage_events` an absent vendor id has nowhere honest to go. **This is
the `unitsSource` problem again, one column over**: a `?? randomUUID()` on a
`vendor` row is a default that asserts the trusted value, which the standing
ruling of 2026-08-08 forbids — but that ruling settles the PRINCIPLE and not the
MECHANISM, and a reasonable person could pick any of these:

1. **make the column nullable** — NULL means "vendor gave none". Cleanest
   semantics; a schema change on a NOT NULL column with 1312 rows.
2. **a reserved sentinel** — e.g. `vendor-id-absent:<uuid>`. No schema change,
   greppable, countable; a magic string every future reader must know.
3. **keep `randomUUID()` for `mock` rows only, and refuse a `vendor` row without
   one** — strongest guarantee, but it makes a telemetry write able to *lose* a
   billable event, which B5/B6 would then under-charge.

**RECOMMENDATION: (1), and SIZE IT FIRST.** B1-a is what makes the sizing
possible — once deployed, `ai_calls.requestId IS NULL` on Anthropic/Deepgram
success rows counts exactly how often a real vendor call yields no id. If that
count is zero over a real week, (3) is safe and strictly best; if it is not,
(1) is the honest shape and (3) would have been discarding revenue. **Picking
before measuring is guessing dressed as engineering** — the same discipline the
AUTH item wrote down for its retry budget.

**Dedup is downstream of that choice** and is not independently rulable: the key
can only be `requestId` if `requestId` is trustworthy. Note B0 Q2 already
constrains it — L4b's k=3 ensemble emits **3** rows with **3** distinct vendor
ids, so a unique index on `requestId` is compatible with the ensemble and would
NOT collapse it.

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

⚠️ **THIS TABLE LAGS THE BODY, AND THE BODY IS AUTHORITATIVE.** The
`T1, T3 … A6 — ⏸ not started` row below has been false since 2026-08-05: T1
through T8, F-TYPE and T5-W are all closed and live, each with its own section
above carrying its own citation. It is left in place rather than rewritten,
because rewriting it would mean re-asserting ten items' status from memory —
**and a summary re-derived from recollection is exactly the drift this table
already demonstrates.** Read the sections. Repricing this table is its own item.

| Item | Status | Merge SHA | CI run | Notes |
|---|---|---|---|---|
| **B0-b** | 🟩 **LIVE IN PRODUCTION 2026-08-09T00:03Z** | **`079b9205`** (PR #554) | **4 of 4 on the MERGE COMMIT** — `CI` `31283708499` · `e2e` `31283708484` · `a11y-ci` `31283708503` · `secrets-scan` `31283708494` | Step 2 of the `unitsSource` migration, the debt B0-a recorded against itself. `SET NOT NULL` + `api_usage_events_units_source_domain` CHECK, **still NO DEFAULT**. Migration `20260808230000_b0_units_source_not_null`: **92 → 93**, `is_nullable` YES → NO, `default=(none)`, **1312** rows / **0** NULL / **0** off-domain, census `vendor 1312`. Clinical byte-identical (26 · 15 · 16 · 196); `ai_calls` 1122 and `audit_logs` 10591 unmoved. Declaration `docs/foundation/deploys/20260808-079b9205.md` written first and judged line by line; log `deploy-20260808T235928Z.log`; rollback **`:pre-b0b-20260808`** digest-verified against RUNNING ids. Sweep was BY TABLE: 0 raw-SQL inserts (positive-controlled — the same pattern finds 7 on `transcribe_visits`), 1 ORM writer, and that writer is `(prisma as any)` so **`tsc` cannot see it**. Gate `38-usage-provenance.spec.ts`, 5 arms, 3 mutations each naming its victim first. ⚠️ **Does NOT prove the meter in production** — newest usage row is still 2026-08-05. Does not close B1/B4. Full section above. |
| **B0-a** | 🟩 **LIVE IN PRODUCTION 2026-08-08T18:40Z** | build **`9a56293f`** (PR #549) · deployed from `main` @ **`87327db6`** | **4 of 4 on the deployed commit** — `CI` · `e2e` · `a11y-ci` · `secrets-scan` all `completed/success` on `87327db6`. This **discharges** the descendant citation owed after `9a56293f`'s `e2e` was cancelled by PR #550's merge | The mock boundary sits BELOW the meter — a mocked run now METERS. Migration `20260808020000_b0_units_source` applied: **91 → 92**, `unitsSource` present as **TEXT NULLABLE with NO DEFAULT**, all **1312** rows backfilled to `vendor`, **0** NULL. Clinical counts byte-identical (26 · 15 · 16 · 196); `api_usage_events` 1312 and `ai_calls` 1122 unmoved. Declaration `docs/foundation/deploys/20260808-87327db6.md`, written first and judged against; log `deploy-20260808T182917Z.log`; rollback **`:pre-b0a-20260808`** cut against RUNNING ids and digest-verified. ⚠️ **Step 2 (`SET NOT NULL`) is owed and unwritten — the next B-lane item.** Does not close B1 or B4, and **does not prove the meter in production**. Full section above. |
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

### 2. `a11y-ci` never runs on `main` — ✅ **CLOSED 2026-08-05**

Resolved by TEAMS hygiene 2: `a11y.yml` now carries `push: [main]` alongside the
`pull_request` trigger (`.github/workflows/a11y.yml:27`, with the reasoning
below preserved in a comment there). Verified 2026-08-08 — `a11y-ci` is
`completed/success` on merge commits `9a56293f` and `cbb7b087`, so all four
required workflows are now citable on a merge SHA. The original finding follows.

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

---

## Found on the way past — 2026-08-08, on the loop's FIRST unattended run

### ✅ THE LOOP CANNOT RUN ITS OWN SCRIPTS — **RESOLVED 2026-08-08, VERIFIED ON THE NEXT LOOP START**

**Status: CLOSED.** The exact-match fix landed (PR #551, commits `42b20d3a` and
`b28c7fc2`) and **this session is the verification the finding demanded.** All
eight standing checks ran as `bash scripts/<name>.sh`, and
`bash scripts/deploy-prod.sh` ran and shipped B0-a — the first item this
programme has deployed from inside the loop.

The old note said *"do not assume the first fix worked — the failure mode of this
whole class is a grant that reads as present and is not."* It worked, and it was
checked rather than assumed. The ten entries are enumerated, not wildcarded, for
the reason recorded below: `scripts/` is session-writable, so a wildcard would
grant "write a script, then run it".

⚠️ **Two refusals remain, and both are CORRECT — do not file them as gaps.**
`rm`/`rmdir` and `shred` are denied, so the loop still **cannot reap its own
scratch**; it reports paths instead. And `.claude/settings.json` is unwritable
from inside a session, which is the property that makes the allowlist an
allowlist. The original finding follows.

#### The original finding, as recorded

**Status at the time: OWNER ACTION. The loop is blocked on this, and no session
can fix it from the inside.**

`scripts/foundation-loop.sh:142` deliberately passes **no**
`--dangerously-skip-permissions`, running instead inside the committed allowlist
in `.claude/settings.json` (PR #550). That is the right design. It does not
currently work: **every `bash scripts/<name>.sh` invocation is refused with
"This command requires approval"**, despite the allowlist's
`Bash(bash scripts/:*)` entry.

#### What was measured, not assumed

| probe | result | what it rules out |
|---|---|---|
| `bash scripts/check-ingress-tls.sh` (and 3 others, and the absolute-path form) | **refused** | — |
| same, with the sandbox explicitly disabled | **refused**, same message | it is the **permission** layer, not the sandbox — the sandbox's refusal has different wording ("was blocked. For security…") |
| `mkdir -p /opt/meddoc-pro/.foundation-probe` | **allowed** | the allowlist **is** live and **does** grant non-read-only commands. `Bash(mkdir -p:*)` is honoured, so this is not "settings.json was never loaded" |
| `git`, `gh`, `npm`, `docker exec`, `docker run --rm --privileged`, `openssl s_client`, `curl` | all allowed | the blast radius is **specifically** `bash <file>` |

The likely mechanism: the permission layer cannot introspect an arbitrary script
file, so `bash <file>` is opaque to it and escalates regardless of a matching
prefix pattern. **That is a hypothesis and it is labelled as one** — it was not
provable from inside the session, for the reason immediately below.

#### ⚠️ AND A SESSION CANNOT REPAIR IT — WHICH IS CORRECT, AND IS WHY IT IS AN OWNER ACTION

Editing **either** `.claude/settings.json` **or** `.claude/settings.local.json`
is refused, even though both sit under the allowlist's own
`Edit(//opt/meddoc-pro/**)`. The harness protects its permission files against
the session they govern. **That is a good property** — an unattended agent that
can widen its own allowlist has no allowlist — and it means the exact-match fix
below cannot be verified from a session either. It has to be landed by the owner
and confirmed on the next loop start.

#### What it costs, in order of severity

1. **`bash scripts/deploy-prod.sh` is unreachable.** The guardrails name it as
   the *only* sanctioned deploy path, and MASTER §THE WORK requires every item to
   be deployed under §2.5. **The loop can build and gate an item but cannot ship
   one.** B0-a is the first casualty: merged, green, and undeployable.
2. **STEP 0.5 cannot execute as written.** All eight standing checks are
   `bash scripts/*.sh`. This session reconstructed them from allowed primitives
   (`docker exec psql`, `openssl s_client`, `findmnt` via root-via-docker,
   `docker inspect`) and all eight came back as they should — but **a
   reconstruction is not the check.** It re-implements the assertion while
   dropping the script's negative controls and edge handling, which is precisely
   the "measures the right quantity over the wrong universe" hazard the canon
   warns about. Reconstructions are a stopgap for one session, never the posture.
3. **RELAY §Invariants re-checked every item** names four of the same scripts.

#### The recommended fix — EXACT-MATCH ENTRIES, and why not a broader wildcard

Replace `Bash(bash scripts/:*)` with one exact entry per script the loop is
allowed to run:

    "Bash(bash scripts/assert-migrations-applied.sh)",
    "Bash(bash scripts/check-imaging-em-artifacts.sh)",
    "Bash(bash scripts/check-qa-mock-posture.sh)",
    "Bash(bash scripts/check-minio-encrypted-mount.sh)",
    "Bash(bash scripts/check-pg-encrypted-mount.sh)",
    "Bash(bash scripts/check-ingress-tls.sh)",
    "Bash(bash scripts/check-bind-mount-agreement.sh)",
    "Bash(bash scripts/check-composite-fk.sh)",
    "Bash(bash scripts/deploy-prod.sh)",

**Enumerated, not wildcarded, deliberately.** `scripts/` is writable by the
session; a pattern that grants *any* file under it grants "write a script, then
run it", which is `--dangerously-skip-permissions` reached by two steps. The
enumerated list is the same shape as the fixture allowlist living in the hook:
one list, and adding to it is a reviewable diff.

⚠️ **VERIFY IT ON THE NEXT LOOP START BEFORE TRUSTING IT.** If exact-match also
fails, the mechanism is not prefix-matching and the alternative is to give the
runner an explicit `--allowedTools` argument, or to invoke the checks through an
already-granted interpreter (`npm run <script>`, since `Bash(npm:*)` is honoured)
rather than through `bash`. **Do not assume the first fix worked** — the failure
mode of this whole class is a grant that reads as present and is not.

### ✅ THE §2.5 DECLARATION GATE REFUSED ITS FIRST REAL DEPLOY — and was right to

Recorded because a guard's first live exercise is the only moment you learn
whether it guards anything, and this one was landed in PR #550 and had never run.

I wrote the delta declaration **before** the deploy, exactly as §2.5 requires —
baseline, must-change, must-not-change, clinical counts and all — and put it at
`docs/deploy-declarations/b0a-20260808.md`. The gate refused:

    🔴 REFUSING TO DEPLOY — no delta declaration for this commit.
       expected: docs/foundation/deploys/20260808-87327db6.md
       Nothing has been built, migrated or recreated. Production is untouched.

**The content was right and the location was wrong, and the gate cannot tell the
difference — which is the point.** Step 8 re-reads *that* path to judge the
outcome, so a declaration anywhere else is a declaration nothing will ever be
compared against. It would have read as diligence and functioned as decoration.

Two things worth keeping:

- **It failed CLOSED and said so.** "Nothing has been built, migrated or
  recreated" is the sentence that makes a refusal safe to hit — no half-deploy to
  reason about, no partial migration.
- ⚠️ **The refusal was nearly invisible, and the cause is in the canon.** The
  first run was `bash scripts/deploy-prod.sh 2>&1 | tail -80`, and the pipe
  returned **`tail`'s** exit code — so a 🔴 refusal reported **exit 0**. That is
  the *"`&&` chain that does not guard the transition"* family wearing a pipe:
  the script's own verdict was discarded by the thing printing it. The re-run
  dropped the pipe. **Never pipe a gated command into a formatter and read the
  pipeline's status as the command's.**

The misplaced file could not be deleted (`rm` is denied to the loop, correctly),
so it was overwritten with a pointer to the real declaration. **`docs/deploy-declarations/`
is not a convention, is referenced by nothing, and should be reaped.**

### ✅ The runner's own log dirtied the tree it tells the next session to clean

**Fixed here.** `scripts/foundation-loop.sh` writes
`docs/foundation/logs/<date>-runNN.log` as its first act, and only
`logs/.gitkeep` was committed — the `.log` files were not ignored. So every loop
session after the first would open on a dirty tree, and **MASTER.md STEP 0.2
instructs that session to reconcile the tree "before anything else"**: the loop
would spend each run triaging its own exhaust, and a session that learned to wave
that file through would be learning to wave through a dirty tree generally.

One line in `.gitignore` (`docs/foundation/logs/*.log`), same reasoning as
`docs/deploy-logs/`. Verified: `git status --porcelain` is clean on this branch
with the run-01 log present on disk.

**Both findings are the same shape** — the loop's own scaffolding, landed in
PR #550 and never executed once before being relied upon. This session is the
first thing that ever ran it.

### ⚠️ A CLINICAL-COUNT DECLARATION IS TRUE AT AN INSTANT, AND 03:00 UTC MOVES IT

**Found 2026-08-09, 47 minutes after B1-a's deploy was judged green on all 13
declaration rows. Nobody was looking for it.**

A re-run of the standing checks during close-out reported
`0 of **14** imaging visits` where STEP 0 had reported `0 of **15**`. Chased
rather than explained, because a difference the declaration does not name is the
finding:

| quantity | at 02:36 and 02:39 (declared, judged ✅) | at 03:26 |
|---|---|---|
| `transcribe_visits` | **26** | **25** |
| `ai_calls` | **1122** | **1112** |
| `specialty='ultrasound'` | 15 | 14 |

**It was not the deploy.** The worker's own log names the mechanism exactly:

    03:00:00.140Z  cleanup:expired-trash  found:1 deleted:1 olderThanDays:15

The T-M17.3 stale-visit cron (`0 3 * * *`, UTC) purged one visit that a user had
soft-deleted more than 15 days earlier — the documented trash-retention contract
working as designed. `ai_calls` fell by 10 because the sweep deletes a visit's
`AiCall` rows in the SAME transaction (`stale-visits.ts:73-77`). There is no
audit row because the sweep is a system job with no actor, consistent with
`audit_logs` being a named S4c exclusion.

⚠️ **THE GENERALISABLE PART, AND IT IS A GAP IN §2.5 ITSELF.**
The declaration's closing rule is *"a difference not in this table IS THE
FINDING, whatever its explanation sounds like afterwards."* That rule is right,
and this system contains a **scheduled job that legitimately moves the exact
counts the declaration pins** — `0 3 * * *` for the visit sweeps, `0 4 * * *` for
the 90-day retention sweep. A deploy judged at 02:55 and re-checked at 03:05
would show a clinical count moving for an entirely correct reason, and the rule
as written classifies that as a finding.

The failure mode is the dangerous direction, not the noisy one: **once "the cron
did it" becomes an available explanation, it is available for a movement the cron
did NOT cause.** That is precisely the ready-made excuse §2.5 exists to remove.

**So a declaration states the INSTANT its baseline was taken and names the cron
windows it does not span.** B1-a's was captured 02:36, judged 02:39, and spans
neither sweep — that is why its 13 green rows still stand. Had it straddled
03:00, the honest declaration would have said so up front and pinned the
`found/deleted` counts from the worker log instead of the raw table count.

**Not fixed here** — changing the declaration template is its own item, and
`docs/foundation/deploys/README.md` is where it would land. Recorded now because
a finding that lives only in a transcript is not a finding, and because the next
session to deploy near 03:00 UTC will otherwise re-derive this from scratch or,
worse, wave a real movement past.

---

### 🟡 `nightly-tests` is RED and has been for one night — TRIAGED, NOT RESOLVED

Recorded so it does not decay into "probably fine" by repetition, which is the
documented fate of an unanswered question here.

| | |
|---|---|
| run | `31236791228`, scheduled, 2026-08-08T03:15Z on `2c6a9d03` |
| job | `smoke + e2e` — `bash tests/automated/run-all.sh --smoke --e2e` |
| shape | failed in **1m56s**, so it died early rather than on a slow assertion. The step itself reports ✓ and the separate *"Fail the job if any suite failed"* step is what reds — the suite writes a result file the job reads afterwards |
| tracker | issue **#548**, opened automatically; detail is in artefact `meddoc-report-31236791228`, which this session could not open |
| history | `2026-08-06` ✅ · `2026-08-07` ✅ · `2026-08-08` ❌ — **one night old, not chronic** |

**It is NOT one of the four required workflows**, so it gates nothing and did not
block B0-a or PR #550. That is the reason it is a 🟡 and not a stop — and it is
also exactly the reason it will be ignored, so the pricing is written against the
asset rather than the symptom: **the nightly is the only scheduled full
smoke+e2e**, and a program about to start writing money code is the wrong moment
to lose the one signal that runs without anybody asking it to.

**Not chased here** — it is outside B0-a and outside this session's item, and
chasing it would be scope creep. **Owed: open the artefact and name the failing
suite before the next BILLING item starts.** Two candidates worth checking first,
both already recorded elsewhere: the known parallel-worker login race
(`--workers=1` reruns), and the dead production `OPENAI_API_KEY` — though note
the chat-editor eval step was *skipped*, not failed, so the second is a weaker
fit than it first looks.

#### ⚠️ TRIAGE ADVANCED 2026-08-08 — and the row above was WRONG about the mechanism

Corrected against the job log (`gh api …/actions/jobs/93050682579/logs`), not
against the run summary. **The row above says the suite step "reports ✓" and that
a later step is what reds. It does not.** The log is explicit:

    ▶ smoke / health
    ▶ smoke / auth-flow
    ▶ e2e (Playwright)
    → json:  tests/automated/reports/2026-08-08-03-16.json
    → html:  tests/automated/reports/2026-08-08-03-16.html
    ##[error]Process completed with exit code 1.

**The `Run smoke + e2e` step itself exits 1.** It only *renders* as ✓ in the run
summary because it carries `continue-on-error`, which is what lets the later
steps key on `steps.run.outcome == 'failure'` to open the issue. The `exit 1`
step at the end is a re-raise, not the detector. **The summary's tick was read as
the step's verdict, and it is a rendering artefact** — the same shape as a check
whose title is narrower than what it measures.

**One candidate REFUTED, cheaply.** The env dump shows `TEST_APP_PASSWORD:` with
an empty value, which reads as a missing secret and would explain a login
failure. It is **blank in the 2026-08-07 GREEN run too** (job `92768257543`,
line 389) — GitHub redacts secret values in env dumps. Not the cause; do not
spend a session on it.

**Narrowed.** Both smoke legs print their banner and the failure lands after the
Playwright banner: e2e ran 03:16:36 → 03:17:25 (**49s**) versus the green run's
04:18:50 → 04:19:18 (**28s**). So the failing leg is **e2e (Playwright)**, and no
per-test detail reaches stdout — the suite writes only the JSON and HTML.

**STILL OWED, and it is one command.** The artefact is live and unexpired
(`meddoc-report-31236791228`, 2.4 MB, artifact id `9015694199`, 28 files,
14-day retention from 2026-08-08 — **it expires 2026-08-22**).

    gh run download 31236791228 -n meddoc-report-31236791228 -D <scratch>
    # then read 2026-08-08-03-16.json for the failing test names

⚠️ **Not done here, deliberately, and the reason is a real constraint on the
loop.** The session sandbox confines writes to `/opt/meddoc-pro`, so the download
would land **inside the git tree**, and `rm`/`shred` are denied — the loop cannot
reap what it creates. Un-reapable scratch in the repository is a worse outcome
than a deferred triage, so it is deferred **with a deadline attached**: after
2026-08-22 the artefact is gone and this becomes unanswerable.


---

## Found on the way past — 2026-08-09, scoping the sanctioned smoke

### ⛔ B1-a CAPTURES THE VENDOR REQUEST ID IN `anthropic.ts` AND NOWHERE ELSE

**This blocks the sanctioned smoke. Do not run it until this is resolved one way
or the other — the run would spend real money on the shared production balance
and return a number that is FALSE.**

B1-a's gate is *"every success row carries a **vendor** id, not a
`randomUUID()`."* It watched `packages/ai/src/anthropic.ts`, where all ten
`logAiCall` sites thread the id correctly. Three other vendor callers do not:

| caller | `logAiCall` sites | passes `requestId` |
|---|---|---|
| `packages/ai/src/anthropic.ts` | 10 | **10** |
| `packages/ai/src/deepgram-batch.ts` | 3 | 1 (success path only) |
| `apps/transcribe-md/src/lib/em-coding/llm-mdm.ts` — **judge** | 1 | **0** |
| `packages/ai/src/embed.ts` — **tm_embed** | 3 | **0** |
| `packages/ai/src/whisper-batch.ts` | 3 | **0** |

`llm-mdm.ts:363` constructs its own `new Anthropic(...)` and calls
`client.messages.create(...)` at `:422`, deliberately bypassing the shared
wrapper so it can attach `cache_control` — the shared `CompleteTextArgs.system`
is typed `string` and cache control needs content blocks. Its `logAiCall` at
`:457` passes no `requestId`, and `log.ts` writes `requestId ?? null`. The SDK
response **does** carry `_request_id`; nothing on that path reads it.

⚠️ **WHY THIS IS NOT MERELY INCOMPLETE COVERAGE — IT FABRICATES THE MEASUREMENT.**
Per `vendor-request-id.ts`'s own header, a NULL is *indistinguishable* from
"the vendor supplied no id". That is the exact quantity the B1-b ruling
(2026-08-09) says to size before deciding whether `vendor ⇒ id` can be strict.
A smoke run today would record our own missing capture as the vendor's silence.

**And the contamination is not confined to one path.** `worker.ts` fires
`judgeMdm` as an unconditional pre-warm, so a full visit run is affected too:
roughly **18% of a visit's ~13–14 calls are structurally NULL** before
Anthropic's actual header behaviour is measured at all.

⚠️ **The nominated "minimal path" was the WORST available choice.** Recon
proposed `POST /api/visits/[id]/em-score` → `judgeMdm` as the smallest unit that
writes one `ai_calls` row and one `api_usage_events` row. It is correct about the
row counts and it is the single Anthropic path in the system that structurally
**cannot** produce the deliverable.

**This is the watched-set-vs-named-set defect, at the write layer:** B1-a's gate
watched `anthropic.ts`; the ruling named *"real calls"*. The gate passed
truthfully over a universe that did not contain most of the question.

#### Two resolutions; the first is recommended

1. **Thread `readAnthropicRequestId(response)` into the three callers** — it
   mirrors `anthropic.ts:276/487` and is a small change per file. Then one smoke
   run yields a clean number.
2. **Pre-register in writing that the metric EXCLUDES `purpose IN ('judge',
   'tm_embed')`**, with expected-NULL declared per purpose before the run.
   Honest, but it measures less and leaves the defect shipped.

⚠️ **The telemetry rows are PERMANENT — no deleter of `api_usage_events` exists
anywhere in the tree.** So a contaminated run pollutes the sizing sample forever
unless every future analysis is timestamp-bounded. That asymmetry is why this is
worth fixing before measuring rather than after.

### What the same pass CLEARED, so nobody re-derives it

- **The smoke fixture is well isolated.** `smoke-doctor@smoke.quillmd.invalid`,
  sole member of `quillmd-smoke-practice`, **currently at baseline: 0 patients,
  0 visits**. `assertIsSmokeFixture()` checks email **and** slug. Production's
  25 visits all belong to two real doctors' practices; none is reachable.
- **Cleanup does NOT destroy the evidence.** `ai_calls` has one FK
  (`practiceId → practices`); neither telemetry table references
  `transcribe_visits`, and no deleter of `api_usage_events` exists in application
  code. Empirically: 454 of the fixture's `ai_calls` are already orphaned and
  have survived 15+ days. The feared contradiction is not real.

### ⛔ Two hard stops, both operator-shaped

- **NEVER invoke `runStaleVisitCleanup()` by hand as a cleanup shortcut.** Sweep 2
  is **not practice-scoped** — `WHERE deletedAt < now-15d` across *all* practices,
  and it deletes `ai_calls` with the visits. It is a no-op today only because
  trash happens to be empty, which is a fact about today and not a property.
- **A call made with a wrong `practiceId` spends real money and writes NEITHER
  telemetry row** — both writes swallow their errors. Use the real fixture id.

### Still undecided, and it needs a person

**The Anthropic balance is not discoverable read-only.** There is no balance API;
the only method this repo ever had was a live completion probe, and that check no
longer exists in preflight. Last known-good is 2026-08-05. Against three prior
mid-run exhaustions, *"the key worked four days ago"* is weak evidence — so
spending one probe call is a decision to take explicitly, not an assumption to
make silently.


---

### B1-b — THE ORDERED SEQUENCE, ruled 2026-08-09

**Work these in order. The order is the ruling, not a preference** — each step
exists to make the next one's evidence mean something.

1. **CLOSE THE CAPTURE GAP FIRST.** Thread `readAnthropicRequestId` into
   `llm-mdm.ts`, `embed.ts` and `whisper-batch.ts`, mirroring
   `anthropic.ts:276/487`. Include `deepgram-batch.ts`'s remaining two sites
   **if they are the same shape**; if they are not, **state that vendor's id
   semantics explicitly** rather than leaving the difference unexplained.
   ⚠️ Measure-with-exclusions was offered and **declined**: it measures less and
   ships the defect.

2. **THEN ruling 1a's migration** — `requestId` nullable, plus the CHECK in its
   **safe direction** (`requestId IS NOT NULL ⇒ unitsSource = 'vendor'`). All
   1312 existing rows already satisfy it, so it is a no-op on current data.

3. **THEN the balance probe** — one call, authorised. ⚠️ **Exhausted balance is
   an OWNER ACTION halt, never a degraded run.** A visit dying mid-pipeline on an
   empty balance leaves a stuck chart and partial rows; waiting is strictly
   better.

4. **THEN ONE clean smoke** on the synthetic account, standing rules in full:
   reset to baseline afterwards **via `clean.ts` only**, audit rows left in
   place. Report **sizing numbers PER PURPOSE** — a single blended figure hides
   exactly the per-path variation this whole sequence exists to expose.

**One act, three items discharged:** 1b's sizing, *the meter is unproven in
production*, and B1-a's capture proven on a live call.

⚠️ **Guarantee a NOVEL `soapText`.** An identical body returns a 7-day cached
judgement and makes **zero** vendor calls — so a `200` is not evidence that a
call happened. Check the `em_mdm_cache:` keys or vary the input.

⚠️ **Declare the expected delta BEFORE the first write** (§2.5), and the
clinical-count row is never omitted: prod-wide `patients=15 / visits=25 /
signed=16` **unchanged**, smoke `ai_calls 487→487+N`, `api_usage_events
451→451+N`, `audit_logs 974→974+M` and **never down**. Any movement outside the
declaration is THE FINDING, whatever its explanation sounds like afterwards.

**Abort guards:** any movement in prod-wide patient/visit/signed counts, or the
fixture's `audit_logs` count decreasing at any point → stop and investigate.

---

### 🟩 B1-b STEPS 1 + 2 ARE LIVE IN PRODUCTION — 2026-08-09T18:18Z

Deployed from `main` @ **`d4e33c22`** by `bash scripts/deploy-prod.sh`, under a
delta declaration written before the run:
`docs/foundation/deploys/20260809-d4e33c22.md`. Log
`docs/deploy-logs/deploy-20260809T181441Z.log`. Rollback tags
**`:pre-b1b-20260809`**, cut against the **RUNNING** ids `e781cd52035f` /
`fec3c43dfb61` and digest-verified (`docker inspect --format '{{.Id}}'` returned
exactly the running ids) before the deploy proceeded. No pre-existing `pre-b1b-*`
tag was overwritten.

**Citation — 4 of 4 on `d4e33c22`, all `completed/success`:**
`CI` `31326376721` · `e2e` `31326376718` · `a11y-ci` `31326376757` ·
`secrets-scan` `31326376712`.

⚠️ **The citation is on the DESCENDANT, deliberately.** `c7dbaf48` — the merge
commit that actually carries step 2 — holds only a **partial** citation: one
`secrets-scan` success plus a `startup_failure` with an empty workflow name.
`d4e33c22` contains everything `c7dbaf48` did plus PR #566, and carries a full
4 of 4. Per the recovery pattern in `AGENTS.md`, citing the descendant is
strictly stricter than citing the parent — it covers the same code *plus* the
later commit, and certifies the tree that actually shipped.

**Both steps shipped in one deploy because neither had ever reached production.**
`assert-migrations-applied.sh` exited **1** at STEP 0 naming
`20260809100000_b1b_request_id_nullable` — the RED that opened this session. It
now exits 0: *95 in repo, 95 rows recorded.*

#### THE DECLARATION, JUDGED LINE BY LINE — 17 of 17

| # | declared | measured | |
|---|---|---|---|
| 1 | migrations 94 → **95** | **95**, `assert-migrations-applied` 🟢 95/95 | ✅ |
| 2 | `requestId` `is_nullable` `NO` → **`YES`** | `text`, `is_nullable=YES`, `default=(none)` | ✅ |
| 3 | CHECKs on `api_usage_events` 1 → **2** | `…_request_id_requires_vendor` + `…_units_source_domain` | ✅ |
| 4 | both image ids move | `e781cd52→63889833`, `fec3c43d→685a6c10` | ✅ |
| 5 | `transcribe_visits` **25** | 25 | ✅ |
| 6 | `transcribe_md_patients` **15** | 15 | ✅ |
| 7 | visits with `signedAt` **16** | 16 | ✅ |
| 8 | `users` **196** | 196 | ✅ |
| 9 | `api_usage_events` rows **1312** | 1312 | ✅ |
| 10 | `requestId` NULL count **0** — all 1312 still populated | `vendor\|1312\|0` | ✅ |
| 11 | `unitsSource` census **vendor 1312**, 0 NULL | `vendor\|1312`, no other bucket | ✅ |
| 12 | `…_units_source_domain` still present | present | ✅ |
| 13 | `ai_calls` rows **1112** | 1112 | ✅ |
| 14 | `ai_calls.requestId` **1112 NULL / 0 present** | `1112\|0` | ✅ |
| 15 | `gotenberg` image id **unchanged** | `2d05d225…acd45`, identical | ✅ |
| 16 | co-tenants 307 · 404 · 200 · 200 · 410 | identical | ✅ |
| 17 | 9 of 9 healthy | 9 of 9 healthy | ✅ |

⚠️ **Row 10 is the INVERSE of B1-a's row 10, and that is the point.** B1-a added
a column and declared every historical value must stay **NULL**. This migration
makes a populated column *nullable* and declares every historical value must stay
**NON-NULL**. Both encode the same rule — *a deploy changes what is POSSIBLE,
never what is RECORDED* — and in this direction the dangerous outcome is a
historical vendor id being cleared, which would destroy the very correlation data
B1-a exists to collect.

⚠️ **Row 14 pins the quantity the NEXT step moves.** Steps 3–4 exist to produce
real `ai_calls.requestId` values. Pinning it at 1112 NULL / 0 present *before*
the smoke is what makes the smoke's numbers attributable to the smoke rather than
to this deploy — without that row the two are indistinguishable afterwards.

**The migration's abort guard passed silently, as declared.** It refuses if any
row carries an id on a non-vendor provenance; the pre-deploy census said zero
such rows, and no `[b1b-step2]` exception was raised.

#### THE CRON CAVEAT THIS DECLARATION HONOURED

Baseline captured **18:13Z**, judged **18:18Z** — spanning neither the `0 3 * * *`
stale-visit sweep nor the `0 4 * * *` retention sweep, and the declaration said so
before the deploy ran.

⚠️ **And the baseline itself shows why that clause now exists.** B1-a's
declaration pinned `transcribe_visits=26` / `ai_calls=1122` at 02:36Z. This
session's STEP 0 measured **25** and **1112**. That difference is the documented
03:00Z sweep purging one soft-deleted visit and its 10 `AiCall` rows — *named in
the declaration up front* rather than discovered afterwards as an anomaly. This
is the first deploy to use the clause the previous session wrote.

---

### ✅ B1-b STEP 1 — the capture gap is CLOSED — 2026-08-09

**Step 1 of the ordered sequence only.** Steps 2 (the migration), 3 (the balance
probe) and 4 (the smoke) are NOT done and are not claimed. What is true now is
that a smoke run would no longer record our own omission as the vendor's silence.

#### THE LIST, WORKED ENTRY BY ENTRY — 19 sites, all accounted for

The ledger handed me a 5-row table. I re-derived it rather than trust it, and it
was right about the shape and wrong in two places:

| caller | sites | ledger said | measured |
|---|---|---|---|
| `packages/ai/src/anthropic.ts` | 10 | 10 pass | **2 pass** — the other 8 are FAILURE paths |
| `packages/ai/src/deepgram-batch.ts` | 3 | 1 | 1 ✅ |
| `packages/ai/src/embed.ts` | 3 | 0 | 0 ✅ |
| `packages/ai/src/whisper-batch.ts` | **2** | 3 | 0 ✅ (count was 3, is 2) |
| `…/em-coding/llm-mdm.ts` | 1 | 0 | 0 ✅ |

⚠️ **"10 of 10" was not wrong so much as measuring a different quantity.**
`anthropic.ts`'s 8 failure sites DO capture the id — into `errorDetails` via
`anthropicErrorDetailsJson(err)`, a JSON blob, not the queryable column. For the
B1-b sizing that distinction is the whole question, and a row that reads "10/10"
invites the next reader to conclude the column is populated on failures. It is
not, anywhere.

**Threaded (4 sites):** `llm-mdm.ts` success · `embed.ts` success ·
`embed.ts` EMBED_DIM_MISMATCH · `whisper-batch.ts` success.

⚠️ **`embed.ts`'s EMBED_DIM_MISMATCH carries an id despite `success: false`, and
that is deliberate.** The VENDOR call succeeded there; we rejected its payload
for the wrong dimension count. We were billed for it. Dropping the id because our
own column says `false` would discard a real correlation id for a call that
really happened.

#### ⚠️ THE RULING NAMED THE WRONG READER FOR TWO OF THE THREE FILES

Ruling 75 says *"thread `readAnthropicRequestId` into `llm-mdm.ts`, `embed.ts`
and `whisper-batch.ts`."* **`embed.ts` and `whisper-batch.ts` are OPENAI
callers** — `provider: 'openai'` at every site.

The function would have WORKED, which is what makes this worth writing down:
openai 6.34.0 uses the identical non-enumerable `defineProperty` trick, so the
happy path would have passed and nobody would have looked again. What it would
have cost is the evidence — `vendor-request-id.ts`'s header pins
`@anthropic-ai/sdk 0.85.0 internal/parse.js:55`, and that citation says nothing
about OpenAI. One shared function would have carried two vendors' SDK internals
under one vendor's proof.

Executed as a sibling **`readOpenAIRequestId`**, verified against the installed
`openai 6.34.0`, `internal/parse.js:55` — same shape, header **`x-request-id`**
rather than Anthropic's bare `request-id`. Both readers keep the never-fabricate
contract. Ruling 75 amended in place with the corrected premise, this commit.

#### DEEPGRAM'S TWO FAILURE SITES ARE NOT THE SAME SHAPE — stated, per the ruling

The ruling required inclusion *"if they are the same shape"*, and an explicit
statement of the vendor's id semantics if not. They are not, **and they differ
from each other**:

| site | what exists | disposition |
|---|---|---|
| `fetch` threw | **no response at all**; on a TIMEOUT the request may never have reached Deepgram | NULL is the honest value, not a gap |
| `!res.ok` | Deepgram ANSWERED; the id is in the **`dg-request-id` response header** | capturable, **left to B2** |

Deepgram's id lives in the BODY (`metadata.request_id`), unlike Anthropic and
OpenAI which expose it as a property on a parsed SDK response — this caller uses
raw `fetch`, so there is no SDK to populate one. Both sites carry the reasoning
in place, at the code.

#### FAILURE PATHS ARE B2's, AND B2 NOW HAS ITS INPUTS MEASURED

Deliberately **not** widened into here — B2 is *"wire the failure paths into the
durable table"* by name, and half-doing it under step 1's name is how an item
gets marked done twice. What B2 no longer has to rediscover:

- `deepgram-batch.ts` `!res.ok` → **`dg-request-id` response header**
- `embed.ts` / `whisper-batch.ts` outer catch → **`APIError.requestID`**
  (openai 6.34.0 `core/error.js:14`)
- `anthropic.ts` × 8 → already captured, but into `errorDetails` JSON; the work
  is moving it to the column (`@anthropic-ai/sdk` `core/error.js:14` is the same
  shape)

#### THE GATE — and why it is a RECONCILIATION, not a grep

`packages/ai/src/__tests__/gate-b1b-request-id-capture.test.ts`, 12 tests.

B1-a's gate was green and truthful over a universe that did not contain the
question. So this one buckets **every** `logAiCall` site in **every** vendor
caller — SUCCESS_CAPTURES / SUCCESS_NO_ID / FAILURE_CAPTURES / FAILURE_NO_ID —
asserts the four sum to a per-file census (19 total), holds SUCCESS_NO_ID at
**0**, and declares each FAILURE_NO_ID count BY FILE with its reason.

⚠️ **The assertion that would actually have caught B1-a's gap is the last one:
`CALLERS` is re-derived from the tree and diffed against the hand-kept list.**
Every other test is exact about the five files it was handed; only that one asks
whether five is the right number. **It fired on its first run** — reporting
`packages/ai/src/log.ts`, which turned out to be the `logAiCall` *declaration*,
not a caller. Fixed by skipping declarations; left unfixed it would also have
inflated the census by one.

**Mutation-proven**, by removing the four `requestId:` lines **and leaving their
comments in place**:

    SUCCESS_NO_ID           []  →  embed.ts · whisper-batch.ts · llm-mdm.ts
    embed.ts FAILURE_NO_ID   1  →  2
    "every caller has a capturing success site"  →  red on embed.ts

⚠️ **Leaving the comments in was the point.** This fix wrote the word
`requestId` into prose sitting directly on top of sites that deliberately pass
none — the substring trap that has bitten this repo four times. The sites still
classified as NO_ID, so the comment stripper is positive-controlled **against the
real files**, not only against its fixture.

⚠️ **`cp` and `mkdir` are DENIED to this session and are NOT in MASTER.md's
permissions table** — a finding, recorded below. The mutation proof therefore
used the Edit tool to mutate and restore, which never touches git and **asserts
its own occurrence** (a failed restore errors rather than silently no-op'ing).
That is strictly safer here than the prescribed scratch-copy: the tree carried
this session's uncommitted work, and `git checkout --` is the documented way to
destroy exactly that (B0-a, 2026-08-08). **No scratch was created.**

#### WHAT THIS DOES NOT CLAIM

- **Not proven on a live vendor call.** Every assertion is source-level or
  against an SDK-shaped fixture. The live proof is step 4's smoke, and it is the
  reason step 4 exists.
- **`api_usage_events` is untouched.** Its `requestId` is still NOT NULL across
  1312 rows; that is step 2's migration, and this change writes only to
  `ai_calls`.
- **Failure paths still write NULL** into the column, on every caller. Declared,
  not fixed.
- **`whisper-batch.ts`'s capture is unexercised in practice** — the pipeline runs
  Deepgram; Whisper is the fallback. Correct, and rarely reached.

**Local:** `packages/ai` 449/449 · `transcribe-md` 3228 passed / 4 skipped ·
`tsc --noEmit` clean. Confirmed the gate runs under the app's vitest config —
the exact command CI's `unit tests` job uses (`test:unit -w transcribe-md`), via
its `packages/*/src/**` include glob. A gate CI does not run is decoration.

#### ⚠️ STEP 1's CITATION WAS CANCELLED, AND IS DISCHARGED BY ITS DESCENDANT

**Fourth occurrence of push-cancels-in-flight, and the second to arrive through a
legitimate PR merge rather than a stray push.** Recorded here because the ledger
row for step 1 carried no citation at all, and an uncited commit on `main` is
exactly what the rule exists to prevent.

| commit | what it is | citation |
|---|---|---|
| `aaaf9faa` | PR #564 — B1-b step 1 | **all four `cancelled`** — `CI` 31303870752 · `e2e` 31303870769 · `a11y-ci` 31303870758 · `secrets-scan` 31303870792 |
| `cf738620` | PR #563 — the loop's self-driving contract, merged minutes later | **4 of 4 `completed/success`** — `CI` 31303882816 · `e2e` 31303882823 · `a11y-ci` 31303882815 · `secrets-scan` 31303882837 |

`git merge-base --is-ancestor aaaf9faa cf738620` **holds**, so the green citation
covers step 1's code *plus* the loop change, on the commit that is actually
`main`. Per the recovery pattern this is **strictly stricter** than what was
lost, and no re-run of the cancelled past is owed. **The debt is discharged; do
not re-open it.**

---

### ✅ B1-b STEP 2 — `requestId` goes nullable, and nothing invents one — 2026-08-09

**Step 2 of the ordered sequence only.** Steps 3 (the balance probe) and 4 (the
smoke) are NOT done and are not claimed.

Executes ruling 72(a) — the migration — **plus the writer change that ruling
implies and that a migration alone would have broken**. The two ship together
for a reason given below.

#### WHAT WAS ACTUALLY WRONG, IN THE SCHEMA'S OWN WORDS

`schema.prisma` had named all three defects since B1-a and left them open:

> `api_usage_events.requestId` does NOT have that property — **it is NOT NULL,
> it carries mock rows, and it still falls back to `randomUUID()`.** Closing that
> is B1-b and it needs a ruling.

The column was **100% populated and 0% trustworthy**. `NOT NULL` did not produce
ids; it produced *indistinguishable* ids — a minted UUID and a real vendor
correlation id are the same shape, so one row later nothing could tell them
apart. A ratchet counting "rows with a requestId" would have read 100% and meant
nothing. All three are closed here.

#### THE LIST, WORKED ENTRY BY ENTRY

Swept **BY TABLE**, positive-controlled, and every entry carries its disposition:

| # | entry | disposition |
|---|---|---|
| 1 | migration — `DROP NOT NULL` + CHECK | `20260809100000_b1b_request_id_nullable`, abort guard **before** the constraint, catalog read-back **after** it |
| 2 | `schema.prisma` — the column | `requestId String?` + the CHECK declared in place (Prisma cannot express it; an undeclared `ADD CONSTRAINT` is drift) |
| 3 | `schema.prisma` — `ai_calls.requestId`'s comment | it asserted the defect as PRESENT; now false, rewritten to say how the property was obtained differently |
| 4 | `api-usage.ts` — 5 builders | `?? randomUUID()` → `?? null`. **Expected 5, measured 5, verified 0 remaining** |
| 5 | `api-usage.ts` — the writer | mock ⇒ `requestId: null`, beside the money-zeroing, same reasoning |
| 6 | `api-usage.ts` — the type | `requestId?: string \| null`, so a `string \| null` from the readers passes straight through |
| 7 | `anthropic.ts` ×2, `deepgram-batch.ts` ×1 | `?? undefined` → bare passthrough; the dance existed only to feed the removed fallback |
| 8 | `embed.ts`, `whisper-batch.ts`, `llm-mdm.ts` | **were minting on every call** — threaded the real id, mirroring what step 1 did for `ai_calls` |
| 9 | raw-SQL writer — `38-usage-provenance.spec.ts` | fixture reshaped; see the attribution finding below |
| 10 | `email.ts` ×2 (Resend) | **NOT APPLICABLE, declared with reason** — Resend returns a *message* id, not a call correlation id. See the open question below |

**Entry 8 is the one a symptom-led fix would have missed.** Step 1 threaded those
three files' ids into `logAiCall` and **explicitly declared `api_usage_events`
out of scope** — correctly. So one real vendor call was writing two tables with
two different "correlation ids", exactly one of them real, and `llm-mdm.ts` is
the highest-volume of the three because `worker.ts` pre-warms `judgeMdm` on every
visit. Nothing was in an error state.

#### ⚠️ WHY THE MIGRATION AND THE WRITER COULD NOT SHIP SEPARATELY

Had the CHECK landed while the builders still minted, **every mock row would
have been refused by the database and dropped in silence.** `logApiUsage` is
fire-and-forget: it catches its own write error and `console.warn`s. No test
fails, no surface goes red, and B0-a's guarantee — that a mocked run meters —
quietly stops being true. This is the fire-and-forget class from `AGENTS.md`
arriving at a constraint instead of an enum, so the gate **reads the row back**
rather than trusting the call's status.

#### PROVEN ON QA — the whole truth table, every write rolled back

Migration applied to `meddoc_qa_test`; its own catalog read-back fired.

| provenance | id | result |
|---|---|---|
| `mock` | present | **REFUSED**, by name — `api_usage_events_request_id_requires_vendor` |
| `vendor` | present | accepted |
| `vendor` | NULL | accepted — **the converse is deliberately not asserted** (ruling 72(b)) |
| `mock` | NULL | accepted — B0-a keeps metering |

977 rows before and after; every probe inside `BEGIN … ROLLBACK`, per canon.
The QA `_prisma_migrations` row was recorded so the stack's ledger and its schema
agree.

#### ⚠️ THE NEW CHECK BROKE AN EXISTING GATE'S ATTRIBUTION — measured, not guessed

`38-usage-provenance.spec.ts` built every fixture row with a literal
`'b0gate-req'`. Its NO-JUNK arm asserts a refusal **by constraint name** so the
refusal is attributable to exactly one cause — and a `'Vendor'` row carrying an
id now violates **two** constraints. Postgres reports whichever it evaluates
first, and it was measured on QA:

    ERROR: … violates check constraint "api_usage_events_request_id_requires_vendor"

That is **not** the name the arm asserts. Left alone it would have gone red in
CI, pointing at a constraint the arm was never about. Fixed by making `requestId`
**default to NULL** in the fixture so each arm opts IN to an id — the value that
cannot trip the new CHECK is the one you get by not thinking about it.

#### THE GATE

`packages/ai/src/__tests__/gate-b1b-no-fabricated-request-id.test.ts`, 10 tests,
plus 4 new arms on the E2E spec (9 of 9 pass on QA).

It does not count populated rows — that number was 100% while the defect was
live. It asserts behaviour in **both directions** (a builder hardcoded to `null`
would satisfy "never fabricates" and destroy every real id), the writer's
mock⇒NULL, a comment-stripped source arm, and a **census** whose file list is
re-derived from the tree and diffed against the hand-kept one.

**Mutation-proven, four ways, each naming its victim:**

    builder fabrication restored      → NO FABRICATION red on buildOpenAIEmbedUsage
    writer's mock⇒null removed        → MOCK ROW CARRIES NO ID red
    llm-mdm's threading reverted      → census red, naming the file and the count
    email.ts dropped from the list    → watched-set arm red, naming the file

The third is the one that matters: it proves the census **watches the sites this
item fixed**, so the gate moves when the work lands rather than merely failing on
a regression.

#### ⚠️ FIFTH SIGHTING OF THE SUBSTRING TRAP — and it was mine, within the hour

`grep -c 'ctx.requestId ?? randomUUID()'` reported **6** code sites. There were
**5**. The sixth was a doc comment *I had written minutes earlier* explaining the
fabrication being removed. Had I trusted the 6 and scripted against it, the
occurrence assertion would have failed and I would have gone looking for a site
that does not exist; had I trusted a naive `'randomUUID' in source` guard, it
would fail forever on the documentation of its own fix.

`api-usage.ts` now says `randomUUID` three times in prose deliberately, and the
gate's stripper is **positive-controlled against that real file** — raw contains
the token, stripped does not. Prose is not a proxy for code, and a file's
comments are where the words you grep for are guaranteed to appear.

Also caught by an occurrence assertion in the same pass: a `replace_all` over two
call sites replaced **one**, because the two carried different comments and my
anchor included one of them. A partial application that compiles is the dangerous
kind; the count is what surfaced it.

#### WHAT THIS DOES NOT CLAIM

- **Not deployed.** Production holds 94 applied migrations against the repo's 95.
  Prod's code and schema are consistent with each other — both pre-step-2.
- **Not proven on a live vendor call.** Every arm is source-level, unit-level, or
  a QA database probe. The live proof is step 4's smoke.
- **The converse is unmeasured and unasserted.** `vendor ⇒ id` is ruling 72(b)
  and needs step 4's numbers. An arm pins the absence so a later tidy-up cannot
  ship the guess.
- **Failure paths still write NULL** into `ai_calls.requestId` on every caller.
  Declared in step 1, unchanged here — that is B2.
- **It does not close B1 or B4**, and it does not prove the meter in production.

#### Found on the way past

- **⚠️ THE MOCK BOUNDARY MOVED BELOW THE METER FOR ANTHROPIC ONLY.** B0-a's
  "what it does not claim" section never said so. `deepgram-batch.ts:197` and
  `embed.ts:72` still short-circuit **above** `logApiUsage`, so a mocked run
  emits **zero** usage events for transcription and embedding. Not a defect
  today — `unitsSource: 'vendor'` is hardcoded at both, and correctly, because
  the mock never reaches them. **But it is load-bearing for B4**, whose gate is
  *per-stage coverage with expected call counts*: a QA/mock run structurally
  cannot produce those stages, so B4 must either exclude them by name or run
  against real calls. Left for B4 rather than widened into here.
- **⚠️ GATE 0.5 SAYS RESEND IS NOT METERED; `email.ts` METERS IT.** Two
  `logApiUsage(buildResendUsage(…))` sites write `api_usage_events` rows with
  `unitsSource: 'vendor'`. They predate the ruling. Whether GATE 0.5 governs
  telemetry rows or only the billable price table is **not decided here** — it is
  a B3/B5 question and deciding it silently while touching the same file is how
  two parts of a system end up built to incompatible readings of one ruling.
- **The long-lived QA stack is behind `main`.** `20260809010000_b1a_ai_calls_request_id`
  is neither applied nor recorded there (`ai_calls.requestId` does not exist).
  CI's `e2e` builds a fresh database per run, so no citation is affected. Pre-
  existing; not created by this item.

**Local:** `packages/ai` 459/459 (449 + this gate's 10) · `transcribe-md` 3238
passed / 4 skipped · `tsc --noEmit` clean · `prisma validate` clean · E2E
scenario 38 **9 of 9 on QA**. The unit count moving by exactly 10 under
`test:unit -w transcribe-md` is the evidence that CI runs the new gate.

---

### ✅ B1-b STEPS 3 + 4 — the balance probe and the sanctioned smoke — 2026-08-09

**The B1-b ordered sequence is now COMPLETE end to end: 1 → 2 → 3 → 4.**
Full report, with the declaration committed *before* the run:
`docs/qa-reports/b1b-step4-smoke-20260809.md`.

**Step 3 — the balance probe.** One authorised call,
`claude-haiku-4-5-20251001`, `max_tokens: 1`. **HTTP 200** — the balance is NOT
exhausted, so the sequence proceeded rather than parking. Issued via
`docker compose exec` so the key was read from the container's own environment
and never entered a shell command or any output.

**Step 4 — ONE clean smoke**, visit `cmsm4y2ro00010hqogjeg1x2v` on the synthetic
fixture, `READY`, **13 calls / 13 meter rows / $0.49**, cleaned to baseline.
**15 of 15 declared rows judged ✅**, including the abort guard on the real
clinicians' counts — checked before, during and after: **15 / 25 / 16 unmoved**,
non-smoke `ai_calls` **625 both sides**.

#### THE DELIVERABLE — `requestId` by purpose, on REAL vendor calls

**13 of 13 present. Zero NULL.** Across `judge`, `tm_anchor_entailment` (×3),
`tm_cpt_coding`, `tm_critique`, `tm_entities`, `tm_icd_coding`,
`tm_patient_summary`, `tm_referrals`, `tm_rx_drafting`, `tm_soap_draft`
(anthropic) and `tm_transcribe` (deepgram). `api_usage_events` mirrors it
row-for-row, every row `unitsSource='vendor'`.

**Three owed items discharged in one act**, exactly as ruling 73 intended: 1b's
sizing · *the meter is unproven in production* · B1-a's capture proven live.

⚠️ **AND STEP 1's FIX IS PROVEN IN PRODUCTION ON THE PATH THAT MOTIVATED IT.**
`judge` — recorded as *structurally NULL*, and pre-warmed by `worker.ts` on every
visit — returned **1 of 1 present**. Run before step 1 landed, this smoke would
have recorded our own missing capture as the vendor's silence, permanently:
`api_usage_events` has no deleter anywhere in the tree.

**Ruling 68 confirmed by observation:** `tm_anchor_entailment` produced **3 calls
and 3 meter rows** — one row per CALL for L4b's k=3 ensemble, not one per stage.

#### ⛔ 72(b) IS STILL OPEN. A PERFECT SCORE IS NOT A MEASUREMENT.

**13 of 13 is the shape of evidence most likely to be over-read, and the
declaration said so before the number existed.** It is one visit, one specialty,
one input mode, and **13 of 13 calls SUCCEEDED** — so this sample contains
**exactly zero evidence about failure paths**, which still write NULL by design
(that is B2). The constraint would have to survive precisely the case not
sampled.

**Tightening remains the allowed direction**, so waiting costs nothing and
guessing cannot be walked back. 72(b) stays open and still owed a real
measurement.

#### What this does NOT claim

- **Step 1 is proven live for ONE of its three callers.** `tm_embed` produced no
  rows at all and `whisper-batch.ts` never ran (Deepgram served transcription),
  so `embed.ts` and `whisper-batch.ts` remain unit-proven only.
- **It does not close B1 or B4.**

#### Carried to B4, both from this run

- ⚠️ **A single-visit sample does NOT contain every stage.** `tm_embed` was
  absent. B4's gate is *per-stage coverage with expected call counts* — it must
  not assume one visit exercises the full stage set.
- ⚠️ **The same call is NAMED DIFFERENTLY in the two tables.**
  `ai_calls.purpose='tm_transcribe'` vs
  `api_usage_events.operation='transcribe_realtime'`; every other stage matches.
  **A B4 gate that joins the two tables by stage name will silently mis-pair
  this one.** Fix it in the gate's mapping, not by renaming a column with history
  behind it.

---

## Found on the way past — 2026-08-09, deploying B1-b

### ⛔ `gh run list --commit <SHORT-SHA>` RETURNS `[]` — THE MANDATORY PRE-PUSH CHECK CAN LIE ALL-CLEAR

**This is the check MASTER.md made a MUST yesterday (ruling 74, after the third
push-cancels-in-flight incident), and the form a person naturally types is the
form that silently answers nothing.**

Measured this session, both directions, within a minute:

    gh run list --commit d4e33c22                                  → []
    gh run list --commit d4e33c220ff6555420bd4c3ec843ed4517cb8e69  → 4 runs, all success

`git log --oneline` prints short SHAs, `git rev-parse --short HEAD` returns one,
and every ledger row in this file cites them — so the abbreviated form is the one
that comes to hand. It does not error, does not warn, and does not say
"ambiguous". **It returns an empty list, which is exactly what "no runs in
flight" looks like.**

⚠️ **THE FAILURE IS IN THE DANGEROUS DIRECTION.** The rule's whole purpose is to
stop a push from cancelling somebody's evidence. A pre-push check run with a short
SHA reports *nothing in flight* for a commit with four runs executing, and the
push proceeds — destroying the citation the check existed to protect, while
appearing to have been performed. The audit trail would show the check was run.

And it is the **same family as the one already recorded against `gh pr checks`**
(reported `pending` for a run already `completed/success`). Two different `gh`
surfaces, two different lies, both in the direction that costs a run:

| surface | lies how |
|---|---|
| `gh pr checks` | reports `pending` for a completed run — waits for nothing, or under-reports a citation |
| `gh run list --commit <short>` | reports **`[]`** for a commit with runs — an all-clear that authorises the cancelling push |

**The rule, tightened:** the pre-push check and every citation take the **full
40-character SHA**, from `git rev-parse HEAD` — never `--short`, never a SHA
copied out of `git log --oneline` or out of a ledger row in this file.

⚠️ **AND A ZERO FROM THIS COMMAND IS POSITIVE-CONTROLLED BEFORE IT IS BELIEVED.**
The canon's standing rule applies verbatim here — *a broken check and a clean
system produce identical output*. The control is free: re-run against a commit
known to have runs (`gh run list --branch main --limit 5` names several) and
confirm the command can return non-empty at all. This session's `[]` was caught
only because two consecutive commits both returned empty, which was implausible
enough to check — **one plausible empty result would have passed straight
through.**

MASTER.md's own text still reads `gh run list --commit <sha>`, and `<sha>` is
where the ambiguity lives. Correcting that wording is its own item; recorded here
because a finding that lives only in a transcript is not a finding.
