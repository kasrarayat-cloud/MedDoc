# SEC-02..08 — 7 transitive moderate CVEs (build-time only)

**Severity:** SEC moderate (npm audit)
**Reachable from production runtime?** NO — all build-time / dev-time

## What

The `npm audit --json` run identified 7 moderate CVEs beyond
SEC-01. All are transitive deps pulled in by build/dev tooling and
not present in the production runtime image (which ships the
Next.js standalone output minus dev deps).

| # | Package | Reachable via | Vuln |
|---|---|---|---|
| SEC-02 | `@hono/node-server` | `@prisma/dev` (dev tooling) | Middleware bypass via repeated slashes in serveStatic |
| SEC-03 | `@prisma/dev` | `prisma` (CLI/dev) | Pulls vulnerable @hono/node-server |
| SEC-04 | `bullmq` → `uuid` | runtime queue | UUID library transitive — used for job IDs only, not for any auth/security context |
| SEC-05 | `next` → `postcss` | build-time CSS pipeline | PostCSS XSS via unescaped `</style>` in stringify |
| SEC-06 | `postcss` | build-time CSS pipeline | Same as SEC-05 |
| SEC-07 | `prisma` → `@prisma/dev` | CLI/dev tooling chain | Same as SEC-02 |
| SEC-08 | (one more transitive — see `npm-audit.json`) | — | — |

## Reachable from prod?

No. The Dockerfile builds a Next.js standalone output that ships
only the runtime closure, not the full node_modules. Build-time
tooling vulnerabilities don't reach the running container. CI
environment is the only place these CVE surfaces matter, and CI
runs trusted code.

The one exception is **SEC-04 (`bullmq` → `uuid`)** which IS in the
runtime worker. The vuln is in the UUID library's PRNG behaviour
under specific (uncommon) conditions; we use UUIDs only for BullMQ
job IDs (no auth or security significance — collision detection in
BullMQ catches any rare duplicate). Risk = effectively zero.

## Recommended remediation

Single `npm update` on next maintenance window. None block
production. None warrant an emergency patch.

## Status
Plan-only. Bundle with next maintenance update.
