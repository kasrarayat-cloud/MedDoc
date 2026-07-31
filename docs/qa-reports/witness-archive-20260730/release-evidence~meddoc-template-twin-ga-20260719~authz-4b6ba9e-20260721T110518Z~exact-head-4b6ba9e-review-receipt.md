# QuillMD Template Twin exact-head review receipt

Recorded: 2026-07-21T11:06:12Z

## Verdict

**ACCEPT** for the exact reviewed head. Three independent reviewers returned
ACCEPT with no P0, P1, or P2 finding. This is technical exact-head acceptance;
it is not production authorization. Template Twin remains **NOT RELEASED** and
production availability remains **0%**.

## Exact identity

- Branch: `fix/template-twin-provider-ownership-b017-v1`
- Exact head: `4b6ba9e7060a213829f7f5c42b30318a144f9ba2`
- Tree: `a3cd61cae3a72c3eb0e7f9d061ed79786aa5a562`
- Parent: `a7488ba8cc755beeedef56eb27f828d5d86e037b`
- Corrective implementation parent:
  `a7488ba8cc755beeedef56eb27f828d5d86e037b`
- Rejected historical parent:
  `6f8f3e108fe57bb5f8686ec7a4079624ea629a79`
- Accepted pre-CI ancestor:
  `fc08599533f75dbd7bdf878a9d23595ab83d4be0`
- Main target:
  `1be101912f01293de3b8fddae722c823ecc86f29`
- Immutable bundle: `review-handoff-4b6ba9e.bundle`
- Bundle SHA-256:
  `3ca6209e123616d71c159188f4d2470864504e3a2881304d01a5c6777fa4337f`
- Bundle mode: `0400`
- Bundle head: exact branch ref at `4b6ba9e7060a213829f7f5c42b30318a144f9ba2`
- Bundle prerequisite: exact `origin/main` at
  `1be101912f01293de3b8fddae722c823ecc86f29`

The records-only head cannot contain its own SHA. This external receipt and the
verified immutable bundle bind the exact post-commit identity without rewriting
history.

## Historical rejection and additive closure

Exact `6f8f3e1` remains **REJECTED**. Auth/security and integration/test-census
reviews reproduced two P1 defects:

1. uid-1001 application consumers lacked supplemental gid 1001 and could not
   read the root:1001/0440 MFA keyring;
2. package-level TypeScript reproduced `TS2345` in the synthetic CI helper while
   app-only TypeScript passed.

Exact `a7488ba` closes both findings additively. It gives gid 1001 only to the
physician and admin application keyring consumers, proves the exact immutable
image identity/group/permission contract before reading without printing key
bytes, uses the closed `SyntheticDatabaseSecrets` type, and runs a dedicated
package no-emit typecheck in both helper-using workflows. Exact `4b6ba9e` adds
truthful records without changing implementation or test discovery.

## Independent detached reviews

### Auth/security

- Workspace:
  `/home/claude/release-reviews/auth-security-4b6ba9e-20260721T104315Z`
- Clean detached exact head/tree verified before and after review.
- Verdict: **ACCEPT**.
- P0/P1/P2: none.
- P3: inherited mutable GitHub Action major tags and Redis/MinIO tags; already
  recorded and not introduced by this closure.
- Reviewed `origin/main...HEAD`: 151 commits, 954 files.
- Reviewed `fc08599...HEAD`: 3 commits, 21 files.

### Integration and test census

- Workspace:
  `/home/claude/release-reviews/exact-head-4b6-test-census-7arqIoVi/worktree`
- Clean detached exact head/tree verified before and after review.
- Verdict: **ACCEPT**.
- P0/P1/P2: none.
- P3: no new finding; inherited provenance debt remains recorded.
- Parent/head canonical test manifest SHA-256:
  `8e883118285ab77dd386f9cdb04f88347756d4c86bdd44bdce1a28216a56281c`
- Parent/head test-file manifest SHA-256:
  `6c38fb2154f20c869dc4d5fcf126f35c12222ae83c21cbde2f3b856438b94b8f`

### Rollback, infrastructure, and records

- Workspace:
  `/home/claude/release-reviews/infra-records-4b6ba9e-Ft4rtvwj/worktree`
- Clean detached exact head/tree verified.
- Verdict: **ACCEPT**.
- P0/P1/P2: none.
- P3: inherited mutable GitHub Action major tags and Redis/MinIO tags only.

No reviewer edited or pushed the implementation branch. Reviewers did not
access or modify `/opt/meddoc-pro`.

## Reproduced verification

| Gate                                              | Result | Exact evidence                                                        |
| ------------------------------------------------- | ------ | --------------------------------------------------------------------- |
| Full TranscribeMD suite                           | PASS   | 428 files / 5,788 tests                                               |
| Focused hardening suite                           | PASS   | 8 files / 192 tests                                                   |
| Focused auth/authz/MFA suite                      | PASS   | 14 files / 433 tests                                                  |
| Shared auth package                               | PASS   | 4 files / 73 tests                                                    |
| MedDoc seeded database unit suite                 | PASS   | 11 files / 103 tests                                                  |
| MedDoc auth-runtime focused suite                 | PASS   | 2 files / 7 tests                                                     |
| Application TypeScript                            | PASS   | No errors                                                             |
| Synthetic-helper package TypeScript               | PASS   | Dedicated no-emit project; no errors                                  |
| Parent/head test discovery                        | PASS   | Identical 428-file / 5,788-test manifests                             |
| Rejected-parent regression                        | PASS   | `6f8f3e1` reproduced `TS2345` and had 5 fewer MFA regression tests    |
| Production principal census                       | PASS   | 7 exact services                                                      |
| QA principal census                               | PASS   | 2 exact services                                                      |
| Rollback census                                   | PASS   | 6 long-lived services; one-shot migrator excluded                     |
| Immutable-image MFA permission differential       | PASS   | No gid 1001 denied; exact consumer groups read root:1001/0440         |
| Closed synthetic database release                 | PASS   | 97/97 migrations plus six exact-principal proofs                      |
| Closed synthetic cleanup                          | PASS   | Zero labeled containers, volumes, or images; private channels removed |
| Production TranscribeMD build                     | PASS   | Next.js 16.2.6 plus server-action manifest gate                       |
| Production MedDoc build                           | PASS   | Next.js 16.2.6                                                        |
| Prisma format / validate / generate               | PASS   | Prisma 7.8.0; schema remained clean                                   |
| Workflow YAML, shell, and embedded Node syntax    | PASS   | 3 workflows / 60 shell blocks / 3 embedded Node blocks                |
| Strict TypeScript Semgrep                         | PASS   | 792 requested files; 0 findings, 0 errors, 0 skipped                  |
| Exact `fc08599..4b6ba9e` offline secret scan      | PASS   | 0 findings                                                            |
| Exact `fc08599..4b6ba9e` verified-only scan       | PASS   | 0 verified findings                                                   |
| Reviewer verified-only main-target scan           | PASS   | 954 main-target files; 0 verified findings                            |
| Dependency high/critical gate                     | PASS   | 0 critical, 0 high; 12 moderate and 1 low remain debt                 |
| Changed application lint                          | PASS   | No findings                                                           |
| Full TranscribeMD lint, honest inherited baseline | PASS   | 25 errors / 37 warnings, unchanged from recorded baseline             |
| Full MedDoc lint                                  | PASS   | 0 errors / 3 warnings                                                 |
| Prettier and diff whitespace                      | PASS   | Clean                                                                 |
| Repository state after lead verification          | PASS   | Clean exact `4b6ba9e`                                                 |

The initial standalone MedDoc unit invocation lacked its required synthetic
database channel and failed before valid fixture setup. The lead reran it only
after the closed 97-migration provision and synthetic seed; all 11 files and
103 tests then passed. No false green is claimed for the invalid first run.

## Remote and release truth at review

- `origin/main`: `1be101912f01293de3b8fddae722c823ecc86f29`
- PR #371: OPEN, draft, merge state BLOCKED.
- Published PR #371 head:
  `fc08599533f75dbd7bdf878a9d23595ab83d4be0`
- Local accepted exact head `4b6ba9e` remained intentionally unpushed while
  this receipt was created.
- Production migration/deployment/flag/provider operations: none.
- Production rollout: 0%.
- Human Word, Clinical Safety, Privacy/Legal, Operations, and production change
  gates: still pending.

## Protected worktree

Release agents made no writes to `/opt/meddoc-pro`. Existing evidence records
its branch `feat/template-twin-docx-v1` and SHA
`bb1c828189ee95f85136c7ebd79d07e52467782a`. A read-only fingerprint was
transiently observed changing from and back to the accepted `f2426a8…` value;
the concurrent delta is unattributed and temporal continuity remains failed.
The protected worktree was not used for this receipt or review.

## Remaining gates

This ACCEPT closes exact-head technical review for the additive auth/CI
hardening only. It does not close hosted PR CI, Office/Word evidence, provider
quality, full production infrastructure and restore, immutable signed release
images, a real six-runtime rollback rehearsal, credential rotation, human
approvals, production change authority, or any rollout checkpoint.
