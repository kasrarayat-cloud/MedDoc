# Agent 08 — Dependency Hygiene & Supply Chain · Summary

## Severity counts

| Severity | Count | IDs |
|---|---|---|
| P0 | 0 | — |
| P1 | 2 | A08-P1-001, A08-P1-002 |
| P2 | 4 | A08-P2-001, A08-P2-002, A08-P2-003, A08-P2-004 |
| P3 | 3 | A08-P3-001, A08-P3-002, A08-P3-003 (positive) |
| **Total** | **9** | |

## Top 3 findings
1. **A08-P1-001 — `next-auth@5.0.0-beta.31` floats on the prod auth path.** Both `apps/transcribe-md` and `packages/auth` declare `^5.0.0-beta.30`. v5 has been beta ~14 months. Pin exactly + add root `overrides`.
2. **A08-P1-002 — Every Docker base image uses a floating tag.** All four Dockerfiles use `node:22-alpine`; compose pulls `minio:latest`, `redis:7-alpine`, `pgvector:pg16`, `caddy:2-alpine`, `postgres-backup-local:16` — none SHA256-pinned. Reproducibility hole.
3. **A08-P2-001 — No Dependabot/Renovate.** `.github/` has only workflows; zero automated dep-update cadence with 1,157 deps and 8 open audit findings.

## Vulnerability matrix

`npm audit --workspaces --include-workspace-root`: **0 critical · 0 high · 8 moderate · 0 low · 0 info**. Lockfile dep counts: prod 643, dev 363, optional 173, peer 56, total 1,157. `npm ls --all` tree: 2,531 lines, 51 extraneous packages.

| Advisory | Pkg | Reachable in prod runtime? |
|---|---|---|
| GHSA-p7fg-763f-g4gf | @anthropic-ai/sdk 0.85 (memory tool perms) | **No** — memory tool unused, only `messages.create` |
| GHSA-w5hq-g745-h8pq | uuid <14 (via bullmq) | very low — buf path not exercised |
| GHSA-qx2v-qp2m-jg93 | postcss <8.5.10 (via next) | **No** — build-time, trusted CSS |
| GHSA-92pp-h63x-v22m | @hono/node-server <1.19.13 (via @prisma/dev) | **No** — runtime image ships only `@prisma/client` + `.prisma/`, not the `prisma` CLI / `@prisma/dev` |

Net runtime exposure: **zero**. All 8 are dev/build-time or unused-feature.

## Positives
1. **No `patches/` dir** — zero monkey-patches.
2. **No `git+https://…` deps** in lockfile — every package resolves from npm registry.
3. **Only 8 packages with install scripts** — all reputable.
4. **License sweep clean** — 1,025 manifests, zero GPL/AGPL/SSPL/BUSL.
5. **Multi-stage Dockerfiles + non-root `USER nextjs`/`worker`** — minimal attack surface modulo the tag-pinning gap.
6. **Anthropic SDK advisory non-reachable** — confirmed via grep that no source imports memory_tool / BetaMemoryTool / local_filesystem.

## Cross-domain hooks
- **Agent 02 (auth)**: P1-001 pin should land alongside any next-auth refactor.
- **Agent 05/12 (HIPAA)**: P1-002 (SHA256 pinning) and P2-004 (license attribution doc) directly answer two standard auditor questions.
- **Agent 07 (build)**: P2-003 traces stale `.next/standalone/` package.json files (May 2-3) as proximate cause of 51 extraneous packages — build-cache hygiene fix.
- **Agent 11 (CI)**: 4 gates suggested — `lockfile-lint`, `audit-ci.json` allowlist, `hadolint` base-image-pin check, and the Dependabot YAML itself.
- **Agent 12 (decommissioned `apps/meddoc-pro` cleanup)**: deleting that workspace simplifies P3-002, P2-003, and shrinks the next-auth manifest list in P1-001.

## Audit commands (all read-only — lockfile NOT mutated)

```
npm audit --workspaces --include-workspace-root [--json]
npm ls --workspaces --all
npm outdated --workspaces
npm config get ignore-scripts    # = false
```
