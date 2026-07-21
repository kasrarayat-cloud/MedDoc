# Template Twin Operations approval packet

Status: **HUMAN PENDING — PRODUCTION DEPLOYMENT BLOCKED**

## Current operational findings

- Running production images are preserved, but their exact source SHA is not reproducible and they are not safe post-migration rollback targets.
- A schema-only restore succeeded in an isolated disposable environment; a complete data-bearing restore, PITR, object-store recovery, and queue recovery have not passed.
- Production application traffic uses the database superuser/owner and MinIO root credentials.
- PostgreSQL, Redis, and MinIO service traffic is plaintext on the private Docker network.
- Object versioning, object lock, lifecycle, orphan reconciliation, and durable capacity evidence are incomplete; recent storage-full events were observed.
- Monitoring dashboards, alert routing, on-call ownership, migration window, kill-switch ownership, and the audited maintenance fence remain incomplete.
- Production rollout remains 0% and no production changes were made by this program.

## Decisions and named owners required

| Topic                     | Required evidence                                                            | Status        |
| ------------------------- | ---------------------------------------------------------------------------- | ------------- |
| Deployment owner          | Named person/team with production authority and change window                | HUMAN PENDING |
| Migration owner/window    | Approved window, lock/statement timeouts, abort criteria                     | HUMAN PENDING |
| Backup/restore            | Fresh identifiers plus complete disposable restore and PITR evidence         | FAIL          |
| Storage recovery          | Version/object recovery, retention/deletion/legal-hold behavior              | FAIL          |
| Queue/worker recovery     | Retry, ambiguous outcome, interruption/resume, and idempotency rehearsal     | FAIL          |
| Monitoring/alerts         | Dashboards, thresholds, delivery tests, and named responders                 | FAIL          |
| Kill switch               | Named owner, audited invocation, propagation target, and SLA                 | HUMAN PENDING |
| Rollback                  | Exact bridge images/digests, ordered procedure, maintenance fence, rehearsal | FAIL          |
| Capacity/rate limits      | Production-scale upload/render/sign/provider/queue tests                     | FAIL          |
| Support/incident response | Named support and clinical/privacy/security escalation paths                 | HUMAN PENDING |

## Required rollout authorization

Operations approval must be tied to the final exact SHA, immutable image digests, verified backup identifiers, rollback rehearsal evidence, and the approved canary/10%/25%/50%/100% checkpoint criteria. Authorization is revoked automatically if a checkpoint criterion fails.

## Human decision

- Decision: `APPROVE` / `REJECT` / `REVISE`
- Final exact SHA: **UNFILLED — HUMAN REQUIRED**
- App/worker/migrator image digests: **UNFILLED — HUMAN REQUIRED**
- Backup and restore identifiers: **UNFILLED — HUMAN REQUIRED**
- Name and role: **UNFILLED — HUMAN REQUIRED**
- Date/time and timezone: **UNFILLED — HUMAN REQUIRED**
- Approval record: **UNFILLED — HUMAN REQUIRED**
