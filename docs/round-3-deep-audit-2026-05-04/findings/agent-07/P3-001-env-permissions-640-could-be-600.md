---
id: A07-P3-001
title: /opt/meddoc-pro/.env is 0640 (group-readable); 0600 is the stricter posture
severity: P3
domain: infrastructure-opsec
date: 2026-05-04
---

## Issue

`/opt/meddoc-pro/.env` is mode 0640, owned `claude:claude`. Group-read is
allowed. The group is `claude` (single-user group), so today no other
account can read it via group membership. The auditor's threshold for an
env file containing live API keys (Anthropic, OpenAI, Deepgram, Resend,
Backblaze [pending]) and DB / MinIO / NextAuth secrets is generally
0600 — eliminate the group-read entirely so a future `usermod -aG claude
<other>` does not silently leak secrets.

Same applies to `.env.phase-6.2.template` (also 0640) and
`docker-compose.yml` (mode 0664 — more concerning as it embeds default
secrets like `changeme_in_production` and is *also* world-readable).

## Evidence

```
$ stat -c '%a %U:%G %n' /opt/meddoc-pro/.env /opt/meddoc-pro/.env.phase-6.2.template /opt/meddoc-pro/docker-compose.yml /opt/meddoc-pro/Caddyfile
640 claude:claude /opt/meddoc-pro/.env
640 claude:claude /opt/meddoc-pro/.env.phase-6.2.template
664 claude:claude /opt/meddoc-pro/docker-compose.yml
664 claude:claude /opt/meddoc-pro/Caddyfile
```

`.env` contents (key names listed; live values **deliberately omitted** from
this report — Trufflehog verified each as live on 2026-05-04):
```
ANTHROPIC_API_KEY=<REDACTED-LIVE-sk-ant-api03>
OPENAI_API_KEY=<REDACTED-LIVE-sk-proj-MATCHES-LAUNCH_CHECKLIST.md-§6>
DEEPGRAM_API_KEY=<REDACTED-LIVE>
RESEND_API_KEY=<REDACTED-LIVE-re_>
SCRIBE_SERVICE_TOKEN=<REDACTED-LIVE-64-hex>
DB_PASSWORD=<REDACTED-LIVE>
MINIO_ROOT_PASSWORD=<REDACTED-LIVE>
AUTH_SECRET=<REDACTED-LIVE-base64-44>
```

Live API keys for production. Nothing is rotated since `.env.backup` was
written 2026-04-18. (See A01-P0-002 for the OpenAI rotation status.)

## Risk

- Group-read posture is a latent foot-gun: if any future `usermod`
  accidentally adds another user to the `claude` group (or if `claude`'s
  group is reused as a "developers" group), all of these credentials
  leak.
- `docker-compose.yml` at mode 0664 is *world*-readable. It contains the
  default-fallback secret pattern `${DB_PASSWORD:-changeme_in_production}`
  and `${MINIO_ROOT_PASSWORD:-changeme_in_production}` — the placeholders
  themselves are public-OK, but the structure also contains hostnames,
  ports, API endpoint specifics, and the entire deployment topology. Not
  catastrophic but unnecessary disclosure.
- Reading the .env.production.example confirms it is correctly
  placeholder-only — that's a positive.

## Recommended fix

```bash
sudo chmod 0600 /opt/meddoc-pro/.env /opt/meddoc-pro/.env.phase-6.2.template
sudo chmod 0640 /opt/meddoc-pro/docker-compose.yml /opt/meddoc-pro/Caddyfile
sudo chown claude:claude /opt/meddoc-pro/.env*
```

Also rotate any credentials that appear in this audit's evidence (the
keys above are now logged in this finding's text and should be considered
exposed): Anthropic, OpenAI, Deepgram, Resend, AUTH_SECRET, DB_PASSWORD,
MINIO_ROOT_PASSWORD, SCRIBE_SERVICE_TOKEN. Regenerate via the providers'
consoles and re-deploy with a `docker compose up -d --force-recreate`.
