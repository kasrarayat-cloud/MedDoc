# Evidence manifest — completed-document candidate v1

Branch: `release/completed-document-candidate-v1`

Exact base: `581b5b5cfe17655f0994a382ccde5ca98088f4a9`

The additive commit SHA is recorded in the release-program handoff because a
commit cannot include its own content-addressed identity.

## Redacted review-preview receipt hardening v1.1

Branch: `agent/completed-candidate-preview-receipt-20260719`

Exact base: `7d40c5c01873e8dbe15a0a54f7eae9064b6095d2`

This additive hardening closes the physician pre-approval comparison gap. The
initial review response no longer carries the structural projection. An
authenticated, same-origin preview request validates and returns the exact
value-redacted source/candidate topology with a 15-minute memory-only receipt;
terminal review must consume that exact proof atomically. This is technical
synthetic-only evidence, not independent exact-head acceptance or a human
approval.

### v1.1 artifact hashes

All values are SHA-256 over the exact working-tree bytes after formatting and
before the additive commit.

| SHA-256                                                            | Artifact                                   |
| ------------------------------------------------------------------ | ------------------------------------------ |
| `4ba1f42883f790d15a8913341484c6bb29850add32dec84a8a0ad4d795d68682` | strict completed-candidate contract        |
| `573909639ae525609109b309e3c3315c9354369634eff3f19d293595015b5509` | completed-candidate service                |
| `89c09a0119cf3cbb723a7022d874fa7c7d0f1cd26d5cc3a3255b6e7e6ac17cd0` | review-preview route                       |
| `b398de1fb5900f250ae8437cd1562cd090f4e4c80890e97434a6edb180286e37` | terminal review route                      |
| `f6e7e61d08f17e893bf103c30436024fb8f860d08f832eaa197cc8d4ea7905db` | physician workspace                        |
| `4e5d362529d70be3db36260fa25d2e5bc5321900eb5ed155086b7aff12b8a27f` | physician workspace CSS                    |
| `a6a1bf480677a36a2cac5f4c543a42dfe1c64d24206942d9ecdae43ef7008ef9` | account-deletion retention gate            |
| `e04467c7fd608309ff0e4a83aa6e6335c6aa67264dac40e4a092d0e1b157c3d0` | Prisma schema                              |
| `7476fb84900972a2a9bd6f2da893d53984802910ccc13a25ceca868c6c53557a` | additive receipt/projection migration      |
| `444001625dceac9780c60bf9b68565d38578e0a2b02a1e82b9f1588c1434d0ad` | disposable PostgreSQL tamper contract      |
| `7f7ba69571ac7ce8b99eec2a35ee30c027e56decd34f1e0b3ebc1a421f0e5bed` | converter/strict-projection tests          |
| `5c6f3d2a8a616be0e400a701bcd7aeeeee6049b858260bdd7a91eef67ccabcfc` | service/receipt tests                      |
| `635d7a470086d84a8c332e6b49221b2966ac2a7b5b3e6c042c9354e73d5fd664` | migration-contract tests                   |
| `9f43a6d19365fd70f71267945b20bff03c484fcc7621d4bdd854788551a0cef9` | preview-route tests                        |
| `894de929f03de443ac293d9862b13be45699cc242bbcc66d58ddec601f3dd1e1` | physician-workspace tests                  |
| `9a737a1f943b07acff3b2c39659fc7c8e93b684411b1cba02cd0008d2d215763` | account-deletion retention tests           |
| `26139808e6d3ba1cdd882af56da3a3e08e0ba3971745762650efb53532eb7320` | supported/unsupported compatibility matrix |
| `308da333e7fdc6c57d5b60106ad4d3a614b79a5990dbaf96eebd3fd568b83683` | preflight report                           |

### v1.1 verification census

| Gate                                | Result     | Evidence                                                                                                                                                                                                                                                                                                            |
| ----------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Equivalent repository preflight     | FIX-AND-GO | Clean isolated worktree at exact base; 24 GiB free; dependency-cache symlink documented in `preflight-20260719T092252Z.md`; protected `/opt/meddoc-pro` untouched                                                                                                                                                   |
| Complete affected application tests | PASS       | 9 files, 61 tests: completed-candidate access, converter, service, base/new migration contracts, upload/preview routes, physician workspace, and account-deletion retention                                                                                                                                         |
| Application TypeScript              | PASS       | `npx tsc --noEmit` from `apps/transcribe-md`                                                                                                                                                                                                                                                                        |
| Focused ESLint                      | PASS       | All changed TypeScript/TSX service, route, UI, policy, and test paths                                                                                                                                                                                                                                               |
| Prisma format / validate / generate | PASS       | Prisma 7.8.0; final generated client includes receipt model and audit enum                                                                                                                                                                                                                                          |
| Fresh migration chain               | PASS       | All 82 migrations applied to a new disposable `pgvector/pgvector:pg16` database                                                                                                                                                                                                                                     |
| Live database tamper contract       | PASS       | Valid terminal path plus projection digest/topology/label/redaction-state/source-order tamper, rollout-generation mismatch, receipt-only consumption, unconsumed terminal transition, expiry backdating, and replay all exercised; final marker `PASS template-twin-completed-candidate-review-preview-contract-v1` |
| Migration defect reproduction       | FIXED      | First live run reproduced a deferred JSON-table alias failure; migration was corrected, the database was recreated, all migrations reapplied, and the complete contract passed from a clean state                                                                                                                   |

The exact additive commit SHA and the final staged-diff whitespace/secret-scan
results are recorded in the release-program handoff after the commit. No
credential, patient/physician document, source value, or production environment
evidence is part of this manifest.

## Artifact hashes

All values are SHA-256 over the exact working-tree bytes immediately before the
additive commit.

| SHA-256                                                            | Artifact                                        |
| ------------------------------------------------------------------ | ----------------------------------------------- |
| `dc78689ac8b7fd870b27a7dc80d8b292c1c4b3f64bfe6278dd2245a72d0a8007` | `completed-candidate-access.ts`                 |
| `492b60f94e5b3480e392c51ded05ac4d3beda4f2bcc0bfacf2e3736157755c9d` | `completed-candidate-contract.ts`               |
| `2aa5cd894f184f2f4e7fd61f61a02399a41b808db02e1b3eda3fa4505229030c` | `completed-candidate-converter.ts`              |
| `41da2fdd0461895be0f5fbf0ca180a43ca31689458120dce0be869555c4fa3ad` | `completed-candidate-service.ts`                |
| `992b03a26bda659a5a2168e02e51b6698e4a4d01dee707306f8d7915176510bf` | upload route                                    |
| `cc8bba1342f1d0df1c19a27619a4af88ebd72677d1ba9db4b71b2e7929e907e4` | physician-review route                          |
| `9223dcb1c9d0771dfc10c8bb90ee67d3284f2b6d83d5c026f3164ca077da696a` | approved-candidate download route               |
| `49447c3e21909ae163faf822ee665e511a3123fe7a35c1d6e2a702fbdfbd9a48` | physician workspace                             |
| `d05047c2102785b3aae121b9c8e0004e7ac37092dbf5ae1d49e89426c4057d85` | physician workspace CSS                         |
| `f3140fcd2f09e4e154f5a775997663e187686e692548be361a708d8ca22891e0` | additive PostgreSQL migration                   |
| `b2efdf0d50c8016f7d17f67918858154c578e0b8984529ef7a077ef49b0ac398` | PostgreSQL positive/negative contract rehearsal |
| `bd38a5973102c6ba5215f0fac8a042911b7bee07da4b9aaed28750dfba7455ec` | supported/unsupported compatibility matrix      |
| `da30889c09df802093867372367c5a2faf68f12810dbc5834ae8bf02e2165a49` | converter tests                                 |
| `7767938f6f9d3a4f75095fea3ddf3ffa7bc7bb817704e0173defe3c3ccdf6d8f` | service tests                                   |
| `2e7455328331fc7e2e3c04b8bbcfd2407a8c94b1464a82f8150367704db903ab` | migration contract tests                        |
| `09a0d71475482a047179aa45fcd70663ee2691d7d92d05bca3f7fa691d388119` | upload-route tests                              |
| `9c016ad7a61be2a46de7a51cff6de0351384979535b6a0ddb37500d6b62ca18e` | physician-workspace tests                       |

## Verification census

| Gate                        | Result     | Evidence                                                                                                                                     |
| --------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Repository preflight        | FIX-AND-GO | Clean isolated worktree; dependency cache symlink documented in `preflight-20260719T072904Z.md`                                              |
| Focused and affected tests  | PASS       | 14 files, 120 tests passed                                                                                                                   |
| TypeScript                  | PASS       | `npx tsc -p apps/transcribe-md/tsconfig.json --noEmit`                                                                                       |
| Focused ESLint              | PASS       | Completed-candidate, settings, quarantine, storage, and affected mock/test paths                                                             |
| Prisma format               | PASS       | Prisma schema formatted                                                                                                                      |
| Prisma validate             | PASS       | Schema valid                                                                                                                                 |
| Prisma generate             | PASS       | Prisma Client generated successfully                                                                                                         |
| Migration application       | PASS       | Fresh disposable clone `tt_completed_candidate_v5`, PostgreSQL 16; explicit transaction committed                                            |
| Database contract           | PASS       | Positive candidate transaction plus negative review-bypass, terminal-quarantine-mutation, and tenant-object-key cases; rehearsal rolled back |
| Diff whitespace             | PASS       | `git diff --cached --check`                                                                                                                  |
| Offline secret pattern scan | PASS       | No staged-diff match for private keys, common cloud/API tokens, credentialed service URLs, environment assignments, or JWT-shaped tokens     |
| Identity string census      | PASS       | Only `doctor@synthetic.test` appears in staged test evidence                                                                                 |

## Gate boundary

This manifest verifies a technical synthetic-only slice. It is not an
independent exact-head acceptance, Privacy/Legal approval, Clinical Safety
approval, desktop Microsoft Word evidence, production authorization, or a
claim of arbitrary-DOCX support.
