# Template Twin GA decisions and blocker register

Last updated: 2026-07-19T06:13:48Z

## Decisions

| ID | Decision | Rationale | State |
|---|---|---|---|
| D-001 | Treat `/opt/meddoc-pro` as read-only and use an independent clone under `/home/claude/release-programs`. | The protected worktree contains unrelated user work. | ACTIVE |
| D-002 | Use repository-native `npm ci`; do not introduce pnpm. | The repository has `package-lock.json`, npm workspaces, and no pnpm lockfile. | ACTIVE |
| D-003 | Preserve PRs #362–#370 unchanged and integrate their complete linear history with a merge commit from current `origin/main`. | Retains audited commit history and avoids rebasing or squashing accepted evidence. | COMPLETE |
| D-004 | Never restore a PHI-bearing production dump into engineering/QA. Prove live schema restore separately and use only synthetic data for data-bearing migration/restore rehearsals. | Explicit no-real-PHI boundary overrides convenience. | ACTIVE |
| D-005 | Preserve the exact running pre-release images before any cache cleanup or release build. | Current production has no clean source SHA and its running images were untagged. | COMPLETE |
| D-006 | Keep Template Twin globally and per-practice disabled until all technical and human gates pass. | Existing environment, database-global, and practice gates are fail-closed. | ACTIVE |

## Technical blockers

| ID | Severity | Gate | Evidence | Required closure | Status |
|---|---|---|---|---|---|
| B-001 | P0 | Production provenance | Running worker equals clean `origin/main` plus six uncommitted source/test changes; images have no revision label or registry digest. | Replace only through an exact-SHA, signed/digested release and retain the archived current image IDs for rollback. | FAIL |
| B-002 | P0 | Safe rollback after DB contract | The lineage contract removes the mixed-version insert trigger while the current app predates the required `lineageId`; ordinary template creation after app rollback is not yet proven. | Retain a backwards-compatible transition/default boundary through the rollback window or independently prove old-image compatibility after contract. | FAIL |
| B-003 | P0 | Complete restore | Local dump gzip and live-schema restore pass, but no PHI-safe evidence yet proves full production data/object-store restoration, PITR, or queue recovery. | Complete synthetic data-bearing DB/object restore rehearsals and obtain authorized offsite-key/provider evidence without exposing PHI. | FAIL |
| B-004 | P0 | Object storage durability | Versioning, object lock/immutability, encryption/KMS, lifecycle, legal hold, deletion behavior, and offsite restore evidence are not yet complete. | Verified production policy evidence and a synthetic restore drill. | FAIL |
| B-005 | P1 | GA compatibility | Repeating rows and several complex/merged structures are inventory-only/blocked; the separate Completed Document → Template Candidate workflow is absent. | Implement, test, document, and independently review a bounded fail-closed workflow. | FAIL |
| B-006 | P1 | Malware admission | Existing code claims scanner/privacy evidence but production-grade malware attestation and infrastructure ownership must be verified. | Require a real scanner attestation contract and production scanner readiness; no synthetic bypass. | FAIL |
| B-007 | P1 | Admin operations | Accepted stack intentionally exposes no production HTTP/admin surface for controlled rollout mutation. | Add separately authorized, audited, fresh-admin-session controls in `admin.quillmd.com`. | FAIL |
| B-008 | P1 | Clinical quality | No signed thresholds or representative multispecialty provider-quality report exists for the requested boundary. | Complete synthetic evaluation; Clinical Safety sets and signs thresholds. | FAIL |
| B-009 | P1 | Monitoring | Health reports `minio-orphan-cleanup` never ran and `stuck-visit-watchdog` last ran in May; release-specific alerts/owners are not proven. | Repair/verify heartbeat semantics and establish named alert ownership before rollout. | FAIL |
| B-010 | P1 | Human-package CI scope | The existing human-gate workflow runs only when the PR head branch is `feat/template-twin-wm-iov-compatibility-v1`, so a consolidated release PR skips it. | Generalize safely to exact consolidated release heads and regenerate the package. | FAIL |
| B-011 | P0 | Exact clinical evidence anchors | Core L3 facts may remain `direct` and populate with `sourceTranscriptOffsets: null` when a model-provided evidence quote is absent from the canonical source; signing revalidates the derived fact rather than the source span. | Require an exact source-bound span and immutable source identity/hash for every populated core fact; unresolved anchors must block review/signing/download, with deterministic tests and independent review. | FAIL |
| B-012 | P0 | Database/audit least privilege | Production app and worker use the sole PostgreSQL login, which is `SUPERUSER`, owns `audit_logs`, and can INSERT/UPDATE/DELETE/TRUNCATE it. | Introduce separately scoped owner, migrator, application, audit-writer, and backup roles; rehearse grants and prove audit immutability without destructive production changes. | FAIL |
| B-013 | P0 | Object-store least privilege | Production app and worker use the MinIO root identity and secret rather than a scoped service account. | Provision and rehearse least-privilege application/scanner/reconciler identities and rotate root usage out of runtime configuration. | FAIL |
| B-014 | P0 | Backup/PITR | PostgreSQL `archive_mode=off`; backups are plain gzip on the root filesystem, no offsite schedule/key evidence exists, and full DB/object restore remains unproven. | Establish encrypted offsite backups, PITR, synthetic full restore and object restore evidence, then obtain operational ownership approval. | FAIL |
| B-015 | P1 | Storage capacity and durability | MinIO recorded 76 `StorageFull` events July 16–17; filesystem is 84% used, while health checks only bucket existence. Versioning, object lock/lifecycle, and orphan reconciliation are absent/disabled. | Investigate the event window, create headroom and write-capacity alerts, configure required durability controls, and rehearse recovery. | FAIL |
| B-016 | P1 | Internal transport | PostgreSQL SSL is off, Redis has neither TLS nor authentication, and MinIO client TLS is off on the private Docker network. | Implement and rehearse authenticated encrypted service transport, or obtain an explicit scoped human risk decision if policy is formally changed. | FAIL |
| B-017 | P1 | Provider ownership | Durable claim/unknown-outcome protection covers L7 fanout but not L1–L6 or Template Twin custom extraction. | Extend the provider-ownership contract across the released path or obtain independent proof of an equally strong outcome contract. | FAIL |
| B-018 | P1 | DOCX admission and Office boundary | Uploads are not demonstrably quarantined before admission; real scanner attestation, metadata minimization, hidden-content policy, completed-document conversion, full Office corpus, and returned-Word validation are incomplete. | Implement the bounded workflows, expand corpus and validation, and obtain exact-head desktop Word evidence. | FAIL |

## Human gates

| ID | Decision owner | Exact decision/evidence required | Status |
|---|---|---|---|
| H-001 | Desktop Microsoft Word reviewer | No repair warning; layout, field placement, pagination/fonts, save/reopen, and PDF export all pass for the exact final SHA package. | HUMAN PENDING |
| H-002 | Clinical Safety | Signed thresholds, results acceptance, specialty limitations, evidence policy, unknown behavior, and rollback criteria. | HUMAN PENDING |
| H-003 | Privacy/Legal | HIPAA/BAA/provider handling, retention, legal hold, deletion, export/DSR, breach ownership, and static-media policy. | HUMAN PENDING |
| H-004 | Operations | Named deployment, monitoring, migration, kill-switch, rollback, support, and incident owners; approved window. | HUMAN PENDING |
| H-005 | Authorized practice physician/administrator | Field intent and exact-byte media decisions through authenticated workflows; no founder substitution. | HUMAN PENDING |
