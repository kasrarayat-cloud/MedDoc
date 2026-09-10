# RULED-MUTATION DECLARATION — ruling #226, archive the six test practices

**Written and COMMITTED BEFORE THE ACT.** `scripts/run-ruled-mutation.sh` refuses
to run unless this file is **tracked, unmodified and committed**, so its commit
timestamp provably precedes the rows it describes — the distinction B7's
backfill lost by one minute fifty-seven seconds, when 175 irreversible rows
landed *before* the declaration that described them.

**Ruling:** #226 (`docs/foundation/rulings/2026-09-07-226-229.md`) — class (d),
decided by the owner.

**Instrument:**

    bash scripts/run-ruled-mutation.sh \
      --declaration docs/deploy-declarations/20260907-r226-archive-six-test-practices.md \
      -- docker exec -i meddoc-pro-postgres-1 psql -U meddoc -d meddoc \
           -v ON_ERROR_STOP=1 -f - < scripts/execute-r226-archive.sql

⚠️ **THIS PATH IS NOT `docs/foundation/deploys/`, AND THAT IS DELIBERATE.**
`declaration_resolve` scans that directory and refuses any filename whose last
dash-separated segment is not a commit sha, except a `*-backfill-declaration`
keep-list entry (`scripts/lib/declaration.sh:126,134`). A file named
`…-practice-archive.md` there returns **rc=2** and would **block the next
production deploy for the wrong reason**. `docs/deploy-declarations/` is tracked,
carries precedent (`admin1-seats-20260905.md`), and is scanned by nothing —
measured: `grep -rn 'deploy-declarations' scripts/ .github/` → **0 hits**.
⚠️ And it is not `docs/deploy-logs/`, which is **gitignored** — a declaration
written there looks committed and is invisible.

---

## THE SIX PRACTICES, BY ID AND CLASSIFICATION

As #226 requires. Every one measured read-only from production on 2026-09-07.

| # | practice id | name | classification | members | visits |
|---|---|---|---|---|---|
| 1 | `clinic_test_b` | Test Clinic B | **TEST** — seeded fixture clinic, April | 2 | 0 |
| 2 | `cmopgtjqc000h01qxbysh3ccz` | Solo — QA Tester gaum | **QA SIGNUP SHELL** — 2026-05-03 run | 1 | 0 |
| 3 | `cmophsjyy000001qqmp2e4qdn` | Solo — QA Bypass gc41 | **QA SIGNUP SHELL** — 2026-05-03 run | 1 | 0 |
| 4 | `cmoq7v57p000z01qqp9u9gd16` | Solo — QA Round2 h9wh | **QA SIGNUP SHELL** — 2026-05-03 run | 1 | 0 |
| 5 | `cmoq7w8vj001301qquq6wzxgc` | Solo — Edge apostrophe | **QA EDGE-CASE SHELL** — 2026-05-03 run | 1 | 0 |
| 6 | `cmoq7wjfm001b01qqvwjqtuih` | Solo — Edge long-prefix | **QA EDGE-CASE SHELL** — 2026-05-03 run | 1 | 0 |

**All six: zero able owners, zero live members, zero visits, all members
inactive, all seven users carrying test-shaped emails.** Five are signup shells
minted in one QA run on 2026-05-03; the sixth is a seeded April test clinic.

⚠️ **NOBODY IS STRANDED BY THESE, AND THAT IS THE SECOND QUERY (canon 124):**
`practices with a LIVE member and no able owner` = **0**. The alarming count is
the shape; this is the harm, and there is none.

## THE SEVEN USERS

| user id | practice | `isActive` | `deactivatedAt` | `deactivatedBy` |
|---|---|---|---|---|
| `test_user_admin_b` | `clinic_test_b` | false | **already set** | `gate0-ruling-2026-08-05` |
| `test_user_doctor_b` | `clinic_test_b` | false | **already set** | `gate0-ruling-2026-08-05` |
| `cmopgtjtu000i01qxkbjop4gq` | Solo QA Tester | false | **NULL — to write** | — |
| `cmophsjzn000101qqgy3e4kmv` | Solo QA Bypass | false | **NULL — to write** | — |
| `cmoq7v58f001001qqw9vivgzr` | Solo QA Round2 | false | **NULL — to write** | — |
| `cmoq7w8vz001401qqbk9q46bb` | Solo Edge apostrophe | false | **NULL — to write** | — |
| `cmoq7wjfo001c01qqo6yn3tjy` | Solo Edge long-prefix | false | **NULL — to write** | — |

---

## ⚠️ THE RECONCILIATION WRITES A **RECOVERED** TIMESTAMP, NOT `now()`

#226 says the five divergent users are *"reconciled to one truth"*. **The truth
is knowable and recorded — writing `now()` would be a fabrication.**

Two independent witnesses agree **to the microsecond** on all five:

```
users."updatedAt"  =  audit_logs."timestamp"  =  2026-08-08 20:07:02.578745+00
                                                  (identical on all 5 rows)
```

Five `USER_DEACTIVATED` audit rows already exist for exactly these users. The act
was a **credential containment on 2026-08-08** — a QA password published in an
untracked evidence tree still bcrypt-matched the live production hash 97 days
later.

**Calibration that the timestamp came from Postgres `now()` and not a JS `Date`:**
only **6 of 198** user rows carry sub-millisecond precision in `updatedAt`;
Prisma writes millisecond precision (microsecond remainder `000`). These five are
among the six.

> **So `deactivatedAt` is written as `TIMESTAMPTZ '2026-08-08 20:07:02.578745+00'`
> — the recovered instant — and `deactivatedBy` as `'r226-ruling-2026-09-07'` — the RULING identifier.**

`deactivatedBy` carrying an act identifier rather than a user id **has precedent
in this very data**: the other two users in this same population read
`gate0-ruling-2026-08-05`. The actor for a ruled one-shot is the **ruling**, and
the column has no FK precisely so it can say so.

⚠️ **AND THE WRITE MUST BE RAW SQL, NOT PRISMA.** `users.updatedAt` is
`@updatedAt`, so a Prisma write would bump it — **destroying the corroborating
witness to the very timestamp being recorded.** `updatedAt` is not named in the
UPDATE.

---

## MUST CHANGE

| # | row | before | after | falsifier |
|---|---|---|---|---|
| **R226-C1** | `practices.isActive = false` for the six ids above | **0 of 6** | **6 of 6** | the archive did not happen |
| **R226-C2** | users with `isActive=false AND deactivatedAt IS NULL`, whole table | **5** | **0** | the reconciliation did not happen |
| **R226-C3** | the five users' `deactivatedAt` | `NULL` | **`2026-08-08 20:07:02.578745+00`** exactly | a different value means a fabricated or approximated timestamp — the one thing this declaration exists to prevent |
| **R226-C4** | the five users' `deactivatedBy` | `NULL` | `r226-ruling-2026-09-07` | the act is unattributed |

## MUST NOT CHANGE

| # | row | expectation | falsifier |
|---|---|---|---|
| **R226-N1** | **CLINICAL COUNTS — never omitted, per §2.5.** `transcribe_visits` total and signed | **58 / 40**, unchanged | a mutation that moves a visit or signature count has done something nobody asked for. These six hold zero visits, so ANY movement is the finding. |
| **R226-N2** | `users` row count · `practices` row count | **198 / 199**, unchanged | **this is a SOFT archive. A drop means a DELETE happened, which #226 forbids.** |
| **R226-N3** | the five users' `updatedAt` | **`2026-08-08 20:07:02.578745+00`**, unchanged | Prisma was used, or `updatedAt` was named — and the corroborating witness is gone |
| **R226-N4** | `isActive` on the seven users | **false**, unchanged | the reconciliation flipped the state instead of recording its metadata |
| **R226-N5** | `practiceRole` on the seven users | unchanged | not part of this act |
| **R226-N6** | any practice NOT in the six | `isActive` unchanged | the WHERE was wrong — the single most dangerous failure here |
| **R226-N7** | practices with a LIVE member and no able owner | **0**, unchanged | the act created the harm it was cleaning up after |

## VERIFY — after the act

    docker exec -i meddoc-pro-postgres-1 psql -U meddoc -d meddoc -X -c "
      SELECT count(*) FILTER (WHERE NOT \"isActive\") AS archived_of_6 FROM practices
       WHERE id IN ('clinic_test_b','cmopgtjqc000h01qxbysh3ccz','cmophsjyy000001qqmp2e4qdn',
                    'cmoq7v57p000z01qqp9u9gd16','cmoq7w8vj001301qquq6wzxgc','cmoq7wjfm001b01qqvwjqtuih');
      SELECT count(*) AS still_divergent FROM users WHERE \"isActive\"=false AND \"deactivatedAt\" IS NULL;
      SELECT count(*) AS users, (SELECT count(*) FROM practices) AS practices FROM users;
      SELECT count(*) AS visits, count(*) FILTER (WHERE \"signedAt\" IS NOT NULL) AS signed FROM transcribe_visits;
      SELECT count(*) AS other_practices_touched FROM practices
       WHERE NOT \"isActive\" AND id NOT IN ('clinic_test_b','cmopgtjqc000h01qxbysh3ccz','cmophsjyy000001qqmp2e4qdn',
                    'cmoq7v57p000z01qqp9u9gd16','cmoq7w8vj001301qquq6wzxgc','cmoq7wjfm001b01qqvwjqtuih');"

## RESTORE — the act is reversible, and here is how

    UPDATE practices SET "isActive" = true WHERE id IN (<the six ids>);
    UPDATE users SET "deactivatedAt" = NULL, "deactivatedBy" = NULL
     WHERE id IN ('cmopgtjtu000i01qxkbjop4gq','cmophsjzn000101qqgy3e4kmv',
                  'cmoq7v58f001001qqw9vivgzr','cmoq7w8vz001401qqbk9q46bb',
                  'cmoq7wjfo001c01qqo6yn3tjy');

⚠️ **WHAT THE RESTORE CANNOT UNDO:** nothing. No row is deleted, no enum value is
added, no column is dropped. That is the point of a soft archive, and it is why
#226 forbids the hard delete that `settings/delete-account` performs one route
over.

---

## ⚠️ WHAT THIS DECLARATION DOES **NOT** CLAIM

**The archive is a MARKER, not an enforcement.** Measured: **nothing reads
`practices.isActive`** — the only `isActive` reads in the tree are on the USER
row (`apps/transcribe-md/src/lib/auth.ts:69`). Setting it disables nothing,
hides nothing from any query, and changes no behaviour.

It is bookkeeping: it marks six rows as not-real so a future audit can exclude
them. That is what #226 asked for and it is all that is being claimed.

**AND THE "AUDITED ADMIN PATH" NAMED BY #226 DOES NOT EXIST FOR PRACTICES.**
Measured: zero `prisma.practice.update|updateMany|delete|deleteMany` anywhere
outside tests except one **hard delete** in `settings/delete-account/route.ts:200`
which #226 forbids; the admin API exposes users/audit-logs/usage/system/hipaa/
threats and no practices; and there is no `PRACTICE_ARCHIVED` among the 156
`AuditAction` values. **That question is surfaced to the owner separately** —
adding an enum value is irreversible, and it is not a call this session takes on
its own for a six-row cleanup.
