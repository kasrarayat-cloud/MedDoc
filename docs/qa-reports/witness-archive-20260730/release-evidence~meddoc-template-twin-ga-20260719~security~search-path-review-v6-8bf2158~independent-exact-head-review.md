# Independent exact-head review — search-path terminal contract v7

## Verdict

**REJECT** — exact head `8bf2158db7680a97f52b4338d54ff1912fcb7468` has a P1 completeness defect in the database terminal census and later-migration static gate.

## Exact identity and scope

- Base: `b5b26e0bf5b59293a8f9387550444bb59d2673e8`
- Head: `8bf2158db7680a97f52b4338d54ff1912fcb7468`
- Head tree: `08ee78b7d5b70a0b4653ecde57220047c33760ea`
- Detached review worktree: `/home/claude/release-reviews/search-path-v6-8bf2158`
- Opening and closing `git status --porcelain=v2 --untracked-files=all`: empty
- Diff: seven additive commits; five intended files; no implementation, commit, merge, push, or deployment was performed by the reviewer.

## Findings

### P1-A — PostgreSQL window functions are omitted from the terminal census

The v7 terminal migration restricts its census to `pg_proc.prokind IN ('f', 'p')`. PostgreSQL stores window functions created with `CREATE FUNCTION ... WINDOW` as `prokind = 'w'`. A PostgreSQL 16 fixture created a synthetic public Template Twin-prefixed window function with `proconfig IS NULL`; the exact v7 `DO` block returned successfully instead of failing closed.

PostgreSQL 16 also confirmed that these objects accept `SET/RESET search_path` through both `ALTER FUNCTION` and `ALTER ROUTINE`. The independent static detector correctly classified all tested PostgreSQL-valid create/alter window-function forms, but the v7 runtime census itself does not cover them.

Impact: the claimed complete installed function/procedure boundary is incomplete and can accept an unpinned function shape.

### P1-B — unsupported aggregates under the reserved prefix are silently ignored

PostgreSQL stores aggregates in `pg_proc` as `prokind = 'a'`. A synthetic public Template Twin-prefixed aggregate was accepted, had no `proconfig`, and was ignored by the exact v7 block. PostgreSQL rejects attempts to configure an aggregate through `ALTER ROUTINE`, so aggregates cannot satisfy the fixed-path invariant and must be prohibited under the reserved prefix rather than treated as path-configurable routines.

The later-migration detector returned an empty violation list for a PostgreSQL-valid `CREATE AGGREGATE public.template_twin_*` fixture. The fail-closed boundary therefore needs explicit handling for aggregate creation and namespace-entry forms as well as a runtime absence assertion.

This is a second facet of the same P1 census-completeness defect.

### Other severities

- P0: none found.
- P2: none found.

## Independent detector and manifest evidence

- Exact detector source SHA-256: `28eae74d3013395a998799f43b60ec9fd0b228468c904b99c5de5285393bcde2`.
- Frozen 40-case corpus SHA-256 `60aeec2a6b38e271a11e38cb3aafd1df69bb92ff72d4779c9e994d4ddfdd8acc`: 40/40, zero false negatives, zero false positives.
- Frozen 46-case corpus SHA-256 `2fc5bc7672d6b7a1487eeba8baaab908a7d6dc719a0d253b53418be82e7bbdf6`: 46/46.
- Frozen 36-case corpus SHA-256 `dcd8233a39e9a4dba2819f7566a773e01abae10f7d8b456c84934227ae4b27fd`: 36/36, zero false negatives, zero false positives.
- New 29-case PostgreSQL-valid/decoy corpus SHA-256 `765ed167c3231c7a293c4ef0d38823431fa877efeff2467ba7edb93c6d1219b3`: 29/29, including quoted `LANGUAGE` forms and window-function create/alter forms.
- Unsupported aggregate detector fixture SHA-256 `c02718bb819f57c3dff78202da2b765f7ad7403adb3dbc1c1f8b0505880ab03a`: expected fail-closed rejection, actual `[]`.
- Immutable manifest SHA-256: `6de7df3ca701a1628290f06b7ec089490d2f434b09e3c774d10e2363a32902b7`.
- Independent manifest proof: 92 names in exact lexical prefix order; all 92 `migration.sql` byte hashes matched; same-name mutation, prefix insertion, and prefix deletion were rejected.
- v6 migration SHA-256: `b3fc23e56f4cfa5639628c2cd98c39e16ee62e0cce790cfed16e741837edc433`.
- v7 migration SHA-256: `182cff0b5c5d2f32fc34f45b95f0d951592ea42cd3c0fa33ea26a03c8ca7ec5e`.

## Database and repository gates

- PostgreSQL target: disposable `pgvector/pgvector:pg16`; no provider egress or PHI.
- Fresh 92-migration install: PASS.
- Current installed census after fresh install: 125 ordinary functions, 0 procedures, 0 window functions, 0 aggregates, 0 exact-path violations under the corrected `f/p/w` query.
- Idempotent migration rerun: PASS, no pending migrations.
- Data-bearing upgrade: PASS from exact base's 90 migrations to head's 92; synthetic sentinel value preserved; 0 corrected-path violations.
- Concurrent upgrade: PASS; two simultaneous migrators produced one successful v6/v7 application and one clean no-pending result.
- Focused release-control migration contract: 1 file / 17 tests PASS.
- Template Twin unit scope: 68 files / 614 tests PASS.
- Prisma format, validate, generate: PASS.
- Strict TranscribeMD TypeScript: PASS.
- Scoped ESLint: PASS with no errors; the DB script required explicit app config because it is outside the app base path.
- Scoped Prettier: PASS.
- TruffleHog 3.95.2 offline no-verification scan: 16 chunks / 172,487 bytes / 0 verified / 0 unverified findings.
- TruffleHog verified-only scan: 16 chunks / 172,487 bytes / 0 verified findings.
- Bounded credential-pattern scan: zero matches.
- Full release-control PostgreSQL behavioral suite: not completed after the lead requested prompt finalization once the decisive P1 was reproduced. Early attempts were invalidated by disposable-fixture role provisioning order and are not treated as product results.

## Required disposition

Do not integrate exact `8bf2158`. Preserve it as rejected evidence. Add a new immutable migration and tests so the terminal database census enforces exact configuration for every path-configurable Template Twin function kind, explicitly rejects unsupported `pg_proc` kinds under the reserved prefix, and the static later-migration gate rejects corresponding unsupported namespace-entry forms. Obtain a new fresh detached exact-head review.
