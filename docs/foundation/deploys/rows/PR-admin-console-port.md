# §2.5 AUTHOR ROWS — the console port (`feat/admin-console-port`), ruling #310 step 3

**Written before the act**, at branch time, per ruling #184: a passenger
without author rows is a FINDING, not a pass. The PR number is not known yet;
rename this file to `PR-<n>.md` when the PR opens, with the body byte-identical.

**Lane:** Design/Admin. **CODE-ONLY — NO MIGRATION.** The four `AuditAction`
labels the port uses (`USER_CREATED`, `USER_UPDATED`, `USER_ROLE_CHANGED`,
`USER_DEACTIVATED`) already exist in `enum AuditAction` and in the initial
`CREATE TYPE`; only the TypeScript mirror in `lib/audit.ts` widened.

**Runtime files:** eight route files under `apps/transcribe-md/src/app/api/admin/users/**`
(six new — `deactivate`, `reactivate`, `profile`, `sessions`,
`sessions/[sid]/revoke`, and a `POST` added to `users/route.ts` — plus the
`unsuspend` orphan pre-check); `lib/last-owner-invariant.ts`
(`wouldOrphanMember`); `lib/audit.ts` (type only); the `/admin/users` UI, a new
`/admin/audit` page, and two nav links. `apps/meddoc-pro` also changes (its
grant block is deleted), but that app is not built or deployed by anything.

> **The one-line declaration:** *nothing but the image ids.* A deploy of this
> change writes no row. Every new write happens only when a SUPER_ADMIN clicks
> a new door afterwards, and those acts are audited individually.

## MUST CHANGE

| # | row | before | after | falsifier |
|---|---|---|---|---|
| **PORT-C1** | `transcribe-md` app and worker image ids | baseline | **new** | the thing being shipped |
| **PORT-C2** | the route keys `users:deactivate`, `users:reactivate`, `users:profile`, `users:sessions`, `users:sessions:revoke`, `users:create` in the shipped server bundle (`grep -rl` over `.next/server/app/api/admin/users`) | **0 of 6** | **6 of 6** | a key is a string literal passed to `adminApi()`, so it survives minification; one missing means that door did not ship |
| **PORT-C3** | DOM presence, NO mutation: `/admin/users` renders an **Add user** button; `/admin/audit` renders the heading **Audit trail**; the admin nav carries **Audit** and **Queues** | absent | present | read by loading the page as the synthetic smoke SUPER_ADMIN only — never by clicking a door on a real account |

## MUST NOT CHANGE

| # | row | expectation | falsifier |
|---|---|---|---|
| **PORT-N1** | clinical counts — visits, signed visits, patients | **= baseline** | never omitted; a code-only admin deploy that moves a clinical count has done something nobody asked for |
| **PORT-N2** | `_prisma_migrations` row count, and the newest `migration_name` | **= baseline** | this change carries no migration; movement means one rode unnamed |
| **PORT-N3** | `AuditAction` enum cardinality (`SELECT count(*) FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid WHERE t.typname = 'AuditAction'`) | **= baseline** | the port adds no label; the four it uses were already there |
| **PORT-N4** | `ledger_entries` row count, and the count of `kind = 'grant'` | **= baseline** | ⚠️ **THE MONEY ROW.** This change MOVES promo door 3 into a reachable route, but a deploy calls nothing. A grant appears only when a SUPER_ADMIN reactivates somebody, and then exactly one per practice ever (the global unique on `idempotencyKey`). Any grant row stamped between deploy start and the post-deploy read, with no matching `PROMO_GRANT_CREDITED {door:'reactivation'}` audit row, is the finding |
| **PORT-N5** | `users` row count; count with `"isActive" = false`; count with `"deactivatedAt" IS NOT NULL` | **= baseline** | a deploy creates, deactivates and reactivates no one |
| **PORT-N6** | `user_sessions` row count | **ordinary churn only** — logins and expiries move it; no admin revoke ran (`audit_logs` with `action = 'SESSION_EXPIRED' AND metadata->>'reason' = 'admin_revoke'` **= 0 new**) | a revoke nobody clicked |
| **PORT-N7** | new `audit_logs` rows with action in (`USER_CREATED`, `USER_UPDATED`, `USER_ROLE_CHANGED`, `USER_DEACTIVATED`) since deploy start | **0** | these are written only by the new doors, so any row before a deliberate click is the finding |
| **PORT-N8** | co-tenant HTTP status and the `meddoc-pro` service | unchanged; `meddoc-pro` stays down / 410 | the grant-block deletion in `apps/meddoc-pro` changes a file no image is built from; if anything started that app, #307's closure has been reversed |

## VERIFY — structural, mutating nothing

    # positive control FIRST — the instrument answers at all
    psql -tAc "SELECT count(*) FROM _prisma_migrations;"                       # > 0, = baseline after

    # N3 — label cardinality
    psql -tAc "SELECT count(*) FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid
               WHERE t.typname = 'AuditAction';"                               # = baseline

    # N4 — the money row
    psql -tAc "SELECT count(*), count(*) FILTER (WHERE kind = 'grant') FROM ledger_entries;"   # = baseline

    # N7 — no port-door audit rows before anyone clicked
    psql -tAc "SELECT count(*) FROM audit_logs
               WHERE timestamp >= '<deploy start>'
                 AND action IN ('USER_CREATED','USER_UPDATED','USER_ROLE_CHANGED','USER_DEACTIVATED');"  # 0

    # C2 — the doors shipped (inside the running app container, read-only)
    for k in users:deactivate users:reactivate users:profile users:sessions users:sessions:revoke users:create; do
      grep -rlF "$k" .next/server/app/api/admin/users >/dev/null && echo "$k present" || echo "$k MISSING"
    done

⚠️ **THE FULL WALK OF THESE DOORS IS QA's, NOT PRODUCTION's.** Deactivate →
reactivate (with the grant), create → reset-link, profile, sessions and revoke
are exercised on the isolated `meddoc-qa` stack against a byte-identical build,
on synthetic accounts. None is clicked on a real doctor's account in production
to prove the deploy — and a reactivation in production is a MONEY act (a ledger
grant), so it happens only when an operator means it.
