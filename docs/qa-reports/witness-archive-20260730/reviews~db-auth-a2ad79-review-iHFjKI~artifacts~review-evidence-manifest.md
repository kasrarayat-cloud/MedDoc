# Template Twin v6 search-path independent exact-head review

## Identity

- Verdict: REJECT
- P0: 0
- P1: 1
- P2: 0
- Exact head: `a2ad79f40058ede17f40782efa7981fc4c51bf9b`
- Exact parent: `b5b26e0bf5b59293a8f9387550444bb59d2673e8`
- Head tree: `4ae9016502f2b542050d445801fcefeb0c00139c`
- Parent tree: `521f7864a104c6cc5d2bb010fc42e52e9e7be698`
- Exact binary patch SHA-256: `60d9ed55bad949c541631e690ac5851225a6960ca2c60e9df83098f8719eac00`
- Migration SHA-256: `b3fc23e56f4cfa5639628c2cd98c39e16ee62e0cce790cfed16e741837edc433`
- Changed test SHA-256: `5603ed246e2b0917550122fe0186510890568cf5fbfed41eb5f4c5fd5f2e6feb`
- Lockfile SHA-256: `8506c0612be06c74f498587677958bc5d1137749c4a11b725fc8925b323d6b97`
- 91-name migration manifest SHA-256: `74ff9b37db5ca975f848cd53c1aa715a00c2254f72387e48bce70ab50d4500f9`
- 91-content migration manifest SHA-256: `7437e543c341e751c5823287ed775e3e2d7f7912d5a55cf8e6d1bbf6cb224129`

## PostgreSQL 16 evidence

- Disposable image digest: `pgvector/pgvector@sha256:7d400e340efb42f4d8c9c12c6427adb253f726881a9985d2a471bf0eed824dff`
- Server: PostgreSQL 16.13.
- Parent condition: 90 migrations, exactly four unsafe v5 zero-argument PL/pgSQL trigger functions, global false at generation 1, zero enabled practices.
- Parent catalog contract SHA-256: `ed8010238edbbaf8f3dac6221841d5626b652bbf8f77cc634c59b755b7e521e5`
- Before/after invariant owner/ACL/body/signature/OID/trigger-shape SHA-256: `8285e398ec67474936464c93a0b3fa8a42a1050310dc9306a44b9ef4ac2f2dc9` (identical).
- Post-repair complete Template Twin catalog SHA-256: `62c7c46053c520e8e3216f6e7d8c7f62f649c8015cfd8b95c478f963bcf3cac7`
- Post-repair unsafe Template Twin function count: 0.
- Identity-drift post-failure catalog SHA-256: `6dd2b6d716be156a673d5abaf3cd9530a19f70ce9f4ca975037d8980e8a86e6e`; earlier changes rolled back.
- Extra-surface post-failure catalog SHA-256: `916f961ec56ab7d6097d248aea76b83dca4cd4ad15b1759e605eea5058159716`; all four changes rolled back.
- Fresh 91 catalog SHA-256: `417b0b0af80ae18753ec55a398c6adba1db0c9fd34c309864a32c7d6696f459f`; second deploy had no pending migrations.
- 87-name subset manifest SHA-256: `c740772dc9802d37da9e86cb4577984589969c3c71b1d075269a222213161ff6`.
- 87-content subset manifest SHA-256: `d5699845470920da0901e1090d2befa6cdd8deca4af6be645273b49326f8edb2`.
- Synthetic 87 fixture SHA-256 before and after 87→91: `7e002e5e69e02cd6f006d220e24ae70fac2b5fa2c18e6fac5593f10fd0c1b99a` (identical); global false; zero enabled practices; zero unsafe functions; second deploy had no pending migrations.
- Four-trigger valid/no-op/rejection behavior result SHA-256: `8f74be840b53ac9bc33c18db975c9be50974aa6d84a8f7ad07e93a2140aecfca`.
- Fill/physician lineage rejection result SHA-256: `42cdc1806871a49b52e41bdad6bf0727dbfbcc6a437b92cb5d5ba52aa7ce6324`.
- Full release-control PostgreSQL v3 result SHA-256: `f5a93fe927e2c313dffae80cde371ad3233a6214eff56488eaadf28af3a5cad4`; 63 audit events; final global false.

## Static regression finding

- Corpus: `static-regression-mutation-corpus.mjs`
- Corpus SHA-256: `422c4046e0b04feda50ec83275d0a8188bf5fe4a73996ca261a6f2fa6a68fdef`
- Exact command: `node /home/claude/reviews/db-auth-a2ad79-review-iHFjKI/artifacts/static-regression-mutation-corpus.mjs`
- Output SHA-256: `cf200a74019d556a6f5c077dea02163b9539e7a48720b63655d185cf964c513d`
- Census: 8 fixtures, 2 controls pass, 6 valid-form/order cases missed.
- P1: the test is not a fail-closed parser for later function additions or reconfiguration and skips a newly committed migration that sorts before v6.

## Other gates

- Focused tests: 2 files, 26 tests, PASS; census statement SHA-256 `3d8f1d5dec40c56168827000867043fd07466631787927fa3b436251b39226e2`.
- Full Template Twin library suite: 83 files, 888 tests, PASS; census statement SHA-256 `5f4e230bfe4ebdac37f7c363206b8af513b50b4ffa247826f38beb7638c98cd9`.
- Strict TranscribeMD TypeScript: PASS.
- Focused changed-test ESLint: PASS.
- `git diff --check`: PASS.
- Prisma generate and validate: PASS.
- Contracted lineage operator, repeated contract, and schema drift: PASS; result SHA-256 `f8f6ce1f47ac8e63e4b6668275b8eb187f718b0c15dc2064f3b4d24dafd6b842`.
- Placeholder physical-name schema drift: PASS; result SHA-256 `9310b07a51aceff15cdd2e9f6974b322cd65bacb575a7e17e1af7851a0247198`.
- Changed-file verified and offline secret scans: 0 findings.
- Production dependency audit: 0 high, 0 critical, 13 moderate, 1 low across 680 production dependencies; canonical summary SHA-256 `dee37d8156dc334d325b103dac32f7439cd3220187ea0f98bc398fe287002942`.
- Production build: not required; the exact diff changes only SQL and a test, and strict TypeScript plus relevant runtime/database suites passed.
- Review worktree and parent worktree remained clean and detached.
- `/opt/meddoc-pro` was not modified; its pre-existing status SHA-256 at review end was `4d87033c777fd290f87aba0e8c71f375ca243f71532d46d4b3a9a94c92d2f1a4`.
