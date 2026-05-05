# Incident response runbook

**Purpose:** documented procedure for handling security and reliability incidents. Closes Round 3 audit finding **A12-P0-002** and operationalizes HIPAA §164.308(a)(6) requirements.

**Owner:** Kasra (single-engineer team, pre-pilot). Post-pilot: rotation if + when team grows.
**Last reviewed:** 2026-05-05.

This runbook is the page operator opens at 2 AM. It must be readable cold — terse phrasing, no marketing voice, every command copy-pasteable.

---

## §1 — Severity classification (first 5 minutes)

| SEV | Trigger | Response time |
|---|---|---|
| **SEV-1** | PHI exposure suspected or confirmed; auth bypass; ransomware | Drop everything; target containment within 30 min |
| **SEV-2** | Service down for all users; data integrity compromise (audit_logs tampered, SOAP corruption); secret leak verified | Within 1 hour; staff overnight if needed |
| **SEV-3** | Service degraded for some users; container restart loop; Caddy 5xx storm | Within 4 hours business-day, next-morning off-hours |
| **SEV-4** | Cosmetic bug; non-PHI feature regression; observability gap | Next sprint |

If unsure, classify HIGHER. Downgrading after triage is fine; missing a SEV-1 isn't.

---

## §2 — Detection signals

Where alerts come from:

| Signal | Source | Default action |
|---|---|---|
| Sentry alert | `sentry.io` | Read the breadcrumb chain; classify per §1 |
| User report | `support@quillmd.com` (Resend), in-product feedback | Acknowledge within 1 hr; classify |
| Caddy 5xx spike | `docker logs meddoc-pro-caddy-1` | If sustained >2 min: SEV-2 candidate |
| Container restart loop | `docker compose ps` shows `Restarting (n)` | Investigate before n hits 5 |
| Suspicious DB query | `audit_logs` row with unexpected `action` (e.g. `EXPORTED_AUDIT_LOG` from non-admin) | Treat as SEV-1 until proven benign |
| OOM kill | `dmesg` shows postgres / transcribe-md / worker killed | SEV-2; rotate logs + provision |
| Failed CI on main | GitHub Actions notification | SEV-3 unless it blocks an active deploy |

Daily maintenance task (post-pilot): run `bash scripts/preflight-health-check.sh` (Phase 7 scope; not yet authored). Pre-pilot: manual `docker compose ps` daily.

---

## §3 — First 15 minutes (triage)

```bash
# 1. Snapshot the stack state
docker compose ps
free -h
df -h /
curl -sI -o /dev/null -w '%{http_code}\n' https://app.quillmd.com
curl -sI -o /dev/null -w '%{http_code}\n' https://quillmd.com

# 2. Recent error patterns
docker logs --tail 100 meddoc-pro-transcribe-md-1 2>&1 | grep -iE 'error|fatal' | head -20
docker logs --tail 100 meddoc-pro-transcribe-md-worker-1 2>&1 | grep -iE 'error|fatal' | head -20
docker logs --tail 100 meddoc-pro-caddy-1 2>&1 | grep -E ' (5[0-9]{2}) ' | head -20

# 3. Recent audit events (HIPAA-relevant signals)
docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -c "
  SELECT action, count(*) FROM audit_logs
  WHERE timestamp > now() - interval '15 minutes'
  GROUP BY action ORDER BY count(*) DESC LIMIT 20;
"
```

Make a quick judgment: is PHI exposure plausible?
- Yes → §4 containment FIRST, then §5 investigation
- No → §5 investigation, skip §4

---

## §4 — Containment (PHI exposure path; SEV-1 only)

**The point of containment is to stop the bleeding fast, not to fix the root cause.** Document everything you do; preserve evidence.

```bash
# A. Take the public app offline (kills all live PHI traffic)
docker compose stop transcribe-md transcribe-md-worker

# B. Caddy stays up to serve a maintenance page; the marketing site is fine
# (no PHI). If the breach is at Caddy level, ALSO stop caddy:
# docker compose stop caddy

# C. Lock the DB role to prevent further data exfiltration
# (run as meddoc; it's the bootstrap superuser — see postgres-recovery.md §1)
docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -c "
  ALTER ROLE meddoc CONNECTION LIMIT 0;
"
# This blocks new connections; existing ones continue. Restart postgres
# to fully drain (only if necessary — postgres restart is invasive):
# docker compose restart postgres

# D. Snapshot the current DB state for forensics BEFORE making any
# changes
docker exec meddoc-pro-postgres-1 pg_dump -U meddoc meddoc \
  | gzip > /opt/meddoc-pro/incidents/$(date -u +%Y%m%dT%H%MZ)-pre-investigation.sql.gz

# E. Snapshot recent logs
mkdir -p /opt/meddoc-pro/incidents/$(date -u +%Y%m%dT%H%MZ)
docker logs meddoc-pro-transcribe-md-1 > /opt/meddoc-pro/incidents/$(date -u +%Y%m%dT%H%MZ)/transcribe-md.log 2>&1
docker logs meddoc-pro-caddy-1 > /opt/meddoc-pro/incidents/$(date -u +%Y%m%dT%H%MZ)/caddy.log 2>&1

# F. If credentials suspected compromised: rotate via the §6 procedure
# (every secret in /opt/meddoc-pro/.env)
```

After containment, you have time to think. Don't restart traffic until §5 root-cause is identified.

---

## §5 — Investigation

### Audit-log walk-through

```bash
# Suspicious actions in the last 24h, grouped
docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -c "
  SELECT action, count(*), array_agg(DISTINCT \"userId\") as users
  FROM audit_logs
  WHERE timestamp > now() - interval '24 hours'
  GROUP BY action
  ORDER BY count(*) DESC;
"

# A specific user's full timeline
docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -c "
  SELECT timestamp, action, \"targetType\", \"targetId\", \"ipAddress\"
  FROM audit_logs
  WHERE \"userId\" = '<USER_ID>'
  AND timestamp > now() - interval '7 days'
  ORDER BY timestamp DESC;
"

# All access to a specific PHI record
docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -c "
  SELECT timestamp, action, \"userId\", \"ipAddress\"
  FROM audit_logs
  WHERE \"targetId\" = '<VISIT_OR_PATIENT_ID>'
  ORDER BY timestamp ASC;
"
```

### Caddy access-log walk-through

```bash
docker logs meddoc-pro-caddy-1 2>&1 | grep -E ' (5[0-9]{2}) ' | tail -50
docker logs meddoc-pro-caddy-1 2>&1 | jq -r 'select(.status >= 500) | "\(.ts) \(.request.remote_ip) \(.request.uri) \(.status)"' 2>/dev/null | tail -30
```

### Sentry breadcrumbs

Open `sentry.io/quillmd` → filter to the affected user / time window → walk the breadcrumb chain. Pay attention to network requests that succeeded against the AI providers; transcript content fragments may surface in `redactPhi`-imperfect log lines.

### Application logs

```bash
docker logs meddoc-pro-transcribe-md-1 --since 1h 2>&1 | grep -iE 'error|fatal|warn' | tail -50
docker logs meddoc-pro-transcribe-md-worker-1 --since 1h 2>&1 | grep -iE 'error|fatal|warn' | tail -50
```

### Timeline reconstruction

Open `/opt/meddoc-pro/incidents/<timestamp>/timeline.md`. Fill in:

- T+0: detection signal (what fired the alert?)
- T+N: each subsequent observation with timestamp + source

This is the document an HHS auditor wants. Be honest; redactions can come later.

---

## §6 — Notification (HIPAA breach rules)

**Definitions** (45 CFR §164.402):
- "Breach" = unauthorized acquisition, access, use, or disclosure of unsecured PHI that compromises security or privacy
- "Unsecured" = not rendered unusable per HHS guidance (e.g., not encrypted to FIPS 140-2 standards)

**Decision tree:**

| Question | If yes |
|---|---|
| Was PHI involved at all? | Continue → next question |
| Was the PHI encrypted at rest AND in transit AND the encryption key not also compromised? | Probably **NOT** a reportable breach (HHS safe harbor). Document the determination. |
| Is the affected count ≥ 500 individuals? | Notify HHS + media + state AGs **within 60 days** + post on company website |
| Is the affected count < 500? | Annual aggregate notification to HHS by the end of the calendar year + individual notice within 60 days |

**Affected individuals** must be notified within 60 days of discovery via:
1. First-class US mail (or email if individual previously consented to electronic notice)
2. Substitute notice on company website if can't reach 10+ individuals (web posting + toll-free number for ≥90 days)

**Notification template:** `docs/incidents/templates/breach-notification-letter.md` (Phase 7 — to be authored).

**State-level rules** vary; California (CMIA) is stricter than HIPAA on timing for residents. If pilot launches in California, add the state-specific timeline to this runbook.

**Media notification** (≥500 in same state/jurisdiction): prominent media outlets serving the area; press release through normal channels.

**Don't draft the breach notification at 2 AM.** Containment + investigation first; legal counsel reviews the draft before sending.

---

## §7 — Remediation

After root cause is identified:

```bash
# 1. Apply the fix (code change + deploy, or config change, or
#    credential rotation per ROTATION_RUNBOOK.md)

# 2. Verify the fix in production
docker compose ps   # all healthy?
curl -sI https://app.quillmd.com   # returns expected status?

# 3. Re-enable traffic if it was containment-stopped
docker compose start transcribe-md transcribe-md-worker
docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -c "
  ALTER ROLE meddoc CONNECTION LIMIT -1;
"

# 4. Smoke test for 30 minutes; watch Sentry for new error patterns
```

---

## §8 — Post-mortem

Within 72 hours of remediation, write a post-mortem at `docs/incidents/<YYYY-MM-DD>-<short-slug>.md` using the blameless template:

```markdown
# Incident: <short title>

**Severity:** SEV-N
**Detected:** <timestamp> via <signal>
**Resolved:** <timestamp>
**Author:** <name>

## Summary
<2-3 paragraph executive summary>

## Timeline
- T+0 (timestamp): <event>
- T+15min (timestamp): <event>
- ...

## Impact
- Affected users: N
- Affected PHI records: N
- Service downtime: Nm
- Notifications required: yes/no

## Root cause
<technical explanation; trace from symptom back to actual cause>

## Contributing factors
<what made this worse or harder to detect/contain>

## What went well
<honestly, what saved time or limited blast radius>

## What went poorly
<honestly — without blaming individuals>

## Action items
| Owner | Action | Target date |
|---|---|---|
| ... | ... | ... |

## Detection improvements
<how do we catch this earlier next time?>
```

Action items get linked back to `POST_MERGE_TODO.md` so they don't get forgotten.

---

## §9 — Specific scenarios

### A. Suspicious admin activity

`audit_logs` shows `EXPORTED_AUDIT_LOG`, `USER_GRANTED_SUPER_ADMIN`, or `USER_PASSWORD_RESET_TRIGGERED` from a user not expected to be doing admin work.

→ SEV-1 candidate. Containment §4 step C immediately. Investigate § 5 starting from that user's session_logs + IP history.

### B. Worker stuck — visits accumulating

`docker compose ps` shows worker healthy but `bull:transcribe-md:active` queue is growing. Check Redis:

```bash
docker exec meddoc-pro-redis-1 redis-cli LLEN bull:transcribe-md:active
docker exec meddoc-pro-redis-1 redis-cli LLEN bull:transcribe-md:waiting
```

If active is non-zero for >15 min: a job is stuck. The 15-min per-attempt timeout (`JOB_TIMEOUT_MS`) should kill it; if it doesn't, recreate the worker:

```bash
docker compose up -d --force-recreate transcribe-md-worker
```

Investigate the stuck visit's `transcribe_visits.id` — usually a Deepgram or Anthropic provider issue.

### C. DB connection storm

Postgres logs flood with `FATAL: too many connections for role "meddoc"`. The default max is 100. If the app suddenly opens >100 connections, something is leaking pools.

```bash
# See current connection count + sources
docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -c "
  SELECT application_name, state, count(*)
  FROM pg_stat_activity
  GROUP BY application_name, state ORDER BY count(*) DESC;
"

# Kill idle connections to recover
docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -c "
  SELECT pg_terminate_backend(pid) FROM pg_stat_activity
  WHERE state = 'idle' AND query_start < now() - interval '5 minutes';
"
```

### D. Caddy 5xx storm (upstream timeout)

Caddy returns 502/504 because transcribe-md is slow. Check transcribe-md latency:

```bash
docker logs meddoc-pro-transcribe-md-1 --since 5m 2>&1 | grep -E 'POST|GET' | tail -20
```

If consistent slow Anthropic/Deepgram calls: provider issue, page their status page. If consistent slow DB queries: connection pool exhausted, see §C above.

---

## §10 — When this runbook isn't enough

Escalate to:

1. **Phase 6.2 backup restore** — see `docs/RUNBOOK_OFFSITE_BACKUP.md`
2. **Postgres single-user mode recovery** — see `docs/runbooks/postgres-recovery.md` §3
3. **VPS provider** (Zap Hosting) — for hardware/network issues
4. **Outside legal counsel** — for breach-notification drafting
5. **Anthropic / OpenAI / Deepgram support** — for AI provider escalation if their service is the root cause
