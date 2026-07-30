# Source-admission merged-head verification

## Verdict

**PASS** for the proportional release-integration gates requested at exact
merged head `ef9d980d2f64bcc6c4fe490cf0a3c38bf57ee1ec`.

This is a technical merged-head result only. It does not satisfy Desktop
Microsoft Word or any other human release gate, authorize provider egress, or
authorize production rollout.

Completed at `2026-07-20T01:17:28Z`.

## Frozen identity and scope

- Worktree: `/home/claude/release-programs/meddoc-template-twin-ga-20260719`
- Branch: `release/template-twin-ga-20260719`
- HEAD: `ef9d980d2f64bcc6c4fe490cf0a3c38bf57ee1ec`
- Tree: `ea9d88cbce8db09ddd47585ea863c55d7e48df31`
- First parent: `d6dcdb0c79b18b3da0f81710627c0be6217771df`
- Accepted component parent: `7f90f14aafa45bf5efa4ebee751e965057dda9d9`
- Initial and final tracked/untracked status: empty
- Initial and final worktree/index diff checks: pass
- Final `git diff --check`: pass

No reviewed source was edited. No commit, push, merge, deployment, production
mutation, provider call, real document, or PHI was used. `/opt/meddoc-pro` was
not accessed by this verification.

Evidence: `exact-identity-initial.log`, `exact-identity-final.log`, and their
`.exit` records.

## Test and static gate results

| Gate | Result |
| --- | --- |
| Exact seven-file source-admission manifest | PASS — 7 files, 51/51 tests |
| Complete Template Twin census | PASS — 87 files, 927/927 tests |
| Template Twin migration-contract manifest | PASS — 9 files, 49/49 tests |
| Strict TranscribeMD TypeScript | PASS after serialized Prisma generation |
| Prisma format `--check` | PASS |
| Prisma validate | PASS |
| Prisma generate | PASS — Prisma Client 7.8.0 |
| QA Docker Compose config | PASS |

The complete merged census contains 927 tests, six more than the earlier
source-component-only expectation of 921. No files or tests were lost; the
merged head combines the already accepted search-path work with source
admission.

The exact seven-file manifest was:

1. `malware-scan.test.ts`
2. `quarantine-admission.test.ts`
3. `source-admission.test.ts`
4. `openxml-source-validation.test.ts`
5. `openxml-runtime-config.test.ts`
6. `create-draft-orchestration.test.ts`
7. `upload-certification.integration.test.ts`

Evidence: `focused-seven-source-admission.log`,
`template-twin-complete-census.log`, `migration-contract-tests.log`,
`typescript-strict-after-prisma-generate.log`,
`prisma-format-validate-generate.log`, and `docker-compose-qa-config.log`.

## Retained TypeScript harness-order failure

The first TypeScript process was started concurrently with Prisma generation
and exited 2 while reading the stale pre-merge generated client. Its errors
were model-shape mismatches for fields present in the merged Prisma schema.
No source changed. After Prisma generation finished, the same strict
`tsc --noEmit --incremental false` command was rerun serially and exited 0 with
no diagnostics.

The failed transcript is retained as `typescript-strict.log`; the accepted
serialized rerun is `typescript-strict-after-prisma-generate.log`.

## Disposable PostgreSQL migration verification

- Image: `pgvector/pgvector:pg16`
- Local image ID:
  `sha256:8ed3192326bb9d114cd5ef9acace453d5dae17425bd089d089330584c84c5a34`
- Repository migration directories: 95
- Successfully finished, unrolled migration rows: 95
- Unresolved failed migrations: 0
- `prisma migrate status`: schema up to date
- Second `prisma migrate deploy`: no pending migrations

The first empty-cluster attempt intentionally remains in evidence. It stopped
at historical migration `20260505010210_round_3_pr_c_revoke_audit_mutation`
with Prisma P3018/PostgreSQL 42704 because the disposable owner-only cluster
omitted the repository-required pre-existing `meddoc` role. This was a
verifier bootstrap defect, not a migration-head defect.

That disposable container was removed. A new empty cluster was created and
given the repository-canonical least-privilege role bootstrap before any
migration: the legacy no-login role, four no-login QuillMD boundary roles,
three isolated login principals, and only their one-to-one memberships. All
95 migrations then applied from empty state, status passed, and the second
deploy was idempotent. The corrected disposable container was also removed;
no verifier container remains.

Evidence: `pg-fresh-migrate-deploy.log`, `pg-first-fixture-cleanup.log`,
`pg2-canonical-role-bootstrap.log`, `pg2-fresh-migrate-deploy.log`,
`pg2-migrate-status.log`, `pg2-idempotent-deploy.log`,
`pg2-final-migration-posture.log`, and `pg2-final-cleanup.log`.

## Secret scans

The exact added lines from first parent `d6dcdb0` to merged head `ef9d980`
were materialized with zero diff context and scanned using TruffleHog 3.95.2.

- Added-line material SHA-256:
  `d46c836b95b4b3beb1fb9f01c8b95996a2fe9a5b8780cd01317717f753e5a93d`
- Offline/no-verification candidate records: 0
- Verified-only records: 0
- Raw result bytes: 0 for both scans

Temporary added-line and raw scan material was removed. Only the digest,
counts, scanner stderr, and cleanup record remain; no candidate material is
included in this report or manifest.

Evidence: `secret-added-lines.sha256`,
`trufflehog-added-diff-offline-summary.log`,
`trufflehog-added-diff-verified-summary.log`,
`secret-raw-output-byte-counts.log`, and `secret-scan-cleanup.log`.

## Final conclusion

All requested merged-head product gates pass. The two retained initial
failures were independently corrected verifier sequencing/bootstrap defects;
neither required or caused a source change. The exact merged release worktree
finished clean, production was untouched, and no human gate status changed.
