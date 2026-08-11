-- ===========================================================================
-- FOUNDATION B7 — THE `CHECKOUT_*` AuditAction VALUES.
-- ---------------------------------------------------------------------------
-- RELAY B7: "The `ADMIN_*`/`CHECKOUT_*` audit labels ship as a Prisma enum
-- migration — a TS union edit alone is silently discarded (`535d30d9`)."
-- (`ADMIN_*` belongs to A1; this migration carries B7's half.)
--
-- ⚠️ THIS IS THE THIRD LAYER, AND IT IS THE ONE THAT KEEPS BEING MISSED.
-- `audit_logs.action` is a Postgres ENUM. A new label needs THREE edits and
-- each layer looks sufficient from the one above it:
--
--   the TypeScript union in `lib/audit.ts`   → `tsc` is happy without this file
--   the Prisma enum in `schema.prisma`       → `prisma validate` is happy too
--   THIS FILE                                → the only one the database reads
--
-- It has now shipped wrong three times: `535d30d9` (2026-08-03, a sign refusal
-- whose audit row silently did not write), and twice on 2026-08-06 — attempt 1
-- landed in `audit.ts` only because an anchor missed on indentation, attempt 2
-- landed in BOTH source files and still not in the database, passing
-- `prisma validate`, `tsc` and 3192 unit tests while the app logged
-- `invalid input value for enum "AuditAction"` and swallowed it, because
-- `logAudit` is deliberately fire-and-forget.
--
-- B7 additionally ships `gate-audit-enum-migration.test.ts`, which compares the
-- labels in `schema.prisma` against the labels reachable through the migration
-- history — so this layer is now checked by something rather than remembered.
--
-- ---------------------------------------------------------------------------
-- WHY `ADD VALUE IF NOT EXISTS` AND NOT A NEW TYPE
-- ---------------------------------------------------------------------------
-- Matching the 37 prior `ALTER TYPE "AuditAction"` migrations in this
-- directory. `IF NOT EXISTS` makes the statement idempotent, which matters
-- because a failed deploy can leave a migration half-applied and Postgres does
-- not allow `ADD VALUE` inside a transaction block on older versions.
--
-- ⚠️ AND THE LABELS CANNOT BE REMOVED LATER. Postgres has no
-- `ALTER TYPE … DROP VALUE`. Adding an enum value is effectively permanent, so
-- three is a considered number rather than a convenient one: credited, refused,
-- and duplicate are three genuinely different facts that an operator asks three
-- different questions about. A single `CHECKOUT_WEBHOOK_EVENT` with the outcome
-- buried in metadata would have been cheaper here and unqueryable forever after.
-- ===========================================================================

-- A `topup` row was appended to `ledger_entries`. The one that means money.
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'CHECKOUT_TOPUP_CREDITED';

-- A validly-signed event was declined, with the reason in metadata. Emitted
-- ONLY after signature verification — see the route header for why an
-- unauthenticated endpoint must not write a row per unverified request.
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'CHECKOUT_TOPUP_REFUSED';

-- A redelivery hit the GLOBAL unique on `ledger_entries.idempotencyKey`. This
-- is the idempotency working; it is recorded so retry behaviour is observable
-- rather than inferred from an absence.
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'CHECKOUT_TOPUP_DUPLICATE';
