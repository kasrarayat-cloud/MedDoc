# Private beta security readiness — 2026-09-17

Statuses describe observed evidence and deliberately separate prepared changes
from live activation. The application remains synthetic-only.

| Control | Evidence/status | Remaining qualification |
| --- | --- | --- |
| Private access | Doctor/admin bind 127.0.0.1:9130/9131; public app/admin maintenance503 | Authenticated test access for independent reviewer; reviewed HTTPS deployment before public use |
| Database exposure | Dedicated fresh cluster, published only127.0.0.1:55438; actual wrong-password attempt refused | Transport/encryption requirements for eventual topology; do not expose PostgreSQL publicly |
| Database privilege | Live bootstrap superuser identified; separate roles/tooling pass17 isolated proofs | Coordinated live application, runtime-role readback and maintenance recovery proof |
| Immutable financial/audit records | Restored triggers enabled; runtime mutation/trigger-disable attempts refused | Verify same controls under live runtime role after activation |
| Secret handling | Environment/private artifacts0600, runtime0700; encrypted backup/key separated | Install/reload prepared InaccessiblePaths policy; dedicated OS service identity, rotation and recovery |
| Backup/restore |33tables/75,100rows/15files restore with all hashes; encryption/tamper controls tested | Independent failure domain, key escrow, retention/RPO/RTO, scheduling/alerting and promotion rehearsal |
| File protection | Original/export/receipt hashes checked through backup and restore; no public storage route | At-rest encryption/mount and retention/deletion policy for actual patient data |
| Upload/parser safety | Existing isolated parser and synthetic rejection tests | Independent parser/decompression/OCR/SDK review for supported formats; broader SDK still gated |
| Tenant permissions | Existing API/file/export/job isolation tests | Independent tests across every fresh route and background authorization race |
| Administrator MFA | Existing TOTP gate and internal tests | Recovery/enrollment/revocation procedures and independent bypass attempts |
| Billing controls | Existing exact multiplier, locking, idempotency tests | Real Stripe test-mode exercise when keys available; account invoice reconciliation |
| External services | Synthetic provider use only | Required patient-data agreements, processing regions/retention and provider controls |
| Penetration test | Internal scope/evidence exists; independent handoff prepared | Independent reviewer, approved access/window and resulting report + repaired-findings retest |

An internal test pass, a prepared unit file or a successfully restored local
database does not clear the patient-data gate. No subscription or cloud resource
was provisioned and no real patient data was used for these checks.
