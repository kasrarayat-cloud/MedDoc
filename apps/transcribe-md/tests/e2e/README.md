# transcribe-md E2E suite

Playwright end-to-end tests that exercise the full signup → visit → sign flow.
Four scenarios, one per T-M8 bug cluster.

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

## Fixtures

- `fixtures/audio/silence-3sec.mp3` — 1 KB fake MP3 (ID3v2.4 header + frame-sync
  padding). Content is never actually read because `MOCK_AI_CALLS=true` bypasses
  Deepgram. The file exists so the UI accepts the upload.
- `fixtures/notes/clinical-notes.txt` — ~400-char clinical shorthand for the
  text scenario.

## Test isolation

- Every test creates a fresh user with email prefix `qa-e2e-`.
- `global-setup.ts` runs a prefix-scoped DELETE before the first test so a
  crashed run doesn't leave orphans.
- `afterEach` and `global-teardown.ts` run the same cleanup.
- The cleanup uses `docker compose exec postgres psql` — no Prisma client
  loading inside the Playwright process, so tests don't need `.env` on the
  runner.
