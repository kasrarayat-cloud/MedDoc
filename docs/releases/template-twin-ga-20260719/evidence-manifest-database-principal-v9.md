# Exact database-principal and release-operator evidence

Generated: 2026-07-21T05:19:19Z

## Verdict

**WORKING-TREE TECHNICAL PASS IN DISPOSABLE SYNTHETIC POSTGRESQL; FRESH
DETACHED EXACT-HEAD REVIEW PENDING; PRODUCTION RELEASE FAIL.** Required human
approvals remain **HUMAN PENDING**. This receipt authorizes no production
migration, credential rotation, provider call, PHI, deployment, canary, or
physician rollout.

The candidate is on branch `fix/template-twin-provider-ownership-b017-v1`,
based on committed SHA `2d9c8f8e41fc0e20279ae3d6a253ec10405bc367` and tree
`669b4483c9f4f66f0fa610c5e9bbb103d7c3df42`. The changes described below were
uncommitted when this receipt was generated. They must be committed additively,
rerun from that exact SHA, and receive a fresh independent detached review.

## Frozen structural migration and current operator artifacts

| Artifact                              | SHA-256                                                            |
| ------------------------------------- | ------------------------------------------------------------------ |
| Exact database-principal v9 migration | `8d2c4fe1075490085b34397cdecde3d8c6e50b3e21c778ac9d491da071faf404` |
| v9 generator                          | `1332214a34fc8f242ccd2b8d3919519cf0ead89904c48f061cb4d8d0a69677ad` |
| Exact catalog query                   | `b74c507807d56c1dde54f7c6ad3698f7bd3c58da05e8aae0c1b59d943c61d32e` |
| Exact-principal contract              | `33e373acf1ec45ade312a6a49519357a529967d645a98a5aba99d4d12e95bca1` |
| Exact-principal preflight             | `f08698caeac2d556d3219ca1a6f315c0f355fe469d481133fd72e3b9f9f3a641` |
| Auth-token operator CLI               | `b590320de7b455761b0ade96da7b4646bc10dd1ed6ffe9bcc6c937cc53596133` |
| Auth-token online core                | `4fdd01e8c7ba74867414767777aae982609d19dac2cf410ae39331eed0b87ea5` |
| Auth-token session lock               | `d08d50d20549dbf9e5cf102ce30f6c024b016771834318a7846d9978497ec314` |
| Lineage operator CLI                  | `93bf09fb86748a1eb2c5ad7f3f7111ec06c81a3100f926d03c3d6cea9f03b0f8` |
| Lineage online core                   | `f2d3dbfba324d5326300e1d230f496e6825db728122e7d65d2750d6b08317b21` |
| Closed segmented migrator             | `46afa3f998057d8834d11142dcd4b8fc5b15c5ad137873517a2294df38dbfe1c` |
| Synthetic release executor            | `128f528a9192c56abb0470c93cfce34bf7ee0291b0644bee40814e40eb06b007` |
| Live host-auth assertion              | `65a15f02d7e29c46d8d95e5d804a19448f72e0c20eb2df6b783a69714b1707d4` |
| PostgreSQL image Dockerfile           | `ea50af8ce2e7561d30931b71490a7c5cfb20799bd9f69ef63c4a1e5f0001035e` |
| PostgreSQL HBA policy                 | `8b76fed3fc6791617a828fcf5f1cbff35d681d3e753cda9594c89df52ea929b0` |
| PostgreSQL entrypoint                 | `1121ef841eea8e0b2c7ba3e23c261f19c2806e17217eedd564eccf8c2d705d0a` |
| PostgreSQL HBA verifier               | `c243bb5e2d1313025c392bb5a510e0e9d289b0f316e0eb236881484bb0d79e18` |
| Production Compose                    | `6455732a235dc623d8c441b08b54a75f41cbc1fc7a891158cd07cf383d28bbe2` |
| QA Compose                            | `2cf1610ca744ce013bd63e6d3ea5657a1374a92645c29c6906481483462f8592` |

The unchanged v9 migration proves the fixed role, verifier, membership, helper,
ACL, and shared-dependency boundary. The mandatory external runtime contract
now additionally normalizes PostgreSQL's unstable internal referential-
integrity trigger names while hashing their stable enforcement state into each
constraint: relation identities, enablement, trigger type and arguments,
deferral state, function identity and owner, language, security attributes, and
function definition hash.

## Current runtime manifests

The disposable evidence used PostgreSQL 16.13 from
`pgvector/pgvector@sha256:7d400e340efb42f4d8c9c12c6427adb253f726881a9985d2a471bf0eed824dff`.

| Manifest                              |  Rows | SHA-256                                                            |
| ------------------------------------- | ----: | ------------------------------------------------------------------ |
| Full application ACL/semantic closure | 4,160 | `cb437ac387bcdc582114b688e183e34bcc3e24fa9b02d35ee6997719f145f008` |
| Application `PUBLIC` closure          |   503 | `f4b0042b47bb887343fcd7868203def89baf31294d1d8419f4ef5f6068385707` |
| System `PUBLIC` closure               | 4,046 | `e299da714d13776e242ee163fbb7aa7942696458aad4f7c23553064812204913` |
| Future default ACL closure            |     0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `quillmd_runtime`                     |   260 | `7c257cc86bc9b83528f62fd76765734b4f85713a297c1d87ed4e141944447e42` |
| `quillmd_release_control`             |    53 | `7dd6b610f5171284e8576eb6ea03927618d7d1aeed15c7fd864a24740de404e8` |
| `quillmd_release_security`            |     3 | `08d8966d88162b49e4a19e8e0054a8d507a1d6830bedefc7a6267d852a83974d` |
| `quillmd_audit_dispatcher`            |     7 | `a30159d922564b79229daedd9052c08bcf1adda95bd9e1c91903b6eedccbed9b` |
| `quillmd_auth_email_dispatcher`       |    10 | `dc350422fa6da53ea697ba61956de992022ed3daad93f80227698d361be6e9a3` |
| `quillmd_backup`                      |     2 | `e059a6bf37ca30b019ce585d518ae8d8441ec09aa864a3a1e323065b31a58fe5` |

These values were derived from the retained, data-bearing but synthetic
contracted cluster. Each of two newly created zero-state release replays then
accepted the same contract for every configured principal after the complete
97-migration chain. No catalog JSONL, identifier, database URL, credential, or
environment file was added to the repository.

## Authentication and authorization defect closure

- Auth-token reconciliation and finalization now use the same retained,
  target-proved PostgreSQL session that owns the advisory lock.
- The approval fingerprint binds the exact `meddoc` principal and database
  owner OIDs, login and superuser state, system identifier, database OID,
  recovery state, phase, proof version, and a fresh protocol-state epoch.
- Recovery targets fail closed. A changed state epoch invalidates a previously
  issued approval.
- Final trigger removal occurs only under a bounded `ACCESS EXCLUSIVE` table
  lock after exact index, duplicate, and trigger reproof. Trigger removal is
  exact, and every invariant is re-proved before commit.
- The segmented migrator's approvals are phase-, ledger-, accepted-source-,
  target-, and recovery-bound. Status exposes fingerprints only for currently
  eligible phases.
- The lineage operator retains one target-proved locked session, refuses
  recovery, and emits only cursor presence rather than the identifier value.
- Active operator documentation permits only the closed segmented runner and
  records the distinct HBA and TLS gates. CI cleanup is unconditional.

## Verification

| Gate                                                                                 | Result                   |
| ------------------------------------------------------------------------------------ | ------------------------ |
| Fresh zero-state closed release replay, 97 migrations, all principal proofs, cleanup | PASS, run 1              |
| Independent second zero-state replay with a new project namespace and credentials    | PASS, run 2              |
| Focused operator/source/auth/lineage/HBA census                                      | 14 files, 284 tests PASS |
| App migration/role-graph contracts                                                   | 2 files, 10 tests PASS   |
| Independent HBA/runtime-principal census                                             | 5 files, 169 tests PASS  |
| Pinned-image live PostgreSQL HBA harness                                             | PASS                     |
| HBA entrypoint and verifier shell syntax                                             | PASS                     |
| Full TranscribeMD TypeScript                                                         | PASS                     |
| Changed JavaScript/TypeScript lint                                                   | PASS                     |
| Whole-workspace verified-only secret scan                                            | 0 verified findings      |
| Diff whitespace                                                                      | PASS                     |
| Production provider calls or PHI                                                     | NONE                     |

The exact-principal tamper proof began from a passing data-bearing synthetic
cluster, disabled one internal referential-integrity trigger, and observed the
mandatory preflight fail closed. The trigger was re-enabled and the exact
baseline passed again. The proof retained no unstable trigger name or catalog
dump.

Both fresh replays used an immutable, digest-pinned nonprivileged executor with
a read-only repository mount and root filesystem, a namespace-scoped database
network, explicit minimal environment, synthetic credentials, production-route
refusal, and labeled cleanup. Both ended with
`SYNTHETIC_CI_DATABASE_RELEASE_PROVISION_PASS` and
`SYNTHETIC_CI_DATABASE_RELEASE_CLEANUP_PASS`.

The separate HBA verifier exercised exact IPv4 and IPv6 SCRAM admission,
wrong-password and unknown-login denial, replication denial, weak-startup and
weak-policy rejection, read-only-rootfs operation, reload invalidation, and
exact restart recovery. No labeled test resources remained. This proves the
host-authentication boundary only; encrypted PostgreSQL transport remains a
distinct unmet production gate.

## Review history and open gates

The independent review of exact committed SHA `2d9c8f8` remained **REJECT** for
the earlier frozen-manifest P1. A later read-only snapshot audit of the
uncommitted candidate returned **BLOCK** for the auth-session lock,
principal/recovery/state binding, final trigger-drop race, internal RI
enforcement omission, and raw operator-documentation paths. The current
working tree implements each requested additive closure plus the reviewer's P2
operator hardening. No implementation agent approves those changes.

A new exact commit and fresh detached reviewer **ACCEPT** remain mandatory.
Repository-wide RC/CI, production identity and backup/restore authority,
credential rotation, immutable images and rollback rehearsal, desktop Word
evidence, and signed Clinical Safety, Privacy/Legal, and Operations approvals
also remain open. Production availability is 0%.

`/opt/meddoc-pro` was not switched, reset, cleaned, stashed, or modified by this
work. Its branch/SHA and NUL-status fingerprint require final read-only
reconciliation before handoff.
