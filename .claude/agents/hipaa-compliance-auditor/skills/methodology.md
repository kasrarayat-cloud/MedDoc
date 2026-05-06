# Methodology — HIPAA Compliance Auditor

> **Status: design only.** Concrete query bodies + per-phase
> thresholds are deferred to activation. This doc names the
> methodology + the rule citations; the implementation
> happens at activation time.

## Operating principle

Read-only against system state + `audit_logs` + filesystem +
container env + `docs/compliance/*.md`. Never reads PHI
content. Stricter than `ai-pipeline-auditor`: even
metadata-adjacent values like row counts get bucketed (1–10,
11–100, 101–1000, 1000+) before appearing in reports. Visit
IDs are short-hashed (last 6 chars) so reports themselves
carry no identifiers.

Each phase produces one of:

- **OK** — observed value within expected band
- **DRIFT** — observed value outside expected band; severity
  per `finding-classes.md`
- **NO_DATA** — insufficient samples to compute (e.g. fewer
  than 3 active accounts when phase 1 runs pre-pilot)
- **SCHEMA_GAP** — the column / table / file the phase
  depends on doesn't exist or is unpopulated; blocks the
  phase

Only DRIFT counts as a finding. NO_DATA is informational;
SCHEMA_GAP is itself a finding (the auditor's data contract
broke).

## Severity reminder

Severities (P1/P2/P3) carry an extra dimension here vs.
the other two agents: **regulatory exposure**. A P1 in this
auditor isn't just "production risk" — it's also "this
might trigger a breach-notification obligation under
§164.404 if confirmed." Each P1 finding includes an
`ocr_reportable_candidate` boolean so the operator + counsel
know to consider it.

## 10 audit phases

Run in order. Later phases depend on earlier ones (Phase 0
gates everything; Phase 9 aggregates the rest), so a
SCHEMA_GAP in Phase 0 stops the run.

### Phase 0 — Schema sanity

No HIPAA citation. Confirms the auditor's data sources
still exist where it expects. Per-table presence + per-column
presence checks; per-file presence for
`docs/compliance/*.md`; container env + Caddyfile
parse-ability checks.

Phase 0 emits `schema-ok` events per source or one
SCHEMA_GAP finding per missing source.

### Phase 1 — §164.312(a)(1): Access control

The §164.312(a) rule mandates "technical policies and
procedures … to allow access only to those persons or
software programs that have been granted access rights as
specified in §164.308(a)(4)." The auditor's signals:

**§164.312(a)(1)(i) — Unique user identification.**
Every account has a unique `userId`. Verified at
the database constraint level (UNIQUE on `users.id`); a
violation here means the schema itself broke.

**§164.312(a)(1)(ii)(A) — Emergency access.**
Confirm an "emergency access" account or procedure exists.
Currently captured in `docs/compliance/contingency-plan.md`;
auditor reads the doc + flags staleness.

**§164.312(a)(1)(ii)(B) — Automatic logoff.**
Inspect session-timeout config + verify `user_sessions`
rows older than the configured TTL are being cleaned up
(i.e. the cleanup BullMQ job is healthy). Stale sessions
older than 2× the TTL are a P2 cleanup-stuck signal.

**Cross-tenant session bleed.**
For every active session, verify the session's
`practiceId` matches the user's `practiceId` at the time of
issue. A mismatch (session for practice A still authorized
for practice B's data) is a P1 access-control breach.

**Inactive accounts.**
Accounts with `lastLogin` older than 90 days that still
hold credentials are review candidates (P2). For
SUPER_ADMIN accounts, the threshold tightens to 30 days
(P1) — admin attack surface should be minimized.

**SUPER_ADMIN list.**
Compare the live SUPER_ADMIN list against
`docs/compliance/super-admins.md` (operator-maintained).
Any addition without a `USER_GRANTED_SUPER_ADMIN` audit row
is a P1 (admin expansion without audit trail).

### Phase 2 — §164.312(b): Audit controls

The §164.312(b) rule mandates "hardware, software, and/or
procedural mechanisms that record and examine activity in
information systems that contain or use electronic protected
health information." The auditor's signals:

**Per-action emission check.**
For every value in the `AuditAction` enum, count rows in
`audit_logs` over the last 30 days. Zero rows → P1 finding
(action is wired but never fires; the §164.312(b)
mechanism is incomplete). Exception list maintained for
actions that fire only in rare conditions
(e.g. `EMERGENCY_ACCESS_GRANTED`).

**PHI-read audit coverage.**
Cross-reference the route map
(`apps/transcribe-md/src/app/**/page.tsx` for PHI-bearing
routes) against `VIEWED_*` action emits in `audit_logs`. Any
PHI-bearing route without a corresponding `VIEWED_X` row
emit on render is a P1 §164.312(b) gap.

**Timestamp monotonicity.**
Per `targetId` (visitId, patientId, userId), assert
`audit_logs.timestamp` is monotonic. Out-of-order writes
indicate clock skew, manual row injection, or replication
lag — each is a P2 anomaly worth investigating.

**Retention.**
HIPAA §164.316(b)(2)(i) requires audit-log retention for 6
years. Compute `MAX(timestamp) - MIN(timestamp)` from
`audit_logs`. Surface the oldest row's age. A P2 finding
fires when oldest row age approaches the retention edge
(>5.5 years) so the operator reviews retention policy
before rows age out via a routine cleanup.

**Self-emission check.**
The auditor itself MUST emit an audit row when it runs
(action: `COMPLIANCE_AUDIT_RUN_COMPLETED` — to be added at
activation). If the auditor's own emit fails, that's the
strongest possible §164.312(b) failure — surface as P1
SCHEMA_GAP.

### Phase 3 — §164.312(c)(1): Integrity

The §164.312(c)(1) rule mandates "policies and procedures to
protect electronic protected health information from
improper alteration or destruction." The auditor's signals:

**Schema-level constraints.**
Compare the live `information_schema` against the Prisma
schema definitions for PHI-bearing columns. A previously-
NOT-NULL column that became NULL-able is a P2 schema
regression worth investigation.

**Transcript immutability post-sign.**
For visits with `signedAt` timestamps, verify
`transcriptText` and `transcriptRaw` are unchanged after
sign-off. The current schema doesn't enforce this; the
auditor reads the migration history + flags any column
mutation against signed visits as a P1 integrity gap.

**SOAP version monotonicity.**
For each visit's audit trail, `soapVersion` should never
decrement. A decrement is a P2 integrity concern (likely a
race condition or manual rollback that should leave a
trail).

**Audit-log immutability.**
`audit_logs` rows should never be UPDATEd after insert.
Verify via `pg_stat_user_tables`'s `n_tup_upd` counter for
the table — non-zero is a P1 integrity finding (audit logs
should be append-only; UPDATEs invalidate the §164.312(b)
mechanism).

### Phase 4 — §164.312(d): Person or entity authentication

The §164.312(d) rule mandates "procedures to verify that a
person or entity seeking access … is the one claimed." The
auditor's signals:

**MFA on admin accounts.**
Every SUPER_ADMIN + ADMIN account should have `mfaEnabled =
true`. Any without is a P1 finding.

**Password reset audit pairs.**
For every `PASSWORD_RESET_REQUESTED` audit row, expect a
matching `PASSWORD_RESET_COMPLETED` row within 24h OR an
expiration of the reset token. A request with no
completion AND no token expiration after 24h is a P2
(suspicious — partial flow).

**Session expiration enforcement.**
Verify the `user_sessions.expirationAt` is being honored at
the application layer; sample sessions with
`expirationAt < now()` should not be authenticating
requests (verifiable via the session-cleanup job's audit
emit).

**Failed-login throttling.**
Confirm `LOGIN_FAILED` audit rows from the same IP within a
short window trigger the rate-limit (verify by inspecting
the 429-response audit emit). Absence of throttling is a
P2 hardening gap.

### Phase 5 — §164.312(e)(1): Transmission security

The §164.312(e)(1) rule mandates "technical security
measures to guard against unauthorized access to electronic
protected health information that is being transmitted." The
auditor's signals:

**HTTPS-redirect.**
Probe `http://app.quillmd.com/` and assert a 301/302/308
to `https://`. Direct response on 80 without redirect is a
P1 plaintext-transmission finding.

**HSTS headers.**
Inspect the response from `https://app.quillmd.com/` for
`Strict-Transport-Security`. Missing or short max-age is a
P2 hardening gap.

**TLS version.**
Run `openssl s_client -connect app.quillmd.com:443` and
parse the negotiated version. Below TLS 1.2 is a P1
weak-TLS finding.

**Certificate freshness.**
Cert expiration < 30 days is a P2 hardening gap; < 7 days
is P1.

**WebSocket transmission.**
If/when scribe-ws sidecar is active, confirm it's WSS-only
(the protocol scheme + Caddy upstream config). Plain ws://
is a P1 transmission gap.

### Phase 6 — §164.310: Physical safeguards (config attestation)

§164.310 covers facility access, workstation security, and
device/media controls. The agent isn't on the hardware so
it can't directly verify physical safeguards — what it CAN
verify is **config attesting to physical posture**. Each of
the following is informational (P3) rather than a finding,
because hardware verification lives outside the agent's
scope:

- **MinIO SSE-S3** active on PHI-bearing buckets (bucket
  default-encryption flag via `mc encrypt info`)
- **Postgres on encrypted volume**: read `df` + `lsblk`
  output to confirm `/var/lib/postgresql/data/pgdata` lives
  on a LUKS-mapped device (Phase 6.1)
- **Backups encrypted**: verify backup destination + encryption
  config (Backblaze bucket + age-encryption sidecar)
- **Volume retention**: backup retention policy matches the
  documented one (`docs/compliance/contingency-plan.md`)

These surface in reports under "Physical safeguards
(attested)" rather than under §164.312 findings.

### Phase 7 — §164.308: Administrative safeguards

The §164.308 rule covers security management process,
assigned security responsibility, workforce security,
information access management, security awareness +
training, security incident procedures, contingency plan,
evaluation, and BAAs. The auditor's signals:

**Vendor BAAs.**
Read `docs/compliance/baas.md` (operator-maintained
table: vendor / status / executed-date / expiration-date).
Surface findings:
- BAA expired (expiration < today) → P1
- BAA expiring within 60 days → P2
- BAA missing for a vendor in active use (cross-check
  `ai_calls.provider` + storage destinations) → P1
- BAA in `PENDING` state for a vendor with active usage →
  P1

**Contingency plan freshness.**
Read `docs/compliance/contingency-plan.md` for last
restore-drill date. > 90 days since last drill is P2. > 180
days is P1.

**Workforce training records.**
Read `docs/compliance/workforce-training.md`. Flag stale
entries (training older than 12 months for any active user).

**Security incident log.**
Read `docs/runbooks/incident-response.md` for last incident
or drill exercise. Stale > 12 months is P2 (the muscle
memory atrophies).

### Phase 8 — Encryption posture (operational hardening)

Not a HIPAA citation per se — encryption-at-rest is required
for the §164.312 implementation specifications but the
specific posture is operational. Audits:

- MinIO SSE-S3 bucket-level default on every PHI-bearing
  bucket
- Postgres data directory on LUKS-encrypted volume
- Backup destination encryption (Backblaze + age)
- TLS cert + version (cross-references Phase 5 for
  reporting consistency)
- Sentry DSN posture (DSNs empty until BAA per
  `docs/runbooks/sentry-setup.md`; populated DSN without a
  BAA is a P1 §164.308 vendor-BAA finding)

### Phase 9 — Reporting

Aggregate all phase findings by:

1. Severity (P1 / P2 / P3 / informational)
2. HIPAA section (§164.308 / §164.310 / §164.312 /
   operational-hardening)
3. Phase

Generate `docs/compliance-audit-reports/<UTC-timestamp>.md`
with:

- Cover page: run timestamp, host SHA, total findings by
  severity + section
- One-page operator summary: P1 findings only, with
  closure criteria
- Per-section drilldowns
- Appendix: NO_DATA + SCHEMA_GAP entries
- Appendix: phases that ran in partial coverage (e.g. "Phase
  2 ran with NO_DATA: only 3 visits in window")

Reports retain forever — they're the auditor's evidence
trail. Compliance reviewers ask for them; the operator
points at the directory.

## Run cadence

**Nightly via cron** at a low-traffic hour (e.g. 03:30 UTC,
matching the existing T-M17.3 stale-visit-cleanup cron).
Cron wiring is part of the activation runbook
(`activation-criteria.md` Step 5).

The auditor's run takes ~minutes (read-only queries, no AI
calls). It does not need a separate container; the
operator runs it ad-hoc via the same pattern as other
scripts (one-off Node script triggered by Lead).

## Querying conventions

- All queries explicit-column SELECT (no `SELECT *`); reviewers
  can audit what's read
- All timestamps UTC
- `transcribe_visits.deletedAt` IS NOT NULL filter applied to
  every query that touches that table
- Row counts bucketed before appearing in reports (1–10,
  11–100, 101–1000, 1000+) — knowing exact counts per
  practice is itself PHI-adjacent metadata
- Visit IDs short-hashed (last 6 chars) in report bodies; full
  IDs only in operator-only drilldown appendix

## What the methodology explicitly does NOT do

- **Read PHI content.** Stricter than ai-pipeline-auditor.
- **Make breach-notification decisions.** Flags candidates
  (`ocr_reportable_candidate: true`); the operator + counsel
  decide.
- **Modify state.** Read-only across the board. The auditor
  itself emits a `COMPLIANCE_AUDIT_RUN_COMPLETED` row + a
  per-finding `COMPLIANCE_FINDING_SURFACED` row to provide its
  own §164.312(b) audit trail, but that's the only writes.
- **Perform penetration testing.** TLS-version probing is
  pure observation, not active probing of weakness.
- **Enforce remediation.** Findings flow to a report; the
  operator decides what to do.

## Open questions for activation

Resolved when the operator reaches the activation runbook:

1. **Vendor BAA tracker shape.** Currently scattered across
   runbooks. Activation requires `docs/compliance/baas.md`
   as the single canonical table.
2. **Contingency plan + workforce training docs.** Same —
   templates need to land before phases 7 + 8 can produce
   non-trivial findings.
3. **`COMPLIANCE_AUDIT_RUN_COMPLETED` AuditAction.** Needs a
   migration to add the enum value before activation.
4. **Postgres read-only role.** Same defense-in-depth note as
   ai-pipeline-auditor — create a SELECT-only role for the
   auditor's connection.
5. **Cron schedule + alert routing.** Where do P1 findings
   alert? Sentry? Slack? Email? Activation needs the choice
   + the wiring.
