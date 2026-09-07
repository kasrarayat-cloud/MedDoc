# BOARD FILING — PR #1026's LAST-OWNER PREDICATE COUNTS OWNERS WHO CANNOT SIGN IN

**Filed 2026-09-07 by the Design/Admin session, while building ruling #210.**
This is evidence for the lane that owns PR #1026, from the lane that owns
#1036. **No authorization is attached** — the fix belongs to #1026's re-pass
under ruling #212, not to this filing.

## THE DEFECT, WITH THE ROWS

`practice-owner-guard-sql.ts`'s `LAST_OWNER_CLAUSE` counts a practice's
remaining owners with **one** activity condition:

```sql
(SELECT count(*) FROM users u2
  WHERE u2."practiceId" = $2
    AND u2."practiceRole" = 'OWNER'::"PracticeRole"
    AND u2."deactivatedAt" IS NULL) > 1
```

`users` carries **five** independent expressions of "no longer active", and
`deactivatedAt` is only one of them. Measured on **production**, 2026-09-07:

| | |
|---|---|
| OWNER rows passing `deactivatedAt IS NULL` that **cannot sign in** | **6** |
| practices where this predicate and "can actually administer" disagree | **6** |

### ⚠️ THE ELEVEN-MEMBER PRACTICE

One of those six has **11 members**:

| user | practiceRole | isActive | deactivatedAt IS NULL | suspendedAt |
|---|---|---|---|---|
| `cmotbvvf` | OWNER | `t` | `t` | — |
| `cmnv3gzj` | OWNER | `t` | `t` | **SET** |
| (9 others) | OWNER | `f` | `f` | — |

    clause_sees = 2        can_actually_administer = 1

**So the guard believes there is a spare owner, and permits demoting the only
one who can log in.** Concrete input → wrong output:

> `changeMemberRoleAction(cmotbvvf, 'CLINICIAN')` → the subquery returns `2`,
> `> 1` is TRUE, the `UPDATE` matches, `rowsAffected = 1`, **no refusal** —
> and eleven people are left in a practice nobody can administer.

The branch does permit this: `practice-members.ts:213` records *"AN OWNER IS
NOW EDITABLE, AND THE INVARIANT MOVED RATHER THAN LAPSED"*, and `:243` handles
the `LAST_OWNER` outcome that this input never reaches.

**And the same state is reachable with no demotion at all:** `POST
/api/admin/users/[id]/suspend` had no last-owner guard, so suspending
`cmotbvvf` gets there directly. That door is in scope for ruling #210 and is
guarded on PR #1036.

## WHY THIS IS NOT A REQUEST TO CHANGE #1026

⚠️ **THE MECHANISM IS NOT THE DEFECT, AND #200 SAYS SO.** The practice-row lock
is correct and is the ruled shape; the branch even measured that removing it
leaves the guard green in 1 of 3 runs. **What is wrong is the SET the count is
taken over**, which is a different question from how the count is serialized.

**Nor is the fix "add four conditions to that subquery".** That would make the
rule's **second** copy — ruling #210 puts the definition in the database as
`users_is_active_owner`, precisely so the app layer stops owning it. Under
#210 the app clause becomes the *friendly refusal* and the trigger is the
enforcement, and the two must not drift. **A rule with several readers
contradicts itself the day one is edited, while every arm stays green.**

## WHAT IS ACTUALLY OWED, AND TO WHOM

Ruling **#212** orders one more pass on #1026's finished diff **after #210's
trigger lands**, because the trigger changes what the harness must prove: **the
guard and the trigger must each refuse alone.** This finding is an input to
that pass, not a separate work item.

⚠️ **AND IT IS AN ARGUMENT FOR THE ORDERING, NOT AGAINST #1026.** Two enforcers
with two different ideas of "active owner" is worse than one enforcer, and the
only reason this is visible now is that #210 forced the predicate to be written
down in one place and measured against real rows. **#1026 shipped nothing
wrong that #1018-style review would have caught; the divergence lives in data
nobody had looked at.**

## HOW TO RE-DERIVE IT

    docker exec -i meddoc-pro-postgres-1 psql -U meddoc -d meddoc -X -c "
      SELECT count(*) AS counted_but_cannot_sign_in
        FROM users
       WHERE \"practiceRole\"='OWNER' AND \"deactivatedAt\" IS NULL
         AND (\"isActive\"=false OR \"suspendedAt\" IS NOT NULL OR \"softDeletedAt\" IS NOT NULL);"

⚠️ `docker exec` needs `-i` or you get a silent empty result — a false zero, not
an answer. It cost this session one wrong reading before it was caught by a
positive control.
