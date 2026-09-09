# §2.5 DECLARATION — ADMIN-3a, the `Practice` write path

**Written and committed BEFORE the act.** Branch `feat/admin3a-practice-write`,
migration `20260909080000_admin3a_practice_write_audit_actions`.

## WHAT MUST CHANGE

| # | quantity | before | after |
|---|---|---|---|
| 1 | `AuditAction` enum values | **156** | **159** |
| 2 | new values | — | `PRACTICE_UPDATED`, `PRACTICE_ARCHIVED`, `PRACTICE_RESTORED` |
| 3 | rows carrying any of them | 0 | **0** — nothing writes one yet |

⚠️ **PERMANENTLY IRREVERSIBLE.** Postgres has no `ALTER TYPE … DROP VALUE`.
Once applied, these three exist for the life of the database. That is why the
list is exactly three and why it is written down before the act.

## WHAT MUST NOT CHANGE

| # | quantity | expected |
|---|---|---|
| 4 | `practices` row count | **unchanged** |
| 5 | any `practices` column value | **unchanged** — this deploy writes no practice row |
| 6 | visits, patients, signatures | **unchanged** |
| 7 | `audit_logs` row count | **unchanged** by the migration itself |
| 8 | existing `AuditAction` values | **all 156 still present** |

## WHY THIS IS THE FLOOR UNDER FOUR ROWS

`practice.update` had **zero call sites**. ADMIN-3 needs somebody to set a
specialty; ADMIN-6 needs somebody to archive; ADMIN-2a needs somebody to change
a slug; and **ruling #226 has been blocked since 2026-09-07**, naming this cause
in its own words — *"NO ADMIN PATH WRITES A PRACTICE ROW … and there is no
`PRACTICE_ARCHIVED` among the 156 `AuditAction` values."* Both halves of #226's
blocker are removed here.

## ⚠️ AND A MEASUREMENT THAT SHARPENS THE ROW

The recon reported `practice.update = 0`, which was true and incomplete. There
were already **two** practice writers: `actions/auth.ts` **creates** one at
signup, and `settings/delete-account/route.ts` **hard-deletes** one when the
last account goes.

> **The product could MAKE a practice and DESTROY a practice, and could not
> CHANGE one** — the irreversible half of the lifecycle without the reversible
> half.

That is the shape #306 ruled against one arc over, and it is why ADMIN-6's
archive must exist before anything comes to rely on deletion. The population is
now pinned by a gate arm at three files, failing if it moves either way.

## ROLLBACK

`git revert` the merge. **The enum values remain** — they are additive, unused,
and unreachable once the verb is gone. No data is written by this deploy.

## WHAT WOULD MAKE ME SAY THIS FAILED

- rows 4–6 moving
- any of the 156 pre-existing `AuditAction` values missing afterwards
- a `practices` row written by this deploy
