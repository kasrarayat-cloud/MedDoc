# QuillMD Template Twin GA release-program status

Last updated: 2026-07-19T06:13:48Z

## Production verdict

**NOT RELEASED.** Template Twin remains synthetic-staging-only. No production migration, deployment, flag change, provider call, or PHI-bearing test has been performed by this program.

## Exact source records

| Record | Exact value | Status |
|---|---|---|
| Current `origin/main` | `1be101912f01293de3b8fddae722c823ecc86f29` | PASS |
| Accepted remediation | `fix/template-twin-manual-certification-remediation-v1` at `79c04e88785a16e8e3b37b58544e107e3a16996e` | PASS |
| Accepted parent | `b46c62f97544a0193c60929d5ac8e8870b20dc4b` | PASS |
| Stacked PRs | #362–#370, all open drafts, exact heads verified linear | PASS |
| Consolidated release branch | `release/template-twin-ga-20260719` at `719eea4b27c68cc76e6bf485612c833705cef913` | PASS |
| Consolidated release PR | Not created | FAIL |
| Frozen release candidate | Not created | FAIL |
| Current production Git SHA | Not reproducible from a clean commit | FAIL |

`origin/main` is an ancestor of the accepted remediation; the accepted stack is 82 commits ahead and `git merge-tree` reports no integration conflict. Merge commit `719eea4b27c68cc76e6bf485612c833705cef913` has exactly two parents (`1be1019` and `79c04e8`), and its tree `1450b6fe4acdd78f0d6c46df5ef276e86735ab93` is byte-for-byte identical to the accepted remediation tree. The stack adds 465 files/changes, 146,048 lines, and ten ordered Prisma migrations (production currently has the preceding 67).

## Current production provenance

The running production containers are healthy, but their images have no source-revision labels or registry digests. The running worker source manifest matches `origin/main` except for six uncommitted files from the protected worktree; it therefore cannot be assigned a truthful Git SHA.

| Runtime | Immutable running image ID | Preserved local rollback tag |
|---|---|---|
| Physician app | `sha256:95f57158e3fe56acc832793be3f5da972cc1fdc6c3b85166f8387b3a103f1f90` | `meddoc-pro-transcribe-md:rollback-template-twin-ga-20260719-95f57158` |
| Worker | `sha256:412dd3157475fd60a77d417a6db6880343d58755aaf76f044be035fba4acf44e` | `meddoc-pro-transcribe-md-worker:rollback-template-twin-ga-20260719-412dd315` |

The two exact images were exported without runtime secrets to a mode-0600 local archive outside the repository:

- Path: `/home/claude/release-evidence/meddoc-template-twin-ga-20260719/rollback/pre-release-production-images-20260719T0602Z.tar.gz`
- SHA-256: `73bde836cc4983e7803caf2bda605955023e7eb2ad26f045d5b0fb9d87af8b3a`
- Size: 593,964,098 bytes

## Phase status

| Phase | Status | Evidence / blocking condition |
|---|---|---|
| 0 — Preflight and inventory | FAIL | Read-only inventory completed and production gate is closed: exact deployed SHA, least-privilege DB/object-storage identities, PITR, encrypted offsite restore, internal transport, capacity, and monitoring evidence fail. |
| 1 — Consolidated implementation | FAIL | Accepted history is consolidated losslessly at `719eea4`; draft PR, full census, corrective commits, and independent exact-head review remain pending. |
| 2 — Production template intake | FAIL | Existing safe-alpha boundary is narrower than the requested GA boundary; completed-document conversion is not implemented. |
| 3 — Extraction quality | FAIL | Core facts can currently populate without exact source offsets; existing deterministic/mocked tests are not a signed multispecialty quality evaluation. |
| 4 — Microsoft Office compatibility | HUMAN PENDING | Synthetic Open XML/LibreOffice tooling exists; returned desktop Microsoft Word evidence is mandatory and absent. |
| 5 — Infrastructure and operations | FAIL | Complete restore, PITR, object-store recovery, monitoring, capacity, and operational ownership gates are not passed. |
| 6 — Privacy/Legal, Clinical, Operations approvals | HUMAN PENDING | No approval may be fabricated by Codex. |
| 7 — Final release candidate | FAIL | No frozen exact head or independent final review exists. |
| 8 — Production deployment and 100% rollout | FAIL | Not authorized until Phases 0–7 pass. Current rollout is 0%. |

## Phase 0 evidence already obtained

- Mandatory equivalent preflight: `docs/preflight-reports/preflight-20260719T055320Z.md` (repository skill unavailable; recorded honestly).
- Public health: app 307-to-login; `pro.quillmd.com` and `quillmd.com` 200; established unauthenticated admin root 404; Postgres/Redis/MinIO checks healthy.
- DNS/TLS: app/admin resolve to `147.189.172.8`; certificate covers both and expires 2026-09-01.
- Live schema-only backup/restore: restored all 30 public tables, 295 constraints, and 124 indexes to a network-isolated tmpfs PostgreSQL instance using immutable image `sha256:8ed3192326bb9d114cd5ef9acace453d5dae17425bd089d089330584c84c5a34`.
- Latest local production dump: gzip integrity PASS; 375,260 bytes; SHA-256 `4312095f509e284ac5d7fe016898764f71d571ff36474a38cc54d1bb8df51823`; mtime 2026-07-19T00:00:00Z. Its PHI-bearing contents were not opened or restored into QA.
- Accepted remediation CI: test, unit, Playwright E2E, npm high/critical audit, and verified-only TruffleHog checks succeeded at `79c04e8`; the branch-specific human-package job was skipped on PR #370.
- Production DB: 67/67 migrations complete and no invalid indexes, but one documented historical migration checksum differs from the repository; PostgreSQL has no PITR and application traffic uses the sole superuser/owner role, including unrestricted mutation of `audit_logs`.
- Production storage: MinIO is private and default-SSE encrypted, but web and worker use root credentials; versioning/object lock/lifecycle are absent, orphan reconciliation is disabled, and 76 storage-full events occurred July 16–17.
- Internal service transport: PostgreSQL, Redis, and MinIO use plaintext on the private Docker network. Loopback-only host publishing reduces exposure but does not satisfy the explicit encryption-in-transit gate.

## Protected-worktree statement

`/opt/meddoc-pro` remains untouched. Its pre-existing modified and untracked files were not reset, cleaned, stashed, overwritten, switched, committed, or copied into the release workspace.
