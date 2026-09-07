# ASSERT A SQL MUTATION IN THE DATABASE, NOT IN THE FILE

**Standing 2026-09-07, from a control that went green over a revert that never
landed.**

## THE REFERENCE CASE

Ruling #238 added a missing `practiceId` comparison to a trigger function. To
show the new arm was load-bearing, the fix was reverted **in the file** and the
proof re-run. The expectation was one FAILING arm.

All 35 arms passed.

The revert was real — `git diff` showed it, and the file on disk carried the old
text. What had not happened was the **install**: re-running the migration failed
on

    ERROR:  trigger "users_last_owner_guard_after_write" for relation "users" already exists

`psql` reported it, the surrounding script did not stop on it, and the database
went on holding the **fixed** function while the file held the reverted one. The
proof then measured the fixed function and, correctly, passed.

> **A green control over an unapplied mutation is indistinguishable from a green
> control over a guard that works — and it is the same failure as a mutation
> proof that never applied, one layer further out.**

## WHAT CAUGHT IT

Not the exit code, and not the diff. A one-line assertion against `pg_proc`:

```sql
SELECT position('NEW."practiceId" = OLD."practiceId"' in prosrc) > 0
  FROM pg_proc WHERE proname = 'users_no_orphan_member';
```

It returned `true` when the revert was supposed to be in place, and the run was
thrown away. Re-running with the triggers dropped first made it `false`, and the
arm then failed exactly as predicted.

## THE RULE

**For anything that lives in the database — a function body, a trigger, a
constraint, a default — the file is a SOURCE, not the state.** Assert the state:

| artifact | ask |
|---|---|
| function / procedure body | `pg_proc.prosrc` |
| trigger presence and timing | `pg_trigger` (`tgtype`, `tgdeferrable`, `NOT tgisinternal`) |
| constraint | `pg_constraint.consrc` / `pg_get_constraintdef()` |
| column default | `information_schema.columns.column_default` |

⚠️ **AND THE HAZARD IS SPECIFICALLY MIGRATIONS THAT ARE NOT RE-RUNNABLE.**
`CREATE OR REPLACE FUNCTION` is idempotent; **`CREATE TRIGGER` is not**, and
Postgres has no `CREATE TRIGGER IF NOT EXISTS`. So a migration containing both
will get *part way* through a re-install and abort — replacing nothing or
replacing only what came before the first trigger. A harness that re-installs to
test a mutation must `DROP TRIGGER IF EXISTS` first, and must assert afterwards
rather than assume.

## THE FAMILY

This is the same shape as **a mutation proof that asserts its own application**,
and as **a scripted edit that proves it applied** — moved one layer out. There
the risk was that a `.replace()` matched nothing; here the file changed
perfectly and the *effect* never reached the thing under test.

> **Every layer between your edit and the code that runs is a layer where the
> edit can stop, and each one needs its own assertion.**
