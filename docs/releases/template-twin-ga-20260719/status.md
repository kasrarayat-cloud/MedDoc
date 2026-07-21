# QuillMD Template Twin GA release-program status

Last updated: 2026-07-21T07:48:57Z

## Production verdict

**NOT RELEASED.** Production availability remains **0%**. This hardening series
performed no production migration, deployment, flag change, provider call, or
PHI-bearing test. Template Twin remains unauthorized for production use.

## Exact source records

| Record                                        | Exact value                                                                                                                                                                                                                                | Status |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------ |
| Local `origin/main` reference                 | `1be101912f01293de3b8fddae722c823ecc86f29`; last remotely verified 2026-07-21                                                                                                                                                              | PASS   |
| Accepted remediation                          | `79c04e88785a16e8e3b37b58544e107e3a16996e`; parent `b46c62f97544a0193c60929d5ac8e8870b20dc4b`                                                                                                                                              | PASS   |
| Lossless stack integration                    | Merge `719eea4b27c68cc76e6bf485612c833705cef913`; accepted tree preserved                                                                                                                                                                  | PASS   |
| Provider-ownership head                       | `db1cab904ac5c8d6c7f25878f59d71e1b094a223`                                                                                                                                                                                                 | PASS   |
| Authentication/authorization implementation   | `9a1ded49055d1aef153864b28267c81ab1b0506d`                                                                                                                                                                                                 | PASS   |
| Current committed auth/runtime implementation | `fix/template-twin-provider-ownership-b017-v1` at `25047df1fe095e47610b9e9eda4e25bb2b821d46`; tree `58c7d400886ad4e745e47c6883ad4ddbba9924b3`; parent `50286004f9bc7f940602206e50b24679ab1c2b38`                                           | PASS   |
| Independent review of `50286004`              | **REJECT**. Core auth/operator fixes reproduced successfully; one P1 obsolete raw-migration instruction and P2 release-record, actual-PostgreSQL regression, cleanup, strict-parser, diff-whitespace, and dependency-debt items remained   | FAIL   |
| Independent security review of `3a915158`     | **REJECT**. Every executable security gate passed; two P2 evidence-document defects remained: an unbound current-scan claim and malformed escaped approval blanks                                                                          | FAIL   |
| Lead formatting gate of `b016bfe`             | **REJECT**. Both prior documentation P2s and their regression test passed, but four changed files were not Prettier-clean while every corresponding parent blob was clean                                                                  | FAIL   |
| Exact-head review payload                     | Auth/runtime implementation `25047df1`, `3a915158` records, `b016bfe` evidence correction/test, and this additive formatting closure. A commit cannot contain its own hash; final identity and hashes are recorded externally after commit | PASS   |
| Current exact-head review verdict             | The `b016bfe` formatting debt is corrected here, but a fresh detached review of the resulting exact commit is mandatory; no ACCEPT exists yet                                                                                              | FAIL   |
| Consolidated draft PR                         | PR #371 targets `main`, but its last recorded published head `9088f74f17e11ff3f7e5869e5a56b6c5d36796fd` does not contain this series                                                                                                       | FAIL   |
| Frozen release candidate                      | Not created                                                                                                                                                                                                                                | FAIL   |
| Current production Git SHA                    | Not reproducible from a clean commit at the last authorized inventory                                                                                                                                                                      | FAIL   |

The candidate contains **97 ordered Prisma migrations**; the ordered-name
manifest SHA-256 is
`62efcdab3aea04ad635a1c01d0dab21f360e27a78cb87aab32cbeb3b8ca6040f`.
Two independently created disposable synthetic PostgreSQL release environments
each applied all 97 migrations, completed the closed auth/lineage/release
transitions and six exact-principal proofs, and cleaned up successfully at exact
`50286004`. That rejected head is not a final-head receipt. The 96/96
authentication-email and MFA receipts below remain historical evidence from
`e7b3864`. Production was last observed at 67 migrations; that dated inventory
is not authorization or proof of current production state.

## Phase status

| Phase                                             | Status        | Evidence / blocking condition                                                                                                                                                                                                                                                                          |
| ------------------------------------------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 0 — Preflight and inventory                       | FAIL          | The equivalent preflight and read-only inventory exist, but deployed provenance, least-privilege production identities, PITR, complete restore, internal transport, capacity, monitoring, and credential-rotation gates remain open.                                                                   |
| 1 — Consolidated implementation                   | FAIL          | Accepted history is preserved. Auth/runtime closure is at `25047df1`; the `3a915158` documentation P2s were corrected at `b016bfe`, which failed only its new-diff formatting gate. This additive formatting closure still requires a fresh detached exact-head verdict.                               |
| 2 — Production template intake                    | FAIL          | Misplaced Word-control remediation and completed-document conversion are integrated; production scanner readiness, final compatibility evidence, and combined exact-head review remain open. Unsupported structures continue to fail closed.                                                           |
| 3 — Extraction quality                            | FAIL          | Provider ownership now covers the released path technically, but the release-head live-provider clinical cohort remains `n=0` and Clinical Safety approval is HUMAN PENDING.                                                                                                                           |
| 4 — Microsoft Office compatibility                | FAIL          | Office evidence binding and misplaced-control remediation are integrated. Final-SHA corpus generation and returned desktop Word evidence remain mandatory; Word approval is HUMAN PENDING.                                                                                                             |
| 5 — Infrastructure and operations                 | FAIL          | Two fresh zero-state 97-migration release replays, candidate exact-principal/RI-tamper proof, and historical backup-role dump/restore/re-provision pass. Production identities, immutable image digests, real six-container rollback, PITR/object/queue recovery, and named ownership remain unproven. |
| 6 — Privacy/Legal, Clinical, Operations approvals | HUMAN PENDING | No implementation agent may supply these decisions.                                                                                                                                                                                                                                                    |
| 7 — Final release candidate                       | FAIL          | The auth/runtime closure is at `25047df1`; the two `3a915158` P2s were corrected at `b016bfe`, whose introduced formatting debt is corrected here. The replacement exact head has not received independent ACCEPT. No frozen or accepted RC exists.                                                    |
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

## Current committed and follow-up evidence

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
- Exact `50286004` passed the full TranscribeMD suite (**426/426 files and
  5,754/5,754 tests**), full MedDoc suite (**11/11 files and 103/103 tests**),
  both standalone TypeScript checks, Prisma 7.8.0 format/validate/generate,
  both production builds, changed-file lint, and diff whitespace.
- Exact `25047df1` passes full TranscribeMD TypeScript,
  **427/427 files and 5,758/5,758 tests**, the operator-doc contract
  (**11/11**), cleanup negative paths (**10/10**), changed-file lint, and both
  main-targeting and local diff whitespace checks. Both production builds, one
  fresh closed **97/97** migration replay, MedDoc **11/11 files and 103/103
  tests**, hardened labeled cleanup, and zero residual labeled resources also
  pass. At exact `3a915158`, independent PostgreSQL 16 execution of the queued
  index-drop/finalizer regression and strict HBA harness also passes; the
  companion exact-principal review was still running when this correction was
  authored.
- Exact `3a915158` whole-workspace verified-only secret scan: **0 verified
  findings**; scanner errors are configured to fail the gate. The final
  descendant exact-head scan is recorded in external immutable evidence after
  that commit identity exists.
- Exact `b016bfe` passes the full TranscribeMD unit census (**427/427 files and
  5,759/5,759 tests**), a fresh closed **97/97** migration replay, MedDoc
  **11/11 files and 103/103 tests**, hardened cleanup with zero labeled Docker
  residue, the dependency high/critical gate, and the P2 regression contract
  (**12/12**). Its only lead-agent rejection was introduced Prettier drift in
  four changed files; this descendant is the additive formatting closure.
- Exact-base/head census at `50286004`: parent TranscribeMD **417 files / 5,614
  tests**; candidate **426 files / 5,754 tests** (`+9` files, `+140` tests).
  MedDoc remains **11 files / 103 tests**.
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
- Exact `50286004` had **29 strict Semgrep partial-parse errors** across 790
  main-targeting TypeScript files. The current source-compatible follow-up scans
  all **791/791** with **0 skipped, 0 errors, and 0 findings** under Semgrep
  1.161.0 `p/typescript --strict`. Bash has shell-syntax evidence only; no Bash
  Semgrep result is claimed.
- The detached security review of exact `3a915158` returned **REJECT** solely
  for the two P2 evidence-document defects corrected by this additive change.
  Its executable gates passed: strict Semgrep scanned **791/791** files with
  zero skipped/errors/findings, the dependency gate found zero critical/high,
  the verified-only secret scan found zero verified findings, changed shell
  syntax passed **13/13**, and focused runtime/document tests passed **150/150**.
  Only a fresh detached review of the replacement exact head may decide whether
  the findings are closed.

This is implementation-side evidence for exact `25047df1` plus subsequent
records and evidence-document descendants, not exact-head acceptance. It does
not replace detached review, identical-manifest RC census, PR CI, Office return,
provider-quality evaluation, or production infrastructure and human gates.

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
