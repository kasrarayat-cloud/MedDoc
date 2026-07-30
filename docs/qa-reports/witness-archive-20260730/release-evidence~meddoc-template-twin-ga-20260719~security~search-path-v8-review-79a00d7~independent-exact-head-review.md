# Independent exact-head review — Template Twin search-path terminal contract v8

## Verdict

**ACCEPT** exact head `79a00d7f3fa9513905966906e491235b16e6c641` for integration of this search-path component.

- P0 findings: none.
- P1 findings: none.
- P2 findings: none.
- No implementation, commit, push, merge, deployment, provider call, PHI use, or production mutation was performed by this reviewer.

## Exact identity and isolation

- Head: `79a00d7f3fa9513905966906e491235b16e6c641`
- Tree: `252cb0b9f6769c9b7746473636bc1c6c89c4ae97`
- Parent: `8bf2158db7680a97f52b4338d54ff1912fcb7468`
- Immutable detached review tree: `/home/claude/release-programs/reviews/search-path-v8-79a00d7`
- Exact-head execution tree: `/home/claude/release-programs/reviews/search-path-v8-79a00d7-runner`
- Parent census tree: `/home/claude/release-programs/reviews/search-path-v8-parent-8bf2158-runner`
- Opening and closing status of all three detached trees: clean (`git status --porcelain=v2 --untracked-files=all` empty).
- The immutable review tree was never edited. Ignored dependency links existed only in the disposable execution trees.

The exact delta is four intended paths: one modified contract test, one additive v8 migration, one modified PostgreSQL proof, and one additive v8 immutable manifest. `git diff --check` passed. The v7 migration and v7 manifest are byte-identical to the parent.

## Security and contract review

The prior independent P1 facets are closed:

1. The v8 database census applies the exact one-entry `search_path=pg_catalog, public, pg_temp` invariant to PostgreSQL `prokind` values `f`, `p`, and `w`.
2. Reserved-prefix aggregates (`prokind = 'a'`) are rejected explicitly because PostgreSQL cannot apply the routine search-path invariant to them.
3. Any other routine kind under the reserved public prefix is rejected fail closed.
4. The later-migration detector now classifies aggregate creation, rename into the reserved namespace, and public-schema entry, including quoted and Unicode/UESCAPE forms.
5. Function, procedure, routine, window, aggregate, dynamic-SQL, Unicode, exact-value, and decoy behavior remained fail closed without false positives in the exercised corpora.
6. The migration is assertion-only: it does not rewrite routines or enable rollout. It has bounded lock/statement timeouts and a transaction-local fixed path.

The default rollout remains off. On the fresh database the global singleton had zero enabled rows, all practices had zero enabled rows, and the terminal census reported zero path violations, aggregates, or unknown kinds.

## Independent detector and manifest evidence

- Exact detector source SHA-256: `f059ceb7959ad638949273f0ed389905a670c90aac29d8d21b29b6a56cdd66d6`.
- Frozen corpus: 46/46, corpus SHA-256 `2fc5bc7672d6b7a1487eeba8baaab908a7d6dc719a0d253b53418be82e7bbdf6`.
- Frozen corpus: 36/36, corpus SHA-256 `dcd8233a39e9a4dba2819f7566a773e01abae10f7d8b456c84934227ae4b27fd`.
- Frozen corpus: 40/40, corpus SHA-256 `60aeec2a6b38e271a11e38cb3aafd1df69bb92ff72d4779c9e994d4ddfdd8acc`.
- Prior-reviewer PostgreSQL-valid corpus: 29/29, corpus SHA-256 `765ed167c3231c7a293c4ef0d38823431fa877efeff2467ba7edb93c6d1219b3`.
- New independent aggregate/window/Unicode/dynamic/decoy corpus: 46/46, zero false negatives and zero false positives, corpus SHA-256 `a0108fed25cbc8fea76de6c2237e6b63aa111a5e59b97f0c5d853463b574c949`.
- Frozen v7 manifest SHA-256: `6de7df3ca701a1628290f06b7ec089490d2f434b09e3c774d10e2363a32902b7` (92 entries).
- v8 manifest SHA-256: `815f28992d1b3b077dacdf8261995c26a172a92a871d1f85fe2386cab7d94306` (93 entries).
- v7 migration SHA-256: `182cff0b5c5d2f32fc34f45b95f0d951592ea42cd3c0fa33ea26a03c8ca7ec5e`.
- v8 migration SHA-256: `1597a1f3dd44f1c638ff75f10e012b7c5ed9cb0db5b1c9c90370faccfd74f58a`.
- Independent prefix proof verified every name, lexical position, and `migration.sql` hash, parent immutability, and rejection of same-name byte mutation, prefix insertion, and prefix deletion. Native `sha256sum --check --strict` also passed for both manifests.

## Test census and static gates

- Focused parent: 1 file / 17 tests PASS.
- Focused head: 1 file / 19 tests PASS.
- Template Twin library parent: 83 files / 891 tests PASS.
- Template Twin library head: 83 files / 893 tests PASS; no test loss.
- Broader head path census: 111 files / 1,150 tests PASS.
- Strict TranscribeMD TypeScript: PASS.
- Changed application test ESLint: PASS.
- Changed database proof ESLint: PASS with only the known harmless Next pages-directory context notice and exit code 0.
- Changed TypeScript Prettier: PASS.
- Prisma format, validate, and generate: PASS; formatting left the runner tracked tree clean.

## PostgreSQL 16 evidence

- Disposable engine: PostgreSQL `16.13`, image ID `sha256:8ed3192326bb9d114cd5ef9acace453d5dae17425bd089d089330584c84c5a34`, image digest `pgvector/pgvector@sha256:7d400e340efb42f4d8c9c12c6427adb253f726881a9985d2a471bf0eed824dff`.
- Fresh install: all 93 migrations PASS.
- Idempotent redeploy and migration status: PASS/no pending migrations.
- Fresh installed census: 125 reserved-prefix ordinary functions, zero path violations, zero aggregates, zero unknown kinds.
- Exact v8 runtime fixtures: unpinned ordinary function, procedure, and window function rejected; reserved aggregate rejected; exactly pinned window function accepted with canonical `proconfig`; terminal violations returned to zero after cleanup.
- Data-bearing upgrade: exact parent 92 migrations to head 93 PASS; synthetic sentinel and canonical window function preserved; v8 recorded once; zero violations.
- Concurrent upgrade: two simultaneous head migrators yielded one successful v8 application and one clean no-pending result; one successful migration row, zero failed rows, zero violations.
- Full release-control/race proof: PASS, including database role boundaries, signed runtime and monitoring barriers, capability replay rejection, immutable evidence, six race classes, isolated audit dispatch, 64 synthetic audit events, and final global disabled state.
- The disposable PostgreSQL container and all synthetic fixture data were removed after evidence capture.

## Secret scans

- TruffleHog 3.95.2 exact-delta offline/no-verification scan: zero findings.
- TruffleHog exact-delta verified-only scan: zero findings.
- Sanitization retained only counts; raw scanner output was held in a validated temporary directory and destroyed.
- Bounded added-line credential-pattern scan: 486 added lines, zero private-key, AWS, GitHub, OpenAI, credentialed database URL, or generic secret-assignment matches.

## Transparently retained fixture-only failures

These are not product findings and no failed result was counted as a pass:

1. An initial fixture bootstrap placed `CREATE DATABASE` in a multi-statement transaction; PostgreSQL rejected it and rolled back. Separate corrected database creation passed.
2. The first Prisma invocation used a package-local binary path that did not exist; the root workspace binary was then used.
3. The first fresh migration fixture omitted the repository's legacy `meddoc` role and failed at the historical audit-ACL migration. The disposable database was recreated after exact role provisioning; all 93 migrations passed.
4. One census command lost quoted mixed-case column syntax through nested shell quoting after its earlier queries had passed. The same census was rerun from a preserved SQL file and passed completely.
5. The first release-control proof invocation set only the dedicated test URL. The ordinary database singleton consequently attempted its unconfigured placeholder connection and failed authentication; it authenticated to no shared target. The partially used disposable database was destroyed. A clean database with both database URLs pinned to the isolated test target passed the entire proof.
6. A subsequent fresh fixture correctly failed while the post-migration-only release-security membership was present. The documented pre/post migration membership choreography was applied in a newly recreated disposable database, which then passed.
7. The first TruffleHog Git-source scan could not clone the repository's partial-clone/promisor object graph. The final scans used an exact binary diff materialized only in a validated temporary directory and both passed.
8. One direct manifest-check invocation used the wrong working directory. The independent manifest proof had already passed; the native check was rerun from the correct migration directory and passed.

## Disposition

This component exact head is acceptable for the lead's additive integration workflow. Acceptance is limited to the reviewed search-path v8 delta; it is not a production release authorization and does not alter any outstanding human, infrastructure, credential-rotation, Word, clinical, privacy/legal, operations, merge, or deployment gate.
