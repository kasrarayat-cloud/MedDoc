# Round 3 Audit — Findings index (severity-sorted)

138 findings across 12 domains. Each row is a clickable link to the finding file.

Cross-reference: per-agent SUMMARY.md files in each `agent-NN/` subdirectory; `EXECUTIVE-SUMMARY.md` next to this file.

## P0 — Blocks pilot (21)

| ID | Title | File |
|---|---|---|
| A01-P0-001 | Live Secrets Baked Into Docker Images | [agent-01/P0-001-live-secrets-baked-into-docker-images.md](agent-01/P0-001-live-secrets-baked-into-docker-images.md) |
| A01-P0-002 | Leaked Openai Key Still On Disk Rotation Not Completed | [agent-01/P0-002-leaked-openai-key-still-on-disk-rotation-not-completed.md](agent-01/P0-002-leaked-openai-key-still-on-disk-rotation-not-completed.md) |
| A01-P0-003 | World Writable Env Files With Live Secrets | [agent-01/P0-003-world-writable-env-files-with-live-secrets.md](agent-01/P0-003-world-writable-env-files-with-live-secrets.md) |
| A02-P0-001 | Qa Bypass Domain Grants Trial Accounts | [agent-02/P0-001-qa-bypass-domain-grants-trial-accounts.md](agent-02/P0-001-qa-bypass-domain-grants-trial-accounts.md) |
| A02-P0-002 | Env Backup World Readable Secrets | [agent-02/P0-002-env-backup-world-readable-secrets.md](agent-02/P0-002-env-backup-world-readable-secrets.md) |
| A05-P0-001 | MinIO No Encryption At Rest | [agent-05/P0-001-minio-no-encryption-at-rest.md](agent-05/P0-001-minio-no-encryption-at-rest.md) |
| A05-P0-002 | Database Backups Unencrypted On Disk | [agent-05/P0-002-database-backups-unencrypted-on-disk.md](agent-05/P0-002-database-backups-unencrypted-on-disk.md) |
| A05-P0-003 | Postscript Unencrypted Offsite Mirror | [agent-05/P0-003-postscript-unencrypted-offsite-mirror.md](agent-05/P0-003-postscript-unencrypted-offsite-mirror.md) |
| A05-P0-004 | PHI Read No Audit Log | [agent-05/P0-004-phi-read-no-audit-log.md](agent-05/P0-004-phi-read-no-audit-log.md) |
| A06-P0-001 | No Empty Transcript Guard | [agent-06/P0-001-no-empty-transcript-guard.md](agent-06/P0-001-no-empty-transcript-guard.md) |
| A06-P0-002 | No ICD CPT Allowlist | [agent-06/P0-002-no-icd-cpt-allowlist.md](agent-06/P0-002-no-icd-cpt-allowlist.md) |
| A06-P0-003 | Psychiatry Self Harm Soft Rule | [agent-06/P0-003-psychiatry-self-harm-soft-rule.md](agent-06/P0-003-psychiatry-self-harm-soft-rule.md) |
| A06-P0-004 | No Drug Interaction Or Allergy Database | [agent-06/P0-004-no-drug-interaction-or-allergy-database.md](agent-06/P0-004-no-drug-interaction-or-allergy-database.md) |
| A07-P0-001 | sshd Permitrootlogin Yes | [agent-07/P0-001-sshd-permitrootlogin-yes.md](agent-07/P0-001-sshd-permitrootlogin-yes.md) |
| A07-P0-002 | No Host Firewall UFW Inactive | [agent-07/P0-002-no-host-firewall-ufw-inactive.md](agent-07/P0-002-no-host-firewall-ufw-inactive.md) |
| A07-P0-003 | Out Of Scope Root Uvicorn On port 8000 | [agent-07/P0-003-out-of-scope-root-uvicorn-on-port-8000.md](agent-07/P0-003-out-of-scope-root-uvicorn-on-port-8000.md) |
| A09-P0-001 | Rx Warning Override Gate Bypass Via Double Click | [agent-09/P0-001-rx-warning-override-gate-bypass-via-double-click.md](agent-09/P0-001-rx-warning-override-gate-bypass-via-double-click.md) |
| A09-P0-002 | Audit Log Mutability No DB Role Protection | [agent-09/P0-002-audit-log-mutability-no-db-role-protection.md](agent-09/P0-002-audit-log-mutability-no-db-role-protection.md) |
| A09-P0-003 | SOAP Edit No Optimistic Concurrency Two Tab Data Loss | [agent-09/P0-003-soap-edit-no-optimistic-concurrency-two-tab-data-loss.md](agent-09/P0-003-soap-edit-no-optimistic-concurrency-two-tab-data-loss.md) |
| A12-P0-001 | BAA Overstatement On Public Pages | [agent-12/P0-001-baa-overstatement-on-public-pages.md](agent-12/P0-001-baa-overstatement-on-public-pages.md) |
| A12-P0-002 | No Breach Notification Runbook | [agent-12/P0-002-no-breach-notification-runbook.md](agent-12/P0-002-no-breach-notification-runbook.md) |

## P1 — Blocks public launch (47)

| ID | Title | File |
|---|---|---|
| A01-P1-001 | Decommissioned App Still Runs With Live Keys | [agent-01/P1-001-decommissioned-app-still-runs-with-live-keys.md](agent-01/P1-001-decommissioned-app-still-runs-with-live-keys.md) |
| A01-P1-002 | Resend Api Key In Tests Env Test Tracked On Disk | [agent-01/P1-002-resend-api-key-in-tests-env-test-tracked-on-disk.md](agent-01/P1-002-resend-api-key-in-tests-env-test-tracked-on-disk.md) |
| A01-P1-003 | Dockerignore Misses Env And Env Backup | [agent-01/P1-003-dockerignore-misses-env-and-env-backup.md](agent-01/P1-003-dockerignore-misses-env-and-env-backup.md) |
| A02-P1-001 | Signup Leaks Account Existence | [agent-02/P1-001-signup-leaks-account-existence.md](agent-02/P1-001-signup-leaks-account-existence.md) |
| A02-P1-002 | Account Lockout DoS Via Failed Logins | [agent-02/P1-002-account-lockout-dos-via-failed-logins.md](agent-02/P1-002-account-lockout-dos-via-failed-logins.md) |
| A02-P1-003 | Rate Limit Resets On Container Restart | [agent-02/P1-003-rate-limit-resets-on-container-restart.md](agent-02/P1-003-rate-limit-resets-on-container-restart.md) |
| A02-P1-004 | Nextauth Beta Version Pinned | [agent-02/P1-004-nextauth-beta-version-pinned.md](agent-02/P1-004-nextauth-beta-version-pinned.md) |
| A04-P1-001 | Prompt Injection Via User Text Into Llm Context | [agent-04/P1-001-prompt-injection-via-user-text-into-llm-context.md](agent-04/P1-001-prompt-injection-via-user-text-into-llm-context.md) |
| A04-P1-002 | Audio Upload Content Type Trusted Without Content Inspection | [agent-04/P1-002-audio-upload-content-type-trusted-without-content-inspection.md](agent-04/P1-002-audio-upload-content-type-trusted-without-content-inspection.md) |
| A05-P1-001 | No BAA With Vendors | [agent-05/P1-001-no-baa-with-vendors.md](agent-05/P1-001-no-baa-with-vendors.md) |
| A05-P1-002 | Session 7 Day No Idle Timeout | [agent-05/P1-002-session-7-day-no-idle-timeout.md](agent-05/P1-002-session-7-day-no-idle-timeout.md) |
| A05-P1-003 | Audit Log Not Tamper Evident | [agent-05/P1-003-audit-log-not-tamper-evident.md](agent-05/P1-003-audit-log-not-tamper-evident.md) |
| A05-P1-004 | Backup Script No Public Key Fingerprint Validation | [agent-05/P1-004-backup-script-no-public-key-fingerprint-validation.md](agent-05/P1-004-backup-script-no-public-key-fingerprint-validation.md) |
| A05-P1-005 | Postgres Redis No TLS Intra Network | [agent-05/P1-005-postgres-redis-no-tls-intra-network.md](agent-05/P1-005-postgres-redis-no-tls-intra-network.md) |
| A06-P1-005 | Patient Claim Renders As Factual | [agent-06/P1-005-patient-claim-renders-as-factual.md](agent-06/P1-005-patient-claim-renders-as-factual.md) |
| A06-P1-006 | No Multilang Detection | [agent-06/P1-006-no-multilang-detection.md](agent-06/P1-006-no-multilang-detection.md) |
| A06-P1-007 | Whisper Fallback Doesnt Exist | [agent-06/P1-007-whisper-fallback-doesnt-exist.md](agent-06/P1-007-whisper-fallback-doesnt-exist.md) |
| A06-P1-008 | No Token Budget Truncation | [agent-06/P1-008-no-token-budget-truncation.md](agent-06/P1-008-no-token-budget-truncation.md) |
| A06-P1-009 | No Pediatric Mg Per Kg Validator | [agent-06/P1-009-no-pediatric-mg-per-kg-validator.md](agent-06/P1-009-no-pediatric-mg-per-kg-validator.md) |
| A06-P1-010 | L5 Judge Self Conflict | [agent-06/P1-010-l5-judge-self-conflict.md](agent-06/P1-010-l5-judge-self-conflict.md) |
| A07-P1-001 | Orphan Public Ports 9010 9020 | [agent-07/P1-001-orphan-public-ports-9010-9020.md](agent-07/P1-001-orphan-public-ports-9010-9020.md) |
| A07-P1-002 | No Fail2ban | [agent-07/P1-002-no-fail2ban.md](agent-07/P1-002-no-fail2ban.md) |
| A07-P1-003 | Claude In Docker Group Root Equivalent | [agent-07/P1-003-claude-in-docker-group-root-equivalent.md](agent-07/P1-003-claude-in-docker-group-root-equivalent.md) |
| A07-P1-004 | Postgres Backups World Readable On Host | [agent-07/P1-004-postgres-backups-world-readable-on-host.md](agent-07/P1-004-postgres-backups-world-readable-on-host.md) |
| A07-P1-005 | MinIO Uses Latest image | [agent-07/P1-005-minio-uses-latest-image.md](agent-07/P1-005-minio-uses-latest-image.md) |
| A07-P1-006 | No Swap Encryption | [agent-07/P1-006-no-swap-encryption.md](agent-07/P1-006-no-swap-encryption.md) |
| A07-P1-007 | Unbounded Syslog And Journal Growth | [agent-07/P1-007-unbounded-syslog-and-journal-growth.md](agent-07/P1-007-unbounded-syslog-and-journal-growth.md) |
| A08-P1-001 | Next Auth Beta On Prod | [agent-08/P1-001-next-auth-beta-on-prod.md](agent-08/P1-001-next-auth-beta-on-prod.md) |
| A08-P1-002 | Floating Base image Tags | [agent-08/P1-002-floating-base-image-tags.md](agent-08/P1-002-floating-base-image-tags.md) |
| A09-P1-001 | Worker No In Flight Lock Duplicate Pipeline Runs | [agent-09/P1-001-worker-no-in-flight-lock-duplicate-pipeline-runs.md](agent-09/P1-001-worker-no-in-flight-lock-duplicate-pipeline-runs.md) |
| A09-P1-002 | Soft Delete During Pipeline Undeleted By Worker Writes | [agent-09/P1-002-soft-delete-during-pipeline-undeleted-by-worker-writes.md](agent-09/P1-002-soft-delete-during-pipeline-undeleted-by-worker-writes.md) |
| A09-P1-003 | Backup Chain No Completion Check Stale Dump Uploads | [agent-09/P1-003-backup-chain-no-completion-check-stale-dump-uploads.md](agent-09/P1-003-backup-chain-no-completion-check-stale-dump-uploads.md) |
| A09-P1-004 | Bullmq Jobid Dedupe Window Too Narrow | [agent-09/P1-004-bullmq-jobid-dedupe-window-too-narrow.md](agent-09/P1-004-bullmq-jobid-dedupe-window-too-narrow.md) |
| A10-P1-001 | Axe Color Contrast Globally Suppressed | [agent-10/P1-001-axe-color-contrast-globally-suppressed.md](agent-10/P1-001-axe-color-contrast-globally-suppressed.md) |
| A10-P1-002 | Skip Link Broken No Main Id | [agent-10/P1-002-skip-link-broken-no-main-id.md](agent-10/P1-002-skip-link-broken-no-main-id.md) |
| A10-P1-003 | Marketing No Skip Link | [agent-10/P1-003-marketing-no-skip-link.md](agent-10/P1-003-marketing-no-skip-link.md) |
| A10-P1-004 | Transcript Audio Controls Tabindex Minus 1 | [agent-10/P1-004-transcript-audio-controls-tabindex-minus-1.md](agent-10/P1-004-transcript-audio-controls-tabindex-minus-1.md) |
| A11-P1-001 | Sentry No Source Map Upload | [agent-11/P1-001-sentry-no-source-map-upload.md](agent-11/P1-001-sentry-no-source-map-upload.md) |
| A11-P1-002 | Redis No AOF Persistence | [agent-11/P1-002-redis-no-aof-persistence.md](agent-11/P1-002-redis-no-aof-persistence.md) |
| A11-P1-003 | Worker No Healthcheck | [agent-11/P1-003-worker-no-healthcheck.md](agent-11/P1-003-worker-no-healthcheck.md) |
| A11-P1-004 | No Deepgram Fallback | [agent-11/P1-004-no-deepgram-fallback.md](agent-11/P1-004-no-deepgram-fallback.md) |
| A11-P1-005 | No Marketing Sentry | [agent-11/P1-005-no-marketing-sentry.md](agent-11/P1-005-no-marketing-sentry.md) |
| A11-P1-006 | No Bullmq DLQ Or Board | [agent-11/P1-006-no-bullmq-dlq-or-board.md](agent-11/P1-006-no-bullmq-dlq-or-board.md) |
| A12-P1-001 | No Disaster Recovery Runbook | [agent-12/P1-001-no-disaster-recovery-runbook.md](agent-12/P1-001-no-disaster-recovery-runbook.md) |
| A12-P1-002 | Phase 6.2 Runbook Gaps MinIO | [agent-12/P1-002-phase-6.2-runbook-gaps-minio.md](agent-12/P1-002-phase-6.2-runbook-gaps-minio.md) |
| A12-P1-003 | No Onboarding Doc | [agent-12/P1-003-no-onboarding-doc.md](agent-12/P1-003-no-onboarding-doc.md) |
| A12-P1-004 | No Threat Model No Adrs | [agent-12/P1-004-no-threat-model-no-adrs.md](agent-12/P1-004-no-threat-model-no-adrs.md) |

## P2 — Notable, non-blocking (44)

| ID | Title | File |
|---|---|---|
| A01-P2-001 | Auth Secret Fallback String In Source | [agent-01/P2-001-auth-secret-fallback-string-in-source.md](agent-01/P2-001-auth-secret-fallback-string-in-source.md) |
| A01-P2-002 | Smoke Harness Logs Credentials On Direct Invocation | [agent-01/P2-002-smoke-harness-logs-credentials-on-direct-invocation.md](agent-01/P2-002-smoke-harness-logs-credentials-on-direct-invocation.md) |
| A01-P2-003 | No Secret Scanner In Pre Commit Or Ci | [agent-01/P2-003-no-secret-scanner-in-pre-commit-or-ci.md](agent-01/P2-003-no-secret-scanner-in-pre-commit-or-ci.md) |
| A02-P2-001 | Password Policy No Breach List | [agent-02/P2-001-password-policy-no-breach-list.md](agent-02/P2-001-password-policy-no-breach-list.md) |
| A02-P2-002 | Email Link Prefetch Consumes Token | [agent-02/P2-002-email-link-prefetch-consumes-token.md](agent-02/P2-002-email-link-prefetch-consumes-token.md) |
| A02-P2-003 | IP Trust Without Trusted Proxies | [agent-02/P2-003-ip-trust-without-trusted-proxies.md](agent-02/P2-003-ip-trust-without-trusted-proxies.md) |
| A03-P2-001 | Delete Account Cascade Multi Tenant | [agent-03/P2-001-delete-account-cascade-multi-tenant.md](agent-03/P2-001-delete-account-cascade-multi-tenant.md) |
| A03-P2-002 | Visit Patch Allows Changing Patient With Stale Visit Fk | [agent-03/P2-002-visit-patch-allows-changing-patient-with-stale-visit-fk.md](agent-03/P2-002-visit-patch-allows-changing-patient-with-stale-visit-fk.md) |
| A04-P2-001 | Bcrypt Password Fields Unbounded | [agent-04/P2-001-bcrypt-password-fields-unbounded.md](agent-04/P2-001-bcrypt-password-fields-unbounded.md) |
| A04-P2-002 | Search Query Params Unbounded | [agent-04/P2-002-search-query-params-unbounded.md](agent-04/P2-002-search-query-params-unbounded.md) |
| A04-P2-003 | Id Fields Lack UUID CUID Format Validation | [agent-04/P2-003-id-fields-lack-uuid-cuid-format-validation.md](agent-04/P2-003-id-fields-lack-uuid-cuid-format-validation.md) |
| A05-P2-001 | Luks Volume Undersized 1gb | [agent-05/P2-001-luks-volume-undersized-1gb.md](agent-05/P2-001-luks-volume-undersized-1gb.md) |
| A05-P2-002 | Em Score Text Input No Audit | [agent-05/P2-002-em-score-text-input-no-audit.md](agent-05/P2-002-em-score-text-input-no-audit.md) |
| A06-P2-011 | Eval Framework Missing | [agent-06/P2-011-eval-framework-missing.md](agent-06/P2-011-eval-framework-missing.md) |
| A06-P2-012 | Specialty Guidance Stale Keys | [agent-06/P2-012-specialty-guidance-stale-keys.md](agent-06/P2-012-specialty-guidance-stale-keys.md) |
| A06-P2-013 | Referral Letter Leaks Irrelevant History | [agent-06/P2-013-referral-letter-leaks-irrelevant-history.md](agent-06/P2-013-referral-letter-leaks-irrelevant-history.md) |
| A07-P2-001 | Suboptimal Sysctls | [agent-07/P2-001-suboptimal-sysctls.md](agent-07/P2-001-suboptimal-sysctls.md) |
| A07-P2-002 | CSP Allows Unsafe Inline And Unsafe Eval | [agent-07/P2-002-csp-allows-unsafe-inline-and-unsafe-eval.md](agent-07/P2-002-csp-allows-unsafe-inline-and-unsafe-eval.md) |
| A07-P2-003 | No Rate Limit At Edge On Auth Routes | [agent-07/P2-003-no-rate-limit-at-edge-on-auth-routes.md](agent-07/P2-003-no-rate-limit-at-edge-on-auth-routes.md) |
| A07-P2-004 | Postgres Offsite Cron Not Installed | [agent-07/P2-004-postgres-offsite-cron-not-installed.md](agent-07/P2-004-postgres-offsite-cron-not-installed.md) |
| A07-P2-005 | Floating image Tags And Builders | [agent-07/P2-005-floating-image-tags-and-builders.md](agent-07/P2-005-floating-image-tags-and-builders.md) |
| A08-P2-001 | No Dependabot Renovate | [agent-08/P2-001-no-dependabot-renovate.md](agent-08/P2-001-no-dependabot-renovate.md) |
| A08-P2-002 | Npm Audit Moderate Eight Open | [agent-08/P2-002-npm-audit-moderate-eight-open.md](agent-08/P2-002-npm-audit-moderate-eight-open.md) |
| A08-P2-003 | Stale Lockfile Ghost Workspaces | [agent-08/P2-003-stale-lockfile-ghost-workspaces.md](agent-08/P2-003-stale-lockfile-ghost-workspaces.md) |
| A08-P2-004 | License Fsl And Lgpl Transitives | [agent-08/P2-004-license-fsl-and-lgpl-transitives.md](agent-08/P2-004-license-fsl-and-lgpl-transitives.md) |
| A09-P2-001 | Upload Route Non Atomic Multi Step Write | [agent-09/P2-001-upload-route-non-atomic-multi-step-write.md](agent-09/P2-001-upload-route-non-atomic-multi-step-write.md) |
| A09-P2-002 | No Idempotency On Outbound Resend Anthropic | [agent-09/P2-002-no-idempotency-on-outbound-resend-anthropic.md](agent-09/P2-002-no-idempotency-on-outbound-resend-anthropic.md) |
| A09-P2-003 | Text Route Race On RawTextInput Write | [agent-09/P2-003-text-route-race-on-rawTextInput-write.md](agent-09/P2-003-text-route-race-on-rawTextInput-write.md) |
| A09-P2-004 | Soft Delete Update No Status Guard Restore Recreates Active Visit | [agent-09/P2-004-soft-delete-update-no-status-guard-restore-recreates-active-visit.md](agent-09/P2-004-soft-delete-update-no-status-guard-restore-recreates-active-visit.md) |
| A10-P2-001 | Toast Not Dismissible 4s Timeout | [agent-10/P2-001-toast-not-dismissible-4s-timeout.md](agent-10/P2-001-toast-not-dismissible-4s-timeout.md) |
| A10-P2-002 | No Print Stylesheet SOAP | [agent-10/P2-002-no-print-stylesheet-soap.md](agent-10/P2-002-no-print-stylesheet-soap.md) |
| A10-P2-003 | 404 No Search No Recent Visits | [agent-10/P2-003-404-no-search-no-recent-visits.md](agent-10/P2-003-404-no-search-no-recent-visits.md) |
| A10-P2-004 | No Scroll Restoration Back From Visit | [agent-10/P2-004-no-scroll-restoration-back-from-visit.md](agent-10/P2-004-no-scroll-restoration-back-from-visit.md) |
| A10-P2-005 | Form Validation Submit Only No Onblur | [agent-10/P2-005-form-validation-submit-only-no-onblur.md](agent-10/P2-005-form-validation-submit-only-no-onblur.md) |
| A10-P2-006 | No Mobile Bottom Nav Thumb Reach | [agent-10/P2-006-no-mobile-bottom-nav-thumb-reach.md](agent-10/P2-006-no-mobile-bottom-nav-thumb-reach.md) |
| A11-P2-001 | Mixed Console And Structured Logging | [agent-11/P2-001-mixed-console-and-structured-logging.md](agent-11/P2-001-mixed-console-and-structured-logging.md) |
| A11-P2-002 | No Process Error Handlers Worker | [agent-11/P2-002-no-process-error-handlers-worker.md](agent-11/P2-002-no-process-error-handlers-worker.md) |
| A11-P2-003 | Caddy No Handle_errors Block | [agent-11/P2-003-caddy-no-handle_errors-block.md](agent-11/P2-003-caddy-no-handle_errors-block.md) |
| A11-P2-004 | Sentry No SetUser Context | [agent-11/P2-004-sentry-no-setUser-context.md](agent-11/P2-004-sentry-no-setUser-context.md) |
| A11-P2-005 | No Traces No Slow Query Log | [agent-11/P2-005-no-traces-no-slow-query-log.md](agent-11/P2-005-no-traces-no-slow-query-log.md) |
| A12-P2-001 | No Architecture Diagram | [agent-12/P2-001-no-architecture-diagram.md](agent-12/P2-001-no-architecture-diagram.md) |
| A12-P2-002 | Readme Stale 8 Containers Old IP | [agent-12/P2-002-readme-stale-8-containers-old-ip.md](agent-12/P2-002-readme-stale-8-containers-old-ip.md) |
| A12-P2-003 | No Changelog No Api Docs No BAA Template | [agent-12/P2-003-no-changelog-no-api-docs-no-baa-template.md](agent-12/P2-003-no-changelog-no-api-docs-no-baa-template.md) |
| A12-P2-004 | Claudemd Skeletal And Section Numbering Gap | [agent-12/P2-004-claudemd-skeletal-and-section-numbering-gap.md](agent-12/P2-004-claudemd-skeletal-and-section-numbering-gap.md) |

## P3 — Polish / backlog (26)

| ID | Title | File |
|---|---|---|
| A01-P3-001 | Prior Audit Trufflehog Output Committed With Placeholder Strings | [agent-01/P3-001-prior-audit-trufflehog-output-committed-with-placeholder-strings.md](agent-01/P3-001-prior-audit-trufflehog-output-committed-with-placeholder-strings.md) |
| A02-P3-001 | Stale Nextauth URL In Env | [agent-02/P3-001-stale-nextauth-url-in-env.md](agent-02/P3-001-stale-nextauth-url-in-env.md) |
| A02-P3-002 | Resend From And Link Prefetch Defenses | [agent-02/P3-002-resend-from-and-link-prefetch-defenses.md](agent-02/P3-002-resend-from-and-link-prefetch-defenses.md) |
| A03-P3-001 | Em Coding Cache Key No Practiceid | [agent-03/P3-001-em-coding-cache-key-no-practiceid.md](agent-03/P3-001-em-coding-cache-key-no-practiceid.md) |
| A03-P3-002 | Staff Role Cannot See Doctor Visits | [agent-03/P3-002-staff-role-cannot-see-doctor-visits.md](agent-03/P3-002-staff-role-cannot-see-doctor-visits.md) |
| A04-P3-001 | Stack Field On Client Errors Could Bloat Logs | [agent-04/P3-001-stack-field-on-client-errors-could-bloat-logs.md](agent-04/P3-001-stack-field-on-client-errors-could-bloat-logs.md) |
| A05-P3-001 | BAA Checklist Doc Stale Resend Backblaze Missing | [agent-05/P3-001-baa-checklist-doc-stale-resend-backblaze-missing.md](agent-05/P3-001-baa-checklist-doc-stale-resend-backblaze-missing.md) |
| A06-P3-014 | Flesch Kincaid Claims Unverified | [agent-06/P3-014-flesch-kincaid-claims-unverified.md](agent-06/P3-014-flesch-kincaid-claims-unverified.md) |
| A06-P3-015 | L4 SOAP Output Unstructured | [agent-06/P3-015-l4-soap-output-unstructured.md](agent-06/P3-015-l4-soap-output-unstructured.md) |
| A07-P3-001 | Env Permissions 640 Could Be 600 | [agent-07/P3-001-env-permissions-640-could-be-600.md](agent-07/P3-001-env-permissions-640-could-be-600.md) |
| A07-P3-002 | H8 Post Reboot Script Self Modifying Cron | [agent-07/P3-002-h8-post-reboot-script-self-modifying-cron.md](agent-07/P3-002-h8-post-reboot-script-self-modifying-cron.md) |
| A07-P3-003 | Postscript Curl Mc No Checksum Verify | [agent-07/P3-003-postscript-curl-mc-no-checksum-verify.md](agent-07/P3-003-postscript-curl-mc-no-checksum-verify.md) |
| A08-P3-001 | No Overrides No Engines Pinning | [agent-08/P3-001-no-overrides-no-engines-pinning.md](agent-08/P3-001-no-overrides-no-engines-pinning.md) |
| A08-P3-002 | React Major Mismatch Marketing | [agent-08/P3-002-react-major-mismatch-marketing.md](agent-08/P3-002-react-major-mismatch-marketing.md) |
| A08-P3-003 | No Patches Dir Positive | [agent-08/P3-003-no-patches-dir-positive.md](agent-08/P3-003-no-patches-dir-positive.md) |
| A09-P3-001 | MFA Backup Codes Destructive Migration No Expand Contract | [agent-09/P3-001-mfa-backup-codes-destructive-migration-no-expand-contract.md](agent-09/P3-001-mfa-backup-codes-destructive-migration-no-expand-contract.md) |
| A09-P3-002 | No Redis Distributed Lock For Cron Cron Overlap | [agent-09/P3-002-no-redis-distributed-lock-for-cron-cron-overlap.md](agent-09/P3-002-no-redis-distributed-lock-for-cron-cron-overlap.md) |
| A10-P3-001 | Encounter Vs Visit Terminology | [agent-10/P3-001-encounter-vs-visit-terminology.md](agent-10/P3-001-encounter-vs-visit-terminology.md) |
| A10-P3-002 | Marketing Text 3 Vs App Text 3 Drift | [agent-10/P3-002-marketing-text-3-vs-app-text-3-drift.md](agent-10/P3-002-marketing-text-3-vs-app-text-3-drift.md) |
| A10-P3-003 | Empty State No Recovery From Trash | [agent-10/P3-003-empty-state-no-recovery-from-trash.md](agent-10/P3-003-empty-state-no-recovery-from-trash.md) |
| A10-P3-004 | No Pull To Refresh No Swipe Mobile | [agent-10/P3-004-no-pull-to-refresh-no-swipe-mobile.md](agent-10/P3-004-no-pull-to-refresh-no-swipe-mobile.md) |
| A10-P3-005 | No ARIA Live On Toast Or Status Changes | [agent-10/P3-005-no-aria-live-on-toast-or-status-changes.md](agent-10/P3-005-no-aria-live-on-toast-or-status-changes.md) |
| A11-P3-001 | Rate Limit Message No Eta | [agent-11/P3-001-rate-limit-message-no-eta.md](agent-11/P3-001-rate-limit-message-no-eta.md) |
| A11-P3-002 | Marketing No Error Or Health | [agent-11/P3-002-marketing-no-error-or-health.md](agent-11/P3-002-marketing-no-error-or-health.md) |
| A11-P3-003 | No Log Redaction Middleware | [agent-11/P3-003-no-log-redaction-middleware.md](agent-11/P3-003-no-log-redaction-middleware.md) |
| A12-P3-001 | Polish Batch | [agent-12/P3-001-polish-batch.md](agent-12/P3-001-polish-batch.md) |

