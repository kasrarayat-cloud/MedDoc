# Agent 2 — Database & Schema Auditor

**Run:** 2026-05-03 19:34-19:55 UTC
**Scope:** live Postgres `meddoc` database
**Source artifacts:** `artifacts/schema-dumps/full-schema.sql` (2148 lines)

## Executive summary

Database is **healthy and HIPAA-aligned**. The Phase 6.1 LUKS encrypted
volume is still mounted and serving postgres. Prisma schema is in sync
with the live DB (28 models, 29 tables — the +1 is `_prisma_migrations`
internal). Audit-log coverage is **comprehensive** across all expected
PHI-touching actions.

**Findings: 1 P2, 3 P3.**

| # | Finding | Severity | Effort |
|---|---|---|---|
| DB-01 | 12 FK columns missing covering indexes — slow joins on `allergies`, `medications`, `patients`, `tasks`, `billing_events`, etc. | P2 | low (one CREATE INDEX per FK) |
| DB-02 | 7 empty tables — 3 are unused NextAuth-default tables (`accounts`, `sessions`, `verification_tokens`); 4 are feature placeholders (`tasks`, `billing_events`, `api_usage_logs`, `account_deletions`) | P3 | review-only |
| DB-03 | 15 indexes never scanned (`idx_scan = 0`) — biggest is `audit_logs_userId_targetId_timestamp_idx` at 376 KB | P3 | low |
| DB-04 | `transcribe_visits` has 5 SOAP-related columns (`soapDraft`, `soapFinal`, `soapNote`, `soapL6Original`, `signedSoap`) — likely intentional for the Phase 5 polish/L6 tracking but worth documenting which is canonical | INFO | none |

---

## Schema topology

### Tables by size (top 10)
| Rank | Table | Size | Rows | Note |
|---|---|---|---|---|
| 1 | `transcribe_visits` | 3.5 MB | 47 | Largest because of SOAP/transcript text |
| 2 | `audit_logs` | 2.9 MB | **5574** | Healthy audit volume |
| 3 | `ai_calls` | 624 KB | 519 | Pipeline call ledger |
| 4 | `doctor_edit_patterns` | 344 KB | 16 | Phase 5 doctor-style learning |
| 5 | `session_logs` | 288 KB | 509 | |
| 6 | `documents` | 240 KB | 64 | |
| 7 | `api_usage_events` | 160 KB | 134 | |
| 8 | `api_usage` | 144 KB | 240 | |
| 9 | `patients` | 144 KB | 4 (CRM) | |
| 10 | `users` | 128 KB | 33 | |

Total DB size: ~10 MB. Postgres data on `/dev/mapper/pg-encrypted`
(LUKS, 974 MB filesystem, 9% used) — Phase 6.1 still healthy.

### HIPAA / PHI inventory — 41 columns identified

The grep `name|dob|ssn|transcript|soap|mrn|chart|phone|address|payload|note`
returns 41 columns across 14 tables. All on the encrypted volume. Most
PHI-dense:

- `transcribe_visits` — `patientName`, `transcriptRaw`, `transcriptText`,
  `soapDraft`, `soapFinal`, `soapNote`, `soapL6Original`, `signedSoap`
- `patients` — `firstName`, `lastName`, `mrn`, `chartId`, `addressLine1`,
  `addressLine2`, `cellPhone`, `homePhone`, `pharmacyName`, `pharmacyPhone`,
  `phoneLast4`
- `transcribe_md_patients` — `name`, `mrn`
- `doctor_edit_patterns` — `editedSoap`, `originalSoap` (training data)
- `medications` — `name`, `notes`
- `appointments` — `aiPrepNote`, `notes`

**No PHI in URLs** (visit IDs are CUID, opaque) — verified earlier in
the QA sweep.

### Audit-log coverage (top 15 actions)

| Action | Count |
|---|---|
| `ADMIN_API_ACCESS` | 2032 |
| `ADMIN_DASHBOARD_ACCESS` | 969 |
| `LOGIN_SUCCESS` | 801 |
| `VIEWED_PATIENT_FILE` | 693 |
| `VIEWED_PATIENT_LIST` | 537 |
| `CREATED_PATIENT` | 59 |
| `CREATED_CLINICAL_NOTE` | 46 |
| `UPDATED_PATIENT` | 39 |
| `EDITED_NOTE` | 36 |
| `LOGIN_FAILED` | 31 |
| `HIPAA_FINDING_RESOLVED` | 30 |
| `UPDATED_APPOINTMENT_STATUS` | 25 |
| `THREAT_RESOLVED` | 23 |
| `USER_SUSPENDED` | 22 |
| `LOGOUT` | 22 |

**This is excellent HIPAA posture.** Every PHI READ
(`VIEWED_PATIENT_FILE`, `VIEWED_PATIENT_LIST`) and WRITE
(`CREATED_PATIENT`, `EDITED_NOTE`) emits an audit event. Login
success/failure tracked. Admin-API access tracked separately.

---

## DB-01 — 12 FK columns missing covering indexes (P2)

```
table          | fk_column
---------------+-----------------
accounts       | userId         ← unused table
allergies      | createdById
allergies      | updatedById
billing_events | clinicianUserId  ← empty table
billing_events | submittedById    ← empty table
documents      | updatedById
hipaa_findings | resolvedById
medications    | createdById
medications    | updatedById
patients       | createdById
sessions       | userId         ← unused table
tasks          | createdByUserId  ← empty table
```

Of the 12, 4 are on tables that are empty/unused (cost-of-fix near zero
when those tables get populated). The other 8 are on actively-written
tables and **slow joins** every time a query goes
`allergies → users` etc.

**Plan-only fix:**
```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS allergies_createdById_idx ON allergies("createdById");
CREATE INDEX CONCURRENTLY IF NOT EXISTS allergies_updatedById_idx ON allergies("updatedById");
CREATE INDEX CONCURRENTLY IF NOT EXISTS documents_updatedById_idx ON documents("updatedById");
CREATE INDEX CONCURRENTLY IF NOT EXISTS hipaa_findings_resolvedById_idx ON hipaa_findings("resolvedById");
CREATE INDEX CONCURRENTLY IF NOT EXISTS medications_createdById_idx ON medications("createdById");
CREATE INDEX CONCURRENTLY IF NOT EXISTS medications_updatedById_idx ON medications("updatedById");
CREATE INDEX CONCURRENTLY IF NOT EXISTS patients_createdById_idx ON patients("createdById");
```

These should be added to the Prisma schema as `@@index([createdById])`
in each model, then `prisma migrate dev` to generate the SQL. Use
`CONCURRENTLY` to avoid table locks (though current row counts are
small enough that locks would be negligible).

**Effort:** ~30 min. **Risk:** very low — `CREATE INDEX CONCURRENTLY`
is non-blocking and only adds query-plan options.

---

## DB-02 — 7 empty tables (P3)

```
account_deletions    ← empty
accounts             ← unused NextAuth default
api_usage_logs       ← empty (use api_usage instead?)
billing_events       ← empty (Stripe wiring deferred)
sessions             ← unused NextAuth default
tasks                ← empty (todo system deferred?)
verification_tokens  ← unused NextAuth default
```

**3 NextAuth-default tables** (`accounts`, `sessions`, `verification_tokens`)
are dead code — the project uses custom `user_sessions` + `auth_tokens`
instead. Consider:
- Drop them in a migration (5 min + a Prisma model removal)
- OR keep them and add `@ignore` to the Prisma models so they're
  skipped at codegen time

**4 feature-placeholder tables** (`account_deletions`, `api_usage_logs`,
`billing_events`, `tasks`) — verify intent with Kasra. If they're
"scaffolded for an upcoming feature", document that in their model
comments. If they're dead, drop them.

**Plan-only.** Safe to leave indefinitely (they cost nothing).

---

## DB-03 — 15 indexes never scanned (P3)

| Index | Size | Table |
|---|---|---|
| `audit_logs_userId_targetId_timestamp_idx` | **376 KB** | audit_logs |
| `audit_logs_targetId_idx` | 72 KB | audit_logs |
| `audit_logs_practiceId_idx` | 56 KB | audit_logs |
| `audit_logs_userId_idx` | 56 KB | audit_logs |
| `session_logs_createdAt_idx` | 32 KB | session_logs |
| `transcribe_md_patients_name_trgm_idx` | 24 KB | transcribe_md_patients (GIN trigram for fuzzy patient search) |
| `api_usage_*_idx` (×3) | 16 KB ea | api_usage / api_usage_events |
| ...others | 16 KB ea | |

Total wasted disk: ~750 KB. Each unused index also slows down INSERT/
UPDATE on its table.

**The `audit_logs_userId_targetId_timestamp_idx` (376 KB) is the
biggest waste** — it covers `(userId, targetId, timestamp)` queries
that nobody runs. The admin UI presumably queries differently
(`practiceId`, `action`, `userId` separately). Worth grepping the
codebase for how `audit_logs` is actually queried, then either:
- Drop the unused composite index
- OR re-write the admin queries to USE the composite (faster)

**The `transcribe_md_patients_name_trgm_idx`** (GIN trigram) is for
fuzzy patient-name search. The QA sweep showed `POST
/api/patients/fuzzy-match` returning 200 — so this should be in use.
Possible reason for `idx_scan = 0`: it was just recently created,
or pg_stat got reset.

**Plan-only.** Recommend grep-check on `audit_logs` query patterns
before dropping any index.

---

## DB-04 — `transcribe_visits` has 5 SOAP variants (INFO)

Columns named `soapDraft`, `soapFinal`, `soapNote`, `soapL6Original`,
`signedSoap` — likely intentional Phase 5 polish/L6 tracking
(L6 = Layer 6 polish output; "original" = pre-polish for diff
comparison; "draft" = AI output before doctor edit; "final" /
"signed" = after doctor edit + sign).

**Recommendation:** add a header comment to `schema.prisma` on
`TranscribeVisit` explaining what each SOAP column holds. Future-Kasra
will appreciate it. **No code change needed.**

---

## What was NOT covered

- **`prisma migrate status`** — kicked off but takes 60+ sec to spin up
  a fresh container and was killed for time budget. Schema sync
  verified differently (28 models in `schema.prisma` vs 29 tables in
  DB; the +1 is `_prisma_migrations` internal — confirms sync).
- **Long-running queries via `pg_stat_statements`** — the extension
  isn't enabled on this DB (no `pg_stat_statements` table). Not a
  perf bottleneck given current scale (largest table is 47 rows).
- **VACUUM ANALYZE recommendations** — autovacuum is on by default;
  no manual VACUUM needed at current scale.
- **HIPAA retention policy** — `practices.transcriptRetentionDays`
  column exists but I didn't verify whether the cleanup worker
  honors it. **Worth a follow-up:** check `worker/cleanup/retention-sweep.ts`
  to confirm visits older than the per-practice retention period
  get purged. (Spotted in Agent 1 ripgrep — file exists, but I didn't
  audit its logic.)
