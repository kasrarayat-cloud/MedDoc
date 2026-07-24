# Independent exact-head source-admission review

Date: 2026-07-19 UTC  
Role: independent exact-head security and release-integration reviewer  
Disposition: **REJECT**

## Exact review identity

- Branch claim: `fix/native-docx-openxml-schema-gate-20260719`
- Reviewed commit: `2869ba7b2ab6178adfb180561c68a61bf2037df3`
- Reviewed tree: `9bcfdd960b0ead72de639f182a57522de2c6bbb6`
- Additive parent: `446ea35a7135ac7031ede7a68a514bd93d56f5fe`
- Release base: `b5b26e0bf5b59293a8f9387550444bb59d2673e8`
- Fresh detached workspace: `/home/claude/reviews/source-admission-2869ba7-20260719/detached`
- Evidence directory: `/home/claude/release-evidence/meddoc-template-twin-ga-20260719/security/source-admission-review-2869ba7`

The detached workspace resolved to the commit and tree above and was clean after review. No implementation fixes, commits, merges, pushes, deployment, production data access, real PHI, or provider egress were performed by this review.

## Verdict and finding census

- P0: none identified.
- P1: one open release blocker.
- P2: none identified.
- Human gate: desktop Microsoft Word evidence remains **HUMAN PENDING**.

### P1 — checked-in full Template Twin census is red

The complete Template Twin test census, run from the correct application working directory against the exact reviewed head, ended with:

- Test files: 122 passed, 1 failed, 123 total.
- Tests: 1,562 passed, 1 failed, 1,563 total.
- Failing contract: `apps/transcribe-md/src/lib/template-twin/human-release-gate/__tests__/contracts-and-hygiene.test.ts:162`.

The checked-in human-release-gate contract requires the trusted validator program to contain the exact expression `SHA256.HashData(documentBytes)`. At this head, the CLI path delegates hashing through `Sha256(documentBytes)`, so the exact contract assertion fails. A narrow independent reproduction produced one failure with nine other tests skipped.

The helper may be semantically equivalent, but an independent reviewer cannot waive or reinterpret a checked-in release contract. Therefore exact head `2869ba7b2ab6178adfb180561c68a61bf2037df3` is not releasable and must not be accepted. Resolution requires an additive commit, a green full census, and a new fresh detached exact-head review.

Primary evidence:

- `full-template-twin-tests.log` — SHA-256 `8b239a4fda8891d5a269129caf1d4cb3f32b4ecc18e3271c639c09e36c3904fc`
- `reproduced-p1-release-gate-test.log` — SHA-256 `0516d0037b0f62e201a02be0dbfe2c3aabaa50e4f07c5cc260b2b3fc8fe31d1a`

## Completed independent gates

### Focused application and schema verification

- Focused Template Twin/source-admission suite: 12 files and 393/393 tests passed. It covered admission-receipt v2 migration behavior, Open XML migration/runtime/parser behavior, quarantine admission, source admission, malware contracts, certification lifecycle, draft creation, completed-document candidates, integration, and native compatibility.
- Strict TypeScript check passed.
- Prisma validate and generate passed; formatting a copied schema produced no source change.
- Scoped ESLint passed with zero errors and two non-blocking unused-variable warnings in tests (`_source` and `sha256`).

Evidence:

- `focused-tests.log` — `599a26b5d9b4ec5f10105a53742c073db967882e9213515b3d231c9b67a9bdfc`
- `typescript.log` — `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (successful silent command)
- `prisma-format.log` — `a9b107bd777e58b8ca09e213199d6b1a76ed49f6825a5b93b9d563bd908e80b6`
- `prisma-validate.log` — `23bdb9a29ae79176c449cb9f8c3af5738ab1018a9954808a8a872e60e320e699`
- `prisma-generate.log` — `7ebb919baeed0bd97c3eb929b305c7928885b4cd54f8210964aa48f2dda03139`
- `scoped-eslint.log` — `39a427fb632e45f3ce3c908fa4f2045697f074b8598b75bae6de1c145671c152`

### PostgreSQL migrations, ownership, and concurrency

- A disposable pgvector PostgreSQL 16 database with the exact cluster-role prerequisites accepted all 92 migrations.
- A second deploy was idempotent, migration status was current, and an independent test database also migrated successfully.
- The online lineage sequence `GUARD -> BACKFILL -> INDEX -> VALIDATE -> CONTRACT` passed.
- Real PostgreSQL completed-candidate concurrency testing passed: expected serialization aborts occurred, revocation won, the candidate remained pending, one receipt was durably consumed, and one terminal audit record remained.
- The quarantine/certification PostgreSQL author contract passed valid ownership and certification paths while rejecting cross-physician same-practice access, null ownership, suspended/deactivated/soft-deleted owners, product revocation, wrong certifier, invalid link directions, and direct active admission; ordinary templates remained unchanged.
- Independent SQL checks confirmed exact hardened `search_path=pg_catalog, public, pg_temp` on 13 source-admission/OpenXML/malware routines, rejected owner mutation, rejected direct `ADMITTED` transitions, rejected direct active Twin inserts, and allowed an ordinary active structured template.

Evidence:

- `fresh-migrate-deploy.log` — `f86ce78dbe31abc727cdc9aef0f9a6167e7afaa0e7adf6f4f0910d326dcf1971`
- `idempotent-migrate-deploy.log` — `71b83a8c29be13104139898f3eee5dbbaf9f93ba46f336b8d3c3a0d10523d85e`
- `migrate-status.log` — `956ebb724ee512b8a132e9fb90d146706a13acdc1bbfa840cab73f24340b0e5f`
- `fresh-test-db-migrate.log` — `8110ce47933eea045f838bdda9d9110158026dd9ff7047518f0fa62769e64cc5`
- `lineage-online.log` — `9dcd8e2c9f079b3644a7c84145a6c729419eb24d638bd81b920a9455e8cba46c`
- `completed-candidate-concurrency-pg.log` — `cc69312324384f80c84909b3b656e0863b5456d2a10d2c37125d2fe2157ac27f`
- `quarantine-certification-pg-contract.log` — `7a5e8f417db5ccd29f8e494926ac461c141fa3cb878bfb808cd0e7fe5d30ab68`
- `independent-owner-transition.log` — `58c128a308ad6fe9bf1760270846ef52fb2a8bb34dfefc91145b3cc67c0e2ab8`

### Data-bearing upgrade and interruption/resume

- A disposable database was migrated through the 91-migration parent, seeded only with synthetic draft/quarantine/legacy-link data, and upgraded to migration 92.
- Upgrade verification preserved the quarantine row, left new Open XML fields null for legacy data, preserved the creator, left the legacy source link null, and produced no active Twin rows.
- In a separate rehearsal, an access-exclusive lock caused the migration to time out. Transaction rollback left the three new columns absent. The failed migration was resolved and deployment resumed successfully, ending with all three columns present.

Evidence:

- `upgrade-parent-91-migrate.log` — `2445031a9ce8c7966fed0544ffc022d16c66157c7bc4c196d5f5cb570b119d38`
- `upgrade-91-seed.log` — `e4ec99981f872a7c89a25ce6232636169866ecccc0839aadcc6d47ad3fdbbc26`
- `upgrade-91-to-92-migrate.log` — `6ae7785d6594b1a29795293814ad9bf28819151d9f4764991dc0b7398588aae7`
- `upgrade-91-to-92-verification.log` — `ba303165adc20cb156dc85fe9adb60012cad125ee9d5d5945e4a7e44559eae93`
- `interruption-lock-timeout.log` — `22d935533f84d780ef09456941814bf3dd58002e6a8735a4b55bc5f764c83ca0`
- `interruption-rollback-summary.txt` — `e192d0464892f5fbabe23f129055adc2bba9e828297021cc07fede492e7c9962`
- `interruption-resolve.log` — `73d40ccd9b5c6b3a409e170255cd6da7e472093b0d6cfbb801163cf331d65d07`
- `interruption-resume-deploy.log` — `133bd574c11cee1f94ec9edd59bf03f8ddb8049253aceb388c0810f5cc02db20`

### Negative DOCX admission cases

Independent synthetic DOCX cases passed. The intake rejected active content, external relationships, malformed XML, hidden deletion content, and unsupported `customXml` auxiliary content before any provider callback. No provider call or PHI was used.

- `independent-negative-docx.log` — `b314c0447664c537a9f20f11a00aa7c0411ac5c4fdb1911d13dc57becfc48e8a`

### Open XML image, runtime confinement, and synthetic corpus

- Production and QA Compose configuration validation passed.
- The extracted validator service configuration had `network_mode: none`, a read-only root filesystem, all capabilities dropped, `no-new-privileges`, a 128 PID limit, and a Unix-domain socket volume.
- Immutable local review image ID: `sha256:bbddc5818d3c86542729da3113e6220eb6e71aa028b2f5474388bff09702e260`.
- The image ran as `65532:101`, carried the exact revision label, started with network disabled/read-only/cap-drop/no-new-privileges controls, and became healthy.
- The synthetic Office corpus produced seven cases and 12 DOCX packages: five rendered and two were blocked as expected. Runtime validation accepted all 12 for Office 2013 and all 12 for Microsoft 365 and rejected the malformed package.

Evidence:

- `compose-production-config.log` — `6f89c8ae49d75d777ee01b74e2a6fbd91356d1a24ea4ed4b4095a466fc09c153`
- `compose-qa-config.log` — `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (successful silent command)
- `validator-image-build.log` — `aeabc31305b1e4d1ec4a8aa266f73fdaf853b7ea14eeb30b22f738aa9884cb23`
- `validator-image-config.json` — `44a239c5e59efddbcfc68e7e0ac00a6fb12ee791d7addb81e59288ad2516f797`
- `validator-image-id.txt` — `c7a647e0801fc1b3ea6be45646bc59e310f21f8f1b48ec79a0a979084638455b`
- `validator-runtime-security.json` — `df8ae113819341e727d667b47614c07e02b6187f2f947db111bbf827aa60f3b8`
- `office-corpus-generation.log` — `c786e0a564d72bfac81e432327c346e78d259485c555d41253f5660124afda3f`
- `openxml-runtime-corpus.log` — `358bbb5b73df5b19825319ad57eb3c0bba3f73ca50a3a5446100702b715e1761`

Reviewed input hashes:

- Package lock: `c6a435232ea83717a66a93de5979efb265d0afc1ae98da94138d04c281006114`
- Validator Dockerfile: `4e39b2e9386b4cd02e2a10bcc14170001ffc823acf66c8a9403ad99641de2f67`
- Migration 166: `5d5967ed7b57c2cdce3acd2eef78ecee9a2bb727f286f830165c2c5983918d58`
- Migration 170: `9c3199ce6b25a2a06c93cb3105a6643ca6f2cf377b737318880cbad524c88e32`

### Bounded secret scanning

- Verified-only TruffleHog filesystem scanning of the 40 changed files completed with zero findings.
- An offline bounded credential-pattern scan completed with zero matched files.

Evidence:

- `trufflehog-verified-filesystem-summary.txt` — `131047e4e7578d8c993ba3da5b88252905d808e5bffb493247ace7ae28afbdca`
- `offline-secret-pattern-summary.txt` — `12900fcb8c616a4e285e0e400b7a9482326ce6537ae2`

## Gates not passed or not independently run

- **Full Template Twin census: FAIL** because of the P1 above.
- **Desktop Microsoft Word open/save/reopen/PDF evidence: HUMAN PENDING.** Open XML and synthetic runtime validation do not substitute for this gate.
- A live ClamAV daemon/service was not independently started in this review. Malware receipt binding and admission behavior were exercised through focused tests, PostgreSQL contracts, and static/runtime review only.
- No production deployment, migration, feature enablement, canary, rollout, rollback, merge, or release authorization was attempted. This review provides no production authorization.
- No real provider evaluation was run and no provider egress occurred.

## Invalid or superseded diagnostic invocations

These artifacts are retained for an honest audit trail but do not support a pass claim:

- `full-template-twin-tests-wrong-cwd-expected-fail.log`: initial wrong-working-directory run generated 37 `ENOENT` failures; it was superseded by the correct-working-directory full census, which exposed the real P1.
- `base-b5-eslint-comparison.log`: invalid path invocation exited 127; no base/head lint-census claim is made. The correctly scoped exact-head ESLint run passed.
- `scoped-prettier.log`: configuration/invocation mismatch; Prettier is not claimed as a passed repository gate.
- `trufflehog-verified.raw` and `trufflehog-verified-summary.txt`: local git-mode invocation was invalid and banner-only; the verified-only changed-files filesystem scan superseded it.
- The ordinary-PostgreSQL/no-vector and incomplete/overprovisioned-role migration attempts document expected prerequisite failures. The correctly provisioned disposable pgvector/role configuration subsequently passed.

## Protected-worktree boundary incident

During evidence-script creation, a raw patch command briefly created the untracked file `/opt/meddoc-pro/independent-negative-docx.ts` in the protected pre-existing worktree. The exact file was immediately removed. No tracked file was modified and no surviving artifact remained there.

The program owner independently performed a hash-only protected-status verification after the incident:

- Protected status fingerprint: `4279d7ecbb04309cf7db358ea6a9959785d79fdc7a2dc98132ee0982a6d8115d`
- Updated durable program-record SHA-256: `d91b77f0e3d7c577c3de391967bc8bbc47fc8bcefdf6d52d8e0b9f948da56866`

This incident is disclosed explicitly and is not represented as perfect non-contact with `/opt/meddoc-pro`; the verified result is that its pre-existing tracked changes were preserved.

## Cleanup and evidence integrity

The disposable synthetic PostgreSQL and Open XML validator containers were stopped and removed. No production service or data was touched. Evidence files were retained in the directory listed above.

- `cleanup-summary.txt` — `93dee677de84e22d20400388e99280be39cb658e22b5f602be165eaf0e09ac18`
- A complete filename-sorted evidence manifest is stored as `SHA256SUMS`. The manifest excludes itself and hashes this report plus every other retained top-level evidence artifact.

## Required next action

Do not release or merge this exact head. Create an additive remediation commit that restores or intentionally updates the checked-in hashing contract with appropriate tests, rerun the complete census, and obtain a new independent exact-head review in a fresh detached workspace. Desktop Microsoft Word evidence remains a separate human prerequisite even after the technical P1 is corrected.
