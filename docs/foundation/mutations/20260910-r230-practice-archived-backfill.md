# RULED-MUTATION DECLARATION — ruling #230, the six `PRACTICE_ARCHIVED` rows

**Written and COMMITTED BEFORE THE ACT.** `scripts/run-ruled-mutation.sh` refuses
to run unless this file is tracked, unmodified and committed, so its commit
timestamp provably precedes the rows it describes.

**Ruling:** #230 (`docs/foundation/rulings/2026-09-07-230-232.md`), which executes
#226. #230 deferred these rows on purpose:

> *"A real `PRACTICE_ARCHIVED` action arrives with practice-lifecycle work in the
> ADMIN arc, with its own migration. These six get their rows then."*

ADMIN-3a (PR #1086) added `PRACTICE_ARCHIVED` in migration
`20260909080000_admin3a_practice_write_audit_actions`, which is applied in
production. **So this is "then".** It needs no new ruling. It is the second half
of an act already ruled and already judged.

**Lane:** Design/Admin, under ruling #310.

**Instrument:**

    bash scripts/run-ruled-mutation.sh \
      --declaration docs/foundation/mutations/20260910-r230-practice-archived-backfill.md \
      -- docker exec -i meddoc-pro-postgres-1 psql -U meddoc -d meddoc \
           -v ON_ERROR_STOP=1 -f - < scripts/execute-r230-practice-archived-backfill.sql

---

## WHAT THE ACT IS

Six rows go into `audit_logs`, one per archived practice, and nothing else is
written. No practice, no user, no enum value is touched.

| field | value |
|---|---|
| `id` | `r230-practice-archived-<practiceId>`. `audit_logs.id` has no database default (measured), and a fixed id makes a second run refuse instead of duplicating |
| `action` | `PRACTICE_ARCHIVED` |
| `practiceId`, `practiceIdSnapshot`, `targetId` | the practice id |
| `targetType` | `Practice` |
| `userId` | `NULL`. The actor was the ruling, recorded as `metadata.actor = r226-ruling-2026-09-07`, the same identifier the act wrote to `users.deactivatedBy` |
| `metadata` | `changed.isActive {from:true, to:false}` and `reason`, which are exactly the keys `updatePractice()` writes for a live archive, so one format serves every reader. It also carries `backfill:true`, `ruling:'#226/#230'`, and `act {declaration, declarationCommit 071b80ab, judgementCommit fca86bb0, executedAt 2026-09-07T08:36:52Z}` |
| `timestamp` | `now()`, meaning when the record was written |

⚠️ **THE ROW TIMESTAMP IS NOT THE ACT'S TIME, AND THAT IS DELIBERATE.** The act ran
at `2026-09-07T08:36:52Z`, per the runner transcript recorded in the r226
judgement (`fca86bb0`). But the database holds **no witness** to that instant. The
raw-SQL archive did not bump `practices.updatedAt`, which still reads
`2026-04-13` / `2026-05-03` (measured 2026-09-10). Writing a literal that nothing
in the database corroborates is the fabrication #230 names. So the act's time
travels in `metadata.act.executedAt`, attributed to its source.

## THE SIX PRACTICES

Identical to the r226 act's population, and re-measured read-only from
production on 2026-09-10:

| # | practice id |
|---|---|
| 1 | `clinic_test_b` |
| 2 | `cmopgtjqc000h01qxbysh3ccz` |
| 3 | `cmophsjyy000001qqmp2e4qdn` |
| 4 | `cmoq7v57p000z01qqp9u9gd16` |
| 5 | `cmoq7w8vj001301qquq6wzxgc` |
| 6 | `cmoq7wjfm001b01qqvwjqtuih` |

**Measured 2026-09-10, before this declaration was written:** practices
**199**, of which `isActive=false` **6**, and they are exactly these six. Users
**198**, of which **5** carry `deactivatedBy = r226-ruling-2026-09-07`. Visits
**58**, signed **40**. `PRACTICE_*` audit rows: **0**. Rows with an `r230-` id:
**0**. Enum label `PRACTICE_ARCHIVED`: **present**.

---

## MUST CHANGE

| # | row | before | after | falsifier |
|---|---|---|---|---|
| **R230-C1** | `audit_logs` rows with `id = r230-practice-archived-<id>` for the six, action `PRACTICE_ARCHIVED`, `targetType = Practice`, `practiceId = targetId = <id>`, `userId` NULL, `metadata.changed.isActive.to = false` | **0** | **6** | the backfill did not happen, or wrote a shape readers do not expect |
| **R230-C2** | `PRACTICE_ARCHIVED` rows in the whole table | **0** | **6** | a seventh row means something else archived a practice, or this ran twice |

## MUST NOT CHANGE

| # | row | expectation | falsifier |
|---|---|---|---|
| **R230-N1** | **CLINICAL COUNTS, never omitted per §2.5.** `transcribe_visits` total and signed | unchanged across the act, compared inside the transaction. **58 / 40** at declaration time | any movement means the act did something nobody asked for |
| **R230-N2** | `practices` and `users` row counts | unchanged; **199 / 198** at declaration time | a row was created or deleted |
| **R230-N3** | archived practices | still exactly the six | the archived set moved |
| **R230-N4** | the six practice rows (`updatedAt`, `isActive`) | byte-identical before and after | a practice row was written |
| **R230-N5** | the members of the six (`updatedAt`) | byte-identical before and after | a user row was written |

The script's post-verification asserts every row above inside the transaction
and **rolls back** on any mismatch. The pre-guards refuse if the archived set is
not exactly the six, if any `PRACTICE_ARCHIVED` or `r230-` row already exists, if
the enum label is absent, or if the r226 act's five reconciled users are not
where it left them.

## REVERSIBILITY

Fully reversible: delete the six rows by their known ids. No enum value is spent,
and no other row is written.

## WHAT THIS DOES NOT CLAIM

The archive is still a **marker**. Nothing on `main` reads `practices.isActive`
today (ADMIN-6a). These rows record an act; they enforce nothing. ADMIN-6 makes
the flag a switch, and that is a separate change with its own declaration.

## JUDGEMENT

A separate judgement follows the act (#232): **re-derived independently of the
script's own post-verify.** An act that reports its own success has not been
judged.
