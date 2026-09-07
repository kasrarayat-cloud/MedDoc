# POSTGRES HAS NO NESTED TRANSACTIONS — A FIXTURE'S `COMMIT` ENDS THE OUTER ONE

**Standing 2026-09-07, from a defect introduced while fixing its siblings.**

## THE REFERENCE CASE

A SQL proof file is one transaction: `BEGIN;` at the top, `ROLLBACK;` at the
bottom, so it leaves the database exactly as it found it. That property is
load-bearing — in CI it runs against the database the seed and the whole E2E
suite then use.

A new fixture needed the triggers disarmed while it was seeded, so it was
written as what looks like a scoped block:

```sql
BEGIN;
SET LOCAL session_replication_role = 'replica';
INSERT INTO practices …;
INSERT INTO users …;
COMMIT;
```

**That `COMMIT` does not close an inner block. It ENDS THE OUTER TRANSACTION** —
committing every fixture row written above it, permanently, and leaving the rest
of the file running outside any transaction at all. The closing `ROLLBACK` then
has nothing to roll back and warns rather than fails.

The rows were still there afterwards. Measured, and cleaned by hand.

⚠️ **AND THE AUTHOR HAD JUST WRITTEN THE FIX FOR THE SAME CLASS**, one file over:
the round that produced this repair had itself reported *"the race step leaves
fixture rows and two scratch tables in the database the seed and the whole E2E
suite then use."* **Reading a finding is not being immune to it.**

## WHY IT READS AS SAFE

`BEGIN … COMMIT` is the universal shape for "a scoped unit of work", and every
other language's nesting intuition says an inner block closes an inner scope.
Postgres has **SAVEPOINT**s, not nested transactions: a second `BEGIN` inside an
open transaction emits only

    WARNING:  there is already a transaction in progress

— a warning, on stderr, in a file that prints hundreds of lines.

> **The construct is not rejected, it is not an error, and the only signal is a
> warning that scrolls past.**

## THE RULE

Inside a file that owns its own transaction:

- **Never write `BEGIN` or `COMMIT`.** Use `SAVEPOINT` / `ROLLBACK TO SAVEPOINT`
  if you need a scoped undo, or a plpgsql `BEGIN … EXCEPTION` block.
- **Use `SET LOCAL`, never `SET`**, for anything that must revert —
  `session_replication_role`, `search_path`, `statement_timeout`. `SET LOCAL` is
  transaction-scoped and reverts with the rollback; plain `SET` outlives it.
- ⚠️ **Re-arm immediately after a disarm.** A `session_replication_role =
  'replica'` left in place does not fail anything — it makes every arm below it
  measure a database with the triggers switched off, which is a green that
  proves the opposite of what it claims.

## THE ASSERTION THAT CATCHES IT

Do not trust the `ROLLBACK`. Ask afterwards, from outside:

```sql
SELECT count(*) FROM users WHERE id LIKE '<fixture-prefix>%';   -- must be 0
SELECT current_setting('session_replication_role');             -- must be 'origin'
```

**A proof that cleans up is a claim; a proof that checks it cleaned up is
evidence.**
