# Search-path v8 accepted-head integration verification

Timestamp: 2026-07-20T00:22:34Z

Scope: clean release integration branch only. No push, pull-request mutation,
production access, provider egress, or protected-worktree access occurred.

## Immutable identities

- Release branch: `release/template-twin-ga-20260719`
- Integration merge: `428c94225157d6c61d04147a648e643d5a4a241c`
- Integration tree: `252cb0b9f6769c9b7746473636bc1c6c89c4ae97`
- First parent: `b5b26e0bf5b59293a8f9387550444bb59d2673e8`
- Accepted component head: `79a00d7f3fa9513905966906e491235b16e6c641`
- Accepted component tree: `252cb0b9f6769c9b7746473636bc1c6c89c4ae97`
- Independent verdict: ACCEPT; P0/P1/P2 none
- Independent report SHA-256:
  `1e9938a5a232e5a64b65064d16f19c9b5edcfe45318401ab999a5064d8db9c22`
- Independent 66-entry manifest SHA-256:
  `1f38bf7280222798db8535219dcc7678da834a6bce5ff1c113aae828c3337f8f`

The merge result is byte-for-byte the accepted component tree.

## Merged-tree verification

- Template Twin library: PASS, 83 files / 893 tests.
- Strict TranscribeMD TypeScript: PASS.
- Changed contract-test ESLint: PASS.
- Changed TypeScript Prettier: PASS.
- Prisma validate and generate: PASS.
- PostgreSQL 16 fresh deploy: PASS, all 93 migrations.
- Release-control database role, signature, capability, concurrency, audit, and
  revocation suite: PASS; synthetic-only; final global state disabled.
- Search-path v8 idempotent replay: PASS.
- Terminal routine census: PASS, zero violations.
- Unpinned window-function negative: rejected fail closed as expected.
- Reserved-prefix aggregate negative: rejected fail closed as expected.
- Final v8 replay after fixture removal: PASS.
- Disposable PostgreSQL container and all synthetic fixture data: removed.
- Release worktree after verification: clean.

## Transparent fixture corrections

The first disposable migration attempt omitted the repository's legacy
`meddoc` role and reproduced the fixture-only failure already documented by the
independent reviewer. That isolated database was discarded, the complete role
fixture was installed, and a fresh 93-migration deployment passed.

An attempted second fresh database was created after the cluster-wide
post-migration release-security login role had been provisioned. The v2
migration correctly rejected that ordering. It was not used. The already clean
fresh-deploy database was renamed with the required test marker and the release
suite passed there. One intermediate invocation also correctly failed the
non-production database-name guard before any test mutation. These are fixture
setup observations, not product findings.

## Verdict

PASS for integration of the independently accepted search-path v8 head. This
does not authorize production deployment or rollout.
