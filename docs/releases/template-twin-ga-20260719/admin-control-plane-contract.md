# Template Twin production control-plane contract

Status: IMPLEMENTED AND PG-VERIFIED — independent exact-head review pending
Date: 2026-07-19 UTC

## Purpose

The control plane is the only application workflow allowed to move Template
Twin from globally disabled through Canary, 10%, 25%, 50%, and 100%. It does
not grant approval authority, manufacture evidence, or infer that an uploaded
file is safe. It binds human decisions and technical evidence to one immutable
release identity, then serializes each exposure change with the existing
rollout and rollback locks.

## Release identity

One frozen release candidate binds:

- 40-character source and base commit SHAs;
- application, worker, and migrator OCI digests;
- identical-manifest base/head test-census evidence hash;
- independent exact-head review evidence hash;
- security and secret-scan evidence hash;
- migration/restore-rehearsal evidence hash;
- Office corpus and returned desktop Word evidence hash;
- a versioned, PHI-free guardrail-policy document hash;
- a release-specific authorized-practice manifest hash.

The server computes `releaseIdentitySha256` from a versioned canonical encoding
of those values. Once frozen, identity-bearing columns are immutable. Every
approval, checkpoint, metric snapshot, and audit event repeats that identity.
Any mismatch is ineligible; evidence is never silently carried to a new SHA or
image.

Runtime advancement additionally requires the deployed process to attest the
same commit and image identity through deployment-injected, non-secret
environment values. A missing value fails closed.

## Human authority

Required human disciplines are:

- Desktop Microsoft Word reviewer;
- Clinical Safety;
- Privacy/Legal;
- Operations.

Authority assignments are provisioned out of band and have no self-service
admin API in the GA release. The database starts with no authorities. An
authenticated, MFA-verified SUPER_ADMIN can record a decision only when the
current user has an active authority assignment for that discipline. The
release creator/finalizer cannot approve the same release. Decisions are an
append-only APPROVE, REJECT, or REVOKE ledger with evidence SHA-256, typed
confirmation, decision time, session-bound actor, and audit-outbox receipt.

Codex, CI, and provider processes cannot occupy human authority rows.

## Authorized population

Exposure remains practice-scoped. A frozen release manifest lists the practices
that Operations has authorized and records a PHI-free snapshot count of active,
product-entitled physicians for each practice. The manifest stores no patient
or document data.

Each practice receives a stable cohort rank before freeze. Canary practices are
explicit. Later checkpoints select a cumulative prefix of the stable ranked
manifest until the target physician count is met. Because practices are
indivisible, the UI and ledger show both target and actual physician exposure;
they never claim an exact percentage when practice granularity causes an
overshoot. The 100% checkpoint must include every practice in the frozen
authorized manifest and re-census current authorized physicians before it can
complete.

## State machine

Release candidate:

`DRAFT → FROZEN → APPROVED → ROLLING_OUT → STABLE_100`

Any post-freeze evidence or approval failure moves to `REJECTED`; any rollout
revoke moves to `REVOKED`. Neither state can return to rollout. A new release
identity is required.

Checkpoint:

`PENDING → ACTIVE → PASSED`

An ACTIVE checkpoint can instead become `FAILED` or `REVOKED`. Only the next
ordered checkpoint can activate, only after the previous checkpoint is PASSED.
No checkpoint can be skipped or edited after activation.

## Advancement transaction

Every state-changing request must:

1. pass the dedicated-host, live account/session, entitlement, expiry,
   force-logout, and MFA gate;
2. pass same-origin validation and exact typed confirmation;
3. start a serializable database transaction and take PostgreSQL advisory lock
   `(73119, 20260719)` before any release, rollout, practice, or operation row;
4. lock the global rollout row, release candidate, current checkpoint, required
   approvals, and affected practices in deterministic order;
5. re-compute release identity, current runtime identity, human decisions,
   rollback fence, lineage contract, guardrail state, stage order, and bake time;
6. set a transaction-local checkpoint capability used by database triggers;
7. enable only the cumulative practices assigned to that checkpoint, using the
   existing global-then-practice rollout-generation order;
8. persist the checkpoint decision and audit outbox in the same commit.

The commit is the linearization point. Stale enabling actions and direct rollout
updates lose closed. Exact-identity human/operational revocations and critical
guardrail snapshots are monotonic: if an advance/pass commits first, the
waiting safety action observes that generation and still disables exposure
before it returns.

Database triggers reject global/practice enablement without a matching ACTIVE
checkpoint capability, protect all release/approval/checkpoint history from
UPDATE/DELETE/TRUNCATE, and preserve the existing rollback entry fences.

## Metric snapshot and guardrails

Metrics are aggregate, PHI-free counts/rates only. The accepted key set is
versioned; arbitrary JSON keys, strings containing encounter data, free text,
user/patient/document identifiers, and evidence quotes are rejected. Each
snapshot includes its canonical SHA-256 and observation interval.

At minimum the policy covers:

- failed template uploads and malware/inspection failures;
- render and verification-contract-v2 failures;
- sign/download blocks and unsafe bypass attempts;
- audit-outbox delivery lag/failure;
- object storage and queue failures;
- provider failures and ambiguous outcomes;
- p95/p99 latency and error rate;
- critical-field, negation, laterality, dropdown, table-placement, evidence
  anchor, unsupported-field, and hallucination thresholds approved by Clinical
  Safety.

Thresholds remain HUMAN PENDING until Clinical Safety signs the exact policy.
An absent metric, insufficient sample/bake interval, stale observation, or
threshold breach blocks PASS. A critical breach atomically disables the global
database rollout gate, marks the release/checkpoint revoked, and emits the audit
outbox event before returning. The operator then follows the audited rollback
runbook; a browser action is not the safety boundary.

## Required tests

- fresh and data-bearing migration, idempotency, interruption, and rollback
  rehearsal;
- direct SQL enablement rejected with no checkpoint capability;
- forged/stale capability and cross-release identity rejected;
- exact-SHA/image/evidence mismatch rejected;
- missing, self-authored, wrong-discipline, rejected, revoked, or stale human
  approval rejected;
- actual two-session advance/advance, advance/revoke, approval-revoke/advance,
  global-kill/advance, and critical-guardrail/pass races;
- stage skip, replay, duplicated request, stale generation, and target overshoot
  reporting;
- 100% completeness against the frozen manifest and fresh physician census;
- immutable decision/audit history, exact outbox receipt, DELETE/TRUNCATE
  resistance, and account-deletion behavior;
- PHI-like metric keys/values and unsupported metric schemas rejected;
- responsive, keyboard, screen-reader, focus, contrast, and 44 px interaction
  tests for the admin workbench.
