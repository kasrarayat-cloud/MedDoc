# Exact database-principal and auth-token evidence

Generated: 2026-07-21T00:45:23Z

## Verdict

**TECHNICAL PASS IN DISPOSABLE SYNTHETIC POSTGRESQL 16; INDEPENDENT EXACT-HEAD
REVIEW FAIL (NO COMMITTED CANDIDATE); PRODUCTION RELEASE FAIL.** Required human
approvals remain **HUMAN PENDING**. This evidence does not authorize a
production migration, credential rotation, PHI, deployment, canary, or
physician rollout.

The verified working tree is based on branch
`fix/template-twin-provider-ownership-b017-v1` at
`e7b3864dc6d61d7d36755f59f87909bb7394740d`. The changes recorded here were
not committed when this receipt was generated. The final committed exact head
must receive a fresh detached review and rerun the release gates.

## Frozen structural migration

| Artifact                              | SHA-256                                                            |
| ------------------------------------- | ------------------------------------------------------------------ |
| Exact database-principal v9 migration | `8d2c4fe1075490085b34397cdecde3d8c6e50b3e21c778ac9d491da071faf404` |
| v9 generator                          | `1332214a34fc8f242ccd2b8d3919519cf0ead89904c48f061cb4d8d0a69677ad` |
| Frozen helper `prosrc`                | `4e96e14b9bd337559df5a178a83d76490fa6cba73aed3ced3b2c4a4da644ee01` |
| Pre-backup hook                       | `4344c1277dd436edd6622e388be3c5921f10bd6fd039a09f8284c1a50abf725d` |
| Normalized hook helper semantics      | `61db58de71d232b29e38044cd4c4c7b310209e90be50377039b80ec19900c30e` |
| Backup-principal provisioner          | `f456bd7efb1f79879a165cd5f4a97ff24d3ee57df8e6207fee23ca4702f5810c` |
| Backup-principal PostgreSQL harness   | `b2abdaa10a813392ea294bddedb8fa1d65ac87664f1e65b8650b2eb6c70bb91e` |

The migration creates the fixed
`public.quillmd_boundary_password_is_null(text)` helper. It exposes only a
boolean for the reviewed fixed roles, never a verifier. Runtime, provisioning,
and pre-backup proofs bind its source, owner, ACL, configuration, and shared
dependency tuple. They also require every login verifier to retain the exact
SCRAM shape without returning credential material.

V9 contains only plan-independent target, role/password/membership, helper,
ACL, and shared-dependency assertions. PostgreSQL deparse output changes when
the full runtime catalog query is nested inside a migration assertion, so v9
does not freeze a second context-specific digest. The unchanged runtime-
protocol query is the mandatory immediate post-migration gate; a source
contract test enforces this ordering.

## Frozen runtime manifests

PostgreSQL image:
`pgvector/pgvector@sha256:7d400e340efb42f4d8c9c12c6427adb253f726881a9985d2a471bf0eed824dff`
(PostgreSQL 16.13).

| Manifest                              |  Rows | SHA-256                                                            |
| ------------------------------------- | ----: | ------------------------------------------------------------------ |
| Full application ACL/semantic closure | 4,141 | `17af3f8af88bf594576f30c2cfa9bd6b1ee78b7e1447a9064ca657b71c1cfdd6` |
| Application `PUBLIC` closure          |   504 | `d5e24c7cd5c7b20491973623e3f2387eb72dd2461f78a931897345b5cfd8ad16` |
| System `PUBLIC` closure               | 4,046 | `b2bf14053b1e8d8a0f135bd315f1c2c79a97f6957ab6a718fbed67c4aaf69746` |
| Future default ACL closure            |     0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `quillmd_runtime`                     |   260 | `9a57516235a2bf6e05d78ece57b36a8181b0940517dbac327b2ec38fecb08491` |
| `quillmd_release_control`             |    53 | `1b19ff4639456ed2198b33093733743bf844ff1b0ea535cd96fae987401eb9d2` |
| `quillmd_release_security`            |     3 | `08d8966d88162b49e4a19e8e0054a8d507a1d6830bedefc7a6267d852a83974d` |
| `quillmd_audit_dispatcher`            |     7 | `3bcd5b8e7e9a2a11004d05e262a44dcbfccc4cd835e9ac8db844cb76425205ca` |
| `quillmd_auth_email_dispatcher`       |    10 | `dc350422fa6da53ea697ba61956de992022ed3daad93f80227698d361be6e9a3` |
| `quillmd_backup`                      |     2 | `e059a6bf37ca30b019ce585d518ae8d8441ec09aa864a3a1e323065b31a58fe5` |

Two independently created full-role clusters produced byte-identical JSONL
files for every table row above. A third cluster proved v9 and all required
profiles with the optional release-security login absent. Restricted JSONL
exports were removed after byte comparison; no catalog entries, credentials,
URLs, or environment files were retained in the repository.

## Verification

| Gate                                                                                                                               | Result                               |
| ---------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| Fresh exact-v9 structural migration                                                                                                | PASS on two full-role clusters       |
| Optional release-security-login-absent migration                                                                                   | PASS                                 |
| Immediate external runtime manifest after migration                                                                                | PASS for every present profile       |
| Adversarial exact-principal PostgreSQL harness                                                                                     | PASS                                 |
| Unsafe search path, role attribute/login-verifier/graph drift                                                                      | rejected                             |
| Outgoing membership from predefined `pg_read_all_data`                                                                             | rejected before and after v9         |
| System/application ACL, enum, rule, unapproved-login, template database, role-setting, large-object, grantor, and membership drift | rejected and exact baseline restored |
| Credential bootstrap plaintext/verifier log scan on pinned PostgreSQL                                                              | PASS                                 |
| Shared database startup search path and statement-timeout PostgreSQL proof                                                         | PASS                                 |
| Exact-principal preflight for runtime, release-control, release-security, audit-dispatcher, and auth-email-dispatcher profiles     | PASS                                 |
| Authentic pre-v6 role graph, membership options, optional role, nested role, and assumed-session proof                             | PASS                                 |
| Auth-email outbox concurrency: 24 unique claims, no persisted raw bearer, zero provider calls                                      | PASS                                 |
| Auth-token concurrency: 16 concurrent mints, one current token, one successful consume                                             | PASS                                 |
| Backup principal drift, lock contention, rollback, dump, restore, restored-cluster re-provision, and post-restore preflight        | PASS                                 |
| Targeted database-principal unit/source contracts                                                                                  | 4 files, 229 tests PASS              |
| Associated role-graph/authorization unit contracts                                                                                 | 5 files, 71 tests PASS               |
| Full TranscribeMD TypeScript                                                                                                       | PASS                                 |
| V9 generator byte-sync check                                                                                                       | PASS                                 |
| Shell syntax for the two credential provisioners                                                                                   | PASS                                 |

The synthetic auth-token online proof also passed from an authentic pre-v5
database: deterministic reconciliation retired two older rows from one legacy
duplicate group; same-statement, READ COMMITTED race, REPEATABLE READ, and
SERIALIZABLE cases failed closed as expected; interrupted concurrent-index
recovery, exact-index and trigger checks, operator contention, 16 concurrent
mints, 16 concurrent consumes, and 12 atomic mutation attempts all preserved
one-current-token and one-winner invariants. The test used synthetic-only
identifiers and retained no tokens or hashes.

An independent reviewer returned **ACCEPT** for the frozen v9 and
backup-principal working-tree scope after independently checking the generator,
shell syntax, formatting, exact PostgreSQL role/ACL behavior, checksum drift,
lock contention, rollback, dump, and restore. That scoped working-tree verdict
is not an exact committed integration-head ACCEPT and cannot authorize release.

## Open gates

This receipt is not final release evidence. A committed exact head, independent
detached ACCEPT, repository CI/census, production backup and restore authority,
credential rotation, deployment/rollback evidence, desktop Word evidence, and
signed Clinical Safety, Privacy/Legal, and Operations approvals remain
mandatory. `/opt/meddoc-pro` was not switched, reset, cleaned, stashed, or
modified by release agents. Its branch/SHA remain unchanged, but its
NUL-delimited status fingerprint changed from `f442687…` to `f2426a8…` for an
unattributed/concurrent reason; exact fingerprint continuity is not claimed.
