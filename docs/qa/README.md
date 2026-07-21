# Safe QA / E2E — the isolated `meddoc-qa` stack

The transcribe-md + meddoc-pro test harnesses are **safe-by-default**: the
seeders, fixture builders, and the Playwright E2E cleanup all refuse to run
unless `DATABASE_URL` (or the cleanup target) points at a database whose name
carries a **qa/test/e2e/ci marker**. The production DB is named `meddoc`, so it
is never a valid target. This closes QA-report finding **F1** (the harness used
to be wired to the live `meddoc` DB with only an email-prefix convention).

## The fail-closed guard

`packages/db/src/db-guard.ts` (pure, dependency-free; exposed as
`@meddoc/db/guard` so importing it never instantiates Prisma).

- `assertNonProdDatabase()` — for `DATABASE_URL`-based scripts (seeders).
- `assertNonProdDbName(name)` — for the psql-based E2E cleanup.

It **fails closed**: it aborts unless the target is _positively_ a non-prod DB
(name matches `/(^|[_-])(qa|test|e2e|ci)([_-]|$)/i`, and is neither the prod
name `meddoc` nor on the prod host). Unset / unparseable / marker-less → abort.
Wired into: `seed-tenancy-fixtures.ts`, `seed-e2e-admin.ts`, `seed-admin.ts`
(meddoc-pro); `seed-qa-fixtures.ts`, `seed-qa-user.ts`,
`cross-input-mode/runner.ts`, `tests/e2e/helpers/cleanup.ts` (transcribe-md).

Test: `apps/transcribe-md/tests/db-guard.test.ts` (`npm run test:unit -w transcribe-md`).

## The isolated stack

`docker-compose.qa.yml` (project `meddoc-qa`) — own postgres/redis/minio on
fresh volumes + the app/worker from the **already-built prod images** (no
rebuild), DB `meddoc_qa_test`, app on `127.0.0.1:9020`, `MOCK_AI_CALLS=true` +
dummy keys. Prod is untouched: separate project/network/volumes.

### Run the full safe-QA flow

```sh
cd /opt/meddoc-pro
QA="docker compose -f docker-compose.qa.yml"

# 1. infra
$QA up -d --wait postgres redis minio

# 2. schema status only (server-enforced read-only; applies nothing)
$QA run --rm db-migrate --phase status
```

A bare `$QA run --rm db-migrate` also uses the Compose default
`--phase status`; it never applies migrations. Schema mutation is available
only through the closed cumulative runner phases. For each segment, obtain a
fresh status result, verify its exact ledger position and disposable QA target,
then pass its phase-specific `targetFingerprints.<segment>` entry as
`DATABASE_RELEASE_MIGRATION_APPROVED_TARGET_FINGERPRINT` to exactly one
invocation. The status map is phase-, ledger-, accepted-source-, and
target-bound; obtain a new entry before every retry, resume, or no-op. An empty
map on a recovery target is a stop condition. Execute only this graph:

```text
lineage-expand -> lineage online protocol -> auth-expand
auth online protocol -> pre-v9 -> release-security provisioner -> v9
```

The executable synthetic reference is the matching database-release sequence
in `.github/workflows/e2e.yml`. It obtains a fresh phase-specific lineage status
challenge before **every** `guard-index`, `backfill` (including the no-op rerun),
`indexes`, `validate`, and `contract` command; verifies
`presentIndexesExact`, `validationConstraintExact`, and
`transitionContractExact`; and completes the authentication-token contract
before later migration segments. Production approval variables are unnecessary
for this positively identified disposable QA database and must remain unset.
See
`docs/runbooks/template-twin-lineage-online-migration.md` and
`docs/runbooks/auth-token-linearization-online.md` for the operator gates.

Do not start the QA app or worker until final migration status and every exact
database-principal preflight pass. The optional fixture command below overrides
the image entrypoint only to run a guarded synthetic data seeder after schema
admission; it is not a schema migration path.

The image-embedded HBA contract controls PostgreSQL client authentication. It
does not provide or prove TLS. This local isolated stack's explicit transport
exceptions are synthetic-QA gaps and must never be used as production TLS
evidence.

Only after the closed release graph, final status, and all exact-principal
preflights pass may this synthetic stack continue:

```sh
cd /opt/meddoc-pro
QA="docker compose -f docker-compose.qa.yml"

# 3. app + worker
$QA up -d --wait transcribe-md transcribe-md-worker

# 4. minio bucket (created lazily otherwise → app /api/health minio check stays red)
$QA exec -T minio sh -c 'export MC_CONFIG_DIR=/tmp/mc; mc alias set local http://127.0.0.1:9000 qa_minio qa_minio_pw && mc mb --ignore-existing local/transcribe-md-audio'

# 5. (optional) seed fixtures against the qa DB — the guard confirms the target
QA_URL="postgresql://meddoc:qa_test_pw@127.0.0.1:5432/meddoc_qa_test?schema=public"
#   (seeders run inside the builder image so they have prisma + the source)
#   $QA run --rm -e DATABASE_URL=... --entrypoint sh db-migrate -c 'cd /app/apps/transcribe-md && npx tsx scripts/seed-qa-user.ts'

# 6. run the E2E suite against :9020 (cleanup defaults to this stack)
cd apps/transcribe-md && PW_BASE_URL=http://localhost:9020 npx playwright test --project=chromium

# 7. tear down (removes the qa volumes)
cd /opt/meddoc-pro && $QA down -v
```

`PW_BASE_URL` already defaults to `http://localhost:9020`, and the E2E cleanup
(`cleanup.ts`) defaults to `E2E_CLEANUP_COMPOSE=docker-compose.qa.yml` +
`E2E_CLEANUP_DB=meddoc_qa_test`. So `npm run test:e2e -w transcribe-md` against
this stack is safe with no extra env. Browser: the bundled chromium via
Playwright (never the MCP / chrome channel).

## Pointing at a different isolated env

Set `DATABASE_URL` / `E2E_CLEANUP_DB` to your own database — but its **name must
carry a qa/test/e2e/ci marker** or the guard aborts. There is intentionally no
"force" flag: a database named `meddoc` (prod) can never be a target.
