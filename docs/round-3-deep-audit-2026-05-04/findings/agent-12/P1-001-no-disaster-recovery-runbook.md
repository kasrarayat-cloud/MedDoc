---
id: A12-P1-001
title: No consolidated disaster-recovery runbook; scenarios scattered, RTO/RPO not enumerated per scenario
severity: P1
domain: docs/disaster-recovery
---

# Issue

A QuillMD operator at 02:00 on a Sunday cannot find a single document that says "VPS lost — do these 9 steps", "Postgres data corrupt — restore from backup, here is the SQL", "Backblaze compromised — rotate keys, re-encrypt, here are the file paths", "MinIO bucket nuked — re-upload from local /backups", "Redis lost — what jobs are at risk", "DNS hijacked — failsafes". DR fragments exist scattered across at least six documents, none of them comprehensive, and the consolidation does not exist. RTO/RPO is stated for one scenario only (VPS lost via Phase 6.2 strategy) — no other scenario has documented recovery objectives.

# Evidence

The DR pieces actually present:

- `docs/phase-6.2-backup-strategy.md` §"Disaster scenarios" covers exactly **2 of the 6** in the audit checklist: VPS lost (Scenario 1) and B2 compromised (Scenario 2). Scenario 3 ("Private key lost") is restoration impossibility, not DR. Scenario 4 ("Both lost") is total-loss documentation.
- `docs/RUNBOOK_OFFSITE_BACKUP.md` §D.4 has a 3-question Q&A with shape similar to DR but limited to the offsite-backup angle.
- `docs/DEPLOYMENT_RUNBOOK.md` §3 (Rollback) and §4 (Restore from backup) cover application-rollback and Postgres-restore — strictly within deploy operations, not full disaster.
- `LAUNCH_READINESS.md:160-194` "Rollback plan" three-tier — single container hung / recent commit broke prod / DB corrupted. Tier 3 covers Postgres restore. Does not cover: MinIO loss, Redis loss, DNS hijack, B2 compromise, VPS total loss.
- `KASRA_HANDOFF.md` §E echoes the same three-tier rollback. Same gaps.

The audit checklist scenarios and where each is currently documented:

| Scenario | Documented? | Where |
|---|---|---|
| VPS lost (entire host gone) | ⚠ Partial | `phase-6.2-backup-strategy.md` Scenario 1 — high-level only, no step-by-step |
| Postgres data corrupt (last-known-good restore) | ✅ | `DEPLOYMENT_RUNBOOK.md` §4 + `LAUNCH_READINESS.md` Tier 3 |
| Backblaze B2 compromised | ⚠ Partial | `phase-6.2-backup-strategy.md` Scenario 2 — no step-by-step for re-encryption + key rotation |
| MinIO bucket nuked | ❌ Missing | nowhere — POST_MERGE_TODO §22 mentions a "MinIO restore drill" as a deferred follow-up |
| Redis lost (jobs lost?) | ⚠ Implicit | `phase-6.2-backup-strategy.md` "What's NOT backed up" says BullMQ regenerates; no procedure for an active-job-loss event |
| DNS hijacked | ❌ Missing | nowhere — POST_MERGE_TODO §23 covers an *accidental* DNS misconfiguration, not a hijack |

Per-scenario RTO/RPO:

| Scenario | RTO documented? | RPO documented? |
|---|---|---|
| VPS lost | "under 2 hours" (`phase-6.2-backup-strategy.md`) | 24h |
| Postgres corruption | not stated | implicit "last midnight" via `LAUNCH_READINESS.md` |
| B2 compromised | not stated | not stated |
| MinIO nuked | not stated | not stated |
| Redis lost | not stated (jobs auto-retry) | not stated |
| DNS hijacked | not stated | not stated |

Note: the directory `docs/disaster-recovery/` does not exist; `docs/dr/` does not exist; `docs/incidents/` does not exist (per A12-P0-002 finding).

# Risk

- **Time-to-recovery under stress**: the difference between a 90-minute restore (per the Phase 6.2 RTO) and a 6-hour restore is whether the operator has a runbook open in front of them or is improvising.
- **Audit evidence**: an OCR examiner asks for the DR procedure as part of any §164.308(a)(7) review. "We have a Phase 6.2 strategy document that covers two scenarios" is not a DR plan. §164.308(a)(7)(ii)(B) requires a Disaster Recovery Plan; §164.308(a)(7)(ii)(C) requires an Emergency Mode Operation Plan. Neither exists today.
- **MinIO is unrecoverable today**: the actual recovery procedure for a nuked bucket is undocumented. Even though the offsite backup script exists, no operator can confidently restore from it without a written drill.
- **DNS hijack response is novel — practiced or not**: §23 of POST_MERGE_TODO documents a benign DNS misconfiguration. A malicious hijack (registrar account compromise, BGP attack on the apex) requires different decisions: who to call at the registrar, how to verify the legitimate owner, how to intercept TLS-stripping attempts. None documented.

# Recommended fix

Create `docs/DISASTER_RECOVERY.md` as a single landing-pad with one section per scenario. Each section format:

```
## Scenario N: <name>
**Detection**: how an operator notices this is the failure mode (specific signals + dashboard panels).
**RTO**: <objective>
**RPO**: <objective>
**Containment**: first-15-minute steps to stop the bleed.
**Recovery**: numbered steps to restore service + restore data.
**Verification**: smoke tests confirming recovery (per `LAUNCH_READINESS.md` §C shape).
**Root-cause attribution**: log + audit-log + B2-file-info evidence to capture for post-mortem.
```

Six scenarios at minimum:

1. **VPS lost** — provision new VPS (Ubuntu cloud-init script in the runbook), pull repo, restore Postgres from latest B2 blob (link to existing C.1-C.8 of `RUNBOOK_OFFSITE_BACKUP.md`), restore MinIO from latest B2 blob (currently undocumented — see A12-P1-002), `docker compose up -d`, repoint DNS at new IP. RTO target ≤2h.

2. **Postgres data corrupt** — drain web tier, identify last-known-good dump in `/opt/meddoc-pro/backups/` (sidecar 7+4+6 retention), restore via `gunzip | psql` per `LAUNCH_READINESS.md` Tier 3, re-run db-migrate to bring schema forward, smoke. RTO ≤30 min, RPO ≤24h.

3. **Backblaze B2 compromised** — rotate B2 application key per `RUNBOOK_OFFSITE_BACKUP.md` §A.3, evaluate version-history restoration via Backblaze support, re-encrypt local dumps with rotated age key (only if private key compromise is also suspected), update `.env`, recreate `postgres-backup` sidecar.

4. **MinIO bucket nuked** — operator has no procedure today. Step-by-step: `b2 ls` for latest `meddoc-pro/minio/` blob, decrypt with offline private key, untar, `mc mirror` into a fresh local MinIO bucket on a non-prod port, sample-verify with a known-good audio file, then promote (this is the `restore-drill.sh` shape but for MinIO and ending in production cutover).

5. **Redis lost** — accept session-cookie regeneration (every active user re-logs), accept BullMQ in-flight job loss with the safety net that `transcribe_visits.status=PROCESSING` rows older than 30 min get stuck-job UI banners (T-M16.4) and can be re-queued via the existing `/api/visits/[id]/retry` route. Document a SQL query that finds stuck visits and a script that batch-retries them.

6. **DNS hijacked** — registrar emergency contact (name + phone + post-2FA-recovery procedure stored in compliance vault, NOT in repo), Caddy auto-TLS rotation (the cert auto-renews; the issuer pin and HSTS prevent some downgrade attacks), notification to all logged-in users via in-app banner if the domain has flipped. Pre-document: Cloudflare/Namecheap registrar contact procedure, AAAA + CAA record state.

For each scenario, populate RTO/RPO with a concrete number derived from the existing backup cadence + container start times. The Phase 6.2 strategy doc can keep its strategic-overview shape; the DR runbook is the procedural sibling.

Cross-link from `docs/HIPAA_COMPLIANCE.md` (add §164.308(a)(7)(ii)(B) and §164.308(a)(7)(ii)(C) rows).
