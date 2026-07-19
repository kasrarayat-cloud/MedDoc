# Evidence manifest — completed-document candidate v1

Branch: `release/completed-document-candidate-v1`

Exact base: `581b5b5cfe17655f0994a382ccde5ca98088f4a9`

The additive commit SHA is recorded in the release-program handoff because a
commit cannot include its own content-addressed identity.

## Artifact hashes

All values are SHA-256 over the exact working-tree bytes immediately before the
additive commit.

| SHA-256 | Artifact |
| --- | --- |
| `dc78689ac8b7fd870b27a7dc80d8b292c1c4b3f64bfe6278dd2245a72d0a8007` | `completed-candidate-access.ts` |
| `492b60f94e5b3480e392c51ded05ac4d3beda4f2bcc0bfacf2e3736157755c9d` | `completed-candidate-contract.ts` |
| `2aa5cd894f184f2f4e7fd61f61a02399a41b808db02e1b3eda3fa4505229030c` | `completed-candidate-converter.ts` |
| `41da2fdd0461895be0f5fbf0ca180a43ca31689458120dce0be869555c4fa3ad` | `completed-candidate-service.ts` |
| `992b03a26bda659a5a2168e02e51b6698e4a4d01dee707306f8d7915176510bf` | upload route |
| `cc8bba1342f1d0df1c19a27619a4af88ebd72677d1ba9db4b71b2e7929e907e4` | physician-review route |
| `9223dcb1c9d0771dfc10c8bb90ee67d3284f2b6d83d5c026f3164ca077da696a` | approved-candidate download route |
| `49447c3e21909ae163faf822ee665e511a3123fe7a35c1d6e2a702fbdfbd9a48` | physician workspace |
| `d05047c2102785b3aae121b9c8e0004e7ac37092dbf5ae1d49e89426c4057d85` | physician workspace CSS |
| `f3140fcd2f09e4e154f5a775997663e187686e692548be361a708d8ca22891e0` | additive PostgreSQL migration |
| `b2efdf0d50c8016f7d17f67918858154c578e0b8984529ef7a077ef49b0ac398` | PostgreSQL positive/negative contract rehearsal |
| `bd38a5973102c6ba5215f0fac8a042911b7bee07da4b9aaed28750dfba7455ec` | supported/unsupported compatibility matrix |
| `da30889c09df802093867372367c5a2faf68f12810dbc5834ae8bf02e2165a49` | converter tests |
| `7767938f6f9d3a4f75095fea3ddf3ffa7bc7bb817704e0173defe3c3ccdf6d8f` | service tests |
| `2e7455328331fc7e2e3c04b8bbcfd2407a8c94b1464a82f8150367704db903ab` | migration contract tests |
| `09a0d71475482a047179aa45fcd70663ee2691d7d92d05bca3f7fa691d388119` | upload-route tests |
| `9c016ad7a61be2a46de7a51cff6de0351384979535b6a0ddb37500d6b62ca18e` | physician-workspace tests |

## Verification census

| Gate | Result | Evidence |
| --- | --- | --- |
| Repository preflight | FIX-AND-GO | Clean isolated worktree; dependency cache symlink documented in `preflight-20260719T072904Z.md` |
| Focused and affected tests | PASS | 14 files, 120 tests passed |
| TypeScript | PASS | `npx tsc -p apps/transcribe-md/tsconfig.json --noEmit` |
| Focused ESLint | PASS | Completed-candidate, settings, quarantine, storage, and affected mock/test paths |
| Prisma format | PASS | Prisma schema formatted |
| Prisma validate | PASS | Schema valid |
| Prisma generate | PASS | Prisma Client generated successfully |
| Migration application | PASS | Fresh disposable clone `tt_completed_candidate_v5`, PostgreSQL 16; explicit transaction committed |
| Database contract | PASS | Positive candidate transaction plus negative review-bypass, terminal-quarantine-mutation, and tenant-object-key cases; rehearsal rolled back |
| Diff whitespace | PASS | `git diff --cached --check` |
| Offline secret pattern scan | PASS | No staged-diff match for private keys, common cloud/API tokens, credentialed service URLs, environment assignments, or JWT-shaped tokens |
| Identity string census | PASS | Only `doctor@synthetic.test` appears in staged test evidence |

## Gate boundary

This manifest verifies a technical synthetic-only slice. It is not an
independent exact-head acceptance, Privacy/Legal approval, Clinical Safety
approval, desktop Microsoft Word evidence, production authorization, or a
claim of arbitrary-DOCX support.
