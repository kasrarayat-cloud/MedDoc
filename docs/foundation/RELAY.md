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

#### ⚠️ AND THE CHECK IS NOW PROVEN TO **REFUSE** IN PRODUCTION

Step 2 mutation-proved the constraint **on QA**; on production it had only been
*seen in the catalog*. The smoke could not settle it — all 13 rows were
`(vendor, id present)`, which the CHECK **accepts**, so a fully green smoke is
exactly as consistent with a constraint that refuses nothing.

Proven per the canon's sanctioned form, each attempt in its own transaction and
never committed:

    positive control  mock + id NULL   → UPDATE 1  (legal; the write path works)
    the refusal       mock + id KEPT   → ERROR … "api_usage_events_request_id_requires_vendor"

**Attribution was established before the attempt**: `…_units_source_domain`
permits `'mock'`, so the only constraint the flip can violate is the one under
test — avoiding the trap recorded against the composite-FK arm, where an
unrelated `NOT NULL` refused first and the proof established nothing. Census
`vendor | 1325 | 0` before and after, identical.

#### What this does NOT claim

- **Step 1 is proven live for ONE of its three callers.** `tm_embed` produced no
  rows at all and `whisper-batch.ts` never ran (Deepgram served transcription),
  so `embed.ts` and `whisper-batch.ts` remain unit-proven only.
- **It does not close B1 or B4.**

#### ⚠️ FINDING — `clean.ts` REAPS ROWS, NOT OBJECTS

The smoke's audio survived the clean:
`transcribe-md-audio/…/cmsm4y2ro00010hqogjeg1x2v/b1b-smoke.mp3`, 2.9 MiB, still
present afterwards. **Not PHI** — TTS synthesized from the committed `VS1`
script. **Reported, not deleted**: an undeclared production write is the side
effect the standing rule forbids, and ruling 70 says the loop lists while a
supervised session destroys.

**Priced by the asset, not the symptom.** As residue it is trivial. The shape is
not: *a cleanup routine whose name promises completeness, silently scoped to one
storage layer.* Here the audio is synthetic; the same gap around a real visit
would leave a patient's **voice recording** behind after something reported
success. ⚠️ **Whether the APPLICATION's visit-deletion path reaps audio is a
different code path, was NOT examined, and must not be inferred from this** — but
it is worth its own cheap check.

#### ⚠️ A DELIBERATE RUN CANCELLATION, STATED AS THE RULE REQUIRES

Ruling 74 allows a push over in-flight runs provided the cancellation is named.
Three runs on `57406a15` were cancelled **2m39s** after starting, to add the
production-refusal proof above.

**The arithmetic is the justification, and it generalises:** the cost of
cancelling is the time already *elapsed*, not the run's length. Cancelling at
2m39s cost under three minutes; waiting for the four runs and then pushing the
same paragraph would have cost a second full cycle (~40 min). **The cheapest
moment to add something is immediately after a push, not after the runs finish**
— which is the opposite of the instinct the rule is usually invoked to correct.
The rule is about not destroying evidence *unknowingly*; it is not a prohibition
on ever pushing.

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

---

### 🟩 B2 IS LIVE IN PRODUCTION — 2026-08-09T23:18Z

Deployed from `main` @ **`274a4925`** by `bash scripts/deploy-prod.sh`.
Log: `docs/deploy-logs/deploy-20260809T231810Z.log`.
Declaration: `docs/foundation/deploys/20260809-274a4925.md`.

| commit | what | citation |
|---|---|---|
| `ac9a46cd` | PR #568 — B2's code and gates | **4 of 4** — `CI` 31335894849 · `e2e` 31335894841 · `a11y-ci` 31335894852 · `secrets-scan` 31335894836 |
| `d500b542` | PR #570 — declaration + findings | **4 of 4** — `CI` 31339752406 · `e2e` 31339752405 · `a11y-ci` 31339752415 · `secrets-scan` 31339752413 |

#### THE DECLARATION, JUDGED — 12 of 12 ROWS

**Every row held, and nothing moved except the image ids** — which is exactly
what §5 declared the most likely correct outcome to be.

| declared | before | after | verdict |
|---|---|---|---|
| `transcribe_visits` | 25 | **25** | ✅ unchanged |
| …signed | 16 | **16** | ✅ unchanged |
| `transcribe_md_patients` | 15 | **15** | ✅ unchanged |
| applied migrations | 95 | **95** | ✅ unchanged (B2 carries none) |
| `api_usage_events` | 1325 | **1325** | ✅ unchanged |
| …`unitsSource='mock'` | 0 | **0** | ✅ the mock seam did not leak |
| `sum(totalCostUsd)` | $26.3556 | **$26.3556** | ✅ no row rewritten |
| `ai_calls` | 1125 | **1125** | ✅ unchanged |
| `metadata->>'outcome'='failed'` rows | 0 | **0** | ✅ **the declared expected reading** |
| app image | `6388983335e1` | **`09d4b56410b7`** | ✅ declared change |
| worker image | `685a6c10bd15` | **`d1f6870ded64`** | ✅ declared change |
| co-tenants | 307·404·200·200·410 | **307·404·200·200·410** | ✅ unchanged |

⚠️ **THE ZERO IS THE DECLARED SUCCESS, NOT A DISAPPOINTMENT — AND THAT IS ONLY
CREDIBLE BECAUSE IT WAS WRITTEN DOWN FIRST.** §5 stated in advance that a jump in
`outcome='failed'` rows immediately after deploy would be a FINDING rather than a
success, because the wired branches fire only on a real vendor failure and
production is quiet. Had the number jumped, the declaration is what would have
stopped it being read as "B2 works". The behaviour is proven by the gate; the
deploy proves only that the code shipped without disturbing anything.

#### THE CODE IS IN THE SHIPPED IMAGES — STRUCTURAL, NOT ASSUMED

A green deploy says the containers restarted, not that they carry the change.

    worker  packages/ai/src/anthropic.ts   logFailedAnthropicUsage × 7
                                           (1 declaration + 6 call sites —
                                            cross-checks the enumeration)
            packages/ai/src/embed.ts       outcome: 'failed' × 1
    app     .next/server/chunks            outcome:"failed" × 7

⚠️ **The app container needed a different probe, and the first one silently
found nothing.** It ships a Next.js standalone build, so `packages/ai` is bundled
and `logFailedAnthropicUsage` — a LOCAL function name — is minified away. Grepping
for it returned zero, which is indistinguishable from "the code did not ship".
The marker that works is the **string literal** `outcome:"failed"`, which
survives minification and **did not exist anywhere before B2**. Same lesson as the
`NEXT_PUBLIC_*` bundle grep in AGENTS.md: probe for something that survives the
build, and positive-control the probe before believing its zero.

#### STANDING CHECKS, POST-DEPLOY

`assert-migrations-applied` 🟢 95/95 · `check-composite-fk` 🟢 · all nine
containers healthy · co-tenants unchanged.

#### ⛔ THIS DEPLOY RAN ON A 3-OF-4 CITATION. THE FOURTH LANDED GREEN AFTERWARDS.

**Stated because it is exactly the shape recorded against 2026-08-08, and it was
mine.** At `23:18Z`, when `deploy-prod.sh` ran, `274a4925` had `CI`, `a11y-ci`
and `secrets-scan` green and **`e2e` still `in_progress`**. `e2e` (31341501998)
completed `success` at ~`00:05Z`, so the deployed commit now carries a full
4-of-4 — but **that was luck, not process.**

⚠️ **THE PRE-MERGE CHECK WAS RUN AND WAS NOT THE RIGHT CHECK.** `main` was
correctly queried for in-flight runs *before* merging #570 — and it was clean.
What was never done is the query **after** the merge, against the **new head the
merge created**, which is the commit that actually deploys. The rule as written
says to check before *pushing*; the gap is that a merge PRODUCES a commit whose
citation does not exist yet, and the deploy is a *separate* act minutes later.

**The rule that would have caught it:** `deploy-prod.sh` takes `HEAD`, so the
citation must be re-verified **on `HEAD`, immediately before the deploy** — not
inherited from the pre-merge check on the parent. A 3-of-4 is not a citation, and
`e2e` is the arm most likely to catch a runtime regression in exactly the code
this item changed.

**Worth making mechanical rather than remembered:** the declaration gate already
refuses a deploy without a `<date>-<short-sha>.md`; the same gate could refuse a
`HEAD` whose four runs are not all `success`. That is a strictly-tightening
change, it needs no judgement at deploy time, and it would have blocked this
deploy for the ~45 minutes the citation still had to run. Recorded as a proposal,
not built — `deploy-prod.sh` is the production deploy path and changing it is its
own item with its own gate.

---

### ✅ B2 — the failure paths reach the durable meter — the BUILD row, 2026-08-09

**The build row.** ✅ **DEPLOYED 2026-08-09T23:18Z** — see the LIVE section
directly above for the judged declaration. The 42 surviving historical rows are
**not backfilled and never will be**: ruling 79 declined it and preserved them by
extract instead. Ruling row: RULINGS.md, the B2 entry, marked **PROVISIONAL**.

⚠️ **This row said "the 44 historical rows" when written. The figure was 42 at
that moment** and the difference is itself a finding — see "THE EVIDENCE IS
PERISHING" below.

#### THE ENUMERATION — 14 branches, and the list is the driver

The universe was written down **before** the scan, because "catch blocks" and
"`logApiUsage` call sites" are both the wrong set. The predicate is:

> every site that logs a **FAILED** vendor call **AND** holds the vendor's **own
> reported units** at that point.

The second conjunct decides the row and is observable in source: a failure site
carrying `inputTokens:` / `costUsdCents:` had a real `response` in hand.

| # | branch | units? | disposition |
|---|---|---|---|
| 1 | `anthropic.ts` tool-mode `AI_REFUSAL` | ✅ | **WIRED** |
| 2 | `anthropic.ts` tool-mode `JSON_PARSE_FAIL` (no tool_use block) | ✅ | **WIRED** |
| 3 | `anthropic.ts` text-mode `AI_REFUSAL` | ✅ | **WIRED** |
| 4 | `anthropic.ts` text-mode `JSON_PARSE_FAIL` | ✅ | **WIRED** |
| 5 | `anthropic.ts` `SCHEMA_FAIL` | ✅ | **WIRED** |
| 6 | `anthropic.ts` `completeText` `AI_REFUSAL` | ✅ | **WIRED** |
| 7 | `embed.ts` `EMBED_DIM_MISMATCH` | ✅ | **WIRED** |
| 8 | `anthropic.ts` outer catch (`anthropicComplete`) | ❌ | no row — stated in place |
| 9 | `anthropic.ts` outer catch (`anthropicCompleteText`) | ❌ | no row — stated in place |
| 10 | `embed.ts` outer catch | ❌ | no row — stated in place |
| 11 | `whisper-batch.ts` SDK threw | ❌ | no row — stated in place |
| 12 | `deepgram-batch.ts` `fetch` threw | ❌ | no row — stated in place |
| 13 | `deepgram-batch.ts` `!res.ok` | ❌ | no row — stated in place |
| 14 | `llm-mdm.ts` judge catch | ❌ | no row — **and it gained the `ai_calls` row it never had** |

Each of the seven wired branches also now passes the **vendor request id** to
the queryable column — it was already in scope and was being dropped purely
because the row said `success: false`.

#### ⚠️ BRANCH 14 WROTE TO NEITHER TABLE, AND THAT IS WHY §C.3's OWN QUERY COULD NOT SEE IT

`llm-mdm.ts`'s judge catch left a `log.warn` and nothing else. DISCOVERY's
diagnostic for this hole is a query against `ai_calls` — so **the branch was
invisible to the very instrument used to size the hole**, and `worker.ts`
pre-warms `judgeMdm` on every visit, making it the opposite of a rare path. It
now writes an `ai_calls` telemetry row. It writes no usage row, for the reason
below.

#### ⚠️ A STRUCTURAL CEILING, NAMED RATHER THAN PAPERED OVER

`withTimeout` **races** the SDK promise; it does not abort the HTTP request. So
on a timeout Anthropic may finish and bill the call while its token counts never
reach this process. **No code change can recover units that are on the other
side of the wire.** Sizing it needs a vendor invoice — which **B3 already needs**
for `nova-3-medical`, so one vendor conversation settles both. Recorded as a
known under-count rather than closed.

#### ⚠️ B2's GATE TEXT WAS CORRECTED, NOT QUIETLY DROPPED

The item says *"the Deepgram failure rows carry `audioSeconds`."* Written
2026-08-04 — **four days before `unitsSource` existed** — and it cannot be
executed literally under the provenance doctrine: billable seconds are
`raw.metadata.duration`, Deepgram's own measurement, and neither failure branch
has one. The local audio length is a **different quantity**, and writing it into
a `vendor` row would assert an observation nobody made. Full reasoning and the
reversal path: RULINGS.md, the B2 row.

#### THE GATE — TWO ARMS, because neither is sufficient

**`gate-b2-failure-paths-metered.test.ts`** — the census (13 tests). Every
failure site lands in exactly one of `BILLED_METERED` / `BILLED_UNMETERED` /
`NO_UNITS`; the three sum to the per-file failure count; the programme totals
assert **14 branches, 7 billed, 7 no-units**.

**`gate-b2-failure-paths-behavioural.test.ts`** — the behaviour (11 tests).
Every enumerated branch is actually **driven**, and the row's payload asserted:
tokens, `unitsSource`, the real request id, `metadata.outcome`, and that the
money is **> 0** rather than zeroed.

⚠️ **The census alone is a grep** — it cannot see a wired call passing the wrong
tokens or a fabricated id. **The behavioural arm alone is a hand-kept list of
eight tests** — it cannot see a fifteenth branch appearing in a file nobody
wrote a test for, which is precisely how B1-a's gate came to be green over a
universe missing four callers.

⚠️ **THE NEGATIVE CASES ASSERT THE BRANCH WAS REACHED BEFORE BELIEVING ITS
SILENCE.** "No usage row" is the easiest assertion in the world to satisfy by
accident — a test that drives nothing at all passes it. Each no-units test
asserts the `ai_calls` row **was** written in the same breath.

**Mutation-proven on two files**, and what was observed is what is recorded:

    remove logFailedAnthropicUsage from SCHEMA_FAIL → anthropic.ts failure site #4;  BILLED_METERED 5, expected 6
    remove the logApiUsage block from embed.ts      → embed.ts failure site #0;      BILLED_METERED 0, expected 1

⚠️ **The embed mutation doubles as a REAL-FILE positive control of the pairing
window.** `embed.ts` keeps a `logApiUsage(...)` on its success path further down
the same function; an unbounded search would have let that one satisfy the
failure site and gone **green on a genuinely broken tree**. It reported the
offender instead.

**Not claimed:** that the ratchet was watched going red-with-seven on the pre-B2
tree. Each wiring was mutated away individually and the count moved by exactly
one each time — the same mechanism at unit scale, and stated as the narrower
observation it is.

#### THE OTHER TWO GATES MOVED, AND THAT IS THEM WORKING

B2 was not written against them; they caught it.

| gate | moved | why |
|---|---|---|
| `gate-b1b-request-id-capture` | `anthropic.ts` FAILURE_NO_ID **8 → 2**; census **19 → 20** | six branches now capture the id; branch 14 added a site |
| `gate-b1b-no-fabricated-request-id` | usage sites **8 → 10**, `withoutId` **unchanged** | B2 added two writers and the no-fabrication ratchet held **without being touched** |

#### §C.4 — THE DURABILITY INVERSION IS SETTLED

**`api_usage_events` is the billing source.** `ai_calls` is hard-deleted by four
production paths, so choosing it would mean **a doctor deleting a visit erases
their own bill**. Measured this session:

    deleters of ai_calls ............ 5  (4 production + 1 e2e cleanup)
    deleters of api_usage_events .... 0
    FKs on api_usage_events ......... 2, both ON DELETE SET NULL
    FK on api_usage_events.visitId .. NONE — a visit delete cannot cascade a billing row

The no-deleter property was **already load-bearing before anyone wrote it down**
— ruling 77 had to state it as a guard *note* on `runStaleVisitCleanup`, i.e. an
obligation inferred from a goal. It is now
`scripts/check-billing-source-no-deleter.sh`, two arms:

1. **explicit deleters**, ORM and raw SQL, **positive-controlled against
   `ai_calls`** — if the control returns 0 the pattern is broken and the script
   reports `2`/can't-tell rather than a green;
2. **FK cascades**, read from `pg_constraint`, **which no grep can ever see**.

⚠️ **THE SCRIPT COULD NOT BE EXECUTED THIS SESSION** — see the owner action
below. Both arms were verified **inline** with granted commands (control 5,
target 0, two FKs both `SET NULL`), so the logic is measured; the script as a
single unit is not yet exercised.

#### WHAT THIS DOES NOT CLAIM

- ~~**Not deployed.** No production row has changed shape.~~ **Superseded — B2
  went live 2026-08-09T23:18Z, 12 of 12 declared rows judged.** True when written.
- **The historical rows are NOT backfilled** — and, since ruling 79, never will
  be. B2 stops the bleeding; it does not repair the past, and repairing it was
  DECLINED because a row minted now would claim a provenance regime that
  postdates its own call. They were preserved by extract instead
  (`docs/qa-reports/failed-but-billed-ai-calls-extract-20260809.md`).
  ⚠️ **The figure written here was "44"; it was 42 when written** — see "THE
  EVIDENCE IS PERISHING".
- **Not proven against a live vendor.** Every assertion is in-process against an
  SDK-shaped fixture. The live proof would be a smoke that forces a real
  refusal, which is not something a sanctioned smoke can reliably provoke.
- **The seven no-units branches are declared, not waived** — each with its
  reason, in the gate and at the code.
- **`audioSeconds` on Deepgram failures is not delivered**, deliberately. See
  above.

**Local:** `packages/ai` **468/468** · `tsc --noEmit` clean on `transcribe-md`.

#### ⚠️ OWNER ACTION — the new check cannot be run by the loop

`.claude/settings.json` enumerates the runnable scripts by name and **`Edit` on
that file is DENIED to the loop** — correctly: a session that can widen its own
permissions has none. So `check-billing-source-no-deleter.sh` ships unrunnable
by the unattended queue until a supervised session adds:

    "Bash(bash scripts/check-billing-source-no-deleter.sh:*)",

⚠️ **This refusal is NOT in MASTER.md's permissions table**, which is where a
session is told to look before treating a refusal as a finding. Two gaps worth
closing together: the entry above, and a row in that table saying
`.claude/settings.json` is deliberately un-editable and that a new check ships
with an owner action attached.

---

## Found on the way past — 2026-08-09, taking B2's deploy baseline

### ⛔ THE 44 FAILED-BUT-BILLED ROWS ARE NOW 42. THE EVIDENCE IS PERISHING WHILE WE DECIDE.

> ✅ **ANSWERED 2026-08-09 BY RULING 79 — THE BACKFILL IS DECLINED.** The
> measurement and the reasoning below STAND and are why the ruling was sought.
> **The execution directive at the end of this section is RETRACTED** — see the
> amendment appended to it. Preserved rather than deleted, per the ledger-union
> rule: this section records something that actually happened.

DISCOVERY §C.3 measured **44** rows matching `success = false AND inputTokens > 0`
in `ai_calls` on **2026-08-04**. Measured again for B2's §2.5 baseline on
**2026-08-09**: **42**.

    2026-08-04 ....... 44
    2026-08-09 ....... 42        net −2 in five days

`ai_calls` rows are created by vendor calls and removed by exactly four
production deleters. **Nothing else can lower the count** — so a net −2 means at
least two calls' worth of billing evidence was destroyed by the product working
normally, during the five days this programme spent deciding what to do about it.

⚠️ **THIS IS §C.4's ARGUMENT ARRIVING AS DATA, NOT AS REASONING.** The case for
`api_usage_events` being the billing source was written as a hypothetical — *"a
doctor deleting a visit erases their own bill."* It is not hypothetical. The
table demonstrably does not retain its rows, and the measurement above is the
proof, taken by accident while capturing a baseline for something else.

**And it prices a decision nobody has made yet.** Those 42 rows are the ONLY
record of those charges; they live exclusively in the perishable table; and the
population is shrinking on its own. The backfill into `api_usage_events` is a
production write and needs its own ruling under the standing shape for
owner-ruled prod mutations (ruling 59) — **but its window is closing whether or
not the ruling is sought**, and that fact belongs in the ask rather than in a
post-mortem.

⚠️ ~~**THE FIGURE TO MIGRATE IS WHATEVER THE COUNT IS AT EXECUTION TIME.** Never
44, never 42 copied out of this row. Ruling 59 says re-derive the population at
execution time and never copy it from the ruling; this is exactly the case that
rule exists for, and the drift from 44 is the demonstration.~~

> ⛔ **RETRACTED 2026-08-09 BY RULING 79. THERE IS NO MIGRATION TO EXECUTE.** The
> struck paragraph above is a live instruction for a production write that the
> ruling forbids: legacy `ai_calls` charges are **never inserted** into
> `api_usage_events`, because a row minted now would claim a provenance regime
> that postdates its own call. **The instruction is withdrawn; the measurement
> above is not** — the 44 → 42 attrition is what priced the decision, and ruling
> 59's re-derive-at-execution-time discipline remains correct for every mutation
> that *is* ordered.
>
> **The evidence was preserved the other way, and that ask is now closed:**
> `docs/qa-reports/failed-but-billed-ai-calls-extract-20260809.md` snapshots all
> 42 surviving rows (cost-accounting fields only — `errorDetails` is excluded as
> may-contain-PHI and is non-null on 42 of 42). ⚠️ **The rows keep perishing and
> nothing here stops that**, by design: the four deleters are correct behaviour.
> The extract is a copy taken before the originals go, not a rescue.

### ⛔ `gh run list --commit <FULL-SHA>` ALSO RETURNS `[]` FOR RUNS THAT EXIST BUT ARE `pending`

**A second, independent way the mandatory pre-push check answers "nothing in
flight" when something is.** Yesterday's finding was the SHORT sha; this one
happens with the full 40-character sha, which is the fix that finding
prescribed.

Measured this session, seconds apart, both with the full SHA:

    gh run list --commit 1bb6b8fd4cc39c1a3079324f408e06fe3c941e3a   → []
    gh run list --branch feat/b2-failure-paths-metered              → 3 runs on that SHA, status "pending"
    gh run list --commit 1bb6b8fd4cc39c1a3079324f408e06fe3c941e3a   → 4 runs        (moments later)

So there is a propagation window, immediately after a push, in which the runs
**exist and are queued** but the `--commit` view has not caught up. `--branch`
saw them the whole time.

⚠️ **THE FAILURE IS AGAIN IN THE DANGEROUS DIRECTION, AND THE WINDOW IS EXACTLY
WHEN THE CHECK GETS RUN.** The rule exists to stop a push cancelling somebody
else's evidence — and the moment that risk is highest is right after *they*
pushed, which is precisely the window in which `--commit` under-reports. A
session that queries, sees `[]`, and pushes destroys four queued runs while its
audit trail shows the check was performed correctly.

**The rule, tightened again:** a `[]` from `--commit` is believed **only** when
`gh run list --branch <branch>` also shows nothing for that SHA. Two views, and
the branch view is the one that is right first. The existing positive-control
requirement stands and would NOT have caught this on its own — the command was
working perfectly; it was answering about a set the server had not yet
populated.

⚠️ **AND THIS SESSION'S OWN ACCOUNT OF THE #568 PUSH WAS CORRECTED AGAINST THE
RECORD BY RULING 79'S COMMIT — READ THAT, NOT THIS SESSION'S FIRST TELLING.**
The push cancelled **THREE** runs, not one; and **"just batch it" was NOT
available**, because the docs commit was authored at **20:30:22Z — two minutes
INTO the run it cancelled.** The session logged the cancellation as deliberate,
which was the honest half; it then reached for the batching lesson, which did
not apply and quietly made the mistake sound more avoidable than it was.

**The rule that DOES apply: hold the first push until the session's remaining
commits are written.** Batching is only available to work that already exists.
It is also the SECOND occurrence of this shape in nineteen hours (#557 was the
first), and the by-commit check applies to **PR branches**, not only to `main`.

### 🟡 THE §2.5 DECLARATION GATE'S FILENAME CONVENTION IS NOT WHERE A SESSION LOOKS

`deploy-prod.sh` refused this deploy — correctly — because the declaration was
written as `docs/foundation/deploys/b2-declaration-20260809.md` and the gate
requires `<UTC-date>-<short-sha>.md`. **The gate did its job**; the convention is
recorded only at `deploy-prod.sh:67` and in the existing filenames, neither of
which a session reads before writing the document.

Cost was one refused deploy and a second PR cycle. **Nothing was built, migrated
or recreated** — the gate refuses before any of that, which is the property worth
noting: the failure mode was expensive in minutes and free in risk.

Worth a line in MASTER.md's deploy paragraph naming the path and the format, so
the declaration is written once. Recorded rather than fixed here — MASTER.md is
the loop's own brief and editing it mid-run is its own change.

---

## 🟩 B3 IS LIVE IN PRODUCTION — 2026-08-10T02:48Z. 2 of 3 Deepgram rates, and it says so.

Deployed from `main` @ **`748ec09a`** by `bash scripts/deploy-prod.sh`, under a
delta declaration written before the run:
`docs/foundation/deploys/20260810-748ec09a.md`. Log
`docs/deploy-logs/deploy-20260810T024833Z.log`. Rollback tags
**`:pre-b3-20260810`**, cut against the RUNNING ids `09d4b56410b7` /
`d1f6870ded64` and verified before the deploy started.

**Citation: 4 of 4 on the MERGE COMMIT `748ec09a`** — `CI` **31348665086** ·
`e2e` **31348665113** · `a11y-ci` **31348665105** · `secrets-scan`
**31348665103**. The PR-head citation on `918196a2` was 4 of 4 as well and is
recorded in the declaration for provenance; **it was not substituted for the
merge-commit one, and the deploy did not start until the merge-commit runs were
green.**

**§2.5 declaration judged: 20 of 20 rows.** The one-line reading declared in
advance — *"one new table with 44 rows, one new extension, one migration, two new
image ids, and nothing else at all"* — is exactly what happened. Clinical counts
byte-identical (25 · 16 · 15 · 196 · 197); `api_usage_events` **1325** and
`ai_calls` **1125** unmoved, which is the row that matters most here because B3
adds no writer.

⚠️ **ONE DECLARED ROW'S WORDING WAS WRONG AND IS CORRECTED IN THE JUDGEMENT, NOT
SMOOTHED OVER.** §4 said `audit_logs` may rise *"only by rows a **human** caused"*.
It rose 10619 → 10626 **before** the deploy, and no human caused it: seven
read-only rows at 02:00:15–02:00:32Z from two SYNTHETIC accounts. The substance
held — pre-deploy re-measure 10626, post-deploy 10626, so **the deploy wrote zero
audit rows** — but the predicate should have read *"activity outside this
deploy"*. See the finding below; the source of that traffic is **not
established**.

⚠️ **PREVIOUS-SESSION CITATION REPAIRED WHILE PASSING.** Session 02's ledger cited
B2's judgement row (PR #572) with runs `313432915xx` — those are on `4d39493d`,
the **PR head**, not on the merge commit `0e04a759`. The merge-commit runs existed
and were still in flight at STEP 0; they are now all `completed/success`:
`CI` **31345214465** · `e2e` **31345214463** · `a11y-ci` **31345214442** ·
`secrets-scan` **31345214444** on `0e04a759`. **The deployed commit `274a4925`
was always correctly cited** — this affects only the docs-only judgement row that
followed it.

### What shipped

`price_rates` — one vendor rate, for one period, with the source it came from.
**44 rows**, seeded from DISCOVERY §D as read on **2026-08-04**, every one
carrying its URL and its read-date.

| provider | rows | what |
|---|---|---|
| anthropic | 40 | 8 model-periods × 5 unit types |
| deepgram | 2 | `nova-3` pre-recorded + streaming |
| openai | 2 | `whisper-1`, `text-embedding-3-small` |

A rate is **never edited**. A change CLOSES the incumbent (`effectiveTo`) and
INSERTS its successor — which is the entire reason history stays stable, and the
property B3's gate proves.

### THE GATE, AND WHY THE ITEM'S OWN WORDING WOULD NOT HAVE BEEN ENOUGH

RELAY's gate for B3 reads: *"re-pricing a historical row does not change it — the
snapshot is proven by changing a rate and re-running."*

⚠️ **A lookup that always returned the same constant would pass that sentence.**
So every versioning assertion runs the period-correct lookup **and the obvious
wrong implementation** (`ORDER BY effectiveFrom DESC LIMIT 1`) side by side, and
asserts they **disagree** after the rate change. Measured, on a real published
rate change rather than an invented one — Sonnet 5's introductory rate ends
2026-08-31:

| priced at | versioned | latest-wins counterfactual |
|---|---|---|
| 2026-08-15 | **2 000 000** | 9 000 000 |
| 2026-09-15 | **3 000 000** | 9 000 000 |
| 2026-11-15 | 9 000 000 | 9 000 000 |

The two historical prices do not move; the new rate does apply to calls made
under it, so the table is not merely frozen. **If both columns ever agree, the
fixture cannot tell a versioned table from an unversioned one and the gate is
decoration.**

### THE THREE CONSTRAINTS ARE THE POINT — and all are mutation-proven

Twelve refusals were attempted on a **throwaway database**, each inside
`BEGIN … ROLLBACK`, and **every one named the right constraint** — a refusal is
evidence only when you know WHAT refused:

| attempt | refused by |
|---|---|
| a second `nova-3` pre-recorded rate over the same open period | `price_rates_no_overlap` |
| a period straddling the Sonnet 5 handover | `price_rates_no_overlap` |
| `published` with no `sourceUrl` / no `sourceReadAt` (2 shapes) | `price_rates_published_needs_source` |
| tokens priced per 1; audio priced per 1 000 000; an undeclared unit | `price_rates_unit_quantity_matches_type` |
| an undeclared provider / delivery mode / provenance (`'announcement'`) | the three vocabulary CHECKs |
| a period that ends before it begins; a negative rate | `price_rates_period_ordered`, `..._rate_non_negative` |

**And the guards are not over-strict** — five positive controls were accepted:
the `nova-3-medical` row arriving with `invoice` provenance, a `console`
provenance row with no url, the same model+unit under a different delivery mode,
a zero rate, and a **close-then-succeed handover at the same instant**.

⚠️ **One positive control was REFUSED and the refusal was correct — my label was
wrong.** The case described as *"a new version abutting an existing one"* left the
incumbent row still OPEN (`effectiveTo` NULL, so its range runs to infinity),
which genuinely overlaps. The properly-shaped version of the same intent — close
the incumbent, then insert the successor at that instant — was accepted.
Recorded rather than quietly re-run, because a reader who saw the first result
has no way to know the second replaced it.

### THE SEED PROVES ITS OWN APPLICATION, and that was proven able to go RED

The migration ends in a `DO` block asserting `total=44 / anthropic=40 /
deepgram=2 / openai=2`, that every row is `published` with url + read-date, and
that **`nova-3-medical` is absent**. Both arms were mutation-proven on a
throwaway database, and each mutation's application was asserted before its
result was believed:

- deleting one row → `total=43 (want 44) … openai=1 (want 2)`, exit 3.
- **a count-preserving SWAP** of the streaming row for a `nova-3-medical` one →
  `nova-3-medical must NOT be seeded here`. ⚠️ Worth noting because the first
  attempt at this proof — *adding* a medical row — was **shadowed by the count
  arm** and never reached the medical arm at all. An arm that only fires behind
  another arm is an arm nobody has tested.

### FOUR CORRECTIONS, AND THE FOURTH WAS NOT ON THE LIST

1. **Deepgram is $0.0077/min, not the in-code $0.0145** (~3.4× over).
2. **Anthropic has TWO cache-write classes**, 1.25× and 2×, seeded as separate
   `cache_write_5m` / `cache_write_1h` rows. `pricing.ts:claudeCostCents`
   collapses them into a single 1.25× — right today only because the one caching
   call site uses ephemeral 5m (DISCOVERY §C.8).
3. **Three Deepgram rates are owed, not one.** Two seeded; see the park below.
4. ⚠️ **FOUND ON THE WAY PAST — the embedding rate disagrees with itself by
   6.5×, and the DURABLE side holds the wrong number.** `api-usage.ts:66` prices
   `text-embedding-3-small` at **$0.13/M**; `pricing.ts:170` prices it at
   **$0.02/M**, which is what OpenAI publishes. Ruling 78(b) makes
   `api_usage_events` the billing source, so the meter's own table is the one
   carrying the unsourced figure. **DISCOVERY §D.3 verified only `pricing.ts`
   and declared the rate "correct"** — a true statement about one of two
   surfaces, which is the same shape as the Deepgram case sitting three
   paragraphs above it in the same document. **Impact today is exactly zero, for
   a reason worth writing down: the embed usage builder has NO CALLER**
   (`api-usage.ts:365`, grepped), so no embed row has ever reached
   `api_usage_events` — measured, **0** rows with `operation='embed'`, against
   **37** `text-embedding-3-small` rows in `ai_calls`. That absence is itself a
   B4 coverage gap.

**Neither in-code surface is patched.** SPEC §4.5 is explicit: changing them now
would silently re-base a year of historical `ai_calls` comparisons for no
benefit. The table supersedes them in B4/B6.

### WHAT B3 DOES NOT CLAIM

- **Nothing is billed from this table.** No code prices money through it; the
  meter still reads `pricing.ts` / `PRICING`. Repointing it is B4/B6.
- **It is 2 of 3 Deepgram rates.** `nova-3-medical` — the model that actually
  runs by default — is **absent on purpose**, and its absence is *asserted* by
  the migration so a later edit cannot quietly seed it from the undated post.
- **It does not claim any rate is CORRECT against the vendor.** A unit test
  cannot read deepgram.com. It claims each rate is present, integral, in-period,
  and carries a source somebody can go and check.
- **`api_usage_events` gains no snapshot column here.** SPEC §2.2 wants the usage
  row to record which price version priced it; that column arrives **with its
  writer**, in B4/B6. A column nothing writes is the half-shipped shape.
- **A lookup before 2026-08-04 returns `null`.** The seed starts at the READ-DATE
  because that is the day we know the rates held. Costs nothing — ruling 79 puts
  the meter's provenance regime at B0-a (2026-08-08).

### A MISSING RATE IS `null`, NEVER ZERO

`claudeCostCents` returns **0** for a model it does not recognise
(`pricing.ts:131`), so an unpriced model **silently bills nothing** — DISCOVERY
§D.3 names it. `rateAt` returns `null` and there is no `?? 0` in the path. This
is a requirement on B4/B6, not a detail: whoever wires the meter must decide what
a refusal means, and must not reach for a zero.

### THE WATCHED SET — diffed, not assumed

⚠️ **A price table is the artefact where coverage fails invisibly.** A rate keyed
on `claude-opus-4.8` instead of `claude-opus-4-8` matches nothing, errors
nothing, and a table that prices *no* model reports the same zero missing rates
as a complete one — if you only ask the table about itself.

So the model list is scanned from **source**, not from the table: the three
shapes a model id reaches a vendor through (`process.env.X || 'id'`,
`DEFAULT_*_MODEL = 'id'`, `model: 'id'`), across `packages/ai/src` and
`apps/transcribe-md/src`, tests excluded. The scanner is positive-controlled
against the two live defaults, and **mutation-proven**: misspelling
`claude-sonnet-4-6` across all five of its rows reddens the gate and names the
**seven** files that emit it.

`KNOWINGLY_UNPRICED` has exactly one entry — `nova-3-medical`, with its reason —
and a third assertion keeps the park list from going stale: every entry must
still be emittable **and** still unpriced, so a park row for a model that has
since been priced fails rather than lingering as a comment.

### PARKED — `nova-3-medical`, and now the TIER too

**The trigger is unchanged: the vendor answers.**
`docs/foundation/B3-deepgram-rate-request.md` is written and staged; sending it
is an owner action.

⚠️ **A SECOND QUESTION JOINED IT WHILE SEEDING.** Deepgram publishes both
pay-as-you-go and Growth-tier rates ($0.0077 / $0.0065 pre-recorded), and
**nothing in DISCOVERY establishes which tier this account is on.** The seed uses
PAYG and says so in the row's `note`. That is the higher number, so a wrong guess
**over**-states cost — and with `charge = cost × 3 / 2` an over-stated cost
over-bills a doctor, which is the direction that matters. The request now asks
for the tier by name. **One vendor conversation still settles everything:** this
tier, the `nova-3-medical` rate, ruling 78(a)'s failed-request question, and
B2's `withTimeout` under-count all point at the same invoice.

### Verification performed

| | |
|---|---|
| unit suite | **3288 passed**, 4 skipped, 265 files — the suite CI runs |
| B3 gate | **26 passed**; 3 mutations, reddening 1, 1 and 6 assertions respectively |
| **the rates themselves, checked independently of my transcription** | Every seeded Anthropic row reproduces DISCOVERY §D.1 **and satisfies the vendor's own stated multipliers** — `cache_write_5m = 1.25 × input`, `cache_write_1h = 2 × input`, `cache_read = 0.1 × input` — computed in SQL across all **8** model-periods, `ok` on 24 of 24. ⚠️ Worth doing because *"I typed the numbers off the table correctly"* is the one claim in this item that no test can make, and the multiplier relation is an arithmetic check that does not depend on my eyes |
| typecheck | `tsc --noEmit` on `apps/transcribe-md` — **0 errors** |
| migration, standalone | applies to an empty database; 44 rows; all `DO`-block assertions pass |
| migration, **in sequence** | **all 96 migrations applied in order** to a fresh database, B3 last, 44 rows present. A standalone apply does not prove this |
| schema drift | `prisma migrate diff --from-empty --to-schema` generates a `CREATE TABLE` **byte-identical** to the migration's, and the same index name. **UNDECLARED-PLAIN = 0** for this table; the EXCLUDE and the six CHECKs are the permitted inexpressible residue and are declared beside the model |
| production | **untouched.** No write, and no read beyond the census figures quoted above |

### 🟠 FOUND ON THE WAY PAST — THE QA STACK IS A MIGRATION BEHIND PRODUCTION

Measured while looking for somewhere to apply the migration in sequence:

```
repo migrations (before B3)        95
prod  _prisma_migrations           95      OK
QA    _prisma_migrations           94      MISSING 20260809010000_b1a_ai_calls_request_id
```

**QA is where behavioural proofs live** precisely because production's population
cannot exercise them — so a QA whose schema is not production's can prove
something about a database nobody runs. B1-a's `ai_calls.requestId` is absent
there.

⚠️ **AND NOTHING WATCHES IT.** `scripts/assert-migrations-applied.sh` is
**prod-scoped**; it returned 🟢 `95 in repo, 95 rows recorded` in this session's
STEP 0 while QA sat one behind. That is the watched-set failure in its cleanest
form — the check is flawless over a universe that does not contain the thing that
was wrong.

Also measured: the QA **image** is older still — `/app/packages/db/prisma/migrations`
inside `meddoc-qa-transcribe-md-1` stops at `20260807060000_t7_tenancy`, so the
container predates B0 entirely while its database has B0 applied.

**Not fixed here** — bringing QA up needs a rebuild, which is its own change and
not B3's. Recorded with its evidence. The cheap durable fix is a `PG_CONTAINER` /
`PG_DB`-parameterised second arm on `assert-migrations-applied.sh`, so the QA
stack is watched by the same script that already watches prod.

#### ✅ CLOSED 2026-08-10 — and the prescribed fix was NOT the fix

**The drift had grown to TWO** by the time it was taken up —
`b1a_ai_calls_request_id` **and** `b3_price_table`, the second landed by the very
session that recorded this finding. A drift nobody watches does not hold still.

⚠️ **THE PRESCRIPTION ABOVE WAS WRONG, AND CHECKING BEAT BUILDING.**
`assert-migrations-applied.sh` has accepted **`[container] [db]` since the day it
was written** — line 36 of its own header says so. No parameterisation was
needed and none was written. What was missing was never a capability; it was an
**invocation**. STEP 0.5 called it bare, bare means production, and so the QA
stack was never once looked at. **A capability nobody invokes is
indistinguishable from one that does not exist** — and this is the watched-set
failure arriving through a *parameter default*, which is a quieter door than a
model list.

Had the prescription been followed literally, the session would have added a
second way to do something the script already did, and the standing check would
*still* have been aimed only at production.

⚠️ **THE BARE INVOCATION IS UNCHANGED, AND THAT IS THE LOAD-BEARING DECISION.**
`scripts/deploy-prod.sh:118` gates the **production deploy** on the bare call.
Folding QA into it would let a stale synthetic container **block shipping** —
so the QA coordinates went behind an explicit `--qa` flag and the two callers
keep their two different questions. Found by enumerating callers *before*
widening a shared thing, per AGENTS.md; the widening that reads as obviously
harmless was the one with a deploy gate on the far end.

**What shipped**

| | |
|---|---|
| `assert-migrations-applied.sh --qa` | QA coordinates ON the component (`meddoc-qa-postgres-1` / `meddoc_qa_test`), not in a runbook line a reader must remember |
| bare invocation | **byte-identical in behaviour** — prod only, `0/1/2` as before |
| `MASTER.md` STEP 0.5 · `AGENTS.md` | the QA arm is now *invoked*, which was the whole defect |

**Proven in both directions, which is the point** — a check that only ever goes
red is a decoration:

```
A  bare          → 🟢 96/96 prod                 exit 0   (deploy contract intact)
B  --qa (before) → 🔴 2 UNAPPLIED on QA          exit 1   (the real drift, unfaked)
C  positional    → 🔴 same 2                     exit 1   (backwards compatible)
D  --qa <stray>  → ⚠️  refuses the argument       exit 2   (no silent ignore)
E  bad container → ⚠️  not present                exit 2
F  --qa (after)  → 🟢 96/96 QA                    exit 0   ← IT MOVED WHEN THE WORK SUCCEEDED
```

**And the stack was actually brought up, not just watched.** QA's *image* was
older than its database — 92 migration dirs, stopping at `t7_tenancy`, predating
B0-a through B3. `db-migrate`, `transcribe-md` and `transcribe-md-worker` were
rebuilt and recreated; the image now carries **96**, and the database **96**.

⚠️ **`check-qa-mock-posture.sh` WAS RE-RUN AFTER THE RECREATE, NOT BEFORE.** It
reads the **running containers** (rule F4), so a rebuild is exactly the event
that could have re-inherited a real key from the shared `.env`. Still 🟢 —
`MOCK_AI_CALLS=true` and all three vendor keys dummies, in the live containers.

**What this does NOT claim.** It does not prove any B4 gate, and it does not make
QA a proof of production. It removes one excuse: **B4's audio path can now be
exercised against a QA stack whose schema is production's.**

**Citation — 4 of 4 on `2017adff3e41fe52f4d0471fddd859a59942a3ec`** (PR #582),
produced by `check-citation.sh`, not typed:

    · `CI`           31369243875 a1
    · `e2e`          31369243845 a1
    · `a11y-ci`      31369243857 a1
    · `secrets-scan` 31369243847 a1

**NOT DEPLOYED, and no §2.5 declaration is owed.** The change is a host script
and three markdown files; nothing reaches a shipped image, so there is no delta
to declare and nothing to roll back. The QA stack rebuild is not a deploy — the
prod stack was untouched throughout and its co-tenant statuses are unchanged
(`app` 307 · `admin` 404 · `quillmd` 200 · `www` 200 · `pro` 410).

⚠️ **The PR head carried `e2e` on `a2` and the merge commit did not.** The head's
first `e2e` died on `npm error code ECONNRESET` during `npm ci` in the worker
image build — an **external fault**, not a product defect, on a branch that
changes no code the build compiles. Named rather than absorbed, and fixed
independently by #583 while this PR was in flight.

### 🟠 FOUND ON THE WAY PAST — SOMETHING ON THIS HOST AUTHENTICATES TO PRODUCTION ON A SCHEDULE, AND ONE OF ITS LOGINS FAILS

Surfaced by the §2.5 baseline, which is exactly what that discipline is for: a
number moved, and the declaration made it a question instead of a shrug.

Between the baseline (01:15Z) and the pre-deploy re-measure (02:47Z),
`audit_logs` went **10619 → 10626**. The seven rows:

```
02:00:32Z  LOGIN_FAILED       success=f   qa-bundle@quillmd.local
02:00:29Z  VIEWED_VISIT_LIST  success=t   qa-bundle@quillmd.local   (x2)
02:00:29Z  LOGIN_SUCCESS      success=t   qa-bundle@quillmd.local
02:00:15Z  VIEWED_VISIT_LIST  success=t   qa-tmd@quillmd.local      (x2)
02:00:15Z  LOGIN_SUCCESS      success=t   qa-tmd@quillmd.local
```

All read-only, both accounts synthetic, and the unmoved clinical counts confirm
nothing was written. **This is not a PHI event and it did not affect the deploy.**

⚠️ **WHAT IS NOT ESTABLISHED IS WHERE IT CAME FROM.** The obvious candidate is
`nightly-tests.yml` — cron `0 2 * * *`, and it targets
`TEST_APP_URL=https://app.quillmd.com`, i.e. **production**. But `gh run list
--workflow nightly-tests.yml` shows **no run for 2026-08-10**, and a full
`gh run list` shows **no GitHub workflow at all** in that window (nearest:
02:01:50Z for this merge commit, 02:10:12Z for PR #574). So the traffic came from
**the host**, not from CI.

**I could not enumerate host cron, and both refusals are findings in their own
right** — see the session log: `crontab -l` is not granted and is **not in
MASTER.md's known-constraints table**, and the sandbox restricts `ls` to
`/opt/meddoc-pro` so `/etc/cron.d` is unreadable.

**Two things for a person:**

1. **The `LOGIN_FAILED`.** A scheduled process that authenticates to production
   and fails one of its logins is either a broken smoke nobody reads or an
   unowned job. Either way it has been failing quietly.
2. ⚠️ **The last two `nightly-tests` runs both `completed/failure`** (2026-08-09
   and 2026-08-08; 2026-08-07 was the last success). That is a required-adjacent
   signal that has been red for two days with nothing in the ledger about it.
   **Not investigated here** — out of B3's scope, and named rather than absorbed.

### 🟠 FOUND ON THE WAY PAST — A RUN ID IS NOT A FULL CITATION. **THE ATTEMPT NUMBER IS PART OF IT.**

This is the useful half of an otherwise unremarkable flake, and it applies to
**every citation this programme has ever taken.**

**What happened.** At 02:53Z, `CI` on `main` @ **`6247aa33`** — the owner's PR
#574, `.claude/settings.json` only — **failed**. First CI failure on `main` in
twelve runs. At 03:20Z it was re-run and **succeeded on attempt 2**.

**What `gh` says about it now:**

```
$ gh run list --branch main
CI  completed/success  6247aa33            <- run id 31351013424
```

⚠️ **THE RUN ID IS UNCHANGED AND THE FAILURE IS INVISIBLE.** A re-run does not
mint a new id; it increments `run_attempt` on the same one. So a citation
recorded the way this ledger records them — four workflow names, four run ids —
**cannot distinguish "green" from "green on the second try."** The only view that
can:

```
$ gh api repos/<owner>/<repo>/actions/runs/<id> --jq .run_attempt
2
```

**Applied immediately to this session's own claim, rather than left as advice:**
all four of B3's merge-commit runs on `748ec09a` were checked and are
**`attempt=1`**. The citation in this section is clean, and now *known* to be
clean rather than assumed.

**Recommendation, not executed here:** a citation should record
`<name> <run-id> a<attempt>`. That is a change to how MASTER.md defines a
citation, and MASTER.md is the loop's own brief — editing it mid-run is its own
change (the same reasoning session 02 applied to the §2.5 filename note).

#### The flake itself — mechanism named, deliberately NOT re-run by me

**All 3288 tests passed** (265 files). The job failed *after* them on:

```
EnvironmentTeardownError: [vitest-worker]: Closing rpc while "onUserConsoleLog" was pending
  This error originated in "src/lib/note-template-parse/__tests__/parse-note-to-template.mock.test.ts"
```

reported twice as `Unhandled Rejection`, exit 1. Vitest's worker RPC channel
closes while a console-log message is still in flight; that test deliberately
emits console output (`[signup] create failed`, `[waitlist] write failed`). It is
timing-sensitive, so it is likelier on a loaded shared runner. **Not a product
defect.**

⚠️ **THE ATTRIBUTION IS DECISIVE, AND WORTH STATING BECAUSE THE OBVIOUS SUSPECT
WAS MINE.** B3 had just landed, and its gate test is a new file in the same
worker pool that imports `price-table.ts`, which imports the prisma client at
module load. That is a plausible way to shift teardown timing. **It is
nonetheless ruled out by the run history:** `748ec09a` — which contains *all* of
B3's code, including that import — passed the identical suite 52 minutes earlier,
and `6247aa33` differs from it by **`.claude/settings.json` alone**, five lines,
in a file no test reads. **There was no code delta between the green run and the
red one**, so no code change can explain it.

**I did not re-run it** — canon forbids re-run-and-hope, and the owner's re-run
is what produced the attempt-2 evidence above. **Nothing is changed here:** one
occurrence in twelve is not a pattern, and editing shared vitest config
(`teardownTimeout`, `pool`) to chase a first-occurrence flake is a larger risk
than the flake. **If it recurs, the fix is the test's console emission or the
teardown timeout — not another re-run.**

---

## Found on the way past — 2026-08-10, session 04

### ⛔ THE MERGE-CANCELS-EVIDENCE CLASS FIRED **THREE TIMES IN ONE MORNING**, AND EVERY PAIR WAS **FOUR SECONDS** APART

AGENTS.md already carries this class at four occurrences and prices it *"by its
worst instance, not its cheapest."* Three more landed inside two hours, all
observed live while this session was waiting on gates:

| pair | merged | what died |
|---|---|---|
| #576 → #578 | `05:15:24Z` → `05:15:28Z` | #576's **four** runs, all `cancelled` at 5–7s |
| #580 → #581 | `06:52:42Z` → `06:52:46Z` | #580's `e2e`, `cancelled` at 7s |
| #583 → #584 | `07:26:06Z` → `07:26:10Z` | #583's **four** runs — *and* `afabbaf1`'s `e2e` at 34 min |

⚠️ **THE FOUR-SECOND SPACING IS THE WHOLE FINDING.** These are not two sessions
racing; that is one actor merging a queue back to back. The canon's existing
advice — *batch, and check two views before pushing* — **does not reach this
case**, because the second merge is not a stray push and there is nothing to
batch: they are two legitimately separate PRs. **The applicable habit is
different: after merging, WAIT for the merge commit's runs before merging the
next PR**, or accept in writing that the first PR will carry no citation of its
own.

⚠️ **AND THE THIRD ROW COST A CITATION THAT WAS BEING DELIBERATELY WAITED FOR.**
This session read the two views, saw #581's runs in flight on `afabbaf1`, and
**chose to wait rather than merge** — precisely as the rule prescribes, and
specifically so that `afabbaf1`'s green would discharge #580's cancelled `e2e`.
The #583/#584 pair then cancelled that very run at 34 minutes. **The rule was
followed correctly by one party and defeated by another**, which is the argument
for making it a merge-side habit rather than a push-side one.

**Discharged, not lost:** `51751c0e` (#584) completed **4 of 4 green**, and it
contains #580, #581 and #583, so the descendant carries them all. That is the
recovery pattern working — but it works by luck of ordering, not by design.

### 🟠 `npm ci` DIED ON `ECONNRESET` TWICE IN TWO HOURS — FIXED INDEPENDENTLY MID-SESSION

`e2e` failed on PR #579 (`04:19Z`) and again on PR #582 (`06:15Z`), both
`npm error code ECONNRESET` / `network aborted` inside the **worker image build**
(`Dockerfile.worker`, `npm ci`), on branches that change no code the build
compiles. **An external fault, named rather than absorbed** — the only available
cure is a re-run, and each one costs a ~40-minute gate cycle.

**Already fixed, by #583** (`fix/npm-ci-registry-retries`), which landed while
#582 was in flight and gave every `npm ci` a retry budget that outlasts a
registry blip. Recorded here so the two failures above are explained rather than
remembered as flakes, and so the fix is attributable if it ever regresses.

### 🟠 STILL OPEN, AND NOT RE-ATTEMPTED HERE

Session 03's findings 1 and 2 are **unchanged and still owed a person**:

- **Something on this host authenticates to production on a schedule and one of
  its logins FAILS.** Not investigated — `crontab -l` is still not granted and
  the sandbox still blocks `/etc/cron.d`. Both refusals remain absent from
  MASTER.md's table.
- **`nightly-tests` has failed three consecutive nights** — 2026-08-08, -09 and
  -10 — auto-filing **#548, #559, #577**, all still open. Last success
  **2026-08-07**. It targets **production**. Deliberately not triaged here: its
  detail lives in a downloadable artefact, which is scratch this session cannot
  reap.

  ⚠️ **A first draft of this row said FOUR nights and a fourth issue.** It was
  wrong: session 03 had already counted the 08-10 run, and this session assumed
  a new failure had appeared overnight without querying. **Re-measured before
  committing** — `gh run list --workflow nightly-tests.yml` gives 3 failures
  after 3 successes, and `gh issue list` gives exactly three issues. A count
  carried forward from another session's report and then incremented by
  assumption is a fabricated number, however small the increment.

---

## 🟩 B4 STEP 1 IS LIVE IN PRODUCTION — 2026-08-10T12:59Z

Deployed from `main` @ **`c8a55986`** by `bash scripts/deploy-prod.sh`, under a
delta declaration written before the run:
`docs/foundation/deploys/20260810-c8a55986.md`. Log
`docs/deploy-logs/deploy-20260810T125411Z.log`. Rollback tags
**`:pre-b4s1-20260810`**, cut against the RUNNING ids `ac34bf1c7718` /
`7944e7a1ff00` and verified before the deploy started.

**Citation: 4 of 4 on the MERGE COMMIT `c8a55986`**, produced by
`check-citation.sh` and not typed — every line `a1`, so nothing was re-run:

    · `CI`           31387144318 a1
    · `e2e`          31387144306 a1
    · `a11y-ci`      31387143818 a1
    · `secrets-scan` 31387143766 a1

The PR-head citation on `17c6553b` was also 4 of 4 and is recorded in the
declaration for provenance; **it was not substituted for the merge-commit one,
and the deploy did not start until the merge-commit runs were green.**

### THE DECLARATION, JUDGED — 12 of 12 ROWS, AND THE ONE-LINE READING HELD

The declared reading was *"nothing moves but the image ids"*. That is exactly
what happened.

| quantity | declared | measured after | verdict |
|---|---|---|---|
| `transcribe_visits` | 25 unmoved | **25** | ✅ |
| signed visits | 17 unmoved | **17** | ✅ |
| `transcribe_md_patients` | 16 unmoved | **16** | ✅ |
| `users` · `practices` | 196 · 197 | **196 · 197** | ✅ |
| `api_usage_events` | 1325 | **1325** | ✅ the row that mattered most |
| `ai_calls` | 1126 | **1126** | ✅ |
| `price_rates` | 44 unmoved | **44** | ✅ |
| applied migrations | 96 → 96 | **96** | ✅ code-only, as declared |
| `audit_logs` | deploy writes ZERO | **10690 → 10690** | ✅ |
| app image id | MUST change | `ac34bf1c7718` → `78a863205cc7` | ✅ |
| worker image id | MUST change | `7944e7a1ff00` → `b7d5f8fb4883` | ✅ |
| co-tenants | 307 · 404 · 200 · 200 · 410 | **307 · 404 · 200 · 200 · 410** | ✅ |

**The baseline was captured twice** — 12:53:04Z and 12:54:06Z, immediately before
the run — and both readings were identical, so the comparison is against a
stationary baseline rather than a drifting one.

`db-migrate` reported *"96 migrations found / No pending migrations to apply"*,
which for a code-only deploy is the declared outcome rather than the warning it
would be otherwise. Standing checks after: **all nine green**, including
`assert-migrations-applied` **both bare and `--qa`** at 96/96. 9 of 9 containers
healthy.

### THE CODE IS IN THE SHIPPED IMAGE — STRUCTURAL, NOT ASSUMED

Verified inside the running worker container, not on the host:

- `mockEmbedResponse` present in `/app/packages/ai/src/embed.ts` and `mock.ts`.
- ⚠️ `transcribe_realtime` still returns **2 hits** in the shipped
  `api-usage.ts` — **both are the doc comment explaining the removed literal.**
  The executable form, `operation: 'transcribe_realtime'`, returns **0**.

That distinction is the substring trap again, and it is recorded because the
naive grep would have read as *"the fix did not ship"*. Match the executable
token, never the bare word — a file's comments are where the word you are
grepping for is guaranteed to appear.

### WHAT THIS DEPLOY DOES NOT CLAIM

- **It does not make `tm_embed` work.** That path still fails on a dead vendor
  credential; the zero `openai` rows in `api_usage_events` remains a CORRECT
  reading. Parked for the owner.
- **It does not prove the audio pipeline in production.** Production has no audio
  visits; the proof is the unit gate, and the QA per-stage run is step 2.
- **It shipped no behaviour change to any production path.** Everything B4 step 1
  alters is reachable only under `MOCK_AI_CALLS`, which production never sets —
  `mockRes ?? await fetch(...)` with `mockRes = null` **is** the original call.
  The only production-visible difference is the CONTENT of a future Deepgram
  usage row, and prod has produced 3 in its entire history.

---

## ✅ B4 STEP 1 — the mock boundary reaches EVERY vendor, and the Deepgram labels stop lying — 2026-08-10

**B4's gate is *"one full QA pipeline run produces one event per stage, counted
against the enumerated stage list"*. Before this change that gate was
unsatisfiable for three stages, by construction.** B0-a moved the mock boundary
below the meter for `anthropic.ts` and fixed ONE vendor; `deepgram-batch.ts` and
`embed.ts` kept their short-circuits ABOVE `logApiUsage`.

⚠️ **AND IT WAS ALREADY WRITTEN DOWN, AS AN EXEMPTION.**
`gate-mock-suite-stubs-the-db.test.ts` carried, in prose:

> `embed.ts:72` returns `mockEmbed()` under mock, ABOVE the `logApiUsage` calls
> at `:123`/`:162` — **the meter is never reached.**

That is the defect, recorded accurately, and lived with. A good example of the
class: the sentence was true when written, nothing ever re-read it against the
item that needed it, and no check could — an exemption's *reason* is prose.

### WHY IT MATTERS MORE THAN "a mock does not meter"

Every production visit is `text_notes`, so **the audio path is unexercised in
production** — RELAY's own B4 text says production cannot be the proof. QA was
therefore the only place L1/L1b could ever be metered, and QA was exactly where
the meter was blind. The gate would have returned *"no audio events"*, which
reads as nothing-to-record rather than nothing-is-wired: the same
zero-is-indistinguishable failure B0-a exists to kill.

### WHAT LANDED

| file | change |
|---|---|
| `deepgram-batch.ts` | the fixture is handed back as a `Response`, so `res.ok`, `res.json()`, duration extraction and the meter are the **same lines** on both paths |
| `embed.ts` | same shape; `mockEmbedResponse()` returns a vendor-shaped response, `getClient()` stays inside the non-mock arm so a mocked run needs no credential |
| `api-usage.ts` | `buildDeepgramUsage` gains **required** `modelName` + `operation` |
| `embed-mock.test.ts` | stubs `@meddoc/db` — it now reaches the meter |
| `gate-mock-suite-stubs-the-db.test.ts` | the stale exemption removed, with the reason it could not have been caught automatically |

**A `Response`, rather than a mock-only metering branch, is the load-bearing
choice.** A parallel branch is a gate that can pass while production's real path
stays broken; identity of code is what makes a QA run evidence about production.

### THE GATE — 9 arms, and the mutation matrix

`packages/ai/src/__tests__/gate-b4-mock-boundary-all-vendors.test.ts`

| mutation | applied? | result |
|---|---|---|
| **M1** — restore Deepgram's pre-B4 early return | asserted 1 occurrence | **5 of 9 RED** (every Deepgram mock arm) |
| **M2** — drop the call-site `mocked ? null :` id guard | asserted 1 occurrence | ⚠️ **STAYED GREEN — see below** |
| **M2b** — remove the WRITER's mock-row `requestId` normalisation | asserted 1 occurrence | **1 RED**, `expected 'mock-deepgram-request' to be null` |
| **M3/M4** — restore both label literals | asserted 2 occurrences | **3 RED** (all LABELLED arms) |
| **M5** — restore embed's pre-B4 early return | asserted 1 occurrence | **2 RED** (both embed arms) |
| **M6** — hardcode `unitsSource: 'mock'` | asserted 1 occurrence | **1 RED** (the REAL arm — the both-directions proof) |

Every mutation asserted its own application before its result was believed, and
every one was restored with the restoration verified.

Unit suite: **3304 passed / 4 skipped**, before and after.

### ⚠️ M2 IS THE FINDING — A GATE ARM WHOSE TITLE WAS NARROWER THAN WHAT IT MEASURED

The arm was titled *"the CALL SITE refuses the fixture's id"*, and
`deepgram-batch.ts` carried a `mocked ? null : …` guard to match. **Removing that
guard left the arm GREEN.**

The cause: `logApiUsage` **already** normalises every mock row to
`requestId: null` (`api-usage.ts:168-171`), and B1-b step 2 put it on the WRITER
for the reason that applies verbatim here — *"five builders exist today and a
sixth will not remember."* So the arm was never watching the call site. It was
watching the writer, and only its NAME said otherwise.

Two corrections, both taken:

1. **The redundant call-site guard is REMOVED.** A per-caller copy of a
   writer-side invariant is the hand-kept list that rule exists to prevent — and
   worse, it made `deepgram-batch.ts` *look* like the thing keeping the row legal
   when it was not. Anyone later "simplifying" the writer would have found a
   green suite.
2. **The arm is re-titled for what it measures** — the END-TO-END property: an id
   IS available upstream and the row that lands still carries NULL. That is worth
   guarding, because it is what keeps mocked Deepgram rows legal at all. Its live
   mutation is M2b, on the writer.

**Neither the arm nor the guard was wrong about anything; they were correct about
the wrong subject.** It was found only because the mutation was run — which is
the entire argument for running them.

### THE FIXTURE KEEPS ITS `request_id`, ON PURPOSE

`MOCK_DEEPGRAM_BATCH.metadata.request_id` is `'mock-deepgram-request'`. Deleting
it would make the arm above **vacuous** rather than passing for a good reason, so
the gate opens with a **negative control** asserting the fixture still supplies
one. Fixture and test now name each other.

Why it matters: a mock row carrying an id violates
`api_usage_events_request_id_requires_vendor`, and because `logApiUsage` is
fire-and-forget the violation is **swallowed** — the row simply never exists. The
audio stage would go missing from a QA run with every line of code looking
correct.

### ⚠️ FOUND ON THE WAY PAST — `tm_embed` HAS NEVER SUCCEEDED IN PRODUCTION

Measured while enumerating stages, not looked for:

| table | `tm_embed` / openai |
|---|---|
| `ai_calls` | **38 calls, 2026-07-07 → 2026-08-10, `success=false` on ALL 38**, `errorCode='ERROR'` |
| `api_usage_events` | **zero `openai` rows, ever** |
| `doctor_edit_patterns` | 17 rows, **0 carry an embedding** (17 signed visits) |

`OPENAI_API_KEY` **is set** in the worker (`sk-proj…`, 164 chars), so this is not
an unset-credential fault; `errorCode='ERROR'` is `err.name.toUpperCase()` on a
generic `Error`, consistent with a 401/429 from the vendor.

⚠️ **AND IT WAS DIAGNOSED 39 DAYS AGO, WITH A NAMED OWNER ACTION.**
`docs/qa-reports/audio-path-verification-20260702T155110Z.md:54` says, in bold:

> the current prod `OPENAI_API_KEY` is dead (401), which also breaks the Doc
> Editor evals today. **Kasra: rotate/replace the key.**

That is **2026-07-02**. The first failed `tm_embed` is **2026-07-07**. The key is
still dead today.

⚠️ **THIS IS THE PRICED-BY-THE-SYMPTOM CLASS AGAIN, AND THE PARALLEL TO THE
65-DAY 🟢 IS EXACT.** The 07-02 report priced the item by the loudest thing it
could see — *"breaks the Doc Editor evals"*, a dev-tooling annoyance — when the
asset behind the symptom was **a vendor credential two product features depend
on**. The second feature was never named, because on 07-02 it had not started
failing yet: `tm_embed` only began five days later. So the follow-up was filed
against the wrong noun, and every reader since has triaged it as an eval problem.

Renamed after the asset, per canon: **`prod OpenAI credential is dead — kills
tm_embed AND the Doc Editor evals`**. Nothing else about the item changes; the
name is what decides whether it gets picked up.

**The meter is CORRECT to hold no row** — no vendor units were ever reported, and
B2 ruled a branch meters iff it holds vendor-reported units. So this is not a
metering defect. It is a **product feature silently dead for 34 days**: the
per-doctor edit-pattern capture writes its row and stores a NULL vector every
time, and nothing anywhere is in an error state.

⚠️ **DELIBERATELY NOT ACTED ON. PARKED — owner action.** Establishing whether the
key is expired, unfunded or revoked needs either a vendor call or the vendor's
console. The first is outside the money envelope (which pre-approves **Anthropic**
balance probes only); the second needs a person. **What would unpark it:** the
owner confirming the key's status, or authorising one minimal OpenAI probe.

⚠️ **AND IT CHANGES WHAT B4 STEP 2 CAN CLAIM.** A full QA run will now meter
`tm_embed` (the fixture path works), but **production will keep showing zero
`tm_embed` meter rows until the key is fixed** — and that zero will be CORRECT. A
step-2 gate that reads production and expects a row per stage would fail on a
true statement about a broken vendor credential. The stage list must carry this,
or the gate reports a metering bug that does not exist.

### ⚠️ THE RESTORE THAT ATE ITS OWN CORRECTION — new costume for a known class

Canon says *"restore from git" and "restore from backup" are not the same
operation*. `mkdir`, `cp` and writes to `/tmp` are all **denied** to this session
(finding below), so the scratch-copy form was unavailable and the work was
**committed first** instead — a strictly stronger backup, and the right call.

**Then the M2 finding arrived and `deepgram-batch.ts` was edited again, after the
commit, without re-staging.** The next `git checkout -- <file>` — restoring from
the index — silently reverted that correction along with the mutation. Detected
by grepping for the guard afterwards; re-applied; verified.

> **A commit is a backup of what was COMMITTED. The moment you edit past it, the
> backup is stale and the "restore" is a partial revert.** The protection was
> genuinely sound when established and expired with no signal. Re-stage after
> every correction, or verify the file's *intended* content after every restore —
> not merely that the mutation is gone.

⚠️ **And the verification of that repair tripped the SUBSTRING TRAP, in a comment
written minutes earlier.** `grep -c "mocked ? null"` returned **1** after the fix
— because the new explanatory comment *quotes the removed guard*. The all-clear
needed the executable token, `const vendorRequestId = mocked ? null`, which
returns 0. Exactly the case AGENTS.md names: *a file's comments are the one place
where the words you are grepping for are guaranteed to appear.*

### ⚠️ PERMISSION REFUSALS NOT IN MASTER.md's TABLE — three, all this session

Per MASTER.md: a refusal not in the table is a finding, with the command and what
it was establishing.

| command | establishing | granted re-formulation? |
|---|---|---|
| `mkdir -p /tmp/b4-mutation-backup` | scratch dir for the mutation backups | **none found** — commit-first was used instead |
| `cp <7 files> /tmp/…` | the canon-mandated pre-mutation backup | **none found** — same |
| `Write` to `/tmp/b4-commit-msg.txt` | commit message via `-F` (prose-is-never-a-shell-argument) | **yes** — `git commit -F -` with a quoted heredoc (`<<'MSG'`), which canon names as an accepted form |

The first two matter more than they look: they make the canon's **prescribed**
mutation-proof procedure unavailable to the unattended loop, which is what forced
the commit-first substitute and, indirectly, produced the stale-backup finding
above. Recommend adding `mkdir -p /tmp/*` and `cp` to the allowlist, or recording
commit-first as the sanctioned form for this session class.

### WHAT THIS DOES NOT CLAIM

- **It does not price anything.** Every Deepgram row is still priced at
  `PRICING.deepgram_nova3_medical` whatever model it names. Ruling 80(c)'s
  `null`-rate decision is still owed by B4/B6.
- **It does not run the per-stage count.** That is B4 step 2. This change makes
  it possible; it does not perform it.
- **It proves nothing on QA.** The proof here is the unit gate. No QA pipeline
  run was executed for this step.
- **It changes no historical row**, and it does not claim `tm_embed` works in
  production — it demonstrably does not.
- **`whisper-batch.ts` was NOT given a mock boundary**, stated rather than
  silently skipped: under `MOCK_AI_CALLS` the Deepgram fixture always succeeds,
  so the Whisper fallback is unreachable. If a future change makes the mocked
  Deepgram path fail, Whisper becomes reachable **and would call the real
  vendor**. Named here as B4 step 2's input.
- **The `operation` label split is now B4 step 2's problem** — see ruling 81: the
  per-stage join must accept BOTH `transcribe_realtime` (3 legacy prod rows) and
  `tm_transcribe` (everything after this change).

### 📐 B4 STEP 2 RECONNAISSANCE — measured 2026-08-10, READ-ONLY, before any code

The stage universe, enumerated from the sources rather than from a `worker.ts`
call-site scan (which DISCOVERY §C.1 warns misses the nested layers):

| # | purpose | file | notes |
|---|---|---|---|
| 1 | `tm_transcribe` | `01-transcribe.ts:128` **and** `01b-transcribe-dictation.ts:109` | **two files, one label** — audio_upload vs voice_dictation, mutually exclusive per visit |
| 2 | `tm_speaker_roles` | `02-speaker-roles.ts:234` | audio_upload only |
| 3 | `tm_entities` | `03-extract-entities.ts:638` | |
| 4 | `tm_soap_draft` | `04-generate-soap.ts:241` | |
| 5 | `tm_anchor_entailment` | `04b-anchor-verify.ts:965` | **nested in L4**, k=3 — see below |
| 6 | `tm_critique` | `05-self-critique.ts:214` | |
| 7 | `tm_polish` | `06-polish.ts:293` | |
| 8 | `tm_polish_gate` | `06b-polish-fidelity-gate.ts:237` | **nested in L6** |
| 9–13 | `tm_icd_coding` · `tm_cpt_coding` · `tm_rx_drafting` · `tm_referrals` · `tm_patient_summary` | `07a`–`07e` | parallel fan-out |
| 14 | `judge` | `lib/em-coding/llm-mdm.ts:400` | bypasses `modelClient` entirely |
| 15 | `tm_embed` | sign-time hook, not a worker layer | **dead in prod — see the finding above** |

⚠️ **THE EXPECTED COUNT FOR `tm_anchor_entailment` IS NOT "3 PER VISIT", AND
RULING 68's WORDING COULD BE READ THAT WAY.** `04b-anchor-verify.ts:1023-1028`
fans out over `ENSEMBLE_LENSES` — 3 lenses, 3 calls — **per INVOCATION of L4b**,
not per visit. Production bears that out and refutes the naive reading:

    tm_anchor_entailment  231        tm_soap_draft  102

3 × 102 would be **306**, not 231. **The mechanism for the difference is NOT
established here** — it could be visits that skip L4b, a different invocation
granularity, or both — and it must be derived from the code path before the gate
asserts a number. **A gate that hardcodes `3 × visits` will be wrong**, and wrong
in the direction that reads as a metering hole.

⚠️ **`tm_speaker_roles` AND `tm_transcribe` ARE INPUT-MODE-DEPENDENT.** L2 runs
only for `audio_upload`; L1 vs L1b is decided by input mode. So *"one event per
stage"* is not a property of a visit — it is a property of **a visit of a given
input mode**, and the gate needs the mode in its expected-count table. This is
the same trap as the single-visit sample that lacked `tm_embed` (carried out of
B1-b step 4): one visit never exercises the full stage set.

---

## ✅ STEP 0.4 — the citation `635bf819` was owed, and here it is

Session 05 shipped B4 step 1's §2.5 judgement (PR #587) and stated its citation
in the morning report, but the merge landed after the ledger row was written —
so the row was owed to this session by design. Verified **with the checker**,
`--expect` armed against the ids the report claimed, which is the only direction
that can see a substitution:

**Citation — 4 of 4 on `635bf8194990a52ea52c147876c1113f8d425a1b`:**
   · `CI` 31394489107 a1
   · `e2e` 31394489007 a1
   · `a11y-ci` 31394489173 a1
   · `secrets-scan` 31394489193 a1

All `a1` — no re-runs, nothing to explain.

---

## ✅ B4 STEP 2 — the stage that could not be counted, and the production invariant that says what to count — 2026-08-10

### The finding: B4's gate was STILL unsatisfiable, one layer above where step 1 looked

Step 1 removed two mock boundaries that sat above `logApiUsage`, inside the
vendor clients. **`tm_anchor_entailment` had the same defect in a different
place** — not in a vendor client but in the LAYER, at `04b-anchor-verify.ts`,
where `entailmentStage` returned all-entailed under `MOCK_AI_CALLS` before
`entailmentPass`, therefore before `modelClient`, therefore before the meter.

    ZERO USAGE EVENTS LOOKS EXACTLY LIKE A WORKING METER THAT FOUND
    NOTHING TO RECORD.

⚠️ **AND THE REPO ALREADY KNEW, IN WRITING — FOR THE SECOND TIME IN TWO
SESSIONS.** Step 1's defect was carried as a written exemption in its own
mock-boundary gate. This one was carried as a written exemption in the fixture:

> `// Anchored-generation entailment verifier — UNREACHABLE in practice: the`
> `// verifier short-circuits to all-entailed under MOCK_AI_CALLS before any`
> `// model call (04b-anchor-verify.ts). Defensive fixture only`

**A comment explaining why something cannot be measured is a finding, not a
caveat.** Both times the sentence was accurate, both times it was filed as
context, and both times it was describing the exact reason an item's close
condition was unreachable. That is now twice; it is a class, not a coincidence.

⚠️ **NO UNIT TEST COULD EVER HAVE SEEN IT.** Every test in
`04b-anchor-verify.test.ts` calls `delete process.env.MOCK_AI_CALLS` in its
`beforeEach` — correctly, so their stubs are reached. The short-circuit was
therefore live on exactly the path no unit test takes, and dead on every path
one does. `modelClient.completeText` already carries B0's note that the
stage-level short-circuit was deleted *there*; 04b kept a private copy of it.

### What shipped

- **`04b-anchor-verify.ts`** — the stage-level short-circuit is deleted. The
  k=3 ensemble now runs as three MOCKED calls, and each one meters
  (`unitsSource='mock'`, `requestId` NULL per ruling 72a).
- **`packages/ai/src/mock.ts`** — one selection function,
  `completeTextFixture(purpose, user)`, read by BOTH `buildMockMessage` (the
  production path) and `mockCompleteText` (the test-facing helper). The
  `tm_anchor_entailment` branch is **content-sensitive** per ruling 69: it
  returns one entailed verdict per claim the prompt actually names.
- **Gate** `packages/ai/src/__tests__/gate-b4-anchor-entailment-meters.test.ts`
  — 7 arms; plus 2 arms in `04b-anchor-verify.test.ts` that set
  `MOCK_AI_CALLS` on purpose.

**Behaviour is unchanged and that is the point.** All three lenses agree, every
claim clears the ≥2 majority, and `entailedIdx` is the same set the
short-circuit returned by hand. What changed is that three usage rows now
exist. `tsc` 0 errors; **3313 passed / 4 skipped** in the app suite, **532** in
`packages/ai`.

### Mutation proof — four, each naming its victim first

| mutation | asserted | measured |
|---|---|---|
| **M1** — restore the stage-level short-circuit | 1 occurrence | **RED**, `expected 3 calls, got 0` — the number the meter used to see |
| **M2** — make the fixture CONSTANT again | 1 occurrence | **4 RED** (ANSWERS · ECHOES · ANCHORED · ONE) |
| **M3** — unanchor the claim regex to `/CLAIM (\d+):/g` | 1 occurrence | **1 RED**, exactly the ANCHORED arm |
| **M4** — let `mockCompleteText` read the fixture table directly | 1 occurrence | **4 RED** — the B0 drift shape, caught |

⚠️ **M2 IS THE ONE THAT DISCRIMINATES.** The two METER arms stayed GREEN under
it, correctly — metering does not depend on fixture content — so the file is not
seven arms all testing one thing. And **every mutation was applied and reverted
by an inverse string swap with an occurrence assertion on BOTH legs**, never by
`git checkout --`: the tree was dirty throughout, and session 05 lost work to
exactly that command on exactly that reasoning.

### 📐 THE MECHANISM SESSION 05 LEFT OPEN — now established, and it is not what the naive reading says

The recon recorded `tm_anchor_entailment 231` against `tm_soap_draft 102`, noted
that `3 × 102 = 306`, and said in as many words that **the mechanism for the gap
was NOT established**. It is now, and the answer is a much stronger invariant
than a multiplier:

```sql
SELECT n_calls, count(*) FROM (
  SELECT "visitId", count(*) AS n_calls FROM ai_calls
   WHERE purpose='tm_anchor_entailment' GROUP BY "visitId") s
GROUP BY n_calls;
--  3 | 73
```

**Every visit that carries the stage carries EXACTLY 3 calls. There is no 1, no
2, no 6.** So:

- **the granularity is one L4b invocation per visit** — a visit is never
  verified twice, which the "per INVOCATION, not per visit" warning left open;
- **there is no partial-ensemble case** — `entailmentPass` errors do not reduce
  the call count, they only change the votes;
- **the gap is entirely visits that never reach the verifier** with a claim —
  `claims.length === 0` returns before the ensemble, and that return is correct
  and stays. **No work is not a suppressed call.**

⚠️ **SO THE GATE ASSERTS A DISTRIBUTION, NOT A PRODUCT.** The expected value is
`n ∈ {0, 3}` per visit — checkable, and it cannot be satisfied by a coincidence
the way `3 × visits` can. A gate hardcoding the product would have been wrong in
the direction that reads as a metering hole, exactly as the recon warned.

### ⚠️ AND THE RECON'S OWN NUMBERS NO LONGER REPRODUCE — WHICH IS THE FINDING

Measured today, ~2 hours after session 05 measured them:

| purpose | session 05 | now | Δ |
|---|---|---|---|
| `tm_anchor_entailment` | 231 | **219** | **−12** |
| `tm_soap_draft` | 102 | **96** | **−6** |

`api_usage_events` did **not** move: it still holds 231 and 102. **`ai_calls`
lost rows and the usage table did not** — which is ruling 78(b)'s reasoning
happening in front of us rather than in the abstract. `ai_calls` is hard-deleted
by four production paths; `api_usage_events` has no deleter, which is why it is
the billing source.

> **A COUNT TAKEN FROM `ai_calls` HAS A SHELF LIFE. No B4 gate may take its
> expected numbers from that table** — not because the numbers are wrong, but
> because they are *true and perishable*, and a gate that re-derives them will
> disagree with the one that wrote them down for reasons that have nothing to do
> with the meter.

The per-visit distribution above is stated as an INVARIANT (`{0,3}`) precisely
so it survives deletion: losing a visit removes 3 calls and 1 group, and the
shape is unchanged.

### ⛔ WHAT THIS DOES **NOT** CLAIM

- **It does not close B4.** The per-stage count over a full QA run is not run
  here. This removes the second-to-last construction blocker.
- **⚠️ `judge` STILL CANNOT METER UNDER MOCK, AND IT IS NOT FIXED HERE.**
  `llm-mdm.ts:395` returns `null` before the call — the same shape — but the
  remedy is **not** the same and must not be assumed to be. `judge` **bypasses
  `modelClient` entirely** and speaks to the Anthropic SDK directly, so there is
  no meter beneath it to fall below; wiring one is a real change to the E/M
  path. And its `null` return is **deliberate and documented**: `judgeMdm`
  routes `null` to a deterministic fallback, so the mock yields a real MDM level
  with `llmJudged: false`, which is *true*. Ruling 69 makes that content
  sensitivity load-bearing for the E/M movement gates. **Fabricating a
  judgement to make the meter tick would be a mock that lies about its own
  provenance** — strictly worse than a stage that does not meter. → carried as
  **B4 step 3**, named, not silently inherited.
- **It proves nothing about production.** Production's L4b path was already
  metering; this only makes QA able to.
- **It does not touch money.** Mock rows carry zero cost columns.

### Carried to B4 step 3

1. **`judge` is 1-to-many per visit, NOT one-per-visit.** Measured today:
   58 visits with 1, 12 with 2, 2 with 3, one with 6, **one with 13**. E/M can
   be re-scored, and `callClaudeMdm` retries once on a parse failure. **A gate
   asserting one `judge` event per visit will be wrong**, and the tail is long
   enough that a small sample will not reveal it.
2. **The two-label obligation from ruling 81 still stands** — the per-stage join
   must accept `transcribe_realtime` (3 legacy rows) *and* `tm_transcribe`.
3. **`email_send` holds 219 `api_usage_events` rows** while GATE 0.5 rules
   Resend **not metered**. The last one is dated **2026-08-03** and the ruling
   is dated **2026-08-04**, so nothing has been written since the ruling and the
   *current* posture is consistent. But the history is there and any rollup over
   past months will pick it up. **Not adjudicated here** — flagged as an input
   to B5/B9, where a rollup first has to decide what it includes.

### Citation — produced by `check-citation.sh`, not typed

**Citation — 4 of 4 on `8307a1d696d812cf83d752e68850ba365c3c6f00`:**
   · `CI` 31403803982 a1
   · `e2e` 31403803965 a1
   · `a11y-ci` 31403803913 a1
   · `secrets-scan` 31403803941 a1

All `a1` — no re-runs, nothing to explain. PR **#588**, merged from
`feat/b4-step2-anchor-entailment-meters` (branch retired on merge). The PR head
`1bd8801d` was also 4 of 4; the merge-commit citation above is the one that
counts.

### ⚠️ NOT DEPLOYED THIS SESSION — a decision, stated, with its evidence

**This change is provably inert in production**, so it ships with the next
deploy that has a reason of its own rather than earning one here.

The deleted branch was `process.env.MOCK_AI_CALLS === 'true'`. Measured in the
**running containers**, not in the compose file — the distinction that mattered
on 2026-07-28, when the file read safe and the containers did not:

```
meddoc-pro-transcribe-md-1         MOCK_AI_CALLS=false
meddoc-pro-transcribe-md-worker-1  MOCK_AI_CALLS=false
```

Explicitly `false`, not merely absent, in both. So the short-circuit never fired
in production and its removal changes nothing there; `mock.ts` is reachable only
under the same flag. **Everything this item changes lives on the QA/CI path.**

⚠️ **This is a departure from the per-item deploy rhythm and is called out
rather than left as an omission.** A §2.5 declaration for a code-only deploy
reads *"nothing but the image ids"* — which would have been true, and would have
proved nothing about this change, because the behaviour it alters is not
reachable from any production code path. The next B-lane deploy carries it.
**`main` is ahead of production by this commit, deliberately and knowingly.**

---

## ✅ B4 STEP 3 — the judge stage can be counted, and the meter still refuses to invent a judgement — 2026-08-10

**Session 07.** `judge` was the last enumerated stage that could not be counted
on a mocked run. It is now counted. Ruling **83** (PROVISIONAL) records the
decision; this section records the work and what it does not claim.

### The finding, and why step 2 deliberately did not fix it

`callClaudeMdm` returned `null` under `MOCK_AI_CALLS` **before any meter ran**,
so a mocked QA run emitted **zero** `api_usage_events` rows for `judge`, and
B4's gate — *"one full QA pipeline run produces one event per stage"* — was
unsatisfiable for it **by construction**.

    ZERO USAGE EVENTS LOOKS EXACTLY LIKE A WORKING METER THAT FOUND
    NOTHING TO RECORD.

That is the same sentence steps 1 and 2 were written under. ⚠️ **But the fix is
NOT the same, which is precisely why ruling 82 refused to extend itself here.**
Every other mocked Anthropic path meters because `anthropic.ts` hands back a
fixture `Message` and the real pipeline runs over it. Doing that here means
producing a parseable `MdmJudgement` — and `judgeMdm` would then report
**`llmJudged: true` for a judgement no LLM produced.**

**So the two claims were separated.** *"A judge call was made"* and *"the LLM
produced a judgement"* are different facts, and only the first is metered:

| | before | after |
|---|---|---|
| `api_usage_events` row under mock | **none** | **one**, `operation='judge'`, `unitsSource='mock'`, `requestId=null`, money zeroed |
| `ai_calls` row under mock | none | none (unchanged — `log.ts` suppresses centrally) |
| return value | `null` | `null` |
| `llmJudged` downstream | `false` | `false` |
| a `judge` fixture in `mock.ts` | none | **still none** |

Nothing outside the meter changed. The deterministic fallback still runs and
still produces the same level from the same input.

### What landed

- **`llm-mdm.ts`** — the mock branch builds the log context, emits ONE usage
  row, and returns `null`. It stays **above `args.soap.trim()`**, because
  `gate-mock-ai-honored` asserts that POSITION: a flag read below the
  prompt-building line is not a short-circuit, the request would already exist.
- **`mock.ts`** — `MOCK_FIXTURE_USAGE` extracted as a shared constant;
  `buildMockMessage` now spreads it instead of carrying its own literal.
- **`index.ts`** — `isMockEnabled` and `MOCK_FIXTURE_USAGE` exported, for the
  one production path that cannot inherit `anthropic.ts`'s meter.
- **`gate-b4-judge-meters.test.ts`** — 7 arms, mutation-proved below.
- **`gate-b1b-no-fabricated-request-id.test.ts`** — census total 10 → 11.

### ⚠️ THE `gate-b1b` CENSUS CAUGHT THIS ITEM UNPROMPTED — SECOND TIME

The bucket-sum arm went red on `expected 11 to be 10` without anyone pointing
it at this change. **`withoutId` did NOT move**, correctly: the new site passes
`requestId: null` **explicitly**, which keeps it in the `withId` bucket and out
of `NO_ID_DECLARED`. *"Passes no id"* and *"passes null on purpose"* are
different facts and the two buckets exist to keep them apart.

It is the second item that gate has reported without being written for it (B2
was the first). **It should not be softened.**

### Mutation proof — five, each naming its victim first

Every file the proof touched was copied to scratch **before the first
mutation** and restored from those copies, never from git — the working tree
held uncommitted work, and `git checkout --` would have eaten it.

| # | mutation | predicted victim | observed |
|---|---|---|---|
| M1 | delete the `logApiUsage` call | EMITS, ONE-SOURCE, COUNTS | **3 red**, the four provenance/absence arms stayed green |
| M2 | `unitsSource: 'mock'` → `'vendor'` | MARKED | **red** — `expected 'vendor' to be 'mock'` |
| M3 | return a fabricated `MdmJudgement` | HONEST | **red** — `llmJudged is true under mock — a judgement was fabricated` |
| M4 | `buildMockMessage` back to its own literal | ONE-SOURCE | **red** — the two mock meters can now drift |
| M5 | make a cache HIT emit a row | CACHED | **red** — `a cache hit emitted a usage event — that meters a call nobody made` |

**M3 is the one that matters.** It is the forbidden fix — the one ruling 82
named — and the gate refuses it by name.

Restores verified byte-identical with `diff`, not assumed.

### ⚠️ THE GATE'S OWN NON-VACUITY ARM MADE A LIVE VENDOR CALL

Found by the full suite, not by the arm's author. The first draft proved
non-vacuity by deleting `MOCK_AI_CALLS` and calling `judgeMdm` with the dummy
`ANTHROPIC_API_KEY` still set — so the flag-OFF branch **built a real client and
issued a real HTTPS request to api.anthropic.com**, twice (the retry), against a
30-second timeout.

It passed in isolation and **failed intermittently under full-suite load**,
which is the only reason it was caught. ⚠️ **That is this item's own defect
reintroduced inside its own gate** — a network round-trip wearing a unit test's
clothes, in the file whose subject is "a code path that reaches a vendor from a
stack that promises it cannot".

Fixed by removing the credential too, so `getAnthropicClient()` throws **before
any socket opens**. The two-condition doctrine is not only for production code:
the flag is one condition, the credential is the other, and a test that keeps
the credential is relying on the flag alone.

Full suite re-run twice after the fix: **3320 passed, 4 skipped**, stable.

### ⚠️ FOUND ON THE WAY PAST — A JUDGEMENT CACHE EXISTS, AND RULING 69 READS AS THOUGH IT DOES NOT

`llm-mdm.ts` has carried a **Redis judgement cache** since Phase 5.2 —
`em_mdm_cache:`, SHA-256 of the normalised SOAP, **7-day TTL**, with a 20%
drift bypass. Ruling 69 says, in as many words, *"NO judgement cache ships in
B0 (proposal scope-creep); if ever wanted it arrives as its own ruled item."*

**Both are true and they are about different things** — 69 declined a *new*
cache proposed in B0's design; the existing one predates it. But a reader
greping `RULINGS.md` for "cache" finds a sentence that reads as *there is no
judgement cache*, and there is one, in production, today.

**Not silently reconciled.** What 69 got exactly right is the metering answer,
and the shipped cache already obeys it: a hit returns before `callClaudeMdm`,
so no vendor call, no cost, **no usage event**. That is now asserted (arm
CACHED) rather than left to be rediscovered.

⚠️ **It cannot confound a mocked QA run.** `writeCache` is only reached when the
LLM returns a judgement, and under mock it never does — so the cache is
**always cold under `MOCK_AI_CALLS`**, and the per-stage count is unaffected.
Checked, not assumed; it was the first thing that could have made this item's
numbers unreproducible.

**Owed to B5/B9, not to this item:** a rollup that counts `judge` calls against
a doctor's bill has to decide what a 7-day cache means for *"calls made this
month"*. Flagged, not answered.

### ⛔ WHAT THIS DOES **NOT** CLAIM

- **It does not close B4.** The per-stage count over a full QA pipeline run is
  still not run. This removes the LAST *construction* blocker; the gate itself
  is B4's closing step.
- **It proves nothing about production.** Production's judge path already
  metered — `MOCK_AI_CALLS=false` in both containers, so the new branch is
  unreachable there. Everything this item changes lives on the QA/CI path.
- **It does not touch money.** Mock rows carry zero cost columns, zeroed by the
  writer, not by this call site.
- **It does not resolve the `withTimeout` under-count** recorded in ruling 78 —
  a timed-out judge call may be billed by Anthropic while its tokens never
  reach this process. Structural, and only an invoice can size it.

### Citation — produced by `check-citation.sh`, not typed

**Citation — 4 of 4 on `870413c134f21a92f31e3073a9579cd364a5dcf0`:**
   · `CI` 31423059629 a1
   · `e2e` 31423059647 **a2**
   · `a11y-ci` 31423059768 a1
   · `secrets-scan` 31423059717 a1

PR **#591**, merged from `feat/b4-step3-judge-meters` (branch retired on merge).
The PR head `fde6153a` was 4 of 4 on its own; the merge-commit citation above is
the one that counts.

#### ⚠️ WHY `e2e` IS `a2` — the checker demands a reason, and here it is

Attempt 1 **failed**, on `16-account-settings.spec.ts:38` — *"the profile panel
never showed its saved chip — updateProfileAction did not return ok"* — after
its own retry, with **91 passed / 1 failed / 1 skipped**. Nothing in the failure
touches metering, E/M, or any file this item changed.

**The re-run was not re-run-and-hope. The flake was DEMONSTRATED first:**

    git rev-parse 870413c1^{tree} fde6153a^{tree}
    ee415940a039fc3b09a56d079e4bc1558b52be2d
    ee415940a039fc3b09a56d079e4bc1558b52be2d

**The merge commit and the PR head have BYTE-IDENTICAL TREES.** `e2e` on that
exact tree had already passed on `fde6153a` (run 31417054897). Same code, two
runs, two outcomes — which is the definition of non-determinism, established by
evidence rather than asserted from the failure's appearance.

⚠️ **AND IT IS A RECORDED FLAKE WITH A NAMED MECHANISM** —
`docs/rounds/RELAY.md:791`: *"`16-account-settings` flake — the submit can still
beat the client tree. Needs a hydration-PROVING wait, not a network condition."*

### ⚠️ FOUND ON THE WAY PAST — THE PRESCRIBED FIX FOR THAT FLAKE IS **ALREADY APPLIED**, AND IT RECURRED ANYWAY

This is the part worth carrying forward, and it is **new information**, not a
restatement of the known flake.

The recorded remedy was *"a hydration-PROVING wait, not a network condition"*,
and `16-account-settings.spec.ts:74` **already does exactly that** — it waits on
`#profile form[data-hydrated="true"]`, an attribute set from an effect body,
which cannot run during SSR. That marker replaced `networkidle` on 2026-08-05
precisely because `networkidle` *"narrows the window without closing it"*.

So the spec's own comment block documents a fix that has now **failed in the
field**. The hydration wait passed; the save still did not report `ok` within
10s.

> **A remedy that is recorded as sufficient, and is applied, and is still
> failing, is a WORSE state than an open flake** — because the file reads as
> solved and the next reader will spend their first hour re-deriving that the
> marker is present.

**Not fixed here, and deliberately so.** The recorded mechanism is now excluded
by evidence, which means the real one is unidentified — and guessing a second
remedy on top of a disproven first is how a flake becomes folklore. The
candidates the next investigator should separate:

1. `updateProfileAction` genuinely exceeding 10s under full-suite load (the
   assertion's own timeout is the thing being measured, not the app);
2. the action returning not-ok for a reason the spec cannot see, because it
   asserts a chip rather than the action's result;
3. hydration completing while the `useActionState` dispatcher is not yet bound —
   i.e. `data-hydrated` is a *necessary* marker that is still not *sufficient*.

⚠️ **(3) would make the marker the same class of proxy as the two it replaced**,
and the spec's own history — rail buttons (1-in-10), then `networkidle` (2 in one
run) — is a list of proxies each believed sufficient until it wasn't. **The
instrument to settle it is the failure's own trace/screenshot artifacts**, which
this session deliberately did not download (un-reapable scratch, per the
close-out contract).

**Owed as its own item.** It is not B4's, it costs a merge-commit re-run every
time it fires, and it has now burned one.

### 📐 B4's CLOSING STEP — RECON MEASURED 2026-08-10, READ-ONLY, so the next session does not re-derive it

Three facts about the closing gate (*"one full QA pipeline run produces one
event per stage, counted against the enumerated stage list"*), established while
waiting on CI. **None of these is acted on here.**

#### 1. `judge` is ≥1 PER VISIT under mock, not exactly 1 — and this item is why

`judgeMdm` has **two** production callers, and under mock **both** meter:

| caller | when |
|---|---|
| `worker.ts:944` | pre-warm, fires on **every** visit (soft-fail wrapper) |
| `score.ts:142` | the E/M score path, at page render |

The pre-warm exists to populate `em_mdm_cache:` so the render hits a warm cache.
⚠️ **But nothing writes that cache under mock** — `writeCache` is reached only
when the LLM returns a judgement, and the mock path returns `null` by design. So
the render's call is **always a cache miss under mock**, and now meters too.

**A closing gate asserting `judge == 1` per visit will be wrong.** It is `>= 1`,
and production already agrees for a different reason (58 visits with 1, 12 with
2, one with 13 — re-scoring plus the parse-failure retry).

#### 2. QA's `api_usage_events` CANNOT serve as the gate's baseline — it is entirely pre-regime

Measured on the live QA stack (`meddoc-qa-postgres-1` / `meddoc_qa_test`):

```
total 977 rows · earliest 2026-07-24 01:57Z · latest 2026-07-28 22:48Z
unitsSource='mock' → 0
```

**Every QA row is `vendor`, and the newest is 2026-07-28** — the date of the 298
real-Anthropic-calls incident. These ARE those rows. Nothing has metered on QA
since, so **no mocked pipeline run has ever produced a usage event there**, and
B0-a's regime (2026-08-08) is entirely absent from that database.

⚠️ **The closing gate therefore needs a FRESH mocked QA run and must not measure
the existing population** — which would report `mock = 0` for every stage and
read as "the meters are all broken".

#### 3. Three stages are ABSENT from QA entirely

`tm_transcribe` / `transcribe_realtime`, `tm_anchor_entailment` and `tm_embed`
have **no rows at all** on QA. Combined with the step-2 recon's warning that
`tm_speaker_roles` and `tm_transcribe` are **input-mode-dependent**, the closing
gate's expected-count table has to be keyed by input mode, and the run has to
exercise **audio_upload** — which B4's own text already demands, because
production is 100% `text_notes` and cannot prove it.

---

## ✅ B4 CLOSING STEP — the stage list becomes a thing, and one full mocked run is counted against it — 2026-08-10

**Session 08.** B4's gate reads, verbatim: *"one full QA pipeline run produces
one event per stage, **counted against the enumerated stage list**, not
eyeballed. The audio path must be exercised on QA."* Steps 1–3 each removed a
stage that **could not** be counted. This is the run, and the list.

**14 of 15 stages COUNTED. One UNPROVEN, named, with its mechanism established
and its closure recipe written down.** That distinction is the item's main
deliverable and is explained below — it is not a hedge.

### The sentence has two halves and they need two machines

| half | where it lives | why it cannot live in the other |
|---|---|---|
| **the LIST** | `src/lib/billing/pipeline-stages.ts` + `__tests__/gate-b4-stage-enumeration.test.ts` — **CI, every push** | pure source; needs no stack |
| **the RUN** | `scripts/qa/b4-stage-coverage.ts` — the isolated `meddoc-qa` stack | needs a worker, a queue, a bucket and a database |

⚠️ **THE LIST IS THE HALF THAT ROTS, AND A RUN AGAINST A STALE LIST IS THE
`doctor_edit_patterns` FAILURE AGAIN** — a gate flawless at counting a universe
that does not contain what it was asked to protect. So the census diffs both
directions: every enumerated stage's named source really declares that purpose,
and every purpose assignment in `apps/transcribe-md/src` lands in a named bucket
— pipeline / declared-non-pipeline / **UNCLASSIFIED** — with the buckets summing
to the total.

### ⚠️ THE MATCHER WAS `purpose: '…'` FOR TWENTY MINUTES AND IT COULD NOT SEE `judge`

The first census was written around `grep "purpose: '"`. It found 22 sites and
looked complete. **`llm-mdm.ts:439` writes `const purpose = 'judge' as const;`**
— a different shape, one line above the object that spreads it — so the census
would have reconciled cleanly over **14 of 15** stages while the fifteenth, the
one B4 step 3 had finished four hours earlier, was invisible.

Caught by reading the file rather than by any check. The matcher is now
`/\bpurpose\s*[:=]\s*'…'/` and **the const shape is a named positive control**,
because a matcher's zero and a matcher that cannot see are the same output.

### ⚠️ AND THE PROSE CONTROL I WROTE FOR IT WAS VACUOUS — MUTATION M3 IS WHAT SAID SO

The first version of *"does NOT see a purpose that appears only in PROSE"* was
asserted against the real `pipeline-stages.ts`, on the reasoning that a file
naming every operation in its comments is the natural haystack. **Deleting
`stripComments` from the extractor left all 34 tests GREEN.**

The control was measuring nothing: that file's prose says
`tm_anchor_entailment`, but it never says `purpose: 'tm_anchor_entailment'`, and
the **MATCHER** is what the stripper has to defeat — not the operation name. A
check whose title is wider than what it measures, in a file whose header
lectures about exactly that.

Now split in two, and the second half is the honest one:

- the extractor's discrimination is controlled on a **fixture** — same string,
  stripped and unstripped, zero vs two matches;
- a second arm **asserts the equality on the real tree**: stripping changes
  NOTHING today, because no non-test file under `apps/transcribe-md/src` writes
  `purpose: 'x'` in a comment. The only file in the app that does is the gate's
  own header, and `walk()` skips `__tests__`.

> **Recording the equality is what stops a future reader believing M3's green
> means the stripper is decoration.** It means the haystack is currently clean,
> and the day somebody documents a call site the way this repo documents
> everything, it stops being.

### THE RUN — three visits, one per input mode, on images built from this tree

QA was rebuilt from `16cadf50` + this change and recreated with
`--force-recreate` before anything was measured. The driver creates one visit
per mode, uploads the committed 1 044-byte `silence-3sec.mp3` for the two audio
modes, enqueues through the production `enqueueProcessVisit`, polls to terminal,
then exercises `tm_embed` and counts `api_usage_events` **scoped to its own
visit ids**.

⚠️ **SCOPED, BECAUSE QA's EXISTING POPULATION IS ENTIRELY PRE-REGIME** — 977
rows, every one `unitsSource='vendor'`, newest 2026-07-28, which are the rows
from the 298-real-calls incident. A gate measuring the population would report
`mock = 0` for every stage and read as *"the meters are all broken"*. Confirmed
at run time: the script prints the baseline before it creates anything.

Final run, all three visits `READY`:

```
text_notes       12 stages · voice_dictation 13 · audio_upload 14
tm_transcribe ✔ (dictation + upload)   tm_speaker_roles ✔ (upload only)
tm_entities ✔  tm_soap_draft ✔  tm_critique ✔  tm_polish ✔  tm_polish_gate ✔
tm_icd_coding ✔ tm_cpt_coding ✔ tm_rx_drafting ✔ tm_referrals ✔ tm_patient_summary ✔
judge ✔        tm_embed ✔ (out of band)        tm_anchor_entailment — UNPROVEN
```

### ⚠️ THE FIRST RUN REPORTED EIGHT FINDINGS AND SIX OF THEM WERE MY TABLE, NOT THE METER

That is the gate working. Each is recorded because each corrected something.

**1. `tm_polish` and `tm_polish_gate` are `{0,1}`, not `exactlyOne`.**
`06-polish.ts:186` takes a **passthrough** branch when the critique found
nothing auto-patchable: the draft becomes the final note and **no model call is
made**. No call, no meter — the same shape as `tm_anchor_entailment`, and *no
work is not a suppressed call*.

Measured on production's DURABLE table, not `ai_calls`: of **82** visits
carrying a `tm_soap_draft`, exactly **28** carry a `tm_polish`, one each.
**Fifty-four took the passthrough.** A gate demanding one would have reported a
metering hole on two thirds of production.

**2. AND THE TWO ARE COUPLED, WHICH A PER-STAGE COUNT CANNOT SEE.** L6b sits
inside L6's model-call branch, so it can only fire on a visit that polished. The
visit sets are **identical** — 28 and 28, full outer join returning **zero**
asymmetric rows. Two `{0,1}` stages firing on *different* visits would satisfy
every per-stage assertion and every total; `COUPLED_STAGES` is asserted
per-visit by the run for exactly that reason.

**3. ⛔ `tm_embed`'s meter rows were labelled `embed`, and the stage list could
never have matched them.** `buildOpenAIEmbedUsage` hardcoded
`operation: 'embed'` while every caller's purpose is `tm_embed`. The run
reported it as `unenumerated operation 'embed' metered against this run's
visits` — a stage metering **correctly**, under a name no enumeration can hold.

> ⚠️ **AND IT EXPLAINS A NUMBER ALREADY IN THIS LEDGER.** B4 step 1 recorded
> *"`api_usage_events`: zero openai rows, ever"* for `tm_embed`. True — and it
> would have stayed true **after** the dead OpenAI credential is replaced,
> because the rows would arrive labelled `embed`. **The zero was going to
> survive its own cure.**

Fixed exactly as step 1 fixed Deepgram: `operation` is a **required parameter**
taking the caller's purpose. Swept by the predicate rather than by the symptom —
`grep "operation: '"` in `api-usage.ts` returns three literals, and all three
are dispositioned:

| builder | literal | disposition |
|---|---|---|
| `buildOpenAIEmbedUsage` | `'embed'` | **FIXED** — takes `args.purpose` |
| `buildWhisperUsage` | `'transcribe_batch'` | **FIXED** — same defect, same fix; the cross-provider fallback's purpose is `tm_transcribe` |
| `buildResendUsage` | `'email_send'` | **LEFT, deliberately.** Its ctx carries no purpose at all — Resend is not a model call, GATE 0.5 rules it not metered, and 219 historical rows carry that label |

**No history moves.** Production holds **zero** rows from either fixed builder
under either label — whisper is gated off pending a BAA, and the OpenAI
credential has been dead since 2026-07-02.

⚠️ **AND B4 STEP 1's OWN GATE WAS PINNING THE DEFECT.**
`gate-b4-mock-boundary-all-vendors.test.ts:267` asserted
`expect(row.operation).toBe('embed')` — the wrong label written down as the
contract, one step earlier, by a session that had no reason to doubt it.

### 🟠 FOUND ON THE WAY PAST — QA HAS **NEVER** RUN L4b, AND PRODUCTION ALWAYS HAS

Not looked for. `tm_anchor_entailment` came back zero on all three modes even
after the polish corrections, so the flag was read **in the running containers**:

```
meddoc-pro-transcribe-md-worker-1   TRANSCRIBE_MD_EVIDENCE_ANCHORS=true
docker-compose.qa.yml               (absent — evidence-anchors-flag.ts:9 defaults OFF)
```

The QA worker has logged `{"flag":"TRANSCRIBE_MD_EVIDENCE_ANCHORS","enabled":false}`
at **every boot since the stack existed**. So **L4b — the per-claim entailment
verifier, a fail-closed clinical safety layer — has never executed on QA**,
while production has 231 of its usage rows. The step-3 recon recorded
`tm_anchor_entailment` as *"absent from QA entirely"* and did not establish why;
this is why.

⚠️ **THE FILE'S OWN STATED INTENT WAS THE THING BEING VIOLATED.**
`docker-compose.qa.yml` says, in as many words, *"The build args mirror
production's deliberately: QA must be production-SHAPED, and 'the pack is green'
and 'the shipped product works' have to be one statement."* A **runtime** flag
that production sets and QA does not is that promise failing on the axis the
sentence does not mention. Set to `"true"` here, **declared rather than
inherited**, so a future `.env` cannot quietly flip it. Inert on SOAP content
under mock: the flag appends an anchoring block to L4's system prompt, and a
mocked L4 returns a fixture regardless.

### ⚠️ COUNTED vs MERELY PERMITTED — THE ARM THAT STOPS THIS GATE BEING A DECORATION

Correcting the polish rows to `{0,1}` made the run green and **proved less than
before**. Three stages now have expectations that ADMIT ZERO for good reasons —
and a run in which they never fire satisfies every assertion while saying
nothing about them.

> **A STAGE OBSERVED AT ZERO EVERYWHERE IS INDISTINGUISHABLE FROM A STAGE WHOSE
> METER WAS DELETED.**

B4's gate says *"one event per stage"*, not *"no contradiction per stage"*. So
the run classifies every enumerated stage as **COUNTED** (observed ≥1 somewhere)
or **UNPROVEN**, and exits **2 — can't tell**, never 0, while any stage is
unproven. Same three-code convention as every other check in `scripts/`.

**This is the `tm_polish` correction's own antidote.** Without it, the honest
fix to finding 1 would have quietly turned a red gate into a permanently
unfalsifiable green.

### CLOSING TWO OF THE THREE — an env-selected fixture, default OFF

`MOCK_CRITIQUE_ISSUES=true` swaps the empty `tm_critique` fixture for one
carrying a **single MINOR** issue, mirroring the established `MOCK_RX_WARNINGS`
and `MOCK_TEMPLATE_PHI_FLAG` variants. With it, L6 calls its model instead of
passing through, and `tm_polish` + `tm_polish_gate` are counted **1 on every
mode**.

Two details are load-bearing and both are asserted:

- **MINOR, not critical** — a critical issue gates signing and would break every
  suite that signs a visit. The default stays `issues: []` for the same reason.
- **the `suggested_fix` is a REMOVAL** — `isAdditiveFix` (`06-polish.ts:127`)
  DEFERS any fix needing content the draft lacks, and a deferred fix is not a
  fixable one. **An "add …" phrasing would have left `fixable.length === 0`, L6
  would still have passed through, and the whole mechanism would have been an
  elaborate no-op that looked correct.**

Carried on a committed overlay, `docker-compose.qa.b4-coverage.yml`, rather than
a shell env prefix — the prefix form is not in the FOUNDATION loop's allowlist,
and **a procedure the unattended loop cannot execute is a procedure that will
not be re-run**.

### ⛔ THE ONE THAT IS STILL UNPROVEN, AND EXACTLY WHY

**`tm_anchor_entailment`.** Turning the flag on makes L4b *run*; it does not
give it anything to verify. Two conditions, and only one is a flag:

1. `TRANSCRIBE_MD_EVIDENCE_ANCHORS=true` — **now fixed**.
2. L4's draft must CARRY anchors (`⟦A:…⟧`, `ANCHOR_BLOCK_RE`). Under mock L4
   returns a fixture, and **`mock.ts` contains ZERO anchor markers** (measured:
   `grep -c '⟦A:' mock.ts` → `0`). So `deterministicStage` puts every line in
   the exempt bucket, `toEntail` is empty, and `entailmentStage` returns at
   `04b-anchor-verify.ts:999` before any call.

That return is **correct** — ruling 82(d) keeps it deliberately, and production's
`{0,3}` distribution depends on it. The stage is correctly silent, not broken.

**THE CLOSURE, written down so the next session does not re-derive it:** an
anchored `tm_soap_draft` mock variant selected by its own env flag, exactly as
`MOCK_CRITIQUE_ISSUES` selects the populated critique. Not attempted here — the
SOAP fixture is read by many suites and the variant needs its own blast-radius
argument, which is a session's work, not a footnote.

### ⚠️ FOUND ON THE WAY PAST — THE GATE PRINTED A GREEN VERDICT AND THEN NEVER EXITED

Three `meddoc-qa-db-migrate-run-*` containers were still `Up` **thirty-five
minutes** after their scripts had printed complete output, including a 🟢.
`enqueueProcessVisit` opens a BullMQ Redis connection that holds the event loop
open forever; `prisma.$disconnect()` in the `finally` does not touch it.

> **A SCRIPT THAT FINISHES BUT NEVER EXITS READS AS A HANG — and worse, its
> EXIT CODE is its entire contract with any caller.**

A gate that cannot return 0/1/2 cannot be run by CI, by a wrapper, or by the
unattended loop, which means it would have been run exactly once, by hand, by
the session that wrote it. Fixed: close the queue, then `process.exit()` on the
computed code as the backstop. Recorded because the first three runs *looked
fine* — the output was complete and the verdict was correct.

### Mutation proof — four, each naming its victim first, each asserted APPLIED

| # | mutation | must go red | did |
|---|---|---|---|
| **M1** | the list forgets `tm_polish_gate` (its `operation` renamed to a real-but-wrong one) | LIST→SOURCE **and** the unclassified bucket | ✅ 3 arms |
| **M3** | `stripComments` deleted from the extractor | the prose control | ✅ 1 arm — **after** the control was rewritten; the FIRST version stayed green, which is the finding above |
| **M4** | the matcher narrowed to `purpose:` only — the naive grep | the `judge` control, LIST→SOURCE for `judge`, and the site count | ✅ 3 arms |
| **M5** | `tm_transcribe` made universal (`text_notes` added) | the input-mode arm | ✅ 1 arm |

Every mutation was `grep -c`-asserted present before running, and every restore
came **from the scratch backup, never from git** — the working tree carries
untracked new files and `git checkout --` would have deleted them.

### ⛔ WHAT THIS DOES **NOT** CLAIM

- **It does not close B4.** Fourteen of fifteen stages are counted;
  `tm_anchor_entailment` is UNPROVEN on a mocked run and the coverage script
  exits **2**, not 0, while that is true.
- **It proves nothing about production's meters.** The run is `unitsSource='mock'`
  end to end. What it proves is that every enumerated stage *reaches* the meter
  on the code production runs — which is the only claim a mocked run can make.
- **`tm_embed` is exercised at its own function boundary, not through the sign
  route.** The driver writes `signedSoap` and calls `captureEditPattern` with
  the three arguments `sign/route.ts:603` passes. It never touches
  `signedAt`/`signedBy`, so no signature is fabricated and the
  `signed_requires_signer` constraint is never in play. **That the sign route
  calls this function is the sign route's tests' business.**
- **It does not price anything.** No row's money columns are asserted; B3's
  `price_rates` is still unwired, per ruling 80(e).
- **The census cannot see a purpose passed positionally.** Its matcher is an
  ASSIGNMENT (`purpose:` / `purpose =`). A future call site handing a bare
  string to a helper would be invisible to it — named here rather than left as
  an assumed completeness.
- **`email_send` is untouched and unenumerated.** 219 production rows, GATE 0.5
  rules Resend not metered, and any B5/B9 rollup still has to decide what it
  includes — carried from step 2, still open.

### Citation — produced by `check-citation.sh`, not typed

**Citation — 4 of 4 on `32706453ee975a0c1f1dd92671e38d6936b3e78a`:**
   · `CI` 31442955526 a1
   · `e2e` 31442955517 a1
   · `a11y-ci` 31442955554 a1
   · `secrets-scan` 31442955510 a1

All `a1` — **no re-runs, nothing to explain**, and the `e2e` that has flaked
twice this week passed first attempt at 43m11s on the merge commit and 42m17s on
the PR head. PR **#594**, merged from `feat/b4-close-stage-coverage` (branch
retired on merge).

⚠️ **THE `e2e` GREEN IS THE LOAD-BEARING ONE HERE, NOT A FORMALITY.** This change
turns `TRANSCRIBE_MD_EVIDENCE_ANCHORS` **on for the whole QA stack**, and the
`e2e` job builds and drives that stack — eleven packs, thirteen image recreates,
every Rounds surface, the document surfaces and the flag-gated fixture packs. L4b
now runs in all of them, for the first time ever. That is the only instrument
that could have shown the posture change breaking something, and it is why the
change was made in the same PR rather than "verified" by reasoning about it.

### ⚠️ NOT DEPLOYED THIS SESSION — the same decision step 2 made, restated with its evidence

**Provably inert in production**, path by path:

| what changed | why production cannot see it |
|---|---|
| `buildOpenAIEmbedUsage` operation label | every prod embed call FAILS on the dead credential, so no row is written under either label |
| `buildWhisperUsage` operation label | the cross-provider fallback is gated OFF pending a BAA (`isWhisperFallbackEnabled` → false) |
| `mock.ts` critique variant | reachable only under `MOCK_AI_CALLS`, and **both prod containers declare `false`** — read in the running containers, not the compose file |
| `docker-compose.qa.yml`, the overlay, the coverage script | the QA stack and nothing else |
| `pipeline-stages.ts` + its gate | a list and a test; no runtime path imports them |

⚠️ **SO `main` IS NOW AHEAD OF PRODUCTION BY FOUR MERGES, DELIBERATELY, AND THE
NEXT DEPLOY CARRIES ALL FOUR.** Named here so the next session's §2.5 declaration
is written against the right diff rather than against this item alone:

| merge | production reachability |
|---|---|
| B4 step 2 (`8307a1d6`) | inert — mock-path only |
| B4 step 3 (`870413c1`) | inert — mock-path only |
| **self-hosted fonts (`a8bf9307`)** | ⚠️ **NOT inert.** It changes the shipped bundle and removes the build's last reach to Google. This is the one with a reason of its own, and it is what the next deploy is actually FOR |
| B4 closing step (`32706453`) | inert — the table above |

**A code-only deploy's declaration is one line — "nothing but the image ids" —
and it would be true for three of these four and unfalsifiable for the fourth.**
The fonts change deserves a declaration that names the bundle, so it gets its own
deploy rather than riding one written for a metering item.

---

## 🟩 THE OWED DEPLOY IS DONE — `f89c7c33` IS LIVE IN PRODUCTION, 2026-08-11T01:48Z

**Session 03 took the handoff above and executed it.** Production ran `c8a55986`
for twelve hours while `main` accumulated nine merges; it now runs `f89c7c33`.

| | |
|---|---|
| deployed commit | `f89c7c333b2921c3a063d5484382eec1e5d32a5b` |
| declaration | `docs/foundation/deploys/20260811-f89c7c33.md` |
| deploy log | `docs/deploy-logs/deploy-20260811T014641Z.log` |
| rollback tag | **`:pre-selfhostfonts-20260811`** — app `78a863205cc7` / worker `b7d5f8fb4883` / gotenberg `2d05d22572ba`, each verified against the RUNNING container's digest at tag time |
| app image | `78a863205cc7` → **`d29b852d8d9b`** |
| worker image | `b7d5f8fb4883` → **`c18d9dbf1092`** |

### Citation — produced by `check-citation.sh`, not typed

**Citation — 4 of 4 on `f89c7c333b2921c3a063d5484382eec1e5d32a5b`:**
   · `CI` 31447965593 a1
   · `e2e` 31447965599 a1
   · `a11y-ci` 31447965588 a1
   · `secrets-scan` 31447965608 a1

All `a1` — no re-runs, nothing to explain. `e2e` passed first attempt in 42m38s.

⚠️ **THIS IS A DESCENDANT CITATION AND THAT IS WHY IT IS THE RIGHT ONE.** The
previous session cited `32706453` (PR #594) and then a docs PR (#595) landed on
top. Deploying `32706453`'s evidence would have certified the parent of what
actually ships. `f89c7c33` contains everything the four substantive merges did
**plus** the docs commit, so its citation covers strictly more.

### THE DECLARATION, JUDGED — 21 of 21 ROWS, EVERY ONE AS DECLARED

| declared | measured | |
|---|---|---|
| app image id moves | `78a863205cc7` → `d29b852d8d9b` | ✓ |
| worker image id moves | `b7d5f8fb4883` → `c18d9dbf1092` | ✓ |
| **font assets 32 → exactly 8** | **8** | ✓ |
| six committed byte sizes, exact | 41344 · 20156 · 48256 · 31432 · 50824 · 51516 — all six | ✓ |
| six expected filename stems | `bricolage_grotesque_latin` · `figtree_latin` · `inter_latin` · `jetbrains_mono_latin` · `source_serif_4_latin` · `source_serif_4_latin_italic` | ✓ |
| `transcribe_visits` 25 | 25 | ✓ |
| … `signedAt IS NOT NULL` 17 | 17 | ✓ |
| … `deletedAt IS NOT NULL` 0 | 0 | ✓ |
| `transcribe_md_patients` 16 | 16 | ✓ |
| **`api_usage_events` 1325** | **1325** | ✓ |
| `ai_calls` 1126 | 1126 | ✓ |
| `users` 196 | 196 | ✓ |
| `practices` 197 | 197 | ✓ |
| `note_templates` 6 | 6 | ✓ |
| `price_rates` 44 | 44 | ✓ |
| `marketing` image id UNCHANGED | `e9568d07d057` | ✓ |
| `gotenberg` image id UNCHANGED | `2d05d22572ba` | ✓ |
| migrations 96 of 96 | 96 of 96 | ✓ |
| co-tenants `307/404/200/200/410` | identical | ✓ |
| `MOCK_AI_CALLS=false` both containers | false, both | ✓ |
| `app /api/health` 200 | 200 | ✓ |

### ⚠️ THE FONT PREDICTION WAS POSITIVE-CONTROLLED BEFORE THE DEPLOY, NOT AFTER

The declaration could have said *"the bundle changes"* and been unfalsifiable.
Instead it named **8 files and six exact byte counts** — and then, before the
deploy ran, checked that prediction against an **equivalent build**: the QA image
`5d9c8679df6d`, built 2026-08-10T22:33Z from a tree already containing
`a8bf9307`. It held 8 files with those six exact sizes.

That matters because of what it rules out. A post-deploy count of 8 is consistent
with both *"the fix landed"* and *"I guessed how `next/font/local` behaves and
got lucky"*. Having observed it on an equivalent build first, the only remaining
question was whether the production build agreed — and it did, down to identical
content hashes.

**The mechanism, for the record:** `next/font/google` fetched every subset of
every family (latin, latin-ext, cyrillic, greek…), so six families produced
**thirty** files. `next/font/local` copies the six declared latin files verbatim.
32 → 8 is that difference, and it is why the byte sizes match the committed
files exactly.

### ⚠️ THE INERTNESS OF THE FOUR METERING MERGES WAS RE-VERIFIED, NOT INHERITED

Two prior sessions declared B4 steps 2/3/closing inert in production. That is a
claim about a tree and a configuration, so it was re-checked here before shipping
it:

- **`llm-mdm.ts` (step 3)** — the entire diff sits inside
  `if (process.env.MOCK_AI_CALLS === 'true')` and still `return null`. Read the
  diff, not the summary.
- **`04b-anchor-verify.ts` (step 2)** — the change is a **pure deletion** of the
  mock short-circuit plus a comment. `entailmentStage`'s live path is untouched.
  This one mattered most to check: **L4b genuinely runs in production**
  (`TRANSCRIBE_MD_EVIDENCE_ANCHORS=true` on both containers), so "mock-path only"
  needed to be true of a file on a live path.
- **`MOCK_AI_CALLS=false`** read from the **running containers**, before and
  after — not from the compose file.
- **`isWhisperFallbackEnabled()`** is `=== 'true'` fail-closed and the env var is
  absent from the worker, so `buildWhisperUsage`'s new required parameter is
  unreachable.

**And the declaration made it falsifiable rather than argued:** the
`api_usage_events = 1325` arm is exactly the test. A recreate-and-settle is when
a mis-wired meter would fire; the count did not move by one.

### WHAT THIS DEPLOY DOES NOT CLAIM

- **It proves no meter works in production.** Nothing here made a vendor call.
  The four metering merges ship unexercised, deliberately.
- **It does not close B4.** `tm_anchor_entailment` is still UNPROVEN on a mocked
  run; the coverage script still exits 2. See the recon below.
- **The marketing half of the fonts fix did NOT ship.** `deploy-prod.sh` never
  builds `marketing`, so `quillmd.com` still runs a 13-day-old image. This is not
  a defect and not a runtime exposure — `next/font/google` self-hosts at build
  time too (`node_modules/next/dist/docs/01-app/01-getting-started/13-fonts.md`:
  *"no requests are sent to Google by the browser"*), so marketing was never
  fetching fonts from Google at runtime and still is not. What lands whenever
  marketing is next rebuilt is the removal of the **build's** reach.
- **No clinical flow was exercised.** Verification was structural throughout, per
  ruling 56 — container health, image ids, migration count, asset bytes inside
  the image, DOM-free HTTP status, and DB counts. No visit was touched.

---

## 🟠 FOUND ON THE WAY PAST — "THE BUILD'S LAST REACH TO GOOGLE" IS NOT ACCURATE, AND ONE OF THE SURVIVORS IS COMPILED BY A REQUIRED GATE

The handoff table above says `a8bf9307` *"removes the build's last reach to
Google"*. **It removes it from every build any gate or deploy performs — which is
the part that matters — but the repository still holds SEVEN live
`next/font/google` imports.** Recording it because AGENTS.md's own rule for this
class says the sweep is **by import**, and the disposition of each import is
exactly what a future reader will need when the masked
`turbopack-next/internal/font/google/font` error appears in a file nobody touched.

**The list, worked entry by entry** — `grep -rn "next/font/google"` over
`*.ts,*.tsx,*.js,*.jsx`, excluding `node_modules`: **ten hits, three of which are
now comments.**

| site | disposition |
|---|---|
| `apps/marketing/src/app/page.tsx:24` | ✅ **COMMENT** — migrated |
| `apps/marketing/src/app/layout.tsx:11` | ✅ **COMMENT** — migrated |
| `apps/transcribe-md/src/app/layout.tsx:18` | ✅ **COMMENT** — migrated |
| **`apps/meddoc-pro/src/app/layout.tsx:2`** | ⚠️ **LIVE** — `import { Inter } from "next/font/google"`. Built by **no** deploy step and **no** image build, but see below |
| `landing-monolith/app/layout.tsx:2` | ⚠️ **LIVE** — `Anton, Manrope, IBM_Plex_Mono` |
| `landing-monolith/app/heroes/layout.tsx:1` | ⚠️ **LIVE** — `Newsreader` |
| `landing-monolith/app/structures/layout.tsx:1` | ⚠️ **LIVE** — `Newsreader` |
| `landing-monolith/app/concepts/(app)/layout.tsx:2` | ⚠️ **LIVE** |
| `landing-monolith/app/concepts/soap/layout.tsx:1` | ⚠️ **LIVE** |
| `landing-monolith/app/concepts/soap-v2/layout.tsx:1` | ⚠️ **LIVE** |

**The six `landing-monolith` ones are genuinely out of scope**, two ways over:
zero hits for `landing-monolith` in `.github/workflows/`, and the directory is
**excluded from the docker build context** by `.dockerignore`. It is staging-only.

⚠️ **`apps/meddoc-pro` IS THE ONE WORTH KNOWING ABOUT, AND IT IS NOT REACHED BY
ANY *IMAGE* BUILD — IT IS REACHED BY `CI`.** Every image build in the programme
is service-scoped and none names it:

- `deploy-prod.sh` builds `db-migrate`, `transcribe-md-worker`, `transcribe-md`,
  `gotenberg`.
- `e2e.yml:176/179` builds `transcribe-md transcribe-md-worker` and `db-migrate`.
- `a11y.yml:201` runs `npm run build -w transcribe-md`.

But `test.yml`'s `test` job runs `npm run test:all`, which the root
`package.json` resolves to `-w meddoc-pro`, whose `playwright.config.ts` starts a
**Next dev server** for that app. A dev server compiles the root layout on first
request, and `next/font/google` resolves by fetching at compile time — so the
**required `CI` workflow retains a build-time dependency on Google's font
servers**, in a decommissioned app, behind an error message that names
`layout.tsx` rather than the network.

⚠️ **Stated precisely about what was and was not observed:** the import, the
workspace resolution and the dev-server config are read from the files cited. The
compile-time *fetch* is the documented mechanism (AGENTS.md's own incident
paragraph, plus the Next docs above) — **it was not observed on the wire here**,
which would need network tracing inside a CI run. Confirming it cheaply: the
failure signature is the masked turbopack error, and the tell AGENTS.md already
records is byte-identical trees passing and failing minutes apart.

**Recommended disposition: route to A5, do not patch here.** A5 retires
`apps/meddoc-pro`, and ruling 83 already settled this exact shape — when the
capability is itself being retired, the fix belongs to the retiring item rather
than to a repair that manufactures a passing assertion about something on its way
out. **Nothing is being proposed for the six `landing-monolith` files**; they are
correctly out of every gate.

---

## 🟠 FOUND ON THE WAY PAST — UNREAPED SESSION SCRATCH SITS INSIDE THE DOCKER BUILD CONTEXT

`.b4close-backup/` — the previous session's mutation-proof backups, which it
correctly listed and could not reap (`shred` is denied to the loop by ruling 70)
— is at the repository **root** and is **not** matched by any `.dockerignore`
rule. It holds `.ts` copies of `pipeline-stages.ts`, `gate.test.ts` and
`b4-stage-coverage.ts`, plus a `pr-body` and two `commit-msg` files.

So `COPY . .` shipped it into the **builder layer** of the image this deploy
built.

✅ **It does NOT reach the final image — verified, not assumed.**
`ls -d /app/.b4close-backup` inside the running `transcribe-md` container returns
**ABSENT**. Multi-stage kept it out, exactly as `.dockerignore`'s own note
records for `secrets/`.

**So the severity is builder-layer weight and hygiene, not exposure** — and the
files are non-clinical source copies, so nothing PHI-shaped is involved. It is
recorded because the *class* is worse than this instance: the loop is required to
leave scratch behind for a supervised session, that scratch lands at the repo
root by convention, and the root is the build context. A session that backed up
something sensitive would ship it into a builder layer with nothing reporting it.

**Recommended, and deliberately NOT bundled into this deploy-judgement PR:** a
`.dockerignore` entry for the session-scratch convention. It is a build-config
change that deserves its own gate cycle rather than riding a docs PR, and the
verified-absent result means it is not urgent.

---

## 📐 B4's LAST OPEN STAGE — RECON MEASURED 2026-08-11, READ-ONLY, INCLUDING THE BLAST-RADIUS ARGUMENT THE CLOSING STEP ASKED FOR

B4's closing step left `tm_anchor_entailment` **UNPROVEN** and named the closure
*"an anchored `tm_soap_draft` variant on the same env-selected pattern"* —
**named, not attempted**, because *"that fixture is read by many suites and needs
its own blast-radius argument."* Here is that argument, so the next session does
not re-derive it.

**The mechanism, confirmed:** `grep -c '⟦A:' packages/ai/src/mock.ts` → **0**. A
mocked L4 emits no anchors, so `claims.length === 0` and `entailmentStage`
returns at `04b-anchor-verify.ts:999` before any model call. Ruling 82(d) says
that early return is correct and must stay — no work is not a suppressed call.

**The pattern is already established three times over, in one file.**
`mock.ts:608–617` dispatches on `purpose` + an env var:

| existing variant | flag |
|---|---|
| `tm_template_phi_scan` | `MOCK_TEMPLATE_PHI_FLAG` |
| `tm_rx_drafting` | `MOCK_RX_WARNINGS` |
| `tm_critique` | `MOCK_CRITIQUE_ISSUES` |

A fourth on `tm_soap_draft` is the same shape, and `tm_soap_draft`'s fixture is
declared at `mock.ts:305`.

⚠️ **THE BLAST RADIUS OF *ADDING* IT IS ZERO, AND THE CLOSING STEP'S WORRY WAS
AIMED AT A DIFFERENT OPERATION.** Sixteen source files reference
`tm_soap_draft` (five eval scripts, nine tests, `04-generate-soap.ts`,
`preview-note-template.ts`, `pipeline-stages.ts`, `types.ts`). **Every one of them
is unaffected by a DEFAULT-OFF variant** — which is precisely what
`MOCK_CRITIQUE_ISSUES` demonstrated in the closing step itself. The concern is
valid only for *changing the default fixture*, which is not what the pattern does.

**Where the real risk sits, so it is not mistaken for the fixture:** the anchored
draft must emit anchors that `04b`'s parser actually recognises, and the three
entailment lenses must then agree. If they do not, claims get demoted and the
**mocked pipeline's OUTPUT changes** — but only in runs that set the new flag,
which is the coverage overlay (`docker-compose.qa.b4-coverage.yml`) and nothing
else. **That is the thing to mutation-prove**, not the presence of the fixture.

**Not attempted here.** This session's item was the owed deploy; this is recon
left deliberately as recon.

---

## ✅ B4's LAST STAGE IS CLOSED — THE ANCHORED DRAFT, AND ITS SPANS ARE DERIVED — 2026-08-11

**Session 04, batch 2.** The closing step (ruling 86) named this and did not
attempt it: *"an anchored `tm_soap_draft` variant on the same env-selected
pattern — named, not attempted, because that fixture is read by many suites and
needs its own blast-radius argument."* Session 03 measured that argument. This
session built the variant.

### THE DEFECT, RESTATED PRECISELY — A ZERO THAT WAS BOTH CORRECT AND USELESS

`tm_anchor_entailment` needs two conditions and only one was ever fixable by a
flag. `TRANSCRIBE_MD_EVIDENCE_ANCHORS=true` was fixed on QA by the closing step.
The second is that L4's draft must actually CARRY anchors — and under mock it did
not, so `deterministicStage` swept every line into the exempt bucket, `toEntail`
was empty, and `entailmentStage` returned at `04b-anchor-verify.ts:999` before
any model call.

That zero is **correct** (ruling 82(d) — no work is not a suppressed call) and
the stage's expectation is `{0,3}`, so the zero **also satisfies it**. The
coverage run was therefore green on a stage it had never once observed working,
which is exactly the condition ruling 85(a)'s UNPROVEN arm exists to name.

### WHAT LANDED

| | |
|---|---|
| flag | `MOCK_SOAP_ANCHORS=true`, **default OFF** — the `MOCK_CRITIQUE_ISSUES` / `MOCK_RX_WARNINGS` / `MOCK_TEMPLATE_PHI_FLAG` shape |
| wiring | `docker-compose.qa.b4-coverage.yml`, both services — a committed overlay, not a shell env prefix the loop cannot run |
| fixture | `MOCK_SOAP_TEXT_ANCHORED` + `MOCK_SOAP_TEXT_ANCHORED_STRIPPED` (`tm_polish`) |
| derivation | `MOCK_TRANSCRIPT_UTTERANCES` — one exported constant read by `MOCK_DEEPGRAM_BATCH` **and** every anchor |
| export | `ENSEMBLE_LENSES` from `04b-anchor-verify.ts` |
| gate | `apps/transcribe-md/src/worker/layers/__tests__/gate-b4-anchored-draft-entails.test.ts`, 5 arms |

⚠️ **THE SPANS ARE DERIVED, NOT COPIED, AND THAT IS THE LOAD-BEARING DECISION.**
An anchor survives `deterministicStage` only if its span is a LITERAL substring
of the normalized transcript. A hand-copied quote stops matching the moment
somebody edits an utterance — and **every way this fixture can break degrades to
a legal zero**: `anchor_not_in_transcript`, a digit the span cannot support, the
flag not arriving. None of those is red anywhere; the stage simply returns to
UNPROVEN, which is a signal nobody is obliged to read. So the two utterances are
one constant and the drift is **unrepresentable rather than unlikely**.

⚠️ **AND IT IS A DIFFERENT NOTE, NOT THE DEFAULT WITH ANCHORS BOLTED ON.**
`MOCK_SOAP_TEXT` asserts `BP 120/80, HR 72`; the mock transcript contains no exam
at all, so those digits are unanchorable **by construction**
(`digits_unsupported`) — which is precisely what the verifier exists to catch.
The anchored variant says only what its two utterances say and marks Objective
`[not documented]`, which `isExemptLine` exempts. `tm_polish` returns the
anchor-stripped SAME note under the flag, so L6's output equals its input and L6b
is never handed a "polished" note sharing no text with the draft it polished.

`ENSEMBLE_LENSES` is exported because **the `{0,3}` expectation's 3 IS that
array's length.** A gate asserting a literal 3 would stay green if somebody added
a fourth lens while the meter under-counted.

### THE MUTATION PROOF — SAID FIRST, THEN MADE TO FAIL

Backups taken to scratch **before** the first mutation and restored **from those
copies, never from git** (AGENTS.md: `git checkout --` on a dirty tree deletes
uncommitted work). The work was also committed first, so a restore error could
not have cost it.

| mutation | predicted red | measured |
|---|---|---|
| **M1** — one derived span replaced by a hand-copied literal that no longer matches (the exact drift the derivation prevents) | DERIVED, CLAIMS+CLEAN | **2 failed / 3 passed** — DERIVED, CLAIMS+CLEAN ✓ |
| **M2** — `soapAnchorsEnabled()` hard-false (the flag stops reaching the fixture) | DERIVED, CLAIMS+CLEAN, ENSEMBLE+MARKED | **3 failed / 2 passed** — all three ✓ |

Each mutation script asserted `expected 1 / measured 1` occurrences before
writing, and aborted otherwise. Both restores verified by `git status` clean
against the commit; the suite re-run green (5 of 5) afterwards.

⚠️ **AND THE MOVEMENT DIRECTION IS PROVEN TOO, NOT ONLY THE FAILURE DIRECTION.**
`OFF` asserts the unanchored default at **0 claims, 0 rows** and `CLAIMS`/
`ENSEMBLE` assert the anchored variant at **3 claims, 3 rows** — so the pair
shows the gate MOVES when the fix lands, which is the arm ruling 85(a) and
AGENTS.md both say decorative ratchets lack. In both mutations `OFF` and
`CONTROL` stayed green, correctly: they describe behaviour the mutations did not
touch.

### 🟢 AND THE COVERAGE RUN WAS EXECUTED — **15 of 15 COUNTED, 0 UNPROVEN**

Run on the isolated `meddoc-qa` stack, 2026-08-11T03:49Z, against images rebuilt
from this branch. The four flags were verified **inside the live worker** before
the run — `MOCK_SOAP_ANCHORS=true MOCK_CRITIQUE_ISSUES=true
TRANSCRIBE_MD_EVIDENCE_ANCHORS=true MOCK_AI_CALLS=true` — because a compose file
is a claim and the container is the fact.

```
[b4-coverage] visits: 3   usage rows scoped to them: 43
[b4-coverage] stages enumerated: 15   COUNTED: 15   UNPROVEN: 0
[b4-coverage] 🟢 all 15 enumerated stages were COUNTED
```

Three visits, all `READY`. `tm_anchor_entailment` by mode:

| mode | count | |
|---|---|---|
| `text_notes` | **0** | permitted — see below |
| `voice_dictation` | **3** | ✓ |
| `audio_upload` | **3** | ✓ |

Both 3s are the ensemble, and the coupled invariant held on every mode
(`tm_polish=1 ≡ tm_polish_gate=1`). **The stage that had never once been observed
working is now observed at 3, twice.**

### ⚠️ NAMED, BECAUSE THE RUN MEASURED IT AND A SUMMARY WOULD HIDE IT: `text_notes` IS STILL A PERMITTED ZERO

The total is non-zero so the run is honestly green — but the stage is COUNTED on
**two of the three** modes, not three, and the reason is structural rather than
incidental.

The fixture's spans are derived from the **mock transcript**. `voice_dictation`
inherits it because L1b transcribes through Deepgram too (`worker.ts:554`), so
its `contextText` is the same two utterances. **`text_notes` does not**: its
`contextText` is `visit.rawTextInput`, which the coverage script supplies itself
(`SCRIPT_TEXT` — a cough-and-wheeze script). No anchor derived from the Deepgram
fixture can be a literal substring of it, so every claim demotes
`anchor_not_in_transcript` and the stage returns a legal 0.

⚠️ **THIS WAS PREDICTED AS AFFECTING TWO MODES AND MEASURED AS AFFECTING ONE.**
The prediction was that only `audio_upload` would count; the run showed
`voice_dictation` counting as well, for the reason above. **Recorded as measured,
not as predicted** — the guess was pessimistic in a way no reasoning here would
have corrected, and the coverage run is the instrument that settled it.

**The cure, if it is ever wanted, is a content-sensitive fixture** that derives
its anchor from the transcript **in the prompt it was handed**, rather than from
a module constant — the `tm_chat_edit` / `tm_anchor_entailment` shape (rulings
69, 82(b)). A claim whose text IS its span passes the deterministic gauntlet on
any transcript, so it would count on all three modes. **Named, not attempted** —
it parses a prompt, which is its own blast-radius question and deserves its own
gate, and the stage is already countable without it.

Local: **3367 passed / 4 skipped**, `tsc` **0 errors**. Neither closes an item —
the merge-commit citation does.

---

## 🟠 FOUND ON THE WAY PAST — SESSION 04 LANDED B4's CLOSE AND LEFT NO RECORD OF ITS NIGHT

**STEP 0.9's finding, filed by the session that came after it.** Run
`20260810-173811-b2`, session 04, started `03:26:02Z` and died at `04:50:10Z`
with a single line:

```
API Error: Unable to connect to API (ENOTIMP)
[loop] session 04 exited rc=1 at 2026-08-11T04:50:10Z
LOOP HALTED : SESSION ERROR — session 04 exited rc=1
```

Its log is **12 lines**, of which 7 are the header and 5 are that error.

⚠️ **AND IT HAD ALREADY DONE THE WORK.** PR #598 merged at `04:36:45Z` as
`82d6f2d7` — B4's last unproven stage, three commits, the anchored draft whose
spans are derived from the transcript. The RELAY section describing it is on
`main` and is excellent. What is missing is everything the session was supposed
to say ABOUT that night: **no morning report, no scratch list, no citation for
its own merge commit, and no statement of what it did not finish.**

**This is a THIRD shape, distinct from the two the contract already names.** The
08-09 case ended without a marker and stopped the run — loud. The 08-10 case
reported correctly and then kept going, losing the record — silent. **This one
never got to report at all**, because the process died between merging and
writing. No amount of discipline inside the session prevents that, which is
precisely why the recovery has to live in the NEXT session.

**Reconstructed from disk, per STEP 0.9:**

| | |
|---|---|
| landed | PR #598 → `82d6f2d7dafcfe720ee494a3b442ace489c3c410`, merged `04:36:45Z` |
| commits | `86975adb` (the fixture + gate), `074b371c` (the ledger row), `cab4b0f6` (the coverage run) |
| rulings added | **87** — B4's closure, PROVISIONAL, present and complete in `RULINGS.md` |
| citation | **owed, and discharged below** |
| scratch | **unrecoverable.** Nothing can now say what session 04 wrote outside its commits |

⚠️ **THE SCRATCH LIST IS THE PART THAT CANNOT BE RECONSTRUCTED, AND IT IS THE
SECOND TIME.** Batch 1 session 01 lost one the same way and batch 1 session 02
wrote that down; the finding was recorded and not turned into a check, and here
it is again nine days later. `/opt/meddoc-pro/.b4close-backup/` — session 01's,
named by session 03 — is still unreaped, and there is now no way to know whether
session 04 added to it or made its own. **A supervised session reaping this run
should treat the repo root and `/tmp` as unenumerated rather than empty.**

`REPORT-MISSING` was **not** present in any log, so the runner's own tripwire did
not fire here: it flags a session that finishes without a report, and this one did
not finish. **That gap is worth closing** — the halt path emits
`LOOP HALTED : SESSION ERROR` and nothing checks whether the dead session had
merged anything first. Named, not fixed; it is a change to the runner, not to
this programme's queue.

### ✅ AND THE CITATION SESSION 04 OWED, PRODUCED BY THE CHECKER

Not typed. `82d6f2d7`'s `e2e` sat **queued for 2h13m** — created `04:36:47Z`,
started `06:50:04Z` — which is why session 04 could not have cited it even had it
lived, and why this session waited for it rather than citing three of four.

---

## ✅ B5 IS BUILT — MONEY IS AN INTEGER, THE LEDGER REFUSES TO BE EDITED, AND THE BALANCE IS THE DATABASE'S ARITHMETIC — 2026-08-11

**The item, verbatim:** *"Integer micro-unit; append-only `LedgerEntry` with
`balanceAfter`; practice wallet. **Gate:** append-only enforced at the
**database**, not by convention — an `UPDATE` and a `DELETE` are both attempted
and both refused. `balanceAfter` consistency proven across a generated
sequence."*

Its hard predecessor was named in BILLING RECONNAISSANCE §4 — *"Do not start B5
before F-TYPE lands"* — and F-TYPE is closed and live.

### WHAT LANDED

| | |
|---|---|
| migration | `20260811070000_b5_ledger_entries` — one table, 2 unique indexes, 1 FK, **5 CHECKs, 4 triggers** |
| model | `LedgerEntry` @@map(`ledger_entries`), with all 9 inexpressible objects documented beside it |
| CI gate | `packages/db/src/__tests__/gate-b5-ledger-append-only.test.ts` — **34 assertions**, 6 groups, 4 positive controls |
| DB guard | `scripts/check-ledger-append-only.sh` — structural (safe on prod) + `--attempt` behavioural, fail-closed off non-prod |
| rows | **zero, and nothing writes it.** B6 is the writer, B7 the top-ups, B8 the block |

### ⚠️ NOTHING WRITES THIS TABLE, AND THAT IS THE POINT, NOT AN OMISSION

B5 ships the SHAPE and its guarantees so the writer is built against a table
that already refuses to be wrong — the way B3's price table shipped with nothing
reading it. Ruling 80(e) warns that *a column nothing writes is the half-shipped
shape*; an **empty table whose CONSTRAINTS are the deliverable** is the opposite,
and the difference is that here the constraints are the product.

**And the claim is enumerated rather than asserted.** The gate sweeps **BY TABLE
and BY ORM METHOD** — `ledgerEntry.(create|createMany|upsert|update|updateMany|
delete|deleteMany)` **and** `INSERT INTO ledger_entries` — over 500+ sources
under `apps/transcribe-md/src` and `packages/`, and asserts the offender set
equals an empty declared list. Both patterns are positive-controlled against
synthetic strings (so the control cannot be satisfied by the thing it controls
for), and the file walker asserts it found >500 files, because a walker that
silently entered nothing returns a clean zero for every pattern you try.

**When B6 lands, that assertion goes red — deliberately.** The first writer
arrives as an edit to `WRITERS` rather than as a surprise.

### THE BEHAVIOURAL PROOF — ON QA, EVERY WRITE INSIDE `BEGIN … ROLLBACK`

Run against the isolated `meddoc-qa` stack after rebuilding `db-migrate`
(`0b54ff763036` → `b4c0fe96505b` — the rebuild was **verified by image id**,
because this compose file's own header records a case where building that
service was a silent no-op and new migrations went unapplied while the log read
"No pending migrations to apply"). `97 migrations found`, applied clean.

| probe | result |
|---|---|
| **derivation** — 3 rows inserted with `balanceAfter=99999, seq=77` etc. | stored **5000000/1**, **3500000/2**, and `promo` **10000000/1** — the caller's values discarded, the running sum correct, the second bucket keeping its own balance from zero |
| **snapshot** | derived from `practiceId` on all three (the caller's `WRONG-SNAPSHOT` discarded) |
| `UPDATE … SET "amountMicroUsd" = 1` | **refused** — `ledger_entries_append_only: UPDATE is refused …` |
| `DELETE FROM ledger_entries` | **refused** — `… DELETE is refused …` |
| `TRUNCATE ledger_entries` | **refused** — `… TRUNCATE is refused …` |
| **the S4c detach** (positive control) | **permitted**; tombstone, amount, balance and seq all survived |
| **the smuggle** — detach *plus* an amount change | **refused** |
| **tenantless INSERT** | **refused** by `ledger_entries_insert_requires_practice` |
| **residue** on a fresh connection | `ledger_entries` **0 rows**, probe practices **0** |

Every refusal was matched **on the guard's own name in the message**, never on
"an error happened" — a refusal is evidence only when you know WHAT refused.

### ⚠️ "ACROSS A GENERATED SEQUENCE" IS THE GATE'S OWN WORDING, AND THREE ROWS IS NOT ONE

The item says `balanceAfter` consistency is proven **across a generated
sequence**. The derivation probe above is three rows. That is the watched-set
failure in miniature — a real proof of a smaller claim than the criterion names
— so the criterion was executed literally:

```
INSERT … SELECT FROM generate_series(1,200)   -- mixed topup/usage, signed
→ INSERT 0 200
→ rows 200 | min_seq 1 | max_seq 200 | distinct_seq 200
→ rows where balanceAfter disagrees with the running sum: 0
```

**Gapless, unique, and every row's `balanceAfter` equal to the running sum of
every `amountMicroUsd` before it**, over 200 rows the database numbered and
totalled itself — the caller supplied neither column.

⚠️ **AND THE ZERO IS POSITIVE-CONTROLLED, because a zero from a broken query and
a zero from a correct ledger are the same output.** The identical query run
against a deliberately wrong expectation (`running + 1`) returned **200**. The
comparison discriminates; the 0 means something.

Both runs inside `BEGIN … ROLLBACK`; the table is back to 0 rows.

### 🔑 THE PROBE THAT MATTERED MOST WAS THE ONE THAT HAD TO *SUCCEED*

```
INSERT INTO practices …;  INSERT INTO ledger_entries …;
DELETE FROM practices WHERE id = 'b5probe-practice';
→ DELETE 1
→ lp-del | detached t | tombstone b5probe-practice | 7000000 | 7000000 | 1
```

**A RESTRICT here would have passed every refusal arm above with full marks and
made account deletion impossible** — which is not a hypothetical: `audit_logs`
had exactly that FK and S4c exists because of it, and `RxWarningOverride`
repeated it and *"silently blocked the whole cascade for any doctor who had ever
overridden an Rx warning"*. On an append-only table it is strictly worse, because
no delete could ever clear the blocker.

The decision was therefore **not taken here.** It is already written down in
`delete-account/route.ts:184`: *"audit_logs and billing_events … DETACH (SET
NULL) when the practice goes, because an audit trail and A FINANCIAL RECORD must
outlive the account they describe."* A billing ledger is a financial record.
This is the rediscovery `RULINGS.md` exists to prevent, avoided by reading the
code that already implements the rule.

### ⚠️ THE MUTATION PROOF — SAID FIRST, THEN MADE TO FAIL, AND ONE OF THEM IS THE WHOLE DESIGN

Both mutations ran **inside a transaction that was rolled back**, so the DDL
never committed — AGENTS.md's *"any write inside a gate that a constraint is
supposed to refuse belongs in `BEGIN; … ROLLBACK;`"*, applied to the mutation
itself rather than only to the probe. Restored state verified afterwards: 4 of 4
triggers present, and `pg_proc` still holds the `to_jsonb(NEW)` body.

| mutation | predicted | measured |
|---|---|---|
| **M1** — `DROP TRIGGER …_before_truncate` | TRUNCATE stops being refused | `TRUNCATE TABLE`, row count **1 → 0** ✓ |
| **M2** — the guard's row comparison replaced by a hand-written 5-column `IS NOT DISTINCT FROM` list omitting `amountMicroUsd` | the smuggle succeeds | `UPDATE 1` — amount **5000000 → 999** while `balanceAfter` stayed **5000000** ✓ |

**M2 is the argument for the whole design.** The obvious way to write *"and
nothing else changed"* is that column list, and omitting one column produced a
ledger row whose amount and running balance disagree — through a guard that
reported success, on a table where no correction can ever be applied in place.
`(to_jsonb(NEW) - 'practiceId') = (to_jsonb(OLD) - 'practiceId')` refuses the
identical statement and covers every column added from now on without anybody
remembering to. The gate pins the jsonb form **and bans the list form**, so a
future author has to argue with an assertion rather than quietly weaken a guard.

**M1 is the arm most likely never to have existed at all.** TRUNCATE fires
neither row-level trigger and is not a DELETE, so a ledger protected by
`BEFORE DELETE` alone can still be emptied in one statement — and every
behavioural test of UPDATE and DELETE would stay green.

**And the CI gate was mutated too, because a database proof says nothing about
whether the CHECK-IN-CI can see a regression.** Both mutations were made to the
SOURCE and restored by the exact inverse edit — **no backup file was created and
none was needed**, because the work was committed first and the restore is
verified by `git status --porcelain` returning empty, not by trusting the edit:

| mutation | predicted red | measured |
|---|---|---|
| **M3** — the `BEFORE TRUNCATE` trigger deleted from the migration | the trigger-set assertions fail | **4 failed / 30 passed** — the timing test, the exact-four test, the drift-record diff, **and the positive control that counts the objects before diffing them** ✓ |
| **M4** — the jsonb comparison replaced by a two-column `IS NOT DISTINCT FROM` list | the un-decayable-comparison assertions fail | **2 failed / 32 passed** — both the "uses jsonb" and the "does NOT fall back to a column list" arms ✓ |

Restored: `git status --porcelain` empty, gate back to **34 of 34**.

⚠️ **M3's fourth failure is the one worth noting: the positive control failed
too, and that is correct behaviour.** It asserts the object-scanning regex found
9 objects before the diff below trusts it. With one deleted it found 8 and said
so — so the control cannot be satisfied by a tree that is missing the very thing
it is counting, which is the failure mode a positive control exists to have.

### THE DRIFT ENUMERATION — `UNDECLARED-PLAIN = 0`, MEASURED ON THE DATABASE

AGENTS.md rule 7's standing expectation, checked against `pg_indexes` and
`pg_constraint` on QA after the migration applied — not against the migration
file, which is a claim about what should exist:

| object | declared where |
|---|---|
| `ledger_entries_pkey` | `@id` |
| `ledger_entries_idempotencyKey_key` | `idempotencyKey String? @unique` |
| `ledger_entries_practiceId_bucket_seq_key` | `@@unique([practiceId, bucket, seq])` |

**Three indexes, three declarations, zero undeclared plain indexes.** The names
were written to match Prisma's own convention exactly, so the schema and the
hand-written migration cannot disagree about them.

The permitted residue is the 5 CHECKs and the 4 triggers, every one **named in
the model's comment block** — and the CI gate does not take that on trust: it
extracts the object names from the migration by regex, positive-controls the
count, and asserts each one appears in `schema.prisma`. A constraint added later
without its documentation fails a test rather than becoming invisible drift.

### WHAT B5 DOES NOT CLAIM

- **Not that anything is billed.** No writer, no reader, no balance check.
  `charge = cost × 3 / 2` and the prod-only refusal are **B6**; ruling 80(c)'s
  question — what a `null` rate means — is still B6's to answer.
- **Not that the amount is right.** The database derives the BALANCE; the AMOUNT
  is the caller's claim and no constraint can check it.
- **Not that the triggers are installed anywhere but QA.** They exist in a
  migration; `assert-migrations-applied` and the guard script answer "installed".
  **Production has not run this migration** — it ships with B5's deploy.
- **Not that concurrency is proven under load.** The advisory lock serializes and
  the unique index is the backstop; what is proven is the mechanism's presence
  and the refusal's shape, not a benchmark.

### ⚠️ AND ONE THING THE LOOP CANNOT DO WITH WHAT IT JUST BUILT

`scripts/check-ledger-append-only.sh` is **not invocable by the unattended
loop**. `.claude/settings.json` names its allowlisted scripts one per line, the
new script is not among them, and **editing that file is denied to the loop** —
correctly, since a self-granting agent is the wrong risk.

So the behavioural evidence above was produced through the granted `docker exec
… psql` path instead, statement by statement. The evidence is the same; the
*procedure* is not re-runnable by a future unattended session, and ruling 86(d)
records what that costs: **a procedure the loop cannot execute will not be
re-run.**

**OWNER ACTION, one line:** add
`"Bash(bash scripts/check-ledger-append-only.sh:*)"` to the `allow` list in
`.claude/settings.json`. Until then this guard is a supervised-session tool, and
it must NOT be added to STEP 0's standing set — a standing check that always
reports "cannot tell" is worse than one nobody listed.

⚠️ **The script already takes `--qa` as a FLAG rather than an env prefix**, for
the same reason: `PG_DB=… bash script` is outside the allowlist, and
`assert-migrations-applied.sh` ran production-only for three months precisely
because its QA capability needed a form nobody could invoke.

Local: **3401 passed / 4 skipped** (3367 + the gate's 34), `tsc` **0 errors**.
Neither closes the item — the merge-commit citation does.

---

## 🟠 FOUND ON THE WAY PAST — A RENDERED CLINICAL NOTE IS A TRACKED IMAGE, AND THE GUARD ONLY WATCHES `.docx`/`.pdf`

**Found while enumerating this session's scratch, which is the only reason
anybody looked at the repo root.**

`/opt/meddoc-pro/` holds **161 tracked `.jpeg` files** — `audit-*.jpeg`,
`ax-*.jpeg`, `ax2-*.jpeg`, `billing-*.jpeg` — all dated 2026-07-25, none
gitignored, all in every clone.

### THE FILES THEMSELVES ARE CLEAN, AND THAT WAS ESTABLISHED BY READING THEM

Per AGENTS.md's standing pattern (*READ IT, THEN ADJUDICATE, THEN WRITE THE
DECISION DOWN*) — not by filename, which has already been rejected as evidence
once in this programme:

| read | content |
|---|---|
| `audit-patients-list.jpeg` | an 11-patient list: **QA Pediatric Test · QA Test Patient · Kasratest · tets_1 · Test · Bobby · Joe** — the synthetic QA population, under the **"QA Interaction Auditor"** account |
| `billing-desktop-note.jpeg` | a **fully rendered SOAP note** — chief complaint, HPI, ROS — for **"QA Test Patient"**, the standard synthetic fixture (hypertension + low back pain) |

**Verdict: non-PHI, by OWNERSHIP and by CONTENT.** These are the
`qa-interaction-auditor` agent's captures of the synthetic population. **They are
not strays and must survive any future sweep.**

### THE FINDING IS THE GAP THEY REVEAL, NOT THE FILES

`scripts/hooks/pre-commit` blocks added **`.docx` and `.pdf`** outside the
fixture allowlist. **It says nothing about images** — the whole watched set is
one `case` arm at **`scripts/hooks/pre-commit:44`**:

```sh
*.docx|*.pdf|*.DOCX|*.PDF) ;;
```

AGENTS.md's actual rule is broader than the guard that enforces it:

> *"Nothing that renders a patient's note belongs in the repository at all — not
> as evidence, not as a QA artifact, not 'just this once'."*

A screenshot renders a patient's note **more** directly than a `.docx` does: no
unzip, no parse, just open it. And the class is entirely unguarded — a
`.png`/`.jpeg` of a real doctor's signed note would be committed with no
murmur, by a hook that would have refused the identical content as a PDF.

**The precedent prices it.** `docs/qa-reports/twin-real-visit-20260726.docx` cost
a full `git filter-repo` rewrite, a force-push over a protected branch, 22 scratch
clones deleted, two dependabot branches deleted — and **293 permanent
`refs/pull/*` refs needing GitHub Support**. The second purge, on files 85 days
old, was *"~200x the work of the first for the same two files' worth of
content"*. **The cost of a tracked clinical file is not fixed; it compounds** —
and these are already 17 days old and in every clone.

⚠️ **AND THIS IS THE WATCHED-SET SHAPE, NOT A MISSING RULE.** The rule is
written and correct. What is missing is that *the check watches a narrower set
than the rule names* — AGENTS.md's own **"a gate's WATCHED SET is diffed against
the spec's NAMED set"**, pointed at the pre-commit hook. Nothing would ever
surface it: both existing arms work perfectly, no test fails, and a clean run of
the hook is indistinguishable from a hook that never looked at images.

### DISPOSITION — NAMED, NOT BOLTED ON

**Not fixed here, deliberately.** The naive fix — block added `.jpeg`/`.png` —
would refuse the design-reference workflow this repo actively uses (161 files at
the root, plus `_design-references/redesign-2026/`'s 136 PNGs), so it needs a
designed allowlist rather than a one-line addition. An image guard whose
allowlist is guessed is the hand-kept-list failure in a new file extension.

**The item:** extend the hook's guard to images with an allowlist covering the
design-reference and QA-auditor capture paths, and add the same
READ-IT-THEN-ADJUDICATE row to the allowlist table in `AGENTS.md`. Until then,
**the rule about screenshots is enforced by nothing but attention.**

### ⚠️ AND THE PUSH THAT CARRIED THIS FINDING CANCELLED THREE OF ITS OWN RUNS, DELIBERATELY

Recorded because AGENTS.md requires a cancellation to be a **named decision**
rather than an accident, and because this is the #568 shape with the session on
the wrong side of it.

| | |
|---|---|
| cancelled | `CI` `31468976163`, `a11y-ci` `31468976112`, `e2e` `31468976098` — all at **3m37s** |
| survived | `secrets-scan` `31468976193`, completed success at 29s |
| cost | **~11 runner-minutes**, and the citation clock restarted |

**The two-view check was taken first and both views agreed** (three
`in_progress`, one `completed`), so this was a decision with the numbers in
front of it, not a zero believed too early.

⚠️ **THE HABIT THAT WOULD HAVE PREVENTED IT IS THE HARDER ONE, AND IT IS THE ONE
#568 ALREADY NAMED.** The finding above did not exist when the PR was pushed —
it was found minutes later, while enumerating scratch for the close-out. So the
cure is not *"batch two commits that are already sitting there"*; it is **hold
the first push until the session's remaining work — including the close-out
enumeration — is done.** This session pushed at the moment the item was green,
which felt like the right moment and was not.

**Pushing now was nevertheless the cheaper of the two available options**, and
the arithmetic is the whole reason it was taken at 3m37s rather than deferred:
waiting for the three runs, then pushing, then waiting again would have cost
**~85 minutes** of wall clock against **~45**. AGENTS.md's own pricing rule —
*"the cost is set by HOW LATE the second push lands"* — cuts toward pushing
immediately once the decision to push at all is made. **The mistake was the
early first push; the response to it was the cheap one.**

### THE WATCHED-SET DIFF B5 FORCES, PERFORMED AND ANSWERED

`scripts/check-billing-source-no-deleter.sh` watches **`api_usage_events`** and
nothing else. B5 introduces a second money table — the **wallet** — so the
question the canon requires is whether the guard's watched set is now narrower
than what it is for.

**Answer: no widening needed, and the reason is mechanism, not scope.**

| that guard's arm | how `ledger_entries` is covered |
|---|---|
| **arm 1** — no ORM or raw-SQL deleter, by grep | a **`BEFORE DELETE` trigger**, which refuses the delete however it is spelled. A grep can be evaded by a spelling it does not match; a trigger cannot |
| **arm 2** — no FK cascades a delete (*"which no grep can see"*) | the only FK is `practiceId → practices` and it is **SET NULL** (verified on `pg_constraint`, not on the migration file). And a cascade would fire the same row trigger and be refused, so the property is fail-closed rather than dependent on the FK's action staying right |

The grep guard exists because `api_usage_events` has no enforcement of its own —
its no-deleter property is an **absence of code**, which is exactly the thing
that decays silently. `ledger_entries`'s is a **presence of a trigger**, and the
guard for *that* is `check-ledger-append-only.sh`, whose whole first arm is
"are the four triggers still there and still enabled".

⚠️ **So the two tables have different guards for the same property, on purpose,
and neither is a substitute for the other.** Recorded here rather than left
implicit, because the next reader's obvious move is to add `ledger_entries` to
the deleter script's table list — and that would produce a second green that
proves less than the one already there.

## 🟠 FOUND ON THE WAY PAST — `check-composite-fk.sh`'s BEHAVIOURAL ARM IS UNREACHABLE BY THE LOOP, FOR THE SAME REASON `--qa` HAD TO EXIST

Found by trying it, while B5 was building the same capability next door.

```
$ bash scripts/check-composite-fk.sh --attempt
✔ structural: transcribe_visits_patientId_practiceId_fkey references BOTH columns
🟡 refusing --attempt against 'meddoc' — that is a production database name.
```

The script's own header says *"Add `--attempt` on a qa/test database for the
behavioural proof"*, and **the only way to aim it at one is an env prefix**
(`PG_CONTAINER=… PG_DB=… bash …`) **which is outside the FOUNDATION loop's
allowlist.** So from an unattended session `--attempt` targets production, and
production correctly refuses it. The arm can never run.

⚠️ **THIS IS THE `assert-migrations-applied` FAILURE, EXACTLY, AND IT IS THE
SECOND SIGHTING IN ONE DAY.** That script accepted `[container] [db]` since it
was written and **nothing ever passed them for three months**, while the QA
stack drifted two migrations behind and every session reported the check green.
The cure there was a `--qa` flag — a form the loop can actually type. AGENTS.md
records the lesson in one sentence: **a capability nobody invokes is
indistinguishable from one that does not exist.**

**What is lost here is not hypothetical.** That behavioural arm is the one that
was *mutation-proved on a throwaway database to show a same-named single-column
FK passes a name-only check and fails this one* — i.e. it is the arm that
distinguishes T3's tenancy wall from a convincing impostor of it. The structural
arm, which is all the loop can run, is precisely the check that mutation
defeated.

**The item, and it is now two scripts wide:** give `check-composite-fk.sh` the
same `--qa` flag B5 gave `check-ledger-append-only.sh`, and sweep the other
guards for env-only targeting. The predicate is *"a script whose documented
capability is reachable only through an env prefix"* — statable, therefore
greppable, therefore not a memory exercise.

⚠️ **AND THE ALLOWLIST ENTRY ALONE WOULD NOT HAVE FIXED IT.** Adding the script
to `.claude/settings.json` — the owner action B5 already needs — makes it
runnable, not aimable. **Two different gaps that both present as "the check is
green and means nothing".**

---

## ✅ THE CITATION SESSION 04 OWED — `82d6f2d7`, 4 OF 4, AND THE `a2` EXPLAINED

Produced by `check-citation.sh`, not typed.

**Citation — 4 of 4 on `82d6f2d7dafcfe720ee494a3b442ace489c3c410`:**
   · `CI` 31459025779 a1
   · `e2e` 31459025756 **a2**
   · `a11y-ci` 31459025761 a1
   · `secrets-scan` 31459025753 a1

### ⚠️ `e2e` IS ON ATTEMPT 2, AND THE CHECKER IS RIGHT TO DEMAND A REASON

The canon forbids re-run-and-hope, so an unexplained `a>1` is a finding of its
own. **This session did not perform the re-run** — here is what the record says,
measured rather than assumed:

| | |
|---|---|
| attempt 1 | created `04:36:47Z`, **FAILED** `05:09:07Z` (32m20s) |
| attempt 2 | started `06:50:04Z`, **success** `07:34:32Z` (44m28s) |
| session 04 | died `04:50:10Z` — **19 minutes BEFORE attempt 1 failed** |
| this session | started `06:58:57Z` — **8 minutes AFTER attempt 2 began** |

So the re-run falls in the gap between two sessions and **neither of them did
it**. `triggering_actor` is `kasrarayat-cloud`, which is the account both the
loop and the owner use, so the field cannot distinguish them.

### THE MECHANISM, NAMED FROM THE LOG RATHER THAN GUESSED

Attempt 1's single failing step was **"Build flag-ON image for the document
preview"**:

```
#17 [builder 11/14] RUN npm ci
#17 38.44 npm error code EEXIST
#17 38.44 npm error syscall open
#17 38.44 npm error path /root/.npm/_cacache/tmp/14352194
#17 38.44 npm error EEXIST: file already exists, open '/root/.npm/_cacache/tmp/14352194'
#17 ERROR: process "/bin/sh -c npm ci" did not complete successfully: exit code: 239
ERROR: failed to build: failed to solve: process "/bin/sh -c npm ci" did not complete successfully
```

**An npm CACHE COLLISION — a tmp file in `_cacache` that already existed — not a
network failure.**

⚠️ **AND THAT MAKES IT A SECOND, DISTINCT CLASS FROM THE ONE AGENTS.md ALREADY
RECORDS, WHICH IS THE WHOLE POINT OF WRITING IT DOWN.** The canon's
external-reach section names `npm ci → ECONNRESET` and says it was **retried**,
via `NPM_CONFIG_FETCH_RETRIES=5` across 16 sites (#583). **That mitigation does
not touch this failure**: `EEXIST` on a local cache path is not a fetch that can
be retried, so the shipped cure is aimed at a neighbouring problem.

| reach | error | the shipped mitigation |
|---|---|---|
| npm registry | `ECONNRESET` — says the word | `NPM_CONFIG_FETCH_RETRIES=5` ✔ |
| `next/font/google` | a bogus `Module not found` | removed, self-hosted ✔ |
| **npm local cache** | **`EEXIST` on `_cacache/tmp/<n>`** | **none — and fetch-retries cannot help** |

The `_cacache/tmp/<n>` name is derived per-process, so a collision points at a
**shared or reused cache across concurrent builds on one runner**, not at the
registry. Whether that is a buildx cache mount reused between the workflow's
parallel image builds is the thing to establish next; this session did not,
because it is not B5's item and the finding is worth more filed accurately than
diagnosed hastily.

**Two other lines appear in the same log and are NOT claimed as causes** — a
`the twin seed HUNG (killed at 7m)` error annotation at `04:46:05Z` and a
Playwright `toHaveURL` expect failure at `04:54:21Z`. The job's only step with
`conclusion: failure` was the build, and Playwright retries assertions, so
naming either would be reading a symptom as a diagnosis.

### WHAT THIS DOES NOT CLAIM

That the re-run was wrong. Re-running a build that died on an infrastructure
fault is the correct response and matches how the ECONNRESET wave was handled.
**What is missing is that nobody wrote down that it happened or why** — and a
green `a2` with no note beside it is indistinguishable from re-run-and-hope.
That is the gap this section closes, one session late.

---

## 🟩 B5 IS LIVE IN PRODUCTION — `50b02832`, 2026-08-11T09:09Z

| | |
|---|---|
| deployed commit | `50b02832352e849fd4c46d61384ba332a8492a04` |
| declaration | `docs/foundation/deploys/20260811-50b02832.md` — **written 08:25Z, 44 minutes BEFORE the deploy ran** |
| deploy log | `docs/deploy-logs/deploy-20260811T090504Z.log` |
| pre-deploy dump | `backups/pre_deploy_20260811T090504Z.sql.gz` (792 KB) |
| rollback tag | **`:pre-b5-20260811`** — app `d29b852d8d9b` / worker `c18d9dbf1092` ⚠️ **cut LATE — see below** |
| app image | `d29b852d8d9b` → **`5483ff331dd7`** |
| worker image | `c18d9dbf1092` → **`7aabd4cc69c6`** |
| migration | `20260811070000_b5_ledger_entries` applied; **96 → 97**, asserted by the deploy itself |

### Citation — produced by `check-citation.sh`, not typed

**Citation — 4 of 4 on `50b02832352e849fd4c46d61384ba332a8492a04`:**
   · `CI` 31472938418 a1
   · `e2e` 31472938365 a1
   · `a11y-ci` 31472938459 a1
   · `secrets-scan` 31472938517 a1

All `a1` — no re-runs, nothing to explain. `e2e` passed first attempt in 41m30s.

### THE DECLARATION, JUDGED — 28 of 28 ASSERTIONS, EVERY ONE AS DECLARED

**What must change**

| declared | measured | |
|---|---|---|
| `_prisma_migrations` 96 → 97 | **97** | ✓ |
| …and the new row is `20260811070000_b5_ledger_entries` | that exact name, from the deploy log | ✓ |
| `ledger_entries` comes into existence | present | ✓ |
| …and is **EMPTY** | **0 rows** | ✓ |
| exactly 4 triggers, all `tgenabled='O'` | **4** | ✓ |
| exactly 5 named CHECK constraints | **5** | ✓ |
| exactly 3 indexes | **3** | ✓ |
| FK is **ON DELETE SET NULL** | `FOREIGN KEY ("practiceId") REFERENCES practices(id) ON UPDATE CASCADE ON DELETE SET NULL` | ✓ |
| app image id moves | `d29b852d8d9b` → `5483ff331dd7` | ✓ |
| worker image id moves | `c18d9dbf1092` → `7aabd4cc69c6` | ✓ |

**What must NOT change** — the half a migration supplies an excuse for

| declared | measured | |
|---|---|---|
| `transcribe_visits` 25 | 25 | ✓ |
| … `signedAt IS NOT NULL` 17 | 17 | ✓ |
| … `deletedAt IS NOT NULL` 0 | 0 | ✓ |
| `transcribe_md_patients` 16 | 16 | ✓ |
| **`api_usage_events` 1325** | **1325** | ✓ |
| **`ai_calls` 1126** | **1126** | ✓ |
| `users` 196 | 196 | ✓ |
| `practices` 197 | 197 | ✓ |
| `note_templates` 6 | 6 | ✓ |
| `price_rates` 44 | 44 | ✓ |
| `audit_logs` ≥ 10704 | 10704 | ✓ |
| `marketing` image UNCHANGED | `e9568d07d057` | ✓ |
| `gotenberg` image UNCHANGED | `2d05d22572ba` | ✓ |
| co-tenants `307/404/200/200/410` | identical | ✓ |
| `MOCK_AI_CALLS=false` — app | false | ✓ |
| `MOCK_AI_CALLS=false` — worker | false | ✓ |
| composite FK still correctly shaped | references BOTH columns on both sides | ✓ |
| no OTHER table gains a trigger | **0** non-internal triggers on any table but `ledger_entries` | ✓ |

`app /api/health` **200**. Both containers `Up … (healthy)`.

⚠️ **THE CLINICAL COUNTS WERE ALSO TAKEN BETWEEN THE MIGRATION AND THE
RECREATE**, not only at the end — 25 · 17 · 16 · 1325 · 1126 · 196 · 197,
already byte-identical. So "the migration moved nothing" is measured
**separately** from "the deploy moved nothing", and a movement caused by either
one could not have hidden behind the other.

### ⚠️ ONE DEVIATION FROM MY OWN DECLARATION, AND IT IS A PROCESS MISS, NOT A STATE MISS

The declaration says **"Tag before recreating"**. I did not. `deploy-prod.sh`
does **not** cut rollback tags — that is a manual step the session performs —
and I read the previous session's tag table as evidence that it was automatic.
It is not.

**The tag was cut ~4 minutes AFTER the recreate**, and it is correct: both
pre-deploy images were still present as **dangling** images
(`d29b852d8d9b` 01:49:26, `c18d9dbf1092` 01:48:13), so
`:pre-b5-20260811` points at exactly the ids the declaration's baseline recorded
as running. Verified by id match against the baseline, not by assumption.

⚠️ **BUT IT SURVIVED ON LUCK, AND THE LUCK IS NAMEABLE.** A dangling image is
precisely what `docker image prune` deletes. For those four minutes the rollback
path for this deploy did not exist, and any prune — including the one preflight
Check 2 is designed to run automatically when the cache is large — would have
destroyed it silently. The recovery would then have been
`:pre-selfhostfonts-20260811`, one generation further back, which reverts the
**fonts** work as well: a rollback strictly larger than the change it undoes.

**The rule, so it is not re-derived:** *the rollback tag is cut against the
RUNNING container ids BEFORE `deploy-prod.sh` is invoked, because the script
does not do it and the images it would name become collectable the moment the
new build takes `:latest`.*

### WHAT IS LIVE, AND WHAT IS NOT

**Live:** an empty, append-only, self-deriving `ledger_entries` with 4 triggers
and 5 CHECKs, on production.

**NOT live — and this is the whole point of B5 shipping this way:** any billing
behaviour. Nothing reads or writes the table. `charge = cost × 3 / 2` and the
prod-only writer are **B6**; top-ups **B7**; the fail-closed balance block
**B8**. The deploy's own prediction — *"beyond the image ids and the new empty
table, nothing about the running system's behaviour should differ at all"* —
held on every one of the 18 must-not-change assertions.

---

## ✅ B6 IS BUILT — THE CHARGE IS INTEGER ARITHMETIC, AND THE WRITER REFUSES OFF PRODUCTION — 2026-08-11

**RELAY B6's gate, verbatim:** *"the writer **refuses on the live QA stack**,
demonstrated, not asserted (F4). `STRIPE_SECRET_KEY` is added to
`scripts/check-qa-mock-posture.sh` `KEYS` in the same commit, and the QA compose
entry does **not** use `${STRIPE_SECRET_KEY:-…}`. Rounding rule stated and tested
at the boundary."*

All four met. The design decisions are **ruling 90 (PROVISIONAL)**; this row is
the evidence.

### WHAT LANDED

| | |
|---|---|
| `packages/ai/src/price-table.ts` | `chargeMicroUsd(cost) = divRoundHalfUp(cost × 3n, 2n)`, beside B3's exact arithmetic |
| `packages/ai/src/billing-charge.ts` | the pure decision core + the prod-only committer — **the first writer of `ledger_entries`** |
| `packages/db/src/db-guard.ts` | `checkProdDb` / `assertProdDatabase` — the fail-closed mirror, **not** a negation |
| `20260811103000_b6_ledger_pricing_snapshot` | `pricing` jsonb + `ledger_entries_usage_has_pricing` |
| `scripts/check-qa-mock-posture.sh` | `STRIPE_SECRET_KEY` joins `KEYS`, ahead of its caller |
| `scripts/qa/b6-writer-refuses-on-qa.ts` | the F4 demonstration, against the live QA container's own `DATABASE_URL` |
| `gate-b6-charge-prod-only.test.ts` | 27 assertions in 7 arms |
| B5's `WRITERS` list | `[]` → one entry, **by hand, as B5 asked** |

### THE GATE'S FOUR CLAUSES, EACH WITH ITS EVIDENCE

**1. "Refuses on the live QA stack, demonstrated, not asserted."**

    live QA target, read from the container: host=postgres database=meddoc_qa_test
       ✔ positive control: the guard ACCEPTS database=meddoc
       ✔ the writer REFUSED, and the guard is what refused:
         [db-guard] FAIL-CLOSED: database "meddoc_qa_test" carries a
         qa/test/e2e/ci marker — this is not production
    🟢 F4 met — the billing writer refuses on the live QA stack.

The URL is read from the **running container**, never from a literal — the whole
failure class here is a config that reads safe and is not, so the only evidence
worth having comes from the live process environment. And a refusal is evidence
only when you know WHAT refused: the script matches the guard's own message
rather than the fact of an exception, and runs the accept-production control
first, because a missing import would also "refuse".

**2. `STRIPE_SECRET_KEY` in `KEYS`** — done, and it reports **unset** on both QA
containers, which is stronger than a dummy: nothing to leak because nothing is
there.

**3. No `${STRIPE_SECRET_KEY:-…}` in any compose file** — measured: **zero**
matches for `stripe` across every `*.yml` in the tree. The gate asserts the
absence so B7 has to argue with it.

**4. Rounding at the boundary** — every ODD cost is a boundary case, because
`cost × 3 / 2` lands exactly on `.5` for all of them and nowhere else.
`0→0, 1→2, 2→3, 3→5, 4→6, 5→8`.

### ⚠️ THE ASSERTION THAT DISTINGUISHES `× 3 / 2` FROM `* 1.5`, AND WHY THE OBVIOUS TEST DOES NOT

Below 2^53 the two implementations agree on **every** input. A boundary test
using small numbers passes against the float form and proves nothing about SPEC
§4.4's rule — which names `* 1.5` as the thing it exists to forbid. So the gate
asserts at `2^53 + 1` micro-dollars, where `Math.round(Number(cost) * 1.5)`
loses the low bit and returns a different number. **Mutation-proved: swapping in
the float form reds this arm and only this arm.**

### THE MUTATION MATRIX — SAID FIRST, THEN MADE TO FAIL

Each names its victim arm before running, asserts the occurrence count **before**
writing (a `.replace()` on a non-match is a silent no-op that reports success),
and restores from git — safe because the tree was committed clean first, which
the driver asserts rather than assumes.

| # | mutation | victim arm | |
|---|---|---|---|
| M1 | `checkProdDb` becomes `!checkNonProdDb().ok` | 5.1 "not the negation" | **RED** |
| M2 | charge per component, then sum | 2 "one rounding step" | **RED** |
| M3 | `BigInt(Math.round(Number(c) * 1.5))` | 1 "above the float-safe range" | **RED** |
| M4 | charge the priced part, skip the unpriced | 3.2 "refuses the WHOLE visit" | **RED** |
| M5 | `resend` added to `BILLABLE_PROVIDERS` | 4 "GATE 0.5" | **RED** |
| M6 | `assertProdDatabase()` moved below the pricing | 5.5 "FIRST statement" | **RED** |

`tree after restore: CLEAN`.

**M7 — the database arm, on QA, every write inside `BEGIN … ROLLBACK`.** The
positive control ran FIRST: a `usage` row **with** pricing was accepted and the
trigger derived `balanceAfter=-1500, seq=1`. The same row with NULL pricing was
refused, naming the constraint:

    ERROR: new row for relation "ledger_entries" violates check constraint
           "ledger_entries_usage_has_pricing"

And the CHECK is **conditional, not a blanket NOT NULL** — proved in its own
transaction, because the first had aborted: `topup` and `grant` with NULL
`pricing` both accepted, each bucket running its own sequence from 1.
`rows_after_rollback = 0` on both.

### 🟠 FOUND ON THE WAY PAST — TWO FILES THAT WERE NEVER TYPE-CHECKED, AND WHAT THAT WAS HIDING

**This was found by positive-controlling a green, and it is the session's most
useful finding.** `tsc --noEmit` returned clean on the new writer, including a
Prisma `create` — the exact site AGENTS.md warns is invisible when the client is
`any`. The client is **not** `any` here (F-TYPE fixed that), so the green looked
decisive. It was not:

> **A deliberately bogus Prisma field added to `commitVisitCharge`'s
> `create({ data })` produced ZERO errors.**

`tsc` walks the import graph from the app's entry points. **Nothing in either app
imported `billing-charge.ts` or `price-table.ts`, so neither was in the
programme at all** — confirmed by `tsc --listFiles`, which named neither. B3's
price table has been in that position since it shipped.

That is the emptiness failure wearing a new costume. AGENTS.md's rule reads
*"type-check is decisive only for TYPED sites"*; here the site was fully typed
and merely **unreachable**, and a green typecheck over a programme that does not
contain your file is indistinguishable from a green typecheck over one that
does.

**Exporting both from `packages/ai/src/index.ts` put them in the programme, and
the same bogus field then errored by name** (`TS2353 … 'bogusFieldThatCannotExist'
does not exist in type LedgerEntryCreateInput`). The coverage fix immediately
surfaced two real defects that had been hidden behind it:

1. ⚠️ **B3's `price-table.ts` has NEVER COMPILED under this repo's tsconfig.**
   `target: ES2017` rejects BigInt literals with `TS2737` regardless of `lib`,
   which already lists `esnext` — so the BigInt *type* resolved and the *syntax*
   did not. The file is written entirely in BigInt literals, because GATE 0.4
   requires that no float touch a price. **Raised to ES2020** — safe under
   `noEmit`, where `target` only decides which syntax the checker accepts and
   `lib` is set explicitly so it does not shift. **Not higher, deliberately:**
   ES2022 switches on `useDefineForClassFields`, a runtime behaviour change
   nobody asked for. `marketing` type-checks clean on the new target too.
2. **The Prisma client was stale** and did not know `ledger_entries.pricing`.
   Regenerated.

### ⚠️ AND A SEAM DEFECT IN B5, NAMED RATHER THAN PATCHED FROM INSIDE B6

`LedgerEntry.practiceIdSnapshot` is derived by the trigger
(`NEW."practiceIdSnapshot" := NEW."practiceId"`, unconditional), exactly like
`balanceAfter` and `seq` — **but Prisma's generated type REQUIRES it**, because
it has no `@default`. B5 gave the other two an `@default(0)` for precisely this
reason, in its own words: *"so a Prisma caller need not send a value it is not
allowed to choose."* The third derived column did not get the same treatment, so
every Prisma caller must supply a value the database discards.

B6 sends `practiceIdSnapshot: args.practiceId` — the same variable it sends as
`practiceId`, in the same object, so the pair cannot drift. **It is recorded
here rather than fixed** because changing a B5 column's default is B5's design,
not B6's, and the current state is safe with one source.

⚠️ Note the caller value is **silently replaced, not rejected**: the trigger
overwrites before `ledger_entries_snapshot_agrees` is evaluated, so that CHECK
can never see a disagreeing caller value. Anyone reading the CHECK as protection
against a wrong caller is reading it wrong.

### ⚠️ ONE BUILD FAILURE I COULD NOT ATTRIBUTE, REPORTED RATHER THAN EXPLAINED

The first `docker compose -f docker-compose.qa.yml build db-migrate` failed at
`npm run build -w transcribe-md` / `next build`. The second succeeded and the
third hit cache. **I did not capture the underlying error** — only the npm
wrapper lines — so I cannot say whether it was the `ECONNRESET` /
`next/font/google` family AGENTS.md records or something else. It is named here
because *"it worked the second time"* is not a diagnosis, and because a future
occurrence should find this row rather than start from zero. `tsc` is clean and
3428 unit tests pass; CI's own build on the PR is the authoritative signal.

### WHAT B6 DOES **NOT** CLAIM

- **Nothing is charged, anywhere.** The writer has no call site — ruling 90(e).
  `ledger_entries` still holds **0 rows** in production and on QA.
- **The writer has never been observed WRITING**, and cannot be by any test we
  are allowed to run: F4 requires it to refuse everywhere except production.
  That is why the arithmetic lives in a separate pure function that IS fully
  exercised. Ruling 86(a)'s antidote, applied before the fact.
- **The demonstration script's 🔴 branch is unexercised, deliberately** — see
  ruling 90's closing note. Exercising it would write an undeletable row into
  QA's ledger.
- **The `nova-3-medical` rate is still PARKED**, so production's audio remains
  unpriceable. B6 does not change that and must not be read as pricing it.
- **Ruling 80(d)'s PAYG assumption is untouched** — if the Deepgram tier is
  wrong, the over-statement it causes is now multiplied by 3/2 wherever a
  Deepgram rate does apply.

### ⚠️ M8 — I FOUND THIS GATE'S OWN WATCHED SET WAS ONE FILE SHORT, BEFORE MERGING IT

The clause reads *"the QA compose entry does not use `${STRIPE_SECRET_KEY:-…}`"*.
I wrote the arm as a hand-kept list of two — `docker-compose.yml` and
`docker-compose.qa.yml`. **There are three.**
`docker-compose.qa.b4-coverage.yml` is a QA overlay ruling 86(d) added four days
ago, and a `${STRIPE_SECRET_KEY:-…}` placed in it would have sailed past the
gate that exists to forbid exactly that.

Found by positive-controlling an unrelated zero: the claim *"zero matches for
`stripe` across every compose file"* was checked with the same matcher against a
token known to be present (`MOCK_AI_CALLS` → 4 files), and the control's output
listed a **third** compose file the arm was not reading.

**The arm now enumerates by glob** — `/^docker-compose.*\.ya?ml$/` over the repo
root, with a count assertion so a broken glob cannot report a clean zero over
nothing, and a matcher control so the regex cannot be vacuous.

| # | mutation | victim arm | |
|---|---|---|---|
| M8 | `${STRIPE_SECRET_KEY:-sk_test_qa}` appended to **`docker-compose.qa.b4-coverage.yml`** | 7 "no compose file introduces a default" | **RED**, naming the file |

⚠️ **THE POINT IS NOT THAT M8 IS RED. It is that M8 would have been GREEN on the
version I nearly shipped**, and nothing would ever have said so — this is
AGENTS.md's watched-set rule arriving inside the gate written to satisfy a
clause that names the universe explicitly. A hand-kept list was already stale
four days after the third file appeared, by an author who had read all three
that morning.

### ⚠️ AND THE PUSH CARRYING M8 CANCELLED THIS PR's `e2e`, DELIBERATELY

`e2e` `31482462518` was ~39 minutes in when the fix was pushed; `CI`, `a11y-ci`
and `secrets-scan` had already passed. **Declared, not accidental.**

The alternative was to let it finish and merge a gate I had already proved
incomplete, then file a follow-up — which trades ~40 minutes of wall clock for
merging a known hole in the exact clause B6's gate names. It is the wrong trade:
the required checks would have to be re-run on the new head before merging
anyway, so the follow-up costs the same cycle **plus** a window in which `main`
carries the weaker gate.

**The avoidable part is upstream of the choice**, and it is #568's lesson again:
the first push happened before the close-out enumeration was done, so a finding
that arrives during verification necessarily lands mid-run. *Hold the first push
until the session's remaining work is written* is the habit; I did not.

---

## 🟩 B6 IS LIVE IN PRODUCTION — `f1c6dfde`, 2026-08-11T12:39Z

| | |
|---|---|
| deployed commit | `f1c6dfdeff2ade97e98b62850a3dac240f628dc9` |
| declaration | `docs/foundation/deploys/20260811-f1c6dfde.md` — **written 11:58Z, 41 minutes BEFORE the deploy ran** |
| deploy log | `docs/deploy-logs/deploy-20260811T123844Z.log` |
| rollback tag | **`:pre-b6-20260811`** — app `5483ff331dd7` / worker `7aabd4cc69c6`, **cut BEFORE `deploy-prod.sh` ran**, verified by id match |
| app image | `5483ff331dd7` → **`c6c9ec2edce7`** |
| worker image | `7aabd4cc69c6` → **`0c5a78e163e4`** |
| migration | `20260811103000_b6_ledger_pricing_snapshot`; **97 → 98**, asserted by the deploy itself |

### Citation — produced by `check-citation.sh`, not typed

**Citation — 4 of 4 on `f1c6dfdeff2ade97e98b62850a3dac240f628dc9`:**
   · `CI` 31488664560 a1
   · `e2e` 31488664518 a1
   · `a11y-ci` 31488664506 a1
   · `secrets-scan` 31488664520 a1

All `a1` — no re-runs, nothing to explain.

### THE DECLARATION, JUDGED — 21 of 21, EVERY ONE AS DECLARED

**What must change**

| # | declared | measured | |
|---|---|---|---|
| 1 | `_prisma_migrations` 97 → 98 | **98** | ✓ |
| 2 | the new row is `20260811103000_b6_ledger_pricing_snapshot` | that exact name | ✓ |
| 3 | `ledger_entries.pricing` exists, `jsonb`, nullable | `pricing / jsonb / YES` | ✓ |
| 4 | `ledger_entries_usage_has_pricing` exists | present | ✓ |
| 5 | CHECKs on `ledger_entries` 5 → 6 | **6** | ✓ |
| 6 | app image id moves | `5483ff331dd7` → `c6c9ec2edce7` | ✓ |
| 7 | worker image id moves | `7aabd4cc69c6` → `0c5a78e163e4` | ✓ |

**What must NOT change**

| # | declared | measured | |
|---|---|---|---|
| 8 | **`ledger_entries` 0 rows** | **0** | ✓ |
| 9 | `transcribe_visits` 25 | 25 | ✓ |
| 10 | … `signedAt IS NOT NULL` 17 | 17 | ✓ |
| 11 | `transcribe_md_patients` 16 | 16 | ✓ |
| 12 | `api_usage_events` 1325 | 1325 | ✓ |
| 13 | `ai_calls` 1126 | 1126 | ✓ |
| 14 | `users` 196 | 196 | ✓ |
| 15 | `practices` 197 | 197 | ✓ |
| 16 | `price_rates` 44 | 44 | ✓ |
| 17 | 4 triggers, all `tgenabled='O'` | 4 / 4 enabled | ✓ |
| 18 | 3 indexes | 3 | ✓ |
| 19 | composite FK present | `check-composite-fk` 🟢 | ✓ |
| 20 | 9 of 9 containers healthy | 9 of 9 | ✓ |
| 21 | co-tenants `307/404/200/200/410` | exactly that | ✓ |

**Assertion 8 was the one that mattered** — B6 introduces the first writer this
table has ever had, and a row appearing would be a defect that had *already
become permanent*, the table being append-only. It stayed 0, which is what
ruling 90(e) predicted and what keeps ruling 90(d)'s retrofit window open.

### ⚠️ THE ROLLBACK TAG WAS CUT FIRST THIS TIME, AND THAT IS A CORRECTION

Session 01 recorded cutting B5's tag **late**, noting it survived on luck: a
dangling image is exactly what `docker image prune` removes and preflight runs
one automatically, so that deploy had no rollback path for four minutes.
`deploy-prod.sh` still does not cut tags. So the declaration named the two
`docker tag` commands explicitly, and they ran **before** the deploy — verified
by id match against the running containers, not by the tag existing.

### WHAT IS LIVE, AND WHAT IS NOT

**Live:** a `pricing` column and a conditional CHECK on an empty
`ledger_entries`, and `packages/ai`'s charge rule and prod-only writer, compiled
into the image.

**NOT live:** any billing behaviour whatsoever. **Nothing calls the writer** —
ruling 90(e) — so `ledger_entries` still holds **0 rows** and the deploy's own
prediction (*"beyond the image ids, one migration row, one column and one CHECK,
nothing about the running system's behaviour should differ at all"*) held on all
14 must-not-change assertions. Top-ups are **B7**; the fail-closed balance block
and **the writer's call site** are **B8**.

---

## ✅ THE CITATION OWED FOR `7b88cf06` — PRODUCED BY THE CHECKER

Session 01 closed with *"`7b88cf06`'s citation (PR #600) — owed to the next
session, per the established lag."* Verified as STEP 0.4 of session 02 and
recorded here rather than deferred again.

**Citation — 4 of 4 on `7b88cf06e69a5de4451ce130540a24a2417c47b4`:**
   · `CI` 31479674193 a1
   · `e2e` 31479674185 a1
   · `a11y-ci` 31479674191 a1
   · `secrets-scan` 31479674174 a1

⚠️ **It was `2`/still-running for the first ~2h20m of this session** — `e2e`
completed at 11:52Z having started at 09:52Z. That is a WAIT, not a finding, and
the checker withheld the block correctly throughout. **The lag exists because a
docs PR's own merge-commit `e2e` outlives the session that opened it**, which is
structural and not anybody's oversight.

### ⚠️ CORRECTION TO THE M8 ROW ABOVE — THE CANCELLED RUN WAS 41m12s, NOT "~39 MINUTES"

The M8 section states the cancelled `e2e` was *"~39 minutes in"*. That figure was
an estimate written before the run finished dying. **Measured afterwards:
`31482462518` started `10:29:54Z` and ended `11:11:06Z` — 41m12s**, against a
median `e2e` of ~41m. So it was cancelled within roughly a minute of completing,
not two minutes short of it.

The decision stands — the required checks had to re-run on the new head before
merging regardless — but **the price was at the expensive end of the class, not
the cheap end**, and AGENTS.md is explicit that the cost is set by how late the
second push lands. Recorded because a number I estimated and did not re-measure
is exactly the shape the FOUNDATION canon calls a fabricated figure, and the
correction is cheaper than the precedent.

---

## ✅ B7 STEP 1 IS BUILT — THE WEBHOOK, AND AN INBOUND EVENT'S MODE IS HALF THE GUARD — 2026-08-11

**Session 03 of run `20260811-065857-b1`.** B7's gate has four clauses and this
step lands all four, plus the fail-closed arm that makes the route safe to ship
ahead of any Stripe account. **Nothing is billed, nothing is charged, and no
Stripe account, secret key or webhook secret exists in any environment.**

### WHAT SHIPPED

| | |
|---|---|
| the decision, PURE | `apps/transcribe-md/src/lib/billing/stripe-topup.ts` |
| the effect | `apps/transcribe-md/src/app/api/stripe/webhook/route.ts` |
| the enum's third layer | `20260811160000_b7_checkout_audit_actions` — three `ALTER TYPE … ADD VALUE` |
| the gate | `gate-b7-webhook-topup.test.ts` — 26 arms |
| a NEW standing gate | `gate-audit-enum-migration.test.ts` — the layer that has silently failed three times |
| QA posture | `STRIPE_WEBHOOK_SECRET` joins `check-qa-mock-posture.sh`'s `KEYS` |
| QA compose | both Stripe secrets as **literal** dummies, in both services |

The split is B6's, for B6's reason: a writer that refuses in some environments
"can never be watched WRITING by any test we are allowed to run", so the
DECISION is separated from the EFFECT and proven exhaustively from object
literals, anywhere.

### THE ONE THAT MATTERS — `assertProdDatabase()` WOULD HAVE BEEN FAIL-OPEN HERE

SPEC §2.4 says *"prod-only billing writer — the writer asserts it is in
production and refuses otherwise"*, and B6's `commitVisitCharge` does exactly
that. **Applied to an INBOUND event that carries its own `livemode` flag, that
clause guards half the question:**

> A **TEST-mode** `checkout.session.completed` delivered to `app.quillmd.com`
> satisfies `assertProdDatabase()` completely — and credits a real practice's
> real wallet with money **nobody paid**, on a table that cannot delete it.

That is reachable *today*: Stripe is TEST MODE ONLY on this programme, so a
test-mode event is the only kind that can currently exist. So the rule is a
two-sided match, ruling 90(c)'s shape pointed at an inbound fact:

| database | event | |
|---|---|---|
| production | `livemode: true` | credit |
| non-production | `livemode: false` | credit |
| `staging`, unset, unparseable | either | **refuse — `undeterminable_environment`** |
| production | `livemode: false` | **refuse — nobody paid for it** |
| non-production | `livemode: true` | **refuse — the record would be lost** |

Ruling 91(a), **PROVISIONAL**, recorded with the divergence stated rather than
buried. The reversal is to AND `assertProdDatabase()` on top, which only ever
makes it stricter.

### THE GATE, MUTATION-PROVED — 8 OF 8, EACH BY A NAMED TEST

Backups to scratch **before** the first mutation and restored from those copies,
never `git checkout --` (the 2026-08-08 lesson: on a dirty tree that reverts to
HEAD and destroys the session's uncommitted work). Every mutation asserted its
own occurrence count before its result was believed. Baseline green first, and
green again afterwards with all four files verified byte-identical.

| | mutation | caught by |
|---|---|---|
| M1 | `req.text()` → `JSON.stringify(await req.json())` | the `req.text()` arm |
| M2 | a `logAudit` call moved ABOVE `constructEvent` | *nothing touches the database before the signature has verified* |
| M3 | `practiceId:` removed from one `logAudit` call | *userId and practiceId are passed to every logAudit call* |
| M4 | `checkProdDb(…).ok` → `!checkNonProdDb(…).ok` | *an UNIDENTIFIABLE database refuses in BOTH modes* |
| M5 | `visitId` added to the metadata allowlist | *ANY metadata key outside the allowlist* |
| M6 | the credit negated (`-decision.amountMicroUsd`) | *the ledger row is a POSITIVE topup* |
| M7 | an enum label added with no migration | *EVERY label in schema.prisma is created by some migration* |
| M8 | B7's OWN migration statement deleted | the same arm, **plus** *B7's own three labels are creatable* |

⚠️ **M4 FIRST REPORTED "GATE IS BLIND", AND THE GATE WAS FINE.** The harness
ran each mutation against a NAME-FILTERED test, and the filter named the
prod-plus-test-mode arm — which the negation genuinely does not change, because
`checkNonProdDb('meddoc')` is not-ok either way. The negation leaks on the
*unidentifiable* cases (`staging` negates to "this is production, write"), and
that arm caught it immediately once the filter was dropped. **The harness had
the defect its own subject is designed against: a check whose title was narrower
than what it measured.** Every mutation now runs against the whole gate file and
the run prints which test caught it.

### TWO OTHER ITEMS' GATES WENT RED, AND BOTH WERE RIGHT

**B5's writer census.** `gate-b5-ledger-append-only.test.ts` asserts the set of
files that write `ledger_entries` equals a hand-declared list, so that "the
first writer arrives as a DELIBERATE edit rather than as a surprise". B7 is the
second writer and is declared, with the shape of its refusal written beside it —
including *why* it is not `assertProdDatabase()`.

**B6's compose sweep, and it is the substring trap for the fourth time.**
`gate-b6-charge-prod-only.test.ts` asserts no compose file contains
`${STRIPE_SECRET_KEY:-…}`. B7 added the variables as literal dummies **and a
comment warning against the interpolation form** — and the warning tripped the
guard against the thing it warns about. AGENTS.md's own summary of the class:
*"a file's comments are the one place where the words you are grepping for are
guaranteed to appear."* Fixed on the GUARD, not by rewording the warning: the
scan now strips `#` comment lines, which is strictly more correct (a `${VAR:-…}`
inside a comment interpolates nothing), and carries a new control proving the
stripper neither blanks the file nor lets an ACTIVE interpolation through. The
arm now covers `STRIPE_WEBHOOK_SECRET` too.

⚠️ **It bit twice more in the same hour, in my own shell**: a
`grep -c '\${STRIPE' docker-compose.qa.yml` returned 2 and both hits were that
same comment.

### THE NEW STANDING GATE — THE THIRD LAYER, CHECKED AT LAST

`gate-audit-action-parity.test.ts` compares the TS union against
`schema.prisma`. It is correct and it is not sufficient, because
**`schema.prisma` is not the database either** — a Prisma enum VALUE needs its
own `ALTER TYPE` migration. That gap is where the bug lived twice: on
2026-08-06 attempt 2 landed in BOTH source files and still not in Postgres,
passing `prisma validate`, `tsc` and **3192 unit tests**, while the app logged
`invalid input value for enum "AuditAction"` and swallowed it.

`gate-audit-enum-migration.test.ts` closes it as a SOURCE comparison, so it
fails in the unit suite instead of in an E2E that queries `audit_logs`. It
parses per-statement up to the semicolon and strips SQL comments, because both
statement forms occur here — including a MULTI-LINE `ALTER TYPE "AuditAction"`
in two migrations that a line-oriented matcher would miss while reporting clean.

⚠️ **AND ITS MULTI-LINE POSITIVE CONTROL WAS WRONG WHEN FIRST WRITTEN.** It
asserted `SPEAKER_ROLE_REASSIGNED`, which the SINGLE-line form also creates — so
the assertion named the multi-line arm and would have passed without exercising
it. Corrected to `AI_REFUSAL`, verified against the two files that actually use
that form. Same class as M4 above, twice in one session.

⚠️ **WHAT IT DOES NOT CLAIM:** that any migration has been APPLIED. That is
`assert-migrations-applied.sh`, and the two together are what the claim needs.

### PROVEN ON QA, AND WHAT IS DELIBERATELY NOT

`pg_enum` on `meddoc_qa_test` after applying the migration — **not**
`prisma validate`, which is the check that has passed through this defect twice:

```
CHECKOUT_TOPUP_CREDITED
CHECKOUT_TOPUP_DUPLICATE
CHECKOUT_TOPUP_REFUSED
```

QA is **99 of 99** migrations. Production is 98 of 98 and stays there until the
deploy — the normal pre-deploy asymmetry.

⚠️ **THE CREDITED PATH IS NOT PROVEN END TO END, AND THAT IS A CHOICE.**
Proving it means appending a `topup` row to QA's append-only `ledger_entries`,
which permanently ends the zero-row state rulings 89(e) and 90(d) deliberately
preserved — that emptiness is what lets a future column land without a
fail-open DEFAULT or a backfill UPDATE. The REFUSED path is proven end to end
instead (below), which exercises the security-critical half — the signature —
and the Postgres enum. **The credit is proven at unit level only.** An
unverified step named honestly is worth more than a green tick bought by
poisoning an invariant another ruling depends on.

### WHAT THIS STEP DOES **NOT** CLAIM

- **Nothing is billed.** `ledger_entries` holds **0 rows** in both environments.
- **No Stripe account exists**, and no `STRIPE_SECRET_KEY` or
  `STRIPE_WEBHOOK_SECRET` is set in production — so the route **503s on every
  request** as shipped. That is the fail-closed arm, and it is why this can ship
  ahead of the account.
- **There is no way to CREATE a Checkout Session yet** — that is B7 step 2,
  along with the settings-page door (`settings/page.tsx:895-905` still carries
  the disabled placeholder).
- **The `$10` promo grant is not built.** `bucket = 'promo'` exists in B5's
  schema and nothing writes it.
- **`pricing` stays NULL on a topup**, permitted by the CONDITIONAL
  `ledger_entries_usage_has_pricing` CHECK — ruling 90(d): a top-up is money
  arriving, not money computed.

### THE STRIPE SDK IS BACK IN THE CLINICAL WORKER — MEASURED, NOT WAVED AT

`Dockerfile.worker:62` copies the entire workspace-root `node_modules`, so a
dependency of the WEB app reaches the worker. DISCOVERY §E.2 measured this class
and the SECURITY BLOCK removed the two Stripe entries on 2026-08-04.

**No standing ruling forbids re-adding it — `RULINGS.md` grepped, absent** — and
§E.2's own words were that the nine CRM packages ship *"for no reason"*, which
stops being true once the SDK is load-bearing. Taken rather than hand-rolling
HMAC because `constructEvent` also does the replay-tolerance window and the
constant-time compare.

Lockfile delta **measured on both sides of the install**, not assumed:

| | before | after |
|---|---|---|
| lockfile packages | 1167 | **1168** (exactly one entry, `node_modules/stripe`) |
| `sharp`/`@img` subtree | 29 | **29** — the known `npm update` splice trap, positive-controlled |
| `npm audit` findings | 6 (4 moderate, 2 high) | **6, none through `stripe`** |

Closure is **A6**, which deletes `apps/meddoc-pro` and takes the other seven CRM
packages with it. Named so it is a checked outcome rather than a hoped-for one.

---

## 🟩 B7 STEP 1 IS LIVE IN PRODUCTION — `2a102890`, 2026-08-11T16:31Z

| | |
|---|---|
| deployed commit | `2a1028906b16077fc7495708646135114935589c` |
| declaration | `docs/foundation/deploys/20260811-2a102890.md` — **written 15:44Z, 45 minutes BEFORE the deploy ran** |
| deploy log | `docs/deploy-logs/deploy-20260811T162936Z.log` |
| rollback tag | **`:pre-b7-20260811`** — app `c6c9ec2edce7` / worker `0c5a78e163e4`, **cut BEFORE `deploy-prod.sh` ran**, verified by id match |
| app image | `c6c9ec2edce7` → **`c14397e8ae1a`** |
| worker image | `0c5a78e163e4` → **`aec2badfd693`** |
| migration | `20260811160000_b7_checkout_audit_actions`; **98 → 99**, asserted by the deploy itself |

### Citation — produced by `check-citation.sh`, not typed

**Citation — 4 of 4 on `2a1028906b16077fc7495708646135114935589c`:**
   · `CI` 31508472169 a1
   · `e2e` 31508472220 a1
   · `a11y-ci` 31508472226 a1
   · `secrets-scan` 31508472196 a1

All `a1` — no re-runs, nothing to explain. (The checker also listed five
dependabot `npm_and_yarn` runs as `extra`; they are not required workflows and
form no part of the citation.)

### THE DECLARATION, JUDGED — 22 of 22, EVERY ONE AS DECLARED

**What must change**

| # | declared | measured | |
|---|---|---|---|
| 1 | `_prisma_migrations` 98 → 99 | **99** | ✓ |
| 2 | the new row is `20260811160000_b7_checkout_audit_actions` | that exact name, newest | ✓ |
| 3 | `AuditAction` labels 138 → 141 | **141** | ✓ |
| 4 | the three labels in `pg_enum` | `CHECKOUT_TOPUP_CREDITED`, `…_DUPLICATE`, `…_REFUSED` | ✓ |
| 5 | app image id moves | `c6c9ec2edce7` → `c14397e8ae1a` | ✓ |
| 6 | worker image id moves | `0c5a78e163e4` → `aec2badfd693` | ✓ |
| 7 | **`POST /api/stripe/webhook` 404 → 503** | **503** | ✓ |

**What must NOT change**

| # | declared | measured | |
|---|---|---|---|
| 8 | **`ledger_entries` 0 rows** | **0** | ✓ |
| 9 | `transcribe_visits` 25 | 25 | ✓ |
| 10 | … `signedAt IS NOT NULL` 17 | 17 | ✓ |
| 11 | `transcribe_md_patients` 16 | 16 | ✓ |
| 12 | `api_usage_events` 1325 | 1325 | ✓ |
| 13 | `ai_calls` 1126 | 1126 | ✓ |
| 14 | `users` 196 | 196 | ✓ |
| 15 | `practices` 197 | 197 | ✓ |
| 16 | `price_rates` 44 | 44 | ✓ |
| 17 | **`audit_logs` rows with a `CHECKOUT_%` action 0** | **0** | ✓ |
| 18 | 4 triggers on `ledger_entries`, all `tgenabled='O'` | 4 / 4 enabled | ✓ |
| 19 | 6 CHECK constraints on `ledger_entries` | 6 | ✓ |
| 20 | composite FK present | `check-composite-fk` 🟢 | ✓ |
| 21 | 9 of 9 containers healthy | 9 of 9 | ✓ |
| 22 | co-tenants `307/404/200/200/410` | exactly that | ✓ |

### ⚠️ ASSERTION 7 IS THE ONE WORTH READING TWICE — **503 IS THE PASS**

`POST https://app.quillmd.com/api/stripe/webhook` returned **404 before the
deploy and 503 after it**. That single number is the whole safety argument for
shipping an unauthenticated, internet-reachable payment endpoint ahead of any
Stripe account:

- **503 means the route exists and refused before reading the body.** The first
  statement checks `STRIPE_WEBHOOK_SECRET`, and it is unset in production.
- **A 200 or a 400 would have been the finding** — either would mean a webhook
  secret is configured in production, which nothing in this programme has
  authorised.

DISCOVERY §E.1 measured no `STRIPE` entry in any of the twelve `.env*` files on
disk. This assertion is what turned that measurement into a statement about the
**running container**, which is where the two have diverged before.

⚠️ Probed with **no `stripe-signature` header and an empty body** — a request
that can have no effect whatever the secret is, and one any internet caller can
already make.

### WHAT IS LIVE, AND WHAT IS NOT

**Live:** three permanent `AuditAction` labels, and a route that refuses
everything.

**NOT live:** any billing behaviour whatsoever. `ledger_entries` still holds
**0 rows**; no Stripe account, secret key or webhook secret exists in any
environment; there is no way to CREATE a Checkout Session (B7 step 2); and the
`$10` promo grant is unwritten. The deploy's own prediction — *"three new labels
on a Postgres enum, plus an HTTP route that returns 503 to every request"* — held
on all 15 must-not-change assertions.

### ⚠️ THE MIGRATION CANNOT BE ROLLED BACK, AND THAT WAS DECLARED IN ADVANCE

Postgres has no `ALTER TYPE … DROP VALUE`. The three labels are permanent from
the moment this deploy applied. Rolling the IMAGE back (`:pre-b7-20260811`)
removes the route and leaves three unused enum labels behind, which cost
nothing. Named in the declaration's Rollback section before the deploy rather
than discovered during one.

---

## 📌 THE CITATION SESSION 03 OWED FORWARD — `433afe2c`, PR #605

Session 03 took a full citation on its own docs merge and recorded it in its log
rather than here, naming this as the next session's STEP 0 line. Re-verified
with the checker before being written down — **not copied from the log** — using
`--expect`, which is the only direction that can see a substitution:

```
bash scripts/check-citation.sh 433afe2cca0618da6f2aa41e72b36de09ec85163 \
  --expect 31516996435,31516996523,31516996431,31516996529
```

**Citation — 4 of 4 on `433afe2cca0618da6f2aa41e72b36de09ec85163`:**
   · `CI` 31516996435 a1
   · `e2e` 31516996523 a1
   · `a11y-ci` 31516996431 a1
   · `secrets-scan` 31516996529 a1

🟢 CITATION COMPLETE. All `a1` — no re-runs, nothing to explain.

---

## ✅ B7 STEP 2 IS BUILT — THE DOOR, AND THE PAYING PARTY IS NEVER THE BODY'S — 2026-08-11

**Session 04 of run `20260811-065857-b1`.** Step 1 built the INBOUND half: the
webhook that credits a wallet when Stripe says a session was paid. This is the
OUTBOUND half — the only thing in the system that may ask Stripe to take money —
plus the settings-page door step 1 recorded as missing by line number.

| what | where |
|---|---|
| the pure decision | `apps/transcribe-md/src/lib/billing/stripe-checkout.ts` |
| the route | `apps/transcribe-md/src/app/api/stripe/checkout/route.ts` |
| the door | `apps/transcribe-md/src/app/settings/billing-topup-panel.tsx` + `settings/page.tsx` |
| the gate | `src/lib/billing/__tests__/gate-b7-checkout-session.test.ts` |
| the migration | `20260811190000_b7_checkout_session_audit_actions` — 2 labels |

### THE ONE THAT MATTERS — WHAT MAKES STEP 1's ALLOWLIST MEAN ANYTHING

Step 1's metadata allowlist is enforced on the INBOUND event, and its own header
says what that can and cannot catch: *"what this actually catches is OUR OWN
session-creation code (B7 step 2) putting something forbidden there — a
regression, not an attacker."*

**This is that code.** Stripe echoes back whatever metadata a session was created
with, so if this half read `practiceId` out of a request body, the inbound
allowlist would be validating a value an anonymous caller chose — and DISCOVERY
§E.5's concern (a visit id dereferences to a named patient in ONE hop) would
arrive through the front door with a valid Stripe signature on it.

So the route accepts **one** value from the body — `amountCents` — and nothing
else. `practiceId` and `userId` are read off the authenticated session. The
metadata is CONSTRUCTED from those two and its keys checked against step 1's
`ALLOWED_METADATA_KEYS`, **imported rather than restated**: two literals would
both stay green while drifting apart.

⚠️ **AND THE CONTRACT BETWEEN THE TWO HALVES IS ASSERTED BY FEEDING ONE INTO THE
OTHER.** The halves are separated by Stripe — this code writes metadata, Stripe
stores it, step 1's code reads it back days later — so there is no type between
them and no test that runs both. The gate builds the event Stripe *would*
deliver for the session this decision describes and requires `decideTopup` to
credit it, with a positive control (one extra key) proving the round trip can
fail. A drift between the two halves would otherwise be discovered by a doctor
who had already paid.

### THE MODE RULE, OUTBOUND — RULING 91(a) POINTED THE OTHER WAY

Ruling 91(a) settled the inbound rule: an event's `livemode` must match the
database, both confirmed positively, anything unidentifiable refusing BOTH ways.
The outbound question has the same two facts, so it takes the same shape — the
mode here being carried by the SECRET KEY:

|  | LIVE key | TEST key | unclassifiable | absent |
|---|---|---|---|---|
| **production db** | create | refuse | refuse | refuse |
| **non-prod db** | **refuse** | create | refuse | refuse |
| **`staging` / unset** | refuse | refuse | refuse | refuse |

⚠️ **THE DANGEROUS DIRECTION IS NOT THE SAME ONE AS THE WEBHOOK'S.** Inbound, the
reachable-today hazard was `prod + test event` — a credit nobody paid for.
Outbound it is **`non-prod + LIVE key`: a QA or staging box that can charge a
real card**, which is a FOUNDATION hard-halt item by name. That is why a key
whose prefix classifies as neither is refused rather than tried.

⚠️ **AND THE UNRECOGNISED ARM IS WHAT MAKES THIS WALKABLE ON QA.** The QA compose
declares the literal `STRIPE_SECRET_KEY: "qa-dummy-stripe-secret-never-valid"`.
It matches neither `sk_test_` nor `sk_live_`, so it classifies `unrecognised` and
is refused **before any SDK call** — the door renders, the route runs, the
refusal is named, the audit row lands, and no network, Stripe account or test key
is involved anywhere. B7's gate asks for exactly that ("tests use
`generateTestHeaderString` with no network and no Stripe account"), and the QA
dummy is asserted **by its literal value** in the gate so nobody helpfully
replaces it with a real-looking `sk_test_` string.

### THE AMOUNT IS AN ALLOWLIST, AND IT IS DELIBERATELY NOT A PRICING DECISION

`TOPUP_DENOMINATIONS_CENTS = [2500, 5000, 10000, 25000]` — $25 / $50 / $100 /
$250. The caller sends one of these or is refused by name; there is no path by
which an arbitrary integer becomes a charge.

⚠️ **PRICING IS A HARD HALT ON THIS PROGRAMME, SO THE SHAPE OF THIS LIST IS THE
POINT.** Every denomination buys credit at **FACE VALUE** — $50 buys 50 000 000
micro-dollars, one to one, via step 1's `centsToMicroUsd`. **No discount, no
bonus, no volume tier**, because each of those *would* be a pricing claim and
none is authorised. The price of the service is settled elsewhere and unchanged:
GATE 0.4's `cost × 3 / 2`, applied when usage is metered (B6), not when money is
added. The gate asserts the face-value property directly (`cents % 100 === 0`,
plus the exact array) so a bonus cannot be added quietly.

A BOUND (`min <= cents <= max`) was the alternative and is worse for the same
reason a denylist was worse in step 1: it admits every value in between, so the
set of charges that can reach Stripe is defined by arithmetic rather than by a
diff somebody reviewed.

### THE DOOR RENDERS ON **PRESENCE** OF A KEY, NOT ON VALIDITY

`settings/page.tsx` reads `process.env.STRIPE_SECRET_KEY` on the SERVER and
renders the panel when it is non-empty — including a key whose mode cannot be
classified.

Gating on VALIDITY would be tidier and would make the path unreachable in every
environment we are allowed to test: **production has no key at all** (so nothing
renders and today's UI is byte-identical), and QA has the deliberate dummy. So
presence is what makes the whole door → route → refusal → audit-row path
walkable. The only environment that can display a button whose key is unusable is
the one built to be walked.

⚠️ **AND PRODUCTION'S BILLING SECTION IS UNCHANGED.** With no key, the old
disabled *"Manage billing"* placeholder and its pilot copy still render, byte for
byte. The gate asserts that branch explicitly, because the deploy declaration's
*"nothing but the image ids"* depends on it.

### THE GATE, AND WHAT WAS MADE TO FAIL

**10 of 10 mutations caught, each by a NAMED test.** The harness runs the WHOLE
gate per mutation and prints which test caught it — session 03 recorded why: its
own harness reported "GATE IS BLIND" for a healthy gate because each mutation ran
against a name-filtered subset naming an arm the mutation does not change.

| | mutation | caught by |
|---|---|---|
| M1 | an unclassifiable key silently treated as TEST | the QA-dummy literal case |
| M2 | the mode rule uses `!checkNonProdDb` instead of `checkProdDb` | the UNIDENTIFIABLE-database case |
| M3 | the amount allowlist becomes a BOUND | the between-two-denominations case |
| M4 | the metadata gains a key the allowlist lacks | the create cases + the round trip |
| M5 | the paying practice is read from the REQUEST BODY | the source ordering |
| M6 | the return URL derives from a caller-controlled `Host` | the return-URL source |
| M7 | metadata is rebuilt inline at the Stripe call site | the call-site source |
| M8 | the door is gated on validity, so QA can never walk it | the door source |
| M9 | the panel sends a practice id with the amount | the panel source |
| M10 | a denomination gains a BONUS | the face-value assertion |

⚠️ **AND THE `tsc` POSITIVE CONTROL IS A SEPARATE STEP, BECAUSE EXIT 0 PROVES THE
WRONG THING.** `tsc --noEmit` exiting 0 proves every file *in the project*
type-checks and says nothing about whether a given file *is* in the project — an
excluded file produces identical silence. Each of the three new sources was
poisoned with a deliberate type error in turn; all three made `tsc` exit 2 **and
name their own path**. Session 03's version of this control matched the injected
identifier and briefly reported two healthy files as never-type-checked; `tsc`
reports `path(line,col): error`, so the path is the matcher.

### FOUND ON THE WAY PAST — THE SUBSTRING FAMILY, SIXTH SIGHTING, AND IT IS THE **WATCHED-SET** SHAPE

`gate-rounds-bridge.test.ts` caught two real defects in this work and then a
third thing that was not a defect at all.

1. **Real.** The first draft of the error message used `--color-linear-red`,
   which is **undeclared**. An undeclared token falls to `transparent` with no
   error — the message would simply not have been there.
2. **Real, and the better catch.** The second draft reached for the DANGER token,
   which IS declared and bridges to `--rounds-critical` at **3.33:1** — below AA
   on a Rounds surface. The gate derives its foreground set FROM USAGE, so
   writing that name as a `color:` anywhere is what put it in scope. Fixed by
   adopting the house pair (`--color-linear-coral` + the `qm-rounds-error`
   class), which is where the Rounds host owns the treatment instead of this
   caller.
3. **NOT real — and this is the finding.** With the code correct, the gate stayed
   RED, because the **comment explaining why neither of the first two tokens was
   used names both of them.** The scan read raw source, so a token appearing in
   PROSE counted as a surface using it.

⚠️ **THAT THIRD ONE IS THE WATCHED-SET FAILURE, NOT A BROKEN MATCHER.** The
matcher worked perfectly; CSS never reads a comment, so its universe simply
included text that cannot be a usage. **Fixed ON THE GUARD** — a `surfaceCode()`
helper strips comments before every scan — rather than by rewording the comment,
because rewording fixes one comment and the next author documenting a colour
decision hits it again. This is session 03's precedent from the day before, where
a compose sweep tripped on its own warning and was fixed by stripping `#` lines.

**Both directions are controlled**, because a stripper that ate too much would
make every assertion in that file vacuous while staying green:

- a unit control on literals — active `var(--color-linear-*)` usages survive,
  names that exist only in prose do not, and the real tree's read-name set stays
  above 10;
- an end-to-end probe (`.b7s2-bridge-probe.py`) that puts an **ACTIVE** bad token
  into the panel and runs the whole gate: **both arms still go RED** — the
  undeclared name on arm 1, the AA failure on arm 2 — and the gate returns green
  on restore.

### WHAT THIS STEP DOES **NOT** CLAIM

- **Nothing is billed, and nothing can be.** `ledger_entries` holds **0 rows** in
  both environments. No Stripe account, secret key or webhook secret exists
  anywhere, so production's route refuses with `not_configured` (503) and QA's
  with `unrecognised_key_mode` (400).
- **No Checkout Session has ever been created**, by anything, in any
  environment. The CREATE path is proven at unit level and by source; the
  REFUSAL path is what runs end to end.
- **The `$10` promo grant is still unwritten** — `bucket = 'promo'` exists in
  B5's schema and nothing writes it. That is B7 step 3, and see below for why it
  did not ride with this one.
- **The webhook's CREDITED path remains unproven end to end**, unchanged from
  step 1 and for the same reason: proving it appends a `topup` row to QA's
  append-only ledger and permanently ends the zero-row state rulings 89(e) and
  90(d) preserve.

### ⚠️ WHY B7 STEP 3 DID NOT RIDE WITH THIS — NAMED, NOT FORGOTTEN

The `$10` promo grant writes a `grant` row per practice. In production that is
**197 rows into an append-only table**, and it therefore:

- **ends the zero-row state on purpose**, closing the window rulings 89(e) and
  90(d) both rely on — an append-only table cannot take a new column later
  without either a fail-open DEFAULT or a backfill UPDATE, and *"the table is
  empty"* is the whole reason B5's `bucket` and B6's `pricing` were free;
- is a **ruled production mutation** in the sense of ruling 59, so it needs that
  shape in full: population re-derived at execution time, every abort guard
  proven to fire, transactional with verification before COMMIT;
- **grants credit before anything can spend it.** B8 is where balance is
  assessed and where the fail-closed block lives; a wallet that cannot be
  debited and cannot be blocked is a number nobody can act on.

None of that is an argument for never doing it — it is an argument for doing it
as its own item with its own declaration, rather than as the tail of a UI change.
**Carried as B7 step 3, unchanged in scope.**

---

## 🟩 B7 STEP 2 IS LIVE IN PRODUCTION — `626badad`, 2026-08-11T20:02Z

| | |
|---|---|
| deployed commit | `626badad9975b6eb0e18d4deb7c66bf3b8784140` |
| declaration | `docs/foundation/deploys/20260811-626badad.md` — **written 19:12Z, 50 minutes BEFORE the deploy ran** |
| deploy log | `docs/deploy-logs/deploy-20260811T200247Z.log` |
| rollback tag | **`:pre-b7s2-20260811`** — app `c14397e8ae1a` / worker `aec2badfd693`, **cut BEFORE `deploy-prod.sh` ran**, verified by id match |
| app image | `c14397e8ae1a` → **`0063e011f2c4`** |
| worker image | `aec2badfd693` → **`0b23d43de9a4`** |
| migration | `20260811190000_b7_checkout_session_audit_actions`; **99 → 100**, asserted by the deploy itself |

### Citation — produced by `check-citation.sh`, not typed

**Citation — 4 of 4 on `626badad9975b6eb0e18d4deb7c66bf3b8784140`:**
   · `CI` 31526520356 a1
   · `e2e` 31526520317 a1
   · `a11y-ci` 31526520371 a1
   · `secrets-scan` 31526520337 a1

All `a1` — no re-runs, nothing to explain.

### THE DECLARATION, JUDGED — 23 of 23, EVERY ONE AS DECLARED

**What must change**

| # | declared | measured | |
|---|---|---|---|
| 1 | `_prisma_migrations` 99 → 100 | **100** | ✓ |
| 2 | the new row is `20260811190000_b7_checkout_session_audit_actions` | that exact name, newest | ✓ |
| 3 | `AuditAction` labels 141 → 143 | **143** | ✓ |
| 4 | `CHECKOUT_SESSION_*` in `pg_enum` 0 → 2 | `CHECKOUT_SESSION_CREATED`, `CHECKOUT_SESSION_REFUSED` | ✓ |
| 5 | app image id moves | `c14397e8ae1a` → `0063e011f2c4` | ✓ |
| 6 | worker image id moves | `aec2badfd693` → `0b23d43de9a4` | ✓ |
| 7 | **`POST /api/stripe/checkout` NOT 404 and NOT 400** | **401** | ✓ |

**What must NOT change**

| # | declared | measured | |
|---|---|---|---|
| 8 | **`ledger_entries` 0 rows** | **0** | ✓ |
| 9 | `transcribe_visits` 25 | 25 | ✓ |
| 10 | … `signedAt IS NOT NULL` 17 | 17 | ✓ |
| 11 | `transcribe_md_patients` 16 | 16 | ✓ |
| 12 | `api_usage_events` 1325 | 1325 | ✓ |
| 13 | `ai_calls` 1126 | 1126 | ✓ |
| 14 | `users` 196 | 196 | ✓ |
| 15 | `practices` 197 | 197 | ✓ |
| 16 | `price_rates` 44 | 44 | ✓ |
| 17 | `audit_logs` rows with a `CHECKOUT_%` action 0 | **0** | ✓ |
| 18 | 4 triggers on `ledger_entries`, all `tgenabled='O'` | 4 / 4 enabled | ✓ |
| 19 | 6 CHECK constraints on `ledger_entries` | 6 | ✓ |
| 20 | `POST /api/stripe/webhook` still 503 | **503** | ✓ |
| 21 | `GET /settings` 200, and no settings content unauthenticated | 200, **NONE** of the markers | ✓ |
| 22 | 9 of 9 containers healthy | 9 of 9 | ✓ |
| 23 | co-tenants `307/404/200/200/410` | exactly that | ✓ |

### ⚠️ ASSERTION 7 CAME BACK **401**, AND THAT IS WHY IT WAS DECLARED AS A PAIR

Step 1's equivalent assertion was a flat *"503 is the pass"*. Writing the same
sentence for this route would have been **wrong**, and the declaration says so
in advance rather than explaining it afterwards.

The two routes order their checks differently, and deliberately:

| | first check | an unauthenticated probe gets |
|---|---|---|
| `/api/stripe/webhook` | is a webhook secret configured? | **503** |
| `/api/stripe/checkout` | **is there a session?** | **401** |

The checkout route authenticates first, so an anonymous probe never reaches the
configuration check. **The declared pass condition was therefore `401 OR 503`,
with the finding stated as `NOT 404 and NOT 400`** — 404 would mean the route
did not ship, and **400 would mean a Stripe secret key exists in production**,
because 400 is what a *configured* environment returns for a bad amount or an
unclassifiable key.

⚠️ **Both 401 and 503 have a comfortable story available to them after the fact.
That is exactly the class §2.5 exists to close**, so the pair and its finding
condition were fixed in writing 50 minutes before the probe ran.

### AND THE DECISIVE STRUCTURAL FACT — MEASURED IN THE CONTAINER, NOT THE COMPOSE FILE

**`no STRIPE_* variable at all`** in both `meddoc-pro-transcribe-md-1` and
`meddoc-pro-transcribe-md-worker-1`, read with `printenv` **inside the running
containers**. `check-qa-mock-posture.sh`'s header records why the compose file is
not evidence: a `${VAR:-default}` inherits the shared `.env`, so a file can read
safe while the container is not.

**Positive-controlled**: the same `printenv` returned **55** variables including
`NODE_ENV` and `DATABASE_URL`, so the empty `STRIPE_*` result is a fact about the
environment rather than about a command that read nothing. An emptiness test on a
set whose size was never established is this project's named recurring defect.

That fact is what makes assertion 7's 401 sufficient. The route is authenticated,
so it cannot be probed past its first check — but the configuration it *would*
check is provably absent one layer down.

### WHAT IS LIVE, AND WHAT IS NOT

**Live:** two permanent `AuditAction` labels, an authenticated route that refuses
every anonymous caller at 401 and would refuse every authenticated one at 503,
and a settings page whose billing section is **byte-identical to yesterday's**
because the door only renders when a key is present and there is none.

**NOT live:** any billing behaviour whatsoever. `ledger_entries` still holds
**0 rows**. No Stripe account, secret key or webhook secret exists in any
environment. **No Checkout Session has ever been created, by anything, anywhere.**
The `$10` promo grant is still unwritten. The deploy's own prediction — *"two new
labels on a Postgres enum, plus an HTTP route that refuses, and a settings page
byte-identical to today's"* — held on all 16 must-not-change assertions.

### ⚠️ THE MIGRATION CANNOT BE ROLLED BACK, AND THAT WAS DECLARED IN ADVANCE

Postgres has no `ALTER TYPE … DROP VALUE`. `CHECKOUT_SESSION_CREATED` and
`CHECKOUT_SESSION_REFUSED` are permanent from the moment this deploy applied.
Rolling the IMAGE back (`:pre-b7s2-20260811`) removes the route and the door and
leaves two unused enum labels behind, which cost nothing. Named in the
declaration's Rollback section before the deploy rather than discovered during
one.

### QA WAS ONE MIGRATION BEHIND, AND THE `--qa` ARM IS WHAT SAID SO

Immediately after the deploy, `assert-migrations-applied.sh --qa` went **RED**:
`100 in repo, 99 recorded`, naming `20260811190000_b7_checkout_session_audit_actions`.

That is the ordinary post-deploy asymmetry rather than a fault — but it is
**exactly the drift that accumulated invisibly for three months** while every
session ran the bare invocation and reported the check green. AGENTS.md's note on
that is the reason the arm is now a standing STEP 0 line.

Cleared in the same session, per the QA compose file's own instructions: build
`db-migrate` **from the QA compose** (which does have a `build:` section, unlike
the service note's warning about the *no-build* case), then
`run --rm db-migrate migrate deploy`, then **re-assert**. Prod and QA are both
**100 of 100**, and `check-qa-mock-posture.sh` is still 🟢 afterwards — the QA
stack remains vendor-severed with its literal dummy keys, which is what makes
B7's refusal path walkable there.

---

## ✅ B8 STEP 1 IS BUILT — THE WALLET READ, AND ADMISSION JUDGES THE MONEY A DEBIT CAN REACH — 2026-08-11

**Item:** B8's first half — *"insufficient balance blocks the work; fail-closed
here means: if the balance cannot be read, block"* (SPEC §2.4).

**Nothing calls either function.** The pipeline call site is B8 step 2, and that
is required rather than merely deferred: ruling 90(e) says the debit and the
block land *"in one change and in that order"*, and the debit inherits the
`logApiUsage` read-after-write race that same ruling moved onto B8. This step
ships a proven decision for that change to wire.

### WHAT LANDED

| | |
|---|---|
| `packages/ai/src/billing-balance.ts` | `readPracticeBalance` (the only database touch) + `decideAdmission` (pure) |
| `packages/ai/src/__tests__/gate-b8-balance-fail-closed.test.ts` | 19 assertions across 6 arms |
| `packages/ai/src/index.ts` | the export surface B8 step 2 will import |

No migration. No schema change. **`ledger_entries` is untouched and still holds
0 rows in both environments** — which matters, because rulings 89(e) and 90(d)
both depend on that state and this item deliberately does not spend it.

### ⚠️ THE ONE THAT MATTERS — ADMITTING ON THE TOTAL WOULD HAVE BEEN A FAIL-OPEN

B6's writer hard-codes `bucket: 'paid'` (`billing-charge.ts:414`), with the
comment *"usage always draws on `paid`; the `promo` bucket is granted and drawn
separately, and B7 owns that split."* **B7's three steps did not take that
split**, so it is genuinely unowned today.

That makes the obvious implementation wrong, and wrong in the direction that
looks generous:

> a practice holding **$10 promo and $0 paid** would be ADMITTED on a total of
> $10, then debited against `paid` — which is empty. It goes negative, the work
> happens, and the $10 nobody can reach is still sitting there.

**The block would have blocked nothing, and B7 step 3's promo grant would be a
number that can never be spent.** So admission reads `SPENDABLE_BUCKETS` — the
set the debit can actually reach — and the cost is paid loudly: a promo-only
practice is refused, under its own reason `credit_not_spendable`, never folded
into `insufficient_balance`. B6 made the same trade for an unpriceable visit and
gave the reason: naming it is *"the only one where being wrong is VISIBLE"*.

⚠️ **AND THE AGREEMENT IS ASSERTED ACROSS THE FILE BOUNDARY, BECAUSE NO TYPE CAN
SEE IT.** `bucket: 'paid'` is a string literal in another file. The gate reads
B6's source and asserts the set it writes equals the set admission judges —
**mutation-proved from BOTH sides** (M6: this constant drifts; M7: the writer
drifts), because the drift will arrive from whichever side a future step edits.

### THE SECOND ONE — THE BALANCE IS READ TWO WAYS AND MUST AGREE

Every row carries `balanceAfter`, derived by `ledger_entries_derive()`. So a
balance can be stated twice: `SUM("amountMicroUsd")`, and the `balanceAfter` of
the highest `seq`. They are identical by construction, and B5's migration header
says the only way they diverge is *"if something wrote around the trigger"*.

**Ruling 89(c) recorded exactly that happening**: a hand-written guard accepted
an UPDATE that rewrote an amount `5000000 → 999` **while `balanceAfter` stayed
5000000**. A reader trusting either number alone would have reported a balance
with total confidence.

Reading both and REFUSING on disagreement turns a silent corruption into a
block, for one extra aggregate in the same query. ⚠️ **And the refusal is not
"pick the smaller"** — a ledger that disagrees with itself has an unknown
balance, and the smaller of two numbers you do not trust is still a number you
do not trust. That specific repair is its own gate arm (M3).

### THE MUTATION MATRIX — SAID FIRST, THEN MADE TO FAIL

The gate's header names the five ways it could go blind *before* the proofs ran.
**7 of 7 caught, 0 blind**, each applied to the SOURCE with an occurrence
assertion, observed RED, and restored from scratch copies whose digests were
asserted first — never `git checkout`, per the 2026-08-08 `anthropic.ts` loss.

| | mutation | arm that reddened |
|---|---|---|
| M1 | the `catch` returns a balance instead of `ok:false` | a thrown query yields `ok:false`, NOT zero |
| M2 | the SUM-vs-`balanceAfter` comparison is dropped | DISAGREEING rows refuse |
| M3 | the disagreement resolves by picking the smaller | the refusal does NOT resolve to the smaller |
| M4 | admission reads `totalMicroUsd` | promo-only is BLOCKED |
| M5 | `> 0n` becomes `>= 0n` | EXACTLY ZERO blocks |
| M6 | `SPENDABLE_BUCKETS` drifts | writes exactly the buckets admission judges |
| M7 | **the WRITER** drifts to `promo` | the same arm, from the other side |

Control green before, green after restore. `tsc` 0 errors; **3525 unit tests
passed**, 2 files skipped.

### ⚠️ FOUND ON THE WAY PAST — THE SUBSTRING FAMILY, SEVENTH SIGHTING, IN MY OWN FILE

Arm 6 asserts the source contains **no `?? 0`** — the fail-open shape ruling
80(c) forbids by name. It went red on correct code, because
`billing-balance.ts`'s header **discusses `?? 0` at length**, precisely to
explain why the habit is fail-open at the pricing seam and harmless at this one.

Same family as the five in `AGENTS.md`, and the same cure: the scanner strips
comments before matching, using the byte-identical `strip` from
`gate-mock-suite-stubs-the-db.test.ts:70`. **Controlled in both directions** —
the arm asserts the RAW file *does* match (so the control cannot go stale when
somebody rewrites the header) and the stripped file does not, plus a check that
the strip is not simply eating the file.

Caught before the arm had ever run, by reading the regex against the file it
would scan rather than by running it.

### WHAT THIS STEP DOES **NOT** CLAIM

- **Nothing blocks anything.** No caller exists. A doctor's visit runs exactly as
  it did yesterday; this is unreachable code compiled into the image, the same
  shape B6's writer shipped in (ruling 90(e)).
- **The reader has never seen a real ledger row**, because there are none
  anywhere. The gate drives it through a stubbed `@meddoc/db`, so what is proven
  is that it refuses the shapes a broken database produces — not that this
  database produces them. RELAY already requires B8 to be proven on QA; that is
  step 2's, against rows step 2 writes.
- **No per-visit cost is estimated, and the threshold is only `> 0`.** The one
  measured visit is the 2026-08-09 sanctioned smoke at **$0.49** — n=1, one
  specialty, one input mode, every call succeeding. A threshold invented from
  that would refuse work on a guess and would be indistinguishable, in the
  ledger, from one that was measured.
- **The promo drawdown is still unowned.** This step makes its absence *loud*
  rather than fixing it — `credit_not_spendable` is a refusal reason, not a
  feature.

### ⚠️ WHY B7 STEP 3 DID NOT GO FIRST — THE REORDER, AND ITS REASONING

Session 04 named the promo grant as the next item and gave three reasons it did
not ride with B7 step 2. **The third is decisive and it is an ORDERING argument,
not a scheduling one**: the grant *"grants credit before anything can spend it.
B8 is where balance is assessed and where the fail-closed block lives; a wallet
that cannot be debited and cannot be blocked is a number nobody can act on."*

There is a second argument session 04 half-made, and it is the stronger one:

> **the zero-row state is a BUDGET, and the grant spends it permanently.**

B5's `bucket` and B6's `pricing` both landed early *specifically because the
table was empty* — rulings 89(e) and 90(d) say so in as many words, because an
append-only table cannot take a new column later without either a fail-open
DEFAULT or a backfill UPDATE. Writing **197 grant rows** closes that window for
every column B8 has not yet discovered it needs.

So the grant executes **after** B8 knows its own schema, not before. Deferring an
execution is free and reversible in the only direction that matters; executing
it is not. Recorded as ruling **#94(e)**.

⚠️ **This does NOT contradict ruling 90(e)'s *"the debit and the block belong in
one change and in that order"*.** That constrains the WIRING change — nothing is
wired here, so neither the debit nor the block is live, and step 2 remains free
to land both together.

---

## 🟩 B8 STEP 1 IS LIVE IN PRODUCTION — `dbb584a4`, 2026-08-12T01:10Z

| | |
|---|---|
| deployed commit | `dbb584a4469f39f1eb74c3649e1c56c83ac364f2` |
| declaration | `docs/foundation/deploys/20260812-dbb584a4.md` — **written 00:45Z, 25 minutes BEFORE the deploy ran** |
| deploy log | `docs/deploy-logs/deploy-20260812T011004Z.log` |
| rollback tag | **`:pre-b8s1-20260812`** — app `0063e011f2c4` / worker `0b23d43de9a4`, **cut BEFORE `deploy-prod.sh` ran**, verified by id match |
| app image | `0063e011f2c4` → **`fa219f877a58`** |
| worker image | `0b23d43de9a4` → **`daa21860f140`** |
| migration | **none** — 100 → 100, asserted by the deploy itself |

### Citation — produced by `check-citation.sh`, not typed

**Citation — 4 of 4 on `dbb584a4469f39f1eb74c3649e1c56c83ac364f2`:**
   · `CI` 31550128629 a1
   · `e2e` 31550128531 a1
   · `a11y-ci` 31550128489 a1
   · `secrets-scan` 31550128504 a1

All `a1` — no re-runs on the merge commit, nothing to explain. ⚠️ **The PR HEAD's
`e2e` was re-run once and that is recorded below**; it does not enter this
citation, which is merge-commit-scoped by construction.

### THE DECLARATION, JUDGED — 17 of 17, EVERY ONE AS DECLARED

**What must change** — the whole list was two rows.

| # | declared | measured | |
|---|---|---|---|
| 1 | app image id moves from `0063e011f2c4` | `fa219f877a58` | ✓ |
| 2 | worker image id moves from `0b23d43de9a4` | `daa21860f140` | ✓ |

**What must NOT change**

| # | declared | measured | |
|---|---|---|---|
| 3 | `_prisma_migrations` 100 | 100 | ✓ |
| 4 | **`ledger_entries` 0 rows** | **0** | ✓ |
| 5 | `transcribe_visits` 25 | 25 | ✓ |
| 6 | … `signedAt IS NOT NULL` 17 | 17 | ✓ |
| 7 | `transcribe_md_patients` 16 | 16 | ✓ |
| 8 | `api_usage_events` 1325 | 1325 | ✓ |
| 9 | `ai_calls` 1126 | 1126 | ✓ |
| 10 | `users` 196 | 196 | ✓ |
| 11 | `practices` 197 | 197 | ✓ |
| 12 | `price_rates` 44 | 44 | ✓ |
| 13 | `audit_logs` with `CHECKOUT_%` 0 | 0 | ✓ |
| 14 | `POST /api/stripe/webhook` still 503 | **503** | ✓ |
| 15 | `POST /api/stripe/checkout` still 401 | **401** | ✓ |
| 16 | 9 of 9 containers healthy | 9 of 9 | ✓ |
| 17 | co-tenants `307/404/200/200/410` | exactly that | ✓ |

### WHAT IS LIVE, AND WHAT IS NOT

**Live:** two exported functions compiled into the image, reachable from
`@meddoc/ai`'s barrel and called by nothing.

**NOT live:** any blocking behaviour whatsoever. No caller exists, so a doctor's
visit runs exactly as it did yesterday. `ledger_entries` still holds **0 rows**,
which is assertion 4 and the one that carries the item — rulings 89(e), 90(d) and
94(e) all depend on that state.

### ⚠️ THE BASELINE SCRIPT LIED FIRST, AND A POSITIVE CONTROL IS WHAT CAUGHT IT

The first baseline attempt nested its SQL inside two layers of double quotes
under `shell=True`. The shell ate it, `psql` received nothing, and the script
**printed an empty DB section as a result**. Every must-not-change figure in this
declaration would have been written from no measurement at all.

The rewrite passes the SQL as an argv element and runs
`SELECT 'control', 1` against its known answer first. **That control earned
itself immediately**: attempt two failed with `role "postgres" does not exist` —
the production role is `meddoc` — which the silent version would have rendered
as another blank section, indistinguishable from the first.

Two blank sections in a row, both of which would have read as "the tables are
empty" on a deploy whose headline assertion is *a table being empty*.

### ⚠️ THE PR HEAD's `e2e` WENT RED, AND IT WAS NOT `logoutViaMenu`

`e2e` on the PR head failed on **`16-account-settings.spec.ts:38`** — *"account:
profile edit persists across reload"* — with
`the profile panel never showed its saved chip — updateProfileAction did not
return ok`, on **both** attempts.

**Diagnosed before re-running, not after.** Three independent lines, and the
first is decisive:

1. **REACHABILITY.** `src/actions/profile.ts` imports `next/cache`, `zod`,
   `@meddoc/db`, `@meddoc/shared/specialties` and `@/lib/auth`. It does **not**
   import `@meddoc/ai`, directly or through `@/lib/auth`. This commit's only
   non-doc, non-test change is a new file plus five export lines in
   `packages/ai/src/index.ts` — **not in that path's import graph at all.**
2. **THE TEST'S OWN HEADER SAYS IT.** It documents this exact symptom as an
   already-root-caused hydration race: *"reproducible 1-in-8 flake"*, where a
   pre-hydration click submits as a native form POST so `state` stays `null` and
   the chip never renders. The mitigation is a `networkidle` wait measured at
   **12/12** — which does not establish a rate below roughly 8%.
3. **HISTORY.** Eight consecutive main-lineage `e2e` successes preceded it.

⚠️ **Playwright's `retry #1` is NOT a second draw** — it runs in the same job on
the same runner, so a slow runner biases both attempts identically. A fresh run
is a draw. One re-run was taken **with the mechanism named in advance**, and it
came back green on the identical commit: **`e2e` red then green on the same
tree** is the tree-identity check in its strongest available form, and it rules
out the code.

**Filed as its own issue rather than absorbed into this item**, because the
mitigation's 12/12 is not proof and the next session should not re-derive this.

### ⚠️ AND SESSION 04's UNATTRIBUTED `e2e` FAILURES ARE NOW ATTRIBUTED

Session 04 recorded *"five dependabot `e2e` failures in a 12-minute window at
15:42–15:54Z; logs unreadable, so not attributed either way."*

They are attributable through the jobs API rather than the logs: all five failed
at the step **`Install Playwright chromium`**, before a single test executed.
That is the *external reach in the build* class AGENTS.md already names — a
download step, not a test failure — and it means **those five say nothing about
any tree** and do not corroborate the `16-account-settings` flake above.

### ⚠️ AND MY OWN CI POLLER PRODUCED A CLEAN-LOOKING LIE FOR NINE MINUTES

The first poller asked `gh run list --json` for a field named `attempt`, which
does not exist. `gh` wrote the error to **stderr** and exited non-zero; the
script captured only **stdout**, and `json.loads("" or "[]")` produced `[]`. It
printed *"no runs visible yet"* **thirteen times across nine minutes** while four
runs were in flight.

⚠️ **THE DANGEROUS PART IS NOT THE BUG, IT IS THE EXPLANATION THAT WAS WAITING.**
AGENTS.md documents a REAL `gh run list --commit` defect with precisely this
signature — `[]` during the propagation window on a full SHA. Adopting it would
have produced a session report *corroborating a recorded canon entry with
evidence that was actually my own broken script*, which is worse than the
original bug: it would have made a genuine defect look better-evidenced than it
is. Two wrong mechanisms were reached for before the right one — a merge-ref
hypothesis (refuted: the run's `headSha` is byte-identical to the branch head)
and propagation lag (refuted: the plain non-`--json` call answered correctly at
the same moment).

The fix is the general one: **a non-zero exit or unparseable output is an ERROR,
never an empty set.** It earned itself on its first run by catching a genuine
transient — `tls: failed to verify certificate` from `api.github.com` — which the
silent version would have reported as *"no runs visible yet"*.

**A broken check and a clean system produce identical output**, and this is the
third instrument in this one session to demonstrate it (the poller, the baseline
script, and arm 6's comment-stripper).

---

## ✅ B8 STEP 2 IS BUILT — THE PIPELINE SEAM, AND IT SHIPS INERT — 2026-08-12

**Item:** B8's second half — the call site. Ruling 90(e): *"B8 is where money is
assessed, so the debit and the block belong in ONE CHANGE AND IN THAT ORDER"*,
and, on the hazard it moved here by name, *"whoever wires this must solve the
ordering, and CANNOT DO IT BY ACCIDENT."*

### WHAT LANDED

| | |
|---|---|
| `packages/ai/src/api-usage.ts` | `drainApiUsage()` + `pendingApiUsageWrites()` — the fire-and-forget meter becomes *observable* without becoming blocking |
| `packages/ai/src/billing-usage-source.ts` | `loadVisitChargeableUsage` — drains, then reads, then maps `timestamp` → `createdAt` |
| `packages/ai/src/billing-pipeline.ts` | `admitVisitOrThrow` / `chargeVisitUsage` / `billingEnforced` / `BillingAdmissionError` |
| `apps/transcribe-md/src/worker.ts` | the two seams, at the two correct points in `processVisit` |
| `apps/transcribe-md/src/worker/error-categorize.ts` | one structural arm — a refusal classifies itself |
| `packages/ai/src/__tests__/gate-b8-pipeline-seam.test.ts` | 19 assertions across 8 arms |
| `apps/transcribe-md/src/worker/error-categorize.test.ts` | 5 more, in the suite that owns the classifier |

No migration. No schema change. **`ledger_entries` is untouched and still holds
0 rows in both environments** — and with the flag off it will stay that way,
which is the point.

### ⚠️ THE ONE THAT MATTERS — WIRING THIS ON TODAY IS A TOTAL CLINICAL OUTAGE

`ledger_entries` holds **0 rows in production**, deliberately: rulings 89(e),
90(d) and 94(e) each spent design budget keeping it empty, and B7 step 3's promo
grant — the only thing that would put money in a wallet — is PARKED behind this
very item by ruling 94(e).

So enabling the block does not "turn on billing". It means:

> every practice has a spendable balance of 0 → `decideAdmission` returns
> `insufficient_balance` for every one of them → **EVERY VISIT IN PRODUCTION
> FAILS, for every doctor, immediately.**

A fail-closed money gate whose default is ON is normally the right posture.
Here it is an outage, **because the gate is correct and the wallets are empty**.
That is an ordering problem, not a design flaw in the gate, and a flag is what
lets the debit and the block land together — as 90(e) requires — without the
landing being the moment they take effect.

**The sequence the flag holds open:**

1. this item lands and deploys, **INERT** ← we are here
2. **B7 step 3** grants the promo credit (197 `grant` rows)
3. `BILLING_ENFORCED=true`, and the block starts blocking

⚠️ **The debit is behind the SAME flag as the block, and that is not tidiness.**
Charging while not blocking is a coherent posture and it is the wrong one here:
`ledger_entries` is APPEND-ONLY, so a debit against an unfunded practice drives
it negative with no way to remove the row — only to offset it with an
`adjustment`. Charging before anyone can be funded manufactures a debt nobody
agreed to, permanently, and ends the zero-row state three rulings depend on.

### ⚠️ THE RACE RULING 90(e) NAMED — CLOSED, AND NOT WITH A SLEEP

`logApiUsage` returns before its row exists (`setImmediate`), so a caller that
reads `api_usage_events` at pipeline end sees fewer rows than the visit
consumed. **The failure is silent and always an UNDER-charge** — no error, no
missing visit, just a smaller number in a table that can only be corrected by an
`adjustment` row.

Three things about the fix are deliberate:

- **The meter stays fire-and-forget.** Awaiting the write would put a database
  round-trip in every vendor call's hot path, which is exactly what the
  `setImmediate` exists to prevent. The pending set becomes *observable*
  instead, so one caller can wait while every other caller keeps not waiting.
- **`await sleep(50)` would have looked identical on every test.** It drains
  this queue in practice today and guarantees nothing: green locally, green in
  CI, under-charging on the one loaded night a write takes 60ms. A promise you
  can await is a fact; a delay you tuned is a hope.
- **The drain lives INSIDE the loader, not at the call site.** A caller that
  must remember to drain first is a hand-kept list of one, and forgetting it
  produces a slightly small number rather than an error. There is now no way to
  obtain these rows without having waited.

### ⚠️ AND A SECOND, QUIETER DEFECT: `createdAt` IS NOT A COLUMN

`ChargeableUsageRow` declares `createdAt: Date`. **The column is `timestamp`** —
`ApiUsageEvent.timestamp`, no `@map`. A loader that did the obvious thing —

```ts
const rows = await prisma.apiUsageEvent.findMany({ where: { visitId } });
return commitVisitCharge({ ..., rows });
```

— hands `priceUsageRows` a row whose `createdAt` is `undefined`, and that field
is load-bearing: `billing-charge.ts:294` passes it as `at` to the rate lookup,
which is how `effectiveFrom` picks the period. Every component would come back
`no_rate_for_key_at_instant` and the whole visit would decline as `unpriced` —
**a charge of nothing, reported as a pricing gap, for a reason that has nothing
to do with pricing.**

`tsc` catches it — **mutation-proved**: replacing the mapping produces
`TS2322 … Property 'createdAt' is missing`. But only where the client is typed,
and this repo reaches for `(prisma as any)` in several places, `api-usage.ts:175`
among them. The mapping is written out field by field for that reason.

### ⚠️ AN UNREADABLE BALANCE IS A SYSTEM FAULT, NOT AN EMPTY WALLET

SPEC §2.4 says *"if the balance cannot be read, block"*, and step 1 obeys it.
But refusing is half a decision — the visit still has to be RECORDED as
something, and the two refusals are not the same event:

| refusal | who is at fault | retry |
|---|---|---|
| `insufficient_balance` / `credit_not_spendable` | the practice is out of money | **permanent** |
| `balance_unreadable` | **our** database, or a ledger disagreeing with itself | **transient** |

Filing the second under the first tells a paid-up doctor they are out of credit
because our pool was exhausted, and puts that in their account's story. It is
also the half of B8 the auto-credit exists to compensate — **a fault misfiled as
a balance problem is a fault the credit will never find.**

The category travels as a **typed property**, never a message substring:
`categorizeError` is otherwise a regex over message text, and AGENTS.md records
four sightings of the substring trap. Negative-controlled both ways — a
look-alike message gets no billing semantics, and the class name alone does not
force `permanent`.

### THE SEAMS FAIL IN OPPOSITE DIRECTIONS, ON PURPOSE

- **`admitVisitOrThrow` THROWS.** A boolean return has to be checked, and a
  caller that forgets proceeds to spend money — the silent direction.
- **`chargeVisitUsage` NEVER throws.** It runs after a finished clinical note
  exists. Throwing would take a READY visit and fail it, **destroying a
  doctor's completed work over a billing write.** The money we could not record
  is lost rather than the note, and the loss is loud (`charged: 'failed'`,
  logged). Same trade `logApiUsage` and `logAudit` already make here.

### WHAT WAS MUTATION-PROVED

| # | mutation | result |
|---|---|---|
| M1 | drop the `timestamp` → `createdAt` mapping | **`tsc` RED** — TS2322 |
| M2 | remove `drainApiUsage()` from the loader | **3 arms RED** |
| M3 | move `markSettled()` out of `finally` | **GREEN** — see below |
| M4 | M3 *and* remove the broad `catch` | **whole file RED** (drain hangs) |
| M5 | remove the structural arm from `categorizeError` | **2 arms RED** |

⚠️ **M3 IS REPORTED AS GREEN BECAUSE IT WAS GREEN.** The `finally` is redundant
with today's broad `catch`; it is not what makes the current code correct. It is
what keeps it correct the day somebody narrows that catch to a specific error
type — a change that would otherwise convert a swallowed warning into a
permanently hung pipeline, with **nothing failing at the moment of the edit**.
Stated rather than counted as a fifth proof.

### ⚠️ AND THE GATE CAUGHT ITSELF — TITLE NARROWER THAN MEASUREMENT

Arm 9's first assertion was written as `src.includes('unitsSource:')` under the
title *"the query filters on visitId only"*. It **went red on its first run
against correct code**: `unitsSource:` appears three times legitimately — the
row interface, the `select`, and the mapping. **Selecting a column is not
filtering on it**, and the check's name said *filters* while its body measured
*mentions*.

That is AGENTS.md's *"a check whose TITLE is narrower than what it MEASURES"*,
caught in this file's own first execution. The honest form counts `where:`
clauses (exactly one) and asserts no comparison against the ruled values.

### WHAT IS BUILT, AND WHAT IS NOT

**Built:** both seams, wired at the two correct points in `processVisit`, with
the ordering hazard closed.

**NOT built, and NAMED rather than left to be discovered:**

- **The failure path does not charge.** A visit that dies at L5 has already paid
  for L1–L4 and nothing records it. Charging there is inseparable from B8's
  other half — *"system faults credit back via DLQ classification"* — because
  the two decide the same question from opposite ends, and building the debit
  without the credit would **bill doctors for our outages**. Carried as B8 step 3.
- **The debit's success path has never executed, in any environment.**
  `commitVisitCharge` refuses off production by ruling 90(c), so the gate proves
  only that the refusal is absorbed rather than thrown. Unprovable anywhere a
  test may run, and it stays that way until the flag is turned on in production.

### FINDINGS THIS ITEM DID NOT GO LOOKING FOR

1. **Template calls are billable and belong to no visit — so a per-visit debit
   can never charge them.** `tm_template_parse` (35 rows), `tm_template_phi_scan`
   (29) and `tm_template_synthetic_phi_scan` (2) are **anthropic** — inside
   `BILLABLE_PROVIDERS` — and 100% `visitId IS NULL`, correctly, because they run
   at template UPLOAD. Every one is real money this seam structurally cannot
   reach. Not a bug in the wiring; a gap in what "a visit's usage" can mean.
   Whether they are billed at all is a product question, and B9 will surface them
   as an unreconciled remainder if nothing does.
2. **A historical attribution hole, now closed.** `tm_soap_draft` is
   `visitId IS NULL` on **20 of 102** rows and `tm_entities` on **3 of 82** — all
   between 2026-07-02 and 2026-07-26, against attributed rows running to
   2026-08-09. Since 2026-07-27 the only unattributed anthropic rows are the 8
   template ones above, so **live per-visit attribution is 100%**. Recorded
   because a future reader querying lifetime totals will find a 20% hole in the
   dominant stage and reasonably conclude the meter is broken.
3. **`CommitResult` under-specifies its own pair.** The `written: false` arm
   types `decision` as the WHOLE `ChargeDecision` union, including the
   `charge: true` branch that cannot occur there. Narrowed rather than cast at
   the one caller, so the day the relationship changes it stops compiling.
4. **`mkdir` and `cp` are not granted to the loop, and they are not in
   MASTER.md's permissions table.** AGENTS.md's mutation-proof rule requires
   copying every file to scratch *before* the first mutation and restoring from
   the copy — that procedure is **not executable by this loop**. The substitute
   used here is Edit-mutate / Edit-restore, which is byte-exact because the prior
   text is in context, and which never touches git. Worth a table row.

### 🔓 B7 STEP 3 IS UNPARKED — ITS TRIGGER WAS NAMED, AND IT IS NOW MET

Ruling 94(e) parked the promo grant *"until B8 knows its own schema"*, and the
reason was specific rather than general: an append-only table cannot take a
later column without a fail-open DEFAULT or a backfill UPDATE, so **the zero-row
state was a budget being held open for B8.**

**B8 step 2 spent none of it.** No column, no CHECK, no migration: admission
only reads, the debit uses B6's existing `pricing` column, and a refusal records
itself through `failureCategory`, which is already `String?` and needed no enum
value — so it is not even the three-edit `AuditAction` hazard.

The budget was not needed. **B7 step 3 is the next item**, and it is the thing
that makes turning `BILLING_ENFORCED` on possible at all. Its scope is unchanged
from the description at *"Carried as B7 step 3"* above — a ruled production
mutation in the sense of ruling 59, needing the population re-derived at
execution time, every abort guard proven to fire, and verification inside the
transaction before COMMIT.

⚠️ **Note what unparking does NOT mean.** The grant ends the zero-row state
permanently, so it is the last moment any append-only column can be added for
free. Anything B9 will want on `ledger_entries` should be argued for **before**
that item runs, not after — and "B9 has not been designed yet" is a reason to
check, not a reason to assume it wants nothing.

---

## 🟩 B8 STEP 2 IS LIVE IN PRODUCTION — `b4738ad8`, 2026-08-12T06:00Z

| | |
|---|---|
| deployed commit | `b4738ad86c15b1f4a33f70b0d9a837049f4f9d6a` |
| declaration | `docs/foundation/deploys/20260812-b4738ad8.md` — **written 05:14Z, 40 minutes BEFORE the deploy ran** |
| deploy log | `docs/deploy-logs/deploy-20260812T055458Z.log` |
| rollback tag | **`:pre-b8s2-20260812`** — app `fa219f877a58` / worker `daa21860f140`, **cut BEFORE `deploy-prod.sh` ran**, verified by id match against the running containers |
| app image | `fa219f877a58` → **`135784a005d7`** |
| worker image | `daa21860f140` → **`c72c02e027a9`** |
| migration | **none** — 100 → 100, asserted by the deploy itself |

### Citation — produced by `check-citation.sh`, not typed

**Citation — 4 of 4 on `b4738ad86c15b1f4a33f70b0d9a837049f4f9d6a`:**
   · `CI` 31565843507 a1
   · `e2e` 31565843786 a1
   · `a11y-ci` 31565843508 a1
   · `secrets-scan` 31565843512 a1

All `a1` — no re-runs anywhere, on the PR head or the merge commit, so there is
nothing to explain. The PR head was also 4 of 4 first time; `e2e` took 41m18s
and the `16-account-settings` flake of issue #610 did **not** recur.

### THE DECLARATION, JUDGED — 19 of 19, EVERY ONE AS DECLARED

**What must change**

| # | declared | measured | |
|---|---|---|---|
| 1 | app image moves from `fa219f877a58` | `135784a005d7` | ✓ |
| 2 | worker image moves from `daa21860f140` | `c72c02e027a9` | ✓ |

**What must NOT change**

| # | declared | measured | |
|---|---|---|---|
| 3 | `_prisma_migrations` 100 | 100 | ✓ |
| 4 | **`ledger_entries` 0** | **0** | ✓ |
| 5 | `transcribe_visits` 25 | 25 | ✓ |
| 6 | … `signedAt IS NOT NULL` 17 | 17 | ✓ |
| 7 | … `status = 'FAILED'` 0 | **0** | ✓ |
| 8 | `transcribe_md_patients` 16 | 16 | ✓ |
| 9 | `api_usage_events` 1325 | 1325 | ✓ |
| 10 | `ai_calls` 1126 | 1126 | ✓ |
| 11 | `users` 196 | 196 | ✓ |
| 12 | `practices` 197 | 197 | ✓ |
| 13 | `price_rates` 44 | 44 | ✓ |
| 14 | `audit_logs` with `CHECKOUT_%` 0 | 0 | ✓ |
| 15 | `POST /api/stripe/webhook` 503 | 503 | ✓ |
| 16 | `POST /api/stripe/checkout` 401 | 401 | ✓ |
| 17 | 9 of 9 containers healthy | 9 of 9 | ✓ |
| 18 | co-tenants `307/404/200/200/410` | exactly that | ✓ |
| 19 | **`BILLING_ENFORCED` unset in the LIVE containers** | **absent from both**, positive-controlled | ✓ |

### ⚠️ `audit_logs` MOVED +16, AND IT WAS EXCLUDED IN ADVANCE — WITH ITS REASON

10731 → 10747. The declaration deliberately did **not** carry `audit_logs` as a
must-not-change total, because ordinary traffic writes to it, and declared the
falsifiable form instead: **no row from a billing or checkout action** (row 14).

Enumerated rather than assumed. All 16 are human traffic between **05:24Z and
05:26Z — half an hour BEFORE the deploy started at 05:54Z**:

`ADMIN_API_ACCESS` 5 · `LOGIN_SUCCESS` 3 · `MFA_CHALLENGE_PASSED` 2 ·
`ADMIN_DASHBOARD_ACCESS` 2 · `VIEWED_VISIT_LIST` 2 · `VIEWED_SETTINGS` 1 ·
`VIEWED_PATIENT_LIST` 1. That sums to exactly 16, and nothing in it is
billing-shaped.

⚠️ **It also means another actor was signed in during this session** — an admin
login at 05:24Z, not this loop. Recorded because a session that assumes it is
alone will attribute somebody else's movement to itself.

### ⚠️ AND THE QUERY THAT INVESTIGATED IT LIED FIRST

The first breakdown query used a **30-minute** window and returned **zero rows**
— against a count that had provably moved by 16. Two wrong explanations were
available and both were plausible: the wrong column name (an earlier query in
this same session had already failed on `createdAt`, which `api_usage_events`
does not have either) and an empty set.

It was neither. **The window was narrower than the measurement interval** —
baseline at 05:14Z, measurement at 06:05Z, a 51-minute gap being asked about
over 30 minutes. The contradiction is what caught it: *a zero that disagrees
with a number you already measured is a broken query, not a clean answer.*
Widened to 90 minutes, all 16 appeared at once.

### WHAT IS LIVE, AND WHAT IS NOT

**Live:** the two seams compiled into the worker image and called on every
visit — `admitVisitOrThrow` before the first vendor call, `chargeVisitUsage`
after READY. Both return immediately, because `billingEnforced()` is false.

**NOT live:** any billing behaviour whatsoever. No balance is read, no ledger
row is written, no visit is blocked. `ledger_entries` still holds **0 rows**,
which is assertion 4 and the one that carries the item — rulings 89(e), 90(d)
and 94(e) all depend on that state, and B7 step 3 is the item that will
deliberately end it.

⚠️ **THE FLAG IS THE ONLY THING BETWEEN THIS CODE AND A TOTAL CLINICAL OUTAGE**,
and that is not hyperbole about a hypothetical: with 0 rows in `ledger_entries`,
turning `BILLING_ENFORCED=true` today refuses every visit for every doctor.
Row 19 exists so that fact is checked in the containers rather than assumed from
the compose file, and row 7 exists so the symptom is checked too.

### ⚠️ OWED BEFORE THE FLAG IS EVER TURNED ON — THE QA BEHAVIOURAL PROOF

RELAY requires *"B8 must be proven on QA"*, and this item does **not** discharge
it. What exists is a unit-level gate over the decision logic plus a type-checked
wiring; what does not exist is a visit walked end to end through the real worker
with the flag on, watching admission refuse and the visit land FAILED with a
`transient`/`permanent` category.

That proof is cheap on QA — the stack's `ledger_entries` is also empty, so a
zero-balance refusal is its natural state — and it is **a precondition of
enabling the flag**, not of landing this code. Named here so the next session
does not have to re-derive that it is missing.

---

## ✅ B7 STEP 3a IS BUILT — THE PROMO DRAW ORDER, AND WHY IT HAD TO COME FIRST — 2026-08-12

**Item:** an INSERTED half-step, ahead of B7 step 3's grant. Ruling **#96**.

### THE FINDING THAT CREATED THIS ITEM

The queue said B7 step 3 was next and ruling #95 said it "is what makes turning
the flag on possible". **It is not, on its own** — and the check that shows it is
one line of the shipped code:

```
SPENDABLE_BUCKETS = ['paid']          # billing-balance.ts, B8 step 1
bucket: 'paid'                        # billing-charge.ts, B6
```

Grant $10 of `promo` to 197 practices, turn `BILLING_ENFORCED` on, and ruling
94(a) refuses **every one of them** under `credit_not_spendable` instead of
`insufficient_balance`. **The reason string changes. The total clinical outage
does not.**

⚠️ **EVERY STEP THAT PRODUCED THIS WAS INDIVIDUALLY RIGHT.** B6 hard-coded
`'paid'` and said B7 owned the split. B7's three steps did not take it. B8 step 1
read the literal correctly and concluded — correctly — that admission must judge
`paid` alone, because admitting on the total would have been a fail-open. The
defect is in the JOIN, and it is invisible from inside any one of them.

**It was found by reading the item's premise against the code before building
it**, which is the watched-set discipline pointed at a queue entry rather than at
a gate: *what does this item CLAIM, and is the claim true of the system as it
stands?*

### WHY THIS HALF GOES FIRST — REVERSIBILITY DECIDES THE ORDER

| | this half | B7 step 3 |
|---|---|---|
| what it is | one constant + a loop | **197 rows** into an append-only table |
| in effect today | no — `BILLING_ENFORCED` is OFF | permanently, the moment it commits |
| reversal | revert `DRAW_ORDER` | **impossible** — only offsettable by `adjustment` rows that live beside them forever |

So the reversible half lands first and the irreversible half lands only once its
premise is true. **This is not a re-scoping of B7 step 3** — its scope is
unchanged. It gained a prerequisite that was previously unnamed.

⚠️ **AND IT IS NOT A CONTRADICTION OF RULING 94(a), IT IS THE PATH 94(a) WROTE
DOWN.** That ruling's own reversal clause reads: *"the honest version of that
reversal teaches the WRITER to draw promo first, at which point the gate's
cross-file arm forces both to move together."* Executed exactly there.

### WHAT LANDED

| file | what |
|---|---|
| `packages/ai/src/billing-buckets.ts` | **NEW.** `DRAW_ORDER` (the single fact), `SPENDABLE_BUCKETS` derived from it, and the pure `splitCharge` |
| `packages/ai/src/billing-charge.ts` | the writer iterates `DRAW_ORDER` inside a transaction, under `ledger_entries_derive()`'s own advisory lock key; `visitChargeKey` is now per (visit, bucket); `CommitResult` gained a `reason` discriminator |
| `packages/ai/src/billing-balance.ts` | consumes the shared constant; `readPracticeBalance` takes an optional client so the debit reads inside its transaction |
| `packages/ai/src/billing-pipeline.ts` | `ledgerEntryIds` plural; `balance_unreadable` reports as `failed`, not `declined` |
| `packages/ai/src/__tests__/gate-b7s3a-promo-draw-order.test.ts` | **NEW.** 20 arms |

### THE HAND-KEPT MIRROR IS DELETED, NOT RE-POINTED

94(a) could only assert the cross-file agreement with a regex, because `'paid'`
was a literal in another file. It is now an identity: the writer iterates
`DRAW_ORDER` and `SPENDABLE_BUCKETS` is derived from it. The gate asserts the
**stronger** property in its place — `billing-charge.ts` contains **no `bucket:`
literal at all** — with a positive control proving the matcher can still find one
in a canary. AGENTS.md: put the behaviour where it cannot be forgotten.

### MUTATION-PROVED — SIX, EACH DECLARED BEFORE IT RAN

| | mutation | declared | observed |
|---|---|---|---|
| M1 | `DRAW_ORDER` reversed to `['paid','promo']` | promo-first, overrun and inertness arms red | **6 red** |
| M2 | `splitCharge` caps the last bucket, dropping the overrun | conservation + overrun red | **3 red** |
| M3 | advisory-lock loop deleted | the three lock arms red | **3 red** |
| M4 | `SPENDABLE_BUCKETS` pinned back to `['paid']` | identity + behavioural admit arms red | **6 red**, across all three gates incl. the end-to-end pipeline arm |
| M5 | lock key drops the bucket (`practiceId` alone) | the lock-KEY arm red | **1 red** |
| M6 | unreadable balance falls back to all-on-`paid` | the refusal arm red | **1 red** |

⚠️ **AND THE MUTATION TOWARD *SUCCESS* WAS OBSERVED TOO, NOT ONLY TOWARD
FAILURE.** AGENTS.md requires proving a ratchet MOVES when the fix lands. It did,
live: the change reddened **4** existing arms, and each was flipped deliberately
and went green. A gate that could not have gone red before the change would have
been a decoration.

### ⚠️ TWO VACUOUS ASSERTIONS FOUND IN THE EXISTING GATES — NEITHER WAS IN THE FAILURE LIST

Both were **green** while measuring nothing. Neither would ever have surfaced.

1. **`gate-b6`'s `balanceAfter`/`seq` arm sliced on `prisma.ledgerEntry.create`.**
   This change moved the write to `tx.ledgerEntry.create`, so `indexOf` returned
   `-1`, **`slice(-1)` returned the file's last character**, and both
   `not.toMatch` assertions passed against a one-character string. Fixed by
   asserting the anchor **before** the slice.

2. **`gate-b8-balance`'s `read()` fixture hardcoded `spendableMicroUsd: paid`.**
   True when `paid` was the only spendable bucket; a lie afterwards. Every arm in
   that describe block was asserting the OLD behaviour against an input
   `readPracticeBalance` can no longer produce. Fixed by deriving it from
   `SPENDABLE_BUCKETS`.

**A fixture that states a derived field by hand is a second implementation of
the thing under test, and it does not get updated when the first one changes.**

### WHAT THIS STEP DOES **NOT** CLAIM

- **Nothing is billed, and nothing can be.** `BILLING_ENFORCED` is OFF and
  `ledger_entries` holds **0 rows** in both environments.
- **The split has never executed against a real ledger, in any environment.**
  `commitVisitCharge` refuses off production (F4, ruling 90(c)); with 0 rows
  everywhere, the split degenerates to the single `paid` row B6 already wrote.
  What is proven is the arithmetic, the ordering and the wiring.
- **The QA behavioural proof of B8 is still owed** — unchanged from B8 step 2,
  and still a precondition of turning the flag on.
- **B7 step 3 is still the grant, unchanged in scope.** It is now unblocked
  rather than merely unparked.

### ⚠️ THE B9 COLUMN QUESTION, ASKED BEFORE THE ZERO-ROW BUDGET IS SPENT

B8 step 2's ledger row required that anything B9 wants on `ledger_entries` be
argued for **before** the grant ends the zero-row state. Asked and answered here,
because this is the last item before that happens:

**No new column is needed.** B9 reconciles our ledger against the vendors'
invoices, and every input already exists — `pricing` carries the rate ids and the
per-component costs for `usage`; `note` carries the Stripe session and event ids
for `topup`; `practiceIdSnapshot` survives a practice deletion; `seq` orders the
ledger. The one thing this item ADDED to the JSON is `pricing.draw`
(`bucket`, `amountMicroUsd`, `ofBuckets`), so a split visit's rows can be summed
back to one charge without double-counting `components` — and it went into the
existing `Json` column, spending none of the budget.

⚠️ **`pricing` IS `Json?` AND THAT IS WHAT MAKES THIS CHEAP.** A future B9 field
that fits inside it costs nothing at any row count. Only a genuinely new COLUMN
is gated by the zero-row state, and none is proposed.


---

## 🟩 B7 STEP 3a IS LIVE IN PRODUCTION — `d2702a9c`, 2026-08-12T09:26Z

| | |
|---|---|
| deployed commit | `d2702a9ce5bfb805b92b0bd64e629838dc52b416` |
| declaration | `docs/foundation/deploys/20260812-d2702a9c.md` — **written 08:35Z, 45 minutes BEFORE the deploy ran** |
| deploy log | `docs/deploy-logs/deploy-20260812T092055Z.log` |
| rollback tag | **`:pre-b7s3a-20260812`** — app `135784a005d7` / worker `c72c02e027a9`, **cut BEFORE `deploy-prod.sh` ran**, verified by id match against the running containers |
| app image | `135784a005d7` → **`906ce01500ca`** |
| worker image | `c72c02e027a9` → **`af65d5c9d562`** |
| migration | **none** — 100 → 100, asserted by the deploy itself |

### Citation — produced by `check-citation.sh`, not typed

**Citation — 4 of 4 on `d2702a9ce5bfb805b92b0bd64e629838dc52b416`:**
   · `CI` 31579224269 a1
   · `e2e` 31579224256 a1
   · `a11y-ci` 31579224239 a1
   · `secrets-scan` 31579224287 a1

All `a1` — no re-runs on the PR head or the merge commit, so there is nothing to
explain. The PR head (`8b7f41a5`) was also 4 of 4 first time.

### THE DECLARATION, JUDGED — 21 of 21, EVERY ONE AS DECLARED

**What must change**

| # | declared | measured | |
|---|---|---|---|
| 1 | app image moves from `135784a005d7` | `906ce01500ca` | ✓ |
| 2 | worker image moves from `c72c02e027a9` | `af65d5c9d562` | ✓ |

**What must NOT change**

| # | declared | measured | |
|---|---|---|---|
| 3 | `_prisma_migrations` 100 | 100 | ✓ |
| 4 | **`ledger_entries` 0** | **0** | ✓ |
| 5 | `transcribe_visits` 25 | 25 | ✓ |
| 6 | … signed 17 | 17 | ✓ |
| 7 | … `FAILED` 0 — the flag-leak canary | 0 | ✓ |
| 8 | `transcribe_md_patients` 16 | 16 | ✓ |
| 9 | `api_usage_events` 1325 | 1325 | ✓ |
| 10 | `ai_calls` 1126 | 1126 | ✓ |
| 11 | `users` 196 | 196 | ✓ |
| 12 | `practices` 197 | 197 | ✓ |
| 13 | `price_rates` 44 | 44 | ✓ |
| 14 | `audit_logs` `CHECKOUT_%` 0 | 0 | ✓ |
| 15 | `audit_logs` `BILLING_%` 0 | 0 | ✓ |
| 16 | webhook 503 | 503 | ✓ |
| 17 | checkout 401 | 401 | ✓ |
| 18 | containers 9 of 9 | 9 of 9 | ✓ |
| 19 | co-tenants `307/404/200/200/410` | `307/404/200/200/410` | ✓ |
| 20 | `BILLING_ENFORCED` unset in the LIVE containers | **unset in both** (`printenv` exit 1) | ✓ |
| 21 | QA `ledger_entries` 0 | 0 | ✓ |

**Nothing moved that was not declared.** `audit_logs` was deliberately not
declared as a total (ordinary traffic writes it); rows 14–15 are its falsifiable
form and both held.

### WHAT IS LIVE, AND WHAT IS NOT

**Live:** `commitVisitCharge` now opens a transaction, takes
`ledger_entries_derive()`'s own advisory lock per bucket in `DRAW_ORDER`, reads
the wallet through the same reader admission uses, and appends one `usage` row
per bucket drawn. `SPENDABLE_BUCKETS` is `{paid, promo}`, derived.

**NOT live:** any of it, in effect. `BILLING_ENFORCED` is OFF, so neither seam
executes — and **even with the flag on, this code writes the row B6 wrote**,
because every wallet is `{0, 0}` and the split degenerates to a single `paid`
draw. Row 4 and row 21 are the assertions that carry that claim.

### ⚠️ ONE OPERATIONAL PROPERTY THIS CHANGE INTRODUCES — NAMED, NOT TUNED

`commitVisitCharge` is now an **interactive Prisma transaction**, and Prisma's
default `timeout` for one is **5s**. A charge that waits on a contended
per-(practice, bucket) advisory lock longer than that aborts; `chargeVisitUsage`
absorbs the throw and reports `charged: 'failed'`, loudly. **No clinical
outcome is affected** — the debit never throws upward, by ruling 95(e).

It is **not tuned**, deliberately. Raising the timeout holds locks longer, and
the honest input is a contention distribution nobody has: 193 of 196 users are
alone in their practice, so same-practice concurrency is close to hypothetical
today. Inventing a number from that would be indistinguishable, later, from a
measured one — the same argument ruling 94(d) made for not estimating a
per-visit cost. **It arrives when B9 gives a real month**, and it is written down
here so the day a `charged: 'failed'` cluster appears, this is the first thing to
check rather than the last.

### WHAT IS OWED, UNCHANGED

- **The QA behavioural proof of B8.** Still not discharged. ⚠️ It is now
  BROADER than B8 step 2 left it: my change makes a promo-funded wallet ADMIT,
  so the proof should walk both directions. **The refusal half needs no ledger
  rows** — an empty QA wallet is its natural state, which is why RELAY calls it
  cheap. The admit half WOULD need a `grant` row on QA, which ends that stack's
  zero-row state; that is a decision, not a detail.
  Prep done this session: the QA worker's `environment:` block is **hardcoded**
  (no `${VAR:-}`), so `BILLING_ENFORCED` needs an overlay file, and `e2e.yml`
  already demonstrates the recreate pattern.
- **The debit's success path has never executed, in any environment.**
- **B7 step 3** — the grant. Now genuinely unblocked rather than merely unparked.
- **B8 step 3** — the failure path's charge, inseparable from the auto-credit.

