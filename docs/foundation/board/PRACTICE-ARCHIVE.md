# BOARD FILING — PRACTICE-ARCHIVE (ADMIN-6), created by ruling #306

**Filed 2026-09-09 by the Design/Admin session. OWNER: Design/Admin.
SLOT: ADMIN lifecycle, after ADMIN-5 — it is the same guard's other half.**

## WHY THIS ROW EXISTS

**Not because somebody wanted a feature. Because a capability was narrowed and
the legitimate need under it had to go somewhere.**

`users_last_owner_guard` now refuses this sequence:

    1. suspend the only clinician   — legal, ordinary
    2. soft-delete the only owner   — legal, ordinary

It used to succeed, and left a practice with **no active owner** and a member
who could **never be restored**:

    users_no_orphan_member: refusing to place a live member in practice P,
    which has no active OWNER. Restore or appoint an owner first.

⚠️ **NEITHER REMEDY THAT SENTENCE NAMES EXISTS.** Verified in source:
`softDeletedAt` is written in exactly one place and **cleared nowhere**, so
there is no un-soft-delete door; and every `practiceRole` writer goes through
`requirePracticeAdmin`, which demands `practiceRole = 'OWNER'`, so an ownerless
practice can neither mint an invite nor change a role. That file names this
class **twice** as *"worse than no guard"* and then shipped it in its own
`RAISE`.

## THE DISTINCTION THE RULING TURNS ON

> **The old path reached the end state by ACCRETION** — one legal click at a
> time, with **no actor ever deciding "this practice is closing"**.

Winding a practice down is a real need. It is not, and should never have been, a
side effect of two unrelated administrative acts.

## THE SHAPE

**ONE declared act** that archives the practice **AND its members together**:

- **restorable** — ⚠️ **load-bearing.** An archive that cannot be undone is the
  same trap with a friendlier name.
- **audited** — on the deferred `PRACTICE_ARCHIVED` row, the one this was always
  going to need.
- **atomic over the practice and its members**, because archiving the practice
  while leaving members live is exactly the split state the guard refuses.

## WHAT IS ALREADY TRUE, SO THE BUILD DOES NOT RE-DERIVE IT

- The narrowing is **shipped and mutation-proven** (`#1036`): exemption 2 counts
  RESTORABLE members (`users_is_restorable_member` — not soft-deleted) rather
  than LIVE ones, in two halves that cancel — `trapped_left` (restorable
  non-owners, each locked out for good) and `rescuer_left` (restorable OWNERS,
  who can recover the practice because `users_no_orphan_member` short-circuits
  on `users_is_active_owner(NEW)`).
- Refusal is exactly `trapped_left > 0 AND rescuer_left = 0`. **Suspending a
  solo OWNER stays legal** — that owner is their own rescuer — and that has its
  own arm, because without it the narrowing would have cost a capability nobody
  agreed to lose.
- The app-side `wouldStrandPractice` moves with the trigger and carries its own
  sentence (`STRANDS_RESTORABLE_REFUSAL`), because `LAST_OWNER_REFUSAL` says
  *"transfer ownership to another member"* and here there is nobody who can
  receive it — the #256 lesson.

## THE ACCEPTANCE QUESTION FOR WHOEVER BUILDS IT

The archive must make the **currently unreachable** state reachable **and
reversible**: a practice with no live members, which can be brought back whole.
If the built door cannot restore a practice it archived, it has re-created the
defect it was filed to replace.

## ⚠️ PRIOR ART THIS FILING DID NOT CITE — FOUND BY THE NINE-ROW RECON

**Two standing rulings already cover this row, and both are unexecuted.**

**RULING #226** orders the exact act: *"the six test practices and their seven
inactive users are ARCHIVED — a ruled mutation with a committed declaration,
executed through the audited admin path, restorable: soft archive, never hard
delete."* **No declaration exists** — `docs/foundation/mutations/` ends at
`20260903-transfer-certification-to-active.md`. Its own *TWO MEASURED FACTS*
record why it has never run:

> *"NO ADMIN PATH WRITES A PRACTICE ROW … The admin API exposes users,
> audit-logs, usage, system, hipaa, threats — no practices. And there is no
> `PRACTICE_ARCHIVED` among the 156 `AuditAction` values."*

⚠️ **#226 IS BLOCKED ON EXACTLY THIS ROW'S SUBSTRATE.** So ADMIN-6 is not a new
capability with a fresh justification — it is the missing floor under a ruling
that has been standing since 2026-09-07. **A builder working this row discharges
#226 whether or not they know it**, which is precisely why it is cited here now.

**RULING #222** and `board/THE-SIX-ZERO-OWNER-PRACTICES.md` supply the
population: all six practices tabled by id, name, created date and member / live
/ visit counts — five QA signup shells minted 2026-05-03, one April test clinic
— plus the query that de-escalates them (*practices with a LIVE member and NO
able owner: **0***) and the shape to honour: **archive the PRACTICE and leave
the user rows to the ordinary path.** Arms 28–32 on PR #1036 already assert that
a zero-owner practice stays writable *precisely so this cleanup is possible*.

⚠️ **I FILED THIS ROW WITHOUT EITHER CITATION.** The recon found them; review did
not. The lesson is the one the ledger keeps re-teaching — **a capability filed as
new is a claim that nothing already covers it**, and that claim is checkable by
grep before the row is written.

## ⚠️ CORRECTIONS, 2026-09-10 — FOUND WHILE BUILDING THE ROW

**Appended, never rewritten.** The text above is kept as written, because the
corrections are the point.

**1 · #226 WAS EXECUTED. "No declaration exists" was a search of the wrong
directory.** The act ran on 2026-09-07 as a raw-SQL one-shot under ruling #230,
which put its declaration in `docs/deploy-declarations/` deliberately (a
non-sha filename in `docs/foundation/deploys/` blocks the next deploy):

| artifact | where | commit |
|---|---|---|
| declaration | `docs/deploy-declarations/20260907-r226-archive-six-test-practices.md` | `071b80ab`, 08:35:42Z |
| the one-shot | `scripts/execute-r226-archive.sql` | ran 08:36:52Z |
| judgement, **9 of 9** | `docs/deploy-reports/20260907-r226-archive-JUDGEMENT.md` | `fca86bb0`, 08:38:04Z |
| on `main` | PR #1041 | `ef21f059` |

The recon's "`docs/foundation/mutations/` ends at …" was true and answered the
wrong question. **A declaration can live in either directory; grep both.**

**What remains of #226 is only #230's deferral: the six `PRACTICE_ARCHIVED`
audit rows.** They are a separate ruled mutation that the lead runs. They are
not part of the ADMIN-6 build.

**2 · "ARCHIVING THE PRACTICE WHILE LEAVING MEMBERS LIVE IS EXACTLY THE SPLIT
STATE THE GUARD REFUSES" — WRONG.** `users_last_owner_guard` and
`users_no_orphan_member` read `users` columns only. Neither reads
`practices.isActive`, and there is no trigger on `practices` at all
(measured in the migrations). The guard refuses *live members with zero active
owners*, whatever the practice flag says. So an archive that writes only the
practice row trips nothing.

**3 · THE SHAPE THAT WAS BUILT IS DESIGN A: ONLY THE PRACTICE ROW IS WRITTEN.**
The branch is `feat/admin6-practice-archive`, not yet merged.

- **The members are archived in effect, not in their rows.** Three doors now
  read the flag through one predicate (`@meddoc/db/practice-admits`):
  - login;
  - every request (`validateSession`), which ends the session;
  - invite redemption.
- **The worker is deliberately not a door**, because it is on the clinical
  generation path. The act refuses while any visit is in flight instead.
- **No `users` row changes**, so neither trigger fires. A restore returns every
  member exactly as they were, including any earlier suspension or
  deactivation.
- **Proven on a real Postgres:** the md5 hash over every `users` row is
  identical before and after both the archive and the restore.

**Why this satisfies #306.** #306 says the act "archives the practice AND its
members together". Per #200, that binds the invariant, not the mechanism:

- no member of an archived practice can sign in, keep a session, or be invited
  in;
- one act brings them all back.

**The acceptance question above is answered yes.** An archived practice has no
live members, and it can be brought back whole.

**Design B would suspend every member instead.** It was rejected, because it
would need all of the following:

- a multi-row statement to get past the guard;
- a stored record of who was already suspended, so a restore could tell them
  apart;
- `withPracticeLock`;
- a new writer on #289's door list;
- a `forceLogoutAt` bump.

It would also leave the OWNER-invite hole open (T3 in the ADMIN-6 research). Design A has
none of these costs, and #222's own recommendation was *"archive the PRACTICE and
leave the user rows to the ordinary path."*
