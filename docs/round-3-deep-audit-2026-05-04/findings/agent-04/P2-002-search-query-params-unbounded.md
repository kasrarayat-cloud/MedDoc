---
id: A04-P2-002
title: Search query params lack `.max()` and feed `ILIKE %x%` / `pg_trgm.similarity()` — DoS-via-long-string
severity: P2
domain: Input validation / DoS
status: open
---

## Summary

Several search/list endpoints take a free-text `search` query param and pass it (parameterized but unbounded) into Postgres ILIKE or pg_trgm `similarity()` predicates. None of these schemas put a `.max()` on the search string, so the only ceiling is whatever Next or the upstream proxy enforces on URL length.

Specific cases:

1. **`apps/transcribe-md/src/app/admin/users/_lib/users-data.ts:122-130`** — server-rendered `/admin/users` page. `p.search` (typed `string` per `_types.ts:64-71`) is read directly from `searchParams.search` in `page.tsx:36` — no Zod, no length bound. It becomes `%${p.search.trim()}%` and is parameter-bound into 3 `ILIKE` predicates (email, name, practice name) inside a `$queryRawUnsafe` (lines 158-164). A 100 KB search term is parameter-safe (no SQL injection — params are `$1, $2, $3`) but fans out across email/name/practice indexes; ILIKE doesn't use the trigram index without `pg_trgm`'s `gin_trgm_ops` index on each column, so it's a sequential scan with one regex compile per row.

2. **`apps/transcribe-md/src/app/api/patients/route.ts:50-110`** — GET search uses `p.name` via `similarity(LOWER(p.name), LOWER(${search}))` and `ILIKE ${'%' + search + '%'}` (lines 67-89). The route does:
   ```ts
   const rawSearch = url.searchParams.get('search');
   const search = rawSearch && rawSearch.trim().length > 0 ? rawSearch.trim() : null;
   ```
   No length cap. `pg_trgm.similarity` on a multi-MB input hashes a quadratic number of trigram pairs — not catastrophic with the GIN index on the column, but the input itself is hashed each call.

3. **`apps/transcribe-md/src/app/api/admin/audit-logs/route.ts:31-47`** — `action`, `userId`, `targetType`, `cursor` all `z.string().optional()` with no `.max()`. `userId` is then used in a Prisma `where: { userId: q.userId }` clause; Postgres won't fail but the comparison is on a 100 KB string against a 64-char column. Negligible CPU but noisy.

4. **`apps/transcribe-md/src/app/api/admin/users/route.ts:23-35`** — `search` is `.max(200)`, `cursor` is `z.string().optional()` with no `.max()`. Cursor is parsed by `parseCursor` into a Date + string id; an over-long cursor is rejected as invalid by `parseCursor`, so this one is fine.

5. **`apps/transcribe-md/src/app/api/patients/fuzzy-match/route.ts:47-54`** — `name` is `.max(200)`. Good.

## Evidence

`apps/transcribe-md/src/app/admin/users/_types.ts:64-71`:
```ts
export interface ListParams {
  search: string;
  status: StatusFilter;
  role: RoleFilter;
  product: ProductFilter;
  page: number;
}
```

`apps/transcribe-md/src/app/admin/users/page.tsx:33-41`:
```ts
const sp = await searchParams;
const params: ListParams = {
  search: typeof sp.search === 'string' ? sp.search : '',  // <-- no length bound
  status: parseStatus(sp.status),
  ...
};
```

`apps/transcribe-md/src/app/admin/users/_lib/users-data.ts:122-130`:
```ts
if (p.search.trim()) {
  const q = `%${p.search.trim()}%`;
  params.push(q, q, q);
  ...
  where.push(`(u.email ILIKE ${a} OR u.name ILIKE ${b} OR pr.name ILIKE ${c})`);
}
```

`apps/transcribe-md/src/app/api/patients/route.ts:57-60, 82-85`:
```ts
const rawSearch = url.searchParams.get('search');
const search = rawSearch && rawSearch.trim().length > 0 ? rawSearch.trim() : null;
// ...
similarity(LOWER(p.name), LOWER(${search})) > ${SEARCH_SIMILARITY_THRESHOLD}
OR p."externalId" ILIKE ${'%' + search + '%'}
```

## Why P2

No SQL injection — every site parameter-binds. The damage ceiling is "burn DB CPU on a wildcard scan" and "consume ~100 KB of node memory per request when constructing the where clause". Compared to actual DoS primitives, modest. But the fix is a one-line `.max(200)` on each schema and there's no reason not to add it.

The /admin/users one is the most exposed because it's both unauthenticated-from-the-browser-sense (server-rendered, but anyone can hit a session-protected URL with their own session and pass query params) AND raw-SQL-built.

## Recommended fix

1. `apps/transcribe-md/src/app/admin/users/page.tsx:36` — wrap `sp.search` with `.slice(0, 200)` or run it through a Zod schema like the API routes.
2. `apps/transcribe-md/src/app/api/patients/route.ts:60` — add a 200-char cap on the trimmed search.
3. `apps/transcribe-md/src/app/api/admin/audit-logs/route.ts:31-47` — add `.max()` on `action` (max 50, AuditAction names are short), `userId` (max 64), `targetType` (max 64), `cursor` (max 100 — `<iso>|<id>` is ~60 chars).

## Cross-domain hooks

- Agent 09 (DoS): scope of the search endpoint's ceiling depends on how heavy the rate limits are.

## Files

- `/opt/meddoc-pro/apps/transcribe-md/src/app/admin/users/page.tsx`
- `/opt/meddoc-pro/apps/transcribe-md/src/app/admin/users/_lib/users-data.ts`
- `/opt/meddoc-pro/apps/transcribe-md/src/app/api/patients/route.ts`
- `/opt/meddoc-pro/apps/transcribe-md/src/app/api/admin/audit-logs/route.ts`
