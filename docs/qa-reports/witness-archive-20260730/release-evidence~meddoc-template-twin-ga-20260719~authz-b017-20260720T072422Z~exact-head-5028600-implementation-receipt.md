# Authentication and database-release hardening implementation receipt

Generated: 2026-07-21T05:30:34Z

## Verdict

**IMPLEMENTATION COMMITTED; INDEPENDENT EXACT-HEAD VERDICT PENDING;
PRODUCTION RELEASE FAIL.** This receipt records defensive synthetic evidence
only. It authorizes no production migration, deployment, provider call,
credential change, PHI, canary, or physician rollout.

## Immutable identity

- Branch: `fix/template-twin-provider-ownership-b017-v1`
- Rejected parent: `2d9c8f8e41fc0e20279ae3d6a253ec10405bc367`
- Additive candidate: `50286004f9bc7f940602206e50b24679ab1c2b38`
- Git tree: `465d0b6908f8dfcfe49bc3f1993119fbdbff5e91`
- Binary diff SHA-256, parent to candidate:
  `4ade2afb6486d7cc4e90629dd19d4fe7fd0f168f98becc9df57887989a28f004`
- Recursive Git tree-listing SHA-256:
  `814db61485a2be274dced74f0f735e484699d4a419546a61d4f5ce19ea1e04d9`
- Worktree immediately after commit: clean

## Defensive closure

- One retained target-proved PostgreSQL session owns both the auth-token
  advisory lock and every mutation.
- Approval binds exact principal and database ownership, cluster/database
  identity, recovery state, phase, proof version, and a fresh protocol epoch.
- Auth finalization takes a bounded exclusive table lock and re-proves the
  exact index, duplicates, and transition trigger before exact removal and
  again before commit.
- Exact-principal hashing includes stable internal referential-integrity
  enforcement semantics while normalizing unstable catalog-generated names.
- Segmented migration approvals bind phase, current ledger, accepted source,
  target, and recovery state; raw Prisma operator paths are prohibited.
- Lineage uses one locked target-proved session and never emits a cursor value.
- Strict SCRAM HBA admission, an immutable guarded PostgreSQL image, and a live
  host-auth proof are part of runtime principal admission.
- Synthetic execution uses a digest-pinned nonprivileged executor, read-only
  source/root filesystems, a namespace-local database network, minimal
  environment, production-route refusal, and unconditional labeled cleanup.

## Implementation-side verification

- Two independently created zero-state synthetic release environments applied
  all 97 migrations, completed auth/lineage/release transitions and six exact-
  principal proofs, and emitted fixed provision and cleanup PASS markers.
- Reversible internal RI-trigger tamper: baseline PASS, disabled enforcement
  rejected, restored enforcement PASS.
- Focused operator/source/auth/lineage/HBA: 14 files, 284 tests PASS.
- App migration and role-graph contracts: 2 files, 10 tests PASS.
- Independent HBA/runtime-principal scope: 5 files, 169 tests PASS.
- Live pinned-image PostgreSQL HBA integration and shell syntax: PASS.
- Full TranscribeMD TypeScript, changed-file lint, formatting, and diff
  whitespace: PASS.
- Whole-workspace verified-only secret scan: 0 verified findings.
- Provider calls: 0. Production writes: 0. PHI: 0.

## Exact-head verification after commit

- Full TranscribeMD unit census: 426/426 files and 5,754/5,754 tests PASS.
- A direct MedDoc invocation first failed before assertions because no valid
  synthetic database credential was present. The failure was reproduced as a
  harness error, not represented as green, and no credential was inspected or
  printed.
- A third fresh closed synthetic database applied all 97 migrations, seeded
  only the repository's synthetic tenancy fixtures, and passed the full MedDoc
  census: 11/11 files and 103/103 tests. Cleanup passed; its mode-0600
  credential file and exact task directory were destroyed.
- Prisma 7.8.0 format check, validate, and generate: PASS.
- Standalone TranscribeMD and MedDoc TypeScript: PASS.
- TranscribeMD Next.js 16.2.6 production build and server-action manifest gate:
  PASS; 30 source and 28 compiled exports classified.
- MedDoc Next.js 16.2.6 production build: PASS.
- Changed-file lint: PASS. Full repository lint is honestly unchanged from the
  recorded parent baseline: TranscribeMD 25 errors/37 warnings and MedDoc 0
  errors/3 warnings; no existing debt is represented as green.
- Exact SHA/tree and clean worktree were unchanged after these gates.

### Test census comparison

| Suite | Exact parent `2d9c8f8` | Exact candidate `5028600` | Delta |
| --- | ---: | ---: | ---: |
| TranscribeMD files | 417 | 426 | +9 |
| TranscribeMD tests | 5,614 | 5,754 | +140 |
| MedDoc files | 11 | 11 | 0 |
| MedDoc tests | 103 | 103 | 0 |

Every candidate test in this census passed. The added files/tests are the
database release, auth-token, exact-principal, lineage, HBA, and operator-
documentation contracts in the additive diff.

The committed exact head is now assigned to a fresh detached reviewer. These
implementation-side results are claims for that reviewer to reproduce, not an
approval.

## Open gates

Independent detached ACCEPT, exact-head full-suite/build/security evidence,
PR CI, production backup/restore and identity authority, immutable deployment
images and rollback rehearsal, credential rotation, desktop Word evidence,
provider-quality evidence, and signed Clinical Safety, Privacy/Legal, and
Operations approvals remain mandatory. Production availability is 0%.

`/opt/meddoc-pro` was not switched, reset, cleaned, stashed, or modified by
this implementation. Its final branch/SHA/status reconciliation remains
required.
