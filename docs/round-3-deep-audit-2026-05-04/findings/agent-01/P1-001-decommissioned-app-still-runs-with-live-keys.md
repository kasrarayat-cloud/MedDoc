---
id: A01-P1-001
severity: P1
title: "Decommissioned apps/meddoc-pro container holds full live key set in env vars"
domain: Credential & secret hygiene
files:
  - docker-compose.yml
  - apps/meddoc-pro/.env
  - apps/meddoc-pro/.next/standalone/apps/meddoc-pro/.env
---

## Issue
AGENT 01 brief explicitly states `apps/meddoc-pro` is **DECOMMISSIONED** and out of scope. Yet the running container `meddoc-pro-meddoc-pro-1` is **active** and `docker inspect` confirms it has the full live key set in its environment:

```
$ docker inspect meddoc-pro-meddoc-pro-1 --format '{{range .Config.Env}}{{println .}}{{end}}' \
    | grep -iE "API_KEY|SECRET|PASSWORD"
RESEND_API_KEY=<REDACTED-LIVE-RESEND>
SCRIBE_SERVICE_TOKEN=0edd0e5...
DB_PASSWORD=X9kLm2pQz7
OPENAI_API_KEY=sk-proj-<REDACTED>...
ANTHROPIC_API_KEY=sk-ant-api03-<REDACTED>...
DEEPGRAM_API_KEY=<REDACTED-DEEPGRAM>...
MINIO_ROOT_PASSWORD=WHu8b2IFVoc...
AUTH_SECRET=1S9z4BGjYjbIn...
```

The image `meddoc-pro-meddoc-pro:latest` also bakes `/app/apps/meddoc-pro/.env` with all the same secrets (see A01-P0-001).

## Evidence
`docker ps --format 'table {{.Names}}\t{{.Image}}'` (live):
```
meddoc-pro-caddy-1                  caddy:2-alpine
meddoc-pro-transcribe-md-1          meddoc-pro-transcribe-md
meddoc-pro-meddoc-pro-1             meddoc-pro-meddoc-pro      ← decommissioned per brief
meddoc-pro-transcribe-md-worker-1   meddoc-pro-transcribe-md-worker
meddoc-pro-postgres-1               pgvector/pgvector:pg16
meddoc-pro-postgres-backup-1        prodrigestivill/postgres-backup-local:16
meddoc-pro-redis-1                  redis:7-alpine
meddoc-pro-minio-1                  minio/minio:latest
meddoc-pro-marketing-1              meddoc-pro-marketing
```

Despite the decommissioning, the service continues to receive every secret the live `transcribe-md` apps use. Each additional process holding the keyring multiplies the attack surface (memory scrape, /proc/PID/environ leak, container escape).

## Risk
1. **Increased attack surface**: a decommissioned codebase doesn't get the same patch hygiene, yet still holds the production keyring.
2. **Out-of-scope holdover**: nine containers were expected per the regression matrix — meddoc-pro service is one of them. If "decommissioned" is the intended steady state, the decision to keep it running needs rationale documented; if not, it should be removed from `docker-compose.yml`.
3. The Next.js standalone bundle for this decommissioned app — `apps/meddoc-pro/.next/standalone/apps/meddoc-pro/.env` — exists on the host (mode 0755) with live keys. Future ops mistakes (rsync, scp, image rebuild) will continue to copy it.

## Recommended fix
1. Decide explicitly whether `apps/meddoc-pro` is decommissioned. If yes:
   - Remove the service from `docker-compose.yml`.
   - Drop the `meddoc-pro-meddoc-pro:latest` image.
   - `rm -rf /opt/meddoc-pro/apps/meddoc-pro/.next /opt/meddoc-pro/apps/meddoc-pro/.env*`.
   - Update the regression matrix in `docs/preflight-reports/` and `meddoc_pro_regression_matrix.md` to reflect 8-container baseline.
2. If the service must remain (e.g. as a redirect shim), strip its env vars to **only** what it needs. `pro.quillmd.com` doesn't need OpenAI / Anthropic / Deepgram if it's just redirecting — that is `transcribe-md`'s domain.
3. Document the decision in `KASRA_HANDOFF.md` so a future operator doesn't re-add the env vars by reflex.
