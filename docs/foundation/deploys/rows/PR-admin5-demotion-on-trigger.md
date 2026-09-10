# §2.5 AUTHOR ROWS — branch `feat/admin5-demotion-on-trigger` (ADMIN-5 + ADMIN-5a)

**Written before the act**, per the ADMIN-1 board filing and ruling #184: a
passenger without author rows is a FINDING, not a pass. The PR number is not
known at the time of writing; rename this file to `PR-<n>.md` when the PR opens
(`git mv`, body byte-identical — verify by sha, not by eye).

**Lane:** Design/Admin, under ruling #310. **⚠️ MIGRATION-CARRYING** —
`20260910120000_admin5_practice_member_removed`:

    ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'PRACTICE_MEMBER_REMOVED';

⚠️ **PERMANENTLY IRREVERSIBLE** — Postgres has no `ALTER TYPE … DROP VALUE`
(ruling #198: an irreversible act takes the STRICT declaration). It is the ONLY
schema change. The last-owner trigger (`20260907040000`) is NOT touched: no
function, trigger, column, table or constraint moves.

**Runtime files:** `actions/practice-members.ts` (owner demotion opened;
`removeMemberAction`, `transferOwnershipAction` new), `lib/last-owner-invariant.ts`
(`classifyGuardError`, `SOLE_MEMBER_REFUSAL`), `lib/admin-last-owner-refusal.ts`
(new), `api/admin/users/[id]/suspend` and `/soft-delete` routes,
`api/settings/delete-account/route.ts`, `lib/audit.ts` (split into
`buildAuditRow` / `publishAuditRow` / `logAudit`, behaviour unchanged for every
other caller), `lib/practice-admin.ts`, `lib/practice-roles.ts`,
`app/settings/practice-members-panel.tsx`.

## THE BASELINE — CAPTURED BY THE DEPLOYING SESSION, READ-ONLY, BEFORE THE ACT

This branch did NOT read production (its brief forbids it). The deploying
session writes the `before` column from the queries under VERIFY while it is
still true. For orientation only, the last JUDGED record
(`20260909-7445308b-JUDGED.md`) read visits **58**, patients **46**, signed
**40**, practices **199**, applied migrations **117** — last recorded, **not
re-measured here**. This branch adds the 118th repo migration.

## MUST CHANGE

| # | row | before | after | falsifier |
|---|---|---|---|---|
| **A5-C1** | `pg_enum` label `PRACTICE_MEMBER_REMOVED` on `AuditAction` | **0** | **1** | this IS the migration. Absent means every removal's audit row is rejected by Postgres and swallowed by `logAudit` — the three-layer failure the enum gates exist for |
| **A5-C2** | `AuditAction` cardinality | **B** (captured) | **B + 1** | more than +1 means a second migration rode unnamed; 0 means C1 failed. (On a scratch DB with every repo migration: 161 → 162) |
| **A5-C3** | `_prisma_migrations` carries `…20260910120000_admin5_practice_member_removed`, finished | **0** | **1** | a label without a recorded migration arrived by a hand no ledger saw |
| **A5-C4** | string literal `PRACTICE_MEMBER_REMOVED` in the shipped SERVER bundle (`.next/server`) | **0 files** | **≥ 1** | a string literal survives minification, so 0 means the removal door did not ship |
| **A5-C5** | string literal `transfer-ownership` (the panel's test id) in the shipped CLIENT bundle (`.next/static`) | **0 files** | **≥ 1** | the transfer control did not ship |
| **A5-C6** | image ids (transcribe-md, worker) | old | new | a code deploy that does not move the image shipped nothing |

## MUST NOT CHANGE

| # | row | expectation | falsifier |
|---|---|---|---|
| **A5-N1** | **clinical counts** — visits, signed visits, patients | **unchanged** | **never omitted (§2.5).** Nothing in this branch writes a visit, a signature or a patient. The delete-account change only NARROWS what can be deleted (it refuses shared practices by name); any movement is something nobody asked for |
| **A5-N2** | `users` count; `practices` count | **unchanged** | a deploy moves no user row. Removal writes `isActive=false` on a click, never at deploy, and never deletes a row |
| **A5-N3** | triggers on `users` — `users_last_owner_guard_after_write`, `users_no_orphan_member_after_insert` | **2**, both `tgenabled = 'O'` | the enforcer this whole design stands on. A disabled or missing trigger makes every friendly refusal the only line |
| **A5-N4** | `md5(prosrc)` of `users_last_owner_guard` and `users_no_orphan_member` | **unchanged** | this migration touches the enum only; a moved function body is an unnamed change to the enforcer |
| **A5-N5** | practices with a LIVE member and ZERO active owners (the forbidden state) | **0 → 0** | the invariant #210 exists for |
| **A5-N6** | `audit_logs` rows with action `PRACTICE_MEMBER_REMOVED` | **0 → 0** at deploy time | the label is new; a row at deploy time was written by something other than an owner's click |
| **A5-N7** | users with `isActive = false` | **unchanged** | removal and transfer-and-leave write this on a CLICK; movement at deploy means a door fired without one |

## BEHAVIOUR THAT CHANGES FOR PEOPLE (declared, so the judge does not have to infer it)

- A practice OWNER can demote another owner, remove any other member, and hand
  the practice on (Transfer ownership: promote a live member, then step down or
  leave, in one transaction). The last owner still cannot leave a practice with
  members — the TRIGGER refuses; the page says why.
- The SUPER_ADMIN `suspend` / `soft-delete` last-owner 409 is now AUDITED
  (`PRACTICE_ADMIN_REFUSED`, `source: precheck`), and the race the out-of-lock
  pre-check cannot see returns 409 `LAST_OWNER` (`source: trigger`) instead of
  a raw 500.
- Self-service account deletion REFUSES BY NAME (409 `PRACTICE_HAS_MEMBERS` /
  `PRACTICE_HAS_FORMER_MEMBERS`) when any other user row is in the practice.
  Before this change that case returned a generic 500 after attempting a
  practice-wide purge that only the users→practices FK rolled back — so no
  previously-successful deletion is refused. A SOLO practice is deleted exactly
  as before, and its `ACCOUNT_DELETED` row now rides the transaction (no row
  survives a refused deletion).

## VERIFY — structural, mutating nothing

    # positive control FIRST — the instrument answers about this enum at all
    psql -tAc "SELECT count(*) FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid
               WHERE t.typname='AuditAction';"                               # B -> B+1  (C2)
    psql -tAc "SELECT count(*) FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid
               WHERE t.typname='AuditAction' AND enumlabel='PRACTICE_MEMBER_REMOVED';"  # 0 -> 1 (C1)
    psql -tAc "SELECT count(*) FROM _prisma_migrations
               WHERE migration_name='20260910120000_admin5_practice_member_removed'
                 AND finished_at IS NOT NULL;"                               # 0 -> 1 (C3)

    # N3 / N4 — the enforcer is present, armed, and byte-unchanged
    psql -tAc "SELECT tgname, tgenabled FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
               WHERE NOT t.tgisinternal AND c.relname='users' ORDER BY 1;"
    psql -tAc "SELECT proname, md5(prosrc) FROM pg_proc
               WHERE proname IN ('users_last_owner_guard','users_no_orphan_member') ORDER BY 1;"

    # N5 — the forbidden state
    psql -tAc "SELECT count(*) FROM (SELECT p.id FROM practices p JOIN users u ON u.\"practiceId\"=p.id
               GROUP BY p.id HAVING count(*) FILTER (WHERE users_is_active_owner(u)) = 0
                                AND count(*) FILTER (WHERE users_is_live_member(u)) > 0) z;"   # 0 -> 0

    # N1 / N2 / N6 / N7
    psql -tAc "SELECT (SELECT count(*) FROM transcribe_visits),
                      (SELECT count(*) FROM transcribe_visits WHERE status='SIGNED'),
                      (SELECT count(*) FROM users), (SELECT count(*) FROM practices),
                      (SELECT count(*) FROM audit_logs WHERE action='PRACTICE_MEMBER_REMOVED'),
                      (SELECT count(*) FROM users WHERE NOT \"isActive\");"

    # C4 / C5 — the bundles (string literals survive minification)
    grep -rl 'PRACTICE_MEMBER_REMOVED' .next/server | wc -l                  # >= 1
    grep -rl 'transfer-ownership' .next/static | wc -l                       # >= 1

⚠️ **Confirm the visits table name and the SIGNED spelling against the judged
record's own query before using the N1 line** — it is written here from the
schema, not copied from a query that has run against production.

## ROLLBACK

Code: redeploy the previous image. **The enum label stays** (irreversible) and is
harmless to the old code — its TypeScript union never names it, so nothing
writes it. The trigger was never touched, so there is nothing to roll back in
the enforcer.

## OWED BEFORE MERGE

- The adversarial (refutation) pass over the finished diff (#310 keeps the proof
  burden unchanged).
- The deploy cross-references held declarations (§2.5): this branch changes
  `lib/audit.ts`, which every audited route imports.
