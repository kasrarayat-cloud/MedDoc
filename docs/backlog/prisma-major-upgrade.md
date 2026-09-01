# DEBT — the Prisma major upgrade

**Filed 2026-09-01 by ruling #163 B(ii).** This item is the **retirement
condition** of a live exception in `scripts/audit-exceptions.json`. It is not a
wish-list entry: while it is open, the npm-audit gate is passing an advisory it
would otherwise refuse.

## What is excepted, and why the exception is honest

`GHSA-3f6p-5ww8-9rcr` — *MySQL2: Auth Plugin Downgrade to mysql_clear_password
Leaks Plaintext Credentials*, HIGH.

**Measured, not asserted:**

| claim | evidence |
|---|---|
| this is a Postgres application | `packages/db/prisma/schema.prisma` declares `provider = "postgresql"` |
| nothing loads the driver | no file under `apps/*/src` or `packages/*/src` imports `mysql2` or `mysql` |
| it arrives via the CLI, not the runtime | `mysql2` is declared by `node_modules/prisma`; `prisma` is a **devDependency** in every `package.json` that names it — root, `apps/meddoc-pro`, `packages/db` |
| the shipped runtime is a different package | `@prisma/client` is the dependency that ships, and this advisory is not about it |

The advisory describes an auth-plugin downgrade leaking plaintext credentials to
a MySQL server. There is no MySQL server, no MySQL connection string, and no
code path that constructs one.

⚠️ **AND THE ONE THING THAT IS NOT OBVIOUS:** `npm audit --omit=dev` reports
`prisma` as a **direct HIGH** anyway. That is why an exception is needed at all
rather than the finding simply not appearing — the gate does not agree that a
devDependency is out of scope here, and rather than argue with the instrument
the disposition is written down where the next reader will find it.

## Why it is not just fixed

`npm audit fix` offers exactly one remedy: a **Prisma major**. That is the ORM
for the entire clinical database — schema client, migration engine, every query
path in the product. It is scheduled under the clinical-DB bar (its own
declaration, its own adversarial pass, its own §2.5 deploy), not taken as a
lockfile bump at the end of an unrelated session.

## Definition of done

1. Prisma and `@prisma/client` on the major that carries a patched `mysql2`.
2. `npx prisma migrate status` clean against production, and the standing
   invariant checks green.
3. **The exception entry is DELETED from `scripts/audit-exceptions.json`.**
   `scripts/audit-gate.mjs` fails on a stale exception, so this step is not
   optional — leaving the entry behind turns the gate red and says why.

## Scope notes for whoever picks it up

- `mysql2` is transitive through the `prisma` CLI. Confirm after the bump that
  it is gone or patched, rather than assuming the major carried it.
- The advisory id is the key. If a **different** advisory appears on `mysql2` or
  `prisma` before this lands, the gate blocks it — by design. That is a new
  decision, not a continuation of this one.
