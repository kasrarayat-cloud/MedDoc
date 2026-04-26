# Operational test scripts

Three Node scripts that act as production smoke / regression suites
for the admin surface. They live on the VPS at `/tmp/`, not in the
repo, because they are intentionally environment-coupled: they need
a live database, a real super-admin login cookie, and SSE/Playwright
connections to the running services.

| Script | Asserts | Origin |
|---|---|---|
| `/tmp/admin-audit.mjs` | 46 invariants for `/admin/*` (HTTP codes, ARIA roles, PHI redaction, tenant isolation, audit-row presence, SSE keep-alive). | Phase 6 dashboard build-out. |
| `/tmp/test-flows.mjs` | 19 end-to-end flows: resolve-threat → Active count drop, suspend-user round-trip, resolve HIPAA finding → Overview decrement → Resolved tab → reopen, audit-row write-back per action. | Phase 7A dashboard consistency sweep. |
| `/tmp/test-consistency.mjs` | 9 cross-API probes: HIPAA card matches /admin/hipaa list, threats banner matches /api/admin/threats, cent-match across `summary` + `byProvider` + `byUser` for 24h/7d/30d windows, audit-timeline buckets sum to stats total. | Phase 8 launch hardening. |

## Running

```bash
node /tmp/admin-audit.mjs
node /tmp/test-flows.mjs
node /tmp/test-consistency.mjs
```

Each script connects to `https://admin.quillmd.com` via the loopback
`--resolve` trick, logs in as `qa-audit@quillmd.local`, runs its
assertions, and exits non-zero on failure. They do not require Playwright
browsers — they use Playwright's `request` API plus direct `psql` calls.

## Phase 14 note (drift-resistance)

`test-flows.mjs` E5 picks the first open finding from `hipaa_findings`
to resolve. The Overview badge `data-open-count` is computed from
`severity IN ('critical','high','medium')` only — `low`-severity rows
exist in the table but don't move the badge (see
`apps/transcribe-md/src/app/admin/_lib/dashboard-data.ts:1207`). The E5
target picker therefore filters by the same severity set, otherwise
adding a new low-severity follow-up finding would silently break the
assertion.

## Why not in the repo?

These scripts hard-code the live host (`admin.quillmd.com`), use a
real super-admin password, and assume a running compose stack. Putting
them in the repo would invite either secret-leak or dead-code drift
when fixtures rebuild. Keeping them at `/tmp/` on the VPS makes their
operational scope explicit: they're deploy-time tools, not unit tests.

The Vitest + Playwright suites in `apps/meddoc-pro/tests/` cover the
in-repo regression layer. The three `/tmp/` scripts cover the
"is the deployed thing actually behaving correctly" layer.
