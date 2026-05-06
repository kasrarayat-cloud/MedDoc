# Data sources — HIPAA Compliance Auditor

> **Status: design only.** Schema drift since this doc was
> written is expected; activation includes a fresh schema
> sanity check (Phase 0 in `methodology.md`) before any
> phase runs. Stricter PHI handling than
> `ai-pipeline-auditor`: no content reads, bucketed counts,
> short-hashed IDs in reports.

The auditor is **read-only** across these sources. Adding a
new source is a deliberate change — must land here in the
same PR that adds the corresponding audit phase.

## §1 — Postgres tables (`meddoc-pro-postgres-1`)

### `audit_logs` (primary surface)

The §164.312(b) mechanism. Read on Phases 1, 2, 4.

| Column | Why | PHI consideration |
|---|---|---|
| `id` | Identity for cross-row joins | Safe |
| `userId` | Per-account rollups | Safe (UUID) |
| `userEmailSnapshot` | Detect orphan-actor patterns | **Email is identifier** — auditor reads only the **domain** for cross-tenant detection, never logs the local part |
| `practiceId` | Per-practice rollups | Safe (string ID) |
| `action` | The §164.312(b) signal | Safe (enum) |
| `targetType` + `targetId` | What the action affected | Safe (type + UUID); IDs short-hashed in reports |
| `metadata` (JSON) | Per-action structured fields | **READS KEYS ONLY**; never logs values. Per `audit.ts` IMPORTANT comment, emit sites use field NAMES not values |
| `ipAddress` | Cross-tenant + bot-detection signals | **PII** — auditor reads /24 prefix only, never logs full IP |
| `userAgent` | Bot-detection | Safe |
| `success` | Failure-rate computation | Safe |
| `errorCode` | Structured failure category | Safe (enum) |
| `timestamp` | Monotonicity + retention checks | Safe |

The auditor never reads:

- Full IP (only /24 prefix for log-rate computations)
- Email local part (only domain)
- Any free-text in metadata values

### `users`

Account state. Read on Phase 1 + 4.

| Column | Why |
|---|---|
| `id` | Identity |
| `email` | **Domain only** (PII) |
| `role` | Inactive-admin + SUPER_ADMIN-list checks |
| `practiceId` | Cross-tenant check anchor |
| `lastLogin` | Inactive-account detection |
| `mfaEnabled` | §164.312(d) MFA-on-admin check |
| `createdAt` / `deletedAt` | Lifecycle anchor |
| `passwordChangedAt` | §164.312(d) auth hygiene |

Never reads: `passwordHash`, `mfaSecret`, security questions
(if present). These are at rest in DB but never in audit
output.

### `user_sessions`

Active session state. Read on Phase 1 + 4.

| Column | Why |
|---|---|
| `id` | Per-session identity |
| `userId` + `practiceId` | Cross-tenant scoping check |
| `expirationAt` | Stale-session cleanup verification |
| `createdAt` | Stale-session window |
| `ipAddress` | /24 prefix only |
| `userAgent` | Bot-detection signal |

Never reads: session token / cookie value (if present).

### `transcribe_visits` + `transcribe_md_patients`

Structural reads only — column existence, NOT NULL
constraints, count bucketing. Read on Phase 2 + 3 + 8.

| Read | What |
|---|---|
| `information_schema.columns` | Constraint integrity over time |
| `pg_stat_user_tables.n_tup_upd` | Audit-log immutability check (audit_logs specifically) |
| `count(*)` filtered by status | **Bucketed before report** |
| `signedAt` (existence check only) | Phase 3 transcript-immutability anchor |
| Per-visit `audit_logs` join | Phase 2 PHI-read coverage |

Auditor never reads: `transcriptText`, `transcriptRaw`,
`soapDraft`, `soapFinal`, `rawTextInput`, `audioKey`,
patient `name`, patient `dateOfBirth`, patient `mrn` (if
populated). Not even via JSON paths or computed columns.

### `_prisma_migrations`

Schema version + applied dates. Read on Phase 0 + 3.

| Column | Why |
|---|---|
| `migration_name` | Detecting recent migrations for schema-drift detection |
| `finished_at` | Timeline anchor |
| `rolled_back_at` | Integrity signal — non-NULL means schema state may not match expectations |

## §2 — Operator-maintained docs

These are filesystem reads. Each is the canonical source for
the corresponding audit signal.

### `docs/compliance/baas.md` (vendor BAA tracker)

Used by Phase 7. Expected schema (markdown table):

```
| Vendor | Status | Executed | Expiration | Vendor-managed encryption | Notes |
|---|---|---|---|---|---|
| Anthropic | EXECUTED | 2026-NN-NN | 2027-NN-NN | yes (BAA covers their infra) | ... |
| OpenAI | EXECUTED | ... | ... | ... | ... |
| Deepgram | EXECUTED | ... | ... | ... | ... |
| Sentry | PENDING | n/a | n/a | n/a | DSN env empty until executed |
| Resend | EXECUTED | ... | ... | ... | ... |
| Backblaze | EXECUTED | ... | ... | ... | ... |
| MinIO (self-hosted) | n/a | n/a | n/a | yes (self-hosted, SSE-S3 PR-M) | not a vendor relationship |
```

Status values the auditor recognizes: `EXECUTED`, `PENDING`,
`EXPIRED`, `n/a`. Anything else is a SCHEMA_GAP at the doc
level (operator must use the standard vocabulary).

The auditor never modifies this file — operator-maintained.

**Pre-activation backlog item:** the doc doesn't currently
exist in canonical form. It's referenced in
`docs/COMPLIANCE_REGISTER.md` and `docs/runbooks/sentry-setup.md`
but not consolidated. Activation Step 1 in
`activation-criteria.md` is to land this doc.

### `docs/compliance/contingency-plan.md`

Backup runbook + last-restore-drill date. Phase 7 reads:

```
Last full restore drill: 2026-NN-NN
Drill RPO observed: <minutes>
Drill RTO observed: <minutes>
Backup verifications since last drill: N
```

If the doc doesn't exist or the date isn't parseable, P2
Phase 7 finding "contingency-plan.md missing or malformed."

### `docs/compliance/workforce-training.md`

Per-person training log. Phase 7 reads:

```
| User email domain | Role | Last training | Topic |
|---|---|---|---|
| @ashtechgroup.com | SUPER_ADMIN | 2026-NN-NN | HIPAA refresher |
| ... |
```

Email is **domain-only** even in this doc (operator
discipline; auditor verifies and surfaces if a full email
appears).

### `docs/compliance/super-admins.md`

Allowlist of expected SUPER_ADMIN accounts. Phase 1 reads
this list + cross-checks against the live `users` table.
Any live SUPER_ADMIN not in the doc is a P1 finding.

### `docs/runbooks/incident-response.md`

Phase 7 reads the "last incident or drill exercise" entry.

### `docs/COMPLIANCE_REGISTER.md`

The umbrella compliance status doc. Phase 7 reads as
context for finding-drilldowns; doesn't drive findings
directly (it's an aggregator, not a source-of-truth for
each axis).

## §3 — Container env + config

These are not files in the repo; they're live state of the
production cluster.

### Caddyfile (in `meddoc-pro-caddy-1` container)

Phase 5 reads:

- HTTP-to-HTTPS redirect rule
- HSTS header settings (`Strict-Transport-Security`)
- Per-host TLS config
- Snippet imports (security headers)

Read via `docker exec meddoc-pro-caddy-1 cat /etc/caddy/Caddyfile`.

### Live cert state

Phase 5 + 8 reads via `openssl s_client -connect
app.quillmd.com:443` + parses the negotiated version, cert
expiration, cipher.

### MinIO SSE config

Phase 8 reads via `docker exec meddoc-pro-minio-1 mc encrypt
info local/<bucket>` per PHI-bearing bucket. Output parsed
to confirm SSE-S3 is the active mode + the named master key
matches `quillmd-master-key-1` (PR-M).

### Postgres encryption posture

Phase 6 reads `df /var/lib/postgresql/data/pgdata` (inside
the postgres container) + `lsblk` on the host (via host
shell command if accessible — Lead's `claude` user can run
this) to confirm the data directory lives on a LUKS-mapped
device.

### Backup destination posture

Phase 6 reads:

- Postgres backup sidecar config (compose env)
- Backblaze offsite-sync config (`infra/backup-offsite-sync.sh`)
- age-encryption config (the public key path, the key
  rotation marker)

## §4 — What the auditor does NOT read

Beyond the per-table exclusions above:

- **`apps/meddoc-pro` tables** — out of scope per memory
  #9. Even though the same Postgres instance hosts both
  apps' data, the auditor's queries explicitly exclude
  `apps/meddoc-pro` tables (CRM `Patient`, etc.) by
  whitelist (auditor lists tables it READS rather than
  blacklisting tables it skips).
- **`auth_tokens`** — auth-side; out of pipeline scope and
  not §164.312-bearing for this auditor's purpose
- **`account_deletions`** — Phase 7 reads count + age but
  not the per-row metadata (which may include reason free
  text)
- **`doctor_edit_patterns`** — Phase 14.1 captured-edit-
  pattern table. Embeddings + edit text contain PHI; out
  of scope
- **`drchrono_*` tables** — DrChrono sync surface; CRM
  scope
- **`ai_calls.*`** prompt body / response body fields — the
  auditor is interested in cost rollups and provider
  identity (to cross-check BAAs), not call content. Cost
  rollups are read by `ai-pipeline-auditor`; this auditor
  reads only `ai_calls.provider` for the BAA cross-check
  (Phase 7)

## §5 — Querying conventions

- **Connection.** Auditor connects via the `DATABASE_URL`
  used by other agents pre-activation. At activation, a
  Postgres SELECT-only role
  (`hipaa_compliance_auditor`) is created (defense-in-
  depth — backlog item in `activation-criteria.md`).
- **Time zone.** UTC.
- **Bucketing.** Counts > 10 are bucketed: 1–10, 11–100,
  101–1000, 1000+. Exact counts only ever appear in operator-
  only drilldown appendix, never in the headline summary.
- **Visit-ID hashing.** Reports show last-6 chars of cuids.
  Full IDs only in operator-only drilldown.
- **No PHI even via metadata keys.** When the auditor reads
  `audit_logs.metadata`, it iterates KEYS not VALUES. Any
  finding that references metadata uses key names only.

## §6 — Compliance + PHI handling

The auditor's contract is **structural-only reads with
report-level redaction**. Enforced by:

1. Query bodies — every SELECT names columns; reviewers can
   audit what's read.
2. Report-rendering — bucketing + ID-hashing is in the
   reporter, not at the query layer.
3. Activation review — operator reviews every script
   before adding `SKILL.md`.

A leaked HIPAA Compliance Auditor report should not contain
identifiers — the worst case it should contain is "P1
finding: AuditAction `LOGIN_FAILED` has 0 rows in last 30d
on practice ID prefix `clinic_`." Even at that level the
ID is structural metadata.

The auditor's own emit (`COMPLIANCE_AUDIT_RUN_COMPLETED`,
`COMPLIANCE_FINDING_SURFACED`) is part of its §164.312(b)
self-trace — see methodology Phase 2 self-emission check.
