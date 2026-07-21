# QuillMD Template Twin GA release-program status

Last updated: 2026-07-21T05:19:19Z

## Production verdict

**NOT RELEASED.** Production availability remains **0%**. This hardening series
performed no production migration, deployment, flag change, provider call, or
PHI-bearing test. Template Twin remains unauthorized for production use.

## Exact source records

| Record                                      | Exact value                                                                                                                                                                                                                                                                            | Status |
| ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------ |
| Local `origin/main` reference               | `1be101912f01293de3b8fddae722c823ecc86f29`; last remotely verified 2026-07-19                                                                                                                                                                                                          | PASS   |
| Accepted remediation                        | `79c04e88785a16e8e3b37b58544e107e3a16996e`; parent `b46c62f97544a0193c60929d5ac8e8870b20dc4b`                                                                                                                                                                                          | PASS   |
| Lossless stack integration                  | Merge `719eea4b27c68cc76e6bf485612c833705cef913`; accepted tree preserved                                                                                                                                                                                                              | PASS   |
| Provider-ownership head                     | `db1cab904ac5c8d6c7f25878f59d71e1b094a223`                                                                                                                                                                                                                                             | PASS   |
| Authentication/authorization implementation | `9a1ded49055d1aef153864b28267c81ab1b0506d`                                                                                                                                                                                                                                             | PASS   |
| Current committed baseline                  | `fix/template-twin-provider-ownership-b017-v1` at `2d9c8f8e41fc0e20279ae3d6a253ec10405bc367`; tree `669b4483c9f4f66f0fa610c5e9bbb103d7c3df42`                                                                                                                                          | PASS   |
| Independent review of committed baseline    | **REJECT**; authentication/runtime scope passed, but the reviewer found one P1 stale post-v9 exact-principal manifest                                                                                                                                                                  | FAIL   |
| Current remediation candidate               | Uncommitted additive working tree based on `2d9c8f8`; a snapshot audit returned **BLOCK**, and its auth-session, recovery/principal/state, finalization-race, RI-enforcement, documentation, and P2 findings are implemented and focused-tested; no detached exact-head verdict exists | FAIL   |
| Consolidated draft PR                       | PR #371 targets `main`, but its last recorded published head `9088f74f17e11ff3f7e5869e5a56b6c5d36796fd` does not contain this series                                                                                                                                                   | FAIL   |
| Frozen release candidate                    | Not created                                                                                                                                                                                                                                                                            | FAIL   |
| Current production Git SHA                  | Not reproducible from a clean commit at the last authorized inventory                                                                                                                                                                                                                  | FAIL   |

The candidate contains **97 ordered Prisma migrations**; the ordered-name
manifest SHA-256 is
`62efcdab3aea04ad635a1c01d0dab21f360e27a78cb87aab32cbeb3b8ca6040f`.
Two independently created disposable synthetic PostgreSQL release environments
each applied all 97 migrations, completed the closed auth/lineage/release
transitions and six exact-principal proofs, and cleaned up successfully. This is
working-tree evidence, not a committed final-head receipt. The 96/96
authentication-email and MFA receipts below remain historical evidence from
`e7b3864`. Production was last observed at 67 migrations; that dated inventory
is not authorization or proof of current production state.

## Phase status

| Phase                                             | Status        | Evidence / blocking condition                                                                                                                                                                                                                                                                          |
| ------------------------------------------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 0 — Preflight and inventory                       | FAIL          | The equivalent preflight and read-only inventory exist, but deployed provenance, least-privilege production identities, PITR, complete restore, internal transport, capacity, monitoring, and credential-rotation gates remain open.                                                                   |
| 1 — Consolidated implementation                   | FAIL          | Accepted history is preserved. The latest independent snapshot audit returned BLOCK; every listed auth/authz and operator finding is additively remediated and focused-tested, but the result is uncommitted and has no fresh detached exact-head verdict.                                             |
| 2 — Production template intake                    | FAIL          | Misplaced Word-control remediation and completed-document conversion are integrated; production scanner readiness, final compatibility evidence, and combined exact-head review remain open. Unsupported structures continue to fail closed.                                                           |
| 3 — Extraction quality                            | FAIL          | Provider ownership now covers the released path technically, but the release-head live-provider clinical cohort remains `n=0` and Clinical Safety approval is HUMAN PENDING.                                                                                                                           |
| 4 — Microsoft Office compatibility                | FAIL          | Office evidence binding and misplaced-control remediation are integrated. Final-SHA corpus generation and returned desktop Word evidence remain mandatory; Word approval is HUMAN PENDING.                                                                                                             |
| 5 — Infrastructure and operations                 | FAIL          | Two fresh zero-state 97-migration release replays, candidate exact-principal/RI-tamper proof, and historical backup-role dump/restore/re-provision pass. Production identities, immutable image digests, real six-container rollback, PITR/object/queue recovery, and named ownership remain unproven. |
| 6 — Privacy/Legal, Clinical, Operations approvals | HUMAN PENDING | No implementation agent may supply these decisions.                                                                                                                                                                                                                                                    |
| 7 — Final release candidate                       | FAIL          | The remediation is not yet an exact commit and has no detached exact-head verdict. No frozen or accepted RC exists.                                                                                                                                                                                    |
| 8 — Production deployment and 100% rollout        | FAIL          | No production authority has been exercised; rollout is 0%.                                                                                                                                                                                                                                             |

## Historical scoped verification at rejected `e7b3864`

- Auth/authz release manifest: **116/116 files and 1,362/1,362 tests PASS**.
- Full TranscribeMD TypeScript: **PASS**.
- Targeted ESLint: **163 application files and 17 package/script files PASS**.
- Prisma 7.8.0 format, validate, and generate: **PASS**.
- Diff whitespace check: **PASS**.
- Fresh auth-email PostgreSQL proof: 96 migrations, **PASS**, including
  transactional unique-conflict rollback and zero provider calls.
- MFA v8 backfill and restore rehearsal: 96/96 migrations in both disposable
  databases; encryption, strict plaintext denial, wrong-owner denial, session
  revocation, email-authority cancellation, audit receipt, and restore proof
  **PASS** on synthetic infrastructure.
- Six-runtime rollback guard: static Compose census and focused fake-runtime
  success/failure coverage **PASS** for all three app-image and three
  worker-image long-lived services; the one-shot migrator is excluded.

These scoped passes did not close the review finding. See
`evidence-manifest-auth-authz-mfa-runtime-v1.md`.

## Current pre-commit remediation evidence

- Two independent disposable zero-state executions completed the closed release
  path, all **97/97 migrations**, auth and lineage transitions, six exact-
  principal preflights, and labeled cleanup: **PASS** twice.
- Current focused operator, source, auth, lineage, exact-principal, and HBA
  contracts: **14/14 files and 284/284 tests PASS**. Current app migration and
  role-graph contracts: **2/2 files and 10/10 tests PASS**.
- An independent infrastructure verifier passed **5/5 files and 169/169 HBA
  and runtime-principal tests**, the pinned-image live PostgreSQL HBA harness,
  and shell syntax. PostgreSQL transport encryption remains independently
  unproven for production.
- Full TranscribeMD TypeScript and diff whitespace: **PASS** on the current
  working tree. Current changed JavaScript/TypeScript lint also passes.
- Current whole-workspace verified-only secret scan: **0 verified findings**;
  scanner errors are configured to fail the gate.
- An earlier pre-operator-fix working tree passed the full TranscribeMD suite
  (**416 files / 5,600 tests**), the full MedDoc suite (**11 files / 103 tests**),
  Prisma 7.8.0 format/validate/generate, both production builds, standalone type
  checks, and changed-file lint. Those broader receipts do not bind the latest
  operator diff and must be rerun after the exact candidate is committed.
- Earlier repository lint was unchanged from exact `e7b3864`: TranscribeMD reports the
  same **25 errors / 37 warnings** on base and candidate; MedDoc reports the
  same **0 errors / 3 warnings**. Changed-file lint passes. No baseline debt is
  represented as newly green.
- Earlier exact database-principal source contracts: **4 files / 229 tests PASS**.
- Earlier role-graph and associated authorization contracts: **5 files / 71 tests
  PASS**.
- Disposable PostgreSQL 16 proofs for exact principals, all five runtime
  profiles, credential-bootstrap log redaction, connection options, v6 role
  graph, auth-token concurrency, auth-email outbox concurrency, and backup
  dump/restore: **PASS**. Provider calls remained zero.
- Earlier dependency audit: **0 critical, 0 high, 12 moderate, 1 low**. The 13 lower
  severity findings remain debt pending final RC disposition.
- Earlier TruffleHog whole-workspace verified-only scan: **0 verified secrets** across
  1.386 GB / 160,881 chunks. The source-only offline scan reported 59
  unverified detector matches; the changed-file scan reported 35, all confined
  to named synthetic test/QA fixtures and connection-string contracts. No
  verified secret was found or retained.
- Earlier Semgrep TypeScript scan: **0 findings, 0 errors**. Bash was validated with
  shell syntax checks only; no Bash Semgrep result is claimed.
- The latest independent read-only working-tree audit returned **BLOCK** for
  five P1 categories and four P2 hardening items. All listed findings have been
  implemented additively; only a fresh detached exact-head reviewer may decide
  whether they are closed.

This is working-tree evidence, not exact-head acceptance. It does not replace
the additive commit, detached review, identical-manifest RC census, PR CI,
Office return, provider-quality evaluation, or production infrastructure and
human gates.

## Production and rollback provenance

The last authorized inventory found healthy production containers whose images
had no source-revision labels or registry digests. Their exact image IDs and a
mode-0600 pre-migration archive remain recorded in the Phase 0 manifest and
rollback plan. Those images are forbidden after any Template Twin migration.
Post-migration rollback requires one accepted final-schema-compatible image pair
recreating all six long-lived services with the reviewed bridge protocol.

## Protected-worktree statement

Release agents issued no writes to `/opt/meddoc-pro`; its branch and SHA remain
`feat/template-twin-docx-v1` and
`bb1c828189ee95f85136c7ebd79d07e52467782a`. Its NUL-delimited status
fingerprint changed from
`f442687419e7b111b02f5ee90394330c9df5a4ca4aedd54f908573ba64851946`
to `f2426a8fb327fcc6c5ae5721eb6a5f3823ef723eacc72856636eac81054da461`.
No task-current mtimes were observed, but the change is unattributed and may be
concurrent user activity. Exact fingerprint continuity is therefore not proven;
the protected worktree must remain untouched and receive a final read-only
reconciliation before reporting.
