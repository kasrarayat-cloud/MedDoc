# Independent exact-head review — Template Twin source admission

## Verdict

**ACCEPT** the reviewed source-admission component stack at exact head
`ecf3c2362f37d831498117b6ccdc6950c641a8f8`.

This is a technical exact-head acceptance, not a claim that the broader GA
release is complete. Desktop Microsoft Word evidence remains **HUMAN PENDING**
and must not be inferred from the Open XML SDK or synthetic corpus results.

Product findings:

- P0: 0
- P1: 0
- P2: 0

There are two test-only ESLint warnings and one Prettier-only QA Compose wrap
warning. They are recorded below as non-product tooling/fixture debt; they do
not change authentication, authorization, runtime behavior, admission, or
rollback safety.

## Frozen identity and independence

- Review worktree:
  `/home/claude/release-programs/reviews/source-admission-ecf3c23-20260719`
- HEAD: `ecf3c2362f37d831498117b6ccdc6950c641a8f8`
- Tree: `0efa0a42c751f5d85be81071b920d81c8228c4f7`
- Parent: `2869ba7b2ab6178adfb180561c68a61bf2037df3`
- Component base: `d6f8dd2e7d93b98ce0dea07602bbc88d82f7aa10`
- Component commits:
  - `446ea35a7135ac7031ede7a68a514bd93d56f5fe`
  - `2869ba7b2ab6178adfb180561c68a61bf2037df3`
  - `ecf3c2362f37d831498117b6ccdc6950c641a8f8`
- Detached HEAD: yes
- Tracked, untracked, ignored, and index status after cleanup: empty
- Worktree and index diff exit: 0
- Component `git diff --check` exit: 0

The review used fresh detached worktrees and author reports only as claims to
reproduce. No tracked reviewed source was edited. No provider was called, no
real document or PHI was used, and no push, merge, deployment, or production
mutation occurred. `/opt/meddoc-pro` was not read, switched, reset, cleaned,
stashed, overwritten, or modified by this review.

Evidence: `frozen-detached-cleanliness.log`, `exact-head-commit.log`,
`component-range-stat.log`, and `component-range-files.txt`.

## Prior P1 reproduction and closure

The exact parent `2869ba7b2ab6178adfb180561c68a61bf2037df3`
reproduced the prior defect: the human-release-gate contract failed 1 of 10
tests because the validator source did not contain the required direct
`SHA256.HashData(documentBytes)` expression. The exact reviewed head passed all
10 tests.

The reviewed implementation computes the reported document digest directly
from the same byte array passed to `MemoryStream` and
`WordprocessingDocument.Open`. A live isolated-runtime receipt additionally
confirmed `sourceMatch: true` against an independently computed Node SHA-256,
with zero Office 2013 or Microsoft 365 schema errors. This establishes runtime
semantic equivalence, rather than relying only on string matching.

Evidence: `prior-p1-reproduction-2869.log`,
`former-p1-contract-rerun.log`, `openxml-runtime-hash-equivalence.log`.

## Authentication, authorization, and admission review

The reviewed paths preserve fail-closed source admission:

1. Exact upload bytes enter private immutable quarantine before parsing.
2. The ClamAV v2 receipt binds the unique scan attempt, quarantine artifact,
   practice, lineage/version, intake mode, object key/version/ETag, byte hash,
   size, readiness leases, signatures, and timestamps.
3. The Open XML receipt binds a unique attempt and nonce to the same object
   identity and byte hash and requires both Office 2013 and Microsoft 365.
4. Metadata minimization, compiler, privacy/provider evaluation, mapping,
   certification, activation, fill, signing, and worker resolution cannot
   bypass current admission.
5. Source creator, note-template owner, and certifying physician must be the
   same active physician in the same practice with the required product.
6. Suspension, deactivation, soft deletion, product revocation, stale or
   replayed receipts, cross-practice/cross-physician links, legacy direct
   activation, or lineage substitution fail closed.
7. Ordinary non-Twin note templates retain their existing behavior.

The PostgreSQL contract ran inside a transaction and rolled back its synthetic
fixtures after proving these ownership and lifecycle conditions.

Evidence: `focused-component-tests-rerun.log`,
`full-template-twin-census.log`, `full-transcribe-md-census.log`, and
`quarantine-certification-pg-contract.log`.

## Untrusted DOCX and provider-egress boundary

The independent negative harness rejected active binary content, an external
relationship, malformed XML, and tracked-deleted hidden content with the
expected production error codes. A focused independent rerun of package
security, source privacy, and auxiliary-part suites passed 62 of 62 tests,
including traversal, duplicate/case-folded entries, corrupt CRCs, encryption,
symlinks, oversized/decompression-ratio archives, macro/OLE content, unsafe
fields, namespace shadowing, custom XML, unapproved media, hidden content, and
provider-not-called assertions.

Result: unsupported or ambiguous packages fail before provider egress. This
does not claim that arbitrary DOCX files are supported.

Evidence: `independent-negative-docx.log`,
`independent-negative-docx-harness.sha256`, and
`adversarial-boundary-focused.log`.

## Isolated Open XML runtime

- Exact local OCI image ID:
  `sha256:15979d94adb8c0e056af384876ad7d39e67a3cb145f136d7b2c81f1eff8beb1c`
- Revision label:
  `ecf3c2362f37d831498117b6ccdc6950c641a8f8`
- SDK/runtime base pinned by digest:
  `sha256:aabe48e2f28d3a10bed9cfb7beb8afc7ad4234578c0fdb11f03413b69941faea`
- User: `65532:101`
- Effective capabilities: zero
- `NoNewPrivs`: 1
- Network mode: `none`
- Root filesystem: read only
- All capabilities dropped; PID, memory, and CPU bounds present
- Writable locations limited to bounded tmpfs and the UDS volume
- No database, object-storage, provider, or application credential was placed
  in the validator container
- Main and QA Compose configurations both validated successfully

The fresh synthetic Office corpus produced 7 cases: 5 rendered and verified,
2 blocked as expected, 0 failed. The runtime client discovered 12 DOCX
artifacts and validated all 12 for Office 2013 and all 12 for Microsoft 365;
malformed bytes were rejected.

An initial host/client attempt failed with `EACCES` because a capability-free
root client did not belong to the validator socket's `0660` group. That was a
review-harness identity mismatch, not a service failure. The corrected client
ran as the production-equivalent `65532:101` and passed the complete corpus and
hash-equivalence checks. The failed attempt is retained in evidence for audit
transparency.

Evidence: `validator-image-build.log`, `validator-image-id.txt`,
`validator-image-config.json`, `validator-runtime-security.json`,
`validator-active-runtime-posture.log`,
`validator-compose-main-security.json`,
`validator-compose-qa-security.json`, `compose-validation-summary.log`,
`office-corpus-generation.log`, `openxml-runtime-corpus.log`,
`openxml-runtime-debug.log`, and `openxml-runtime-hash-equivalence.log`.

## PostgreSQL 16, migrations, roles, and recovery

The disposable PostgreSQL 16.13 / pgvector 0.8.2 environment passed:

- fresh installation of all 92 migrations;
- `migrate status` at head;
- a second idempotent deploy with no pending migration;
- data-bearing upgrade from the exact 91-migration parent to head;
- preservation of retained quarantine/source creator data without falsely
  blessing legacy rows as OpenXML-validated or active;
- lock contention and server-side `lock_timeout` failure;
- explicit failed-migration resolution followed by successful resume;
- ordered online lineage guard, backfill, index, validation, and contract;
- production-helper concurrency with observed transaction blocking;
- global revocation winning a preview race without receipt/audit leakage;
- exactly one terminal review winning a concurrent terminal-review race.

The standard `postgres:16-alpine` image correctly failed installation because
the required `vector` extension was absent. The pgvector image then passed the
same install; this is a dependency fail-closed check, not a migration defect.

Final posture:

- successful migrations: 92
- unresolved failed migrations: 0
- Open XML columns: 3
- component receipt constraints: 2
- component unique attempt indexes: 2
- reviewed receipt functions: 6
- reviewed search-path mismatches: 0
- reviewed `SECURITY DEFINER` functions: 0
- runtime and release-control group roles are `NOLOGIN`, non-superuser,
  non-createdb, and non-createrole; synthetic login roles are likewise
  non-superuser and unprivileged

The wider component function census found 13 invoker-rights functions, all
with exact `search_path = pg_catalog, public, pg_temp`. PostgreSQL's default
PUBLIC EXECUTE ACL is present, but these functions are invoker-rights pure
helpers/checks/triggers and do not grant table privileges or elevated
execution. It is not an authorization escalation in this stack.

Evidence: `fresh-pg16-migrate-deploy.log`,
`fresh-pg16-migrate-status.log`, `fresh-pg16-idempotent-deploy.log`,
`fresh-no-vector-expected-fail-rerun.log`,
`upgrade-parent-91-migrate.log`, `upgrade-91-to-92-migrate.log`,
`upgrade-92-data-verification.log`, `interruption-postgres-server.log`,
`interruption-resume-status.log`, `lineage-online-rerun.log`,
`completed-candidate-concurrency-pg-final.log`,
`component-function-role-posture-rerun.log`, and
`pg16-final-posture.log`.

## Test and static-analysis census

- Former P1 contract at head: 1 file, 10/10 tests passed
- Focused source-admission component: 13 files, 121/121 tests passed
- Template Twin census: 87 files, 921/921 tests passed
- Full TranscribeMD census from the correct application cwd:
  317 files, 3894/3894 tests passed
- Additional focused adversarial boundary: 3 files, 62/62 tests passed
- TypeScript `--noEmit`: passed
- Prisma format: passed
- Prisma validate: passed
- Prisma generate: passed
- Component ESLint: 0 errors, 2 warnings
- Full ESLint at head: 27 errors, 38 warnings
- Exact b5 comparison: 27 errors, 36 warnings
- New full-lint errors: 0
- Component Prettier warnings: head 7 versus exact pre-component d6 base 10

The full-lint errors are unchanged baseline failures. The two added warnings
are test-only unused-variable warnings:

- `apps/transcribe-md/src/lib/template-twin/__tests__/create-draft-orchestration.test.ts:89:23`
  — `_source`
- `apps/transcribe-md/src/lib/template-twin/__tests__/upload-certification.integration.test.ts:301:10`
  — `sha256`

The newly Prettier-warned QA file is `docker-compose.qa.yml`; the formatting
hunk begins at line 110 and only wraps the long healthcheck array at line 113.
The component as a whole reduces Prettier warnings from 10 to 7. These three
items are fixture/format tooling debt, not product P2 findings.

Evidence: `typescript.log`, `prisma-format-check.log`,
`prisma-validate.log`, `prisma-generate.log`,
`eslint-component-scoped-head.log`, `eslint-full-head.log`,
`eslint-full-base-b5.log`, `prettier-component-scoped-head.log`,
`prettier-component-baseline-d6.log`, and
`prettier-qa-compose-hunks.log`.

## Secret scanning

The exact 35 changed files were materialized from the frozen commit and scanned
offline. One unverified Postgres detector candidate was the explicit
pre-existing QA-only fixture at `docker-compose.qa.yml:23`; blame attributes it
to `1ad808bd`, outside this component's added lines. The exact component diff
scan found zero candidates. A verified-only scan found zero verified secrets.

Raw scanner output is mode 0600 inside a mode 0700 evidence directory and is
not reproduced in this report.

Evidence: `trufflehog-offline-summary.json`,
`trufflehog-offline-findings-redacted.json`,
`trufflehog-added-lines-offline-summary.json`, and
`trufflehog-verified-summary.json`.

## Human gate and cleanup

- Desktop Microsoft Word open/save/reopen/PDF-export evidence:
  **HUMAN PENDING**
- The technical acceptance above must not be promoted to broader GA acceptance
  until that human gate and the program's remaining approvals pass.
- Disposable validator and PostgreSQL containers and the validator UDS volume
  were removed after evidence capture.
- Synthetic corpus, scan materializations, formatter output, caches, and the
  temporary dependency symlink were removed.
- No real PHI or provider evaluation occurred.

Evidence: `disposable-container-cleanup.log` and
`temporary-harness-cleanup.log`.
