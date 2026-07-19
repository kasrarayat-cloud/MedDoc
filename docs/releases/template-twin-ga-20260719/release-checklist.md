# Template Twin GA release checklist

Only `PASS`, `FAIL`, and `HUMAN PENDING` are release states. A `FAIL` may simply mean the gate has not yet been executed; it is never green by implication.

| Gate | Status | Evidence / next requirement |
|---|---|---|
| Equivalent repository preflight recorded | PASS | `docs/preflight-reports/preflight-20260719T055320Z.md` |
| Protected worktree preserved | PASS | Read-only status recorded; release clone is independent. |
| Remote heads and PR states verified | PASS | Main `1be1019`; accepted head `79c04e8`; PRs #362–#370 open drafts. |
| Current production source SHA verified | FAIL | Current images were built from uncommitted source. |
| Current rollback images preserved | PASS | Exact IDs, local tags, mode-0600 archive, SHA-256 recorded. |
| Production backup freshness/integrity | PASS | Daily local gzip passed integrity at 2026-07-19T00:00Z. |
| Production schema restore without PHI | PASS | 30/30 public tables restored to isolated tmpfs PostgreSQL. |
| Full DB/PITR/object/queue restore | FAIL | Not yet proven with approved synthetic/offsite evidence. |
| Complete production infrastructure inventory | PASS | Read-only census completed; its failures gate production but the inventory itself is recorded. |
| Consolidated branch | PASS | Two-parent merge `719eea4`; tree equals accepted `79c04e8` exactly. |
| Consolidated draft PR | PASS | Draft PR #371 targets `main`; published head `9088f74` is intentionally stale while local additive head `2014ec2` remains under review. |
| All migrations additive/ordered and rollback-safe | FAIL | All 86 current migrations apply from zero in disposable PostgreSQL; rollback v4 fresh/data-bearing proofs pass. Detached review, final control-plane integration, and complete rollback rehearsal remain pending. |
| Default rollout off and ordinary visits unchanged | FAIL | Static evidence exists; final integration verification pending. |
| No production synthetic-only bypass | FAIL | Runtime legacy-source bypass is closed at `9088f74` with 138 focused tests; database activation enforcement, final diff review, and exact-head tests remain pending. |
| Initial identical-manifest base/head test census | PASS | Base 143 files/1,895 tests and head 143 files/1,925 tests pass; head total is 270 files/3,264 tests. |
| Final exact-head identical-manifest census | FAIL | Must rerun after all corrective commits and frozen RC. |
| Independent exact-head integration review | FAIL | Not run. |
| Native blank/fillable DOCX GA matrix | FAIL | Bounded compatibility hardening and explicit unsupported matrix are integrated through `5cafc12`; author corpus/Open XML/LibreOffice evidence passes, but detached and final-head review remain pending. |
| Completed Document → Template Candidate | PASS | Separate workflow integrated through `1edc68c`; detached exact `a0c142bc` review returned ACCEPT with no P0/P1/P2 findings. Final integration review still applies. |
| Real malware-scan attestation and quarantine | FAIL | Independent review rejected enum/client consistency, canonical SQL receipt proof, and deployment readiness; isolated remediation is in progress. |
| Exact core source-evidence anchors | FAIL | Canonical-source reconstruction and review/sign/download revalidation are implemented at `581b5b5`; independent exact-head ACCEPT is pending. |
| Database and audit least privilege | FAIL | Runtime role is a superuser/owner with unrestricted `audit_logs` mutation. |
| Object-storage least privilege | FAIL | Runtime services use MinIO root credentials. |
| Internal service transport encryption | FAIL | PostgreSQL, Redis, and MinIO service traffic is plaintext. |
| Storage write capacity/versioning/lifecycle | FAIL | Recent storage-full events; durability controls and write-capacity checks absent. |
| Clinical-quality evaluation and thresholds | HUMAN PENDING | Technical evaluation and Clinical Safety signature required. |
| Open XML and LibreOffice exact-head evidence | FAIL | Independent review rejected package-origin binding, stale validator-report acceptance, and ignored structural drift; additive remediation and final-SHA execution remain pending. |
| Desktop Microsoft Word returned evidence | HUMAN PENDING | Mandatory external review. |
| Privacy/Legal approval | HUMAN PENDING | Approval packet and signature required. |
| Clinical Safety approval | HUMAN PENDING | Approval packet and signature required. |
| Operations approval | HUMAN PENDING | Approval packet and named ownership required. |
| Frozen release candidate and independent ACCEPT | FAIL | Not created/reviewed. |
| All CI/new-diff/security/secret gates green | FAIL | Local full unit, strict TypeScript, production app build, high/critical audit, and verified-only secret scan pass through `2014ec2`; final exact-head CI and remaining gates are pending. |
| Immutable image build/sign/tag/digests | FAIL | Final exact-SHA images not built. |
| Production migration | FAIL | Not authorized. |
| Canary, 10%, 25%, 50%, 100% checkpoints | FAIL | Current production availability is 0%. |
| Stable 100% authorized-physician availability | FAIL | Do not report released. |
