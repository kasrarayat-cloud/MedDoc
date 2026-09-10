# ⚠️ HISTORICAL EVIDENCE — THE SHIPPED MECHANISM IS THE TRIGGER PLUS THE ADVISORY LOCK

**Added to `main` on 2026-09-10 by the ADMIN-5 branch `feat/admin5-demotion-on-trigger`,
verbatim from PR #1026 (commit `923a84e1`), because ruling #200 cites this path
(`rulings/2026-09-06-199-200.md`, "THE CONDITIONS ON MERGING") and the file did not
exist on `main` — a standing ruling pointed at a missing file.**

**What shipped is NOT the shape measured below.** Ruling #210 moved the enforcement
into the database, and the ADMIN-5 design fixed under #310(a) ("one predicate per
rule") keeps exactly ONE enforcer:

- **`users_last_owner_guard`** — a constraint trigger (`AFTER UPDATE OR DELETE ON
  "users"`, `DEFERRABLE INITIALLY IMMEDIATE`), migration
  `20260907040000_admin5_last_owner_trigger`. It takes
  `pg_advisory_xact_lock(hashtext('users_last_owner_guard'), hashtext(practiceId))`
  and `FOR UPDATE` on the practice's other user rows before it counts, and refuses
  above READ COMMITTED (#269).
- **`withPracticeLock`** (ruling #268) takes the same advisory key BEFORE the write
  at every application door, so the trigger's acquisition is a re-entry, not a
  second lock.
- The application's `wouldStrandPractice` / `classifyGuardError`
  (`apps/transcribe-md/src/lib/last-owner-invariant.ts`) are the FRIENDLY REFUSAL.
  They enforce nothing.

PR #1026's `practices … FOR UPDATE` row lock, its SQL guard (`LAST_OWNER_CLAUSE`)
and its second copy of the owner predicate were **not** ported (#221, #310(a)).
The probe matrix below is kept because ruling #200 rests on it: it is what measured
both of the ADMIN-5 row's named shapes — a partial unique index and a SERIALIZABLE
transaction — as defective for a MINIMUM invariant. **PART TWO drives #1026's SQL,
which does not exist on `main`; those rows describe that branch, not what shipped.**

**The shipped mechanism's own proofs**, and this branch's results on a scratch
`pgvector/pgvector:pg16` carrying every repo migration (2026-09-10):

| proof | result |
|---|---|
| `packages/db/prisma/proofs/admin5-last-owner-trigger-arms.sql` | 45 / 45 arms |
| `packages/db/prisma/proofs/admin5-last-owner-trigger-race.sh` | PASSED — raceA refused once with overlap witnessed; raceB 11/12 violations without the lock, 0/12 with it; order arm 20/40 |
| `apps/transcribe-md/src/lib/__tests__/admin5-db-proofs.db.test.ts` | 16 / 16 — #212's four worlds through the real suspend route, the panel-door races, transfer, delete-account |

---

# ADMIN-5 — THE LAST-OWNER GUARD, MEASURED BEFORE IT WAS BUILT

**Design/Admin lane, 2026-09-06.** Every table below is a two-session
interleaving run against a throwaway `pgvector/pgvector:pg16` container — the
same image family the `test` job declares — driving the exact shape ruling #195
names: two owners, each demoted by a different actor, each having read `count=2`.

⚠️ **THE PROBES ARE THE ARGUMENT, NOT THE REASONING.** This lane asserted a
mechanism out loud twice today and was wrong twice; both corrections are kept
below, because the correction is the point.

## 1 · THE RULED INTERLEAVING IS REAL, AND THE CONTROL FIRES

| isolation | A reads | B reads | outcome | owners left |
|---|---|---|---|---|
| READ COMMITTED | 2 | 2 | both commit | **0** |
| SERIALIZABLE | 2 | 2 | B aborts, SQLSTATE 40001 | **1** |

B's abort, verbatim:

    ERROR:  could not serialize access due to read/write dependencies among transactions
    DETAIL:  Reason code: Canceled on identification as a pivot, during commit attempt.

⚠️ **THE READ COMMITTED ROW IS THE POSITIVE CONTROL AND IT IS NOT OPTIONAL.**
A SERIALIZABLE arm that goes green proves nothing unless the same probe can be
shown to produce the WRONG answer when the mechanism is removed. It does: zero
owners, nobody able to administer the practice — the state #195 predicted in
words.

## 2 · SERIALIZABLE FALSELY ABORTS ACROSS UNRELATED PRACTICES

Two demotions in **different** practices — two admin actions with nothing to do
with each other:

| filler rows | index pages | heap pages | `SIReadLock` granularity | cross-practice B |
|---|---|---|---|---|
| 200 (≈ production: 199 practices, ~200 users) | 2 | 2 | **RELATION on `users`** | **falsely aborted** |
| 200,000 | 180 | 1,274 | **page** on the index + **tuple** on the heap | **falsely aborted** |

⚠️ **TWO EXPLANATIONS WERE OFFERED AND BOTH WERE WRONG.** This lane first said
"page granularity over a one-page index, it resolves as the table grows"; a peer
lane proposed the opposite, "a relation lock that never resolves". Measured, the
lock IS relation-level at today's scale (the peer's reading) and it DOES refine
with scale (this lane's reading) — **and the false abort survives both.**

The mechanism that actually holds: the supporting index is on
`(practiceId, practiceRole)`, so `('PA','OWNER')` and `('PB','OWNER')` are
**adjacent keys on the same leaf page** even in a 180-page index, and the other
transaction's UPDATE dirties that page.

**So the false-conflict rate is a function of where two practice ids happen to
sort next to each other, at any scale.** That is worse than either clean answer:
not a defect that grows out, not a constant tax, but a data-dependent one that
reaches production as an unreproducible intermittent.

## 3 · THE ROW LOCK DOES NOT RESCUE SERIALIZABLE

`BEGIN ISOLATION LEVEL SERIALIZABLE` + `SELECT … FROM practices WHERE id=? FOR UPDATE`
+ the conditional UPDATE:

| arm | result |
|---|---|
| same practice | 1 owner left — but B aborts **40001**, not a clean refusal |
| different practices | **still falsely aborted** |

## 4 · WHAT WAS CHOSEN, AND WHY — THE FULL MATRIX

| shape | same-practice race | cross-practice race | what the doctor is told |
|---|---|---|---|
| READ COMMITTED, no guard | **0 owners** | — | success, falsely |
| SERIALIZABLE alone | 1 owner, B aborts 40001 | **falsely aborts** | "retry" |
| SERIALIZABLE + `FOR UPDATE` | 1 owner, B aborts 40001 | **still falsely aborts** | "retry" |
| **READ COMMITTED + `FOR UPDATE` + the count inside the UPDATE's `WHERE`** | **1 owner, B refused cleanly** | **no interference** | "cannot demote the last owner" |

⚠️ **THE LAST COLUMN IS NOT A UX NICETY.** Under SERIALIZABLE the last-owner
refusal *arrives as a serialization failure*, so the only honest message on the
first attempt is "try again" — the doctor learns the real reason only on the
retry. The conditional UPDATE returns `UPDATE 0` immediately and can say the
true thing the first time.

### The complete guard, proved against its negative control

| mode | owners left |
|---|---|
| **unguarded** (plain UPDATE, same timing) | **0** |
| **guarded** (`FOR UPDATE` + the conditional UPDATE) | **1** |

and in the `same`-practice arm the second actor's read returns **1, not 2** —
the lock is what makes the read authoritative, which is the whole property.
**There is no application arithmetic anywhere: the count lives inside the
UPDATE's own `WHERE`, and `count === 0` from `updateMany` IS the refusal.**

## 5 · ⚠️ THE SHAPE IS A THIRD ONE, AND THAT IS SURFACED, NOT DECIDED QUIETLY

The ADMIN-5 row rules the guard's shape: *"a PARTIAL UNIQUE INDEX or a
SERIALIZABLE transaction. NEVER a count read and then acted on."*

**The prohibition is honoured exactly** — nothing here reads a count and then
acts on it.

**The permission's first option is inexpressible.** A partial unique index
bounds a **maximum**; the invariant is a **minimum**. Applied naively it would
enforce one-owner-per-practice — precisely the exclusivity ruling #195
overturned. ⚠️ **Reached independently by two sessions on the same afternoon,
by the same route, before either had seen the other's message** — which is why
it is recorded as a correction to the row rather than as either lane's finding.

**The permission's second option is implementable and measurably worse**, for
the reasons in §2–§4.

So a third shape is built, and the question *"does the row's option set stand?"*
goes to the owner with this matrix attached. **A ruling whose option set is
defective should be corrected, not routed around in silence.**

## 6 · THE LOCK'S REAL WEAKNESS, NAMED BY THE PEER LANE AND BUILT AGAINST

> *"A pessimistic lock is only as good as its least disciplined writer, and that
> is a property nothing in the type system enforces."*

Correct. One refinement from reading the writers: seat redemption
(`signup-invite.ts` → `actions/auth.ts`) can only ADD a member or set a role on
a new one, so it can only RAISE the owner count and cannot break "≥ 1". The
obligation is therefore narrower than *"every `practiceRole` writer"* and, being
narrower, is actually enforceable:

> **Any writer that can move a user OUT of `OWNER` must take the lock.**

Pinned by a ratchet arm in the shape this repository already uses for
`MAX_UNSCOPED_REQUEST_READS = 0`, so a new demoting writer **reds** instead of
silently bypassing the guard.

---

# PART TWO — THE SAME PROOF, ON THE REAL SCHEMA, WITH THE SHIPPED SQL

**Everything above ran against a throwaway container with a hand-written
two-column table.** That is enough to choose a shape and not enough to ship one:
it proves a mechanism, not this system's mechanism. Part two re-runs the
decisive arms against the **isolated `meddoc-qa` stack** — the real `users` and
`practices` tables, the real `PracticeRole` enum, the real
`users_active_member_has_practice_role` CHECK — driving the **exact statements
the server runs**, imported from `src/lib/practice-owner-guard-sql.ts` rather
than retyped.

⚠️ **THE SQL IS SHARED DATA FOR THIS REASON AND NO OTHER.** A proof that retypes
the statement it is checking proves the author can type the same thing twice. It
goes green against a guard that was never shipped, and — worse — it **stays**
green when the shipped guard changes. `PREPARE` accepts the same `$1/$2/$3`
placeholders the server binds, which is why the parameters are positional.

## THE NEGATIVE CONTROL FIRES ON THE REAL SCHEMA

| arm | session A | session B | owners left |
|---|---|---|---|
| **unguarded, same timing** | `UPDATE 1` | `UPDATE 1` | **0** |

Both actors read `count = 2`, both concluded another owner remained, both wrote.
**The practice was left with nobody able to administer it** — ruling #195's
interleaving, reproduced on production's schema rather than argued from it.

⚠️ **WITHOUT THIS ROW EVERY ROW BELOW IS VACUOUS.** A guarded arm that goes green
is consistent with two sessions that never actually overlapped. The control is
what establishes that they did.

## THE GUARD HOLDS — ALL THREE DOORS, AND THE CROSS-DOOR RACE

| arm | A | B | owners left |
|---|---|---|---|
| demote ∥ demote | `UPDATE 1` | `UPDATE 0` | **1** |
| **remove ∥ remove** | `UPDATE 1` | `UPDATE 0` | **1** |
| **demote ∥ REMOVE** | `UPDATE 1` | `UPDATE 0` | **1** |
| serialization failures, all arms | — | — | **0** |

⚠️ **THE THIRD ROW IS THE ONE A PER-DOOR GUARD PASSES AND A CORRECT ONE EARNS.**
Demotion and removal are two doors to ONE invariant. A build that guards each
door against *itself* still loses the practice when the two race each other: A
demotes owner-1 while B removes owner-2, each sees the other as proof that an
owner remains, and the practice ends with none. It holds here structurally
rather than luckily — **both doors take the same `practices` row lock, so they
cannot overlap at all**, which is exactly why the lock is on the practice and
not on the user rows.

⚠️ **AND THE ZERO IN THE LAST ROW IS A PRODUCT DECISION, NOT A DETAIL.** The
loser gets `UPDATE 0` — a clean refusal — so the doctor is told *"this is the
last owner, make someone else an owner first"* on the **first** attempt. Under
SERIALIZABLE the same refusal arrives as a serialization failure, and the only
honest first message is *"try again"*.

## THE GUARD IS NOT A WALL

Sequentially, with two owners, the first demotion **succeeds** (`UPDATE 1`,
owners 2 → 1) and only the last one is refused (`UPDATE 0`, owners stay 1). An
arm for this is in the spec because a guard that refuses everything passes every
race test ever written.

## ⚠️ A FOURTH SHAPE, CONTRIBUTED BY THE PEER LANE, RECORDED NOT TAKEN

A composite FK — `practices(ownerUserId, ownerRole, ownerPracticeId)` →
`users(id, practiceRole, practiceId)`, `ON UPDATE RESTRICT ON DELETE RESTRICT`,
plus `CHECK (ownerRole = 'OWNER')` — measured by that lane at READ COMMITTED
across 9 runs: one side always errors `23503`, owners ≥ 1 in all 9.

**Its engineering advantage is real and survives even if the shape is
declined:** `23503` is translated by the Prisma pg adapter to a typed
`P2003`, whereas a CHECK violation (`23514`) falls to the adapter's default arm
with no dedicated code.

⚠️ **IT IS NOT PROPOSED, BECAUSE IT IS A DIFFERENT INVARIANT.** It enforces
*"this practice has a DESIGNATED owner who is an active OWNER of it"* — strictly
stronger than *"at least one owner"* — and needs a NOT NULL column on
`practices` plus a backfill that **chooses** which existing owner is designated.
Choosing is a product decision. It belongs in the owner's matrix as an option,
not in this PR as a recommendation.

## ⚠️ AND ONE MEASURED FACT THAT REMOVES A TRAP FROM THE SERIALIZABLE ROUTE

The peer lane measured that ADMIN-5's race is **write skew across different
rows**, detected at `PreCommit_CheckForSerializationFailure`, and that this
**bypasses Prisma's error translation**: a bare `DriverAdapterError` with
`code === undefined`, for which `err instanceof Prisma.PrismaClientKnownRequestError`
is **false**. The sign route's hardened `P2034` predicate, run verbatim over
those failures, classified **14 of 14 as false**.

**So a session that chose SERIALIZABLE and copied the existing retry predicate —
as ruling #187(a) directs — would ship a retry that never fires, silently, on
precisely the race the guard exists to prevent.**

⚠️ **STATED WITH ITS LIMITS, WHICH THAT LANE FLAGGED ITSELF:** the finding was
not re-run by its own synthesiser, and the translated/untranslated ratio was
unstable across two runs (2-of-12, then 0-of-14). **Treat the EXISTENCE of the
leak as measured and the ratio as noise.** It is recorded here because it does
not touch the shape that shipped — which needs no `40001` handling at all — and
because a future session revisiting SERIALIZABLE must meet it.

⚠️ **AND IT CONTRADICTS A COMMENT THAT IS ALREADY ON `main`:** `sign/route.ts`
asserts the translated behaviour as fact. Neither lane has resolved that, and it
is filed rather than fixed in passing.
