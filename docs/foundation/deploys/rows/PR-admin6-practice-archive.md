# §2.5 AUTHOR ROWS — ADMIN-6 / ADMIN-6a (branch `feat/admin6-practice-archive`)

**Written before the act**, per the ADMIN-1 board filing
(`docs/foundation/board/ADMIN1-ROWS-AT-PR-OPEN.md`) and ruling #184. Rename this
file to `PR-<number>.md` when the PR number exists; the body stays byte-identical.

**Lane:** Design/Admin. **NO MIGRATION.** `PRACTICE_ARCHIVED`,
`PRACTICE_RESTORED` and `LOGIN_FAILED` already exist in all three layers
(migration `20260909080000` applied in production); the new login refusal is an
`errorCode` STRING, not an enum value.

⚠️ **CODE-ONLY, BUT NOT "NOTHING BUT THE IMAGE IDS" IN BEHAVIOUR.** This deploy
turns `practices.isActive` from a marker into a SWITCH: three doors start
refusing members of an archived practice. The deploy itself writes no data. The
behaviour change reaches only the members of the **6** already-archived
practices, and the rows below show that population has nobody live in it.

**Runtime files:** `packages/db/src/practice-admits.ts` (new subpath export),
`packages/auth/src/user-session.ts` (D2), `apps/transcribe-md/src/lib/nextauth.ts`
(D1), `apps/transcribe-md/src/actions/auth.ts` (D3),
`apps/transcribe-md/src/lib/practice-write.ts` (archive act),
`apps/transcribe-md/src/app/api/admin/practices/[id]/route.ts` (409 mapping).
Not shipped at runtime: `scripts/prod-smoke/provision.ts` and
`scripts/proofs/admin6-archive-restore-proof.ts`.

⚠️ **`@meddoc/auth` is also a dependency of the retired `apps/meddoc-pro`.** D2
applies there too if it is ever revived. It serves 410 by design, and #307
removes its compose service.

## BASELINE — measured read-only in production, 2026-09-10 (a single `READ ONLY` transaction, then rolled back)

| quantity | value |
|---|---|
| practices `isActive=true` / `false` | **193 / 6** |
| ACTIVE users (`isActive`, not suspended, not soft-deleted) in archived practices | **0** |
| UNEXPIRED `user_sessions` of members of archived practices | **0** |
| USABLE invite codes (unrevoked, unexpired, uses left) into archived practices | **0** |
| practices containing a platform administrator (`role` OR `products`) | **3** |
| audit rows `PRACTICE_UPDATED` / `ARCHIVED` / `RESTORED` | **0** |
| audit rows `LOGIN_FAILED` with errorCode `ACCOUNT_PRACTICE_ARCHIVED` | **0** |
| `AuditAction` labels | **161** |
| control: unexpired sessions, all users | 3 (moves with ordinary logins; informational) |
| control: users | 198 |

## MUST CHANGE

| # | row | before | after | falsifier |
|---|---|---|---|---|
| **A6-C1** | the string `ACCOUNT_PRACTICE_ARCHIVED` in the shipped server bundle | **0 files** | **≥ 1** | D1 never reached the image. A string literal survives minification; a local symbol name does not, so do not grep for `practiceAdmits` |
| **A6-C2** | the string `practice_has_super_admin` in the shipped server bundle | **0 files** | **≥ 1** | the archive act's guards never reached the image, and the live `PATCH` route is an unguarded lockout lever |
| **A6-C3** | the string `INVITE_PRACTICE_NOT_ADMITTING` in the shipped server bundle | **0 files** | **≥ 1** | D3 never reached the image |

⚠️ **THE THREE MUST SHIP TOGETHER.** D2 without the guards makes the live
`PATCH isActive:false` route able to lock out a SUPER_ADMIN's own practice. That
is T1 in the research, and it is the reason the guards and the doors are in one
PR. If C2 is absent while any door string is present, **roll back.**

## MUST NOT CHANGE

| # | row | expectation | falsifier |
|---|---|---|---|
| **A6-N1** | practices by `isActive` | **193 / 6**, unchanged | the deploy archives or restores nothing. Any movement is an act that nobody declared |
| **A6-N2** | ⚠️ **SESSIONS ENDED BY THE DEPLOY** — unexpired sessions of members of archived practices | **0 before, 0 after**. Nothing is ended, because nothing is there to end | a non-zero BEFORE means the population changed after this row was written. **Stop and re-judge**: D2 will log those sessions out on their next request |
| **A6-N3** | active users in archived practices, i.e. the people newly refused at login | **0** | a non-zero means D1 refuses a live person the moment the image lands |
| **A6-N4** | usable invites into archived practices | **0** | a non-zero means D3 starts refusing a code somebody may be holding |
| **A6-N5** | `users` rows by lifecycle state (`isActive`, `suspendedAt IS NULL`, `softDeletedAt IS NULL`, `deactivatedAt IS NULL`) | unchanged | **design A writes no `users` row.** Movement during the deploy window means something other than ordinary use wrote members. A whole-table hash is not used, because an ordinary login updates `lastLogin` |
| **A6-N6** | audit rows `PRACTICE_*` | **0**, unchanged | the deploy performs no practice write. ⚠️ If the lead's separate #230 backfill ran first, this reads **6**, and the deploying declaration must say so by name |
| **A6-N7** | `LOGIN_FAILED` / `ACCOUNT_PRACTICE_ARCHIVED` | **0** at judgement | every user of the six archived practices is `isActive=false` and is refused earlier by the user check, which writes no row. A non-zero means a live person reached D1 |
| **A6-N8** | `AuditAction` labels / `_prisma_migrations` count | **161** / unchanged | this PR carries no migration. Movement means a second migration rode along unnamed |
| **A6-N9** | clinical counts: visits, signed visits, patients | **unchanged from the deploying declaration's baseline** (not measured here, because this lane reads non-clinical columns only) | never omitted, per §2.5. The doors change who may act; they create, move and delete no clinical row |
| **A6-N10** | the smoke practice (`SMOKE_PRACTICE_SLUG` in `scripts/prod-smoke/smoke-account.ts`) | `isActive = true` | if it is archived, `provision.ts` now REFUSES rather than silently un-archiving it. Restore it through `PATCH /api/admin/practices/<id>`, the audited door |

## VERIFY — structural, mutating nothing

    docker exec -i meddoc-pro-postgres-1 psql -U meddoc -d meddoc -X -tA <<'SQL'
    BEGIN TRANSACTION READ ONLY;
    -- positive control FIRST: the instrument answers about this table at all
    SELECT count(*) FROM practices;                                              -- 199
    SELECT "isActive", count(*) FROM practices GROUP BY 1 ORDER BY 1;           -- f 6 | t 193
    SELECT count(*) FROM user_sessions s JOIN users u ON u.id=s."userId"
      JOIN practices p ON p.id=u."practiceId"
      WHERE p."isActive"=false AND s."expiresAt" > now();                        -- 0
    SELECT count(*) FROM users u JOIN practices p ON p.id=u."practiceId"
      WHERE p."isActive"=false AND u."isActive" AND u."suspendedAt" IS NULL
        AND u."softDeletedAt" IS NULL;                                           -- 0
    SELECT count(*) FROM invite_codes i JOIN practices p ON p.id=i."practiceId"
      WHERE p."isActive"=false AND i."revokedAt" IS NULL
        AND (i."expiresAt" IS NULL OR i."expiresAt" > now()) AND i."usedCount" < i."maxUses"; -- 0
    SELECT count(*) FROM audit_logs
      WHERE action::text IN ('PRACTICE_UPDATED','PRACTICE_ARCHIVED','PRACTICE_RESTORED');  -- 0
    SELECT count(*) FROM audit_logs
      WHERE action::text='LOGIN_FAILED' AND "errorCode"='ACCOUNT_PRACTICE_ARCHIVED';     -- 0
    ROLLBACK;
    SQL

    # C1–C3 — string literals, never symbol names
    for s in ACCOUNT_PRACTICE_ARCHIVED practice_has_super_admin INVITE_PRACTICE_NOT_ADMITTING; do
      docker exec meddoc-pro-transcribe-md-1 sh -c "grep -rl '$s' .next/server | wc -l"
    done                                                                         # each >= 1

⚠️ **NO PRODUCTION FLOW IS EXERCISED TO VERIFY THIS.** Archiving a real practice
to prove the doors work is a class (d) act on production data, and no
declaration covers it. The full walk belongs on QA:

1. archive a synthetic practice through the route;
2. see its member refused at login and ejected mid-session;
3. see an invite into it refused;
4. restore it and see the member admitted.

## PROOF CARRIED BY THE PR

- **Unit gates.** `gate-admin6-practice-archive.test.ts`,
  `gate-admin6a-login-door.test.ts`, `gate-admin6a-invite-door.test.ts`,
  `gate-admin6a-practice-active-readers.test.ts`, and a widened
  `gate-admin3a-practice-write.test.ts`.
- **Real-Postgres proof.** `apps/transcribe-md/scripts/proofs/admin6-archive-restore-proof.ts`
  ran on a scratch database with all 117 migrations applied: **18 of 18 arms**,
  `🟢 all arms ran and passed`. It shows:
  - the `users` table is byte-identical across archive, restore and every
    refusal;
  - D2 refuses the session while archived and admits it after the restore;
  - the refusals write nothing;
  - a failed audit insert rolls the write back;
  - two concurrent archives produce one act and one audit row.
