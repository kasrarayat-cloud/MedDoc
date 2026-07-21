# Authentication, authorization, MFA, and six-runtime evidence manifest v1

Generated: 2026-07-20T16:27:15Z

## Verdict

**HISTORICAL SCOPED TECHNICAL VERIFICATION PASS; INDEPENDENT EXACT-HEAD REVIEW
REJECT; PRODUCTION RELEASE FAIL.** This immutable historical receipt records
synthetic and static evidence for `e7b3864`. Its independent review later found
one P1 incomplete production runtime-identity census. It does not authorize
production credentials, migration, provider delivery, deployment, canary, PHI,
or physician rollout.

## Exact identity

| Record                                                | Identity                                                           |
| ----------------------------------------------------- | ------------------------------------------------------------------ |
| Branch                                                | `fix/template-twin-provider-ownership-b017-v1`                     |
| Provider-ownership parent                             | `db1cab904ac5c8d6c7f25878f59d71e1b094a223`                         |
| Auth/authz implementation                             | `9a1ded49055d1aef153864b28267c81ab1b0506d`                         |
| Technical head reviewed and rejected                  | `e7b3864dc6d61d7d36755f59f87909bb7394740d`                         |
| Git tree                                              | `4a9f0bf06dbfc86ef94e03c515b910bd4ac47379`                         |
| Binary diff SHA-256, provider parent → technical head | `e8060e1a7303733f135dd1821534f8d4bca64f81b4599138508305d90e286de5` |
| Exact-head recursive Git tree-listing SHA-256         | `1cd5b4cc121c704c72f16ae25fb143dd7b96506d912a2305c3f1e27d42928ec4` |
| Ordered 96-migration name-manifest SHA-256            | `3f3247ced73ca58e7aff4ad214d0ba280990bf9717f23d26a2fbc303f29c6b40` |

## Technical verification

| Gate                                   | Result | Evidence                                                                                                                                                              |
| -------------------------------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Frozen auth/authz test manifest        | PASS   | 116/116 files; 1,362/1,362 tests                                                                                                                                      |
| Full TranscribeMD TypeScript           | PASS   | Exact technical head                                                                                                                                                  |
| Targeted ESLint                        | PASS   | 163 application files and 17 package/script files                                                                                                                     |
| Prisma 7.8.0                           | PASS   | Format, validate, and generate                                                                                                                                        |
| Diff whitespace                        | PASS   | Exact committed diff                                                                                                                                                  |
| Provider ownership                     | PASS   | Released L1–L7/custom-extraction paths, delivery/scoring fences, durable claims, and unknown-outcome handling covered by focused synthetic PostgreSQL proofs          |
| Authentication authority               | PASS   | Current database-backed user/session/tenant/object authority, token linearization, security-state invalidation, audit, and fail-closed error contracts                |
| Authentication-email database proof    | PASS   | Historical fresh synthetic database, 96 migrations, transactional unique-conflict rollback true, provider calls 0                                                     |
| MFA backfill/restore                   | PASS   | Historical fresh source and restored synthetic databases each 96/96 migrations; strict envelope and owner binding, audit/session/email side effects, and clean census |
| Six-runtime rollback guard             | PASS   | Scoped static Compose census and focused fake-runtime success/failure tests cover three app-image and three worker-image services; migrator excluded                  |
| Independent detached exact-head review | FAIL   | **REJECT**; one P1 incomplete production runtime-identity census. Additive remediation requires a new exact-head review                                               |
| Real six-container rollback rehearsal  | FAIL   | Accepted immutable images, runtime credentials/infrastructure, queue drain, swap, health, and roll-forward evidence unavailable                                       |

## MFA rehearsal receipt

- External synthetic-only report SHA-256:
  `7683451a1a36330bc8e74e6c484657e2eb577f63189ea9f16e6754a99b9df0fe`.
- Reviewed one-candidate dry-run manifest:
  `47dacdbfb63487da2b8fb1aed142f0a9c0c7dfee876f10416dcc5a41303bdf4b`.
- Empty post-apply candidate manifest:
  `4b54fec875b7a30c809c0dcc0fd0675e67457b7e26e635a188d1331a91a93f4e`.
- Removed synthetic custom-format dump SHA-256:
  `39ddf6e0a00745f42760d366093b1757dd91887b826feaef52a70208a0a0ad00`.
- Temporary dump and keyring were removed. The disposable synthetic databases
  remain for audit only. No key, secret, ciphertext, token, email, user ID,
  provider ID, credential, or database URL is included here.

## Selected exact-head artifact hashes

| Artifact                                                    | SHA-256                                                            |
| ----------------------------------------------------------- | ------------------------------------------------------------------ |
| `scripts/template-twin-runtime-swap.sh` (Git mode `100755`) | `3a9231541ad199a727723359924612e0bd93461626e8acee48e577107d97614d` |
| `scripts/template-twin-runtime-census.mjs`                  | `a0432fc593b269a43d645e1af5ff3b3ea8b5523a626e30b813e1b23d8d89f56c` |
| `apps/transcribe-md/scripts/mfa-secret-backfill.ts`         | `5ca7b4a19479452f2c6d32c89b413e704251193c782818ee31bae40cb2fd105d` |
| `apps/transcribe-md/src/lib/mfa-secret-envelope.ts`         | `2abb04199c33ae9b5229ab39d3194612e44d8d961c8e37ed5032f463dc2a52bd` |
| Authentication-email v6 migration                           | `b3c7175f742df8a9931463ed34bdce570cf8bbc153f29136cca93679003ff128` |
| MFA credential-lifecycle v8 migration                       | `2c19bddc370ecfeb56e0912561409a9dc12f6d36e6df14c3a5a323ed8704f49f` |

## Open authorization gates

Production remains blocked on fresh independent exact-head ACCEPT, final RC/CI,
the 97-migration candidate/final-head schema-drift proof, accepted immutable images and a real
six-runtime rollback rehearsal, complete backup/PITR/object/queue recovery,
credential-rotation closure, production MFA key/KMS provisioning and approved
backfill, authentication-email provider/credential/monitoring approval, desktop
Word evidence, and signed Clinical Safety, Privacy/Legal, Operations, and
authorized physician decisions.

Earlier Phase 0, schema-v1, control-plane-v1–v4, rollback-fence, completed-
candidate, and clinical manifests remain historical evidence. None is rewritten
or represented as current exact-head acceptance by this manifest.
