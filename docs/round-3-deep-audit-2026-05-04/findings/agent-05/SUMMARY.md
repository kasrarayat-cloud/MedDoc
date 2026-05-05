# Agent 05 — PHI & HIPAA Technical Safeguards · Summary

## Severity counts
**P0: 4 · P1: 5 · P2: 2 · P3: 1 · Total: 12**

## Top 3 findings
1. **P0-001/P0-002 — Encryption-at-rest is incomplete.** MinIO audio bucket has NO SSE and lives on `/dev/sda2` (root, no LUKS); only `/mnt/pgdata-encrypted` is protected. Daily `*.sql.gz` Postgres backups in `/opt/meddoc-pro/backups/` are plaintext gzip on the same root disk. `HIPAA_COMPLIANCE.md` h8 only covers live Postgres; MinIO + backup dirs are silent gaps.
2. **P0-004 — Every PHI-READ endpoint emits zero audit rows.** `GET /api/visits/[id]`, `GET /api/patients/[id]`, patient/visit list endpoints, `GET /api/visits/[id]/dictation/audio`, and the four SSR pages (`/visits`, `/visits/[id]`, `/patients`, `/patients/[id]`) read PHI without writing AuditLog. Schema comment line 6 mandates audit on every read; code violates it. §164.312(b) minimum-control failure.
3. **P0-003/P1-004 — Backup encryption-key chain is fragile.** `postgres-backup/postscript.sh` ships PLAINTEXT pg_dumps to a remote S3 bucket if `REMOTE_BACKUP_S3_*` env is populated (one env edit away from active). `backup-offsite-sync.sh` does not validate the age public-key fingerprint AND has a fall-through that auto-generates a NEW keypair on the VPS if `/etc/meddoc/offsite-backup-public.age` is missing — defeating the offline-key-custody model.

## Coverage
Every audit emit point in `apps/transcribe-md/src/`; every PHI GET/POST under `/api/visits` and `/api/patients`; all four SSR PHI pages; `AuditLog` schema (zero hash chain, zero DB role enforcement); Caddyfile, docker-compose storage, all `infra/*` backup scripts, redactPhi + Sentry beforeSend, PDF/DOCX metadata, BullMQ payload, browser storage.

## Positives
- PHI-write audit coverage is comprehensive (Phase 17 closed many gaps).
- PDF + DOCX metadata are PHI-free with hardcoded "QuillMD" Author/Creator (Round-1 P1-001 fix held in both formats).
- Sentry has redactPhi `beforeSend` plus `tracesSampleRate=0` + `sendDefaultPii=false` + DSN-required gating.
- Worker stdout wraps every error in `redactPhi(err.message)`.
- Zero `localStorage`/`sessionStorage`/`IndexedDB` usage in the SPA.
- BullMQ payload is `{visitId, userId}` only — no transcript in Redis.
- Caddy enforces HSTS + CSP on all hostnames with admin-host explicit allowlist + 404-default.
- Audit-log SSE fan-out is fire-and-forget with a 100ms timeout bound.

## BAA gap list

| Vendor | Status |
|---|---|
| Anthropic | NOT YET |
| OpenAI | NOT YET |
| Deepgram | NOT YET |
| Sentry | NOT YET |
| Resend | MISSING FROM MATRIX |
| Backblaze B2 | MISSING FROM MATRIX |
| Dropbox (legacy) | VERIFY |
| DrChrono | VERIFY |
| Zap Hosting (VPS) | VERIFY |
| MinIO/Postgres/Redis (self-hosted) | N/A — covered under VPS host BAA |

## Cross-domain hooks
- **Agent 02 (auth)** — P1-002 (7-day session + no idle timeout) — `UserSession.lastUsedAt` reusable for the idle layer.
- **Agent 12 (DR runbook)** — P1-004 fingerprint and P0-003 unencrypted postscript; `restore-drill.sh` readiness depends on the fingerprint gap.
- **Agent 11 (logging)** — Sentry redactPhi audited here; `lib/log.ts` wrapper does NOT auto-redact, callsite-by-callsite review needed.
- **Agent 07 (network/TLS)** — P1-005 intra-Docker plaintext (Postgres/Redis/MinIO) overlaps with the TLS audit; combined Caddy-PKI mTLS remediation possible.
- **Agent 12 (vendors)** — P1-001 + P3-001 BAA matrix overlap with the documentation gap.
- **Agent 09 (data retention)** — `/api/patients/[id]/export` is doctor-scoped only; HIPAA 30-day right-of-access discussion needed.
