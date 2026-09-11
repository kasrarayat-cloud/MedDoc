# §2.5 AUTHOR ROWS — admin pages gate their own data (owner ruling #310)

**Written at PR-open time, before the act.** Branch
`fix/admin-pages-gate-own-data`, based on `origin/main` `158af24f`.

**Lane:** security hotfix. **CODE-ONLY — no migration, no schema change, no
env/flag change.** A code-only deploy's declaration is one line — *nothing but
the image ids* — and the rows below state what the image change must and must
not do.

## What ships

`/admin/*` pages no longer rely on `app/admin/layout.tsx` as their only gate.
Next 16 does not re-run a layout on an RSC subtree refetch, so an
unauthenticated `RSC: 1` request with a crafted `Next-Router-State-Tree`
rendered the page alone and returned its server data (reproduced on the shipped
QA image: `GET /admin/hipaa` → 200 with `hipaaFinding` rows, no cookie, no
audit row). The check now lives in `app/admin/_lib/admin-gate.ts`, called
first by the layout, every admin `page.tsx`, and every exported async data
function under `app/admin/**/_lib`.

## MUST CHANGE

| # | row | how it is judged |
|---|---|---|
| C1 | The crafted RSC request to `/admin/hipaa` returns **404** unauthenticated (no cookie) | post-deploy probe (lead's job — not run by the author against production): `curl -s -o /dev/null -w '%{http_code}' -H 'RSC: 1' -H 'Next-Router-State-Tree: <url-encoded ["",{"children":["admin",{"children":["hipaa",{"children":["__PAGE__",{}]},null,"refetch"]}]}]>' https://<admin host>/admin/hipaa` → `404` (was `200`) |
| C2 | The same probe against `/admin/threats` returns **404** | same probe, leaf `threats` |

## MUST NOT CHANGE

| # | row | how it is judged |
|---|---|---|
| N1 | **Clinical counts** — visits, patients, signatures | identical before/after; this change touches no clinical path and writes nothing |
| N2 | **Admin page rendering for a real SUPER_ADMIN** (active, MFA-enrolled, session < 12h) | unchanged: same pages, same chrome (`min-h-screen bg-linear-bg text-linear-text`), same data |
| N3 | A plain (non-RSC) unauthenticated `GET /admin/hipaa` | stays **404** (control) |
| N4 | An un-enrolled SUPER_ADMIN on `/admin/*` | same redirect as before: `/settings/security/mfa?reason=super_admin_required` |
| N5 | `ADMIN_DASHBOARD_ACCESS` audit rows | still **one** per admin page render (request-cached; the layout and page share one row) |
| N6 | `/api/admin/*` for a SUPER_ADMIN | unchanged (every route is still wrapped by `adminApi()`; the two routes that import `dashboard-data` still return 200) |

## Behaviour changes a reader should know are deliberate

- The page gate now reads `products` / `isActive` / `mfaEnabled` **fresh from
  the DB** in one row read. The layout used to trust a JWT-carried `products`
  claim when present and did not check `isActive`. So a revoked or deactivated
  SUPER_ADMIN is refused immediately instead of at JWT refresh.
- An `auth()` that throws on the admin gate is treated as no session (404),
  matching `adminApi()`, instead of a 500.
- Inside `adminApi()` a refusal from a data helper's own gate
  (`AdminAccessDeniedError`) returns the usual silent 404 instead of a 500.
  Reachable today only by an **un-enrolled** SUPER_ADMIN calling
  `/api/admin/threats` or `/threats/history` (`adminApi` on `main` does not
  check MFA; the helper verdict does). Those two routes were 200 for that
  caller before; they are now 404.

## Rollback

Revert the merge commit. There is no data to restore: the change writes nothing
new, and the audit rows it writes have the same shape as before.
