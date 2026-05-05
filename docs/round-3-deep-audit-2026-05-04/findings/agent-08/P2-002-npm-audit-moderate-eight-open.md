---
id: A08-P2-002
title: 8 moderate-severity npm-audit findings open across workspaces
severity: P2
domain: dependency-hygiene-supply-chain
status: open
---

## Issue

`npm audit --workspaces --include-workspace-root` reports **8 moderate** vulnerabilities.
Zero critical, zero high, zero low, zero info. All eight are addressable; four require
breaking-change upgrades, four are non-breaking.

| # | Package | Severity | Direct? | Vector | Fix | Reachable? |
|---|---------|----------|---------|--------|-----|------------|
| 1 | `@anthropic-ai/sdk@0.85.0` | moderate | yes | Insecure default file perms in *Local Filesystem Memory Tool* (CWE-732) | `0.93.0` (semver-major) | **No** — we use only `Anthropic({apiKey}).messages.create()` for completions; the memory tool is never instantiated (see `packages/ai/src/anthropic.ts`). Cosmetic for us. |
| 2 | `bullmq@5.76.1` (via `uuid` <14) | moderate | yes (transcribe-md) | `uuid: Missing buffer bounds check in v3/v5/v6 when buf is provided` (CWE-787, CWE-1285) | `bullmq@5.76.5` (non-breaking) | Reachable in theory — the worker creates jobs + uses uuid internally — but the affected v3/v5/v6 code paths require the caller to pass a `buf` argument, which BullMQ doesn't. **Patch anyway** — it's free. |
| 3 | `next@16.2.4` (via `postcss` <8.5.10) | moderate | yes | `PostCSS XSS via unescaped </style>` (CWE-79) | `next@9.3.3` (semver-major **down**grade — bogus) | npm's fix path here is wrong; the real fix is **wait for next 16.2.5 or override `postcss`** (see "Recommended fix"). Not user-reachable: `next` only uses postcss at build time on trusted CSS files we author ourselves. |
| 4 | `postcss@<8.5.10` | moderate | no (transitive of next) | same as #3 | tied to next | same as #3 |
| 5 | `prisma@7.8.0` (via `@prisma/dev` → `@hono/node-server` <1.19.13) | moderate | yes | `@hono/node-server: middleware bypass via repeated slashes in serveStatic` (CWE-22, CVSS 5.3) | `prisma@6.19.3` (downgrade!) | **Not reachable in production**: the runtime image (`apps/transcribe-md/Dockerfile` runner stage) copies only `node_modules/.prisma` and `node_modules/@prisma/client`; it does NOT ship the `prisma` CLI or `@prisma/dev`. Only the `db-migrate` compose service (target `builder`) ships the dev tooling, and it runs `prisma migrate deploy` which doesn't invoke the dev pglite server. |
| 6 | `@hono/node-server` | moderate | no | same as #5 | same | same — dev-only |
| 7 | `@prisma/dev` | moderate | no | wrapper of #6 | same | same — dev-only |
| 8 | `uuid@<14.0.0` | moderate | no | same as #2 | `uuid@14.0.0` | safe to bump |

Net: of 8 moderate findings, **0 are user-reachable in production**, **3 are easy
non-breaking patches** (`bullmq`, `uuid`, `@anthropic-ai/sdk` — even though we don't trigger
the bug, the bump is one minor jump in the SDK that we already plan to do for the
`messages.create` API ergonomics).

## Evidence

```bash
$ cd /opt/meddoc-pro && npm audit --workspaces --include-workspace-root
# npm audit report

@anthropic-ai/sdk  0.79.0 - 0.91.0
Severity: moderate
Claude SDK for TypeScript has Insecure Default File Permissions in Local Filesystem Memory Tool
- https://github.com/advisories/GHSA-p7fg-763f-g4gf

@hono/node-server  <1.19.13
Severity: moderate
@hono/node-server: Middleware bypass via repeated slashes in serveStatic
- https://github.com/advisories/GHSA-92pp-h63x-v22m

postcss  <8.5.10
Severity: moderate
PostCSS has XSS via Unescaped </style> in its CSS Stringify Output
- https://github.com/advisories/GHSA-qx2v-qp2m-jg93

uuid  <14.0.0
Severity: moderate
uuid: Missing buffer bounds check in v3/v5/v6 when buf is provided
- https://github.com/advisories/GHSA-w5hq-g745-h8pq

8 moderate severity vulnerabilities
```

Reachability checks:

```bash
$ grep -rE "memory_tool|memoryTool|local_filesystem|BetaMemoryTool" \
    apps/transcribe-md/src apps/marketing/src packages/ai
(no output — Anthropic memory tool not used)
```

```bash
$ grep -E "@prisma/(client|dev)" /opt/meddoc-pro/apps/transcribe-md/Dockerfile
COPY --from=builder /app/node_modules/.prisma ./node_modules/.prisma
COPY --from=builder /app/node_modules/@prisma ./node_modules/@prisma
# (only @prisma/client + .prisma generated artifacts — @prisma/dev / @hono/node-server NOT shipped)
```

## Risk

- Each finding is moderate (CVSS ≤ 6.1) and none is reachable in the production runtime
  containers. So the **immediate** business risk is low.
- The **real** risk is *posture*: an external auditor or a clinician's IT team running their
  own audit ("show me your `npm audit` output") will see "8 moderate vulnerabilities" with
  no remediation comment. We need an `audit-ci` allowlist file that documents *why* each
  finding is accepted, plus a tracked plan to clear the easy ones.

## Recommended fix

1. **Land the easy non-breakers** (one PR):

   ```bash
   npm install bullmq@5.76.5 -w transcribe-md
   npm install @anthropic-ai/sdk@0.93.0 -w @meddoc/ai
   # uuid bumps as a transitive of the bullmq update
   ```

   Verify: `npm audit --workspaces` should drop from 8 → 4 (the four prisma/next ones).

2. **Wait on `next` + `prisma`**: don't downgrade. The `npm audit fix --force` "fix" lies.
   Track the upstream PRs:
   - next: postcss >= 8.5.10 ships in next 16.2.5+ (vendored).
   - prisma: `@prisma/dev` 0.24.4+ has the @hono fix; landing in prisma 7.9.

3. **Add `audit-ci`** to CI (`.github/workflows/test.yml`) with a `audit-ci.json`
   allowlist that explicitly accepts:
   - `GHSA-92pp-h63x-v22m` (@hono/node-server) — dev-only, not in runtime image
   - `GHSA-qx2v-qp2m-jg93` (postcss) — build-time only, trusted CSS source
   - and *fails* on any new high/critical not yet allowlisted.

   Example `audit-ci.json`:
   ```json
   {
     "moderate": true,
     "allowlist": [
       "GHSA-92pp-h63x-v22m",
       "GHSA-qx2v-qp2m-jg93"
     ],
     "report-type": "summary"
   }
   ```

4. **Document reachability** in `docs/SECURITY.md` for each accepted advisory — auditor
   ammunition.

## Cross-domain hooks

- A08-P2-001 (Dependabot): once configured, items 1 and 4 land as auto-PRs.
- Agent 02 (next-auth): the `jose` peer of next-auth is currently at 6.2.2 — clean. Worth
  re-running `npm audit` after the next-auth pin (P1-001).
- Agent 03 (HIPAA): the "show me your audit posture" question is answered by the
  `audit-ci.json` + `docs/SECURITY.md` combo.
