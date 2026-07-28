# npm audit baseline — 2026-05-06T06:41:54Z

- Source: `npm audit` against the monorepo root (covers all workspaces
  via `npm workspaces`).
- Branch: `feat/pr-k-supply-chain-hardening`
- HEAD at audit: `41edf2a` (PR-K base).
- Pre-PR-K verdict: **0 high + 0 critical** across the whole monorepo;
  the CI gate added in PR-K (`--audit-level=high`) passes cleanly.

## Summary by severity (root + all workspaces)

| Severity | Count |
|---|---|
| critical | **0** |
| high | **0** |
| moderate | 8 |
| low | 0 |
| info | 0 |
| **total** | **8** |

## Per-workspace breakdown

| Workspace | total | critical | high |
|---|---|---|---|
| `/` (root) | 8 | 0 | 0 |
| `apps/transcribe-md` | 8 | 0 | 0 |
| `apps/marketing` | 2 | 0 | 0 |
| `packages/db` | 3 | 0 | 0 |
| `packages/auth` | 5 | 0 | 0 |
| `packages/types` | 0 | 0 | 0 |
| `packages/ai` | 4 | 0 | 0 |
| `packages/shared` | 0 | 0 | 0 |

(Per-workspace counts overlap because shared deps live in the
hoisted root `node_modules`. Root is the canonical figure.)

## The 8 moderate vulnerabilities

None are auto-fixed in PR-K — package upgrades can break things.
Each is documented + recommended-fix-scoped here so the next
upgrade cycle has a punch list. None block launch (no high/critical;
all moderate).

| # | Package | Via | Recommended fix scope |
|---|---|---|---|
| 1 | `@anthropic-ai/sdk` | Claude SDK for TypeScript has insecure default file permissions in Local Filesystem Memory Tool | small — bump SDK; we don't use the local-filesystem memory tool, so practical impact for QuillMD is `none` |
| 2 | `@hono/node-server` | Middleware bypass via repeated slashes in serveStatic | small — bump; transitive via `@prisma/dev`. We don't expose `serveStatic` in production traffic (Caddy fronts everything) |
| 3 | `@prisma/dev` | Transitive — pulls `@hono/node-server` | resolves with #2 |
| 4 | `bullmq` | Transitive — pulls `uuid` | resolves with #8 |
| 5 | `next` | Transitive — pulls `postcss` | resolves with #6 (Next minor bump or postcss patch) |
| 6 | `postcss` | XSS via unescaped `</style>` in CSS Stringify Output | small — patch; postcss CSS-stringify path is used at build time, no runtime exposure to user-controlled CSS |
| 7 | `prisma` | Transitive — pulls `@prisma/dev` | resolves with #3 |
| 8 | `uuid` | Missing buffer bounds check in v3/v5/v6 when `buf` is provided | small — bump; we don't use the v3/v5/v6 entry points (uuid v4 default), so practical impact is `none` |

**Practical risk on QuillMD's surface:** all 8 advisories describe
reachability paths the product doesn't actually exercise:

- Caddy fronts every external request → `serveStatic` middleware
  bypass (#2/#3) is unreachable.
- Postcss runs at `next build` time with vendor-controlled CSS
  inputs — no user input flows through the CSS stringify path.
- The `@anthropic-ai/sdk` Local Filesystem Memory Tool is opt-in;
  we don't enable it.
- `uuid` v3/v5/v6 with a user-supplied buffer is the vulnerable
  entrypoint; QuillMD calls the v4 default.

That said, the 8 deserve clearance in normal Dependabot rotation.
None are launch-blockers.

## CI gate added in PR-K

`.github/workflows/test.yml` gains a new `audit` job that runs
`npm audit --audit-level=high --workspaces` on every PR. The gate:

- **Fails the PR** when a NEW high or critical vulnerability appears
  (above the documented baseline of 0 / 0).
- Tolerates the 8 existing moderate vulnerabilities (they're below
  the threshold).
- Runs on every PR + the post-merge main push.

This closes the "BAA conversation" question: "How do you track new
dependency vulnerabilities + ensure they don't ship to production?"
Answer: Dependabot opens a PR; the CI audit gate fails the PR if
any high/critical land; Kasra reviews + ships.

## Review cadence

- **Daily** (Dependabot npm schedule): minor + patch upgrades
  grouped by workspace.
- **Weekly** (Dependabot github-actions + docker schedule): action
  pins + Dockerfile base-image digest bumps.
- **Per-PR** (this gate): fail-fast on any new high/critical vuln.

## Out of scope for PR-K

- Auto-fix any of the 8 moderate vulns above (could break things;
  next dep-upgrade cycle handles them).
- Apply to `apps/meddoc-pro` (memory #9 — out of project scope).

— end of baseline —
