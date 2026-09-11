# JUDGEMENT: ruling #230, the six `PRACTICE_ARCHIVED` rows. 7 of 7 rows hold

**Declaration:** `docs/foundation/mutations/20260910-r230-practice-archived-backfill.md`, committed as `2f86a329` at **2026-09-10T18:38:55Z**, merged to `main` as `158af24f` (#1099).
**Act:** `run-ruled-mutation.sh`, from the shared tree at `158af24f`, started **2026-09-11T00:10:58Z**, exit 0. **The declaration precedes the act by 5h32m**, which is the direction B7's backfill lost by 1m57s.

⚠️ **RE-DERIVED INDEPENDENTLY OF THE SCRIPT'S OWN POST-VERIFY**, per #232. Every row below comes from a fresh read-only query run at 2026-09-11T00:11:57Z, **after** the act committed. None of them is the script's `NOTICE` lines. An act that reports its own success has not been judged.

## The runner's bracket

    committed   : 2f86a329ceab at 2026-09-10T18:38:55+00:00
    starting at : 2026-09-11T00:10:58Z   ← must be AFTER the commit above
    NOTICE  r230 pre-guards: 6 archived (and only 6), 0 existing rows, enum present, r226 corroborated
    INSERT 0 6
    NOTICE  r230 VERIFY: 6 rows in the declared shape, 6 PRACTICE_ARCHIVED in total, practices/users/visits untouched (visits 58/signed 40).
    COMMIT
    FINISHED at 2026-09-11T00:10:58Z, exit 0

## Counts taken around the act (same queries, before and after)

| | before (00:10:58Z) | after (00:10:58Z) |
|---|---|---|
| `audit_logs` total | 12,498 | **12,504** |
| `PRACTICE_ARCHIVED` | 0 | **6** |
| rows with an `r230-` id | 0 | **6** |
| practices / of which archived | 199 / 6 | 199 / 6 |
| users | 198 | 198 |
| visits / signed | 58 / 40 | 58 / 40 |

The only thing that moved is `audit_logs`, by +6.

## The declared rows, judged

| row | declared | measured independently | holds |
|---|---|---|---|
| **R230-C1** | 6 rows, `id = r230-practice-archived-<id>`, `PRACTICE_ARCHIVED`, `practiceId = practiceIdSnapshot = targetId`, `targetType = Practice`, `userId` NULL, `changed.isActive.to = false` | all 6, **one row per id**, each with every listed property true; each also carries `backfill:true`, `ruling:'#226/#230'` and `act.declarationCommit:'071b80ab'` | ✅ |
| **R230-C2** | `PRACTICE_ARCHIVED` table-wide 0 → 6 | **6** | ✅ |
| **R230-N1** | clinical counts unchanged, 58 / 40 | **58 / 40** | ✅ |
| **R230-N2** | practices / users 199 / 198 | **199 / 198** | ✅ |
| **R230-N3** | the archived set is exactly the six | exactly `clinic_test_b` plus the five `cmo…` ids | ✅ |
| **R230-N4** | the six practice rows are untouched | `updatedAt` still reads **2026-04-13** (`clinic_test_b`) and **2026-05-03** (the five); `isActive` is false on all six | ✅ |
| **R230-N5** | the members of the six are untouched | the five r226 users are still at **2026-08-08 20:07:02.578745+00**, which is the r226 witness, still intact. The two gate0 users are at **2026-04-26 07:11:10.999 / 07:11:11.003**, older than the act | ✅ |

**Positive control for the action queries:** the same `action::text` shape counts **20** `USER_DEACTIVATED` rows, so the query sees actions when they exist.

## What this does not claim

The six practices are still archived **as a marker**. Nothing on `main` reads `practices.isActive` yet (ADMIN-6a); #1106 makes it a switch. These rows **record** #226's act; they enforce nothing.

**Reversible:** delete the six rows by their deterministic ids. No enum value was spent.
