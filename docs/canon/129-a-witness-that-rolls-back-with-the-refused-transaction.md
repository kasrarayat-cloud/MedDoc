# A WITNESS THAT ROLLS BACK WITH THE REFUSED TRANSACTION CANNOT WITNESS THE REFUSAL

**Standing 2026-09-07, from the cell a ruling's headline claim rested on.**

## THE REFERENCE CASE

Ruling #220 kept an advisory lock **because it was proven load-bearing**:
*8–12 of 12 violations without it, 0 of 12 with it.* The 0-of-12 cell is the
whole claim.

A later round asked the obvious question — *did those runs actually race?* — and
the harness had an answer built in: an overlap witness, recorded by each racer
into a `t210_window` table with a start and end timestamp, overlap computed from
the endpoints.

**With the lock, the witness reported 0 of 12 overlapped.**

Not "we could not tell". Zero. The cell that proves the lock works was measured
on twelve runs in which, by its own witness, the two transactions never met.

## WHY, AND IT IS STRUCTURAL

Each racer wrote its witness row **inside its own transaction**.

When the lock does its job, the guard **REFUSES** the second racer — and that
transaction rolls back. Its `INSERT INTO t210_window` rolls back with it. The
overlap test required `count(*) = 2`; one row was gone, so the answer was always
`no overlap`.

> **The witness disappeared for exactly the reason the arm was supposed to
> succeed.** It could not have reported an overlap on that arm under any
> circumstances — including the ones where the overlap certainly happened.

⚠️ **AND THE ARM STILL WENT GREEN**, because the verdict read only the violation
count and never read `OW` at all: the number was computed, printed, and never
compared to anything. Two independent failures pointing the same way — a witness
that could not speak, and a verdict that was not listening.

## THE RULE

**A witness must survive the outcome it witnesses.** If the thing being observed
can abort, the observation cannot live inside it.

- Sample from a **third connection** — `pg_stat_activity`, filtered by
  `application_name`, is the cheap form and needs no cooperation from the racers
  beyond setting a name.
- Or write the observation somewhere a rollback cannot reach.
- **Never** record the evidence in the transaction whose failure is the
  interesting case.

⚠️ **THE TELL IS AN ASYMMETRY NOBODY EXPLAINS.** One arm overlapped 10 of 12 and
the other 0 of 12, and the difference was treated as a property of the lock. It
was a property of the instrument. **When a witness reports a clean zero on
exactly the arm where the guard fires, suspect the witness before the guard.**

After the repair — the same third-connection sampler the *other* race in the
same file already used, which this one had never been wired to — both arms
overlap 12 of 12, and #220's claim is supported by evidence rather than by
silence.
