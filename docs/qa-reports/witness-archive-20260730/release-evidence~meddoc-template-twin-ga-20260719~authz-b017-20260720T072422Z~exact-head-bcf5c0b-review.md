# Authentication and database-authority exact-head review receipt

Generated: 2026-07-21T01:00:05Z

## Release identity

- Branch: `fix/template-twin-provider-ownership-b017-v1`
- Additive parent: `e7b3864dc6d61d7d36755f59f87909bb7394740d`
- Exact candidate: `bcf5c0bbc098ec777ab850cc3df4e72070453402`
- Git tree: `e22bc6b3b2db4c8cfda58d232c852912c09aed58`
- Binary diff SHA-256, parent to candidate:
  `546ee6f5b707dd8cf50448dcd11a5a7be5d976512cd2ff2b3903989bdbdda8a8`
- Recursive Git tree-listing SHA-256:
  `456317d6a12dc3c41e85fdbb429b08d423fc12c724e2710c93eb69de232226d2`
- Candidate worktree after commit: clean.

## Candidate verification claims supplied to independent reviewers

- Full TranscribeMD unit census: 416 files / 5,600 tests PASS.
- Full MedDoc unit census: 11 files / 103 tests PASS against a fresh disposable
  synthetic database after 97/97 migrations.
- TranscribeMD and MedDoc standalone TypeScript checks: PASS.
- TranscribeMD and MedDoc production application builds: PASS.
- Next.js server-action manifest gate: 30 source exports / 28 compiled exports
  classified, PASS.
- Prisma 7.8 format, validate, and generate: PASS.
- V9 generator byte synchronization: PASS.
- Production runtime census: six long-lived services, one-shot migrator
  excluded, PASS.
- Production database-principal census: seven services, PASS.
- Synthetic QA database-principal census: two services, PASS.
- Disposable PostgreSQL 16 exact-principal, role-graph, auth-token,
  authentication-email, connection-option, bootstrap-log, and backup
  dump/restore/re-provision proofs: PASS.
- Dependency audit: 0 critical, 0 high, 12 moderate, 1 low.
- TruffleHog verified-only whole-workspace scan: 0 verified secrets.
- Semgrep TypeScript changed-file scan: 0 findings / 0 errors.
- Repository lint has no candidate delta: TranscribeMD base/head both 25 errors
  and 37 warnings; MedDoc base/head both 0 errors and 3 warnings. Changed-file
  lint passes.

These are author-side claims, not substitutes for review. Reviewers were told
to use fresh detached workspaces, inspect exact bytes, run proportional tests,
and treat every claim as untrusted until reproduced.

## Independent exact-head review

- Authentication/runtime integration reviewer: **REJECT**. One P1: the
  clinical worker accepted another known service role because it invoked only
  the generic runtime-principal validator. The replacement must assert the
  exact `transcribe-md-worker` role before database and queue/storage startup,
  add mismatch coverage, commit additively, and receive a new detached review.
- PostgreSQL/database-infrastructure reviewer: PENDING.
- Exact-head verdict: **REJECT**.

## Protected-worktree preservation exception

At 2026-07-21T01:24:37Z the database reviewer reported that a diagnostic patch
was accidentally resolved to exactly one new untracked path,
`/opt/meddoc-pro/.review-exact-diagnostics.ts`. The reviewer immediately removed
that same agent-created file and reported no tracked or pre-existing path was
touched. A lead-agent read-only reconciliation then confirmed:

- branch `feat/template-twin-docx-v1`;
- commit `bb1c828189ee95f85136c7ebd79d07e52467782a`;
- NUL-status SHA-256
  `f2426a8fb327fcc6c5ae5721eb6a5f3823ef723eacc72856636eac81054da461`,
  equal to the most recent pre-incident observation;
- the diagnostic path is absent.

The program does not claim perfect no-write continuity. This is a transient
workspace-boundary violation with no observed persistent Git-status delta, not
a production-system change. Final read-only reconciliation remains required.

## Release boundary

Production remains NOT RELEASED at 0%. No production migration, deployment,
feature-flag change, provider call, credential change, PHI use, canary, or
physician rollout occurred. Desktop Word, Clinical Safety, Privacy/Legal,
Operations, credential-rotation closure, production backup/restore, immutable
images, and real rollback evidence remain mandatory gates.
