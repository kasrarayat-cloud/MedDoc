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
| Consolidated draft PR | FAIL | Branch is not yet pushed and PR is not yet created. |
| All migrations additive/ordered and rollback-safe | FAIL | Ten migrations ordered; post-contract old-image rollback needs closure. |
| Default rollout off and ordinary visits unchanged | FAIL | Static evidence exists; final integration verification pending. |
| No production synthetic-only bypass | FAIL | Final diff review and tests pending. |
| Identical-manifest base/head test census | FAIL | Not run for consolidated exact head. |
| Independent exact-head integration review | FAIL | Not run. |
| Native blank/fillable DOCX GA matrix | FAIL | Existing safe-alpha boundary is incomplete for requested GA scope. |
| Completed Document → Template Candidate | FAIL | Separate workflow absent. |
| Real malware-scan attestation and quarantine | FAIL | Production scanner contract/readiness unproven. |
| Exact core source-evidence anchors | FAIL | Missing/non-exact evidence may currently populate with null offsets. |
| Database and audit least privilege | FAIL | Runtime role is a superuser/owner with unrestricted `audit_logs` mutation. |
| Object-storage least privilege | FAIL | Runtime services use MinIO root credentials. |
| Internal service transport encryption | FAIL | PostgreSQL, Redis, and MinIO service traffic is plaintext. |
| Storage write capacity/versioning/lifecycle | FAIL | Recent storage-full events; durability controls and write-capacity checks absent. |
| Clinical-quality evaluation and thresholds | HUMAN PENDING | Technical evaluation and Clinical Safety signature required. |
| Open XML and LibreOffice exact-head evidence | FAIL | Must rerun on final SHA. |
| Desktop Microsoft Word returned evidence | HUMAN PENDING | Mandatory external review. |
| Privacy/Legal approval | HUMAN PENDING | Approval packet and signature required. |
| Clinical Safety approval | HUMAN PENDING | Approval packet and signature required. |
| Operations approval | HUMAN PENDING | Approval packet and named ownership required. |
| Frozen release candidate and independent ACCEPT | FAIL | Not created/reviewed. |
| All CI/new-diff/security/secret gates green | FAIL | Final exact-head run pending. |
| Immutable image build/sign/tag/digests | FAIL | Final exact-SHA images not built. |
| Production migration | FAIL | Not authorized. |
| Canary, 10%, 25%, 50%, 100% checkpoints | FAIL | Current production availability is 0%. |
| Stable 100% authorized-physician availability | FAIL | Do not report released. |
