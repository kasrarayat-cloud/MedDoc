# Secret & Credential Rotation Runbook

How to rotate every secret and credential used by `/opt/meddoc-pro`. Referenced from `BAA_CHECKLIST.md` — quarterly rotation is a BAA obligation for most AI provider agreements.

All procedures assume you're SSH'd into the VPS as a sudoer and `cd /opt/meddoc-pro`.

---

## Rotation cadence (suggested)

| Secret | Cadence | Trigger |
|--------|---------|---------|
| `AUTH_SECRET` (JWT signing) | quarterly | scheduled |
| `ANTHROPIC_API_KEY` | quarterly | scheduled, or on suspected leak |
| `OPENAI_API_KEY` | quarterly | scheduled, or on suspected leak |
| `DEEPGRAM_API_KEY` | quarterly | scheduled, or on suspected leak |
| `RESEND_API_KEY` | quarterly | scheduled |
| `DB_PASSWORD` | annually | staff departure, audit finding |
| `MINIO_ROOT_PASSWORD` | annually | staff departure, audit finding |
| TLS certificates (domain mode) | automatic | Let's Encrypt, 60-day renewal |

---

## 1. `AUTH_SECRET` — NextAuth JWT signing key

Effect of rotation: every active JWT is invalidated. All users must re-login. Plan a low-traffic window.

```bash
# 1. Generate a new secret
NEW=$(openssl rand -base64 32)

# 2. Update .env
sed -i.bak "s|^AUTH_SECRET=.*|AUTH_SECRET=$NEW|" .env
shred -u .env.bak       # purge the backup — it contains the old secret
unset NEW

# 3. Recreate all services that read AUTH_SECRET
docker compose up -d --force-recreate meddoc-pro transcribe-md

# 4. Verify
docker compose exec transcribe-md printenv AUTH_SECRET | head -c 10
# Should be the first 10 chars of your new value. (Don't print the full value.)
```

Users who were logged in before step 3 will see the login screen on their next request. Their session cookie signature will no longer validate.

---

## 2. AI-provider API keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`)

Goal: zero dropped jobs during rotation. The trick is to provision the new key, cut over, **then** revoke the old one.

```bash
# 1. Create the new key in the provider console. Don't revoke the old one yet.

# 2. Update .env
$EDITOR .env    # replace the value for the key you're rotating

# 3. Recreate the services that consume it:
#    - ANTHROPIC_API_KEY: meddoc-pro + transcribe-md + transcribe-md-worker
#    - OPENAI_API_KEY: meddoc-pro + transcribe-md + transcribe-md-worker (T-M14.1)
#    - DEEPGRAM_API_KEY: transcribe-md-worker only
docker compose up -d --force-recreate transcribe-md-worker transcribe-md meddoc-pro

# 4. Verify the new key is live
docker compose exec transcribe-md-worker printenv ANTHROPIC_API_KEY | head -c 15

# 5. Wait for any in-flight jobs to drain. BullMQ reports active = 0 when safe.
watch -n 5 'docker compose exec redis redis-cli LLEN "bull:transcribe-md:active"'

# 6. Now revoke the OLD key in the provider console.

# 7. Trigger a real (non-mock) AiCall to confirm the new key works end-to-end.
#    Easiest: sign in as a test doctor, create a text-mode visit, watch it
#    complete in the pipeline tab.
```

**If the rotation was forced by a leak**: reverse the order. Revoke first, then cut over. Accept that in-flight jobs at the moment of revoke will fail; BullMQ will retry them with the new key.

---

## 3. `RESEND_API_KEY`

Email delivery is gated by `RESEND_FROM_VERIFIED=true` AND a non-empty key, so a missing/invalid key just means users don't see the "Email to me" option. Rotation is low-risk.

```bash
# 1. New key at resend.com/api-keys
# 2. Update .env
# 3. Recreate the one service that uses it (transcribe-md)
docker compose up -d --force-recreate transcribe-md
# 4. Test by signing a visit with "Email to me" selected.
```

---

## 4. `DB_PASSWORD` — Postgres superuser

Postgres accepts both the old and new password only during the `ALTER USER` window. Plan a ~30s write-pause.

```bash
# 1. Pick a new password
NEW=$(openssl rand -base64 24 | tr '/+=' '_-_')

# 2. Change it inside the running postgres
docker compose exec -T postgres psql -U meddoc -d postgres \
  -c "ALTER USER meddoc WITH PASSWORD '$NEW';"

# 3. Update .env (both DB_PASSWORD and DATABASE_URL)
sed -i.bak "s|^DB_PASSWORD=.*|DB_PASSWORD=$NEW|" .env
sed -i "s|meddoc:[^@]*@|meddoc:$NEW@|" .env
shred -u .env.bak
unset NEW

# 4. Recreate EVERY service that reads DATABASE_URL.
#    This is ALL app services — compose injects it into each.
docker compose up -d --force-recreate meddoc-pro transcribe-md transcribe-md-worker

# 5. Verify
docker compose exec -T postgres psql -U meddoc -d meddoc -c "SELECT 1;"
# Apps are healthy if they reconnect without errors in the logs.
```

Old connections die on the next query — Prisma's pool will reconnect with the new password from the recreated containers.

---

## 5. `MINIO_ROOT_PASSWORD`

MinIO doesn't support live password changes cleanly — it re-reads the root creds from env at container start. The apps read the same value via `MINIO_SECRET_KEY` in compose.

```bash
# 1. New password
NEW=$(openssl rand -base64 24 | tr '/+=' '_-_')

# 2. Update .env
sed -i.bak "s|^MINIO_ROOT_PASSWORD=.*|MINIO_ROOT_PASSWORD=$NEW|" .env
shred -u .env.bak
unset NEW

# 3. Recreate MinIO first, then the app services that use the new password.
#    Existing object data is unaffected — password changes the access,
#    not the storage.
docker compose up -d --force-recreate minio
docker compose up -d --force-recreate transcribe-md transcribe-md-worker

# 4. Verify: worker bootstrap logs should print "bucket ready" shortly
#    after start. If you see auth errors, the env didn't propagate.
docker compose logs --tail 10 transcribe-md-worker | grep bucket
```

---

## 6. TLS certificates (domain mode)

Let's Encrypt auto-renews via Caddy every 60 days; no manual step is usually required. The cert + account key live in the `caddy_data` volume.

To force renewal:

```bash
# Reloading Caddy triggers a renewal pass for any cert < 30 days to expiry.
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile

# Or nuke the cert and let Caddy re-provision on next request:
docker compose exec caddy rm -rf /data/caddy/certificates
docker compose restart caddy
# The next inbound request on port 443 triggers the ACME dance.
```

Back up `caddy_data` before any destructive cert operation. Losing the ACME account key is recoverable but rate-limit-annoying.

---

## 7. Emergency: suspected credential leak

If an API key or secret has leaked (committed to git, pasted in Slack, shown in a screen recording, etc.), follow this order:

1. **Revoke the old credential FIRST** in the provider console. Accept that in-flight jobs will fail for the duration of the switch-over.
2. **Provision a new credential** in the provider console.
3. **Rotate per the sections above** — skip the "wait for in-flight jobs" step since they're already failing.
4. **Grep `AiCall` for suspicious traffic** during the leak window:
   ```sql
   SELECT createdAt, purpose, provider, success, errorCode, COUNT(*)
   FROM ai_calls
   WHERE createdAt > '<leak-window-start>'
   GROUP BY 1,2,3,4,5
   ORDER BY 1;
   ```
   Look for `success=false` clusters, unfamiliar `purpose` values, or cost spikes.
5. **Grep application logs** for unfamiliar user IDs / IPs / UA strings around the leak window.
6. **Document** the incident: what leaked, when it was revoked, who was notified, what was found in logs. File in `docs/incidents/`.
7. **Notify any affected parties** — if PHI may have been exposed (real keys on real data), HIPAA breach-notification rules apply. Loop in legal.

Keep the revoke-before-rotate ordering even if it means a few minutes of pipeline failures. A failing pipeline is recoverable; a leaked-and-still-live key is not.

---

## 8. Rotation checklist (copy into an ops ticket for each quarterly pass)

- [ ] `AUTH_SECRET` rotated, users re-logged in, Settings → Sessions shows fresh rows
- [ ] `ANTHROPIC_API_KEY` rotated, test visit completes, old key revoked
- [ ] `OPENAI_API_KEY` rotated, test visit completes, old key revoked
- [ ] `DEEPGRAM_API_KEY` rotated, test audio visit completes, old key revoked
- [ ] `RESEND_API_KEY` rotated, test email delivery arrives
- [ ] (annual) `DB_PASSWORD` rotated, apps reconnect, no errors in logs for 1 h
- [ ] (annual) `MINIO_ROOT_PASSWORD` rotated, bucket access confirmed
- [ ] Date + operator + rotated-keys list logged in `docs/incidents/rotations.md`
