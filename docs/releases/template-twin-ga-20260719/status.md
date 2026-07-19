# QuillMD Template Twin GA release-program status

Last updated: 2026-07-19T17:54:54Z

## Production verdict

**NOT RELEASED.** Template Twin remains synthetic-staging-only. No production migration, deployment, flag change, provider call, or PHI-bearing test has been performed by this program.

## Exact source records

| Record | Exact value | Status |
|---|---|---|
| Current `origin/main` | `1be101912f01293de3b8fddae722c823ecc86f29` | PASS |
| Accepted remediation | `fix/template-twin-manual-certification-remediation-v1` at `79c04e88785a16e8e3b37b58544e107e3a16996e` | PASS |
| Accepted parent | `b46c62f97544a0193c60929d5ac8e8870b20dc4b` | PASS |
| Stacked PRs | #362–#370, all open drafts, exact heads verified linear | PASS |
| Consolidated release branch | `release/template-twin-ga-20260719` at local additive head `1685e35aef0d26048e031920a0f6e5da4bc79b1b` | PASS |
| Published draft-PR head | `9088f74f17e11ff3f7e5869e5a56b6c5d36796fd`; intentionally stale while additive reviews run | FAIL |
| Lossless stack integration | Merge `719eea4b27c68cc76e6bf485612c833705cef913` | PASS |
| Consolidated release PR | Draft PR #371 targeting `main` | PASS |
| Frozen release candidate | Not created | FAIL |
| Current production Git SHA | Not reproducible from a clean commit | FAIL |

`origin/main` is an ancestor of the accepted remediation; the accepted stack is 82 commits ahead and `git merge-tree` reports no integration conflict. Merge commit `719eea4b27c68cc76e6bf485612c833705cef913` has exactly two parents (`1be1019` and `79c04e8`), and its tree `1450b6fe4acdd78f0d6c46df5ef276e86735ab93` is byte-for-byte identical to the accepted remediation tree. The accepted stack adds ten ordered Prisma migrations. Additive intake, rollback, completed-candidate, and fill-lineage work now brings the local repository total to 87 while production remains at the preceding 67. No local migration result is production authorization.

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
| 1 — Consolidated implementation | FAIL | Accepted history is consolidated losslessly and draft PR #371 exists. The local additive head is `1685e35`; the remote PR is intentionally stale. The authentication/authorization component review accepted exact `137b020`, while schema, rollback, native DOCX, control-plane, final-head CI, census, and full integration review remain open. |
| 2 — Production template intake | FAIL | The separate completed-document candidate workflow received independent ACCEPT and is integrated. Native bounded DOCX review at exact `635d966` returned REJECT: malformed control elements missing their required Word container can evade the placement gate and produce zero certification blockers. Unsupported repeats, rich text, ambiguous merges, unsafe parts, and unprofiled structures remain fail-closed and visible rather than claimed as supported. |
| 3 — Extraction quality | FAIL | Exact evidence is revalidated at review, correction, signing, and download. The deterministic contract cohort passes 176/176, but the release-head live-provider cohort is `n=0` and Clinical Safety approval is pending. |
| 4 — Microsoft Office compatibility | FAIL | The accepted author corpus passes its existing Open XML/LibreOffice checks, but detached review constructed synthetic misplaced dropdown/checkbox controls that intake accepted and Microsoft365 Open XML validation rejected. Additive placement remediation, fresh exact-head review, final-SHA package generation, and returned desktop Word evidence remain mandatory. |
| 5 — Infrastructure and operations | FAIL | Fill-lineage immutability v5 and its rollback harness pass locally and are under detached review. Contracted Prisma schema drift is closed locally at `1685e35`. Control-plane v3 is still being remediated and is not integrated. Complete restore, PITR, object-store recovery, monitoring, capacity, and operational ownership remain unpassed. |
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

## Initial consolidated test census

The census used clean detached worktrees, Node 22.22.0, npm 11.10.0, `npm ci`, and generated Prisma clients. It compared exact base `1be101912f01293de3b8fddae722c823ecc86f29` with release documentation head `4d011f6bcb8b8e9bac17a3f17d1874faec4f8ff3` before corrective commit `c4f6afa`; the final exact head must be rerun.

- Repository test-file census: base 196, head 325, 129 added, 34 modified, none removed.
- Offline unit census: base 143 files / 1,895 tests PASS; head 270 files / 3,264 tests PASS.
- Identical 143-file manifest: base 1,895 tests PASS; head 1,925 tests PASS.
- Head-only unit inventory: 127 files / 1,339 tests PASS.
- The root `npm run test:all` command is a zero-test placeholder and is not counted as evidence.
- The top-level CRM integration suite requires a seeded PostgreSQL instance and failed identically on base and head with the same unavailable test-database authentication; it is not marked PASS.
- Browser, database-backed, Office, provider, load, and migration rehearsals remain separate open gates.

Draft PR #371 remains published at stale head `9088f74f17e11ff3f7e5869e5a56b6c5d36796fd`. Its current unit, TranscribeMD E2E, and accessibility checks are red; test, human-package, high/critical audit, and verified-only secret checks are green. This mixed stale-head result is **FAIL**, not final-head evidence. At combined local head `c9291c6`, the active TranscribeMD unit census passed 304 files / 3,522 tests and strict TypeScript passed; additive startup commit `2014ec2` then passed its focused test, lint, strict TypeScript, production Next.js build, and live standalone fail-fast probes. The full census will run again after control-plane integration and at frozen RC.

## Corrective technical evidence at local head

- Office evidence hardening commit: `70d3717594fd4fe512d5403918729dde23543f53`; focused author tests passed, but independent review rejected the package-origin, validator-report binding, and static-structure enforcement contracts. Desktop Word remains a human gate.
- Intake/evidence/rollback commit: `581b5b5cfe17655f0994a382ccde5ca98088f4a9`; Template Twin path census 93 files / 1,012 tests PASS, application TypeScript PASS, changed-file ESLint PASS, Prisma format/validate/generate PASS.
- A fresh disposable PostgreSQL database applied all 78 migrations. The synthetic-only `template-twin-quarantine-certification-contract-v1` passed its valid path and proved direct-SQL certification of a pre-GA source is rejected.
- Independent detached review of `581b5b5` also returned REJECT: the generated Prisma enum omitted two admitted audit actions, legacy certified rows could bypass quarantine at runtime, the SQL receipt fixture was not canonical, no production ClamAV service was deployable, rollback lacked a callable audited maintenance command, and completed-document conversion was absent. Commit `9088f74` closes the legacy runtime bypass across activation, selection, pinning, fill, signing, and re-delivery; 138 focused tests, application TypeScript, and targeted lint pass. The other findings remain under additive remediation and require new independent exact-head review.
- Completed-document candidate conversion passed detached review at exact `a0c142bc` with no P0/P1/P2 findings and is integrated through `1edc68c`. It never overwrites or activates the completed source and requires explicit physician decisions on every synthetic candidate region.
- Fill-lineage immutability v5 is integrated through `635d966`; fresh, data-bearing, inconsistent-data, contention, race-ordering, stale-snapshot, rollback, and audit-time disposable PostgreSQL proofs passed. Detached exact-head review is in progress.
- Native bounded DOCX hardening is integrated through `5cafc12`, but detached exact `635d966` review returned REJECT on missing-required-container handling for synthetic Word control elements. The existing focused corpus passed 84/84 and the complete app census passed 3,522/3,522 at `c9291c6`, demonstrating the missing negative coverage rather than closing the defect. Desktop Word remains HUMAN PENDING.
- Administrative authentication and authorization hardening is independently accepted at exact `137b020904bfbee31dc5bea2a232bf706fadd300`: fresh per-page/API authority, host-only sessions, mandatory platform-admin MFA, required awaited audit persistence, fixed-detail error logs, and true process termination on unsafe production configuration. The detached reviewer passed 14/14 files and 62/62 tests, strict TypeScript, changed-file lint, production Next.js build, live host/cookie startup probes, Caddy/Compose validation, and returned zero P0/P1/P2 findings. Final combined-head review still applies.
- Contracted schema reconciliation is integrated at `1685e35`: pre-operator drift contains only the documented lineage contract delta; the fully contracted disposable database produces an empty Prisma diff. The new harness rejects both uncontracted state and injected synthetic drift. See `evidence-manifest-schema-contract-v1.md`.
- Current dependency audit has zero high/critical findings; one low and thirteen moderate findings are lower-severity debt for final triage. Verified-only TruffleHog found zero credentials; four offline heuristic hits are confined to named synthetic/placeholder test and example files.

## Rollback compatibility finding

An independent disposable-schema rehearsal rejected the preserved pre-release images as post-migration rollback targets. After the accepted lineage contract, the old application cannot create generic templates, cannot read newly appended audit enum values, can fail ordinary automation/signing transitions, can expose or select Template Twin rows without the new rollout contract, and its worker can replay ambiguous provider work. The archived images remain valid only for a rollback before any Template Twin migration. Commit `581b5b5` implements a final-schema `rollback-compat-v2` bridge and image guard, but production migration remains blocked until independent ACCEPT, immutable bridge digests, a data-bearing swap/roll-forward rehearsal, and an audited maintenance fence prove the required valid-token deactivation-before-revocation sequence.

## Protected-worktree statement

`/opt/meddoc-pro` remains untouched. Its pre-existing modified and untracked files were not reset, cleaned, stashed, overwritten, switched, committed, or copied into the release workspace.
