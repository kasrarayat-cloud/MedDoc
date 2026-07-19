# transcribe-md E2E suite

Playwright end-to-end tests that exercise authenticated clinician workflows
against the isolated QA Postgres, Redis, worker, and MinIO stack.

## One-time setup

```
npm install
npm run test:e2e:install -w transcribe-md   # downloads chromium
```

## Running the suite

The tests hit a live transcribe-md stack (the real app + worker + Postgres +
MinIO). The **worker must have `MOCK_AI_CALLS=true` set** or every pipeline
run will take ~90 seconds of real API latency per scenario.

```sh
# From /opt/meddoc-pro, temporarily flip the worker to mock mode:
docker compose stop transcribe-md-worker
MOCK_AI_CALLS=true docker compose up -d --no-deps transcribe-md-worker

# Run the suite:
npm run test:e2e -w transcribe-md

# Restore the worker:
docker compose stop transcribe-md-worker
docker compose up -d transcribe-md-worker
```

Or add `MOCK_AI_CALLS=true` to `.env` while iterating locally.

`PW_BASE_URL` overrides the default `http://localhost:9020` if you're running
against a different host.

## What each scenario catches

| # | File | Regressions it guards |
|---|---|---|
| 1 | `1-audio-upload-full.spec.ts` | T-M8 Bug 1 (mode-tile 500), Bug 2 (PDF+DOCX dual download), Bug 3 (sign modal hang) |
| 2 | `2-voice-dictation.spec.ts`   | T-M8 Bug 1; dictation upload contract (UI recorder is bypassed — see comment in file) |
| 3 | `3-text-to-soap.spec.ts`      | T-M8 Bug 1; text-mode pipeline end-to-end |
| 4 | `4-back-to-dashboard.spec.ts` | T-M8 Bug 4 (Back-to-dashboard link navigates) |
| 29 | `29-template-twin-infrastructure.spec.ts` | Template Twin upload/certification, typed + mocked-voice worker fills, independent DOCX readback, SOAP invalidation/regeneration, stored-byte signing, and corrupt-object rejection |

## Fixtures

- `fixtures/audio/silence-3sec.mp3` — 1 KB fake MP3 (ID3v2.4 header + frame-sync
  padding). Content is never actually read because `MOCK_AI_CALLS=true` bypasses
  Deepgram. The file exists so the UI accepts the upload.
- `fixtures/notes/clinical-notes.txt` — ~400-char clinical shorthand for the
  text scenario.
- Scenario 29 creates its small synthetic DOCX package in memory. It does not
  add or reuse a physician document. The only identities use
  `@synthetic.test`.

## Test isolation

- Every test creates a fresh user with email prefix `qa-e2e-`.
- `global-setup.ts` runs a prefix-scoped DELETE before the first test so a
  crashed run doesn't leave orphans.
- `afterEach` and `global-teardown.ts` run the same cleanup.
- The cleanup uses `docker compose exec postgres psql` — no Prisma client
  loading inside the Playwright process, so tests don't need `.env` on the
  runner.

## Template Twin infrastructure project

Scenario 29 is excluded from the default `chromium` project because it needs a
richer, evidence-bearing Layer-3 mock. Start/recreate only the isolated QA app
and worker with the dedicated flag, then run the project:

```sh
MOCK_TEMPLATE_TWIN_E2E=true \
  docker compose -f docker-compose.qa.yml up -d --wait \
  transcribe-md transcribe-md-worker

cd apps/transcribe-md
PW_BASE_URL=http://localhost:9020 \
  npx playwright test --project=template-twin
```

The fixture is enabled only when all three server-side conditions hold:
`MOCK_AI_CALLS=true`, `MOCK_TEMPLATE_TWIN_E2E=true`, and the parsed database
name contains a `qa`, `test`, or `synthetic` segment. The scenario intentionally
creates immutable certification/signing evidence; the QA workflow destroys the
entire isolated stack with `docker compose ... down -v` instead of weakening
production retention triggers for test cleanup.

See `docs/qa/template-twin-synthetic-e2e.md` for evidence boundaries and gates.
