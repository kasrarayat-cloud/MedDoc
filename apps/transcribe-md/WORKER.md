# TranscribeMD worker (T-M4)

A BullMQ consumer that runs the 6-layer audio → SOAP pipeline for the
TranscribeMD Solo product. Same monorepo source as `apps/transcribe-md/`
(the web app); it just ships a different container image built from
`apps/transcribe-md/Dockerfile.worker` and invoked via docker-compose
as the `transcribe-md-worker` service.

## The pipeline

```
QUEUED → TRANSCRIBING → EXTRACTING → DRAFTING → CRITIQUING → POLISHING → READY
```

Each status name corresponds to exactly one layer module in
`src/worker/layers/`:

| Status       | File                           | Purpose                               |
| ------------ | ------------------------------ | ------------------------------------- |
| TRANSCRIBING | `01-transcribe.ts`             | Deepgram Nova-3 Medical batch ASR     |
| EXTRACTING   | `02-speaker-roles.ts` + `03-…` | Role map + structured entities        |
| DRAFTING     | `04-generate-soap.ts`          | Markdown SOAP with specialty guidance |
| CRITIQUING   | `05-self-critique.ts`          | Independent audit for hallucinations  |
| POLISHING    | `06-polish.ts`                 | Applies fixable critique issues       |

Each layer updates `TranscribeVisit.status` before it starts and
persists its artifact (`transcriptRaw`, `speakerMap`, `entities`,
`soapDraft`, `critique`, `soapFinal`) before returning. That persistence
is deliberate: the Pipeline tab in the UI reads each field directly so
a failed mid-pipeline run leaves diagnostic breadcrumbs.

## Environment

All values flow in through `docker-compose.yml` and the repo's `.env`.

Required:

- `DATABASE_URL` — same Postgres as meddoc-pro / scribe.
- `REDIS_URL` — shared BullMQ broker.
- `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`.
- `ANTHROPIC_API_KEY`.
- `DEEPGRAM_API_KEY`.

Optional:

- `TRANSCRIBE_MD_MINIO_BUCKET` — default `transcribe-md-audio`.
- `DEEPGRAM_MODEL` — default `nova-3-medical`.
- `TRANSCRIBE_MD_WORKER_CONCURRENCY` — default `2`.
- Pricing overrides:
  - `CLAUDE_SONNET_46_INPUT_CENTS_PER_M` (default `300` → $3/M)
  - `CLAUDE_SONNET_46_OUTPUT_CENTS_PER_M` (default `1500` → $15/M)
  - `DEEPGRAM_COST_PER_MIN_CENTS` (default `1.45` → $0.0145/min)

## Running locally

```
cd apps/transcribe-md
npm run worker   # tsx src/worker.ts
```

Point it at the shared Redis + Postgres + MinIO via env vars. You
rarely need this — the container runs as a compose service.

## Manual test procedure

Real-audio end-to-end test (rough shape — replace `<real.mp3>` and
login credentials with your own):

1. **Bring up the stack**
   ```
   docker compose up -d transcribe-md transcribe-md-worker caddy
   docker compose logs -f transcribe-md-worker
   ```
2. **Sign up** at `https://app.quillmd.com/signup`, or reuse an
   existing account.
3. **Create a visit** on `/visits/new` with mode = "Upload audio".
4. **Upload audio** — drag a `<real.mp3>` into the dropzone, click
   "Upload & transcribe". The UI should flip to the Processing screen
   within ~1s.
5. **Watch the log strip** in the UI (and in worker logs): expect to
   see the status fields advance through TRANSCRIBING → EXTRACTING →
   DRAFTING → CRITIQUING → POLISHING → READY.
6. **Review** the SOAP tab. Skim for accuracy. Visit the Transcript
   tab — confirm speaker roles look right; reassign if not. Visit the
   Pipeline tab — critique issues + entities should be populated.
7. **Edit** the SOAP note (click to open inline editor, save).
   Refresh the page. Edits should persist.
8. **Sign & lock**. Confirm the note goes readonly and the "Signed"
   pill appears.

Expected timing on a 10-minute recording: ~30-90s pipeline wall-clock
depending on Claude/Deepgram latency.

## Inspecting an in-progress run

```
# Worker logs — every layer prints a one-line summary
docker compose logs -f transcribe-md-worker

# Per-visit DB state (replace <id>)
docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc \
  -c "SELECT id, status, \"needsReview\", \"reviewReason\", \"processingCostCents\" \
      FROM transcribe_visits WHERE id = '<id>';"

# AiCall rows — one per layer, includes token counts + cents
docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc \
  -c "SELECT purpose, model, latency_ms, input_tokens, output_tokens, \
             cost_usd_cents, success, error_code \
      FROM ai_calls WHERE \"visitId\" = '<id>' \
      ORDER BY \"createdAt\";"

# MinIO audio object
docker exec meddoc-pro-minio-1 mc ls local/transcribe-md-audio/<userId>/<visitId>
```

## Failure + retry

A failed job sets `status=FAILED` + `needsReview=true` + `reviewReason`
(first 500 chars of the error). The UI shows the failure view with a
"Try again" button that re-uploads audio and re-enqueues the pipeline.

BullMQ is configured with `attempts: 3` + exponential backoff, so
transient Deepgram/Claude 5xx errors usually self-heal before the
user sees FAILED. Terminal 4xx (bad audio, bad API key) short-circuit
the retries.
