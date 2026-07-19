# Template Twin contracted-schema evidence manifest v1

Generated: 2026-07-19T17:54:54Z

## Scope and verdict

This evidence covers additive schema-contract reconciliation commit
`1685e35aef0d26048e031920a0f6e5da4bc79b1b`. It does not authorize a
production migration or rollout.

Verdict: **PASS** for the disposable fully contracted Prisma drift gate.
Independent exact-head integration review and all production/human gates still
apply.

## Immutable inputs

| Input                                        | SHA-256 / identity                                                                          |
| -------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Git tree                                     | `5b3f8b9e41e7cd3aa03566ebc20d9ace8ca571a9`                                                  |
| `packages/db/prisma/schema.prisma`           | `892a673e65b4e6edac7cd772c773dcbc7069e33108c00d55aa8677a88044558c`                          |
| Contract drift harness                       | `0c6d1a4e11139250bf74f27d3e1024c75bdf8f1e17a2632225be24b720a988d5`                          |
| `packages/db/package.json`                   | `5e375db3c70893d09e2b353e406f73979b480d6012ffd89778ae9a6caabf37ee`                          |
| Ordered 87-directory migration-name manifest | `028dbd6e201c517ed803e1adc968104125e3d0bfbdd4c5aafe988bbee7ed1ed4`                          |
| PostgreSQL test image ID                     | `sha256:8ed3192326bb9d114cd5ef9acace453d5dae17425bd089d089330584c84c5a34`                   |
| PostgreSQL test image digest                 | `pgvector/pgvector@sha256:7d400e340efb42f4d8c9c12c6427adb253f726881a9985d2a471bf0eed824dff` |

## Disposable PostgreSQL results

Each run used a new synthetic-only database whose name contained `test`, trust
authentication confined to a loopback-published disposable container, and all
87 repository migrations. Each container was destroyed after its run. No PHI,
production credential, production object, or production database was used.

| Check                                               | Result                                                                                                |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Prisma format, validate, and generate               | PASS                                                                                                  |
| Pre-operator datasource-to-schema diff              | Expected exit 2; only `lineageId SET NOT NULL` and the two reviewed online indexes were present       |
| Online guard, backfill, indexes, validate, contract | PASS; phase `CONTRACTED`, zero nulls/duplicates, final indexes valid/ready, transition trigger absent |
| Post-contract datasource-to-schema diff             | PASS; exit 0 and empty migration                                                                      |
| Harness against uncontracted database               | PASS fail-closed proof; exit 1                                                                        |
| Harness after adding one synthetic extra table      | PASS fail-closed proof; exit 1                                                                        |
| Harness after removing the disposable sentinel      | PASS                                                                                                  |
| Strict standalone TypeScript for the harness        | PASS                                                                                                  |
| Focused ESLint                                      | PASS; no errors                                                                                       |
| `git diff --check`                                  | PASS                                                                                                  |
| TruffleHog verified-only on all changed files       | PASS; zero findings                                                                                   |
| TruffleHog offline on all changed files             | PASS; zero findings                                                                                   |

The final positive harness emitted profile
`template-twin-contracted-schema-drift-v1`, schema hash
`892a673e65b4e6edac7cd772c773dcbc7069e33108c00d55aa8677a88044558c`,
`columnNotNull=true`, both online indexes valid, and
`transitionTriggerPresent=false`.

## Contract decision

Existing audited PostgreSQL constraint and index identities are represented by
Prisma `map` attributes rather than renamed in production. The durable
`template_twin_lineage_migration_progress` table is represented as an ignored
Prisma model: schema tools retain it, while Prisma Client cannot mutate it as a
generated model. The two rollback-control `updatedAt` database defaults are
represented accurately. No historical migration checksum or physical database
object was rewritten.
