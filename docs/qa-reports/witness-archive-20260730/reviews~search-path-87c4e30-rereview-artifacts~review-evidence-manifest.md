# Template Twin v6 static guard exact-head re-review

## Identity and verdict

- Verdict: REJECT
- P0: 0
- P1: 1
- P2: 0
- Exact head: `87c4e306455e6a199e5974338f7b6944d6b3c659`
- Exact parent: `a2ad79f40058ede17f40782efa7981fc4c51bf9b`
- Accepted release base: `b5b26e0bf5b59293a8f9387550444bb59d2673e8`
- Head tree: `67788f75061c608bfdd5ad05df5699dc6c5fbf95`
- Parent tree: `4ae9016502f2b542050d445801fcefeb0c00139c`
- Base tree: `521f7864a104c6cc5d2bb010fc42e52e9e7be698`
- Base-to-head binary patch SHA-256: `a649589d9bef84d2116aa3c64107022fe1885240d9c602b9c94149a40fe74541`
- Parent-to-head binary patch SHA-256: `18bc11e806f843e668f851dd8fa4ff3dab4ad15cb68cbc46d0559bd92acaa1eb`

## Migration identity and PostgreSQL 16 proof

- The v6 migration blob is identical at parent and head: Git blob `cb0441c77b3b5aa3f2100f6f66887fe489583e29`.
- Migration SHA-256: `b3fc23e56f4cfa5639628c2cd98c39e16ee62e0cce790cfed16e741837edc433`.
- Test SHA-256: `0c837d8145b7ccaef9c304a8a565f73aea441e10ba010cff16fb8f64a37581a8`.
- Migration census: 91; immutable prefix through v6: 91; later migrations: 0.
- Immutable prefix name SHA-256: `3a6fb1ecd2661720efb99075c5f36bdb7c0e595aefd83ab9b7df531521983f06`.
- Disposable image: `pgvector/pgvector@sha256:7d400e340efb42f4d8c9c12c6427adb253f726881a9985d2a471bf0eed824dff`.
- Server: PostgreSQL 16.13; `standard_conforming_strings=on`.
- Fresh base deploy: 90 migrations; parent had exactly four unpinned target functions and four unsafe Template Twin functions.
- After v6: all four targets had the exact fixed search path and the complete unsafe count was zero.
- Owner, ACL, body, OID, signature/non-path configuration, and trigger-shape invariant SHA-256 before and after: `bbc5736ba08a8888f96543ec00368d2fbd05f9f3424281d9052d97e086498277` (identical).
- Default-off state before and after: global `false`, generation 1, fence `OPEN`, zero enabled practices.
- Repeated deploy: no pending migrations.
- The minimal lexical fixture executed successfully on the same PostgreSQL 16 instance and created the expected routine.

## Static regression finding

- All six prior misses are closed.
- The actual exact-head helper passed the prior seven routine cases, the prior lexically-prior migration case, 18 additional routine cases, and all four immutable-prefix insert/rename/delete/order mutations.
- No false positive was observed. There are no real migrations after v6 at this head.
- One new false negative remains: the lexer treats a backslash in an ordinary standard-conforming string as if it escaped the closing quote, so subsequent migration SQL can be omitted from the routine census.
- Minimal fixture: `standard-literal-trailing-backslash.sql`; SHA-256 `8afc769df1241f6535c9d304bb1aba9f8e8da67bdb0bdcff41fcd91c8ffabe9f`.
- Mutation result: `mutation-corpus-result.txt`.

## Other gates

- Exact committed focused tests: 2 files, 27 tests, PASS.
- Strict TranscribeMD TypeScript: PASS.
- Focused changed-test ESLint: PASS.
- `git diff --check`: PASS.
- Exact changed-file TruffleHog 3.95.2 verified scan: 4 chunks, 42,647 bytes, zero verified or unverified findings.
- Review worktree was returned to the exact committed file state before cleanup.
- No production/shared service was used; no PHI or production credential was accessed; `/opt/meddoc-pro` was not written.
