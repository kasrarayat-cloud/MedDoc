# Service Token Rotation Runbook

The `SCRIBE_SERVICE_TOKEN` authenticates every call from `apps/scribe`
to `apps/meddoc-pro`'s `/api/internal/*` endpoints. It should be
rotated on a schedule (quarterly minimum) and immediately on any
suspected compromise.

## Resolution order (M7)

Both apps resolve the token via `readServiceToken()` in
`@meddoc/auth`:

1. **`SCRIBE_SERVICE_TOKEN_FILE`** env var → file contents (trimmed).
   Populated via a Docker/Kubernetes secret mount, e.g.
   `/run/secrets/scribe_service_token`.
2. **`SCRIBE_SERVICE_TOKEN`** env var — direct value.

First non-empty source wins. Resolution happens once per process and
the value is cached; **a rotation requires a container restart.**

## Rotation procedure

### Option A — file-based (recommended)

Prerequisite: both apps mount the same secret file.

1. Generate a new token:
   ```bash
   openssl rand -base64 48 | tr -d '=+/' | cut -c1-48
   ```
2. Write it atomically to the mounted path on every host running
   Scribe + MedDoc Pro containers:
   ```bash
   # Atomic replace — move is atomic on POSIX within the same filesystem.
   TOKEN='<new-token>'
   printf '%s' "$TOKEN" > /run/secrets/scribe_service_token.new
   chmod 0400 /run/secrets/scribe_service_token.new
   mv /run/secrets/scribe_service_token.new /run/secrets/scribe_service_token
   ```
3. Restart the affected containers **in this order** so no internal
   call sees a mid-rotation state:
   ```bash
   docker compose restart meddoc-pro        # accepts new token
   docker compose restart scribe scribe-worker scribe-ws   # starts using new token
   ```
   Total downtime per container: ~5–10 s.
4. Verify with a canary sign attempt (create a test ScribeVisit,
   sign it — the SOAP push + 5 best-effort pushes should all succeed).
5. Document the rotation in the practice's audit log system
   (SIEM / security ticket).

### Option B — env-var rotation (fallback)

If secret mounting isn't available:

1. Update `SCRIBE_SERVICE_TOKEN=` in `.env` with the new value.
2. `docker compose up -d --force-recreate meddoc-pro scribe scribe-worker scribe-ws`.
3. Verify + document as in Option A.

## Failure modes

- **New token propagated to only one side.** The other side returns
  401 `Invalid token.` on every internal call. Fix: restart the
  lagging container. Scribe's per-push retry (one inline retry on
  5xx/network) does not retry 4xx (M6 D4), so the user sees failed
  pushes in the review UI and can retry after the restart finishes.
- **File exists but is empty.** `readServiceToken()` logs a warning
  and falls back to `SCRIBE_SERVICE_TOKEN` env. If that's also unset,
  every internal request gets 403 `Internal API is disabled`.
- **File exists but contains the wrong token.** Same as any mismatch
  — internal calls get 401s. Fix by rewriting the file + restarting.

## SIGHUP reload (deferred to M7.1)

Live reload without restart is intentionally not supported in M7 —
simpler + safer given one internal surface. If the operational cost
of the restart window becomes painful, M7.1 can add a SIGHUP handler
that re-runs `_resetServiceTokenCache()` + `readServiceToken()`.

## Audit expectations

Every rotation should produce:

1. An entry in the ops runbook / change log.
2. A Sentry release marker (so any post-rotation errors group by
   release, not by the prior window).
3. A Scribe smoke test (create → sign → verify all M6 pushes land).
