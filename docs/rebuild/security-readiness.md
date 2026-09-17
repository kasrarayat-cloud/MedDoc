# Private beta security readiness — 2026-09-17

Statuses describe observed evidence and deliberately separate prepared changes
from live activation. The application remains synthetic-only.

| Control | Evidence/status | Remaining qualification |
| --- | --- | --- |
| Private access | Doctor/admin bind 127.0.0.1:9130/9131; public app/admin maintenance503 | Authenticated test access for independent reviewer; reviewed HTTPS deployment before public use |
| Database exposure | Dedicated fresh cluster, published only127.0.0.1:55438; actual wrong-password attempt refused | Transport/encryption requirements for eventual topology; do not expose PostgreSQL publicly |
| Database privilege | Dedicated runtime role active;17role assertions and restored trigger checks passed | Independent privilege/race testing and credential recovery rehearsal |
| Immutable financial/audit records | Eight restored custom triggers enabled; runtime mutation/trigger-disable attempts refused; live billing audit passes | Independent financial mutation and concurrency review |
| Secret handling | Dedicated UID996/GID988, no capabilities, same-PID9denials+3positive controls per service; environment0600 inaccessible | Credential rotation and owner recovery rehearsal |
| Backup/restore |Post-OS restore:33tables/75,248rows/22referencedfiles, all hashes/invariants verified; ciphertext authenticated | Independent failure domain, key escrow, retention/RPO/RTO, scheduling/alerting and promotion rehearsal |
| File protection | Original/export/receipt hashes checked through backup and restore; no public storage route | At-rest encryption/mount and retention/deletion policy for actual patient data |
| Upload/parser safety | Existing isolated parser and synthetic rejection tests; bounded Word SDK qualification in progress | Finished clinical/SDK refutation and deployed WM workflow; scanned forms deferred |
| Tenant permissions | Existing API/file/export/job isolation tests | Independent tests across every fresh route and background authorization race |
| Administrator MFA | Existing TOTP gate and internal tests | Recovery/enrollment/revocation procedures and independent bypass attempts |
| Billing controls | Existing exact multiplier, locking, idempotency tests | Real Stripe test-mode exercise when keys available; account invoice reconciliation |
| External services | Synthetic provider use only | Required patient-data agreements, processing regions/retention and provider controls |
| Penetration test | Internal scope/evidence exists; independent handoff prepared | Independent reviewer, approved access/window and resulting report + repaired-findings retest |

An internal test pass, a prepared unit file or a successfully restored local
database does not clear the patient-data gate. No subscription or cloud resource
was provisioned and no real patient data was used for these checks.

## Evidence scope after dedicated identity activation

Release68883747 is private and synthetic-only. Direct namespace entry failed
because Docker AppArmor denied the ptrace read. Actual service-PID file/socket
probes now establish the intended denial without changing host protections;
this specific coverage gap is closed. The local backup restore is not offsite
recovery and the operator-held key is not independently escrowed.

Cost audit:10usage rows,14wallets, all arithmetic/ledger checks pass; two early
missing receipts remain documented exceptions. Eight real synthetic jobs have
configured-rate costUSD0.012801775400 and chargeUSD0.019202663100. Captured
provider units do not establish account billed cost or invoice reconciliation.
Available Deepgram billing/report access was denied403; Anthropic ordinary
request access does not grant organization billing access.

Stripe sandbox delivery, real Resend invitation/recovery delivery, approved
remote backup restoration, CPT entitlement and independent testing remain
unverified external gates. Use `owner-actions.md` for exact secure handoff steps.
No broad cleanup, new cloud provisioning, purchase or real patient data is
part of these changes.
