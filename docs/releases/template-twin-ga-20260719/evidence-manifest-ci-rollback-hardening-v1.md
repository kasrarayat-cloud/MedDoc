# Template Twin CI, rollback, and MFA runtime hardening evidence manifest v1

Recorded: 2026-07-21

## Release verdict

**NOT RELEASED.** Production availability is **0%**. This work performed no
production migration, deployment, flag change, provider call, credential
rotation, or PHI-bearing test. It does not authorize production use.

## Immutable implementation lineage

- Branch: `fix/template-twin-provider-ownership-b017-v1`
- Accepted pre-CI parent:
  `fc08599533f75dbd7bdf878a9d23595ab83d4be0`
- Historical CI/rollback implementation:
  `6f8f3e108fe57bb5f8686ec7a4079624ea629a79`
- Historical implementation tree:
  `4b1602311a0a75198aa1f27f70d474410c1b8971`
- Additive P1 closure:
  `a7488ba8cc755beeedef56eb27f828d5d86e037b`
- Additive P1 closure tree:
  `2104af1c07283540f6c459fdccad6e7ed4ee62db`
- Additive P1 closure parent:
  `6f8f3e108fe57bb5f8686ec7a4079624ea629a79`
- Main target last read-only verified at:
  `1be101912f01293de3b8fddae722c823ecc86f29`
- Draft PR #371 published head at manifest authoring:
  `fc08599533f75dbd7bdf878a9d23595ab83d4be0`

The implementation is an additive descendant of the accepted parent. No
accepted or rejected commit was amended or rewritten. PRs #362 through #370
were not modified. The records-only descendant cannot embed its own commit SHA;
its exact identity, bundle, and review verdict must therefore be bound in an
external mode-0600 receipt after commit.

## Triggering CI failures and log incident

Published accepted parent `fc08599` exposed three release-gate defects:

1. E2E run `29815703035`, job `88586438447`, could not parse production
   Compose because `QUILLMD_POSTGRES_IMAGE` was absent.
2. Human/Office run `29815703432`, job `88586439995`, could not statically
   parse the colon-bearing short-form MFA keyring mount.
3. A11y job `88586438421` and CI test job `88586439114` returned the safe code
   `SYNTHETIC_CI_DATABASE_RELEASE_CHILD_DATABASE_RELEASE_MIGRATION_PRISMA_FAILED`.

The E2E preamble displayed randomly generated, job-only disposable synthetic
credentials because those values had not first been registered with the GitHub
Actions masking channel. The build failed before services started. Exact raw
E2E logs were deleted through the Actions API; run/check metadata was retained.
No value is reproduced here. The sanitized incident receipt has SHA-256
`bbe39384e28108d692a4b19774453dc4044e4499cde3a3f1db3d762cf3ecac6e`.

## Historical `6f8f3e1` closure and rejection

Exact `6f8f3e1` added synchronous generated-secret masking, immutable checkout
and local image binding, long-form no-create keyring mounts, strict Compose map
normalization, and a real base-plus-six-service rollback overlay proof. Its
technical census passed **428 files / 5,783 tests**, focused **8 files / 187
tests**, full application TypeScript, static principal and rollback censuses,
offline and verified-only staged-patch scans with zero findings, and a closed
**97/97** synthetic migration replay with zero labeled residue.

Those passes did not make the head acceptable:

- Auth/security review: **REJECT**, P1. The application image runs uid 1001,
  primary gid 65533, but the two keyring consumers lacked supplemental gid 1001
  and could not read the root:1001/0440 keyring.
- Integration/test-census review: **REJECT**, two P1 findings. It reproduced the
  keyring defect and package TypeScript `TS2345`; app-only TypeScript had not
  covered the synthetic helper.
- Rollback/infrastructure review: **ACCEPT in its scoped rollback area**. This
  did not override either P1 or accept the exact head.

## Additive `a7488ba` closure

- Production physician runtime receives exactly supplemental gids 101 and
  1001; the admin application receives exactly gid 1001. Admin control, legacy
  app, workers, and dispatchers receive no gid 1001.
- Synthetic QA physician runtime mirrors the exact 101/1001 group contract.
- Static and resolved principal censuses reject missing, wrong, extra, or
  non-consumer keyring groups.
- E2E invokes the immediately inspected `sha256:` application image with no
  network, a read-only root filesystem, all capabilities dropped, and
  `no-new-privileges`. Before reading the mounted keyring, it requires uid 1001,
  primary gid 65533, exact group set `[101, 1001, 65533]`, and source metadata
  root:1001/0440. It parses structure without printing key bytes.
- `proveExactPrincipals` now accepts the closed `SyntheticDatabaseSecrets`
  type. A dedicated no-emit package TypeScript configuration covers the helper
  and both contracts.
- Both helper-using workflows run package typechecking after Prisma generation
  and before synthetic database provisioning.

## Verification census at `a7488ba`

| Gate                                                      | Result  | Evidence                                                           |
| --------------------------------------------------------- | ------- | ------------------------------------------------------------------ |
| Full TranscribeMD unit suite                              | PASS    | 428 files, 5,788 tests                                             |
| Focused changed-test census                               | PASS    | 8 files, 192 tests                                                 |
| Full application TypeScript                               | PASS    | `tsc --noEmit` exited 0                                            |
| Synthetic helper package TypeScript                       | PASS    | Dedicated no-emit project exited 0                                 |
| Production static principal census                        | PASS    | 7 exact services                                                   |
| QA static principal census                                | PASS    | 2 exact services                                                   |
| Production static rollback census                         | PASS    | 6 long-lived services; migrator excluded                           |
| Workflow syntax                                           | PASS    | 60 shell blocks and 3 embedded Node blocks                         |
| Prettier, JavaScript syntax, and diff whitespace          | PASS    | Exact 13-file implementation delta                                 |
| Exact staged-patch offline secret scan                    | PASS    | Zero findings; scanner errors fail the gate                        |
| Exact staged-patch verified-only secret scan              | PASS    | Zero verified findings; scanner errors fail the gate               |
| Independent precommit auth/security code review           | ACCEPT  | No P0/P1/P2; staged patch SHA-256 recorded below                   |
| Independent precommit rollback/infrastructure code review | ACCEPT  | No P0/P1/P2/P3 in scope                                            |
| Independent precommit integration/test-census code review | ACCEPT  | No P0/P1/P2                                                        |
| Fresh detached records-bearing exact-head review          | PENDING | Required before publication                                        |
| Fresh PR CI                                               | FAIL    | Published PR still points at failing `fc08599` until reviewed push |

The exact staged 13-file patch accepted by the precommit reviewers has SHA-256
`fcd6072b1fb1cbeffe64716fcb4df2599e0927b2ae8ff82e47ff932b4e1ca813`.
Precommit acceptance does not substitute for the fresh detached exact-head
review required after the records-only descendant exists.

## `a7488ba` artifact SHA-256

| Artifact                                                                              | SHA-256                                                            |
| ------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `.github/workflows/a11y.yml`                                                          | `b55e0ef7fde84ab508587adb34922addfdd425578d75fb552c71c62cb112d067` |
| `.github/workflows/e2e.yml`                                                           | `4a87b92e83d42806e8fc8b82ac85c19608d17e948551945d6ae79b799b1af4a4` |
| `.github/workflows/test.yml`                                                          | `43e21247c76cd8a6e78987d055c9a2b4632c4d2d4672c0f2745ee845eb5cfd52` |
| `apps/transcribe-md/src/lib/__tests__/database-role-graph-migration-contract.test.ts` | `78259a2dd5462b58aac6b64e795afa6eb82dab369015e6fdd675aae3d0957cab` |
| `apps/transcribe-md/src/lib/__tests__/mfa-secret-infrastructure-contract.test.ts`     | `a669badf8c9065ee474adeb974e47e2926078cf11dbe90f059f95dfd8f536c98` |
| `apps/transcribe-md/src/lib/database-principal-runtime-census.test.ts`                | `6b7fcdb45d4ee1ad845ad63f06a4989dd92f7b61478a4461cf51d16a24e6b942` |
| `docker-compose.qa.yml`                                                               | `27c88c4918851b19bc20eec21ae658a3f240fe38986f35c367687df7b27f5f14` |
| `docker-compose.yml`                                                                  | `eeff4c31d270a789efdc742770395da3d66734d5f00e32542fb8fbe02ffc562f` |
| `packages/db/package.json`                                                            | `46dfac23dfcad7be11c961e382202d1ee4fa8b5a3953e9f784ec8af605bdd56f` |
| `packages/db/scripts/synthetic-ci-database-release.ts`                                | `3562c6a182d2b39ea8ddbd51decd38e68efe96127e92b82a5343f3ad42c72861` |
| `packages/db/src/synthetic-ci-database-release-contract.test.ts`                      | `fe81037f98ba17b57ca5bf48aeaef01dbb0c869f1a425b57e7cb9144ca25619d` |
| `packages/db/tsconfig.synthetic-ci-release.json`                                      | `9e02a79fcd9579694d30e7b9afab8d52d0738ba38957b317c40f7141fca7b032` |
| `scripts/database-principal-runtime-census.mjs`                                       | `3c4ac1557455246c9522d715f7784610de0386d54ccedb99d49fa917b649a61b` |

## Explicit debt and remaining gates

This series does not claim to pin inherited mutable third-party references,
including Redis/MinIO image tags and moving GitHub Action major tags. They are
P3 dependency-provenance debt requiring a separate reviewed change or explicit
final-RC acceptance.

Fresh exact-head review and PR CI must pass after records freeze and
publication. A recurrence of the shared migration failure requires masked,
value-free diagnosis and another additive fix. This manifest does not satisfy
desktop Word, live-provider clinical quality, Privacy/Legal, Clinical Safety,
Operations, credential rotation, production backup/restore, immutable signed
production images, a real six-container rollback rehearsal, deployment
authority, or any rollout checkpoint.
