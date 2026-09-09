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
