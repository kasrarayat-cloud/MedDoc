---
id: A05-P1-005
title: Postgres + Redis + MinIO traffic is plaintext on the Docker bridge — TLS not configured
domain: HIPAA-technical-safeguards
severity: P1
agent: 05
---

## Issue

§164.312(e)(1) "Transmission security" requires implementing
"technical security measures to guard against unauthorized access to
electronic protected health information that is being transmitted over
an electronic communications network." HHS guidance interprets the
"network" broadly — even an internal Docker bridge counts under
defence-in-depth.

The compose file uses plaintext URLs everywhere:

| Hop | URL | TLS? |
|---|---|---|
| App → Postgres | `postgresql://meddoc:...@postgres:5432/meddoc?schema=public` | NO — no `sslmode=require` |
| App → Redis | `redis://redis:6379` | NO — would need `rediss://` |
| App → MinIO | `MINIO_ENDPOINT: minio:9000`, `MINIO_USE_SSL: "false"` | NO |

`grep -E "sslmode|rediss|MINIO_USE_SSL: .true." docker-compose.yml`
confirms none are set.

While these connections never leave the Docker bridge on a single VPS
host, two attacker scenarios exploit the gap:

1. **Lateral movement after one container compromise.** If e.g. a
   Caddy plugin RCE or a worker dependency RCE gives an attacker code
   exec inside one container, they can read every PHI byte off the
   bridge between MinIO and the worker (audio bytes), or off the
   pgwire stream (every SQL row).
2. **Future multi-host expansion.** When the worker is split off to a
   dedicated host (RAM-constrained VPS makes this likely within 12
   months — see memory note on RAM regression), the URLs become
   cross-VPS without a TLS retrofit.

The Postgres bind is `127.0.0.1:5432` (good — no external exposure)
but the intra-bridge traffic still rides cleartext.

## Evidence

- `docker-compose.yml:112,118,341,342,346-347,432,440-445,494` —
  every URL plaintext.
- No certificate configuration in any service block.

## Risk

- §164.312(e)(1) — Transmission security; defence-in-depth posture is
  weak. Not a categorical violation since the data stays inside one
  host's loopback-equivalent, but every HIPAA-mature SaaS encrypts
  intra-cluster too.
- Future migration risk: re-enabling TLS during a multi-host split
  while in production is a P0 incident waiting to happen.

## Recommended fix

1. **Postgres TLS.** Issue an internal CA cert via Caddy's PKI app
   (already running) or step-ca. Configure Postgres `ssl=on`, mount
   server cert + chain. App connects with `sslmode=require`.
2. **Redis TLS.** Use `redis:7-alpine` with `--tls-port 6380`,
   provide cert/key, switch URL to `rediss://redis:6380`.
3. **MinIO TLS.** Set `MINIO_USE_SSL: "true"`, mount certs at
   `/root/.minio/certs/public.crt` + `private.key`. Caddy can
   front-proxy this on the same Docker network.
4. **Document the decision** if intra-bridge TLS is intentionally
   deferred for the pilot — add to `docs/HIPAA_COMPLIANCE.md` as
   "Accepted risk" with a sunset date and the threat-model rationale.

This is P1 because the practical exposure window is narrow (single-
host Docker bridge), but the formal §164.312(e)(1) posture is below
industry standard for healthcare SaaS.
