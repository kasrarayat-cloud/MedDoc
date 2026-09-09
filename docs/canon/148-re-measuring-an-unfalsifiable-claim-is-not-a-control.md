# RE-MEASURING AN UNFALSIFIABLE CLAIM IS NOT A CONTROL

**Standing 2026-09-08, from a probe that ruling #260 had ratified BY NAME for
doing the very thing it turned out not to do.**

This programme already knows that *a documented fact nobody re-measures is the
next stale comment*, and it acts on it: probes are written to re-derive their
facts on every run rather than to quote them. **That discipline is necessary and
it is not sufficient.** A re-derivation whose answer is fixed in advance is a
ceremony, and it is a more expensive failure than the stale comment it replaced —
because the comment was merely unverified, while the probe reports a
verification that did not happen.

> **A control must be able to produce the answer nobody wants. If you cannot
> name the input that makes it say NO, it is not measuring anything.**

---

## THE REFERENCE CASE

`admin5-last-owner-trigger-race.sh` documented a fact about Postgres — *a
savepoint rollback releases an advisory `xact` lock* — and, correctly, refused to
believe its own comment. It ran a probe on every invocation:

```sql
BEGIN;
SAVEPOINT s1;
SELECT pg_advisory_xact_lock(424242, 1);
ROLLBACK TO SAVEPOINT s1;
SELECT count(*) FROM pg_locks WHERE ... classid=424242;   -- expect 0
ROLLBACK;
```

The count is `0` and the harness prints *"a savepoint rollback RELEASES the
advisory lock (0 held) — as documented above."*

⚠️ **`0` IS ALSO WHAT AN UNHELD LOCK READS.** A mistyped classid, a renamed
function, a lock call that quietly did nothing — every one of them produces the
same `0`, and the probe reports the documented conclusion. It could not
distinguish *"the savepoint released it"* from *"there was nothing to release"*.

**MEASURED, against a real database, by taking the lock on the wrong classid so
`424242` is never held:**

| probe | verdict |
|---|---|
| the shipped shape | 🟢 *"a savepoint rollback RELEASES the advisory lock (0 held) — as documented above"* |
| with a BEFORE reading | 🔴 *"the advisory lock was never observed HELD (BEFORE read `0`, expected 1)"* |

The first line is a green produced by a run in which the subject of the
measurement was absent.

---

## THE SHAPE OF THE FIX, AND IT GENERALISES

**Measure a TRANSITION, not an end state.** The probe now reads the count
**before and after**, and `before` must read `1` or it refuses *without any
opinion about savepoints at all* — it has not observed the thing whose release it
was about to time.

That ordering is the point. The positive control comes **first** and its failure
is terminal, because every reading after it is meaningless if the subject was
never there.

> **THE TEST FOR ANY PROBE: name the input that makes it say NO. If the only
> answer is "if the universe changed", it is asserting, not measuring.**

⚠️ **AND THIS IS THE `pg_locks` FAMILY SPECIFICALLY.** Any assertion of the form
*"after X, the count is 0"* has this defect by construction, because absence is
the default state of nearly everything. `0` is what you read before you start,
what you read if you looked in the wrong place, and what you read if the thing
you are counting was never created. A count that is expected to fall must be
watched falling.

---

## WHAT IT DOES **NOT** SAY

It does not say the conclusion was wrong. **A savepoint rollback does release an
advisory `xact` lock**, and the harness's race results were never affected — the
probe's job was to notice if that ever changed, and the fix is that it now can.

⚠️ **The correction is to the INSTRUMENT, and the conclusion survives it.** That
is the same distinction #260 drew about the comment one layer up: *"the
conclusion survived and the reason didn't."* Here the conclusion survived and the
**verification** didn't, which is the next costume the same failure wears.

---

## RELATED

- **A CONTROL CAN PASS VACUOUSLY** — the general family. This is its
  absence-shaped member.
- **#260** — *the savepoint fact is re-measured on every run*. Ratified for a
  property this probe had in form and not in substance.
- **#252** — *the witness is autonomous*; and the earlier finding that a witness
  measuring the starting gun can never say NO. Same defect, different instrument.
