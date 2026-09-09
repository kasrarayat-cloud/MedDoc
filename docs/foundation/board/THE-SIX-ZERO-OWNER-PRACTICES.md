# BOARD FILING — THE SIX ZERO-OWNER PRACTICES, IDENTIFIED (ruling #222)

**Filed 2026-09-07 by the Design/Admin session.** Ruling **#222** makes these a
**data-hygiene item for ADMIN**: *identify each — signup shell, abandoned, or
test — and assign an owner or archive.* This is the identification half. **The
archive/delete decision is not taken here** (see the last section).

Measured read-only against production, 2026-09-07.

## ⚠️ THE HEADLINE: NOBODY IS ACTUALLY STRANDED

```
practices with a LIVE member and NO able owner (the real harm) ........ 0
```

The harm this invariant exists to prevent — **people in a practice nobody can
administer** — is **not currently realised anywhere in production**. All six
zero-owner practices are inert: every member of every one is `isActive = false`.

**That is the number that decides how urgent this is, and it is the one that
would have been easiest not to ask for.** The count of zero-owner practices is
alarming on its own and harmless in context, and only the second query
separates them.

## THE SIX

| practice | name | created | members | live | visits |
|---|---|---|---|---|---|
| `clinic_tes…` | Test Clinic B | 2026-04-13 | 2 | **0** | 0 |
| `cmoq7v57p0…` | Solo — QA Round2 h9wh | 2026-05-03 | 1 | **0** | 0 |
| `cmophsjyy0…` | Solo — QA Bypass gc41 | 2026-05-03 | 1 | **0** | 0 |
| `cmopgtjqc0…` | Solo — QA Tester gaum | 2026-05-03 | 1 | **0** | 0 |
| `cmoq7w8vj0…` | Solo — Edge apostrophe | 2026-05-03 | 1 | **0** | 0 |
| `cmoq7wjfm0…` | Solo — Edge long-prefix | 2026-05-03 | 1 | **0** | 0 |

**Classification: all six are TEST/QA artifacts.** Five are `Solo — QA …` /
`Solo — Edge …` signup shells minted on one day (2026-05-03) by a QA run
exercising signup edge cases; the sixth is an April test clinic. **All 7 users
across them carry test-shaped emails, and all 7 are inactive. None holds a
single visit.**

## ⚠️ A DATA-SHAPE OBSERVATION WORTH RECORDING

| | not `isActive` | `deactivatedAt` set |
|---|---|---|
| Test Clinic B (2 users) | 2 | 2 |
| the five QA shells (5 users) | 5 | **0** |

**Five users are `isActive = false` with `deactivatedAt IS NULL`** — inactive
without the timestamp that is supposed to record when and by whom.

This is exactly the divergence ruling **#221** is about, seen from the other
side: `isActive` and `deactivatedAt` are two columns expressing one idea, and
they already disagree on five real rows. **A predicate reading only one of them
answers a different question depending on which one it picked** — which is why
#221 puts the definition in one place and has all three readers derive from it.

It also confirms the trigger's exemption 1 is load-bearing rather than
theoretical: without it, these six practices' rows would be unwritable forever.

## WHAT THIS SESSION DID NOT DO, AND WHY

**It did not archive or delete anything.** Ruling class **(d)** — *money, keys,
or deletion of data* — reaches the owner, and archiving six practices with seven
user rows is deletion-adjacent on production data. The identification is the
part that can be done from here; **the disposal is a decision, not a chore.**

**The recommendation, offered rather than taken:** all six are safe to archive —
no live member, no clinical data, test-shaped throughout — and none needs an
owner assigned, because there is nobody in them to strand. ⚠️ **If any is
archived, archive the PRACTICE and leave the user rows to the ordinary path**;
the trigger permits both, and arms 28–32 on PR #1036 assert that a zero-owner
practice stays writable precisely so this cleanup is possible.

## HOW TO RE-DERIVE

    docker exec -i meddoc-pro-postgres-1 psql -U meddoc -d meddoc -X -c "
      SELECT count(*) FROM (
        SELECT p.id FROM practices p JOIN users u ON u.\"practiceId\"=p.id GROUP BY p.id
        HAVING count(*) FILTER (WHERE u.\"practiceRole\"='OWNER' AND u.\"isActive\"
                 AND u.\"deactivatedAt\" IS NULL AND u.\"suspendedAt\" IS NULL
                 AND u.\"softDeletedAt\" IS NULL) = 0
           AND count(*) FILTER (WHERE u.\"isActive\" AND u.\"deactivatedAt\" IS NULL
                 AND u.\"softDeletedAt\" IS NULL AND u.\"suspendedAt\" IS NULL) > 0) z;"

⚠️ `docker exec` needs `-i` or the heredoc form returns a **silent empty
result** — a false zero, not an answer.
