# §2.5 AUTHOR ROWS — ADMIN-5, OWNER DEMOTION AND MEMBER REMOVAL

**Written at PR-OPEN time, before the act**, per the ADMIN-1 board filing and
**ruling #198** — a MIGRATION-carrying deploy requires the STRICT declaration,
committed before the act, because a migration is irreversible.

**Lane:** Design/Admin. ⚠️ **THIS PR CARRIES A MIGRATION** —
`20260906120000_admin5_member_removed_action`.

    ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'PRACTICE_MEMBER_REMOVED';

⚠️ **PERMANENTLY IRREVERSIBLE.** Postgres has no `ALTER TYPE … DROP VALUE`.
**One** value, not two: demotion needs no new label (`PRACTICE_ROLE_CHANGED`
already carries `from`/`to`) and refusals reuse `PRACTICE_ADMIN_REFUSED` with a
`refusal` discriminator. An irreversible addition is bought only where a rollup
would otherwise be wrong — here, telling a practice's own removals apart from a
super-admin's account deactivations.

## MUST CHANGE

| # | row | before | after | falsifier |
|---|---|---|---|---|
| **A5-C1** | `AuditAction` label cardinality in production | **156** | **159** | ⚠️ **THE ARITHMETIC IS 156 + 2 + 1, AND THE 2 ARE NOT MINE.** Production is two behind `main`: PR #1015 merged and has not deployed, and its migration adds `DEFAULT_INSERTED_BY_DOCTOR` and `DEFAULT_INSERT_UNDONE`. If this deploy carries both PRs the count is 159; if #1015 shipped first it moves 158 → 159. **A count of 157 means my migration ran and #1015's did not, which would mean the deploy did not carry what it claimed.** |
| **A5-C2** | `PRACTICE_MEMBER_REMOVED` present in `pg_enum` | absent | present | the removal path writes an audit label the database does not have; `logAudit` swallows the failure into one `console.error` and the trail loses every removal |
| **A5-C3** | `practice-owner-guard` in the shipped server bundle | **0 files** | **≥ 1 file** | the guard never reached the image and the action calls something that is not there |
| **A5-C4** | `members-owner-note` in the shipped client bundle | present | **absent** | the page still tells a doctor that owners "cannot be demoted or removed here yet — ask support" while the control beside it does exactly that |

## MUST NOT CHANGE

| # | row | expectation | falsifier |
|---|---|---|---|
| **A5-N1** | ⚠️ **practices with an ACTIVE member and NO active owner** | **0**, before and after | **THIS IS THE ROW THE WHOLE FEATURE IS ABOUT.** Measured on production before the act: **0**. If it is anything but 0 afterwards, a practice has been stranded — nobody can invite, change roles, or remove, and support running SQL is the only route back |
| **A5-N2** | total practices / total users | unchanged | this PR adds no row and deletes none; movement means something else rode the deploy |
| **A5-N3** | users with `deactivatedAt IS NOT NULL` | **unchanged by the deploy itself** | the migration migrates no data. A removal AFTER the deploy moves this by design; the deploy moving it means a migration wrote rows |
| **A5-N4** | clinical counts — visits, patients, signatures | unchanged | never omitted, per §2.5 |
| **A5-N5** | `AuditAction` labels other than the added one | unchanged | an `ADD VALUE` that reordered or renamed anything would corrupt every historical row |
| **A5-N6** | practices with **zero** owners | **17**, unchanged | ⚠️ **A KNOWN PRE-EXISTING POPULATION, MEASURED AND EXPLAINED SO IT IS NOT READ AS DAMAGE.** 16 carry no members at all; the 17th has 2 members, both deactivated. **None has an active member** (A5-N1). This deploy neither creates nor repairs them, and a session meeting the number cold would reasonably read it as the failure A5-N1 is guarding |

## VERIFY — structural, mutating nothing

⚠️ **THE DISCRIMINATOR IS STATED.** `PRACTICE_MEMBER_REMOVED`,
`practice-owner-guard` and `LAST_OWNER` are all NEW in this range; each measures
**0** against the image running today. `members-owner-note` is the mirror case —
it must go from present to absent, so it discriminates in the other direction.

    -- A5-C1
    SELECT count(*) FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid
      WHERE t.typname='AuditAction';                                  -- 159

    -- A5-C2
    SELECT enumlabel FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid
      WHERE t.typname='AuditAction' AND enumlabel='PRACTICE_MEMBER_REMOVED';

    -- A5-N1  ⚠️ the row the feature is about
    SELECT count(*) FROM (
      SELECT p.id FROM practices p JOIN users u ON u."practiceId"=p.id
      GROUP BY p.id
      HAVING count(u.id) FILTER (WHERE u."deactivatedAt" IS NULL) > 0
         AND count(u.id) FILTER (WHERE u."practiceRole"='OWNER'
                                   AND u."deactivatedAt" IS NULL) = 0) t;   -- 0

    -- A5-N6
    SELECT count(*) FROM (
      SELECT p.id FROM practices p LEFT JOIN users u ON u."practiceId"=p.id
      GROUP BY p.id
      HAVING count(u.id) FILTER (WHERE u."practiceRole"='OWNER'
                                   AND u."deactivatedAt" IS NULL) = 0) t;   -- 17

    -- A5-C3 / A5-C4, in the shipped bundle
    docker exec meddoc-pro-transcribe-md-1 sh -lc \
      "grep -rl 'practice-owner-guard' /app/apps/transcribe-md/.next/server | wc -l"
    docker exec meddoc-pro-transcribe-md-1 sh -lc \
      "grep -rl 'members-owner-note' /app/apps/transcribe-md/.next | wc -l"   -- 0

⚠️ **POSITIVE CONTROL FIRST, AND IT IS NOT THE CHECK.** Grep the bundle for
`CANNOT_CHANGE_OWN_ROLE` — it shipped with ADMIN-1 and exists in **both**
images, so it proves the grep reaches the bundle while proving nothing about
this PR.

**No real doctor's visit is a smoke target, and no real practice is either.**
The full demote / remove / refuse walk belongs on QA. In production this is the
structural queries above and DOM presence on `/settings/members`, mutating
nothing.

## ⚠️ WHAT THESE ROWS CANNOT DETECT, SAID PLAINLY

A schema row cannot see whether the guard holds **under concurrency** — the one
property the feature exists for. No query against a settled database can: the
failure only exists while two transactions overlap. That is why the proof is
`tests/e2e/scenarios/40-admin5-last-owner.spec.ts`, which races the shipped
statements against a real Postgres **with a negative control that must leave
zero owners**, and why its measurements are recorded in
`docs/foundation/evidence/admin5-last-owner-guard-probes.md` rather than
implied by a green tick here.
