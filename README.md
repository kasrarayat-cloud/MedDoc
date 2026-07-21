# QuillMD (TranscribeMD) + MedDoc Pro [decommissioned]

One monorepo, two products — but only one in active scope:

- **QuillMD / TranscribeMD** — solo-doctor AI scribe. Upload audio / dictate / paste notes → SOAP note + ICD/CPT codes + Rx drafts + referrals + patient summary, all signed and exported to the EHR of choice. **Active development.**
- **MedDoc Pro** — HIPAA-compliant clinical CRM for small practices. Patient files, clinical notes, document editor, voice intake, audit log. **Decommissioned** as of 2026-05-04 — production container still serves legacy traffic on `pro.quillmd.com`/`admin.quillmd.com`, but no new development, no CI tests, no audits. See `docs/POST_MERGE_TODO.md` §21.

Both share infrastructure: Postgres, NextAuth, shared types, same VPS. A third app (`marketing`) is the static landing site that points new users at TranscribeMD signup.

---

## Architecture at a glance

- **Frontend**: Next.js 16 (App Router) for all three apps.
- **Auth**: NextAuth v5 with JWT strategy + single-session enforcement via `UserSession` rows.
- **Database**: PostgreSQL 16 with the `pgvector` extension (for per-doctor edit-pattern embeddings added in T-M14.1).
- **Queue**: Redis + BullMQ drives the 6+7 transcription pipeline.
- **Object storage**: MinIO (S3-compatible) for uploaded audio + dictation.
- **AI providers**: Anthropic Claude Sonnet 4.6 (pipeline), Deepgram Nova-3 Medical (transcription), OpenAI (embeddings + meddoc-pro voice features).
- **Email**: Resend (signed-note delivery; gated behind a verified-domain flag).
- **Edge**: Caddy terminates HTTP and routes by port/host to each app.
- **Observability**: Sentry on meddoc-pro (transcribe-md pending).

Everything runs in Docker Compose on a single VPS — 8 containers total at steady state.

---

## Monorepo layout

```
/opt/meddoc-pro/
├── apps/
│   ├── meddoc-pro/        Next.js — clinical CRM (port 3000 internal)
│   ├── transcribe-md/     Next.js + BullMQ worker (port 9020 public)
│   └── marketing/         Next.js — static landing site (port 9010 public)
├── packages/
│   ├── ai/                Shared Anthropic + Deepgram + OpenAI client, MOCK hook, pricing
│   ├── auth/              Shared NextAuth config + tenant helpers
│   ├── db/                Prisma schema + migrations + generated client
│   └── types/             Shared Zod schemas (SOAP parser + renderer)
├── docs/
│   ├── BAA_CHECKLIST.md
│   ├── DEPLOYMENT_RUNBOOK.md
│   ├── ROTATION_RUNBOOK.md
│   ├── T-M11-FOLLOWUPS.md
│   ├── T-M12-MINIO-CLEANUP.md
│   └── T-M15-AUDIT-REPORT.md
├── docker-compose.yml     8 services (caddy + marketing + meddoc-pro + transcribe-md
│                          + transcribe-md-worker + postgres + redis + minio)
├── Caddyfile              reverse proxy config (MODE A = IP, MODE B = domain+TLS)
└── .env.production.example  copy to .env and fill in real values
```

---

## Prerequisites

- Docker Engine 24+ with the Compose v2 plugin
- Node 22+ (for local dev + running migrations)
- npm 10+
- A VPS with ≥2 GB RAM for all 8 containers at idle. More is better; the current setup swaps under real load.
- Optional for real AI calls: accounts + API keys with Anthropic, Deepgram, OpenAI. All three offer BAAs — **sign them before sending real PHI**.

---

## Local dev setup

```bash
# 1. Clone
git clone https://github.com/kasrarayat-cloud/MedDoc.git /opt/meddoc-pro
cd /opt/meddoc-pro

# 2. Copy the env template and fill in values
cp .env.production.example .env
$EDITOR .env     # at minimum: DB_PASSWORD, AUTH_SECRET, ANTHROPIC_API_KEY,
                 # OPENAI_API_KEY, DEEPGRAM_API_KEY (or set MOCK_AI_CALLS=true
                 # to skip real provider calls for local dev)

# 3. Install dependencies (workspace-aware)
npm install

# 4. Start infrastructure only
docker compose up -d postgres redis minio caddy

# 5. Inspect migration ledger and target only (applies nothing)
docker compose run --rm db-migrate --phase status
```

A bare `docker compose run --rm db-migrate` is also read-only status. It no
longer applies migrations. For disposable local development, complete the
isolated closed database-release flow in `docs/qa/README.md`; do not grant
production mutation controls to the production-named database merely to make a
local setup work. A separately authorized production-style target must follow
`docs/DEPLOYMENT_RUNBOOK.md` §1.4.1 and both online-transition runbooks. Raw
Prisma deploy/resolve commands are not setup shortcuts. Every cumulative
segment invocation requires a newly verified phase-specific
`targetFingerprints.<segment>` status entry; the entry is ledger-,
accepted-source-, phase-, and target-bound and must never be reused or derived.

Only after the closed release graph and exact database-principal preflights
pass may the app tier start:

```bash
# 6. Start apps
docker compose up -d marketing meddoc-pro transcribe-md transcribe-md-worker

# 7. Smoke-check
curl -sS -o /dev/null -w "marketing: %{http_code}\n" http://localhost:9010/
curl -sS -o /dev/null -w "transcribe-md: %{http_code}\n" http://localhost:9020/
# Both should return 200 or 307.
```

Local ports (all bound to `127.0.0.1` only):

| Service                   | Container port → Host port | Purpose                            |
| ------------------------- | -------------------------- | ---------------------------------- |
| caddy                     | 80 → 80                    | meddoc-pro via Caddy               |
| marketing                 | 9010 → 9010                | Public landing site                |
| transcribe-md             | 9020 → 9020                | Solo-doctor app                    |
| meddoc-pro (behind caddy) | 3000 (internal only)       | Clinical CRM                       |
| postgres                  | 5432 → 127.0.0.1:5432      | Direct SQL via `psql -h localhost` |
| redis                     | 6379 → 127.0.0.1:6379      | BullMQ broker                      |
| minio API                 | 9000 → 127.0.0.1:9000      | Object storage                     |
| minio console             | 9001 → 127.0.0.1:9001      | Web UI for bucket inspection       |

---

## Production deploy

See **[docs/DEPLOYMENT_RUNBOOK.md](docs/DEPLOYMENT_RUNBOOK.md)** for:

- First-time deploy on a fresh Ubuntu VPS
- Rolling updates (`git pull` → rebuild → recreate)
- Rollback procedure
- Restore from pg_dump backup
- Common failure modes

For secret rotation (AUTH_SECRET, OPENAI_API_KEY, DB password, TLS certs), see **[docs/ROTATION_RUNBOOK.md](docs/ROTATION_RUNBOOK.md)**.

For BAA / HIPAA pre-flight, see **[docs/BAA_CHECKLIST.md](docs/BAA_CHECKLIST.md)**.

---

## Tests

```bash
# Unit tests (both apps). Vitest.
cd apps/transcribe-md && npx vitest run
cd apps/meddoc-pro   && npx vitest run

# Playwright E2E (TranscribeMD only). Runs with MOCK_AI_CALLS=true so
# it never touches Anthropic/Deepgram.
cd apps/transcribe-md && npx playwright test
```

Current counts at time of writing: 181 unit tests (85 transcribe-md + 96 meddoc-pro), 4 Playwright E2E scenarios.

---

## Milestones

This repo ships in numbered milestones. Each milestone gets a PR, a set of focused commits, and (usually) a follow-up doc in `docs/`. Recent:

- **T-M12** — MinIO orphan cleanup cron.
- **T-M13** — Per-layer pipeline resumability (retries skip already-completed stages).
- **T-M14.1** — Invisible per-doctor edit tracking (pgvector schema + sign-time capture hook).
- **T-M15** — Pre-launch QA audit. See [docs/T-M15-AUDIT-REPORT.md](docs/T-M15-AUDIT-REPORT.md) for the findings driving T-M16.
- **T-M16** — Audit follow-ups, shipped in batches. T-M16.1 (this one) = docs sprint + legal pages.

---

## Support / contact

Issues or questions: **support@ashtechgroup.com** (also the NextAuth admin address).

For HIPAA / compliance questions: read `docs/BAA_CHECKLIST.md` first, then email the same address.
